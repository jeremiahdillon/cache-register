"""The Ramp AI Index views ("cuts") and the parser for their "Get the data" text.

Each view on ramp.com/data/ai-index copies its full history to the clipboard as tab-separated text:
one header row, ISO dates, empty cells for missing values, LF line endings and no trailing newline
(CRLF, a BOM and a trailing newline are tolerated too). Row order varies by view and column order
varies between wide views with the same columns, so neither is relied on.

The paste does not name its view, so the author declares it (`--cut`). The header is checked where
it can tell views apart: long views must match exactly; wide views by column name (`Date` first,
the cut's anchor columns present, every other column matching the cut's pattern). The three price
views share one header, and Token volume and Token spend share one column set; marts 062 check those
with the data (`ramp_price_check`, `ramp_token_check`).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date

PAGE = "https://ramp.com/data/ai-index"
NUMBER = re.compile(r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?")  # plain decimals or scientific notation
ANY = r".+"


@dataclass(frozen=True)
class Cut:
    id: str
    menu: str  # primary : secondary, as on the page
    url: str  # the page URL that shows the view (the bare page where the fragment was not recorded)
    table: str  # staged table the rows go to
    shape: str  # "long" (Date, key, values…) | "wide" (Date, one column per series)
    grain: str  # "month" (1st) | "week" (Sunday ending a Monday–Sunday week) | "day"
    columns: tuple[str, ...]  # long: the exact header; wide: required anchors after Date
    pattern: str = ANY  # wide: every non-anchor column must match
    text_columns: tuple[str, ...] = ()  # long: non-numeric value columns

    @property
    def file_name(self) -> str:
        return self.id.replace("/", "__") + ".tsv"


ADOPTION = ("Adoption rate (%)", "Monthly change (pp)")
YOY = "Yearly change (pp)"
PER_EMPLOYEE = "Median (USD / employee / month)"
LABS = ("OpenAI", "Anthropic")
PRICES = ("OpenAI & Anthropic", "OpenAI", "Anthropic")

# In the order of the monthly routine (the page's menu order).
CUTS: tuple[Cut, ...] = (
    Cut("adoption/overall", "Adoption : Overall", f"{PAGE}#adoption#overall", "adoption", "long", "month",
        ("Date", "Series", *ADOPTION, YOY, "Census question version"), text_columns=("Census question version",)),
    Cut("adoption/models", "Adoption : Overall + Models", PAGE, "adoption", "long", "month",
        ("Date", "Series", *ADOPTION, YOY)),
    Cut("adoption/sector", "Adoption : Sector", f"{PAGE}#adoption#sector", "adoption", "long", "month",
        ("Date", "Sector", *ADOPTION)),
    Cut("adoption/size", "Adoption : Business size", f"{PAGE}#adoption#business-size", "adoption", "long",
        "month", ("Date", "Business size", *ADOPTION)),
    Cut("spend_per_employee/overall", "AI spend per employee : Overall", f"{PAGE}#spend-per-employee#overall",
        "spend_per_employee", "wide", "month",
        (PER_EMPLOYEE, "Top 10% (USD / employee / month)", "Top 1% (USD / employee / month)"),
        pattern=r".+ \(USD / employee / month\)"),
    Cut("spend_per_employee/sector", "AI spend per employee : Sector", PAGE, "spend_per_employee", "long",
        "month", ("Date", "Sector", PER_EMPLOYEE)),
    Cut("spend_per_employee/size", "AI spend per employee : Business size",
        f"{PAGE}#spend-per-employee#business-size", "spend_per_employee", "long", "month",
        ("Date", "Business size", PER_EMPLOYEE)),
    Cut("spend_share/overall", "AI share of business spend : Overall", f"{PAGE}#ai-share-of-business-spend#overall",
        "spend_share", "wide", "month", ("AI share of business spend (%)",), pattern=r".+ \(%\)"),
    Cut("token_volume/maker", "Token volume : By model maker (Volumes)",
        f"{PAGE}?metric=token-volume&detail=maker&mode=volume", "token_index", "wide", "week", LABS),
    Cut("token_spend/maker", "Token spend : By model maker (Volumes)",
        f"{PAGE}?metric=token-spend&detail=maker&mode=volume", "token_index", "wide", "week", LABS),
    Cut("token_price/blended", "Token prices : Blended", f"{PAGE}?metric=token-price&detail=blended",
        "token_price", "wide", "day", PRICES),
    Cut("token_price/input", "Token prices : Input", f"{PAGE}?metric=token-price&detail=input",
        "token_price", "wide", "day", PRICES),
    Cut("token_price/output", "Token prices : Output", f"{PAGE}?metric=token-price&detail=output",
        "token_price", "wide", "day", PRICES),
)  # fmt: skip
BY_ID = {c.id: c for c in CUTS}


def get(cut_id: str | None) -> Cut:
    if cut_id not in BY_ID:
        raise ValueError(f"unknown cut {cut_id!r}; run the import without --cut to list the cuts")
    return BY_ID[cut_id]


def listing() -> str:
    return "\n".join(f"  {c.id:<28} {c.menu:<42} {c.url}" for c in CUTS)


@dataclass(frozen=True)
class Cell:
    period: date
    key: str  # long: the row's label (Series, Sector, Business size); wide: the column name
    column: str  # long: the value column; wide: "value"
    value: float | str | None


def _number(text: str, where: str) -> float | None:
    if text == "":
        return None
    if not NUMBER.fullmatch(text):  # float() would also take "1_000", "nan", "inf"
        raise ValueError(f"{where}: {text!r} is not a number")
    x = float(text)
    if not math.isfinite(x):  # e.g. 1e999
        raise ValueError(f"{where}: {text!r} is not a finite number")
    return x


def _period(text: str, grain: str, where: str) -> date:
    try:
        d = date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"{where}: {text!r} is not an ISO date") from None
    if grain == "month" and d.day != 1:
        raise ValueError(f"{where}: {text} is not the first of a month")
    if grain == "week" and d.weekday() != 6:
        raise ValueError(f"{where}: {text} is not a Sunday")
    return d


def _lines(body: bytes) -> list[list[str]]:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("not UTF-8 text") from None
    text = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    if not text.strip():
        raise ValueError("empty input")
    return [line.split("\t") for line in text.split("\n")]


def _check_header(header: list[str], cut: Cut) -> None:
    if cut.shape == "long":
        if header != list(cut.columns):
            raise ValueError(f"header {header} does not match {cut.id} (expected {list(cut.columns)})")
        return
    if header[0] != "Date":
        raise ValueError(f"header does not start with Date (got {header[0]!r}) for {cut.id}")
    names = header[1:]
    if len(names) != len(set(names)) or "" in names:
        raise ValueError(f"header has empty or repeated columns for {cut.id}")
    missing = [a for a in cut.columns if a not in names]
    if missing:
        raise ValueError(f"header lacks {missing} for {cut.id}")
    odd = [n for n in names if n not in cut.columns and not re.fullmatch(cut.pattern, n)]
    if odd:
        raise ValueError(f"header has columns {odd} that do not belong to {cut.id}")


def parse(body: bytes, cut: Cut) -> list[Cell]:
    """Validate a whole paste for `cut` and return its cells; raise ValueError on anything off."""
    rows = _lines(body)
    header = rows[0]
    while len(header) > 1 and header[-1] == "":  # a trailing tab
        header = header[:-1]
    _check_header(header, cut)
    if len(rows) < 2:
        raise ValueError(f"{cut.id}: no data rows")
    cells, keys = [], set()
    for n, fields in enumerate(rows[1:], start=2):
        where = f"{cut.id} line {n}"
        if len(fields) > len(header):
            if any(f != "" for f in fields[len(header) :]):
                raise ValueError(f"{where}: more fields than the header")
            fields = fields[: len(header)]
        fields = fields + [""] * (len(header) - len(fields))  # trailing empty cells may be cut off
        period = _period(fields[0], cut.grain, where)
        if cut.shape == "long":
            key = fields[1].strip()
            if not key:
                raise ValueError(f"{where}: empty {header[1]}")
            if (period, key) in keys:
                raise ValueError(f"{where}: duplicate row for {period} {key!r}")
            keys.add((period, key))
            for col, text in zip(header[2:], fields[2:], strict=True):
                text = text.strip()
                value = (text or None) if col in cut.text_columns else _number(text, f"{where} {col}")
                cells.append(Cell(period, key, col, value))
        else:
            if period in keys:
                raise ValueError(f"{where}: duplicate row for {period}")
            keys.add(period)
            for col, text in zip(header[1:], fields[1:], strict=True):
                cells.append(Cell(period, col, "value", _number(text.strip(), f"{where} {col}")))
    return cells

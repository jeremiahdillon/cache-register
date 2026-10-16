"""The curated asset-values file: its columns, validation and the append-only rule.

`config/curated/asset_values.csv` holds one row per stated figure about what an asset was worth,
cost or was assumed to last: GPUs and AI infrastructure, and the fiber of the dot-com build-out
(docs/plans/2026-10-14-gpu-vs-fiber.md). `config/curated/asset_vocab.yaml` is its controlled
vocabulary: the assets and the metrics, each metric with the units it may be stated in. Values stay
in the unit the source used; analyses convert. Validation is shared by `fetch`, `stage` and the tests;
it catches a quote pasted against the wrong row or a mis-normalised value, not a misread source.

`check_append_only(old, new)` refuses an edited or removed row. It runs in the pre-push hook and in
CI (`python -m cachereg.sources.curated_asset_values.dataset --base <sha> [--head <sha>]`).
"""

from __future__ import annotations

import math
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from cachereg.core.paths import REPO_ROOT
from cachereg.sources import _curated
from cachereg.sources._curated import MAX_QUOTE_WORDS, CuratedError, norm, parse_stated

CURATED_DIR = REPO_ROOT / "config" / "curated"
FILE = "asset_values.csv"
VOCAB = "asset_vocab.yaml"
REPO_PATH = f"config/curated/{FILE}"  # for `git show <sha>:<path>`

COLUMNS = (
    "id", "statement_date", "asset", "entity", "metric", "value_as_stated", "value", "unit", "qualifier",
    "period_start", "period_end", "scope", "source_url", "source_kind", "source_quote", "recorded_on",
    "supersedes", "notes",
)  # fmt: skip
REQUIRED = tuple(c for c in COLUMNS if c not in ("supersedes", "notes"))
QUALIFIERS = ("exact", "over", "about", "under", "up_to", "range_low", "range_high")
SOURCE_KINDS = ("primary", "secondary")
SUFFIX = re.compile(r"[2-9]|[1-9]\d+")  # the n of a second, third, … row with the same base id
ERAS = ("ai", "dotcom")
LAYERS = ("equipment", "infrastructure", "company", "mixed")


def load_vocab(path: Path | None = None) -> dict:
    """`{assets: {id: {label, era, layer}}, metrics: {id: {units: [...], definition}}}`, checked."""
    data = yaml.safe_load((path or CURATED_DIR / VOCAB).read_text()) or {}
    return check_vocab(data)


def check_vocab(data: dict) -> dict:
    assets, metrics = data.get("assets") or {}, data.get("metrics") or {}
    for name, a in assets.items():
        if not isinstance(a, dict) or not a.get("label") or a.get("era") not in ERAS or a.get("layer") not in LAYERS:
            raise CuratedError(f"{VOCAB}: asset {name!r} needs a label, an era in {ERAS} and a layer in {LAYERS}")
    for name, m in metrics.items():
        if not isinstance(m, dict) or not m.get("definition") or not m.get("units"):
            raise CuratedError(f"{VOCAB}: metric {name!r} needs a definition and units")
    return {"assets": assets, "metrics": metrics}


def parse_figure(text: str) -> tuple[Decimal, bool, bool, str | None]:
    """`value_as_stated` → (value, has `$`, has a trailing `+`, suffix). The shared parser, plus an
    optional trailing `%` or the word `percent` (suffix `%`), or `x` / `×` after a digit (a multiple,
    suffix `x`)."""
    text = text.strip()
    suffix = None
    for end, kind in (("%", "%"), (" percent", "%"), ("x", "x"), ("×", "x")):
        if text.lower().endswith(end) and (kind == "%" or text[: -len(end)][-1:].isdigit()):
            text, suffix = text[: -len(end)].rstrip(), kind
            break
    value, currency, plus = parse_stated(text)
    return value, currency, plus, suffix


def read_rows(body: bytes) -> list[dict]:
    """Parse the CSV (UTF-8, header row) without validating it."""
    return _curated.read_rows(body, COLUMNS, FILE)


def _day(row: dict, col: str) -> date:
    try:
        return date.fromisoformat(row[col])
    except ValueError:
        raise CuratedError(f"{row['id']}: {col} {row[col]!r} is not an ISO date") from None


def validate(body: bytes, vocab: dict | None = None) -> list[dict]:
    """Every rule of the plan; returns the rows. Raises CuratedError on the first broken rule."""
    vocab = load_vocab() if vocab is None else check_vocab(vocab)
    assets, metrics = vocab["assets"], vocab["metrics"]
    rows = read_rows(body)
    seen: dict[str, dict] = {}
    superseded: set[str] = set()
    for r in rows:
        rid = r["id"]
        for col in REQUIRED:
            if not r[col].strip():
                raise CuratedError(f"{rid or '(no id)'}: {col} is empty")
        if r != {k: v.strip() for k, v in r.items()}:
            raise CuratedError(f"{rid}: a field has leading or trailing spaces")
        if rid in seen:
            raise CuratedError(f"{rid}: id is not unique")
        stated, period_start, period_end = _day(r, "statement_date"), _day(r, "period_start"), _day(r, "period_end")
        recorded = _day(r, "recorded_on")
        if period_start > period_end:
            raise CuratedError(f"{rid}: period_start is after period_end")
        if stated > recorded:
            raise CuratedError(f"{rid}: statement_date is after recorded_on")
        base = f"{r['asset']}-{r['metric']}-{r['statement_date']}"
        if rid != base and not (rid.startswith(base + "-") and SUFFIX.fullmatch(rid.removeprefix(base + "-"))):
            raise CuratedError(f"{rid}: id must be <asset>-<metric>-<statement_date>[-n]")
        if r["asset"] not in assets:
            raise CuratedError(f"{rid}: asset {r['asset']!r} is not in {VOCAB}")
        if r["metric"] not in metrics:
            raise CuratedError(f"{rid}: metric {r['metric']!r} is not in {VOCAB}")
        units = metrics[r["metric"]]["units"]
        if r["unit"] not in units:
            raise CuratedError(f"{rid}: unit {r['unit']!r}; metric {r['metric']} is stated in {', '.join(units)}")
        try:
            value = Decimal(r["value"])
        except InvalidOperation:
            raise CuratedError(f"{rid}: value {r['value']!r} is not a number") from None
        if not value.is_finite() or value <= 0 or not math.isfinite(float(value)):
            raise CuratedError(f"{rid}: value must be finite and > 0")
        if r["qualifier"] not in QUALIFIERS:
            raise CuratedError(f"{rid}: qualifier must be one of {', '.join(QUALIFIERS)}")
        if r["source_kind"] not in SOURCE_KINDS:
            raise CuratedError(f"{rid}: source_kind must be primary or secondary")
        if not r["source_url"].startswith("https://"):
            raise CuratedError(f"{rid}: source_url must be https")
        if len(r["source_quote"].split()) > MAX_QUOTE_WORDS:
            raise CuratedError(f"{rid}: source_quote is longer than {MAX_QUOTE_WORDS} words")
        if norm(r["value_as_stated"]) not in norm(r["source_quote"]):
            raise CuratedError(f"{rid}: source_quote does not contain {r['value_as_stated']!r}")
        parsed, currency, plus, suffix = parse_figure(r["value_as_stated"])
        if parsed != value:
            raise CuratedError(f"{rid}: {r['value_as_stated']!r} reads as {parsed}, not value {r['value']}")
        if currency and not r["unit"].startswith("usd"):
            raise CuratedError(f"{rid}: a $ figure needs a usd unit, not {r['unit']}")
        if suffix == "%" and r["unit"] != "percent":  # "70" of "70-80%" is a percent without its own sign
            raise CuratedError(f"{rid}: a % figure has unit percent, not {r['unit']}")
        if suffix == "x" and r["unit"] != "multiple":
            raise CuratedError(f"{rid}: a multiple (x) has unit multiple, not {r['unit']}")
        if plus and r["qualifier"] != "over":
            raise CuratedError(f"{rid}: {r['value_as_stated']!r} ends in + so the qualifier is over")
        if r["supersedes"]:
            old = seen.get(r["supersedes"])
            if old is None:
                raise CuratedError(f"{rid}: supersedes {r['supersedes']!r}, which is not an earlier row")
            if _day(old, "recorded_on") > recorded:
                raise CuratedError(f"{rid}: supersedes a row recorded after it")
            if r["supersedes"] in superseded:
                raise CuratedError(f"{rid}: {r['supersedes']} is already superseded; supersede the newest correction")
            superseded.add(r["supersedes"])
        seen[rid] = r
    return rows


def check_append_only(old: bytes, new: bytes) -> None:
    """No row of `old` may be removed or changed in `new` (rows are only appended)."""
    _curated.check_append_only(old, new, COLUMNS, FILE)


def main(argv: list[str]) -> int:
    """`--base <rev> [--head <rev>]`: the append-only check of the pre-push hook and CI."""
    return _curated.append_only_main(
        argv, module=__spec__.name, label="curated asset values", repo_path=REPO_PATH, columns=COLUMNS
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

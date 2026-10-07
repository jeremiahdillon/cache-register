"""Parse one BTOS workbook into AI cells and cycle dates (used by fetch to validate and by stage).

Estimate sheets are wide: the breakdown's key columns, `Question ID, Question, Answer ID, Answer`,
then one column per cycle (`202619`, newest first). Values are strings like `23.8%`; `S` is a
suppressed cell, `.` a cycle in which the question was not asked. A twin sheet holds the standard
errors in the same layout. Only the two AI questions are read.

The question ID does not mark the November 2025 wording change (both wordings are question 7 and
24), so the wording is read from the question text and must match the file's declared wording; an
AI question in any other wording stops the parse, so a new change is seen, not absorbed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from cachereg.sources import _xlsx
from cachereg.sources.census_btos.files import DATES, File, Table

FIXED = ("Question ID", "Question", "Answer ID", "Answer")
AI_MARK = "Artificial Intelligence (AI)"
QUESTIONS = {
    "ai_current": "In the last two weeks, did this business use Artificial Intelligence (AI) ",
    "ai_expected": "During the next six months, do you think this business will be using Artificial Intelligence (AI) ",
}
WORDINGS = {"original": "in producing goods or services", "current": "in any of its business functions"}
ANSWERS = {"Yes": "yes", "No": "no", "Do not know": "dont_know"}
SIZE_CLASSES = {  # BTOS employment size classes from cycle 202319 on (employees, inclusive)
    "A": (1, 4), "B": (5, 9), "C": (10, 19), "D": (20, 49), "E": (50, 99), "F": (100, 249), "G": (250, None),
}  # fmt: skip
CYCLE = re.compile(r"^\d{4}(0[1-9]|1\d|2[0-6])$")
PCT = re.compile(r"^(\d+(\.\d*)?|\.\d+)%$")
SECTOR_CODE = re.compile(r"^(\d\d|XX)$")
EXCEL_EPOCH = date(1899, 12, 30)
DATE_COLUMNS = {
    "smpdt": "cycle",
    "collection start": "collection_start",
    "col start": "collection_start",
    "col end": "collection_end",
    "reference period start": "reference_start",
    "ref start": "reference_start",
    "ref end": "reference_end",
    "publication date": "publication_date",
    "sample year": "sample_year",
    "cycle": "census_cycle",
    "panel": "panel",
}


@dataclass(frozen=True)
class Cell:
    breakdown: str
    sector_code: str | None
    size_class: str | None
    question: str  # ai_current | ai_expected
    answer: str  # yes | no | dont_know
    cycle: str
    estimate_pct: float | None
    se_pct: float | None
    suppressed: bool

    @property
    def group_key(self) -> str:
        parts = [p for p in (self.sector_code, self.size_class) if p]
        return self.breakdown + (":" + "/".join(parts) if parts else "")


@dataclass(frozen=True)
class Cycle:
    cycle: str
    collection_start: date
    collection_end: date
    reference_start: date
    reference_end: date
    publication_date: date | None
    sample_year: int | None
    census_cycle: int | None
    panel: int | None
    note: str | None  # e.g. SHUTDOWN, as the sheet writes it


@dataclass
class Parsed:
    cells: list[Cell] = field(default_factory=list)
    cycles: dict[str, Cycle] = field(default_factory=dict)
    rejected: int = 0


def _clean(v) -> str:
    return "" if v is None else str(v).strip()


def classify(question: str, wording: str) -> str:
    """ai_current | ai_expected for an AI question in the file's wording; anything else is an error."""
    kind = next((k for k, start in QUESTIONS.items() if question.startswith(start)), None)
    found = [w for w, phrase in WORDINGS.items() if phrase in question]
    if kind is None or len(found) != 1:
        raise ValueError(f"unknown AI question (a new wording?): {question!r}")
    if found[0] != wording:
        raise ValueError(f"{found[0]} wording found in a file declared {wording}: {question!r}")
    return kind


def _value(raw: str) -> tuple[float | None, bool, bool]:
    """(value, suppressed, ok) for one cell; `.` and empty are (None, False, True) and yield no row."""
    if raw in ("", "."):
        return None, False, True
    if raw == "S":
        return None, True, True
    if PCT.match(raw):
        return float(raw[:-1]), False, True
    return None, False, False


def _rows_by_key(sheet: list[list], table: Table, label: str) -> tuple[list[str], dict, int]:
    """(cycle columns, {(keys…, question, answer): row}, rejected rows) for one estimate or SE sheet."""
    if not sheet:
        raise ValueError(f"sheet {label!r} is empty")
    header = [_clean(h) for h in sheet[0]]
    while header and header[-1] == "":
        header.pop()
    n = len(table.keys)
    if tuple(header[: n + 4]) != table.keys + FIXED:
        raise ValueError(f"sheet {label!r}: header starts {header[: n + 4]}, expected {list(table.keys + FIXED)}")
    cycles = header[n + 4 :]
    bad = [c for c in cycles if not CYCLE.match(c)]
    if not cycles or bad:
        raise ValueError(f"sheet {label!r}: cycle columns must be YYYYFF codes; got {bad or 'none'}")
    rows, rejected = {}, 0
    for row in sheet[1:]:
        cells = [_clean(v) for v in row]
        question = cells[n + 1] if len(cells) > n + 1 else ""
        if not question:  # blank rows and the trailing "Source: …" line
            rejected += any(cells[1:])
            continue
        if AI_MARK not in question:
            continue
        key = (*cells[:n], question, cells[n + 3] if len(cells) > n + 3 else "")
        if key in rows:
            raise ValueError(f"sheet {label!r}: duplicate row {key}")
        rows[key] = cells[n + 4 : n + 4 + len(cycles)] + [""] * (len(cycles) - len(cells[n + 4 :]))
    return cycles, rows, rejected


def _table(sheets: dict, table: Table, spec: File, out: Parsed) -> None:
    cycles, est, rejected = _rows_by_key(sheets[table.estimates], table, table.estimates)
    se_cycles, se, se_rejected = _rows_by_key(sheets[table.errors], table, table.errors)
    if se_cycles != cycles:
        raise ValueError(f"{table.errors!r} has other cycle columns than {table.estimates!r}")
    out.rejected += rejected + se_rejected
    n = len(table.keys)
    for key, values in est.items():
        codes, question, answer = key[:n], key[n], key[n + 1]
        kind = classify(question, spec.wording)
        if answer not in ANSWERS:
            raise ValueError(f"{table.estimates!r}: unknown answer {answer!r} to {question!r}")
        sector = codes[table.keys.index("Sector")] if "Sector" in table.keys else None
        size = codes[table.keys.index("Empsize")] if "Empsize" in table.keys else None
        if (sector is not None and not SECTOR_CODE.match(sector)) or (size is not None and size not in SIZE_CLASSES):
            out.rejected += 1
            continue
        errors = se.get(key, [""] * len(cycles))
        for cycle, raw, raw_se in zip(cycles, values, errors, strict=True):
            value, suppressed, ok = _value(raw)
            if not ok:
                out.rejected += 1
                continue
            if value is None and not suppressed:
                continue  # not asked in this cycle
            se_value, _, se_ok = _value(raw_se)
            out.cells.append(
                Cell(table.breakdown, sector, size, kind, ANSWERS[answer], cycle, value,
                     se_value if se_ok and not suppressed else None, suppressed)
            )  # fmt: skip


def _date(raw: str, label: str) -> date | None:
    if raw == "":
        return None
    if re.fullmatch(r"\d+(\.0+)?", raw):
        return EXCEL_EPOCH + timedelta(days=int(float(raw)))
    try:
        return datetime.strptime(raw, "%m/%d/%Y").date()
    except ValueError:
        raise ValueError(f"{DATES!r}: unreadable date {raw!r} in {label}") from None


def _int(raw: str) -> int | None:
    return int(float(raw)) if re.fullmatch(r"\d+(\.0+)?", raw) else None


def parse_dates(sheet: list[list]) -> dict[str, Cycle]:
    if not sheet:
        raise ValueError(f"sheet {DATES!r} is empty")
    header = [_clean(h).lower() for h in sheet[0]]
    cols = {DATE_COLUMNS[h]: i for i, h in enumerate(header) if h in DATE_COLUMNS}
    needed = {"cycle", "collection_start", "collection_end", "reference_start", "reference_end"}
    if needed - cols.keys():
        raise ValueError(f"{DATES!r}: missing columns {sorted(needed - cols.keys())}; header {header}")
    out, sample_year = {}, None
    for row in sheet[1:]:
        cells = [_clean(v) for v in row]

        def get(k: str, cells: list[str] = cells) -> str:
            return cells[cols[k]] if k in cols and cols[k] < len(cells) else ""

        cycle = get("cycle")
        if not CYCLE.match(cycle):
            continue
        year_cell = get("sample_year")
        sample_year = _int(year_cell) if _int(year_cell) is not None else sample_year  # written once per year
        c = Cycle(
            cycle,
            *(_date(get(k), cycle) for k in ("collection_start", "collection_end", "reference_start", "reference_end")),
            _date(get("publication_date"), cycle),
            sample_year if "sample_year" in cols else None,
            _int(get("census_cycle")),
            _int(get("panel")),
            None if year_cell == "" or _int(year_cell) is not None else year_cell,
        )
        if None in (c.collection_start, c.collection_end, c.reference_start, c.reference_end):
            raise ValueError(f"{DATES!r}: cycle {cycle} lacks a collection or reference date")
        if not (c.reference_start <= c.reference_end < c.collection_start <= c.collection_end):
            raise ValueError(f"{DATES!r}: cycle {cycle} dates out of order")
        if cycle in out:
            raise ValueError(f"{DATES!r}: cycle {cycle} listed twice")
        out[cycle] = c
    if not out:
        raise ValueError(f"{DATES!r}: no cycles")
    return out


def parse(body: bytes, spec: File) -> Parsed:
    """Every AI cell of the workbook and its cycle dates; raises ValueError if the file is not usable."""
    sheets = _xlsx.read_sheets(body, spec.sheets)
    out = Parsed(cycles=parse_dates(sheets[DATES]))
    for table in spec.tables:
        _table(sheets, table, spec, out)
    if not out.cells:
        raise ValueError(f"{spec.name}: no AI rows")
    undated = sorted({c.cycle for c in out.cells} - out.cycles.keys())
    if undated:
        raise ValueError(f"{spec.name}: cycles without dates: {undated}")
    return out

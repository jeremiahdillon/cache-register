"""The curated disclosures file: its columns, validation and the append-only rule.

`config/curated/disclosures.csv` holds one row per stated figure (docs/plans/2026-10-08-curated-
disclosures.md); `config/curated/metrics.yaml` is its controlled vocabulary. Validation is shared
by `fetch` (before anything is stored), `stage` and the tests. It catches a quote pasted against
the wrong row or a mis-normalised value, not a misread source (that is the reviewer's job).

`check_append_only(old, new)` refuses an edited or removed row. It runs in the pre-push hook and in
CI (`python -m cachereg.sources.curated_disclosures.dataset --base <sha> [--head <sha>]`), against the
file as it was at the pushed range's base.
"""

from __future__ import annotations

import math
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

from cachereg.core.paths import REPO_ROOT, entities_dir
from cachereg.sources import _curated
from cachereg.sources._curated import MAX_QUOTE_WORDS, CuratedError, parse_stated
from cachereg.sources._curated import norm as _norm

CURATED_DIR = REPO_ROOT / "config" / "curated"
FILE = "disclosures.csv"
METRICS = "metrics.yaml"
REPO_PATH = f"config/curated/{FILE}"  # for `git show <sha>:<path>`

COLUMNS = (
    "id", "statement_date", "entity", "metric", "value_as_stated", "value", "unit", "qualifier",
    "period_start", "period_end", "scope", "source_url", "source_kind", "source_quote", "recorded_on",
    "supersedes", "notes",
)  # fmt: skip
REQUIRED = tuple(c for c in COLUMNS if c not in ("supersedes", "notes"))
QUALIFIERS = ("exact", "over", "about", "under", "up_to")
SOURCE_KINDS = ("primary", "secondary")
SUFFIX = re.compile(r"[2-9]|[1-9]\d+")  # the n of a second, third, … row with the same base id

DisclosureError = CuratedError  # this dataset's name for the shared error


def _day(row: dict, col: str) -> date:
    try:
        return date.fromisoformat(row[col])
    except ValueError:
        raise DisclosureError(f"{row['id']}: {col} {row[col]!r} is not an ISO date") from None


def load_metrics(path: Path | None = None) -> dict[str, dict]:
    data = yaml.safe_load((path or CURATED_DIR / METRICS).read_text()) or {}
    metrics = data.get("metrics") or {}
    for name, m in metrics.items():
        if not isinstance(m, dict) or not m.get("unit") or not m.get("definition"):
            raise DisclosureError(f"{METRICS}: metric {name!r} needs a unit and a definition")
    return metrics


def load_vendors() -> set[str]:
    return set(yaml.safe_load((entities_dir() / "vendors.yaml").read_text())["vendors"])


def read_rows(body: bytes) -> list[dict]:
    """Parse the CSV (UTF-8, header row) without validating it."""
    return _curated.read_rows(body, COLUMNS, FILE)


def validate(body: bytes, metrics: dict[str, dict] | None = None, vendors: set[str] | None = None) -> list[dict]:
    """Every rule of the plan; returns the rows. Raises DisclosureError on the first broken rule."""
    metrics = load_metrics() if metrics is None else metrics
    vendors = load_vendors() if vendors is None else vendors
    rows = read_rows(body)
    seen: dict[str, dict] = {}
    superseded: set[str] = set()
    for r in rows:
        rid = r["id"]
        for col in REQUIRED:
            if not r[col].strip():
                raise DisclosureError(f"{rid or '(no id)'}: {col} is empty")
        if r != {k: v.strip() for k, v in r.items()}:
            raise DisclosureError(f"{rid}: a field has leading or trailing spaces")
        if rid in seen:
            raise DisclosureError(f"{rid}: id is not unique")
        stated, period_start, period_end = _day(r, "statement_date"), _day(r, "period_start"), _day(r, "period_end")
        recorded = _day(r, "recorded_on")
        if period_start > period_end:
            raise DisclosureError(f"{rid}: period_start is after period_end")
        if stated > recorded:
            raise DisclosureError(f"{rid}: statement_date is after recorded_on")
        base = f"{r['entity']}-{r['metric']}-{r['statement_date']}"
        if rid != base and not (rid.startswith(base + "-") and SUFFIX.fullmatch(rid.removeprefix(base + "-"))):
            raise DisclosureError(f"{rid}: id must be <entity>-<metric>-<statement_date>[-n]")
        if r["entity"] not in vendors:
            raise DisclosureError(f"{rid}: entity {r['entity']!r} is not in vendors.yaml")
        if r["metric"] not in metrics:
            raise DisclosureError(f"{rid}: metric {r['metric']!r} is not in {METRICS}")
        unit = metrics[r["metric"]]["unit"]
        if r["unit"] != unit:
            raise DisclosureError(f"{rid}: unit {r['unit']!r}; metric {r['metric']} is measured in {unit}")
        try:
            value = Decimal(r["value"])
        except InvalidOperation:
            raise DisclosureError(f"{rid}: value {r['value']!r} is not a number") from None
        if not value.is_finite() or value <= 0 or not math.isfinite(float(value)):
            raise DisclosureError(f"{rid}: value must be finite and > 0")
        if r["qualifier"] not in QUALIFIERS:
            raise DisclosureError(f"{rid}: qualifier must be one of {', '.join(QUALIFIERS)}")
        if r["source_kind"] not in SOURCE_KINDS:
            raise DisclosureError(f"{rid}: source_kind must be primary or secondary")
        if not r["source_url"].startswith("https://"):
            raise DisclosureError(f"{rid}: source_url must be https")
        if len(r["source_quote"].split()) > MAX_QUOTE_WORDS:
            raise DisclosureError(f"{rid}: source_quote is longer than {MAX_QUOTE_WORDS} words")
        if _norm(r["value_as_stated"]) not in _norm(r["source_quote"]):
            raise DisclosureError(f"{rid}: source_quote does not contain {r['value_as_stated']!r}")
        parsed, currency, plus = parse_stated(r["value_as_stated"])
        if parsed != value:
            raise DisclosureError(f"{rid}: {r['value_as_stated']!r} reads as {parsed}, not value {r['value']}")
        if currency and not unit.startswith("usd"):
            raise DisclosureError(f"{rid}: a $ figure needs a usd unit, not {unit}")
        if plus and r["qualifier"] != "over":
            raise DisclosureError(f"{rid}: {r['value_as_stated']!r} ends in + so the qualifier is over")
        if r["supersedes"]:
            old = seen.get(r["supersedes"])
            if old is None:
                raise DisclosureError(f"{rid}: supersedes {r['supersedes']!r}, which is not an earlier row")
            if _day(old, "recorded_on") > recorded:
                raise DisclosureError(f"{rid}: supersedes a row recorded after it")
            if r["supersedes"] in superseded:
                raise DisclosureError(
                    f"{rid}: {r['supersedes']} is already superseded; supersede the newest correction"
                )
            superseded.add(r["supersedes"])
        seen[rid] = r
    return rows


def check_append_only(old: bytes, new: bytes) -> None:
    """No row of `old` may be removed or changed in `new` (rows are only appended)."""
    _curated.check_append_only(old, new, COLUMNS, FILE)


def main(argv: list[str]) -> int:
    """`--base <rev> [--head <rev>]`: the append-only check of the pre-push hook and CI."""
    return _curated.append_only_main(
        argv, module=__spec__.name, label="curated disclosures", repo_path=REPO_PATH, columns=COLUMNS
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

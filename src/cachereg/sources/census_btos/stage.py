"""Stage every stored version of every BTOS workbook (marts pick, per file, the version to use).

Tables:
- `estimates`: one row per AI cell (wording × question × answer × group × cycle) per file version;
  a suppressed cell (`S`) is a row with null values and `status = suppressed`, never 0.
- `versions`: one row per stored file version (readable or not, with the error).
- `cycles`: collection, reference and publication dates per cycle, from the newest readable version,
  current-wording files before the original-wording file.
- `size_classes`, `sectors` (config/entities/sectors.yaml `aliases.btos` → NAICS).

Parsing all versions keeps old vintages for `btos_revision_check`; the sector × size workbook takes a
few seconds per version.
"""

from __future__ import annotations

import polars as pl
import yaml

from cachereg.core.paths import entities_dir
from cachereg.core.store import list_fetches
from cachereg.sources.census_btos import files, workbook

SOURCE = "census_btos"
TAG = {"file": pl.String, "fetch_id": pl.String, "fetched_at": pl.Datetime("us", "UTC")}
ESTIMATES_SCHEMA = TAG | {
    "wording": pl.String, "question": pl.String, "answer": pl.String, "breakdown": pl.String,
    "group_key": pl.String, "sector_code": pl.String, "size_class": pl.String, "cycle": pl.String,
    "estimate_pct": pl.Float64, "se_pct": pl.Float64, "status": pl.String,
}  # fmt: skip
VERSIONS_SCHEMA = TAG | {
    "fetch_date": pl.Date,  # UTC, as build's cutoff counts fetch dates
    "sha256": pl.String, "readable": pl.Boolean, "error": pl.String, "cells": pl.Int64, "newest_cycle": pl.String,
}  # fmt: skip
CYCLES_SCHEMA = {
    "cycle": pl.String, "collection_start": pl.Date, "collection_end": pl.Date, "reference_start": pl.Date,
    "reference_end": pl.Date, "publication_date": pl.Date, "sample_year": pl.Int64, "census_cycle": pl.Int64,
    "panel": pl.Int64, "note": pl.String, "first_of_sample_year": pl.Boolean, "dates_from": pl.String,
}  # fmt: skip
SIZE_SCHEMA = {"size_class": pl.String, "min_employees": pl.Int64, "max_employees": pl.Int64, "label": pl.String}
SECTORS_SCHEMA = {"code": pl.String, "naics": pl.String, "title": pl.String}


def load_sectors() -> list[dict]:
    data = yaml.safe_load((entities_dir() / "sectors.yaml").read_text()) or {}
    return [
        {"code": str(code), "naics": str(naics), "title": s["title"]}  # `assumed` is about Ramp's labels
        for naics, s in (data.get("sectors") or {}).items()
        for code in ((s.get("aliases") or {}).get("btos") or [])
    ]


def size_classes() -> list[dict]:
    return [
        {"size_class": k, "min_employees": lo, "max_employees": hi, "label": f"{lo}–{hi}" if hi else f"{lo}+"}
        for k, (lo, hi) in workbook.SIZE_CLASSES.items()
    ]


DATE_FIELDS = ("collection_start", "collection_end", "reference_start", "reference_end")


def _cycles(dated: list[tuple[tuple, str, dict]]) -> list[tuple]:
    """Merge the date sheets: (priority, file, cycles); lower priority wins for a cycle.

    Collection and reference dates must agree across every sheet and version that lists a cycle (a stage
    error otherwise: the monthly method rests on them). Publication dates may move; the winner's is kept.
    """
    chosen = {}
    for _, key, cycles in sorted(dated, key=lambda d: d[0]):
        for code, c in cycles.items():
            first = chosen.setdefault(code, (c, key))[0]
            if any(getattr(first, f) != getattr(c, f) for f in DATE_FIELDS):
                raise ValueError(f"{SOURCE}: cycle {code} has other collection or reference dates in {key}")
    rows, previous_year = [], None
    for code in sorted(chosen):
        c, key = chosen[code]
        first = c.sample_year is not None and c.sample_year != previous_year
        previous_year = c.sample_year if c.sample_year is not None else previous_year
        rows.append((
            c.cycle, c.collection_start, c.collection_end, c.reference_start, c.reference_end, c.publication_date,
            c.sample_year, c.census_cycle, c.panel, c.note, first, key,
        ))  # fmt: skip
    return rows


def stage() -> dict[str, pl.DataFrame]:
    estimates, versions, dated, rejected = [], [], [], 0
    fetches = list_fetches(SOURCE)
    for n, f in enumerate(fetches):
        for spec in files.FILES:
            digest = f.manifest.get("files", {}).get(spec.file_name)
            if not digest:
                continue
            tag = (spec.key, f.manifest["fetch_id"], f.fetched_at)
            try:
                parsed = workbook.parse(f.read(spec.file_name), spec)
            except (OSError, ValueError) as e:  # an unreadable old version must not block the build
                versions.append((*tag, f.fetched_at.date(), digest, False, str(e)[:300], 0, None))
                rejected += 1
                continue
            rejected += parsed.rejected
            versions.append(
                (*tag, f.fetched_at.date(), digest, True, None, len(parsed.cells), max(c.cycle for c in parsed.cells))
            )
            # Newest fetch first, then current-wording files before the frozen original-wording one.
            dated.append(((len(fetches) - n, spec.wording != "current"), spec.key, parsed.cycles))
            for c in parsed.cells:
                estimates.append((
                    *tag, spec.wording, c.question, c.answer, c.breakdown, c.group_key, c.sector_code, c.size_class,
                    c.cycle, c.estimate_pct, c.se_pct, "suppressed" if c.suppressed else "published",
                ))  # fmt: skip
    wording_at, cycle_at = list(ESTIMATES_SCHEMA).index("wording"), list(ESTIMATES_SCHEMA).index("cycle")
    by_wording: dict[str, set[str]] = {}
    for row in estimates:
        by_wording.setdefault(row[wording_at], set()).add(row[cycle_at])
    both = sorted(by_wording.get("original", set()) & by_wording.get("current", set()))
    if both:  # the two wordings are separate series; Census never asked both in one cycle
        raise ValueError(f"{SOURCE}: cycles hold values in both AI wordings: {both}")
    return {
        "estimates": pl.DataFrame(estimates, schema=ESTIMATES_SCHEMA, orient="row"),
        "versions": pl.DataFrame(versions, schema=VERSIONS_SCHEMA, orient="row"),
        "cycles": pl.DataFrame(_cycles(dated), schema=CYCLES_SCHEMA, orient="row"),
        "size_classes": pl.DataFrame(size_classes(), schema=SIZE_SCHEMA, orient="row"),
        "sectors": pl.DataFrame(load_sectors(), schema=SECTORS_SCHEMA, orient="row"),
        "_rejected_rows": pl.DataFrame({"rejected": [rejected]}),
    }

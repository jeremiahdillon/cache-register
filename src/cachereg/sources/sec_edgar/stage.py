"""Stage SEC company facts: every fact of every configured company, from its newest fetch.

The source is append-only (a restatement is a new fact, earlier facts stay in the file), so the
newest fetch holding a CIK contains every fact an earlier fetch did. Marts select facts by their
`filed` date (PLAN §4.4, Exact); the fetch date does not matter.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.paths import staged_dir
from cachereg.core.store import list_fetches
from cachereg.sources.sec_edgar.companies import cik10, load_companies
from cachereg.sources.sec_edgar.fetch import decode, iter_facts

SOURCE = "sec_edgar"
FACTS_SCHEMA = {
    "cik": pl.String,
    "taxonomy": pl.String,
    "tag": pl.String,
    "unit": pl.String,
    "period_start": pl.Date,  # null for instant facts (balance sheet)
    "period_end": pl.Date,
    "val": pl.Float64,
    "accn": pl.String,
    "fy": pl.Int64,
    "fp": pl.String,
    "form": pl.String,
    "filed": pl.Date,
    "frame": pl.String,
    "fetch_id": pl.String,
}
COMPANIES_SCHEMA = {
    "cik": pl.String,
    "ticker": pl.String,
    "name": pl.String,
    "group": pl.String,
    "vendor_id": pl.String,
    "entity_name": pl.String,
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
}


def _date(v) -> date | None:
    return date.fromisoformat(v) if v else None


def _int(v) -> int | None:
    return int(v) if v not in (None, "") else None


def newest_files() -> dict[str, tuple]:
    """CIK → (stored fetch, file name) of the newest fetch that holds it."""
    out = {}
    for f in list_fetches(SOURCE):  # oldest first, so later fetches overwrite
        for name in f.manifest["files"]:
            if name.startswith("companyfacts_CIK"):
                out[name.removeprefix("companyfacts_CIK")[:10]] = (f, name)
    return out


def vintage_at(as_of: date) -> dict | None:
    """The newest filing on or before ``as_of`` among the staged facts (PLAN §4.4)."""
    path = staged_dir(SOURCE) / "facts.parquet"
    if not path.is_file():
        return None
    row = (
        pl.scan_parquet(path)
        .filter(pl.col("filed") <= as_of)
        .sort("filed", "accn")
        .select("filed", "accn")
        .last()
        .collect()
    )
    if row.is_empty():
        return None
    return {"kind": "edgar_filed", "value": row["accn"][0], "date": row["filed"][0].isoformat()}


def stage() -> dict[str, pl.DataFrame]:
    files = newest_files()
    rows, companies, rejected = [], [], 0
    for company in load_companies():
        if company.cik not in files:
            raise ValueError(f"{SOURCE}: no stored facts for {company.ticker} (CIK {company.cik}); run a fetch")
        f, name = files[company.cik]
        data = decode(f.read(name))
        if cik10(data.get("cik", "")) != company.cik:
            raise ValueError(f"{SOURCE}: {name} holds CIK {data.get('cik')!r}")
        for taxonomy, tag, unit, x in iter_facts(data):
            try:
                row = (
                    company.cik,
                    taxonomy,
                    tag,
                    unit,
                    _date(x.get("start")),
                    date.fromisoformat(x["end"]),
                    float(x["val"]),
                    x.get("accn"),
                    _int(x.get("fy")),
                    x.get("fp"),
                    x.get("form"),
                    date.fromisoformat(x["filed"]),
                    x.get("frame"),
                    f.manifest["fetch_id"],
                )
            except (AttributeError, KeyError, TypeError, ValueError):  # AttributeError: x is None
                rejected += 1
                continue
            rows.append(row)
        companies.append(
            (
                company.cik,
                company.ticker,
                company.name,
                company.group,
                company.vendor_id,
                data.get("entityName"),
                f.manifest["fetch_id"],
                f.fetched_at,
            )
        )
    return {
        "facts": pl.DataFrame(rows, schema=FACTS_SCHEMA, orient="row"),
        "companies": pl.DataFrame(companies, schema=COMPANIES_SCHEMA, orient="row"),
        "_rejected_rows": pl.DataFrame({"rejected": [rejected]}),
    }

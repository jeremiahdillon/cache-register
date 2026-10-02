"""Stage rankings-daily raw fetches into one tidy table (all vintages kept)."""

from __future__ import annotations

import json

import polars as pl

from cachereg.core.store import list_fetches

SOURCE = "openrouter_rankings"
SCHEMA = {
    "date": pl.Date,
    "model_permaslug": pl.String,
    "total_tokens": pl.Int64,
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
    "api_as_of": pl.String,
}


def stage() -> dict[str, pl.DataFrame]:
    rows, rejected = [], 0
    for f in list_fetches(SOURCE):
        for name in f.manifest["files"]:
            body = json.loads(f.read(name))
            as_of = body.get("meta", {}).get("as_of")
            for r in body["data"]:
                try:
                    rows.append(
                        {
                            "date": r["date"],
                            "model_permaslug": r["model_permaslug"],
                            "total_tokens": int(r["total_tokens"]),
                            "fetch_id": f.manifest["fetch_id"],
                            "fetched_at": f.manifest["fetched_at"],
                            "api_as_of": as_of,
                        }
                    )
                except (KeyError, TypeError, ValueError):
                    rejected += 1  # counted and reported, never silently dropped
    df = (
        pl.DataFrame(rows, schema={k: pl.String for k in SCHEMA}, orient="row")
        if rows
        else pl.DataFrame(schema={k: pl.String for k in SCHEMA})
    )
    df = df.with_columns(
        pl.col("date").str.to_date(),
        pl.col("total_tokens").cast(pl.Int64),
        pl.col("fetched_at").str.to_datetime(time_zone="UTC"),
    )
    return {"daily": df, "_rejected_rows": pl.DataFrame({"rejected": [rejected]})}

"""Stage Vercel AI Gateway export bodies: daily shares by lab and by model (all vintages kept).

Mart 090 picks, per dataset × window × day, the rows of the latest fetch on/before the cutoff that
holds that day (Latest-only), never mixing rows across fetches. Models rows carry `window` (the
requested month: the list is that month's top models) and `unlisted_pct` = 100 − Σ the day's
named models (Vercel's `Other` when it is published, else the residual), so the coverage of the
listed models is always known.
"""

from __future__ import annotations

import json
import math
from datetime import date

import polars as pl

from cachereg.core.store import list_fetches

SOURCE = "vercel_ai_gateway"
OTHER = "Other"
SHARES_SCHEMA = {
    "date": pl.Date,
    "dataset": pl.String,  # labs | models
    "name": pl.String,  # as published (lab slug or model display name)
    "metric": pl.String,  # requests | tokens | spend
    "modality": pl.String,
    "share_pct": pl.Float64,
    "is_other": pl.Boolean,
    "window_start": pl.Date,  # models: the requested month (labs: null; a lab list does not depend on it)
    "unlisted_pct": pl.Float64,  # models only
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
}


def _row(r: dict, dataset: str, window: date | None, common: dict) -> dict:
    share = r["share_percent"]
    if isinstance(share, bool) or not isinstance(share, int | float) or not math.isfinite(share):
        raise ValueError(share)
    return {
        "date": date.fromisoformat(r["date"]),
        "dataset": dataset,
        "name": str(r["name"]),
        "metric": str(r["metric"]),
        "modality": str(r["modality"]),
        "share_pct": float(share),
        "is_other": dataset == "models" and r["name"] == OTHER,
        "window_start": window,
    } | common


def stage() -> dict[str, pl.DataFrame]:
    rows, rejected = [], 0
    for f in list_fetches(SOURCE):
        common = {"fetch_id": f.manifest["fetch_id"], "fetched_at": f.fetched_at}
        for name in f.manifest["files"]:
            body = json.loads(f.read(name))
            data = body.get("rows") if isinstance(body, dict) else None
            dataset = body.get("dataset") if isinstance(body, dict) else None
            try:
                if dataset not in ("labs", "models") or not isinstance(data, list):
                    raise ValueError(name)
                window = date.fromisoformat(body["from"]).replace(day=1) if dataset == "models" else None
            except (KeyError, TypeError, ValueError):
                rejected += len(data or [])  # a file without a readable header: all its rows are rejected
                continue
            for r in data:
                try:
                    rows.append(_row(r, dataset, window, common))
                except (KeyError, TypeError, ValueError):
                    rejected += 1  # counted and reported, never silently dropped
    shares = pl.DataFrame(rows, schema=SHARES_SCHEMA, orient="row")
    listed = (
        shares.filter((pl.col("dataset") == "models") & ~pl.col("is_other"))
        .group_by("fetch_id", "window_start", "date", "metric")
        .agg((100 - pl.col("share_pct").sum()).clip(lower_bound=0).alias("unlisted"))
    )
    shares = (
        shares.drop("unlisted_pct")
        .join(listed, on=["fetch_id", "window_start", "date", "metric"], how="left", nulls_equal=False)
        .with_columns(
            pl.when(pl.col("dataset") == "models")
            .then(pl.col("unlisted").fill_null(100.0))
            .otherwise(None)
            .alias("unlisted_pct")
        )
        .select(list(SHARES_SCHEMA))
        .sort("dataset", "date", "metric", "fetch_id", "name")
    )
    labels = (
        shares.group_by("dataset", "name")
        .agg(
            pl.col("date").min().alias("first_day"),
            pl.col("date").max().alias("last_day"),
            pl.col("share_pct").filter(pl.col("metric") == "tokens").max().alias("peak_tokens_pct"),
            pl.col("share_pct").filter(pl.col("metric") == "spend").max().alias("peak_spend_pct"),
            pl.col("share_pct").filter(pl.col("metric") == "requests").max().alias("peak_requests_pct"),
        )
        .sort("dataset", "name")
    )
    return {"shares": shares, "labels": labels, "_rejected_rows": pl.DataFrame({"rejected": [rejected]})}

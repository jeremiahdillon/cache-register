"""Stage Artificial Analysis snapshots: one row per model per fetch, and per-eval scores (long).

Every fetch is kept (Author-only snapshots); mart 120 reads the latest fetch on/before the cutoff.
Evaluations are staged as published (the intelligence indexes on AA's 0–100 scale, single evals as
0–1 fractions); null and non-numeric values are left out and counted in `_rejected_rows`
(non-numeric only: a null means "not evaluated" and is not an error).
"""

from __future__ import annotations

import json
import math

import polars as pl

from cachereg.core.store import list_fetches

SOURCE = "artificial_analysis"
MODELS_SCHEMA = {
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
    "snapshot_date": pl.Date,
    "aa_id": pl.String,
    "slug": pl.String,
    "name": pl.String,
    "release_date": pl.Date,
    "creator_slug": pl.String,
    "creator_name": pl.String,
}
EVALS_SCHEMA = {"fetch_id": pl.String, "slug": pl.String, "metric": pl.String, "value": pl.Float64}


def _number(v) -> float | None:
    if isinstance(v, bool) or not isinstance(v, int | float) or not math.isfinite(v):
        return None
    return float(v)


def stage() -> dict[str, pl.DataFrame]:
    models, evals, rejected = [], [], 0
    for f in list_fetches(SOURCE):
        common = {"fetch_id": f.manifest["fetch_id"], "fetched_at": f.fetched_at}
        for m in json.loads(f.read("models.json"))["data"]:
            creator = m.get("model_creator") or {}
            models.append(
                common
                | {
                    "snapshot_date": f.fetched_at.date(),
                    "aa_id": m.get("id"),
                    "slug": m.get("slug"),
                    "name": m.get("name"),
                    "release_date": m.get("release_date"),
                    "creator_slug": creator.get("slug"),
                    "creator_name": creator.get("name"),
                }
            )
            for metric, v in (m.get("evaluations") or {}).items():
                if v is None:
                    continue
                if (x := _number(v)) is None:
                    rejected += 1
                    continue
                evals.append({"fetch_id": common["fetch_id"], "slug": m.get("slug"), "metric": metric, "value": x})
    schema = MODELS_SCHEMA | {"release_date": pl.String}
    mdf = pl.DataFrame(models, schema=schema).with_columns(pl.col("release_date").str.to_date(strict=False))
    return {
        "models": mdf.select(list(MODELS_SCHEMA)),
        "evaluations": pl.DataFrame(evals, schema=EVALS_SCHEMA),
        "_rejected_rows": pl.DataFrame({"rejected": [rejected]}),
    }

"""Stage session-cost snapshots into one table (all fetches kept) plus the harness map.

Each fetch holds one snapshot, identified by its `window_end_date`; mart 055 picks the latest
fetch per snapshot. `harnesses` comes from config/entities/apps.yaml, not from the raw store.
"""

from __future__ import annotations

import json
import math
from datetime import date

import polars as pl

from cachereg.core.store import list_fetches
from cachereg.sources.openrouter_session_cost.harnesses import load_harnesses

SOURCE = "openrouter_session_cost"
TURN_BOUNDS = {"1-turn": (1, 1), "2-9-turns": (2, 9), "10-49-turns": (10, 49), "50-plus-turns": (50, None)}
CELLS_SCHEMA = {
    "window_end_date": pl.Date,
    "window_days": pl.Int64,
    "app_slug": pl.String,
    "app_name": pl.String,
    "turn_range": pl.String,
    "turn_min": pl.Int64,
    "turn_max": pl.Int64,  # null for the open-ended 50-plus range
    "model_permaslug": pl.String,
    "median_session_cost_usd": pl.Float64,
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
    "api_as_of": pl.String,
}
HARNESSES_SCHEMA = {"app_slug": pl.String, "app_id": pl.Int64, "name": pl.String, "vendor_id": pl.String}


def _cell(r: dict, meta: dict, f) -> dict:
    turn_min, turn_max = TURN_BOUNDS[r["turn_range"]]
    cost = float(r["median_session_cost_usd"])
    if not math.isfinite(cost) or cost < 0:
        raise ValueError(cost)
    slug = r["model_permaslug"]
    if not isinstance(slug, str) or not slug or not isinstance(r["app_slug"], str) or not r["app_slug"]:
        raise ValueError("blank key")
    return {
        "window_end_date": date.fromisoformat(meta["window_end_date"]),
        "window_days": int(meta["window_days"]),
        "app_slug": r["app_slug"],
        "app_name": r.get("app_name"),
        "turn_range": r["turn_range"],
        "turn_min": turn_min,
        "turn_max": turn_max,
        "model_permaslug": slug,
        "median_session_cost_usd": cost,
        "fetch_id": f.manifest["fetch_id"],
        "fetched_at": f.fetched_at,
        "api_as_of": meta.get("as_of"),
    }


def stage() -> dict[str, pl.DataFrame]:
    rows, rejected = [], 0
    for f in list_fetches(SOURCE):
        for name in f.manifest["files"]:
            body = json.loads(f.read(name))
            meta = body.get("meta") or {}
            for r in body.get("data") or []:
                try:
                    rows.append(_cell(r, meta, f))
                except (KeyError, TypeError, ValueError):
                    rejected += 1  # counted and reported, never silently dropped
    cells = pl.DataFrame(rows, schema=CELLS_SCHEMA, orient="row")
    harnesses = pl.DataFrame(
        [
            {"app_slug": h.app_slug, "app_id": h.app_id, "name": h.name, "vendor_id": h.vendor_id}
            for h in load_harnesses()
        ],
        schema=HARNESSES_SCHEMA,
        orient="row",
    )
    return {"cells": cells, "harnesses": harnesses, "_rejected_rows": pl.DataFrame({"rejected": [rejected]})}

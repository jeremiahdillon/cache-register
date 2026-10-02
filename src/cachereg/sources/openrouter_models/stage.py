"""Stage model-catalog snapshots into a price table (one row per model per snapshot)."""

from __future__ import annotations

import json

import polars as pl

from cachereg.core.store import list_fetches

SOURCE = "openrouter_models"


def _price(p: dict, key: str) -> float | None:
    v = p.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def stage() -> dict[str, pl.DataFrame]:
    rows = []
    for f in list_fetches(SOURCE):
        snapshot = f.manifest["fetched_at"][:10]
        for m in json.loads(f.read("models.json"))["data"]:
            p = m.get("pricing") or {}
            rows.append(
                {
                    "snapshot_date": snapshot,
                    "id": m.get("id"),
                    "canonical_slug": m.get("canonical_slug") or m.get("id"),
                    "name": m.get("name"),
                    "created": m.get("created"),
                    "prompt_usd_per_token": _price(p, "prompt"),
                    "completion_usd_per_token": _price(p, "completion"),
                    "cache_read_usd_per_token": _price(p, "input_cache_read"),
                }
            )
    df = pl.DataFrame(rows, infer_schema_length=None) if rows else pl.DataFrame()
    if rows:
        df = df.with_columns(pl.col("snapshot_date").str.to_date())
    return {"prices": df}

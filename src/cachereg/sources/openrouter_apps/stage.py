"""Stage app-rankings raw fetches: weekly top-200 apps and app tags (all vintages kept).

Mart 050 picks, per week, the rows of the latest fetch on/before the cutoff that holds that week.
"""

from __future__ import annotations

import json
from datetime import date

import polars as pl

from cachereg.core.store import list_fetches

SOURCE = "openrouter_apps"
WEEKLY_SCHEMA = {
    "week_start": pl.Date,
    "week_end": pl.Date,
    "rank": pl.Int64,
    "app_id": pl.Int64,
    "app_name": pl.String,
    "total_tokens": pl.Int64,
    "total_requests": pl.Int64,
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
    "api_as_of": pl.String,
}
TAGS_SCHEMA = {
    "app_id": pl.Int64,
    "app_name": pl.String,
    "tag_kind": pl.String,  # category | subcategory
    "tag": pl.String,
    "rank_in_tag": pl.Int64,
    "tag_week_start": pl.Date,
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
}


def _count(v) -> int:
    if isinstance(v, bool):
        raise ValueError(v)
    n = int(v)  # total_tokens is a decimal string (64-bit safe), total_requests an int
    if n < 0 or (isinstance(v, str) and not v.isdigit()):
        raise ValueError(v)
    return n


def stage() -> dict[str, pl.DataFrame]:
    weekly, tags, rejected = [], [], 0
    for f in list_fetches(SOURCE):
        common = {"fetch_id": f.manifest["fetch_id"], "fetched_at": f.fetched_at}
        for name in f.manifest["files"]:
            body = json.loads(f.read(name))
            meta = body.get("meta") or {}
            start = date.fromisoformat(meta["start_date"])
            if name.startswith("tag_"):
                _, kind, tag, *_ = name.split("_")
            for r in body.get("data") or []:
                try:
                    if name.startswith("tag_"):
                        row = {"app_id": _count(r["app_id"]), "app_name": r["app_name"], "tag_kind": kind, "tag": tag}
                        tags.append(row | {"rank_in_tag": int(r["rank"]), "tag_week_start": start} | common)
                    else:
                        weekly.append(
                            {
                                "week_start": start,
                                "week_end": date.fromisoformat(meta["end_date"]),
                                "rank": int(r["rank"]),
                                "app_id": _count(r["app_id"]),
                                "app_name": r["app_name"],
                                "total_tokens": _count(r["total_tokens"]),
                                "total_requests": _count(r["total_requests"]),
                                "api_as_of": meta.get("as_of"),
                            }
                            | common
                        )
                except (KeyError, TypeError, ValueError):
                    rejected += 1  # counted and reported, never silently dropped
    return {
        "weekly": pl.DataFrame(weekly, schema=WEEKLY_SCHEMA, orient="row"),
        "tags": pl.DataFrame(tags, schema=TAGS_SCHEMA, orient="row"),
        "_rejected_rows": pl.DataFrame({"rejected": [rejected]}),
    }

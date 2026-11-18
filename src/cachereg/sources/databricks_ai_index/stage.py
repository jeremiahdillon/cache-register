"""Stage Databricks AI Index pages: one row per chart × layer × week, all vintages kept.

Mart 095 picks, per week, the rows of the latest fetch on/before the cutoff that holds that week (Latest-only),
never mixing a week's rows across fetches. A stored page that no longer parses (it did when fetched) counts
its fetch as rejected rather than failing the build.
"""

from __future__ import annotations

import polars as pl

from cachereg.core.store import list_fetches
from cachereg.sources.databricks_ai_index import parse

SOURCE = "databricks_ai_index"
SCHEMA = {
    "week_start": pl.Date,  # Monday
    "chart": pl.String,  # canvasId
    "metric": pl.String,  # tokens | spend
    "segment": pl.String,  # proprietary | open_weight | split (the proprietary / open-weight token mix)
    "provider_group": pl.String,  # as published: Anthropic, OpenAI, Other proprietary, Zhipu, …, Model type
    "label": pl.String,  # as published: model name, "Older … Models", "Gemini, Grok", "Other", segment name
    "share_pct": pl.Float64,
    "updated": pl.Date,  # the chart's "Updated" date
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
}


def stage() -> dict[str, pl.DataFrame]:
    rows, rejected = [], 0
    for f in list_fetches(SOURCE):
        common = {"fetch_id": f.manifest["fetch_id"], "fetched_at": f.fetched_at}
        for name in f.manifest["files"]:
            try:
                recs = parse.records(f.read(name).decode("utf-8"))
            except (ValueError, KeyError, IndexError, TypeError, UnicodeDecodeError):
                rejected += 1  # counted and reported, never silently dropped
                continue
            rows += [r | common for r in recs]
    layers = pl.DataFrame(rows, schema=SCHEMA, orient="row").sort("week_start", "chart", "fetch_id", "label")
    return {"layers": layers, "_rejected_rows": pl.DataFrame({"rejected": [rejected]})}

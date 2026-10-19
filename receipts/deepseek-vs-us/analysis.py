"""DeepSeek vs US models on OpenRouter: weekly tokens of DeepSeek, closed US models and all US models.

Reads marts only (or_rankings_daily, dim_vendor_alias). Open vs closed is tagged per model (us_weights.yaml).
See README.md for method and caveats. Receipt: cacheregister.dev/deepseek-vs-us. `cachereg render
receipts/deepseek-vs-us` renders the visual declared in receipt.yaml.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import yaml

from cachereg.core.warehouse import query
from cachereg.story.model import Story

HERE = Path(__file__).parent
DEEPSEEK = "DeepSeek"
US_CLOSED = "US closed models"
US_ALL = "All US models"
US_OPEN = "US open-weight models"
OTHER_US_CLOSED = "Other US closed"
LABS = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google", "xai": "xAI (Grok)"}
# Stack bottom to top: the largest labs first, the long tail on top.
LAB_ORDER = ["OpenAI", "Anthropic", "Google", "xAI (Grok)", OTHER_US_CLOSED]
TABLE_PERCENT_COLUMNS: list[str] = []
MIN_DAYS = 6  # a week with one missing day still counts, scaled to 7 days (OpenRouter lacks Jun 15 and Jul 15, 2025)
EMBEDDING = r"embed|bge-|/bge|e5-|minilm"  # as in open-middle: embedding models are not chat/completion traffic
T = 1e12


def open_patterns() -> list[re.Pattern]:
    return [re.compile(p) for p in yaml.safe_load((HERE / "us_weights.yaml").read_text())["open"]]


def _daily(con, as_of: date) -> pl.DataFrame:
    """Tokens per (week, model) for DeepSeek and US developers; `days` = days of data that week (any model)."""
    return query(
        con,
        """
        WITH v AS (SELECT DISTINCT alias, vendor_id, hq FROM dim_vendor_alias WHERE source = 'openrouter'),
        r AS (
            SELECT date, model_permaslug, total_tokens FROM or_rankings_daily
            WHERE date <= ? AND NOT regexp_matches(model_permaslug, ?)
        ),
        n AS (SELECT date_trunc('week', date)::DATE AS week, count(DISTINCT date) AS days FROM r GROUP BY 1)
        SELECT date_trunc('week', r.date)::DATE AS week, r.model_permaslug AS model, v.vendor_id,
               sum(r.total_tokens) AS tokens, n.days
        FROM r
        JOIN v ON v.alias = split_part(r.model_permaslug, '/', 1)
        JOIN n ON n.week = date_trunc('week', r.date)::DATE
        WHERE v.vendor_id = 'deepseek' OR (v.hq = 'US' AND NOT starts_with(v.vendor_id, '_'))
        GROUP BY ALL
        """,
        [as_of, EMBEDDING],
    )


def band_of(model: str, vendor_id: str, patterns: list[re.Pattern]) -> str:
    if vendor_id == "deepseek":
        return DEEPSEEK
    if any(p.search(model) for p in patterns):
        return US_OPEN
    return LABS.get(vendor_id, OTHER_US_CLOSED)


def fmt_t(x: float) -> str:
    """Tokens as a short figure: 45.9T, 820B."""
    return f"{x / T:.1f}T" if x >= 0.995e12 else f"{x / 1e9:.0f}B"


def _streak(wide: pl.DataFrame, a: str, b: str) -> tuple[date | None, int, int]:
    """(first week a > b, length of the current run of weeks with a > b, all weeks with a > b)."""
    above = wide.select("week", (pl.col(a) > pl.col(b)).alias("x"))
    weeks = above.filter(pl.col("x"))["week"]
    run = 0
    for x in reversed(above["x"].to_list()):
        if not x:
            break
        run += 1
    return (weeks.min() if weeks.len() else None), run, weeks.len()


def build(con, as_of: date, cfg: dict) -> Story:
    d = _daily(con, as_of)
    last_full = d.filter(pl.col("days") == 7)["week"].max()
    d = d.filter((pl.col("days") >= MIN_DAYS) & (pl.col("week") <= last_full) & (pl.col("week") >= cfg["start"]))
    patterns = open_patterns()
    d = d.with_columns(
        pl.struct("model", "vendor_id")
        .map_elements(lambda r: band_of(r["model"], r["vendor_id"], patterns), return_dtype=pl.String)
        .alias("band"),
        # A 6-day week is scaled to 7 days so weekly totals stay comparable (every series alike).
        (pl.col("tokens") * 7 / pl.col("days")).alias("tokens"),
    )
    bands = [DEEPSEEK, US_OPEN, *LAB_ORDER]
    wide = d.group_by("week", "band").agg(pl.col("tokens").sum()).pivot(on="band", index="week", values="tokens")
    wide = wide.select("week", *[pl.col(b) if b in wide.columns else pl.lit(0.0).alias(b) for b in bands])
    wide = wide.fill_null(0.0).sort("week")
    wide = wide.with_columns(pl.sum_horizontal(LAB_ORDER).alias(US_CLOSED))
    wide = wide.with_columns((pl.col(US_CLOSED) + pl.col(US_OPEN)).alias(US_ALL))
    wide = wide.join(d.select("week", "days").unique(), on="week").sort("week")
    if wide.height < 3:
        raise ValueError(f"need at least 3 complete weeks on or before {as_of}, found {wide.height}")

    first, last = wide["week"].min(), wide["week"].max()
    end = last + timedelta(days=6)
    r1 = wide.row(-1, named=True)
    ds, closed, us = r1[DEEPSEEK], r1[US_CLOSED], r1[US_ALL]
    peak = wide.sort(DEEPSEEK).row(-1, named=True)
    vs_closed = _streak(wide, DEEPSEEK, US_CLOSED)
    vs_all = _streak(wide, DEEPSEEK, US_ALL)

    # Headline follows the data: more than all US models, else more than closed US models, else neither. Present
    # tense, no date: the claim is about the latest complete week. The newline is the preferred break on wide
    # targets (ignored where the first line does not fit).
    if ds > us:
        claim = "DeepSeek serves more tokens on OpenRouter\nthan every US model combined"
    elif ds > closed:
        claim = "DeepSeek serves more tokens on OpenRouter\nthan every closed US model combined"
    else:
        claim = f"DeepSeek serves {ds / closed:.0%} as many tokens on OpenRouter\nas closed US models"
    # The latest figures are on the face of the chart (its labels), so the subtitle is scope only.
    subtitle = f"Weekly tokens on OpenRouter, {first:%B %Y} to {end:%B %-d, %Y}."

    closed_models = (
        d.filter(pl.col("band").is_in(LAB_ORDER))
        .group_by("model", "band")
        .agg(pl.col("tokens").sum())
        .sort("tokens", descending=True)
    )
    open_models = d.filter(pl.col("band") == US_OPEN).group_by("model").agg(pl.col("tokens").sum())
    return Story(
        title=f"{claim}.",
        subtitle=subtitle,
        frames={"wide": wide},
        sources=["openrouter_rankings"],
        as_of=as_of,
        method=(
            "tokens as reported by OpenRouter, each model's own tokenizer; free variants included; embeddings "
            "excluded; identified top-50 models only; open vs closed per model"
        ),
        caveats=[
            "Tokens, not spend or revenue: DeepSeek's models are far cheaper per token than closed US models.",
            "OpenRouter traffic only (third-party developer routing), which over-represents cheap, free and open "
            "models compared with first-party APIs, subscriptions and enterprise contracts.",
            "Identified models only: stealth models and OpenRouter's 'other' row (models outside the daily top 50) "
            "are excluded; either may contain DeepSeek or US models.",
            "DeepSeek fine-tunes by other developers (e.g. TNG's R1T Chimera) are not counted as DeepSeek.",
            "Tokens are counted by each provider's own tokenizer, so volumes are not strictly comparable.",
        ],
        extra={
            "y_title": "Tokens per week",
            "first_week": str(first),
            "last_week": str(last),
            "latest": {k: r1[k] for k in [DEEPSEEK, US_CLOSED, US_ALL, US_OPEN, *LAB_ORDER]},
            "peak_week": str(peak["week"]),
            "peak_tokens": peak[DEEPSEEK],
            "ds_vs_closed": {"first_week_above": str(vs_closed[0]), "current_run": vs_closed[1], "weeks": vs_closed[2]},
            "ds_vs_all_us": {"first_week_above": str(vs_all[0]), "current_run": vs_all[1], "weeks": vs_all[2]},
            "six_day_weeks": [str(w) for w in wide.filter(pl.col("days") < 7)["week"]],
            "us_closed_models": {r["model"]: r["tokens"] for r in closed_models.head(40).iter_rows(named=True)},
            "us_open_tokens": float(open_models["tokens"].sum()),
        },
    )


def table(story: Story) -> pl.DataFrame:
    """Weekly tokens (trillions) by series."""
    w = story.frames["wide"]
    cols = [DEEPSEEK, US_CLOSED, US_ALL, *LAB_ORDER, US_OPEN]
    return w.select("week", *[(pl.col(c) / T).round(3).alias(f"{c} (T)") for c in cols])

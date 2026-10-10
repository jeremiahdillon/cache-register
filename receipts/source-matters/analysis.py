"""Anthropic's share of spend and tokens, by data source.

Receipt (cacheregister.dev/source-matters), promoted from explore/2026-10-10-anthropic-share-by-source. Reads
marts 010 (or_model_daily), 062 (ramp_token_share) and 090 (vercel_lab_share); never cachereg.sources. See
README.md for method and docs/plans/2026-10-10-anthropic-share-by-source.md for the design and the author's
decisions. `cachereg render receipts/source-matters` renders the visuals declared in receipt.yaml into output/.

Every line is the same measure, Anthropic's share of all its source reports, so the sources share one axis
(author decision). The sources see different populations and measure spend differently; the README says
which differences may be method rather than segment.
"""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

LAB = "anthropic"
SOURCES = ["ramp", "vercel", "openrouter"]
NAMES = {"ramp": "Ramp", "vercel": "Vercel", "openrouter": "OpenRouter"}
# (measure, OpenRouter token variant) per visual
VISUALS = {"spend": ("spend", None), "tokens-with-free": ("tokens", "all")}  # paid-only tokens stay in `weekly`


def _sunday(d: date) -> date:
    return d + timedelta(days=6 - d.weekday())


# ---- weekly series ---------------------------------------------------------------------------


def openrouter_weeks(con) -> pl.DataFrame:
    """Per Monday–Sunday week (dated by its Sunday): volume-weighted Anthropic shares and the inputs of the
    spend bound. Free variants are excluded from spend and from the `paid` token variant."""
    return query(
        con,
        """
        WITH d AS (
            SELECT CAST(date_trunc('week', date) + INTERVAL 6 DAY AS DATE) AS week, *
            FROM or_model_daily
        )
        SELECT
            week,
            count(DISTINCT date) AS days,
            sum(total_tokens) FILTER (WHERE vendor_id = ?) AS lab_tokens_all,
            sum(total_tokens) AS tokens_all,
            sum(total_tokens) FILTER (WHERE vendor_id = ? AND NOT is_free) AS lab_tokens_paid,
            sum(total_tokens) FILTER (WHERE NOT is_free) AS tokens_paid,
            coalesce(sum(est_spend_usd) FILTER (WHERE vendor_id = ? AND NOT is_free), 0) AS lab_spend,
            sum(est_spend_usd) FILTER (WHERE NOT is_free) AS spend,
            sum(total_tokens) FILTER (WHERE NOT is_free AND price_matched) AS priced_tokens,
            coalesce(sum(total_tokens) FILTER (WHERE NOT is_free AND NOT price_matched), 0) AS unpriced_tokens,
            coalesce(sum(total_tokens) FILTER (WHERE NOT is_free AND price_matched AND price_date_stale), 0)
                AS stale_tokens,
            max(blended_usd_per_token) FILTER (WHERE NOT is_free AND price_matched) AS max_price,
            coalesce(sum(total_tokens) FILTER (WHERE vendor_id = ? AND NOT is_free AND NOT price_matched), 0)
                AS lab_unpriced_tokens,
            string_agg(DISTINCT model_permaslug, ', ')
                FILTER (WHERE vendor_id = ? AND NOT is_free AND NOT price_matched) AS lab_unpriced_models
        FROM d
        GROUP BY week
        ORDER BY week
        """,
        [LAB] * 5,
    )


def vercel_weeks(con) -> pl.DataFrame:
    """Per week: the mean of daily Anthropic shares (Vercel publishes no volumes); a day without an
    Anthropic row counts 0."""
    return query(
        con,
        """
        WITH days AS (SELECT DISTINCT date, metric FROM vercel_lab_share WHERE metric IN ('spend', 'tokens')),
        lab AS (
            SELECT date, metric, sum(share_pct) AS s FROM vercel_lab_share WHERE vendor_id = ? GROUP BY 1, 2
        )
        SELECT CAST(date_trunc('week', d.date) + INTERVAL 6 DAY AS DATE) AS week, d.metric,
               count(*) AS days, avg(coalesce(l.s, 0)) AS share_pct
        FROM days d LEFT JOIN lab l USING (date, metric)
        GROUP BY 1, 2
        ORDER BY 1, 2
        """,
        [LAB],
    )


def ramp_weeks(con) -> pl.DataFrame:
    """Ramp's own weekly shares (Monday–Sunday, dated by the Sunday): week totals over the makers it reports."""
    return query(
        con,
        """
        SELECT week, measure, 100 * share AS share_pct, makers_with_data
        FROM ramp_token_share WHERE vendor_id = ? AND share IS NOT NULL
        ORDER BY week, measure
        """,
        [LAB],
    )


def weekly(orw: pl.DataFrame, vw: pl.DataFrame, rw: pl.DataFrame, min_days: int) -> pl.DataFrame:
    """Long frame: week × source × measure × variant, weeks with at least `min_days` days of data (gateways;
    Ramp's weeks are whole), with a trailing 4-week mean. `days` shows the 6-day weeks."""
    o = orw.filter(pl.col("days") >= min_days)
    parts = [
        rw.select(
            "week",
            source=pl.lit("ramp"),
            measure=pl.when(pl.col("measure") == "volume").then(pl.lit("tokens")).otherwise(pl.lit("spend")),
            variant=pl.lit(None, pl.String),
            share_pct="share_pct",
            days=pl.lit(7),
        ),
        vw.filter(pl.col("days") >= min_days).select(
            "week",
            source=pl.lit("vercel"),
            measure="metric",
            variant=pl.lit(None, pl.String),
            share_pct="share_pct",
            days="days",
        ),
        o.select(
            "week",
            source=pl.lit("openrouter"),
            measure=pl.lit("spend"),
            variant=pl.lit(None, pl.String),
            share_pct=100 * pl.col("lab_spend") / pl.col("spend"),
            days="days",
        ),
        o.select(
            "week",
            source=pl.lit("openrouter"),
            measure=pl.lit("tokens"),
            variant=pl.lit("paid"),
            share_pct=100 * pl.col("lab_tokens_paid").fill_null(0) / pl.col("tokens_paid"),
            days="days",
        ),
        o.select(
            "week",
            source=pl.lit("openrouter"),
            measure=pl.lit("tokens"),
            variant=pl.lit("all"),
            share_pct=100 * pl.col("lab_tokens_all").fill_null(0) / pl.col("tokens_all"),
            days="days",
        ),
    ]
    df = pl.concat([p.with_columns(pl.col("days").cast(pl.Int64)) for p in parts])
    return rolling(df, "share_pct", "rolling4_pct")


def rolling(df: pl.DataFrame, col: str, out: str) -> pl.DataFrame:
    """Trailing mean over 4 consecutive weeks per series; null unless all 4 weeks are present (a gap, e.g. an
    OpenRouter week missing a day, breaks the line for four weeks rather than averaging across it)."""
    keys = [k for k in ("source", "measure", "variant") if k in df.columns]
    rows = []
    groups = df.sort("week").group_by(keys, maintain_order=True) if keys else [((), df.sort("week"))]
    for _, g in groups:
        grid = pl.DataFrame({"week": pl.date_range(g["week"].min(), g["week"].max(), interval="1w", eager=True)})
        full = grid.join(g, on="week", how="left")
        full = full.with_columns(pl.col(col).rolling_mean(4, min_samples=4).alias(out))
        rows.append(
            full.filter(pl.col(col).is_not_null()).with_columns(
                [pl.lit(g[k][0], dtype=df.schema[k]).alias(k) for k in keys]
            )
        )
    return pl.concat(rows).select(df.columns + [out]).sort([*keys, "week"])


def ramp_checks(con) -> pl.DataFrame:
    """Ramp data quality: per-week share sums (must be 100%) and each maker's share in its first week."""
    sums = query(
        con,
        "SELECT measure, min(s) AS min_sum, max(s) AS max_sum FROM "
        "(SELECT week, measure, 100 * sum(share) AS s FROM ramp_token_share GROUP BY 1, 2) GROUP BY 1",
    )
    first = query(
        con,
        """
        SELECT maker_label, week AS first_week, 100 * share AS first_week_spend_pct
        FROM ramp_token_share
        WHERE measure = 'spend' AND share IS NOT NULL
        QUALIFY row_number() OVER (PARTITION BY maker_label ORDER BY week) = 1
        """,
    )
    entrants = first.filter(pl.col("first_week") > first["first_week"].min())
    return pl.DataFrame(
        [
            {
                "ramp_share_sum_min_pct": sums["min_sum"].min(),
                "ramp_share_sum_max_pct": sums["max_sum"].max(),
                "ramp_entrants_aug_nov_2025_max_first_week_pct": entrants.filter(
                    pl.col("first_week").is_between(date(2025, 8, 1), date(2025, 11, 30))
                )["first_week_spend_pct"].max(),
                "ramp_entrants": ", ".join(
                    f"{m} {w} {pct:.4f}%"
                    for m, w, pct in entrants.sort("first_week")
                    .select("maker_label", "first_week", "first_week_spend_pct")
                    .iter_rows()
                ),
            }
        ]
    )


# ---- OpenRouter spend bound ------------------------------------------------------------------


def or_bound(orw: pl.DataFrame, min_days: int) -> pl.DataFrame:
    """Per week drawn (≥ min_days): computed share (upper bound while Anthropic is fully priced), the sensitivity with
    unpriced paid tokens at the week's mean priced price, and the lower bound with them at the dearest
    priced model's price (assumes no unpriced model is dearer)."""
    o = orw.filter(pl.col("days") >= min_days)
    mean_price = pl.col("spend") / pl.col("priced_tokens")
    b = o.select(
        "week",
        computed_pct=100 * pl.col("lab_spend") / pl.col("spend"),
        sensitivity_pct=100 * pl.col("lab_spend") / (pl.col("spend") + pl.col("unpriced_tokens") * mean_price),
        lower_bound_pct=100 * pl.col("lab_spend") / (pl.col("spend") + pl.col("unpriced_tokens") * pl.col("max_price")),
        unpriced_pct=100 * pl.col("unpriced_tokens") / (pl.col("priced_tokens") + pl.col("unpriced_tokens")),
        stale_pct=100 * pl.col("stale_tokens") / (pl.col("priced_tokens") + pl.col("unpriced_tokens")),
    )
    b = rolling(b, "computed_pct", "computed_r4")
    return rolling(b, "sensitivity_pct", "sensitivity_r4")


def check_lab_priced(orw: pl.DataFrame, min_days: int) -> None:
    """Author decision 4b: stop when a week drawn has unpriced Anthropic tokens (a model not yet mapped)."""
    bad = orw.filter((pl.col("days") >= min_days) & (pl.col("lab_unpriced_tokens") > 0))
    if bad.height:
        r = bad.row(0, named=True)
        raise ValueError(
            f"OpenRouter week ending {r['week']}: unpriced Anthropic tokens ({r['lab_unpriced_models']}); map the "
            "model in config/entities/models.yaml (`cachereg entities suggest --source openrouter`), rebuild, render"
        )


# ---- story -----------------------------------------------------------------------------------


def latest_common(w: pl.DataFrame, measure: str, variant: str | None) -> tuple[date, dict[str, float]]:
    """The latest week where all three sources have a 4-week value, and those values."""
    s = series(w, measure, variant).filter(pl.col("rolling4_pct").is_not_null())
    weeks = set.intersection(*(set(s.filter(pl.col("source") == src)["week"]) for src in SOURCES))
    wk = max(weeks)
    vals = dict(s.filter(pl.col("week") == wk).select("source", "rolling4_pct").iter_rows())
    return wk, vals


def series(w: pl.DataFrame, measure: str, variant: str | None) -> pl.DataFrame:
    """One visual's three series: OpenRouter's token variant selected, the other sources as they are."""
    s = w.filter(pl.col("measure") == measure)
    if measure == "tokens":
        s = s.filter((pl.col("source") != "openrouter") | (pl.col("variant") == variant))
    return s


TITLE = "Different data sources tell different stories about the AI economy"
# The measure, stamped on the chart's face (charts.py), one per visual.
STAMP = {
    "spend": "Anthropic's share of total spend in each data source",
    "tokens-with-free": "Anthropic's share of total tokens in each data source",
}


def _when(week: date) -> str:
    """'by the end of September' when the week ends in the month's last 7 days, else 'in the week to 13 September'."""
    if (week + timedelta(days=7)).month != week.month:
        return f"by the end of {week:%B}"
    return f"in the week to {week:%-d %B}"


def _subtitle(kind: str, week: date, vals: dict[str, float]) -> str:
    parts = [f"{vals[s]:.0f}% on {NAMES[s]}" for s in SOURCES]
    listed = ", ".join(parts[:-1]) + " and " + parts[-1]
    return (
        f"Anthropic's share of all {kind} varies widely between sources and over time; {_when(week)} "
        f"{week:%Y} it stood at {listed} (4-week averages)."
    )


def build(con, as_of: date, cfg: dict) -> Story:
    orw, vw, rw = openrouter_weeks(con), vercel_weeks(con), ramp_weeks(con)
    min_days = int(cfg.get("min_days", 6))  # a gateway week with one day missing still gives its share
    check_lab_priced(orw, min_days)
    w = weekly(orw, vw, rw, min_days)
    if cfg.get("start"):
        w = w.filter(pl.col("week") >= _sunday(date.fromisoformat(str(cfg["start"]))))
    bound = or_bound(orw, min_days).filter(pl.col("week") >= w["week"].min())

    by_visual, extra = {}, {}
    for name, (measure, variant) in VISUALS.items():
        wk, vals = latest_common(w, measure, variant)
        extra[name] = {"week": str(wk), "values": vals}
        kind = "spend" if measure == "spend" else "tokens"
        if measure == "spend":
            notes = [
                "OpenRouter spend is Cache Register's list-price estimate (caching ignored); band: unpriced tokens "
                "at the week's average price."
            ]
        else:
            scope = "includes free models" if variant == "all" else "excludes free models"
            notes = [f"OpenRouter {scope}. Tokens are counted by each provider's tokenizer."]
        by_visual[name] = {"title": TITLE, "subtitle": _subtitle(kind, wk, vals), "notes": notes}

    lw = orw.filter(pl.col("days") >= min_days)
    coverage = (
        lw.select(
            "week",
            priced_pct_of_paid=100 * pl.col("priced_tokens") / (pl.col("priced_tokens") + pl.col("unpriced_tokens")),
            stale_pct_of_paid=100 * pl.col("stale_tokens") / (pl.col("priced_tokens") + pl.col("unpriced_tokens")),
            free_pct_of_all=100 * (1 - pl.col("tokens_paid") / pl.col("tokens_all")),
        )
        .join(
            rw.filter(pl.col("measure") == "spend").select("week", "makers_with_data"),
            on="week",
            how="full",
            coalesce=True,
        )
        .sort("week")
    )
    first_last = w.group_by("source").agg(first=pl.col("week").min(), last=pl.col("week").max()).sort("source")
    dropped = pl.concat(
        [
            orw.filter(pl.col("days") < min_days).select("week", source=pl.lit("openrouter"), days="days"),
            vw.filter(pl.col("days") < min_days).select("week", source=pl.lit("vercel"), days="days").unique(),
        ]
    ).sort("source", "week")
    q = bound.with_columns(
        q=pl.col("week").dt.year().cast(pl.String) + " Q" + pl.col("week").dt.quarter().cast(pl.String)
    )
    bound_q = (
        q.group_by("q")
        .agg(
            pl.col("computed_pct").mean(),
            pl.col("sensitivity_pct").mean(),
            pl.col("lower_bound_pct").mean(),
            pl.col("unpriced_pct").mean(),
            weeks=pl.len(),
        )
        .sort("q")
    )

    first = by_visual["spend"]
    return Story(
        title=first["title"],
        subtitle=first["subtitle"],
        frames={
            "weekly": w,
            "or_bound": bound,
            "or_bound_quarterly": bound_q,
            "coverage": coverage,
            "first_last": first_last,
            "partial_weeks_dropped": dropped,
            # presence: Anthropic's lowest weekly spend share per source over its weeks drawn (> 0 = present
            # every week; a Vercel day without an Anthropic row would count 0)
            "checks": ramp_checks(con).with_columns(
                anthropic_full_weeks_min_spend_share=pl.lit(
                    ", ".join(
                        f"{src} {n} weeks, min {lo:.1f}%"
                        for src, n, lo in w.filter(pl.col("measure") == "spend")
                        .group_by("source")
                        .agg(pl.len(), pl.col("share_pct").min())
                        .sort("source")
                        .iter_rows()
                    )
                )
            ),
        },
        sources=["ramp_ai_index", "vercel_ai_gateway", "openrouter_rankings", "litellm_prices"],
        as_of=as_of,
        method=(
            f"Anthropic's share of each source's reported total per Mon–Sun week; weeks with ≥ {min_days} days of data"
        ),
        notes=first["notes"],
        caveats=[
            "Three populations: Ramp customers who connected their AI providers; Vercel AI Gateway users; "
            "OpenRouter users. None is the market.",
            "Spend measured three ways: Ramp realised, Vercel's measure, OpenRouter our list-price estimate (caching "
            "ignored), so part of a gap may be method, not segment.",
        ],
        extra={"visuals": extra, "stamp": STAMP, "start": str(w["week"].min())},
        by_visual=by_visual,
    )

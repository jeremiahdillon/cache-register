"""Anthropic's share of spend and tokens, by data source.

Receipt (cacheregister.dev/source-matters), promoted from explore/2026-10-10-anthropic-share-by-source. Reads
marts 010 (or_model_daily), 062 (ramp_token_share), 090 (vercel_lab_share) and 095/096 (dbx_vendor_share_week,
dbx_vendor_spend_week, dbx_segment_price_week, dbx_spend_mix_week); never cachereg.sources. See
README.md for method and docs/plans/2026-10-10-anthropic-share-by-source.md for the design and the author's
decisions. `cachereg render receipts/source-matters` renders the visuals declared in receipt.yaml into output/.

Every line is the same measure, Anthropic's share of all its source reports, so the sources share one axis
(author decision). The sources see different populations and measure spend differently; the README says
which differences may be method rather than segment. Each line runs to its own source's latest week (author,
2026-11-18), so the lines end at different dates.
"""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

LAB = "anthropic"
SOURCES = ["ramp", "databricks", "vercel", "openrouter"]
NAMES = {"ramp": "Ramp", "databricks": "Databricks", "vercel": "Vercel", "openrouter": "OpenRouter"}
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


def databricks_weeks(con) -> pl.DataFrame:
    """Databricks (Unity Gateway), per Monday–Sunday week dated by its Sunday: Anthropic's share of ALL tokens
    (its share of proprietary tokens × the proprietary share of tokens) and of ALL spend (its wallet share of
    proprietary × (1 − the estimated open-weight share of spend), with that estimate's sensitivity range;
    mart 096)."""
    return query(
        con,
        """
        SELECT t.week, t.share_of_all_pct AS tokens_pct, s.share_of_all_pct AS spend_pct,
               s.share_of_all_lo_pct AS spend_lo_pct, s.share_of_all_hi_pct AS spend_hi_pct,
               t.share_of_segment_pct AS tokens_of_proprietary_pct, s.wallet_of_segment_pct AS spend_of_proprietary_pct,
               s.open_spend_pct
        FROM dbx_vendor_share_week t
        LEFT JOIN dbx_vendor_spend_week s USING (week, vendor_id, segment)
        WHERE t.vendor_id = ? AND t.metric = 'tokens' AND t.segment = 'proprietary'
        ORDER BY t.week
        """,
        [LAB],
    )


def databricks_coverage(con) -> pl.DataFrame:
    """Per week: the token mix, the estimated open-weight share of spend and how much of each segment's tokens the
    price estimate rests on (named models with a LiteLLM price; stale = nearest listing, not that day's)."""
    return query(
        con,
        """
        SELECT m.week, m.proprietary_token_pct, m.open_token_pct, m.open_spend_pct, m.open_spend_pct_lo,
               m.open_spend_pct_hi, 1e6 * m.p_prop AS prop_usd_per_m, 1e6 * m.p_open AS open_usd_per_m,
               pp.priced_token_pct AS prop_priced_token_pct, po.priced_token_pct AS open_priced_token_pct,
               pp.stale_priced_token_pct AS prop_stale_token_pct, po.stale_priced_token_pct AS open_stale_token_pct,
               pp.named_unpriced AS prop_named_unpriced, po.named_unpriced AS open_named_unpriced
        FROM dbx_spend_mix_week m
        JOIN dbx_segment_price_week pp ON pp.week_start = m.week_start AND pp.segment = 'proprietary'
        JOIN dbx_segment_price_week po ON po.week_start = m.week_start AND po.segment = 'open_weight'
        ORDER BY m.week
        """,
    )


def weekly(orw: pl.DataFrame, vw: pl.DataFrame, rw: pl.DataFrame, dw: pl.DataFrame, min_days: int) -> pl.DataFrame:
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
        dw.select(
            "week",
            source=pl.lit("databricks"),
            measure=pl.lit("tokens"),
            variant=pl.lit(None, pl.String),
            share_pct="tokens_pct",
            days=pl.lit(7),
        ),
        dw.drop_nulls("spend_pct").select(
            "week",
            source=pl.lit("databricks"),
            measure=pl.lit("spend"),
            variant=pl.lit(None, pl.String),
            share_pct="spend_pct",
            days=pl.lit(7),
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


def dbx_bound(dw: pl.DataFrame) -> pl.DataFrame:
    """Databricks spend: the estimate and its sensitivity (open-weight prices × 2 → lo, × ½ → hi), 4-week means."""
    b = dw.drop_nulls("spend_pct").select("week", est_pct="spend_pct", lo_pct="spend_lo_pct", hi_pct="spend_hi_pct")
    b = rolling(b, "lo_pct", "lo_r4")
    return rolling(b, "hi_pct", "hi_r4")


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


def latest_each(w: pl.DataFrame, measure: str, variant: str | None) -> dict[str, dict]:
    """Each source's latest week with a 4-week value, and that value (the lines end at different weeks)."""
    s = series(w, measure, variant).filter(pl.col("rolling4_pct").is_not_null())
    out = {}
    for src in SOURCES:
        r = s.filter(pl.col("source") == src).sort("week").row(-1, named=True)
        out[src] = {"week": str(r["week"]), "value": r["rolling4_pct"]}
    return out


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


def _subtitle(kind: str, ends: dict[str, dict]) -> str:
    """Each source's latest 4-week value, grouped by the week it ends (earliest first)."""
    by_week: dict[str, list[str]] = {}
    for src in sorted(SOURCES, key=lambda x: (ends[x]["week"], -ends[x]["value"])):
        by_week.setdefault(ends[src]["week"], []).append(f"{ends[src]['value']:.0f}% on {NAMES[src]}")
    groups = []
    for wk, parts in by_week.items():
        d = date.fromisoformat(wk)
        listed = ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]
        groups.append(f"{listed} (to {d:%-d %b})")
    last = max(date.fromisoformat(v["week"]) for v in ends.values())
    return (
        f"Anthropic's share of all {kind} varies widely between sources and over time. Latest 4-week averages "
        f"({last:%Y}): " + "; ".join(groups) + "."
    )


def build(con, as_of: date, cfg: dict) -> Story:
    orw, vw, rw, dw = openrouter_weeks(con), vercel_weeks(con), ramp_weeks(con), databricks_weeks(con)
    min_days = int(cfg.get("min_days", 6))  # a gateway week with one day missing still gives its share
    check_lab_priced(orw, min_days)
    w = weekly(orw, vw, rw, dw, min_days)
    if cfg.get("start"):
        w = w.filter(pl.col("week") >= _sunday(date.fromisoformat(str(cfg["start"]))))
    bound = or_bound(orw, min_days).filter(pl.col("week") >= w["week"].min())
    dbound = dbx_bound(dw).filter(pl.col("week") >= w["week"].min())

    by_visual, extra = {}, {}
    for name, (measure, variant) in VISUALS.items():
        ends = latest_each(w, measure, variant)
        extra[name] = {"ends": ends}
        kind = "spend" if measure == "spend" else "tokens"
        if measure == "spend":
            notes = [
                "OpenRouter spend is Cache Register's list-price estimate (caching ignored); band: unpriced tokens "
                "at the week's average price."
            ]
        else:
            scope = "includes free models" if variant == "all" else "excludes free models"
            notes = [f"OpenRouter {scope}. Tokens are counted by each provider's tokenizer."]
        by_visual[name] = {"title": TITLE, "subtitle": _subtitle(kind, ends), "notes": notes}

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
            "dbx_bound": dbound,
            "dbx_weekly": dw,
            "dbx_coverage": databricks_coverage(con),
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
        sources=["ramp_ai_index", "vercel_ai_gateway", "openrouter_rankings", "litellm_prices", "databricks_ai_index"],
        as_of=as_of,
        method=f"Anthropic's share of each source's total per Mon–Sun week (≥ {min_days} days of data)",
        notes=first["notes"],
        caveats=[
            "Four populations: Ramp customers who connected their AI providers; Databricks Unity Gateway "
            "enterprises; Vercel AI Gateway users; OpenRouter users. None is the market.",
            "Spend measured four ways: Ramp realised, Vercel's measure, Databricks list prices (rescaled by our "
            "estimate of the open-weight share), OpenRouter our list-price estimate (caching ignored), so part of a "
            "gap may be method, not segment.",
        ],
        extra={"visuals": extra, "stamp": STAMP, "start": str(w["week"].min())},
        by_visual=by_visual,
    )

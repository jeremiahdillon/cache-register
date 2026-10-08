"""Chinese labs' share of OpenRouter spend: weekly share of estimated OpenRouter spend among the three.

Reads marts only (or_vendor_weekly, dim_vendor_alias). See README.md for method and caveats.
`cachereg render explore/2026-10-07-china-spend-share` renders the visuals declared in explore.yaml.
"""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

CHINA = "Chinese labs"
CLOSED_BANDS = ["OpenAI", "Anthropic"]  # shown first, the WSJ-style two-way split
BANDS_ORDER = ["OpenAI", CHINA, "Anthropic"]  # stack bottom to top: China enters between the two
TABLE_PERCENT_COLUMNS = BANDS_ORDER
# Area visuals are smoothed; the bar visuals show each week's actual values. The method line is shared by every
# visual in the folder, so smoothing is stated in a note on the area visuals only.
AREA_VISUALS = ("push", "stack")
SMOOTHED_NOTE = "Areas smoothed: each week = (previous + 2 × this + next week) / 4."
MIN_DAYS = 6  # a week with one missing day still counts (shares, not totals), unless it is the last week
LEVEL_PP = 0.05  # title says "three-way tie" when the three last-week shares are within 5 points


def group_of(vendor_id: str, hq: str | None) -> str | None:
    if vendor_id == "anthropic":
        return "Anthropic"
    if vendor_id == "openai":
        return "OpenAI"
    return CHINA if hq == "CN" else None  # everyone else is left out (footnoted)


def _weekly(con, as_of: date) -> pl.DataFrame:
    return query(
        con,
        """
        WITH v AS (SELECT DISTINCT vendor_id, hq FROM dim_vendor_alias)
        SELECT w.week, w.vendor_id, v.hq, w.tokens, w.est_spend_usd, w.unpriced_tokens,
               w.stale_priced_tokens, w.days
        FROM or_vendor_weekly w LEFT JOIN v USING (vendor_id)
        WHERE w.vendor_id <> '_other' AND w.week + INTERVAL 6 DAY <= ?
        """,
        [as_of],
    )


def smooth_121(wide: pl.DataFrame) -> pl.DataFrame:
    """Display smoothing: each week = (previous + 2 × this + next) / 4; end weeks = (2 × end + neighbour) / 3."""
    cols = [c for c in wide.columns if c != "week"]
    prev, nxt = pl.col("_v").shift(1), pl.col("_v").shift(-1)
    out = wide.select("week")
    for c in cols:
        v = wide.select(pl.col(c).cast(pl.Float64).alias("_v"))
        sm = v.select(
            pl.when(prev.is_null())
            .then((2 * pl.col("_v") + nxt) / 3)
            .when(nxt.is_null())
            .then((2 * pl.col("_v") + prev) / 3)
            .otherwise((prev + 2 * pl.col("_v") + nxt) / 4)
            .alias(c)
        )
        out = out.with_columns(sm[c])
    return out


def pct(x: float) -> str:
    return "under 1%" if 0 < x < 0.005 else f"{x:.0%}"


def build(con, as_of: date, cfg: dict) -> Story:
    w = _weekly(con, as_of)
    # Weeks judged per week (any vendor's day count). A week counts if it has all 7 days, or MIN_DAYS with a full
    # week after it: OpenRouter's data lacks two single days in 2025 (Jun 15, Jul 15), and shares from the other
    # six days stand for the week. Partial weeks at the end of the data stay out.
    # and the chart bridges them.
    days = w.group_by("week").agg(pl.col("days").max())
    last_full = days.filter(pl.col("days") == 7)["week"].max()
    complete = days.filter((pl.col("days") >= MIN_DAYS) & (pl.col("week") <= last_full))["week"]
    w = w.filter(pl.col("week").is_in(complete.implode()) & (pl.col("week") >= cfg["start"]))
    w = w.with_columns(
        pl.struct("vendor_id", "hq")
        .map_elements(lambda r: group_of(r["vendor_id"], r["hq"]), return_dtype=pl.String)
        .alias("group")
    )
    all_spend = w.group_by("week").agg(pl.col("est_spend_usd").sum().alias("spend_all"))
    shown = w.filter(pl.col("group").is_not_null())
    totals = (
        shown.group_by("week")
        .agg(
            pl.col("est_spend_usd").sum().alias("spend_shown"),
            (pl.col("unpriced_tokens").sum() / pl.col("tokens").sum()).alias("unpriced_share"),
            (pl.col("stale_priced_tokens").sum() / pl.col("tokens").sum()).alias("stale_share"),
        )
        .join(all_spend, on="week")
        .with_columns((1 - pl.col("spend_shown") / pl.col("spend_all")).alias("left_out_share"))
        .sort("week")
    )
    groups = (
        shown.group_by("week", "group")
        .agg(pl.col("est_spend_usd").sum())
        .join(totals.select("week", "spend_shown"), on="week")
        .with_columns((pl.col("est_spend_usd") / pl.col("spend_shown")).alias("share"))
        .drop("spend_shown")
        .sort("week", "group")
    )
    wide = groups.pivot(on="group", index="week", values="est_spend_usd").fill_null(0.0).sort("week")
    wide = wide.select("week", *[pl.col(b) if b in wide.columns else pl.lit(0.0).alias(b) for b in BANDS_ORDER])
    if wide.height < 3:
        raise ValueError(f"need at least 3 complete weeks on or before {as_of}, found {wide.height}")

    first, last = wide["week"].min(), wide["week"].max()
    r0, r1 = wide.row(0, named=True), wide.row(-1, named=True)
    s0 = {b: r0[b] / sum(r0[c] for c in BANDS_ORDER) for b in BANDS_ORDER}
    s1 = {b: r1[b] / sum(r1[c] for c in BANDS_ORDER) for b in BANDS_ORDER}
    two = r1["Anthropic"] / (r1["Anthropic"] + r1["OpenAI"])
    left_out = totals.filter(pl.col("week") == last)["left_out_share"].item()
    left_out_avg = float(totals["left_out_share"].mean())  # mean of weekly shares: "an average week"
    stale_max = float(totals["stale_share"].max())

    end = last + timedelta(days=6)
    # "Three-way tie" only when all three are within LEVEL_PP of each other in the last week.
    level = max(s1.values()) - min(s1.values()) <= LEVEL_PP
    notes = [f"Not shown: Google and other developers, {left_out_avg:.0%} of estimated spend in an average week."]
    return Story(
        title=(
            f"Chinese labs grew from {pct(s0[CHINA])} to {pct(s1[CHINA])} of spend on OpenRouter"
            + (", a three-way tie with Anthropic and OpenAI" if level else "")
            + "."
        ),
        subtitle=(
            f"Share of estimated weekly spend on OpenRouter among Anthropic, OpenAI and Chinese labs, "
            f"{first:%B %Y} to {end:%B %-d, %Y}. "
            f"Week of {last:%B %-d, %Y}: OpenAI {s1['OpenAI']:.0%}, Chinese labs {s1[CHINA]:.0%}, "
            f"Anthropic {s1['Anthropic']:.0%}."
        ),
        frames={"groups": groups, "wide": wide, "display": smooth_121(wide), "totals": totals},
        sources=["openrouter_rankings", "litellm_prices"],
        as_of=as_of,
        method=(
            "est. spend = tokens × list price in LiteLLM on that day (or the nearest date listed; "
            "80% input / 20% output); caching ignored; top-50 models"
        ),
        notes=notes,
        by_visual={v: {"notes": [*notes, SMOOTHED_NOTE]} for v in AREA_VISUALS},
        caveats=[
            "Estimated spend, not revenue: list prices, no negotiated discounts, prompt caching ignored. Caching "
            "discounts are largest for heavily cached coding traffic, so Anthropic's share is likely overstated.",
            "The denominator is Anthropic + OpenAI + Chinese labs only; Google and every other developer are "
            "left out, so these shares are higher than shares of all OpenRouter spend.",
            "OpenRouter traffic only (third-party developer routing), which over-represents cheap and open models "
            "compared with first-party APIs, subscriptions and enterprise contracts.",
            "Chinese labs' early weeks are often priced with LiteLLM listings recorded later (list prices at launch "
            "mostly matched on a spot check; GLM-5.3 Flash's launch discount is not modelled).",
            "Tokens are counted by each provider's own tokenizer.",
        ],
        extra={
            "bands_order": BANDS_ORDER,
            "y_title": "Share of estimated spend",
            "first_week": str(first),
            "last_week": str(last),
            "shares_first": s0,
            "shares_last": s1,
            "anthropic_of_two_last": two,
            "left_out_share_last": left_out,
            "left_out_share_avg": left_out_avg,
            "stale_share_max": stale_max,
            "unpriced_share_max": float(totals["unpriced_share"].max()),
        },
    )


def table(story: Story) -> pl.DataFrame:
    """Weekly share by group (raw, unsmoothed)."""
    g = story.frames["groups"]
    return g.pivot(on="group", index="week", values="share").sort("week").fill_null(0.0).select("week", *BANDS_ORDER)

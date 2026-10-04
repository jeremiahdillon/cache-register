"""Who gets paid on OpenRouter? Weekly share of estimated spend by model developer.

Reads marts only (or_vendor_weekly, dim_vendor_alias). See README.md for method and caveats.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

GROUP_ORDER = ["Anthropic", "OpenAI", "Chinese labs", "Google", "Everyone else"]
TABLE_PERCENT_COLUMNS = GROUP_ORDER
GROUP_COLOR_KEY = {"Anthropic": "anthropic", "OpenAI": "openai", "Chinese labs": "_china", "Google": "google"}


def _weekly(con, as_of: date) -> pl.DataFrame:
    return query(
        con,
        """
        WITH v AS (SELECT DISTINCT vendor_id, vendor_name, hq FROM dim_vendor_alias)
        SELECT w.week, w.vendor_id, coalesce(v.vendor_name, w.vendor_id) AS vendor_name, v.hq,
               w.tokens, w.est_spend_usd, w.unpriced_tokens, w.days
        FROM or_vendor_weekly w LEFT JOIN v USING (vendor_id)
        WHERE w.vendor_id <> '_other' AND w.week + INTERVAL 6 DAY <= ?
        """,
        [as_of],
    )


def group_of(vendor_id: str, hq: str | None) -> str:
    if vendor_id == "anthropic":
        return "Anthropic"
    if vendor_id == "openai":
        return "OpenAI"
    if vendor_id == "google":
        return "Google"
    if hq == "CN":
        return "Chinese labs"
    return "Everyone else"


def headline(a0: float, a1: float, n_weeks: int) -> str:
    """The claim, with the verb taken from the data (never assumed)."""
    span = f"{n_weeks} week" + ("s" if n_weeks != 1 else "")
    if round(a0, 2) == round(a1, 2):
        return f"Anthropic's share of OpenRouter spend held at {a1:.0%} over {span}"
    verb = "fell" if a1 < a0 else "rose"
    return f"Anthropic's share of OpenRouter spend {verb} from {a0:.0%} to {a1:.0%} in {span}"


def build(con, as_of: date, cfg: dict) -> Story:
    w = _weekly(con, as_of)
    # A week is complete when the data covers all 7 days for *some* vendor. Judge per week, never per
    # vendor, or vendors active only part of a week (launches, stealth models) silently drop out.
    complete = w.group_by("week").agg(pl.col("days").max()).filter(pl.col("days") == 7)["week"]
    weeks = sorted(complete.to_list())[-cfg["weeks"] :]
    if len(weeks) < 2:
        raise ValueError(f"need at least 2 complete weeks on or before {as_of}, found {len(weeks)}")
    w = w.filter(pl.col("week").is_in(weeks)).with_columns(
        pl.struct("vendor_id", "hq")
        .map_elements(lambda r: group_of(r["vendor_id"], r["hq"]), return_dtype=pl.String)
        .alias("group")
    )
    totals = w.group_by("week").agg(
        pl.col("est_spend_usd").sum().alias("spend_total"),
        (pl.col("unpriced_tokens").sum() / pl.col("tokens").sum()).alias("unpriced_share"),
    )
    vendor = (
        w.join(totals, on="week")
        .with_columns((pl.col("est_spend_usd") / pl.col("spend_total")).alias("share"))
        .select("week", "vendor_id", "vendor_name", "group", "share", "est_spend_usd", "unpriced_share")
    )
    groups = (
        vendor.group_by("week", "group")
        .agg(pl.col("share").sum(), pl.col("est_spend_usd").sum(), pl.col("unpriced_share").first())
        .sort("week", "group")
    )
    flagged = totals.filter(pl.col("unpriced_share") > cfg["unpriced_flag"]).sort("week")

    first, last = weeks[0], weeks[-1]

    def share(week, group) -> float:
        """A group's share that week; 0 when it had no priced spend at all."""
        s = groups.filter((pl.col("week") == week) & (pl.col("group") == group))["share"]
        return float(s.sum()) if s.len() else 0.0

    a0, a1 = share(first, "Anthropic"), share(last, "Anthropic")
    o1, cn1 = share(last, "OpenAI"), share(last, "Chinese labs")
    spend_last = totals.filter(pl.col("week") == last)["spend_total"].item()

    return Story(
        title=headline(a0, a1, len(weeks) - 1),
        subtitle=(
            f"Share of estimated weekly spend on OpenRouter's top-50 models, by developer. "
            f"Week of {last:%b %-d}: Anthropic {a1:.0%}, OpenAI {o1:.0%}, Chinese labs {cn1:.0%}."
        ),
        frames={"groups": groups, "vendors": vendor, "flagged": flagged, "totals": totals},
        sources=["openrouter_rankings", "litellm_prices"],
        as_of=as_of,
        method=(
            "est. spend = tokens × that day's list price in LiteLLM (80% input / 20% output); caching ignored; "
            "top-50 models only"
        ),
        notes=[f"Shaded weeks: >{cfg['unpriced_flag']:.0%} of tokens have no list price."] if flagged.height else [],
        notes_by_kind={
            "video": [
                "Weeks of "
                + " and ".join(f"{d:%b %-d}" for d in flagged["week"].to_list())
                + f": >{cfg['unpriced_flag']:.0%} of tokens have no list price."
            ]
            if flagged.height
            else []
        },
        caveats=[
            "Estimated spend, not revenue: list prices, no negotiated discounts, prompt caching ignored. "
            "Caching discounts are largest for heavily-cached coding traffic, so Anthropic's share is likely an "
            "upper bound.",
            "Tokens are counted by each provider's own tokenizer, so token volumes aren't strictly comparable "
            "across developers.",
            "OpenRouter traffic only (third-party developer routing), not the whole market. Models outside the "
            "daily top 50 are excluded (no per-model price).",
            "Prices come from a single current price snapshot; weeks where models without a list price "
            "(retired or pre-release) exceed the threshold are shaded.",
        ],
        extra={"weeks": [str(x) for x in weeks], "spend_last_week_usd": spend_last},
    )


def table(story: Story) -> pl.DataFrame:
    """Weekly share by group, for the HTML data table."""
    g = story.frames["groups"]
    wide = g.pivot(on="group", index="week", values="share").sort("week").fill_null(0.0)
    return wide.select(["week", *[c for c in GROUP_ORDER if c in wide.columns]])

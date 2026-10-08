"""Chinese labs' share of OpenRouter tokens: weekly share of tokens among Anthropic, OpenAI and Chinese labs.

Token companion to explore/2026-10-07-china-spend-share (same chart, tokens instead of estimated spend).
Reads marts only (or_rankings_daily, dim_vendor_alias). See README.md for method and caveats.
`cachereg render explore/2026-10-07-china-token-share` renders the visuals declared in explore.yaml.
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
EMBEDDING = r"embed|bge-|/bge|e5-|minilm"  # as in open-middle: embedding models are not chat/completion traffic


def group_of(vendor_id: str | None, hq: str | None) -> str | None:
    if vendor_id == "anthropic":
        return "Anthropic"
    if vendor_id == "openai":
        return "OpenAI"
    return CHINA if hq == "CN" else None  # everyone else, stealth names and the "other" row are left out


def _weekly(con, as_of: date) -> pl.DataFrame:
    """Tokens per (week, vendor), embeddings excluded; `days` = days of data that week (any model)."""
    return query(
        con,
        """
        WITH v AS (SELECT DISTINCT alias, vendor_id, hq FROM dim_vendor_alias WHERE source = 'openrouter'),
        d AS (
            SELECT r.date, r.total_tokens, v.vendor_id, v.hq
            FROM or_rankings_daily r LEFT JOIN v ON v.alias = split_part(r.model_permaslug, '/', 1)
            WHERE r.date <= ? AND NOT regexp_matches(r.model_permaslug, ?)
        ),
        n AS (SELECT date_trunc('week', date)::DATE AS week, count(DISTINCT date) AS days FROM d GROUP BY 1)
        SELECT date_trunc('week', d.date)::DATE AS week, d.vendor_id, d.hq, sum(d.total_tokens) AS tokens, n.days
        FROM d JOIN n ON n.week = date_trunc('week', d.date)::DATE
        GROUP BY ALL
        """,
        [as_of, EMBEDDING],
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
    # A week counts if it has all 7 days, or MIN_DAYS with a full week after it: OpenRouter's data lacks two
    # single days in 2025 (Jun 15, Jul 15), and shares from the other six days stand for the week. Partial weeks
    # at the end of the data stay out.
    last_full = w.filter(pl.col("days") == 7)["week"].max()
    w = w.filter((pl.col("days") >= MIN_DAYS) & (pl.col("week") <= last_full) & (pl.col("week") >= cfg["start"]))
    w = w.with_columns(
        pl.struct("vendor_id", "hq")
        .map_elements(lambda r: group_of(r["vendor_id"], r["hq"]), return_dtype=pl.String)
        .alias("group")
    )
    # Attributed = tokens of a named developer. Not attributed: OpenRouter's "other" row (no vendor) and stealth
    # or router names (vendor ids starting "_"); the spend companion leaves them out too (no price).
    attributed = pl.col("vendor_id").is_not_null() & ~pl.col("vendor_id").str.starts_with("_")
    all_tokens = w.group_by("week").agg(
        pl.col("tokens").filter(attributed).sum().alias("tokens_attributed"),
        pl.col("tokens").sum().alias("tokens_all"),
    )
    shown = w.filter(pl.col("group").is_not_null())
    totals = (
        shown.group_by("week")
        .agg(pl.col("tokens").sum().alias("tokens_shown"))
        .join(all_tokens, on="week")
        .with_columns(
            (1 - pl.col("tokens_shown") / pl.col("tokens_attributed")).alias("left_out_share"),
            (1 - pl.col("tokens_attributed") / pl.col("tokens_all")).alias("unattributed_share"),
        )
        .sort("week")
    )
    groups = (
        shown.group_by("week", "group")
        .agg(pl.col("tokens").sum())
        .join(totals.select("week", "tokens_shown"), on="week")
        .with_columns((pl.col("tokens") / pl.col("tokens_shown")).alias("share"))
        .drop("tokens_shown")
        .sort("week", "group")
    )
    wide = groups.pivot(on="group", index="week", values="tokens").fill_null(0).sort("week")
    wide = wide.select("week", *[pl.col(b) if b in wide.columns else pl.lit(0).alias(b) for b in BANDS_ORDER])
    if wide.height < 3:
        raise ValueError(f"need at least 3 complete weeks on or before {as_of}, found {wide.height}")

    first, last = wide["week"].min(), wide["week"].max()
    r0, r1 = wide.row(0, named=True), wide.row(-1, named=True)
    s0 = {b: r0[b] / sum(r0[c] for c in BANDS_ORDER) for b in BANDS_ORDER}
    s1 = {b: r1[b] / sum(r1[c] for c in BANDS_ORDER) for b in BANDS_ORDER}
    left_out = totals.filter(pl.col("week") == last)["left_out_share"].item()
    unattributed = totals.filter(pl.col("week") == last)["unattributed_share"].item()
    # Everything left out (other named developers and unattributed traffic) as a share of all tokens, averaged
    # over weeks: "an average week".
    left_out_avg = float((1 - totals["tokens_shown"] / totals["tokens_all"]).mean())

    end = last + timedelta(days=6)
    # The comparison clause follows the data: more than the other two combined, else larger than each, else none.
    others = s1["Anthropic"] + s1["OpenAI"]
    if s1[CHINA] > others:
        versus = ", more than Anthropic and OpenAI combined"
    elif s1[CHINA] > max(s1["Anthropic"], s1["OpenAI"]):
        versus = ", more than Anthropic or OpenAI"
    else:
        versus = ""
    notes = [
        "Not shown: Google, other developers and unattributed traffic (incl. stealth models), "
        f"{left_out_avg:.0%} of tokens in an average week."
    ]
    return Story(
        title=f"Chinese labs grew from {pct(s0[CHINA])} to {pct(s1[CHINA])} of tokens on OpenRouter{versus}.",
        subtitle=(
            f"Share of weekly tokens on OpenRouter among Anthropic, OpenAI and Chinese labs, "
            f"{first:%B %Y} to {end:%B %-d, %Y}. "
            f"Week of {last:%B %-d, %Y}: OpenAI {s1['OpenAI']:.0%}, Chinese labs {s1[CHINA]:.0%}, "
            f"Anthropic {s1['Anthropic']:.0%}."
        ),
        frames={"groups": groups, "wide": wide, "display": smooth_121(wide), "totals": totals},
        sources=["openrouter_rankings"],
        as_of=as_of,
        method=(
            "tokens as reported by OpenRouter, each model's own tokenizer; free variants included; embeddings "
            "excluded; top-50 models"
        ),
        notes=notes,
        by_visual={v: {"notes": [*notes, SMOOTHED_NOTE]} for v in AREA_VISUALS},
        caveats=[
            "Tokens, not spend or revenue: Chinese-lab models are far cheaper per token, so their share of tokens "
            "is much larger than their share of spend (see the spend companion).",
            "The denominator is Anthropic + OpenAI + Chinese labs only; Google and every other developer are left "
            "out. So are tokens not attributed to a developer: OpenRouter's 'other' row (models outside the daily "
            "top 50, which may include Chinese-lab models) and models under stealth names.",
            "OpenRouter traffic only (third-party developer routing), which over-represents cheap, free and open "
            "models compared with first-party APIs, subscriptions and enterprise contracts.",
            "Free variants are included, so promotional free launches count in full.",
            "Tokens are counted by each provider's own tokenizer, so volumes are not strictly comparable.",
        ],
        extra={
            "bands_order": BANDS_ORDER,
            "y_title": "Share of tokens",
            "first_week": str(first),
            "last_week": str(last),
            "shares_first": s0,
            "shares_last": s1,
            "left_out_share_last": left_out,
            "unattributed_share_last": unattributed,
            "left_out_share_avg": left_out_avg,
        },
    )


def table(story: Story) -> pl.DataFrame:
    """Weekly share by group (raw, unsmoothed)."""
    g = story.frames["groups"]
    return g.pivot(on="group", index="week", values="share").sort("week").fill_null(0.0).select("week", *BANDS_ORDER)

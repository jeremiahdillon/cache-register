"""Mid-size open-weight models on OpenRouter: weekly tokens by model type (exploration).

Reads the or_rankings_daily mart and tiers.yaml (hand-curated model facts). See README.md for method.
`cachereg render explore/2026-10-05-beam-class-share` renders the visuals declared in explore.yaml.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

import polars as pl
import yaml

from cachereg.core.warehouse import query
from cachereg.story.model import Story

HERE = Path(__file__).parent
WINDOW_START = date(2025, 1, 6)  # first complete Monday-to-Sunday week of 2025

MID = "Mid-size open"
OPEN_BANDS = ["Small open", MID, "Flagship open"]  # default stack order, bottom to top
# Closed bands sit above the open ones, bottom to top: the named labs, then everyone else on top.
CLOSED_BANDS = ["Google", "OpenAI", "Anthropic", "Other closed"]
UNATTRIBUTED = "Unattributed"
VENDOR_BAND = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google"}
STEALTH = re.compile(r"^(stealth|openrouter)/")  # cloaked pre-release names (free test traffic)


def load_tiers() -> dict:
    return yaml.safe_load((HERE / "tiers.yaml").read_text())


EMBEDDING = re.compile(r"embed|bge-|/bge|e5-|minilm")
OTHER_CLOSED_LABS = {"x-ai", "amazon", "cohere", "perplexity", "ai21", "inflection", "writer", "baidu"}


def band_of(model: str, tiers: dict) -> str:
    if model == "other":
        return UNATTRIBUTED  # OpenRouter's catch-all row for everything outside the daily top 50
    m = tiers["models"].get(model)
    if m is None:  # long tail (<0.2% of tokens): its lab if closed, else small open (see tiers.yaml exceptions)
        lab = model.split("/")[0]
        if "gemma" in model or "gpt-oss" in model:
            return "Small open"
        if lab in VENDOR_BAND:
            return VENDOR_BAND[lab]
        return "Other closed" if lab in OTHER_CLOSED_LABS else "Small open"
    if m.get("weights") in ("open", "intent"):
        b = tiers["bands"]
        if m["total_b"] < b["small_below_b"]:
            return "Small open"
        return "Flagship open" if m["total_b"] >= b["flagship_from_b"] else MID
    return VENDOR_BAND.get(m.get("vendor") or model.split("/")[0], "Other closed")


def weekly_tokens(con, as_of: date) -> pl.DataFrame:
    """Tokens per (week, model): `:free` merged, complete weeks only."""
    df = query(
        con,
        """
        SELECT date_trunc('week', date)::DATE AS week,
               regexp_replace(model_permaslug, ':free$', '') AS model,
               sum(total_tokens) AS tokens, count(DISTINCT date) AS days
        FROM or_rankings_daily
        WHERE date <= ?
        GROUP BY ALL
        """,
        [as_of],
    )
    full = df.group_by("week").agg(pl.col("days").max()).filter(pl.col("days") == 7)["week"]
    return df.filter(pl.col("week").is_in(full.implode()) & (pl.col("week") >= WINDOW_START)).drop("days")


def growth_share(wide: pl.DataFrame, start: date, end: date, cols: list[str], weeks: int = 4) -> float:
    """Mid-size open's share of the rise in weekly tokens, comparing `weeks`-week averages."""

    def avg(first: date) -> dict:
        span = wide.filter((pl.col("week") >= first) & (pl.col("week") < first + timedelta(weeks=weeks)))
        return span.select(pl.col(c).mean() for c in cols).row(0, named=True)

    a, z = avg(start), avg(end - timedelta(weeks=weeks - 1))
    return (z[MID] - a[MID]) / (sum(z[c] for c in cols) - sum(a[c] for c in cols))


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


def in_words(share: float, tolerance: float = 0.015) -> str | None:
    """'3 out of every 4' when a simple fraction is within `tolerance` of the share."""
    f = Fraction(share).limit_denominator(5)
    if f.denominator > 1 and abs(float(f) - share) <= tolerance:
        return f"{f.numerator}\u00a0out\u00a0of\u00a0every\u00a0{f.denominator}"  # non-breaking: one line
    return None


def build(con, as_of: date, cfg: dict) -> Story:
    tiers = load_tiers()
    show_u = cfg.get("show_unattributed", False)
    open_bands = cfg.get("open_order", OPEN_BANDS)
    bands_order = [*open_bands, *CLOSED_BANDS, *([UNATTRIBUTED] if show_u else [])]

    w = weekly_tokens(con, as_of).filter(
        ~pl.col("model").is_in(tiers["exclude"]) & ~pl.col("model").str.contains(EMBEDDING.pattern)
    )
    stealth = w.filter(pl.col("model").str.contains(STEALTH.pattern))
    w = w.filter(~pl.col("model").str.contains(STEALTH.pattern))
    w = w.with_columns(pl.col("model").map_elements(lambda m: band_of(m, tiers), return_dtype=pl.String).alias("band"))
    bands = w.group_by("week", "band").agg(pl.col("tokens").sum()).sort("week", "band")
    wide = bands.pivot(on="band", index="week", values="tokens").fill_null(0).sort("week")
    all_bands = [*OPEN_BANDS, *CLOSED_BANDS, UNATTRIBUTED]
    wide = wide.select("week", *[pl.col(b) if b in wide.columns else pl.lit(0).alias(b) for b in all_bands])

    last = wide["week"].max()
    weeks = cfg.get("growth_weeks", 26)
    start = last - timedelta(weeks=weeks)
    g = growth_share(wide, start, last, [b for b in all_bands if show_u or b != UNATTRIBUTED])
    months = round(weeks / 4.35)
    lw = wide.filter(pl.col("week") == last).row(0, named=True)
    u_share = lw[UNATTRIBUTED] / sum(lw[b] for b in all_bands)
    stealth_t = stealth["tokens"].sum() / 1e12
    hidden_t = stealth_t + (0 if show_u else wide[UNATTRIBUTED].sum() / 1e12)
    shown_t = sum(wide[b].sum() for b in bands_order) / 1e12

    words = in_words(g)
    title = (
        f"Mid-size open-weight models accounted for {words} new tokens in the past {months} months"
        if words
        else f"Mid-size open-weight models accounted for {g:.0%} of token growth in the past {months} months"
    )
    notes = (
        []
        if show_u
        else [
            f"Not shown: stealth and unattributed models ({hidden_t:.0f}T tokens, "
            f"{hidden_t / (hidden_t + shown_t):.0%} of the total)."
        ]
    )
    return Story(
        title=title,
        subtitle=(
            f"Tokens per week by model type. Mid-size open models accounted for {g:.0%} of the growth in tokens "
            f"from {start:%b %-d} to {last + timedelta(days=6):%b %-d, %Y}. Mid-size open = open-weight models "
            "with 100B–1T total parameters (e.g. DeepSeek V4 Flash, GLM-5.3 Flash, MiniMax M3)."
        ),
        frames={"bands": bands, "wide": wide, "display": smooth_121(wide)},
        sources=["openrouter_rankings"],
        as_of=as_of,
        method=(
            # non-breaking spaces keep each date range on one line when the footer wraps
            f"growth = change in average weekly tokens, 4\u00a0weeks\u00a0from\u00a0{start:%b\u00a0%-d} vs "
            f"4\u00a0weeks\u00a0to\u00a0{last + timedelta(days=6):%b\u00a0%-d}; "
            "chart smoothed (1-2-1 over 3\u00a0weeks); model sizes from model cards"
        ),
        notes=notes,
        caveats=[
            "OpenRouter traffic only: a developer-heavy marketplace with free tiers, so open and cheap models are "
            "over-represented compared with first-party APIs.",
            "Open weights includes models whose lab has announced the weights will be published.",
            "Tokens are counted by each model's own tokenizer, so volumes are not strictly comparable across models.",
            f"Excluded: models served under stealth names, revealed or not ({stealth_t:.0f}T tokens, free pre-release "
            f"testing), and OpenRouter's 'other' row ({u_share:.0%} of the week of {last:%b %-d}).",
        ],
        extra={
            "last_week": str(last),
            "growth_start": str(start),
            "growth_share": g,
            "stealth_tokens_t": stealth_t,
            "bands_order": bands_order,
        },
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["wide"]

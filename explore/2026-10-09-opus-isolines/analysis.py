"""Opus isolines: what each Claude Opus's capability has cost since launch, by the later models that matched it.

Reads the epoch_eci, dim_model_alias and lp_price_intervals marts. See README.md for method.
`cachereg render explore/2026-10-09-opus-isolines` renders the visuals declared in explore.yaml.

model_prices() and fmt_usd() are copied from explore/2026-10-06-cost-of-intelligence (explorations are
self-contained); the price definition is the same.
"""

from __future__ import annotations

import math
from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

WINDOW_START = date(2025, 1, 1)  # LiteLLM price history is staged from this day
BLEND = (0.8, 0.2)  # house blend: 80% input + 20% output
SMOOTH_DAYS = 28  # a model's price on day D = median of its listed daily prices over the trailing 28 days
DAYS_PER_MONTH = 30.44


def model_prices(con, as_of: date) -> pl.DataFrame:
    """One row per (model_group, listed day): the model's blended list price, trailing 28-day median.

    Cheapest of the model's mapped LiteLLM keys (OpenRouter's listing and the vendor's own API) each day.
    Only days with a valid listing; zero prices (free tiers) are ignored.
    """
    wi, wo = BLEND
    # Only module constants are interpolated (blend weights).
    df = query(
        con,
        f"""
        WITH lim AS (
            SELECT least(max(date), ?::DATE) AS last_day FROM stg_litellm_prices_days
        ), days AS (
            SELECT CAST(d AS DATE) AS day
            FROM lim, generate_series(?::DATE, lim.last_day, INTERVAL 1 DAY) g(d)
        ), m AS (
            SELECT model_group, display_name, eci, eci_ci_low, eci_ci_high, release_date, organization, model_id
            FROM epoch_eci WHERE model_id IS NOT NULL AND release_date IS NOT NULL
        ), iv AS (
            SELECT m.model_group, p.valid_from, p.valid_to,
                   {wi} * p.input_usd_per_token + {wo} * p.output_usd_per_token AS usd_per_token
            FROM m
            JOIN dim_model_alias a ON a.source = 'litellm' AND a.model_id = m.model_id
            JOIN lp_price_intervals p ON p.key = a.alias
            WHERE {wi} * p.input_usd_per_token + {wo} * p.output_usd_per_token > 0
        ), listed AS (
            SELECT iv.model_group, d.day, min(iv.usd_per_token) AS usd_per_token
            FROM iv JOIN days d ON d.day >= iv.valid_from AND (iv.valid_to IS NULL OR d.day < iv.valid_to)
            GROUP BY ALL
        )
        SELECT m.model_group, m.display_name, m.eci, m.eci_ci_low, m.eci_ci_high, m.release_date,
               m.organization, x.day, x.usd_per_token * 1e6 AS usd_per_mtok
        FROM listed x JOIN m USING (model_group)
        WHERE x.day >= m.release_date
        """,  # noqa: S608
        [as_of, WINDOW_START],
    )
    return df.sort("model_group", "day").with_columns(
        pl.col("usd_per_mtok").rolling_median_by("day", window_size=f"{SMOOTH_DAYS}d").over("model_group")
    )


def isoline(prices: pl.DataFrame, anchor: str, eci: str = "point", later_only: bool = True) -> pl.DataFrame:
    """Daily record-low price for the anchor's capability, from the anchor's first listed day.

    Candidates: models scoring at least the anchor's ECI (`eci`: 'point', or 'ci_low' = the candidate's lower
    CI bound must clear it), released on or after the anchor (later_only) and listed that day. The anchor itself
    always counts. `price` is the lowest price seen so far; `setter` is the model that set it.
    """
    a = prices.filter(pl.col("display_name") == anchor).sort("day")
    if a.is_empty():
        raise ValueError(f"anchor {anchor!r} has no listed price")
    a_eci, a_rel, start = a["eci"][0], a["release_date"][0], a["day"][0]
    score = pl.col("eci") if eci == "point" else pl.coalesce("eci_ci_low", "eci")
    keep = (score >= a_eci) | (pl.col("display_name") == anchor)
    if later_only:
        keep &= pl.col("release_date") >= a_rel
    daily = (
        prices.filter(keep & (pl.col("day") >= start))
        .sort("day", "usd_per_mtok", "release_date", "model_group")
        .group_by("day", maintain_order=True)
        .first()
        .sort("day")
    )
    # Record low: carry the setter forward until a strictly lower price appears (ties don't move the line).
    rows, best, setter = [], math.inf, None
    for r in daily.iter_rows(named=True):
        if r["usd_per_mtok"] < best:
            best, setter = r["usd_per_mtok"], r
        rows.append(
            {
                "anchor": anchor,
                "anchor_eci": a_eci,
                "day": r["day"],
                "usd_per_mtok": best,
                "cheapest_today": r["usd_per_mtok"],
                "model_group": setter["model_group"],
                "display_name": setter["display_name"],
                "setter_eci": setter["eci"],
                "setter_release": setter["release_date"],
            }
        )
    return pl.DataFrame(rows)


def events(line: pl.DataFrame) -> pl.DataFrame:
    """The labelled points: the anchor's start, then each day a different model sets a new low.

    A price cut by the model already holding the low moves the line but is not an event.
    """
    prev = pl.col("model_group").shift(1)
    start = line["day"].min()
    return (
        line.filter((pl.col("day") == start) | (pl.col("model_group") != prev))
        .with_columns(
            kind=pl.when(pl.col("day") == start).then(pl.lit("anchor")).otherwise(pl.lit("new model")),
            months=(pl.col("day") - start).dt.total_days() / DAYS_PER_MONTH,
            fold=pl.col("usd_per_mtok").first() / pl.col("usd_per_mtok"),
        )
        .select("anchor", "anchor_eci", "kind", "day", "months", "display_name", "setter_eci", "usd_per_mtok", "fold")
    )


def summary(line: pl.DataFrame) -> dict:
    s = line.sort("day")
    launch, now = s["usd_per_mtok"][0], s["usd_per_mtok"][-1]
    hit = s.filter(pl.col("usd_per_mtok") <= launch / 10)
    return {
        "anchor": s["anchor"][0],
        "anchor_eci": s["anchor_eci"][0],
        "start": s["day"][0],
        "launch": launch,
        "now": now,
        "now_model": s["display_name"][-1],
        "fold": launch / now,
        "months_to_10x": (hit["day"][0] - s["day"][0]).days / DAYS_PER_MONTH if hit.height else None,
        "months": (s["day"][-1] - s["day"][0]).days / DAYS_PER_MONTH,
        "new_models": s["model_group"].n_unique() - 1,
        # Days where something cheaper was on offer than the record (a listing that ended): the line and the
        # day's cheapest price only differ on these days.
        "days_above_record": s.filter(pl.col("cheapest_today") > pl.col("usd_per_mtok")).height,
    }


def sensitivity(prices: pl.DataFrame, anchors: list[str]) -> pl.DataFrame:
    variants = {
        "Main: later models, point ECI": {},
        "Later models, candidate's ECI lower CI bound": {"eci": "ci_low"},
        "Any model (incl. released before the anchor)": {"later_only": False},
    }
    rows = []
    for name, kw in variants.items():
        for a in anchors:
            s = summary(isoline(prices, a, **kw))
            keep = ("anchor", "launch", "now", "now_model", "fold", "months_to_10x")
            rows.append({"variant": name, **{k: s[k] for k in keep}})
    return pl.DataFrame(rows)


def fmt_usd(v: float) -> str:
    if v >= 10:
        return f"${v:.0f}"
    if v >= 1:
        return f"${v:.2f}".rstrip("0").rstrip(".")
    return f"${v:.3f}".rstrip("0") if v < 0.1 else f"${v:.2f}"


def build(con, as_of: date, cfg: dict) -> Story:
    anchors = list(cfg["anchors"])
    prices = model_prices(con, as_of)
    lines = pl.concat([isoline(prices, a) for a in anchors])
    ev = pl.concat([events(lines.filter(pl.col("anchor") == a)) for a in anchors])
    summ = pl.DataFrame([summary(lines.filter(pl.col("anchor") == a)) for a in anchors])
    sens = sensitivity(prices, anchors)

    reached = summ.filter(pl.col("months_to_10x").is_not_null())
    pending = summ.filter(pl.col("months_to_10x").is_null())
    worst = math.ceil(reached["months_to_10x"].max())
    short = [a.removeprefix("Claude ") for a in reached["anchor"]]
    names = ", ".join(short[:-1]) + f" and {short[-1]}" if len(short) > 1 else short[0]
    title = f"{names} were each matched at a tenth of their price within {worst} months"
    tail = "; ".join(
        f"{r['anchor'].removeprefix('Claude ')} ({r['start']:%b %Y}): {r['fold']:.1f}× cheaper so far"
        for r in pending.iter_rows(named=True)
    )
    subtitle = (
        "Lowest list price per million tokens for a model released on or after each Claude Opus that scores at "
        "least as high on the Epoch Capabilities Index. Dots mark each new model that set a new low."
        + (f" {tail}." if tail else "")
    )
    last_day = lines["day"].max()
    return Story(
        title=title,
        subtitle=subtitle,
        frames={"daily": lines, "events": ev, "summary": summ, "sensitivity": sens},
        sources=["epoch_benchmarks", "litellm_prices"],
        as_of=as_of,
        method=(
            "price = 80% input + 20% output, cheapest listing (OpenRouter or vendor), 28-day median "
            "per model, running minimum; capability = Epoch Capabilities Index (current fit) ≥ the Opus's"
        ),
        caveats=[
            "Price per token, not per task: reasoning models can use many more output tokens per answer.",
            "List prices only: no caching, batch or volume discounts. OpenRouter listings follow the cheapest "
            "provider and change almost daily.",
            "ECI is Epoch's current fit, placed at each model's release; Epoch re-fits it on every update. "
            "A model's ECI is for its best published setting, while its price applies at any setting.",
            "Only models released on or after each Opus count, so each line starts at that Opus's own price; "
            "for older Opus models a cheaper match was sometimes already on sale (see README).",
            "Models that are unmapped or listed late in LiteLLM make each line an upper bound.",
        ],
        extra={"anchors": anchors, "last_day": str(last_day)},
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["events"].select("anchor", "day", "display_name", "usd_per_mtok", "fold", "setter_eci")

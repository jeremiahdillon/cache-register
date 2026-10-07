"""Does quality win usage? Capability of the tokens bought on OpenRouter vs the frontier (exploration).

Reads the or_model_daily and epoch_eci marts. See README.md for method and
docs/plans/2026-10-06-quality-vs-usage.md for the design.
`cachereg render explore/2026-10-06-quality-vs-usage` renders the visuals declared in explore.yaml.
"""

from __future__ import annotations

from datetime import date, timedelta

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

WINDOW_START = date(2025, 1, 6)  # first complete Monday-to-Sunday week of 2025
QUANTILES = {"p25": 0.25, "p50": 0.5, "p75": 0.75}


def weekly_models(con, as_of: date, include_free: bool = False) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(per week × scored model: tokens, ECI, blended price; per week: all non-'other' tokens), complete weeks."""
    free = "" if include_free else "AND NOT d.is_free"
    m = query(
        con,
        f"""
        SELECT date_trunc('week', d.date)::DATE AS week, e.model_group, e.display_name, e.eci,
               sum(d.total_tokens) AS tokens,
               -- Rounded to $0.000001/Mtok: parallel sums leave ~1e-15 noise, which made prices at exactly
               -- 2x the cheapest flip in or out of `within_2x_cheapest` between rebuilds.
               round(sum(d.total_tokens * d.blended_usd_per_token) FILTER (WHERE NOT d.is_free)
                 / sum(d.total_tokens) FILTER (WHERE NOT d.is_free) * 1e6, 6) AS usd_per_mtok
        FROM or_model_daily d
        -- `:free` permaslugs carry no model_id in the mart: resolve them through their paid model's alias.
        LEFT JOIN dim_model_alias fa
          ON fa.source = 'openrouter' AND fa.alias = regexp_replace(d.model_permaslug, ':free$', '')
        JOIN epoch_eci e ON e.model_id = coalesce(d.model_id, fa.model_id)
        WHERE NOT d.is_other {free} AND d.date <= ?
        GROUP BY ALL
        """,  # noqa: S608 - only a fixed filter is interpolated
        [as_of],
    )
    t = query(
        con,
        """
        SELECT date_trunc('week', date)::DATE AS week, count(DISTINCT date) AS days,
               sum(total_tokens) FILTER (WHERE NOT is_other) AS all_tokens
        FROM or_model_daily WHERE date <= ? GROUP BY ALL
        """,
        [as_of],
    )
    weeks = t.filter((pl.col("days") == 7) & (pl.col("week") >= WINDOW_START)).select("week", "all_tokens")
    return m.join(weeks.select("week"), on="week"), weeks


def frontier_dates(con, as_of: date) -> pl.DataFrame:
    """Epoch models with an ECI and release date (mapped or not), by release date."""
    return query(
        con,
        "SELECT model_group, eci, release_date FROM epoch_eci WHERE release_date IS NOT NULL AND release_date <= ?",
        [as_of],
    ).sort("release_date")


def wquantile(g: pl.DataFrame, col: str, q: float) -> float:
    g = g.sort(col)
    c = g["tokens"].cum_sum() / g["tokens"].sum()
    return g.filter(c >= q)[col][0]


def weekly(models: pl.DataFrame, weeks: pl.DataFrame, epoch: pl.DataFrame, near: float) -> pl.DataFrame:
    rows = []
    for (wk,), g in models.group_by("week"):
        end = wk + timedelta(days=6)
        released = epoch.filter(pl.col("release_date") <= end)
        best_or = g["eci"].max()
        g = g.with_columns(
            cheapest=pl.struct("eci", "usd_per_mtok").map_elements(
                lambda r, g=g: g.filter((pl.col("eci") >= r["eci"]) & pl.col("usd_per_mtok").is_not_null())[
                    "usd_per_mtok"
                ].min(),
                return_dtype=pl.Float64,
            )
        )
        priced = g.filter(pl.col("usd_per_mtok").is_not_null())
        qs = {k: wquantile(g, "eci", q) for k, q in QUANTILES.items()}
        reached = released.filter(pl.col("eci") >= qs["p50"])["release_date"].min()
        rows.append(
            {
                "week": wk,
                "frontier": released["eci"].max(),
                "best_on_openrouter": best_or,
                **qs,
                "lag_months": (end - reached).days / 30.44,
                "near_frontier_share": g.filter(pl.col("eci") >= best_or - near)["tokens"].sum() / g["tokens"].sum(),
                "within_2x_cheapest": priced.filter(pl.col("usd_per_mtok") <= 2 * pl.col("cheapest"))["tokens"].sum()
                / priced["tokens"].sum(),
                "scored_tokens": g["tokens"].sum(),
            }
        )
    out = pl.DataFrame(rows).join(weeks, on="week").sort("week")
    return out.with_columns(coverage=pl.col("scored_tokens") / pl.col("all_tokens"))


def summary(w: pl.DataFrame, weeks: int = 13) -> dict:
    tail = w.tail(weeks)
    return {
        "lag_months": tail["lag_months"].median(),
        "gap": (tail["frontier"] - tail["p50"]).median(),
        "near_frontier_share": tail["near_frontier_share"].median(),
        "within_2x_cheapest": tail["within_2x_cheapest"].median(),
        "coverage": tail["coverage"].median(),
        "from": tail["week"].min(),
        "to": tail["week"].max() + timedelta(days=6),
    }


def build(con, as_of: date, cfg: dict) -> Story:
    near = float(cfg.get("near_points", 3))
    n = int(cfg.get("summary_weeks", 13))
    epoch = frontier_dates(con, as_of)
    models, weeks = weekly_models(con, as_of)
    w = weekly(models, weeks, epoch, near)
    s = summary(w, n)

    sens = []
    variants = [
        ("main", False, near),
        ("free tokens included", True, near),
        (f"near = within {near + 2:.0f} points", False, near + 2),
    ]
    for name, include_free, nr in variants:
        mm, ww = weekly_models(con, as_of, include_free) if include_free else (models, weeks)
        sens.append({"variant": name, **summary(weekly(mm, ww, epoch, nr), n)})

    last = w.row(-1, named=True)
    top = models.filter(pl.col("week") == last["week"]).sort("tokens", descending=True).head(3)["display_name"]
    lag = round(s["lag_months"])
    return Story(
        title=f"The typical paid token on OpenRouter buys capability the frontier reached {lag} months earlier",
        subtitle=(
            f"Epoch Capabilities Index (ECI) of the model behind each paid token, weekly: median and middle half, "
            f"against the best model released so far. Over the {n} weeks to {s['to']:%b %-d, %Y}, "
            f"{s['near_frontier_share']:.0%} of tokens went to models within {near:.0f} points of the best on "
            f"OpenRouter. Largest last week: {', '.join(top)}."
        ),
        frames={"weekly": w, "sensitivity": pl.DataFrame(sens), "models": models},
        sources=["openrouter_rankings", "epoch_benchmarks", "litellm_prices"],
        as_of=as_of,
        method=(
            "paid tokens of ECI-scored models (free variants and OpenRouter's 'other' row excluded), "
            "complete weeks; frontier = highest ECI released by the week's end; lag = months since the "
            "frontier first reached the median token's ECI"
        ),
        notes=[f"Covers {s['coverage']:.0%} of non-'other' tokens; the rest are free or unscored models."],
        caveats=[
            "OpenRouter traffic only: developer-heavy, with free tiers and many cheap open models. First-party "
            "APIs, where frontier models sell most, are not in this data.",
            "Unscored models (mostly cheap open-weight models) are out of scope; including them would likely "
            "widen the gap.",
            "ECI is Epoch's current fit (one vintage) at each model's best published setting.",
            "Tokens are counted by each model's own tokenizer.",
        ],
        extra={"summary": {k: (str(v) if isinstance(v, date) else v) for k, v in s.items()}, "near": near},
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["weekly"].select(
        "week", "frontier", "best_on_openrouter", "p25", "p50", "p75", "lag_months", "near_frontier_share", "coverage"
    )


TABLE_PERCENT_COLUMNS = ["near_frontier_share", "coverage"]

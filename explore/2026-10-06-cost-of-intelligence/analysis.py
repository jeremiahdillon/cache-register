"""Cost of intelligence: the cheapest list price per token at each capability level, day by day (exploration).

Reads the epoch_eci, dim_model_alias, lp_price_intervals and lp_price_days marts. See README.md for method and
docs/plans/2026-10-06-cost-of-intelligence.md for the design.
`cachereg render explore/2026-10-06-cost-of-intelligence` renders the visuals declared in explore.yaml.
"""

from __future__ import annotations

import math
from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

WINDOW_START = date(2025, 1, 1)  # LiteLLM price history is staged from this day
BLENDS = {"house": (0.8, 0.2), "3to1": (0.75, 0.25), "output": (0.0, 1.0)}
SMOOTH_DAYS = 28  # a model's price on day D = median of its listed daily prices over the trailing 28 days


def model_prices(con, as_of: date, blend: str = "house", keys: str = "min", smooth: bool = True) -> pl.DataFrame:
    """One row per (model_group, day): the model's blended list price that day.

    `basis` = 'listed' (a mapped key is valid that day) or 'backfilled' (released, not yet listed:
    the first later price). keys='min': cheapest of the model's mapped keys; 'rank1': preferred key only.
    smooth: replace each listed day's price with the model's trailing SMOOTH_DAYS-day median
    (OpenRouter listings follow the cheapest provider and swing several-fold within days).
    """
    wi, wo = BLENDS[blend]
    rank_filter = "AND a.rank = 1" if keys == "rank1" else ""
    # Only module constants are interpolated (blend weights, a fixed rank filter).
    df = query(
        con,
        f"""
        WITH lim AS (
            SELECT least(max(date), ?::DATE) AS last_day FROM lp_price_days
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
            JOIN dim_model_alias a ON a.source = 'litellm' AND a.model_id = m.model_id {rank_filter}
            JOIN lp_price_intervals p ON p.key = a.alias
            WHERE {wi} * p.input_usd_per_token + {wo} * p.output_usd_per_token > 0
        ), listed AS (
            SELECT iv.model_group, d.day, min(iv.usd_per_token) AS usd_per_token
            FROM iv JOIN days d ON d.day >= iv.valid_from AND (iv.valid_to IS NULL OR d.day < iv.valid_to)
            GROUP BY ALL
        ), first_listed AS (
            SELECT model_group, min(day) AS first_day, arg_min(usd_per_token, day) AS first_price
            FROM listed GROUP BY ALL
        ), backfill AS (
            SELECT f.model_group, d.day, f.first_price AS usd_per_token
            FROM first_listed f JOIN m USING (model_group)
            JOIN days d ON d.day >= m.release_date AND d.day < f.first_day
        )
        SELECT m.model_group, m.display_name, m.eci, m.eci_ci_low, m.eci_ci_high, m.release_date,
               m.organization, x.day, x.usd_per_token * 1e6 AS usd_per_mtok, x.basis
        FROM (
            SELECT *, 'listed' AS basis FROM listed
            UNION ALL
            SELECT *, 'backfilled' AS basis FROM backfill
        ) x JOIN m USING (model_group)
        WHERE x.day >= m.release_date
        """,  # noqa: S608
        [as_of, WINDOW_START],
    )
    if not smooth:
        return df
    listed = (
        df.filter(pl.col("basis") == "listed")
        .sort("model_group", "day")
        .with_columns(
            pl.col("usd_per_mtok").rolling_median_by("day", window_size=f"{SMOOTH_DAYS}d").over("model_group")
        )
    )
    return pl.concat([listed, df.filter(pl.col("basis") != "listed")])


def cheapest(prices: pl.DataFrame, levels: list[float], eci: str = "point", backfill: bool = False) -> pl.DataFrame:
    """Per (level, day): the cheapest price among models scoring at least the level, and which model."""
    col = {
        "point": pl.col("eci"),
        "ci_low": pl.coalesce("eci_ci_low", "eci"),
        "ci_high": pl.coalesce("eci_ci_high", "eci"),
    }[eci]
    p = prices if backfill else prices.filter(pl.col("basis") == "listed")
    out = []
    for lv in levels:
        q = p.filter(col >= lv).sort("day", "usd_per_mtok", "model_group")
        out.append(q.group_by("day", maintain_order=True).first().with_columns(level=pl.lit(lv)))
    return pl.concat(out).select("level", "day", "usd_per_mtok", "model_group", "display_name", "eci", "basis")


def trend(series: pl.DataFrame) -> dict:
    """First/last values, fold change and the log-linear rate of decline per year (fit on daily points)."""
    s = series.sort("day")
    first, last = s.row(0, named=True), s.row(-1, named=True)
    t = [(d - first["day"]).days / 365.25 for d in s["day"]]
    y = [math.log(v) for v in s["usd_per_mtok"]]
    n = len(t)
    if n < 2 or t[-1] == 0:
        return {"first_day": first["day"], "first": first["usd_per_mtok"], "last": last["usd_per_mtok"]}
    mt, my = sum(t) / n, sum(y) / n
    slope = sum((a - mt) * (b - my) for a, b in zip(t, y, strict=True)) / sum((a - mt) ** 2 for a in t)
    now = last["usd_per_mtok"]
    return {
        "first_day": first["day"],
        "first": first["usd_per_mtok"],
        "first_model": first["display_name"],
        "now": now,
        "now_model": last["display_name"],
        "fold": first["usd_per_mtok"] / now,
        "per_year_fold": math.exp(-slope),  # prices divide by this each year (fit)
        "years": t[-1],
    }


def sensitivity(con, as_of: date, levels: list[float]) -> pl.DataFrame:
    """Headline numbers under each alternative definition (one change at a time from the main one)."""
    variants = {
        "main": {},
        "eci ci_low (conservative)": {"eci": "ci_low"},
        "eci ci_high (generous)": {"eci": "ci_high"},
        "back-filled before listing": {"backfill": True},
        "blend 3:1": {"blend": "3to1"},
        "output price only": {"blend": "output"},
        "preferred key only": {"keys": "rank1"},
        "daily price, not smoothed": {"smooth": False},
    }
    cache: dict[tuple, pl.DataFrame] = {}
    rows = []
    for name, v in variants.items():
        k = (v.get("blend", "house"), v.get("keys", "min"), v.get("smooth", True))
        if k not in cache:
            cache[k] = model_prices(con, as_of, *k)
        c = cheapest(cache[k], levels, v.get("eci", "point"), v.get("backfill", False))
        for lv in levels:
            s = c.filter(pl.col("level") == lv)
            if s.height:
                tr = trend(s)
                keep = ("first_day", "first", "now", "fold", "per_year_fold")
                rows.append({"variant": name, "level": lv, **{x: tr.get(x) for x in keep}})
    return pl.DataFrame(rows)


def coverage(con, as_of: date, levels: list[float], prices: pl.DataFrame) -> pl.DataFrame:
    eci = query(con, "SELECT model_group, eci, model_id FROM epoch_eci WHERE release_date IS NOT NULL")
    priced = set(prices["model_group"].unique())
    rows = []
    for lv in levels:
        e = eci.filter(pl.col("eci") >= lv)
        rows.append(
            {
                "level": lv,
                "models": e.height,
                "mapped": e["model_id"].is_not_null().sum(),
                "priced": e["model_group"].is_in(list(priced)).sum(),
                "unmapped": ", ".join(sorted(e.filter(pl.col("model_id").is_null())["model_group"])),
            }
        )
    return pl.DataFrame(rows)


def steps(c: pl.DataFrame) -> pl.DataFrame:
    """Days where the model setting the cheapest price changes (for labels and the table)."""
    prev = pl.col("model_group").shift(1).over("level")
    return c.sort("level", "day").filter((pl.col("model_group") != prev) | prev.is_null())


def fmt_usd(v: float) -> str:
    if v >= 10:
        return f"${v:.0f}"
    if v >= 1:
        return f"${v:.2f}".rstrip("0").rstrip(".")
    return f"${v:.3f}".rstrip("0") if v < 0.1 else f"${v:.2f}"


def build(con, as_of: date, cfg: dict) -> Story:
    levels = [float(x["eci"]) for x in cfg["levels"]]
    names = {float(x["eci"]): x["name"] for x in cfg["levels"]}
    prices = model_prices(con, as_of)
    c = cheapest(prices, levels).with_columns(name=pl.col("level").replace_strict(names, return_dtype=pl.String))
    tr = {lv: trend(c.filter(pl.col("level") == lv)) for lv in levels}
    sens = sensitivity(con, as_of, levels)
    cov = coverage(con, as_of, levels, prices)

    hero = float(cfg.get("headline_level", levels[-1]))
    h = tr[hero]
    last_day = c["day"].max()
    rate = h["per_year_fold"]
    title = f"The price of {names[hero]} capability is falling about {rate:.0f}× a year"
    subtitle = (
        f"Cheapest list price per million tokens for any model at or above each level of the Epoch Capabilities "
        f"Index. {names[hero]}: {fmt_usd(h['first'])} ({h['first_model']}, {h['first_day']:%b %Y}) to "
        f"{fmt_usd(h['now'])} ({h['now_model']}) by {last_day:%b %-d, %Y}."
    )
    return Story(
        title=title,
        subtitle=subtitle,
        frames={"daily": c, "steps": steps(c), "sensitivity": sens, "coverage": cov},
        sources=["epoch_benchmarks", "litellm_prices"],
        as_of=as_of,
        method=(
            "price = 80%\u00a0input + 20%\u00a0output, cheapest listing (OpenRouter or vendor), "
            "28-day median per model; "
            "rate = log-linear fit; capability = Epoch Capabilities Index (current fit) at each model's release"
        ),
        caveats=[
            "Price per token, not per task: reasoning models can use many more output tokens per answer.",
            "List prices only: no caching, batch or volume discounts. OpenRouter listings follow the cheapest "
            "provider and change almost daily.",
            "ECI is Epoch's current fit, placed at each model's release; Epoch re-fits it on every update. "
            "A model's ECI is for its best published setting, while its price applies at any setting.",
            "Models that are unmapped or listed late in LiteLLM make the series an upper bound: the true cheapest "
            "price can only be lower or earlier.",
        ],
        extra={
            "levels": levels,
            "names": names,
            "headline_level": hero,
            "trend": {
                str(k): {kk: (str(vv) if isinstance(vv, date) else vv) for kk, vv in v.items()} for k, v in tr.items()
            },
            "last_day": str(last_day),
        },
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["steps"].select("name", "day", "usd_per_mtok", "display_name", "eci")

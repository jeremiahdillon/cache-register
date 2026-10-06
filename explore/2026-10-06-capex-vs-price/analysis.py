"""Capex vs price collapse: hyperscaler capex per quarter next to the cheapest price of fixed capability (exploration).

Reads the capex_quarterly / capex_group_quarterly (030), eci_model_price_daily (040) and
dim_vendor_alias marts. See README.md for method and caveats.
`cachereg render explore/2026-10-06-capex-vs-price` renders the visuals declared in explore.yaml.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story


def cheapest(con, levels: list[float], start: date, eci: str = "eci") -> pl.DataFrame:
    """Per (level, day): the cheapest listed price among models scoring at least the level (as analysis (a))."""
    col = {"eci": "p.eci", "ci_low": "coalesce(p.eci_ci_low, p.eci)"}[eci]  # fixed expressions only
    lv = ", ".join(f"({float(x)})" for x in levels)
    return query(
        con,
        f"""
        WITH lv(level) AS (VALUES {lv})
        SELECT CAST(lv.level AS DOUBLE) AS level, p.day, p.usd_per_mtok, p.model_group, p.display_name,
               p.organization, v.vendor_id
        FROM eci_model_price_daily p
        JOIN lv ON {col} >= lv.level
        LEFT JOIN dim_vendor_alias v ON v.source = 'openrouter' AND v.alias = split_part(p.model_id, '/', 1)
        WHERE p.basis = 'listed' AND p.day >= ?
        QUALIFY row_number() OVER (PARTITION BY lv.level, p.day ORDER BY p.usd_per_mtok, p.model_group) = 1
        ORDER BY level, day
        """,  # noqa: S608 (levels are floats from explore.yaml, the column a fixed expression)
        [start],
    )


def capex(con, groups: list[str], start: date) -> tuple[pl.DataFrame, pl.DataFrame]:
    """(per company, per calendar quarter) and the group total per quarter with its completeness."""
    per = query(
        con,
        """SELECT cal_quarter, ticker, company, vendor_id, capex_usd, finance_lease_additions_usd
           FROM capex_quarterly WHERE list_contains(?, company_group) AND cal_quarter >= ?
           ORDER BY cal_quarter, ticker""",
        [groups, start],
    )
    tot = query(
        con,
        """SELECT cal_quarter, sum(capex_usd) AS capex_usd,
                  sum(capex_incl_finance_leases_usd) AS capex_incl_finance_leases_usd,
                  sum(finance_lease_companies) AS finance_lease_companies,
                  sum(companies_reported) AS companies_reported, sum(companies_expected) AS companies_expected,
                  bool_and(complete) AS complete
           FROM capex_group_quarterly WHERE list_contains(?, company_group) AND cal_quarter >= ?
           GROUP BY cal_quarter ORDER BY cal_quarter""",
        [groups, start],
    )
    return per, tot


def quarterly_prices(c: pl.DataFrame) -> pl.DataFrame:
    """Per (level, calendar quarter): median, mean and last-day cheapest price, and days covered."""
    return (
        c.with_columns(cal_quarter=pl.col("day").dt.truncate("1q"))
        .sort("day")
        .group_by("level", "cal_quarter", maintain_order=True)
        .agg(
            median=pl.col("usd_per_mtok").median(),
            mean=pl.col("usd_per_mtok").mean(),
            end=pl.col("usd_per_mtok").last(),
            days=pl.len(),
        )
    )


def window(tot: pl.DataFrame) -> tuple[date, date]:
    """First and last complete capex quarter: the comparison window."""
    done = tot.filter(pl.col("complete"))
    return done["cal_quarter"].min(), done["cal_quarter"].max()


def ratios(tot: pl.DataFrame, qp: pl.DataFrame, q0: date, q1: date, capex_col="capex_usd", price="median") -> dict:
    """Capex growth and price fall (×) per level between quarters q0 and q1; None where a level is missing."""

    def at(df, q, col):
        v = df.filter(pl.col("cal_quarter") == q)[col]
        return v[0] if v.len() else None

    out = {"capex_growth": at(tot, q1, capex_col) / at(tot, q0, capex_col)}
    for lv in qp["level"].unique().sort():
        s = qp.filter(pl.col("level") == lv)
        a, b = at(s, q0, price), at(s, q1, price)
        out[lv] = a / b if a and b else None
    return out


def sensitivity(con, cfg: dict, levels: list[float], start: date) -> pl.DataFrame:
    """The headline ratios under alternative definitions, one change at a time."""
    group = cfg["group"]
    base_c = cheapest(con, levels, start)
    _, base_t = capex(con, [group], start)
    q0, q1 = window(base_t)
    variants = {
        "main (quarterly median price, cash capex)": {},
        "quarterly mean price": {"price": "mean"},
        "last-day price of each quarter": {"price": "end"},
        "capex incl. tagged finance-lease additions": {"capex_col": "capex_incl_finance_leases_usd"},
        "plus neocloud (CoreWeave)": {"groups": [group, "neocloud"]},
        "ECI lower CI bound ≥ level": {"eci": "ci_low"},
        "from the next quarter": {"q0": next_quarter(q0)},
    }
    rows = []
    for name, v in variants.items():
        c = cheapest(con, levels, start, v["eci"]) if "eci" in v else base_c
        t = capex(con, v["groups"], start)[1] if "groups" in v else base_t
        r = ratios(
            t,
            quarterly_prices(c),
            v.get("q0", q0),
            q1,
            v.get("capex_col", "capex_usd"),
            v.get("price", "median"),
        )
        rows.append({"variant": name, "from": v.get("q0", q0), "to": q1, **{str(k): x for k, x in r.items()}})
    return pl.DataFrame(rows)


def setters(c: pl.DataFrame, group_vendors: set[str], q0: date) -> pl.DataFrame:
    """Who set the cheapest price, by level: days per organization from the window start, and whether the
    organization is one of the capex group's companies (by vendor id)."""
    d = c.filter(pl.col("day") >= q0).with_columns(
        in_group=pl.col("vendor_id").is_in(list(group_vendors)).fill_null(False)
    )
    out = (
        d.group_by("level", "organization", "in_group")
        .agg(days=pl.len(), models=pl.col("display_name").unique().sort().str.join("; "))
        .with_columns(share=pl.col("days") / pl.col("days").sum().over("level"))
        .sort("level", "days", descending=[False, True])
    )
    return out


def fmt_usd(v: float) -> str:
    if v >= 10:
        return f"${v:.0f}"
    if v >= 1:
        return f"${v:.2f}".rstrip("0").rstrip(".")
    return f"${v:.3f}".rstrip("0") if v < 0.1 else f"${v:.2f}"


def next_quarter(q: date) -> date:
    return date(q.year + (q.month == 10), q.month + 3 if q.month < 10 else 1, 1)


def qlabel(q: date) -> str:
    return f"{q.year} Q{(q.month - 1) // 3 + 1}"


def build(con, as_of: date, cfg: dict) -> Story:
    levels = [float(x["eci"]) for x in cfg["levels"]]
    names = {float(x["eci"]): x["name"] for x in cfg["levels"]}
    start = cfg["start"] if isinstance(cfg["start"], date) else date.fromisoformat(cfg["start"])
    hero = float(cfg["headline_level"])
    group = cfg["group"]

    c = cheapest(con, levels, start).with_columns(name=pl.col("level").replace_strict(names, return_dtype=pl.String))
    per, tot = capex(con, [group], start)
    q0, q1 = window(tot)
    qp = quarterly_prices(c)
    r = ratios(tot, qp, q0, q1)
    group_vendors = set(per["vendor_id"].drop_nulls())
    who = setters(c, group_vendors, q0)
    in_group = who.filter(pl.col("in_group")).group_by("level").agg(pl.col("share").sum())
    in_group_share = {lv: s for lv, s in in_group.iter_rows()}

    quarters = tot.with_columns(quarter=pl.col("cal_quarter").map_elements(qlabel, return_dtype=pl.String))
    for lv in levels:
        m = qp.filter(pl.col("level") == lv).select("cal_quarter", pl.col("median").alias(f"median_price_{int(lv)}"))
        quarters = quarters.join(m, on="cal_quarter", how="left")

    cap0 = tot.filter(pl.col("cal_quarter") == q0)["capex_usd"][0]
    cap1 = tot.filter(pl.col("cal_quarter") == q1)["capex_usd"][0]
    p = qp.filter(pl.col("level") == hero)
    p0 = p.filter(pl.col("cal_quarter") == q0)["median"][0]
    p1 = p.filter(pl.col("cal_quarter") == q1)["median"][0]
    title = (
        f"Hyperscaler capex grew {r['capex_growth']:.1f}× from {qlabel(q0)} to {qlabel(q1)}; "
        f"{names[hero]} tokens got {r[hero]:.0f}× cheaper"
    )
    subtitle = (
        f"Quarterly cash capex of Microsoft, Alphabet, Amazon, Meta and Oracle: ${cap0 / 1e9:.0f}bn ({qlabel(q0)}) to "
        f"${cap1 / 1e9:.0f}bn ({qlabel(q1)}). Cheapest list price per million tokens at each Epoch Capabilities "
        f"Index level; {names[hero]} quarterly median {fmt_usd(p0)} to {fmt_usd(p1)}."
    )
    return Story(
        title=title,
        subtitle=subtitle,
        frames={
            "capex_by_company": per,
            "capex": tot,
            "daily": c,
            "quarters": quarters,
            "setters": who,
            "sensitivity": sensitivity(con, cfg, levels, start),
        },
        sources=["sec_edgar", "epoch_benchmarks", "litellm_prices"],
        as_of=as_of,
        method=(
            "capex = cash paid for property and equipment (10-K/10-Q), fiscal quarters mapped to calendar quarters; "
            "price = 80% input + 20% output, cheapest listing, 28-day median per model"
        ),
        caveats=[
            "Two series side by side, not a causal link: most of the cheapest models come from labs outside "
            "these five companies.",
            "Company-wide capex (data centres, but also warehouses, offices and devices), cash only: assets "
            "acquired under finance leases are excluded.",
            "Price per token, not per task; list prices only (no caching, batch or volume discounts).",
            "ECI is Epoch's current fit, placed at each model's release; unmapped or late-listed models make "
            "the price lines an upper bound.",
        ],
        notes=[f"Bars: complete quarters only; {qlabel(q1)} is the latest all five have reported."],
        extra={
            "levels": levels,
            "names": names,
            "headline_level": hero,
            "window": [str(q0), str(q1)],
            "ratios": {str(k): v for k, v in r.items()},
            "in_group_share": {str(k): v for k, v in in_group_share.items()},
        },
    )


def table(story: Story) -> pl.DataFrame:
    q = story.frames["quarters"].filter(pl.col("complete"))
    return q.select(
        "quarter",
        (pl.col("capex_usd") / 1e9).round(1).alias("capex_bn"),
        *[c for c in q.columns if c.startswith("median_price_")],
    )

"""Anthropic quarterly revenue from its S-1: level, change from the previous quarter, year-over-year multiple.

Reads marts 080 (disclosures), 031 (revenue_quarterly) and 130 (github_quarterly); never cachereg.sources.
See README.md for method and caveats.
`cachereg render explore/2026-10-26-anthropic-quarterly-revenue` renders the visuals declared in explore.yaml.

The figures are the S-1's quarterly results table (unaudited), recorded row by row in the curated
disclosures dataset as `revenue_quarterly` (millions of US dollars per quarter). Run-rate disclosures are a
different metric and are never mixed in here.

Seasonality (the second and third visuals): does Anthropic's slower growth in 2025 Q3 and Q4 match a
seasonal pattern in engineering work? Comparators, each reduced to a seasonal factor per calendar quarter
(the mean, over the base years, of a quarter's log growth minus its year's mean log growth):
* US git pushes to public GitHub repositories (Innovation Graph);
* the summed revenue of usage-priced developer-infrastructure companies (the `devinfra` group);
* US working days (weekdays minus the holidays below).
Anthropic's quarter-on-quarter growth is then shown as filed and with each factor removed.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story


def quarter_label(end: date) -> str:
    return f"{end.year} Q{(end.month - 1) // 3 + 1}"


def fmt_musd(v: float) -> str:
    return f"${v:,.0f}M"


def load_quarters(con, entity: str, metric: str) -> pl.DataFrame:
    """One row per quarter (the newest statement wins if a quarter is stated twice), oldest first."""
    df = query(
        con,
        """
        SELECT period_start, period_end, value, unit, statement_date, source_url, id
        FROM disclosures
        WHERE vendor_id = ? AND metric = ?
        QUALIFY row_number() OVER (PARTITION BY period_end ORDER BY statement_date DESC, id DESC) = 1
        ORDER BY period_end
        """,
        [entity, metric],
    )
    if df.is_empty():
        raise ValueError(f"no {metric} rows for {entity} in mart 080 at this as-of")
    if df["unit"].n_unique() != 1 or df["unit"][0] != "usd_millions_per_quarter":
        raise ValueError(f"unexpected unit(s) {df['unit'].unique().to_list()}")
    return df


def check_contiguous(df: pl.DataFrame) -> None:
    """Each quarter must start the day after the previous one ends: a gap would make a 'previous quarter'
    change span two quarters."""
    for prev_end, start in zip(df["period_end"][:-1], df["period_start"][1:], strict=True):
        if (start - prev_end).days != 1:
            raise ValueError(f"quarters are not contiguous: {prev_end} then {start}")
    for s, e in zip(df["period_start"], df["period_end"], strict=True):
        if not (s.day == 1 and s.month in (1, 4, 7, 10) and 89 <= (e - s).days <= 91):
            raise ValueError(f"{s}–{e} is not a calendar quarter")


def quarters(df: pl.DataFrame) -> pl.DataFrame:
    """Revenue, % change from the previous quarter and the multiple of the same quarter a year earlier."""
    return df.select(
        quarter=pl.col("period_end").map_elements(quarter_label, return_dtype=pl.String),
        period_start="period_start",
        period_end="period_end",
        revenue_musd=pl.col("value").cast(pl.Float64),
    ).with_columns(
        qoq_pct=(pl.col("revenue_musd") / pl.col("revenue_musd").shift(1) - 1) * 100,
        qoq_multiple=pl.col("revenue_musd") / pl.col("revenue_musd").shift(1),
        yoy_multiple=pl.col("revenue_musd") / pl.col("revenue_musd").shift(4),
    )


# ---- seasonality ------------------------------------------------------------------------------

SERIES = {  # key → label (the order of the legend and of the bars in each group)
    "github": "US git pushes, public GitHub",
    "peers": "Usage-priced cloud revenue",
    "workdays": "US working days",
}


def _nth_weekday(y: int, m: int, weekday: int, n: int) -> date:
    """The n-th `weekday` (0 = Monday) of a month; n = -1 is the last."""
    if n > 0:
        d = date(y, m, 1)
        return d + timedelta((weekday - d.weekday()) % 7 + 7 * (n - 1))
    d = date(y + (m == 12), m % 12 + 1, 1) - timedelta(1)
    return d - timedelta((d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    return d - timedelta(1) if d.weekday() == 5 else d + timedelta(1) if d.weekday() == 6 else d


def us_holidays(y: int) -> set[date]:
    """Days a typical US tech employer is closed: the federal holidays it usually observes (not Columbus or
    Veterans Day), plus the day after Thanksgiving and Christmas Eve."""
    thanksgiving = _nth_weekday(y, 11, 3, 4)
    days = {
        _observed(date(y, 1, 1)),
        _nth_weekday(y, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(y, 2, 0, 3),  # Presidents' Day
        _nth_weekday(y, 5, 0, -1),  # Memorial Day
        _observed(date(y, 6, 19)),
        _observed(date(y, 7, 4)),
        _nth_weekday(y, 9, 0, 1),  # Labor Day
        thanksgiving,
        thanksgiving + timedelta(1),
        date(y, 12, 24),
        _observed(date(y, 12, 25)),
    }
    return {d for d in days if d.weekday() < 5}


def working_days(start: date) -> int:
    end = date(start.year + 1, 1, 1) if start.month == 10 else date(start.year, start.month + 3, 1)
    hol = us_holidays(start.year) | us_holidays(start.year + 1)  # New Year's Day can be observed on Dec 31
    return sum(1 for i in range((end - start).days) if (d := start + timedelta(i)).weekday() < 5 and d not in hol)


def load_github(con, economy: str) -> pl.DataFrame:
    return query(
        con,
        "SELECT cal_quarter, git_pushes::DOUBLE AS value FROM github_quarterly WHERE economy = ? ORDER BY cal_quarter",
        [economy],
    )


def load_peers(con, group: str) -> pl.DataFrame:
    """Summed revenue of the group, only in quarters where every company in it reports."""
    df = query(
        con,
        """
        WITH n AS (SELECT count(DISTINCT cik) AS n FROM revenue_quarterly WHERE company_group = ?)
        SELECT cal_quarter, sum(revenue_usd) AS value, count(*) AS companies
        FROM revenue_quarterly WHERE company_group = ?
        GROUP BY cal_quarter HAVING count(*) = (SELECT n FROM n)
        ORDER BY cal_quarter
        """,
        [group, group],
    )
    if df.is_empty():
        raise ValueError(f"no quarter where every {group} company reports revenue")
    return df.drop("companies")


def log_growth(df: pl.DataFrame) -> pl.DataFrame:
    """Log growth from the previous quarter, only where the previous row is the previous calendar quarter."""
    return (
        df.sort("cal_quarter")
        .with_columns(
            g=(pl.col("value").log() - pl.col("value").log().shift(1)),
            prev=pl.col("cal_quarter").shift(1),
        )
        .filter(pl.col("prev") == pl.col("cal_quarter").dt.offset_by("-3mo"))
        .select("cal_quarter", "g")
    )


def seasonal_factors(g: pl.DataFrame, years: tuple[int, int]) -> pl.DataFrame:
    """Per calendar quarter (1–4): mean and spread of (quarter's log growth − its year's mean), over complete
    base years."""
    y0, y1 = years
    d = g.with_columns(year=pl.col("cal_quarter").dt.year(), k=pl.col("cal_quarter").dt.quarter()).filter(
        pl.col("year").is_between(y0, y1)
    )
    full = d.group_by("year").len().filter(pl.col("len") == 4)["year"]
    if full.len() != y1 - y0 + 1:
        raise ValueError(f"seasonal base {y0}–{y1}: years without four quarters of growth")
    d = d.with_columns(dev=pl.col("g") - pl.col("g").mean().over("year"))
    return (
        d.group_by("k")
        .agg(factor=pl.col("dev").mean(), spread=pl.col("dev").std(), lo=pl.col("dev").min(), hi=pl.col("dev").max())
        .sort("k")
    )


def seasonality(con, cfg: dict, as_of: date) -> pl.DataFrame:
    """Long frame: series, k (calendar quarter), factor_pct (as % growth), min_pct, max_pct over the base years."""
    years = tuple(cfg.get("base_years", (2021, 2024)))
    first = date(years[0] - 1, 10, 1)
    days = pl.DataFrame(
        {"cal_quarter": [date(y, m, 1) for y in range(years[0] - 1, years[1] + 1) for m in (1, 4, 7, 10)]}
    ).with_columns(value=pl.col("cal_quarter").map_elements(working_days, return_dtype=pl.Int64).cast(pl.Float64))
    inputs = {
        "github": load_github(con, cfg.get("github_economy", "US")),
        "peers": load_peers(con, cfg.get("peer_group", "devinfra")),
        "workdays": days.filter(pl.col("cal_quarter") >= first),
    }
    out = []
    for key, df in inputs.items():
        f = seasonal_factors(log_growth(df), years)
        out.append(
            f.select(
                series=pl.lit(key),
                label=pl.lit(SERIES[key]),
                k="k",
                factor_log="factor",
                factor_pct=(pl.col("factor").exp() - 1) * 100,
                min_pct=(pl.col("lo").exp() - 1) * 100,
                max_pct=(pl.col("hi").exp() - 1) * 100,
            )
        )
    return pl.concat(out)


def adjusted(q: pl.DataFrame, seasonal: pl.DataFrame) -> pl.DataFrame:
    """Anthropic's growth from the previous quarter, as filed and with each seasonal factor removed."""
    factor = {(r["series"], r["k"]): r["factor_log"] for r in seasonal.iter_rows(named=True)}
    rows = []
    prev = None
    for r in q.iter_rows(named=True):
        if prev is not None:
            g = math.log(r["revenue_musd"] / prev["revenue_musd"])
            k = (r["period_start"].month - 1) // 3 + 1
            wd = math.log(working_days(r["period_start"]) / working_days(prev["period_start"]))
            variants = {
                "filed": g,
                "workdays": g - wd,  # per working day: this quarter's actual days, not the base-year factor
                "github": g - factor[("github", k)],
                "peers": g - factor[("peers", k)],
            }
            for v, x in variants.items():
                rows.append({"quarter": r["quarter"], "variant": v, "growth_pct": (math.exp(x) - 1) * 100})
        prev = r
    return pl.DataFrame(rows)


VARIANTS = {  # adjusted-growth variant → label, in legend order
    "filed": "As filed",
    "workdays": "Per US working day",
    "github": "GitHub pushes' pattern removed",
    "peers": "Cloud usage revenue's pattern removed",
}


def build(con, as_of: date, cfg: dict) -> Story:
    raw = load_quarters(con, cfg.get("entity", "anthropic"), cfg.get("metric", "revenue_quarterly"))
    check_contiguous(raw)
    q = quarters(raw)
    if q.height < 5:
        raise ValueError("need five quarters for a year-over-year multiple")
    last, year_ago, first = q.row(-1, named=True), q.row(-5, named=True), q.row(0, named=True)
    yoy = last["yoy_multiple"]
    span = last["revenue_musd"] / first["revenue_musd"]
    filed = raw["statement_date"].max()

    seasonal = seasonality(con, cfg, as_of)
    adj = adjusted(q, seasonal)
    years = tuple(cfg.get("base_years", (2021, 2024)))
    sf = {(r["series"], r["k"]): r["factor_pct"] for r in seasonal.iter_rows(named=True)}

    title = f"Anthropic's quarterly revenue grew {yoy:.1f}× in a year"
    subtitle = (
        f"Revenue per quarter (top) and change from the previous quarter (bottom), {first['quarter']} to "
        f"{last['quarter']}: {fmt_musd(year_ago['revenue_musd'])} in {year_ago['quarter']}, "
        f"{fmt_musd(last['revenue_musd'])} in {last['quarter']}."
    )

    def moves(x: float) -> str:
        return f"{'dip' if x < 0 else 'rise'} {abs(x):.0f}%"

    gh3, gh4, pe = sf[("github", 3)], sf[("github", 4)], max(abs(sf[("peers", k)]) for k in range(1, 5))
    seasonal_title = (
        f"Public GitHub pushes {moves(gh3)} in Q3 and {moves(gh4)} in Q4; "
        f"usage-priced cloud revenue moves under {math.ceil(pe)}%"
    )
    seasonal_sub = (
        f"Typical growth from the previous quarter relative to the year's average, by calendar quarter, "
        f"{years[0]}–{years[1]}: US git pushes to public repositories, the summed revenue of seven usage-priced "
        "developer-infrastructure companies, and US working days."
    )
    by_q = {}
    for r in adj.iter_rows(named=True):
        by_q.setdefault(r["variant"], {})[r["quarter"]] = r["growth_pct"]
    slowest = {v: min(g, key=g.get) for v, g in by_q.items()}
    if len(set(slowest.values())) == 1:
        sq = slowest["filed"]
        adjusted_title = f"Removing seasonal patterns leaves {sq} the slowest quarter"
    else:
        adjusted_title = "Removing seasonal patterns changes which quarter grew slowest"
    adjusted_sub = (
        f"Anthropic's revenue growth from the previous quarter, as filed, per US working day, and with the "
        f"typical {years[0]}–{years[1]} quarter pattern of public GitHub pushes or of usage-priced cloud revenue "
        "removed."
    )
    return Story(
        title=title,
        subtitle=subtitle,
        frames={"quarters": q, "seasonal": seasonal, "adjusted": adj},
        sources=["curated_disclosures", "github_innovation_graph", "sec_edgar"],
        as_of=as_of,
        method=(
            "revenue as filed (unaudited); change = quarter ÷ previous quarter − 1; seasonal factor = "
            f"{years[0]}–{years[1]} mean of a quarter's log growth minus its year's mean, removed by division"
        ),
        caveats=[
            "Quarterly figures are unaudited (the S-1's quarterly results table); annual figures in the same "
            "filing are audited.",
            "A registration statement can be amended before the offering; a changed figure would be recorded as "
            "a new row that supersedes the old one.",
            "Revenue is recognised GAAP revenue, not a run-rate: it is not comparable with Anthropic's earlier "
            "run-rate statements without the caveats in README.md.",
            "Year-over-year exists only for the last two quarters (the table starts in 2025 Q1).",
            "GitHub pushes are public activity only; private (most company) work may follow another calendar.",
            "Seasonal factors are means over four base years; Anthropic has one year of each quarter, so its "
            "own seasonality cannot be estimated.",
        ],
        notes=[
            f"Source: Anthropic, PBC Form S-1, SEC EDGAR, filed {filed:%b %-d, %Y}. Quarters are unaudited; "
            "the filing leaves 2026 Q3 blank."
        ],
        extra={
            "yoy_multiple": yoy,
            "yoy_from": year_ago["quarter"],
            "yoy_to": last["quarter"],
            "first_to_last_multiple": span,
            "filed": str(filed),
            "base_years": list(years),
        },
        by_visual={
            "seasonal": {
                "title": seasonal_title,
                "subtitle": seasonal_sub,
                "notes": [
                    "Bars: mean over the base years; whiskers: the lowest and highest year. Cloud revenue: "
                    "Snowflake, Datadog, MongoDB, Cloudflare, DigitalOcean, Twilio, Fastly (10-Q / 10-K)."
                ],
            },
            "adjusted": {
                "title": adjusted_title,
                "subtitle": adjusted_sub,
                "notes": [
                    f"Anthropic: S-1 filed {filed:%b %-d, %Y}. A pattern is removed by dividing the quarter's growth "
                    "by the comparator's typical growth in that calendar quarter relative to its year."
                ],
            },
        },
    )


def table(story: Story) -> pl.DataFrame:
    adj = story.frames["adjusted"].pivot(on="variant", index="quarter", values="growth_pct")
    q = story.frames["quarters"].select("quarter", "revenue_musd", "qoq_pct", "yoy_multiple")
    return q.join(adj.drop("filed"), on="quarter", how="left")

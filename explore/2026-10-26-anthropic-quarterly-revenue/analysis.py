"""Anthropic quarterly revenue from its S-1: level, change from the previous quarter, year-over-year multiple.

Reads mart 080 (disclosures) only; never cachereg.sources. See README.md for method and caveats.
`cachereg render explore/2026-10-26-anthropic-quarterly-revenue` renders the visuals declared in explore.yaml.

The figures are the S-1's quarterly results table (unaudited), recorded row by row in the curated
disclosures dataset as `revenue_quarterly` (millions of US dollars per quarter). Run-rate disclosures are a
different metric and are never mixed in here.
"""

from __future__ import annotations

from datetime import date

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

    title = f"Anthropic's quarterly revenue grew {yoy:.1f}× in a year"
    subtitle = (
        f"Revenue per quarter (top) and change from the previous quarter (bottom), {first['quarter']} to "
        f"{last['quarter']}: {fmt_musd(year_ago['revenue_musd'])} in {year_ago['quarter']}, "
        f"{fmt_musd(last['revenue_musd'])} in {last['quarter']}."
    )
    return Story(
        title=title,
        subtitle=subtitle,
        frames={"quarters": q},
        sources=["curated_disclosures"],
        as_of=as_of,
        method=(
            "revenue as filed (unaudited quarters); change = quarter ÷ previous quarter − 1; "
            "year-over-year = quarter ÷ same quarter a year earlier"
        ),
        caveats=[
            "Quarterly figures are unaudited (the S-1's quarterly results table); annual figures in the same "
            "filing are audited.",
            "A registration statement can be amended before the offering; a changed figure would be recorded as "
            "a new row that supersedes the old one.",
            "Revenue is recognised GAAP revenue, not a run-rate: it is not comparable with Anthropic's earlier "
            "run-rate statements without the caveats in README.md.",
            "Year-over-year exists only for the last two quarters (the table starts in 2025 Q1).",
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
        },
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["quarters"].select("quarter", "revenue_musd", "qoq_pct", "yoy_multiple")

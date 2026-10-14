"""CoreWeave bond yield vs stock price (exploration).

Reads the bond_eod (100) and stock_daily (101) marts. See README.md for method and caveats.
`cachereg render receipts/coreweave-credit` renders the visuals declared in receipt.yaml.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

BIG_DROP = -10.0  # a last-day move at or below this (%) is named in the subtitle


def day(d: date) -> str:
    return f"{d:%B} {d.day}"


def latest_yields(con, ticker: str) -> pl.DataFrame:
    """Each note's last yield on the latest date with a yield for every note."""
    return query(
        con,
        """WITH y AS (SELECT * FROM bond_eod WHERE ticker = ? AND last_yield_pct IS NOT NULL),
                d AS (SELECT min(last_day) AS day FROM (SELECT cusip, max(date) AS last_day FROM y GROUP BY cusip))
           SELECT y.cusip, y.description, y.coupon_pct, y.maturity, y.date, y.last_price, y.last_yield_pct
           FROM y, d WHERE y.date = d.day ORDER BY y.last_yield_pct DESC""",
        [ticker],
    )


def build(con, as_of: date, cfg: dict) -> Story:
    ticker = cfg["ticker"]
    ranks = latest_yields(con, ticker)
    cusip = ranks["cusip"][0] if cfg.get("cusip", "auto") == "auto" else cfg["cusip"]
    bond = query(
        con,
        """SELECT date, last_yield_pct AS yield_pct, last_price AS price, description, coupon_pct, maturity
           FROM bond_eod WHERE cusip = ? AND last_yield_pct IS NOT NULL ORDER BY date""",
        [cusip],
    )
    start = bond["date"][0]
    stock = query(
        con, "SELECT date, close FROM stock_daily WHERE ticker = ? AND date >= ? ORDER BY date", [ticker, start]
    )
    if stock.is_empty() or stock["date"][0] != start:
        raise ValueError(f"no {ticker} close on {start}, the bond's first day with a yield")

    b0, b1 = bond.row(0, named=True), bond.row(-1, named=True)
    s0, s1 = stock.row(0, named=True), stock.row(-1, named=True)
    change = (s1["close"] / s0["close"] - 1) * 100
    last_move = (s1["close"] / stock["close"][-2] - 1) * 100
    desc = b0["description"].removeprefix("CoreWeave ")
    subtitle = (
        f"Yield on CoreWeave’s {desc} rose from {b0['yield_pct']:.1f}% when they began trading on {day(start)} to "
        f"{b1['yield_pct']:.1f}% on {day(b1['date'])}. Over the same span the stock "
        f"{'fell' if change < 0 else 'rose'} {abs(change):.0f}%, from ${s0['close']:.2f} to ${s1['close']:.2f}"
        + (f", after a {abs(last_move):.1f}% drop on {day(s1['date'])}." if last_move <= BIG_DROP else ".")
    )
    notes = []
    if b1["date"] < s1["date"]:
        notes.append(f"Latest bond trade data: {day(b1['date'])}; FINRA publishes each day's after the close.")
    return Story(
        title=cfg["headline"],
        subtitle=subtitle,
        frames={
            "bond": bond.select("date", "yield_pct", "price"),
            "stock": stock,
            "notes_by_yield": ranks,
        },
        sources=["finra_trace", "yahoo_prices"],
        as_of=as_of,
        method=(
            f"yield = FINRA's yield at the day's last reported trade (144A notes, CUSIP {cusip}); "
            "stock = daily close, split-adjusted"
        ),
        caveats=[
            "Two series side by side, each on its own axis; no causal link is drawn.",
            "A last-sale yield is one trade's yield, often a small trade: single days can jump and reverse.",
            "FINRA's yields run ~0.1–0.2 pt below the FactSet figures CNBC quoted for the same notes.",
        ],
        notes=notes,
        extra={
            "cusip": cusip,
            "bond_label": f"Yield to maturity, {b0['coupon_pct']:g}% senior notes due {b0['maturity']:%b. %-d, %Y}",
            "start": str(start),
            "end": str(s1["date"]),
            "stock_change_pct": change,
        },
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["bond"].join(story.frames["stock"], on="date", how="full", coalesce=True).sort("date")

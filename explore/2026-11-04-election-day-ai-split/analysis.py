"""Election-day split in AI stocks (exploration).

Reads the stock_daily (101) and stock_intraday (102) marts. See README.md for method and caveats.
`cachereg render explore/2026-11-04-election-day-ai-split` renders the visual declared in explore.yaml.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

SESSION_MIN = 390  # 09:30 to 16:00
BARS_LAST = "15:55"  # the last 5-minute bar; its end is the official close


def day(d: date) -> str:
    return f"{d:%B} {d.day}"


def minutes(bar_time: str) -> int:
    h, m = bar_time.split(":")
    return (int(h) - 9) * 60 + int(m) - 30


def series(con, ticker: str, name: str, group: str, session: date) -> tuple[list[dict], dict]:
    """A ticker's path as % from the previous close: each 5-minute bar's end, then the official close
    (SESSION_MIN). It starts at the first bar's end, not its open: the first bar's open is one print, and it
    can disagree with Yahoo's own daily open (README)."""
    closes = query(
        con,
        "SELECT date, close FROM stock_daily WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 3",
        [ticker, session],
    )
    if closes.height < 3 or closes["date"][0] != session:
        raise ValueError(f"no {ticker} close on {session} and the two sessions before it")
    close, prev, prev2 = closes["close"].to_list()
    bars = query(
        con,
        "SELECT bar_time, close FROM stock_intraday WHERE ticker = ? AND session = ? ORDER BY bar_time",
        [ticker, session],
    )
    if bars.is_empty() or bars["bar_time"][0] != "09:30" or bars["bar_time"][-1] != BARS_LAST:
        raise ValueError(f"{ticker} has no full 5-minute session on {session}")

    def pct(p: float) -> float:
        return (p / prev - 1) * 100

    points = [(minutes(r["bar_time"]) + 5, pct(r["close"])) for r in bars.to_dicts() if r["bar_time"] != BARS_LAST]
    points.append((SESSION_MIN, pct(close)))
    rows = [{"ticker": ticker, "name": name, "group": group, "minute": m, "pct": p} for m, p in points]
    high = max(rows, key=lambda r: r["pct"])
    low = min(rows, key=lambda r: r["pct"])
    summary = {
        "ticker": ticker, "name": name, "group": group, "prev_close": prev, "close": close,
        "first_bar_pct": rows[0]["pct"], "close_pct": pct(close), "prior_day_pct": (prev / prev2 - 1) * 100,
        "two_day_pct": (close / prev2 - 1) * 100, "high_pct": high["pct"], "low_pct": low["pct"],
    }  # fmt: skip
    return rows, summary


def build(con, as_of: date, cfg: dict) -> Story:
    session = date.fromisoformat(str(cfg["session"]))
    members = [(m, "rose") for m in cfg["rose"]] + [(m, "fell") for m in cfg["fell"]]
    members.append((cfg["baseline"], "baseline"))
    rows, summaries = [], []
    for m, group in members:
        r, s = series(con, m["ticker"], m["name"], group, session)
        rows += r
        summaries.append(s)
    summary = pl.DataFrame(summaries).sort("close_pct", descending=True)
    base = summary.filter(pl.col("group") == "baseline").row(0, named=True)
    subtitle = (
        f"Change from Tuesday’s close through Wednesday’s close, {day(session)}. "
        f"{base['name']} {base['close_pct']:+.1f}%."
    ).replace("-", "−")
    return Story(
        title=cfg["headline"],
        subtitle=subtitle,
        frames={"paths": pl.DataFrame(rows), "summary": summary},
        sources=["yahoo_prices", "yahoo_intraday"],
        as_of=as_of,
        method="% change from Tuesday’s close, 5-minute prices",
        caveats=[
            "One session, with stocks chosen after the move: this illustrates the split and does not measure it.",
            "Prices do not show why a stock moved; attributing the split to the election follows same-day coverage.",
        ],
        extra={"session": str(session)},
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["summary"]

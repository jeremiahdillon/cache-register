"""Chip and data center selloff (exploration).

Reads the stock_daily (101) and stock_intraday (102) marts. See README.md for method and caveats.
`cachereg render explore/2026-11-05-chip-selloff` renders the visual declared in explore.yaml.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

SESSION_MIN = 390  # 09:30 to 16:00
BARS_LAST = "15:55"  # the last 5-minute bar; its end is the official close
SECOND_OPEN = SESSION_MIN + 15  # the two-day path's x position of the second session's open: a short overnight gap


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


def two_day(con, m: dict, group: str, first: date, second: date) -> tuple[list[dict], dict]:
    """A ticker's path across two sessions as % from the close before the first, and each session's change."""
    rows1, s1 = series(con, m["ticker"], m["name"], group, first)
    rows2, s2 = series(con, m["ticker"], m["name"], group, second)
    if s2["prev_close"] != s1["close"]:
        raise ValueError(f"{m['ticker']}: {first} and {second} are not consecutive sessions")
    scale = s1["close"] / s1["prev_close"]
    rows = rows1 + [
        r | {"minute": SECOND_OPEN + r["minute"], "pct": ((1 + r["pct"] / 100) * scale - 1) * 100} for r in rows2
    ]
    summary = {
        "ticker": m["ticker"], "name": m["name"], "group": group, "prev_close": s1["prev_close"],
        "first_close": s1["close"], "close": s2["close"], "first_pct": s1["close_pct"], "second_pct": s2["close_pct"],
        "close_pct": (s2["close"] / s1["prev_close"] - 1) * 100,
    }  # fmt: skip
    return rows, summary


def build(con, as_of: date, cfg: dict) -> Story:
    session = date.fromisoformat(str(cfg["session"]))
    prior = date.fromisoformat(str(cfg["prior_session"]))
    members = [(m, "semis") for m in cfg["semis"]] + [(m, "supply") for m in cfg["supply"]]
    members.append((cfg["baseline"], "baseline"))
    rows, summaries, rows2, summaries2 = [], [], [], []
    for m, group in members:
        r, s = series(con, m["ticker"], m["name"], group, session)
        rows += r
        summaries.append(s)
        r, s = two_day(con, m, group, prior, session)
        rows2 += r
        summaries2.append(s)
    summary = pl.DataFrame(summaries).sort("close_pct", descending=True)
    summary2 = pl.DataFrame(summaries2).sort("close_pct", descending=True)

    def split(frame: pl.DataFrame) -> tuple[dict, pl.DataFrame, int]:
        """The baseline's row, the stocks, and how many stocks fell further than the baseline."""
        baseline = frame.filter(pl.col("group") == "baseline").row(0, named=True)
        stocks = frame.filter(pl.col("group") != "baseline")
        if baseline["close_pct"] >= 0 or stocks["close_pct"].max() >= 0:
            raise ValueError("the notes say the market and every stock fell")
        return baseline, stocks, stocks.filter(pl.col("close_pct") < baseline["close_pct"]).height

    def drops(stocks: pl.DataFrame, group: str) -> dict:
        moves = stocks.filter(pl.col("group") == group)["close_pct"]
        return {"low": -moves.max(), "high": -moves.min()}

    base, stocks, worse = split(summary)
    base2, stocks2, worse2 = split(summary2)
    if worse2 != stocks2.height or base2["first_pct"] <= 0:
        raise ValueError("the two-day headline and note say every stock fell further and the market first rose")
    notes = {
        "session": {
            "baseline": cfg["notes"]["baseline"].format(baseline=-base["close_pct"]),
            "semis": cfg["notes"]["semis"].format(**drops(stocks, "semis")),
            "supply": cfg["notes"]["supply"].format(**drops(stocks, "supply")),
        },
        "two_day": {
            "baseline": cfg["two_day_notes"]["baseline"].format(rose=base2["first_pct"], fell=-base2["second_pct"]),
            "semis": cfg["two_day_notes"]["semis"].format(**drops(stocks2, "semis")),
            "supply": cfg["two_day_notes"]["supply"].format(**drops(stocks2, "supply")),
        },
    }
    return Story(
        title=cfg["headline"].format(worse=worse, total=stocks.height),
        subtitle=f"Change from Wednesday’s close through Thursday’s close, {day(session)}.",
        frames={
            "paths": pl.DataFrame(rows),
            "summary": summary,
            "two_day_paths": pl.DataFrame(rows2),
            "two_day_summary": summary2,
        },
        sources=["yahoo_prices", "yahoo_intraday"],
        as_of=as_of,
        method="% change from the first close shown, 5-minute prices",
        caveats=[
            "A short window, with stocks chosen after the move: this illustrates the selloff and does not measure it.",
            "Prices do not show why a stock moved; tying the selloff to the election follows same-day coverage.",
        ],
        extra={"session": str(session), "notes": notes},
        by_visual={
            "two-day": {
                "title": cfg["two_day_headline"].format(total=stocks2.height),
                "subtitle": "Change from Tuesday’s close through Thursday’s close, November 3 to 5.",
            },
        },
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["summary"]

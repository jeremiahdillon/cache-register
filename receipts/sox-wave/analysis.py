"""The SOX and its 30 members over the two sessions after the midterms (receipt).

Reads the stock_daily (101) and stock_intraday (102) marts. See README.md for method and caveats.
`cachereg render receipts/sox-wave` renders the visual declared in receipt.yaml.
"""

from __future__ import annotations

from datetime import date

import polars as pl

from cachereg.core.warehouse import query
from cachereg.story.model import Story

SESSION_MIN = 390  # 09:30 to 16:00
SECOND_OPEN = SESSION_MIN + 15  # x position of the second session's open: a short overnight gap
BARS_LAST = "15:55"  # the last 5-minute bar; its end is the official close


def minutes(bar_time: str) -> int:
    h, m = bar_time.split(":")
    return (int(h) - 9) * 60 + int(m) - 30


def path(con, ticker: str, session: date, base: float, close: float, offset: int) -> list[dict]:
    """A session's path as % from `base`: each 5-minute bar's end, then the official close."""
    bars = query(
        con,
        "SELECT bar_time, close FROM stock_intraday WHERE ticker = ? AND session = ? ORDER BY bar_time",
        [ticker, session],
    )
    if bars.is_empty() or bars["bar_time"][0] != "09:30" or bars["bar_time"][-1] != BARS_LAST:
        raise ValueError(f"{ticker} has no full 5-minute session on {session}")
    points = [(minutes(r["bar_time"]) + 5, r["close"]) for r in bars.to_dicts() if r["bar_time"] != BARS_LAST]
    points.append((SESSION_MIN, close))
    return [{"minute": offset + m, "pct": (p / base - 1) * 100} for m, p in points]


def series(con, m: dict, group: str, first: date, second: date) -> tuple[list[dict], dict]:
    closes = query(
        con,
        "SELECT date, close FROM stock_daily WHERE ticker = ? AND date <= ? ORDER BY date DESC LIMIT 3",
        [m["ticker"], second],
    )
    if closes.height < 3 or closes["date"].to_list()[:2] != [second, first]:
        raise ValueError(f"no {m['ticker']} closes on {first}, {second} and the session before")
    last, mid, base = closes["close"].to_list()
    rows = path(con, m["ticker"], first, base, mid, 0) + path(con, m["ticker"], second, base, last, SECOND_OPEN)
    summary = {
        "ticker": m["ticker"], "name": m["name"], "group": group, "prev_close": base, "first_close": mid,
        "close": last, "first_pct": (mid / base - 1) * 100, "second_pct": (last / mid - 1) * 100,
        "close_pct": (last / base - 1) * 100,
    }  # fmt: skip
    return [r | {"ticker": m["ticker"]} for r in rows], summary


def build(con, as_of: date, cfg: dict) -> Story:
    first = date.fromisoformat(str(cfg["first_session"]))
    second = date.fromisoformat(str(cfg["session"]))
    rows, summaries = [], []
    for m, group in [(m, "members") for m in cfg["members"]] + [(cfg["index"], "index")]:
        r, s = series(con, m, group, first, second)
        rows += r
        summaries.append(s)
    summary = pl.DataFrame(summaries).sort("close_pct", descending=True)
    members = summary.filter(pl.col("group") == "members")
    index = summary.filter(pl.col("group") == "index")["close_pct"][0]
    if members["close_pct"].max() >= 0 or index >= 0:
        raise ValueError("the headline and notes say every member and the index fell")
    tickers = members["ticker"].to_list()
    if unknown := set(cfg["label"]) - set(tickers):
        raise ValueError(f"labels that are not members: {sorted(unknown)}")
    labelled = [*cfg["label"], cfg["index"]["ticker"]]
    summary = summary.with_columns(pl.col("ticker").is_in(labelled).alias("labelled"))
    return Story(
        title=cfg["headline"].format(total=members.height),
        subtitle="Change from Tuesday’s close through Thursday’s close, November 3 to 5.",
        frames={"paths": pl.DataFrame(rows), "summary": summary},
        sources=["yahoo_prices", "yahoo_intraday"],
        as_of=as_of,
        method="% change from Tuesday’s close, 5-minute prices",
        caveats=[
            "Two sessions: this shows the selloff's spread within the index and does not explain it.",
            "Prices do not show why a stock moved; tying the selloff to the election follows same-day coverage.",
        ],
    )


def table(story: Story) -> pl.DataFrame:
    return story.frames["summary"]

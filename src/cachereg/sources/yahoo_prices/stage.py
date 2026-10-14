"""Stage Yahoo Finance chart bodies: one row per ticker × trading day × fetch (all vintages kept).

A bar's date is its timestamp in the exchange's time zone. `final` is false for the bar of a session
that had not closed when the body was fetched (an intraday price); marts use final bars only.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime, timedelta, timezone

import polars as pl

from cachereg.core.store import list_fetches

SOURCE = "yahoo_prices"
SCHEMA = {
    "ticker": pl.String,
    "date": pl.Date,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,  # split-adjusted (Yahoo), not dividend-adjusted
    "adj_close": pl.Float64,
    "volume": pl.Int64,
    "final": pl.Boolean,
    "currency": pl.String,
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
}


def _num(v) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v) else None


def rows_of(body: dict, fetched_at: datetime) -> list[dict]:
    res = body["chart"]["result"][0]
    meta, q = res["meta"], res["indicators"]["quote"][0]
    adj = (res["indicators"].get("adjclose") or [{}])[0].get("adjclose") or [None] * len(res["timestamp"])
    tz = timezone(timedelta(seconds=int(meta.get("gmtoffset", 0))))
    session_end = meta.get("currentTradingPeriod", {}).get("regular", {}).get("end")
    out = []
    for i, t in enumerate(res["timestamp"]):
        close = _num(q["close"][i])
        if close is None:
            continue  # a bar without a close (a halted or not-yet-traded day)
        day = datetime.fromtimestamp(t, tz).date()
        live = session_end is not None and datetime.fromtimestamp(session_end, tz).date() == day
        out.append({
            "ticker": meta["symbol"], "date": day,
            "open": _num(q["open"][i]), "high": _num(q["high"][i]), "low": _num(q["low"][i]), "close": close,
            "adj_close": _num(adj[i]), "volume": int(q["volume"][i]) if _num(q["volume"][i]) is not None else None,
            "final": not live or fetched_at.timestamp() >= session_end,
            "currency": meta.get("currency"),
        })  # fmt: skip
    return out


def stage() -> dict[str, pl.DataFrame]:
    rows, rejected = [], 0
    for f in list_fetches(SOURCE):
        common = {"fetch_id": f.manifest["fetch_id"], "fetched_at": f.fetched_at.astimezone(UTC)}
        for name in f.manifest["files"]:
            try:
                rows += [r | common for r in rows_of(json.loads(f.read(name)), f.fetched_at)]
            except (KeyError, IndexError, TypeError, ValueError):
                rejected += 1  # an unreadable body: counted, never silently dropped
    daily = pl.DataFrame(rows, schema=SCHEMA, orient="row").sort("ticker", "date", "fetch_id")
    return {"daily": daily, "_rejected_rows": pl.DataFrame({"rejected": [rejected]})}

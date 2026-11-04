"""Stage Yahoo Finance 5-minute bodies: one row per ticker × bar × fetch (all vintages kept).

A bar's session and time are its timestamp in the exchange's time zone. `final` is false for the bars of a
session that had not closed when the body was fetched; marts use final sessions only.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone

import polars as pl

from cachereg.core.store import list_fetches
from cachereg.sources.yahoo_prices.stage import _num

SOURCE = "yahoo_intraday"
SCHEMA = {
    "ticker": pl.String,
    "session": pl.Date,
    "bar_time": pl.String,  # HH:MM
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Int64,
    "final": pl.Boolean,
    "currency": pl.String,
    "fetch_id": pl.String,
    "fetched_at": pl.Datetime("us", "UTC"),
}


def rows_of(body: dict, fetched_at: datetime) -> list[dict]:
    res = body["chart"]["result"][0]
    meta, q = res["meta"], res["indicators"]["quote"][0]
    tz = timezone(timedelta(seconds=int(meta.get("gmtoffset", 0))))
    session_end = meta.get("currentTradingPeriod", {}).get("regular", {}).get("end")
    live_day = datetime.fromtimestamp(session_end, tz).date() if session_end is not None else None
    out = []
    for i, t in enumerate(res["timestamp"]):
        close = _num(q["close"][i])
        if close is None:
            continue  # a bar without a trade
        local = datetime.fromtimestamp(t, tz)
        out.append({
            "ticker": meta["symbol"], "session": local.date(), "bar_time": f"{local:%H:%M}",
            "open": _num(q["open"][i]), "high": _num(q["high"][i]), "low": _num(q["low"][i]), "close": close,
            "volume": int(q["volume"][i]) if _num(q["volume"][i]) is not None else None,
            "final": local.date() != live_day or fetched_at.timestamp() >= session_end,
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
    bars = pl.DataFrame(rows, schema=SCHEMA, orient="row").sort("ticker", "session", "bar_time", "fetch_id")
    return {"bars": bars, "_rejected_rows": pl.DataFrame({"rejected": [rejected]})}

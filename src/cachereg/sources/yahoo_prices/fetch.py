"""Fetch daily stock prices from Yahoo Finance's chart endpoint (unofficial, no key).

One request per ticker for the whole window (FLOOR to now). Bodies are stored as served; they are
never committed or inlined (author's personal, non-commercial use; SOURCE.md). Today's bar is
intraday until the session closes: stage.py keeps the bar but marks it `final` only once the
fetch came after the regular session's end.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

from cachereg.core import http
from cachereg.core.store import RawFetch

SOURCE = "yahoo_prices"
ADAPTER_VERSION = "1"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
TICKERS = ["CRWV"]  # one-off for the CoreWeave credit exploration; add tickers as analyses need them
FLOOR = date(2025, 1, 1)
HEADERS = {"User-Agent": "Mozilla/5.0"}  # the endpoint refuses unknown agents


def check_body(body, ticker: str) -> None:
    where = f"yahoo {ticker}"
    try:
        res = body["chart"]["result"][0]
        meta, ts = res["meta"], res["timestamp"]
        quote = res["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError):
        raise ValueError(f"{where}: unexpected response shape ({str(body)[:200]})") from None
    if meta.get("symbol") != ticker:
        raise ValueError(f"{where}: answered for {meta.get('symbol')!r}")
    if not ts or any(len(quote.get(k) or []) != len(ts) for k in ("open", "high", "low", "close", "volume")):
        raise ValueError(f"{where}: empty series or ragged columns")


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    now = datetime.now(UTC)
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    for ticker in TICKERS:
        params = {
            "period1": str(int(datetime(FLOOR.year, FLOOR.month, FLOOR.day, tzinfo=UTC).timestamp())),
            "period2": str(int(now.timestamp())),
            "interval": "1d",
            "includeAdjustedClose": "true",
        }
        resp = http.get(URL.format(ticker=ticker), params, HEADERS)
        check_body(resp.json(), ticker)
        raw.add(f"{ticker}.json", resp.body, resp.url, resp.status)
    digest = hashlib.sha256(b"".join(raw.files[n] for n in sorted(raw.files)))
    raw.vintage = {
        "kind": "content",
        "value": digest.hexdigest(),
        "window": [FLOOR.isoformat(), now.date().isoformat()],
    }
    return raw

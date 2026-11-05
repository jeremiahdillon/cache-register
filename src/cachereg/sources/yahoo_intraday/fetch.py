"""Fetch 5-minute stock prices from Yahoo Finance's chart endpoint (unofficial, no key).

One request per ticker for the last 60 days, all Yahoo serves at this interval. Bodies are stored as served;
they are never committed or inlined (author's personal, non-commercial use; SOURCE.md).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

from cachereg.core import http
from cachereg.core.store import RawFetch
from cachereg.sources.yahoo_prices.fetch import check_body

SOURCE = "yahoo_intraday"
ADAPTER_VERSION = "1"
URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
TICKERS = [  # election-day, chip-selloff and sox-members explorations; add tickers as analyses need them
    "MSFT", "AMZN", "GOOGL", "VST", "VRT", "PWR", "CRWV", "GEV", "SPY",
    "NVDA", "TSM", "TXN", "AVGO", "AMD", "ADI", "MU", "ASML", "ETN", "CEG", "ANET", "DELL",
    "AMAT", "ARM", "ALAB", "COHR", "CRDO", "ENTG", "GFS", "INTC", "KLAC", "LRCX", "LSCC", "MTSI", "MRVL", "MCHP",
    "MPWR", "NXPI", "ON", "Q", "QCOM", "SITM", "TER", "TSEM", "^SOX",
]  # fmt: skip
RANGE, INTERVAL = "60d", "5m"
HEADERS = {"User-Agent": "Mozilla/5.0"}  # the endpoint refuses unknown agents


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    for ticker in TICKERS:
        resp = http.get(URL.format(ticker=ticker), {"range": RANGE, "interval": INTERVAL}, HEADERS)
        check_body(resp.json(), ticker)
        raw.add(f"{ticker}.json", resp.body, resp.url, resp.status)
    digest = hashlib.sha256(b"".join(raw.files[n] for n in sorted(raw.files)))
    raw.vintage = {
        "kind": "content",
        "value": digest.hexdigest(),
        "window": [RANGE, datetime.now(UTC).date().isoformat()],
    }
    return raw

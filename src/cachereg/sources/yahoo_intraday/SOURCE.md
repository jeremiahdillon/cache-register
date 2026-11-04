# Yahoo Finance 5-minute prices (`yahoo_intraday`)

**Endpoint:** `GET https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=60d&interval=5m`
(the same unofficial, undocumented endpoint as `yahoo_prices`; it refuses requests without a browser-like
`User-Agent`)
**Auth:** none. **Tickers:** `TICKERS` in `fetch.py` (added as analyses need them).
**Terms:** Yahoo's terms (legal.yahoo.com) allow personal, non-commercial use and prohibit redistribution.
Used under the same author policy as `yahoo_prices` (2026-10-14): personal, non-commercial analysis; raw data
is never committed, inlined or redistributed; only derived charts and figures are published, credited.
**Last verified:** 2026-11-04 (first fetch).

## What it contains
One body per ticker: `chart.result[0]` with `meta` (symbol, currency, `gmtoffset`, `currentTradingPeriod`),
`timestamp[]` (one per bar, at the bar's start) and `indicators.quote[0]` (`open`, `high`, `low`, `close`,
`volume`). Regular session only.

## Classification
- history: snapshot (Yahoo serves roughly the last 60 days of 5-minute bars, so older sessions exist only in
  our own fetches) · revisions: revised
- redistribution: forbidden · derived_charts: allowed-with-attribution

## Fetch strategy
The last 60 days, one request per ticker. Refused unless the body answers for the requested symbol and every
quote column matches the timestamps. Vintage: sha256 of the bodies.

## Staged tables
- `bars`: `ticker`, `session` (exchange-local date), `bar_time` (exchange-local start of the bar, HH:MM), `open`, `high`,
  `low`, `close`, `volume`, `final`, `currency`, `fetch_id`, `fetched_at`. `final` is false for the bars of a
  session still open when fetched. All vintages kept; mart 102 picks the latest fetch per ticker on/before
  the cutoff, final sessions only.

## Known quirks and caveats
- Unofficial endpoint: it may change shape, rate-limit or disappear; the fetch then fails loudly.
- A session's last row can be a stub at 16:00 holding the closing price; mart 102 drops it. Take a session's
  closing price from `stock_daily`, not from the last 5-minute bar, which can differ by a few cents.
- Prices are not adjusted for splits or dividends.

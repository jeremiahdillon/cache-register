# Yahoo Finance daily prices (`yahoo_prices`)

**Endpoint:** `GET https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?period1=&period2=&interval=1d&includeAdjustedClose=true`
(unofficial and undocumented; it refuses requests without a browser-like `User-Agent`)
**Auth:** none. **Tickers:** `TICKERS` in `fetch.py` (CRWV only, for `explore/2026-10-14-coreweave-credit`).
**Terms:** Yahoo's terms (legal.yahoo.com) allow personal, non-commercial use and prohibit redistribution.
Used here under the author's policy (2026-10-14): personal, non-commercial analysis; raw data is never
committed, inlined or redistributed; only derived charts and figures are published, credited. Anyone
reproducing is bound by the same terms.
**Last verified:** 2026-10-14 (first fetch).

## What it contains
One body per ticker: `chart.result[0]` with `meta` (symbol, currency, exchange time zone and
`gmtoffset`, `currentTradingPeriod`), `timestamp[]` (one per session, at the open), and
`indicators.quote[0]` (`open`, `high`, `low`, `close`, `volume`) plus `indicators.adjclose[0]`.

## Classification
- history: native · revisions: revised (Yahoo re-adjusts past closes for splits; Latest-only)
- redistribution: forbidden · derived_charts: allowed-with-attribution

## Fetch strategy
Whole window from 2025-01-01 to now, one request per ticker. Refused unless the body answers for the
requested symbol and every quote column matches the timestamps. Vintage: sha256 of the bodies.

## Staged tables
- `daily`: `ticker`, `date` (exchange-local), `open`, `high`, `low`, `close` (split-adjusted),
  `adj_close`, `volume`, `final`, `currency`, `fetch_id`, `fetched_at`. `final` is false for a session
  still open when fetched (intraday price). All vintages kept; mart 101 picks the latest fetch per
  ticker on/before the cutoff, final bars only.

## Known quirks and caveats
- Unofficial endpoint: it may change shape, rate-limit or disappear; the fetch then fails loudly.
- A fetch during the session holds an intraday last price for today, marked not final.

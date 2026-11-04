-- inputs: yahoo_intraday
-- 5-minute regular-session stock prices from Yahoo Finance (explore/2026-11-04-election-day-ai-split), Latest-only.
-- Variables set by cachereg.build: as_of, yahoo_intraday_cutoff.
-- Assumptions (documented in every analysis that uses this mart):
--   * bar_time = the bar's start, exchange-local HH:MM; final sessions only (a session still open is dropped).
--   * each ticker's rows all come from ONE fetch: the latest on/before the cutoff.
--   * a stub row at or after 16:00 is dropped; a session's closing price is in stock_daily.

CREATE OR REPLACE TABLE stock_intraday AS
WITH pick AS (
    SELECT ticker, max(fetch_id) AS fetch_id
    FROM stg_yahoo_intraday_bars
    WHERE CAST(fetched_at AS DATE) <= getvariable('yahoo_intraday_cutoff')
    GROUP BY ticker
)
SELECT b.session, b.bar_time, b.ticker, b.open, b.high, b.low, b.close, b.volume, b.currency, b.fetch_id
FROM stg_yahoo_intraday_bars b
JOIN pick USING (ticker, fetch_id)
WHERE b.final AND b.session <= getvariable('as_of') AND b.bar_time < '16:00'
ORDER BY b.ticker, b.session, b.bar_time;

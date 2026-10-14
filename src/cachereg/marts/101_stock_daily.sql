-- inputs: yahoo_prices
-- Daily stock closes from Yahoo Finance (explore/2026-10-14-coreweave-credit), Latest-only.
-- Variables set by cachereg.build: as_of, yahoo_prices_cutoff.
-- Assumptions (documented in every analysis that uses this mart):
--   * close = Yahoo's split-adjusted close; final sessions only (an intraday bar is dropped).
--   * each ticker's rows all come from ONE fetch: the latest on/before the cutoff.

CREATE OR REPLACE TABLE stock_daily AS
WITH pick AS (
    SELECT ticker, max(fetch_id) AS fetch_id
    FROM stg_yahoo_prices_daily
    WHERE CAST(fetched_at AS DATE) <= getvariable('yahoo_prices_cutoff')
    GROUP BY ticker
)
SELECT d.date, d.ticker, d.close, d.adj_close, d.volume, d.currency, d.fetch_id
FROM stg_yahoo_prices_daily d
JOIN pick USING (ticker, fetch_id)
WHERE d.final AND d.date <= getvariable('as_of')
ORDER BY d.ticker, d.date;

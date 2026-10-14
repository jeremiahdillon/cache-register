-- inputs: finra_trace
-- FINRA TRACE end-of-day bond prices and yields (explore/2026-10-14-coreweave-credit), Latest-only.
-- Variables set by cachereg.build: as_of, finra_trace_cutoff.
-- Assumptions (documented in every analysis that uses this mart):
--   * a day's yield is the yield of its last reported trade (FINRA), not a quote or an evaluated price;
--     days without trades have no row.
--   * each CUSIP's rows all come from ONE fetch: the latest on/before the cutoff.

CREATE OR REPLACE TABLE bond_eod AS
WITH pick AS (
    SELECT cusip, max(fetch_id) AS fetch_id
    FROM stg_finra_trace_eod
    WHERE CAST(fetched_at AS DATE) <= getvariable('finra_trace_cutoff')
    GROUP BY cusip
)
SELECT
    e.date,
    e.cusip,
    b.ticker,
    b.coupon_pct,
    b.maturity,
    b.description,
    e.last_price,
    e.last_yield_pct,
    e.fetch_id
FROM stg_finra_trace_eod e
JOIN pick USING (cusip, fetch_id)
JOIN stg_finra_trace_bonds b USING (cusip)
WHERE e.date <= getvariable('as_of')
ORDER BY e.cusip, e.date;

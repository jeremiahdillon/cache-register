-- inputs: sec_edgar
-- Capex marts (PLAN §2.1 #11, analysis (b)): quarterly cash capital expenditure per company and
-- per company group from SEC XBRL company facts, as known on as_of (Exact: facts are selected by
-- their filing date, not by when they were fetched).
-- Variables set by cachereg.build: as_of.
-- Assumptions (documented in every analysis that uses these marts):
--   * capex = cash paid for property and equipment, us-gaap tag precedence
--     PaymentsToAcquireProductiveAssets (Amazon, NVIDIA) then
--     PaymentsToAcquirePropertyPlantAndEquipment; one tag per company quarter, kept in `tag`.
--   * finance_lease_additions = RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability (new
--     finance-lease assets, non-cash); capex_incl_finance_leases_usd adds it where tagged (an
--     upper bound where tagged; several companies tag it only in some quarters, counted in
--     finance_lease_companies).
--   * only 10-K / 10-Q facts (and amendments) filed on or before as_of; for each period the
--     latest filing wins (a restatement replaces the earlier value from its filing date).
--   * cash-flow facts are year-to-date: a quarter is a reported 3-month fact, else the
--     difference of two year-to-date facts with the same start (Q4 = FY − 9M).
--   * a fiscal quarter belongs to the calendar quarter containing its midpoint.

CREATE OR REPLACE TABLE edgar_quarterly AS
WITH measures(measure, tag, pref) AS (
    VALUES
        ('capex', 'PaymentsToAcquireProductiveAssets', 1),
        ('capex', 'PaymentsToAcquirePropertyPlantAndEquipment', 2),
        ('finance_lease_additions', 'RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability', 1)
),
facts AS (
    SELECT f.cik, m.measure, m.tag, m.pref, f.period_start, f.period_end, f.val, f.accn, f.filed,
        round(datediff('day', f.period_start, f.period_end) / 30.4375) AS months,
        datediff('day', f.period_start, f.period_end) AS days
    FROM stg_sec_edgar_facts f
    JOIN measures m ON f.tag = m.tag
    WHERE f.taxonomy = 'us-gaap' AND f.unit = 'USD' AND f.period_start IS NOT NULL
      AND f.form IN ('10-K', '10-Q', '10-K/A', '10-Q/A')
      AND f.filed <= getvariable('as_of')
),
latest AS (  -- one value per period as known on as_of
    SELECT * FROM facts
    WHERE months IN (3, 6, 9, 12) AND abs(days - months * 30.4375) <= 8
    QUALIFY row_number() OVER (
        PARTITION BY cik, measure, tag, period_start, period_end ORDER BY filed DESC, accn DESC
    ) = 1
),
reported AS (
    SELECT cik, measure, tag, pref, period_start, period_end, val AS value_usd,
        'reported' AS method, accn, filed
    FROM latest WHERE months = 3
),
derived AS (
    SELECT y.cik, y.measure, y.tag, y.pref, CAST(p.period_end + INTERVAL 1 DAY AS DATE) AS period_start,
        y.period_end, y.val - p.val AS value_usd, 'ytd_difference' AS method,
        y.accn, greatest(y.filed, p.filed) AS filed
    FROM latest y
    JOIN latest p ON p.cik = y.cik AND p.measure = y.measure AND p.tag = y.tag
        AND p.period_start = y.period_start AND p.months = y.months - 3
    WHERE y.months > 3
),
quarters AS (
    SELECT * FROM reported
    UNION ALL
    SELECT * FROM derived
)
SELECT
    q.cik,
    c.ticker,
    c.name AS company,
    c."group" AS company_group,
    c.vendor_id,
    q.measure,
    q.period_start,
    q.period_end,
    CAST(date_trunc('quarter', q.period_start + CAST(datediff('day', q.period_start, q.period_end) // 2 AS INTEGER)) AS DATE) AS cal_quarter,
    q.value_usd,
    q.method,
    q.tag,
    q.accn,
    q.filed
FROM quarters q
JOIN stg_sec_edgar_companies c USING (cik)
-- highest-precedence tag first, then a reported quarter over a derived one
QUALIFY row_number() OVER (
    PARTITION BY q.cik, q.measure, q.period_end ORDER BY q.pref, q.method = 'ytd_difference', q.filed DESC
) = 1;

-- Two fiscal quarters in one calendar quarter (e.g. a changed fiscal year end) would be summed:
-- fail the build instead.
SELECT CASE WHEN count(*) > 0 THEN error('030_capex: two fiscal quarters map to one calendar quarter for '
    || string_agg(DISTINCT cik || ' ' || cal_quarter, ', ')) END
FROM (SELECT cik, cal_quarter FROM edgar_quarterly GROUP BY cik, measure, cal_quarter HAVING count(*) > 1);

CREATE OR REPLACE TABLE capex_quarterly AS
SELECT
    cik,
    any_value(ticker) AS ticker,
    any_value(company) AS company,
    any_value(company_group) AS company_group,
    any_value(vendor_id) AS vendor_id,
    cal_quarter,
    sum(value_usd) FILTER (WHERE measure = 'capex') AS capex_usd,
    sum(value_usd) FILTER (WHERE measure = 'finance_lease_additions') AS finance_lease_additions_usd,
    capex_usd + coalesce(finance_lease_additions_usd, 0) AS capex_incl_finance_leases_usd,
    min(period_start) FILTER (WHERE measure = 'capex') AS period_start,
    max(period_end) FILTER (WHERE measure = 'capex') AS period_end,
    max(filed) FILTER (WHERE measure = 'capex') AS filed
FROM edgar_quarterly
GROUP BY cik, cal_quarter
HAVING capex_usd IS NOT NULL;

CREATE OR REPLACE TABLE capex_group_quarterly AS
WITH first_q AS (
    SELECT cik, company_group, min(cal_quarter) AS first_quarter FROM capex_quarterly GROUP BY ALL
),
grid AS (
    SELECT DISTINCT q.company_group, q.cal_quarter, f.cik
    FROM capex_quarterly q
    JOIN first_q f ON f.company_group = q.company_group AND f.first_quarter <= q.cal_quarter
)
SELECT
    g.company_group,
    g.cal_quarter,
    sum(q.capex_usd) AS capex_usd,
    sum(q.capex_incl_finance_leases_usd) AS capex_incl_finance_leases_usd,
    count(q.cik) AS companies_reported,
    count(q.finance_lease_additions_usd) AS finance_lease_companies,
    count(*) AS companies_expected,
    count(q.cik) = count(*) AS complete,
    string_agg(q.ticker, ',' ORDER BY q.ticker) AS tickers
FROM grid g
LEFT JOIN capex_quarterly q ON q.cik = g.cik AND q.cal_quarter = g.cal_quarter
GROUP BY ALL
ORDER BY g.company_group, g.cal_quarter;

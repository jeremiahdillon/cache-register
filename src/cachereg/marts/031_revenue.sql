-- inputs: sec_edgar
-- Revenue marts: quarterly company revenue from SEC XBRL company facts, as known on as_of (Exact:
-- facts are selected by their filing date). Built on edgar_quarterly (030_capex), which derives
-- quarters the same way for every measure.
-- Variables set by cachereg.build: as_of.
-- Assumptions (documented in every analysis that uses these marts):
--   * revenue = us-gaap RevenueFromContractWithCustomerExcludingAssessedTax, else
--     RevenueFromContractWithCustomerIncludingAssessedTax (Fastly), else Revenues; one tag per
--     company quarter, kept in `tag`. Company-wide only (no segments).
--   * a quarter is a reported 3-month fact, else the difference of two year-to-date facts (Q4 = FY − 9M);
--     the latest 10-K / 10-Q filed on or before as_of wins.
--   * a fiscal quarter belongs to the calendar quarter containing its midpoint (a Nov–Jan quarter is Q4).

CREATE OR REPLACE TABLE revenue_quarterly AS
SELECT
    cik,
    ticker,
    company,
    company_group,
    vendor_id,
    cal_quarter,
    period_start,
    period_end,
    value_usd AS revenue_usd,
    method,
    tag,
    accn,
    filed
FROM edgar_quarterly
WHERE measure = 'revenue'
ORDER BY ticker, cal_quarter;

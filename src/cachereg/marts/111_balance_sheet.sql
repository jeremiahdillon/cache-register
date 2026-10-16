-- inputs: sec_edgar
-- Balance-sheet marts (docs/plans/2026-10-14-gpu-vs-fiber.md): each company's cash and short-term
-- investments and its debt at each balance-sheet date, from SEC XBRL company facts as known on as_of.
-- Variables set by cachereg.build: as_of.
-- Assumptions (documented in every analysis that uses these marts):
--   * liquidity = cash and cash equivalents plus short-term (current) investments. Tag options, in
--     order of preference: CashCashEquivalentsAndShortTermInvestments; else
--     CashAndCashEquivalentsAtCarryingValue plus the first current-investment tag the company uses
--     (MarketableSecuritiesCurrent, DebtSecuritiesCurrent, ShortTermInvestments,
--     AvailableForSaleSecuritiesDebtSecuritiesCurrent); else cash alone.
--   * debt = borrowings: LongTermDebt (current and non-current); else LongTermDebtNoncurrent plus
--     LongTermDebtCurrent; else DebtInstrumentCarryingAmount. Leases are excluded (kept apart as
--     operating_lease_liability where tagged).
--   * instant facts from 10-K / 10-Q (and amendments) filed on or before as_of; for each date the latest
--     filing wins. Each measure uses the most preferred option complete at that date; `option` records it.

CREATE OR REPLACE TABLE balance_sheet AS
WITH parts(measure, option, tag) AS (
    VALUES
        ('liquidity', 1, 'CashCashEquivalentsAndShortTermInvestments'),
        ('liquidity', 2, 'CashAndCashEquivalentsAtCarryingValue'),
        ('liquidity', 2, 'MarketableSecuritiesCurrent'),
        ('liquidity', 3, 'CashAndCashEquivalentsAtCarryingValue'),
        ('liquidity', 3, 'DebtSecuritiesCurrent'),
        ('liquidity', 4, 'CashAndCashEquivalentsAtCarryingValue'),
        ('liquidity', 4, 'ShortTermInvestments'),
        ('liquidity', 5, 'CashAndCashEquivalentsAtCarryingValue'),
        ('liquidity', 5, 'AvailableForSaleSecuritiesDebtSecuritiesCurrent'),
        ('liquidity', 6, 'CashAndCashEquivalentsAtCarryingValue'),
        ('debt', 1, 'LongTermDebt'),
        ('debt', 2, 'LongTermDebtNoncurrent'),
        ('debt', 2, 'LongTermDebtCurrent'),
        ('debt', 3, 'DebtInstrumentCarryingAmount'),
        ('operating_lease_liability', 1, 'OperatingLeaseLiability')
),
latest AS (  -- one value per (company, tag, date) as known on as_of
    SELECT f.cik, f.tag, f.period_end, f.val, f.accn, f.filed
    FROM stg_sec_edgar_facts f
    WHERE f.taxonomy = 'us-gaap' AND f.unit = 'USD' AND f.period_start IS NULL
      AND f.form IN ('10-K', '10-Q', '10-K/A', '10-Q/A')
      AND f.filed <= getvariable('as_of')
      AND f.tag IN (SELECT tag FROM parts)
    QUALIFY row_number() OVER (PARTITION BY f.cik, f.tag, f.period_end ORDER BY f.filed DESC, f.accn DESC) = 1
),
options AS (  -- an option counts at a date only when every one of its tags is reported there
    SELECT l.cik, p.measure, p.option, l.period_end, sum(l.val) AS value_usd, count(*) AS n,
        string_agg(l.tag, ' + ' ORDER BY l.tag) AS tags, max(l.filed) AS filed
    FROM latest l
    JOIN parts p ON p.tag = l.tag
    GROUP BY l.cik, p.measure, p.option, l.period_end
    HAVING count(*) = (SELECT count(*) FROM parts q WHERE q.measure = p.measure AND q.option = p.option)
)
SELECT
    o.cik,
    c.ticker,
    c.name AS company,
    c."group" AS company_group,
    o.measure,
    o.period_end,
    o.value_usd,
    o.option,
    o.tags,
    o.filed
FROM options o
JOIN stg_sec_edgar_companies c USING (cik)
QUALIFY row_number() OVER (PARTITION BY o.cik, o.measure, o.period_end ORDER BY o.option) = 1
ORDER BY c.ticker, o.measure, o.period_end;

-- Each company's latest balance-sheet date with both liquidity and debt, and the two side by side.
CREATE OR REPLACE TABLE balance_sheet_latest AS
WITH both_known AS (
    SELECT cik, period_end FROM balance_sheet
    WHERE measure IN ('liquidity', 'debt')
    GROUP BY cik, period_end HAVING count(DISTINCT measure) = 2
),
last_date AS (SELECT cik, max(period_end) AS period_end FROM both_known GROUP BY cik)
SELECT
    b.ticker,
    b.company,
    b.company_group,
    d.period_end,
    max(b.value_usd) FILTER (WHERE b.measure = 'liquidity') AS liquidity_usd,
    max(b.value_usd) FILTER (WHERE b.measure = 'debt') AS debt_usd,
    max(b.value_usd) FILTER (WHERE b.measure = 'operating_lease_liability') AS operating_lease_liability_usd,
    max(b.tags) FILTER (WHERE b.measure = 'liquidity') AS liquidity_tags,
    max(b.tags) FILTER (WHERE b.measure = 'debt') AS debt_tags
FROM balance_sheet b
JOIN last_date d ON d.cik = b.cik AND d.period_end = b.period_end
GROUP BY b.ticker, b.company, b.company_group, d.period_end
ORDER BY b.ticker;

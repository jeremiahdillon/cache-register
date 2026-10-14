# FINRA TRACE end-of-day prices and yields (`finra_trace`)

**Endpoint:** `POST https://services-dynarep.ddwa.finra.org/public/reporting/v2/data/group/FixedIncomeMarket/name/EndOfDayPriceYield`,
the data service behind finra.org/finra-data/fixed-income (each bond page's "Price and Yield" chart).
Undocumented; found in the site's own script (`app-dynamic-reporting.js`, 2026-10-14). A GET to any
public endpoint sets an `XSRF-TOKEN` cookie that data requests echo in `X-XSRF-TOKEN`. FINRA's documented
API (api.finra.org) needs an account and was not checked for per-bond data.
**Auth:** none. **Bonds:** `bonds.py` (CoreWeave's four straight senior notes, 144A CUSIPs).
**Terms:** finra.org's terms of use; FINRA data may not be redistributed. Used under the author's policy
(2026-10-14): personal, non-commercial analysis; raw data never committed, inlined or redistributed;
derived charts and figures published, credited "FINRA TRACE".
**Last verified:** 2026-10-14 (first fetch).

## What it contains
`{status, returnBody: {headers, data}}` where `data` is a JSON string: one row per CUSIP × trade date
with `tradeDate`, `lastSalePrice` (% of par) and `lastSaleYield` (%), FINRA's end-of-day summary of
TRACE: the price of the day's last reported trade and the yield at that price. Only days with a trade.
FINRA leaves the yield empty on some days (a bond's first days of trading; Reg S lines always).

## Classification
- history: native · revisions: revised (late trade reports can change a day's last sale; Latest-only)
- redistribution: forbidden · derived_charts: allowed-with-attribution

## Fetch strategy
One request per CUSIP, 2025-01-01 to today, `limit` 5000 (a full page fails the fetch: paginate then).
Refused unless `status` is `success`, rows exist and every row is for the requested CUSIP. Vintage:
sha256 of the bodies.

## Staged tables
- `eod`: `cusip`, `symbol`, `date`, `last_price`, `last_yield_pct` (null when FINRA gives none),
  `fetch_id`, `fetched_at`. All vintages; mart 100 picks the latest fetch per CUSIP on/before the cutoff.
- `bonds`: `cusip`, `ticker`, `coupon_pct`, `maturity`, `description` (from `bonds.py`).

## Known quirks and caveats
- A last-sale yield is one trade's yield, often a small one: single days can jump (2026-07-29: +1.3 pt
  and back the next day on both the 2031 and 2032 notes). Not a quote, not an index, not FactSet's
  evaluated yield (CNBC's figures run ~0.1–0.2 pt higher).
- Undocumented endpoint: it may change without notice; the fetch then fails loudly.
- No rows on bond-market holidays (e.g. Columbus Day) or days without trades; today's rows appear
  after FINRA's end-of-day run.

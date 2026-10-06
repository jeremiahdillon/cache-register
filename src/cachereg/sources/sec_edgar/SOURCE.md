# SEC EDGAR XBRL company facts (`sec_edgar`)

**API:** `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
([EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces))
**Companies:** `config/entities/tickers.yaml` (ticker → CIK, name, group, vendor)
**Terms:** [sec.gov privacy and security policy](https://www.sec.gov/privacy), "Website
Dissemination": information on sec.gov "is considered public information and may be copied or
further distributed by users of the web site without the SEC's permission. Please consider
appropriate citation to the SEC as the source."
**Fair access:** at most 10 requests per second, and a User-Agent naming the requester with a
contact address ([developer resources](https://www.sec.gov/about/developer-resources)).
**Attribution:** "SEC EDGAR XBRL financial data (sec.gov)"
**Auth:** none; **requires** `SEC_EDGAR_USER_AGENT` (`Name contact@example.com`), sent as the
User-Agent and never stored.
**Last verified:** 2026-10-06

## What it contains
Every XBRL fact a company has filed, by taxonomy (`us-gaap`, `dei`, …), tag and unit. A fact has
`start` (duration facts only), `end`, `val`, `accn` (filing accession), `fy`, `fp`, `form`,
`filed` and sometimes `frame`. One file per company, 40–340 KB gzip (2026-10-06).

## Classification
- history: native · revisions: append-only → **Exact** (PLAN §4.4): a restatement is a new fact
  with its own accession and `filed` date, and earlier facts stay in the file, so selecting facts
  by `filed` ≤ as-of gives the same values from any later fetch.
- redistribution: allowed · derived_charts: allowed (public information; cited anyway).

## Vintage rule
Manifests record `vintage = {kind: edgar_filed, value: <newest accession>, date: <its filed
date>, window: [<oldest filed>, <fetch date − 1>]}`. Staging reads, per company, the newest fetch
that holds it. `stage.vintage_at(as_of)` gives the newest filing on or before as-of.

## Fetch strategy
One request per company in `tickers.yaml`, gzip, 0.15 s apart; each response is validated (JSON
with `facts`, matching CIK) and stored as served (`companyfacts_CIK##########.json[.gz]`).
Weekly: filings are quarterly.

## Known quirks and caveats
- **Year-to-date flows.** Cash-flow facts are reported from the fiscal-year start (3, 6, 9, 12
  months); some companies also tag the discrete quarter, most do not. Q4 exists only as
  FY − 9M. Mart `030_capex` derives quarters and records the method.
- **Fiscal years differ:** Microsoft ends in June, Oracle in May, NVIDIA in late January
  (52/53 weeks). `030_capex` maps a fiscal quarter to the calendar quarter of its midpoint.
- **Tags change.** Capex is `PaymentsToAcquirePropertyPlantAndEquipment` for most companies;
  Amazon uses `PaymentsToAcquireProductiveAssets` from FY2016 comparatives on and NVIDIA from
  FY2020. Amazon's older tag is net of proceeds and incentives (FY2016: 6.74 bn net vs 7.80 bn
  gross), so Amazon's quarters before 2017 are not comparable with later ones.
- **Finance leases.** The cash capex tag excludes assets acquired under finance leases, which
  Microsoft and Amazon include in the capex they present.
  `RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability` is tagged unevenly (Meta only
  through 2023; Oracle and CoreWeave in a few quarters).
- **Restatements and rounding:** the same period appears in several filings; values differ for
  some periods (e.g. Meta 2021 Q1). The latest filing on or before as-of wins.
- 8-K facts (earnings releases) are in the file and are not used by marts.
- Company-wide figures only: segment facts (Azure, Data Center) are out of scope (PLAN §2.1).

# Census Business Trends and Outlook Survey (`census_btos`)

**Page:** https://www.census.gov/data/experimental-data-products/business-trends-and-outlook-survey.html
(data tool and downloads: https://www.census.gov/hfp/btos; methodology:
`/hfp/btos/downloads/methodology/Business_Trends_and_Outlook_Survey_Methodology_V6.pdf`; wording change:
`/hfp/btos/downloads/AI Question Wording Updates.pdf`)
**Access:** public Excel downloads under `https://www.census.gov/hfp/btos/downloads/`, no key. (The Census
Data API at api.census.gov has no BTOS dataset. The BTOS site's own JSON API, `/hfp/btos/api`, serves one
period per request and national rows only inside a ~10 MB all-strata body; it is not used.)
**License:** a work of the U.S. Government, not subject to copyright in the U.S. (17 U.S.C. §105); no
licence text on the site. Census asks for citation; the files say "Source: U.S. Census Bureau, Business
Trends and Outlook Survey (BTOS)". Census: users who create their own estimates "should cite the Census
Bureau as the source of the original data only", and unpublished estimates derived by subtraction
"should not be attributed to the U.S. Census Bureau". So our monthly averages are labelled as ours.
**Attribution:** "U.S. Census Bureau, Business Trends and Outlook Survey (census.gov/hfp/btos), as of {as_of}"
**Last verified:** 2026-10-07 (design and the requests made: `docs/plans/2026-10-07-census-btos.md`)

## What it contains

A voluntary biweekly survey of U.S. employer businesses (~1.2 million a year in six panels of ~200,000;
each panel answers every 12 weeks; a new sample every summer). Estimates are weighted shares of
**businesses** (firm counts, not employment) answering the question, "Do not know" included in the
denominator, with standard errors (delete-a-group jackknife). This source reads the two core AI
questions, Yes / No / Do not know, from cycle `202319` (collected 11–24 Sep 2023):

- `ai_current`: "In the last two weeks, did this business use Artificial Intelligence (AI) …"
- `ai_expected`: "During the next six months, do you think this business will be using Artificial
  Intelligence (AI) …"

Breakdowns: national, NAICS sector (2-digit; `31` = 31–33, `44` = 44–45, `48` = 48–49, `XX` = multi-unit
firms in several sectors, counted nationally but in no sector), employment size class (`A` 1–4, `B` 5–9,
`C` 10–19, `D` 20–49, `E` 50–99, `F` 100–249, `G` 250+ employees) and sector × size. Not read: state,
subsector, MSA, state × sector, the AI supplements (pooled one-off estimates) and every non-AI question.

## Classification
- history: native (each workbook is its breakdown's full history)
- revisions: **revised** → **Latest-only**. Census describes no revision of published estimates
  (responses are not edited; late responses are not tabulated), but files are replaced in place each
  release with no version history. Mart `070`'s `btos_revision_check` compares each workbook's used
  version with the previous stored one. If it stays empty for two months of weekly fetches, switch to
  `append-only` and select cycles by `publication_date` (Exact). Evidence so far (2026-10-08): every
  month of Ramp's restatement since Sep 2023 reproduces exactly from today's files, so those national
  values have not changed since Ramp computed them.
- redistribution: allowed · derived_charts: allowed (public domain; credited anyway)

## The files (`files.py`)

| Key | File | AI wording | Breakdowns | Size (2026-10) |
|---|---|---|---|---|
| `national` | `National.xlsx` | current | national | 88 KB |
| `sector` | `Sector.xlsx` | current | sector | 1.5 MB |
| `size` | `Employment Size Class.xlsx` | current | size | 0.5 MB |
| `sector_size` | `Sector by Employment Size Class.xlsx` | current | sector × size | 10 MB (120 MB unzipped) |
| `ai_original` | `AI Core Questions.xlsx` (frozen) | original | all four (one sheet pair each) | 1.1 MB |

Layout: an estimates sheet and a standard-error sheet with the same layout (key columns, `Question ID,
Question, Answer ID, Answer`, then one column per cycle, newest first), plus "Collection and Reference
Dates". Values are strings such as `23.8%` and `0.26%`; `S` = suppressed; `.` = not asked in that cycle.
Each sheet ends with a "Source: …" line. Dates are Excel serial numbers in the current files and
`MM/DD/YYYY` text in the AI file; the current files' date sheet also gives the sample year (written once
per year; `SHUTDOWN` on the gap) and the scheduled publication date of every cycle, including future ones.

## Known quirks and caveats
- **The November 2025 wording change is a new series.** From 17 Nov 2025 (`202524`) the questions say
  "in any of its business functions" instead of "in producing goods or services"; Census started a new
  time series because of the level shift (national current use 10.0% in `202520`, 17.3% in `202524`). The
  current files hold only the new wording; the old lives in `AI Core Questions.xlsx`.
- **Question IDs do not mark the break**: both wordings are questions 7 and 24 in the Excel files (6 and
  24 in the JSON API). The parser reads the wording from the question text, requires it to match the
  file, and stops on any other AI wording, so a future change has to be handled, not absorbed.
- **Shutdown:** no data for `202521`–`202523` (collection 6 Oct – 16 Nov 2025), never to be collected.
  `202520` was published on 20 Nov 2025, not on its scheduled 9 Oct; the date sheet keeps the scheduled
  date, so as-of filtering treats it as published on 9 Oct.
- **Dating:** a cycle is collected Monday to Sunday over two weeks and published the following
  Thursday. "The last two weeks" refers to the **reference period**, the fortnight before collection
  (three weeks for fortnight 01 after a 53-week ISO year). Mart `071` puts each cycle's reference days
  into calendar months.
- **Suppression is informative:** `S` marks a relative standard error over 50% (or disclosure or quality
  concerns), so small estimates are the ones that go missing. Within a group one answer can be suppressed
  and the others not. Sector × size is heavily suppressed (original wording: more `S` than values).
- Consecutive cycles are different businesses (panels); a level shift is possible at each sample-year
  start (`202319`, `202417`, `202515`, `202616`). Before `202319` only single-location firms were surveyed,
  with 3 size bins; the AI series start after that.
- Out of scope industries: agriculture production (NAICS 111, 112), railroads, USPS, central bank, funds
  and trusts, religious and civic organisations, private households, public administration (92). So BTOS
  sector 11 is forestry, fishing and support activities only.
- **Ramp's "Census Estimate"** (in the Ramp AI Index) is BTOS's national current-use `yes` averaged by
  month, unweighted: grouped by the month a cycle's collection **starts** through May 2026, by the month
  it **ends** from June 2026 (`btos_ramp_census_check` tests both rules).

## Fetch strategy
Weekly (`cadence: weekly`; releases are biweekly on Thursdays). Five GETs, 1 s apart; each workbook is
parsed in full before anything is written. `National.xlsx` is stored on every fetch (the release marker);
the others only when their SHA-256 differs from the newest stored copy (the manifest's vintage lists the
`unchanged` ones). Vintage: `{kind: btos_release, value: <newest national cycle>, date: <its publication
date>, files: {key: sha256}, unchanged: [...]}`. Stage parses every stored version (the sector × size
workbook takes ~3 s each); marts use, per file, the newest version fetched on or before the build cutoff.

# Plan: Census BTOS AI use as a source (Phase 2 source, prepares analysis (c))

Status: DONE · 2026-10-08

Outcome: built as planned after the author's review (decisions below). Source `census_btos` (5
workbooks, stdlib Excel reader `sources/_xlsx.py`), marts `070`–`072`, 26 synthetic tests. First real
fetch 2026-10-08 (newest cycle `202619`; 76,608 AI cells, 0 rejected; `XX` the only unmapped sector).
`btos_ramp_census_check` reproduces all 35 months of Ramp's restated series, but Ramp changed its
dating rule in June 2026 (collection start → collection end), so the check now tests both rules (§4).

## Goal

1. Add source `census_btos`: the U.S. Census Bureau's Business Trends and Outlook Survey (PLAN #9),
   fetched from the public Excel downloads on census.gov/hfp/btos. No key, no browser.
2. Staged tables and marts that give the two AI questions (current use, expected use) per
   two-week cycle and per month, nationally, by NAICS sector, by employment size class and by
   sector × size, with standard errors, suppression flags and the November 2025 wording break as a
   hard series boundary.
3. One cross-source mart that puts BTOS beside Ramp's adoption by NAICS sector for analysis (c),
   and a check that rebuilds Ramp's own "Census Estimate" from our BTOS data.

Done when everything works on synthetic fixtures in CI and on a real fetch locally. No analysis is
built here.

Out of scope: the AI supplements (Dec 2023–Feb 2024 and Nov 2025–Feb 2026; pooled one-off
estimates of tasks and effects, `AI_Supplement_Table*.xlsx`), the non-AI BTOS questions, the
performance indexes, MSAs, subsectors (NAICS 3-digit), state × sector, and unit response rates.
Each can be added later as one more file or sheet in the adapter. State is discussed in §2.

## What was measured (2026-10-07: read-only requests to census.gov, nothing kept in the repo)

Requests made (all public, unauthenticated, from a scratch folder outside the repo):

| # | Request | What it showed |
|---|---|---|
| 1 | `GET api.census.gov/data/timeseries.json` (Census Data API catalog) | 89 time-series datasets; **no BTOS** (only Household Pulse `hhpulse`/`hps`). The Census Data API is not a route |
| 2–4 | `GET census.gov/data/experimental-data-products/business-trends-and-outlook-survey.html`, `/hfp/btos/about`, `/hfp/btos/data_downloads` | Landing page (questionnaires, methodology links); `/hfp/btos/*` is a client-side app |
| 5 | `GET /hfp/btos/js/app.6558511e.js` (the app's bundle) | The download file names under `/hfp/btos/downloads/`, and a JSON API at `/hfp/btos/api` (endpoints `periods`, `strata`, `questions`, `periods/{p}/data[/{strata_type}/{value}]`) |
| 6–8 | `GET /hfp/btos/api/periods`, `/strata`, `/questions` | 132 periods (18 Jul 2022 → 15 Aug 2027, future ones pre-defined); strata `empsize` A–G, `naics2` (20), `naics3` (130), `state` (60), `msa` (25); AI question texts by period |
| 9–14 | `GET /hfp/btos/api/periods/109/data/naics2/51`, `…/empsize/A`, `…/109/questions/answers`, `…/86/data/naics2/51`, `…/111/data/naics2/51`, `…/109/data` (all strata, 9.9 MB) | Row shape, `null` for suppressed cells, `null` body for a period with no data (86) or not yet released (111); national rows only inside the all-strata body |
| 15–17 | `GET /hfp/btos/downloads/AI Question Wording Updates.pdf`, `BTOS API Reference Documentation.pdf`, `methodology/Business_Trends_and_Outlook_Survey_Methodology_V6.pdf` | Wording change, size classes, estimation, suppression (below) |
| 18–21 | `GET /hfp/btos/downloads/AI Core Questions.xlsx`, `National.xlsx`, `Sector.xlsx`, `Employment Size Class.xlsx` | The download format (below) |
| 22–29 | `GET /hfp/btos/api/periods/{31,60,84,85,87,88,89,90}/data/naics2/51` | Old wording served for periods 31–84, `null` for 85–87, new wording from 88 |
| 30–32 | `GET census.gov/about/policies/citation.html`, `/about/policies/copyright.html` (404), `/data/developers/about/terms-of-service.html` | Citation guidance; API terms (apply to api.census.gov) |
| 33–34 | `HEAD /hfp/btos/downloads/Sector by Employment Size Class.xlsx`, `State.xlsx` | 10.1 MB and 4.0 MB; `Last-Modified` and `ETag` |

### The AI questions

Two core questions, asked every cycle from the cycle collected **11–24 Sep 2023** (`202319`, the
first cycle of sample year 2) on. Answers: Yes / No / Do not know.

| Series | Current use | Expected use | Cycles |
|---|---|---|---|
| **Original** ("producing goods or services") | "In the last two weeks, did this business use Artificial Intelligence (AI) in producing goods or services? (Examples of AI: machine learning, natural language processing, virtual agents, voice recognition, etc.)" | "During the next six months, do you think this business will be using Artificial Intelligence (AI) in producing goods or services? (…)" | `202319` → `202520` (collected 11 Sep 2023 → 5 Oct 2025), 54 cycles |
| **Current** ("any of its business functions") | "In the last two weeks, did this business use Artificial Intelligence (AI) in any of its business functions? (…)" | "During the next six months, do you think this business will be using Artificial Intelligence (AI) in any of its business functions? (…)" | `202524` → today (collected from 17 Nov 2025), 22 cycles as of `202619` |

**The November 2025 wording change** (Census note "BTOS AI Core Question Updates", 3 Dec 2025):
from 17 Nov 2025 the questions say "in any of its business functions", after cognitive testing
found respondents who used AI for hiring, project management, accounting, R&D or inside software
tools answering No. "Due to a level shift observed in conjunction with the new question wording,
the decision was made to create a **new time series** for the AI questions, beginning with data
released on December 4, 2025." National current use: **10.0%** in the last old-wording cycle
(`202520`) → **17.3%** in the first new one (`202524`); **23.8%** (SE 0.26) in `202619` (collected
7–20 Sep 2026). Census publishes the two as separate series in separate files: the current
downloads carry only the new wording (old cycles are `.`), and the old wording lives in the frozen
`AI Core Questions.xlsx` ("AI Core Questions (Original)" on the historical-data tab).

Traps found:
- **Question IDs do not mark the break.** In the Excel files both wordings are question `7`
  (current) and `24` (expected); in the JSON API they are `6` and `24`. Only the text (or the file)
  tells them apart, so a pipeline keyed on question ID splices the two series silently.
- The API's `questions` metadata labels periods 85–87 (the shutdown) with the new wording, although
  they hold no data and the change took effect with period 88.

**Ramp's restatement decoded.** Ramp's `Census Estimate` (in `adoption/overall`) is the
**unweighted mean of the cycles whose collection starts in the month**: Sep 2025 = (9.9 + 10.0)/2 =
9.95; Nov 2025 = 17.3 (one cycle); Dec 2025 = (17.2 + 17.8 + 17.7)/3 = 17.5667 (three cycles start
in December). All three match Ramp to the digit. The empty 2025-10 is the shutdown. (The first real
build found that from June 2026 Ramp groups cycles by the month collection **ends** instead: June =
202612 + 202613, 20.6. Every earlier month fits the start rule; see §4.)

### Collection periods and dating

- Each cycle ("Smpdt", e.g. `202619` = ISO week-year + fortnight 01–26) is **collected over two
  weeks, Monday to Sunday**, and published **the following Thursday** (4 days after collection
  closes). Cycles are contiguous; fortnight 26 of a 53-week ISO year is 21 days (e.g. `202626`,
  14 Dec 2026 – 3 Jan 2027).
- The questions ask about "the last two weeks". Each workbook's "Collection and Reference Dates"
  sheet gives a **reference period = the two weeks before collection starts** ("Prior Two Week
  Reference Period"; 3 weeks for fortnight 01 after a 53-week year). Example: `202619` collected
  7–20 Sep 2026, reference 24 Aug – 6 Sep 2026, published 24 Sep 2026. The sheet also gives the
  publication date of every cycle, including future ones (the next is `202620`, 8 Oct 2026).
- **Shutdown gap:** no data at all for `202521`–`202523` (collection 6 Oct – 16 Nov 2025). Census:
  "The BTOS will not collect past responses … The missing data are treated as structural gaps."
  `202520` was published late (20 Nov 2025). So no reference day between 22 Sep and 2 Nov 2025 is
  covered, and the old and new wordings never share a calendar month on either dating rule.
- **Panels:** the annual sample (~1.2 million businesses) is split into six panels of ~200,000;
  each panel is surveyed every 12 weeks. Consecutive cycles are therefore **different businesses**;
  the same panel recurs every sixth cycle.
- **Sample years:** a new sample is drawn every year and the old one is retired; current
  sample year 5 started with `202616` (27 Jul 2026). Earlier starts: `202319`, `202417`, `202515`.
  A level shift at a sample-year boundary is possible.
- Before `202319` (sample year 1, "BTOS V1") only single-location businesses were surveyed, with
  3 size bins. That does not affect the AI series, which start with `202319`.

### Breakdowns

| Breakdown | File (current wording) | Old wording (`AI Core Questions.xlsx` sheet) | Codes |
|---|---|---|---|
| National | `National.xlsx` (88 KB) | National Estimates / SE | — |
| Sector (NAICS 2-digit) | `Sector.xlsx` (1.5 MB) | Sector Estimates / SE | `11 21 22 23 31 42 44 48 51 52 53 54 55 56 61 62 71 72 81 XX`: `31` = 31–33, `44` = 44–45, `48` = 48–49; **`XX` = multi-unit companies in several sectors** (counted once nationally, in no sector). No 92: public administration is out of scope |
| Employment size class | `Employment Size Class.xlsx` (0.5 MB) | Employment Size Estimates / SE | `A` 1–4, `B` 5–9, `C` 10–19, `D` 20–49, `E` 50–99, `F` 100–249, `G` 250+ employees |
| Sector × size | `Sector by Employment Size Class.xlsx` (10.1 MB) | Sector x Employment Estimates / SE | as above |
| State | `State.xlsx` (4.0 MB) | State Estimates / SE | USPS codes (multi-state firms in no state) |
| Subsector, top-25 MSA, state × sector | `Subsector.xlsx`, `Top 25 MSA.xlsx` (state × sector appears only as a `_v1` historical file in the app's file list; not checked) | Subsector, Top 25 MSA | not used |

Out-of-scope industries (2022 NAICS): agriculture production (110000, 111, 112), railroads (482),
USPS (491), central bank (521), funds and trusts (525), religious/civic organisations (813), private
households (814), public administration (92). So BTOS sector `11` is forestry, fishing and support
activities only.

### Estimates, standard errors, suppression, revisions

- **Estimate:** a weighted share of **businesses** (firm count, not employment): sum of
  nonresponse-adjusted weights for the answer ÷ sum for all businesses answering the question. "Do
  not know" stays in the denominator (national `202619`: Yes 23.8, No 66.5, Do not know 9.7).
- **Standard errors** in a twin sheet with the same layout (delete-a-group jackknife, 10 groups).
  Census: "incorporate sampling error information into their analyses". 90% MOE = 1.645 × SE.
- **Format:** estimates and SEs are strings like `23.8%` / `0.26%` (one and two decimals), cells
  `S` = suppressed, `.` = not asked in that cycle (the other wording, or a gap). The sheets are wide:
  one column per cycle, **newest first** (`202619 … 202319`), a trailing "Source: …" line, and empty
  rows. Excel dates in the date sheet are serial numbers in the current files and `MM/DD/YYYY` text
  in the frozen AI file.
- **Suppression:** `S` when the relative standard error exceeds 50%, or for disclosure avoidance
  or poor response quality. Suppression is therefore **informative**: small estimates are the ones
  that disappear (e.g. sector 11 current use is `S` in many old-wording cycles). Within one group an answer can
  be suppressed while the others are not, so Yes + No + Do not know need not sum to 100. Census:
  "Unpublished estimates derived by subtraction … should not be attributed to the U.S. Census
  Bureau." In `202619`, 3 of 120 sector AI cells and 104 of 755 sector × size AI cells are `S`.
- **Revisions:** the methodology says responses are not edited and late responses are not
  tabulated, and it says nothing about revising published estimates. But there is no versioned
  release either: all files are re-uploaded with each release (every file, including the frozen AI
  file, had `Last-Modified: 22 Sep 2026`), and Census has restructured files in place (the AI
  series moved files in Dec 2025). Unconfirmed until our own vintages are compared (§4).
- The JSON API and the Excel files agree on the cells compared (`202619` national 23.8 / SE 0.26;
  sector 51 49.0 / 1.99; size A 23.8 / 0.31).

### Access routes

| Route | Verdict |
|---|---|
| Census Data API (`api.census.gov`) | **No BTOS dataset** (request 1) |
| BTOS JSON API (`/hfp/btos/api`, documented in "BTOS API Reference Documentation", Apr 2025) | No key, no documented rate limit ("may result in you being rate-limited"). But one dataset per period: national rows only come inside the 9.9 MB all-strata body, so the AI history (76 periods) is ~750 MB per backfill or ~80 calls per period per stratum type; no state × sector or supplements; same question IDs across the wording break; no reference or publication dates. Rejected as the main route |
| **Excel downloads** (`/hfp/btos/downloads/<name>.xlsx`) | **Chosen.** No key. Each file is the full history of one breakdown with SEs, reference and publication dates, codes and notes, in ~5 requests (~17 MB total, of which 10 MB is sector × size). Census's own "Downloads and Documentation" tab and the format its notes refer to |

**No API key is needed** for either census.gov route.

### Terms

BTOS is a work of the U.S. Government (no copyright in the U.S., 17 U.S.C. §105); census.gov
publishes no licence for the files and asks only for citation. The files carry their own source
line: "Source: U.S. Census Bureau, Business Trends and Outlook Survey (BTOS) 2023-2026." Census
citation guidance: "Data users who create their own estimates using data from disseminated tables …
should cite the Census Bureau as the source of the original data only. Conclusions drawn from any
analysis of these data are the sole responsibility of the performing party." The Census Data API
terms (the "not endorsed or certified" notice) apply to api.census.gov, which we do not use.
→ `redistribution: allowed`, `derived_charts: allowed`, attribution
`"U.S. Census Bureau, Business Trends and Outlook Survey (census.gov/hfp/btos), as of {as_of}"`.
Our own monthly averages and differences are labelled as Cache Register derivations in the chart's
METHOD line, never as Census estimates.

## Design

### 1. Core

**No core change.** Fetch is a plain HTTP source (`core.http.get`, binary bodies as `sec_edgar`);
`build`'s per-source cutoff, the registry and the store already cover it. The only shared code is an
Excel reader (below), which lives with the sources as `_epoch_zip.py` does.

### 2. Source `census_btos` (`src/cachereg/sources/census_btos/`)

- **Files** (`files.py`, the registry of what is fetched and how each is read):

  | Key | File | Sheets used | Wording | Breakdown |
  |---|---|---|---|---|
  | `national` | `National.xlsx` | Response Estimates / Standard Errors, Collection and Reference Dates | current | national |
  | `sector` | `Sector.xlsx` | same | current | sector |
  | `size` | `Employment Size Class.xlsx` | same | current | size |
  | `sector_size` | `Sector by Employment Size Class.xlsx` | same | current | sector × size |
  | `ai_original` | `AI Core Questions.xlsx` | National, Sector, Employment Size, Sector x Employment (Estimates / SE), Collection and Reference Dates | original | all four |

  State is left out of this build: (c) does not need it and Ramp's Geographies view is not imported.
  Adding it is one entry here plus its sheets (`State.xlsx`, and State Estimates / SE in the
  original file).
- **Excel reader** `sources/_xlsx.py`: stdlib `zipfile` + `xml.etree` (an `.xlsx` is a zip of
  XML), returning each sheet as rows of strings (shared strings resolved, inline strings, missing
  cells as `None`). ~60 lines. **No new dependency** (polars' `read_excel` needs `fastexcel` or
  `openpyxl`, neither installed). Guards, since the file is downloaded data: refuse a part that
  contains `<!DOCTYPE` (no entity expansion), cap the total uncompressed size (512 MB; the real
  sector × size workbook is 120 MB), and read only the parts the workbook's relationships name.
- **`fetch.py`:** `GET` each file (a short pause between requests). Validate before storing: a zip
  with the expected sheet names; the estimate sheet's header starts with the breakdown's key columns
  then `Question ID, Question, Answer ID, Answer` and six-digit cycle codes; at least one AI row; the
  date sheet parses. Then store as served. **Dedupe:** `National.xlsx` (88 KB) is stored on every
  fetch (the release marker); every other file only when its SHA-256 differs from the newest stored
  copy, so an unchanged 10 MB file is not stored weekly. Stage reads, per file, the newest fetch on
  or before the cutoff that holds it (the `sec_edgar` pattern). Vintage:
  `{kind: "btos_release", value: <newest cycle with data, e.g. "202619">, date: <its publication
  date>, files: {key: sha256}}` (PLAN §4.4: "release id for BTOS").
- **`stage.py`** (AI rows only; other questions stay in raw):
  - `estimates`: `cycle` (`202619`), `wording` (`original` | `current`), `question` (`ai_current`
    | `ai_expected`), `answer` (`yes` | `no` | `dont_know`), `breakdown` (`national` | `sector` |
    `size` | `sector_size`), `sector_code` (as published: `31`, `XX`, …), `size_class` (`A`–`G`),
    `estimate_pct`, `se_pct`, `status` (`published` | `suppressed`), `file`, `fetch_id`. A `.` cell
    yields no row (not asked). `S` yields a row with null values and `status = suppressed`, never 0.
  - **Wording comes from the question text**, matched on the two phrases ("producing goods or
    services" / "any of its business functions"), and must agree with the file's declared wording;
    a mismatch or an AI-looking question that matches neither phrase fails the stage (a new wording
    change must be seen, not absorbed). The question ID is kept but never used as a key.
  - `cycles`: `cycle`, `collection_start`, `collection_end`, `reference_start`, `reference_end`,
    `publication_date` (null for the shutdown cycles), `sample_year`, `panel`, `no_data` (the
    shutdown rows), from the date sheets (serial and `MM/DD/YYYY` both parsed; the current file wins
    where both list a cycle, and disagreement is a stage error).
  - `size_classes`: `A`–`G` with employee bounds, checked against the data dictionary's text.
  - `sectors`: from `config/entities/sectors.yaml` (`aliases.btos`, §3).
  - Rejected cells (unparseable numbers, unknown codes) are counted (`_rejected_rows`), as elsewhere.
  - Cross-file check at stage time: a cycle with a value in both wordings is an error (none exist).
- **Registry entry:** `history: native`, `revisions: revised` (→ Latest-only; PLAN §4.4 already
  lists BTOS there), `redistribution: allowed`, `derived_charts: allowed`, `cadence: weekly` (releases
  are biweekly on Thursdays; weekly keeps the lag ≤ 7 days without a new cadence value),
  `requires: []`.
- **Upgrade path to Exact.** Every cycle carries its publication date. If the vintage comparison
  (`btos_revision_check`, §4) shows no past cell changing over the first two months of weekly
  fetches, switch to `revisions: append-only` and select cycles by `publication_date ≤ as_of`, which
  gives a replicator the same values for any past as-of.

### 3. Entities

- `sectors.yaml`: add `aliases.btos` per sector: `"11"` → `["11"]`, `"31-33"` → `["31"]`,
  `"44-45"` → `["44"]`, `"48-49"` → `["48"]`, and so on (20 codes; none for 92). `XX` (multi-sector
  firms) stays unmapped on purpose and is reported as such, not as a gap. A comment notes that BTOS
  `11` excludes agriculture production.
- **Sizes: no mapping.** BTOS has seven classes defined by employees; Ramp's Large / Medium / Small
  have no published thresholds. No entity file joins them. The BTOS classes are a staged table of
  the source (they matter only inside BTOS). Nor can BTOS classes be merged into wider bands: that
  needs business counts per class, which BTOS does not publish.

### 4. Marts

- **`070_btos_ai_use`** (inputs: `census_btos`): one row per cycle × wording × question × answer ×
  group (national, 19 sectors + `XX`, 7 sizes, sector × size): estimate, SE, 90% bounds,
  `status`, the cycle's collection, reference and publication dates, `sample_year`,
  `first_cycle_of_sample_year`, NAICS code and title (via `aliases.btos`), size bounds. Filters
  `publication_date ≤ as_of`. Also:
  - `btos_series_breaks`: one row per break with its dates: the wording change (last original
    `202520`, first current `202524`), the shutdown gap, sample-year starts. Charts read it to draw
    breaks rather than lines across them.
  - `btos_revision_check`: for each file, cells in the vintage used vs the previous stored vintage
    of the same file (value changed, newly suppressed, newly published, cycle removed). Empty =
    append-only behaviour; this decides the upgrade in §2.
  - `btos_coverage`: per breakdown and wording, cycles published vs suppressed, so suppression-heavy
    groups are visible before an analysis picks them.
- **`071_btos_ai_monthly`** (inputs: `census_btos`): calendar-month series for the `yes` answer,
  aligned with Ramp's months, per wording (never mixed), question and group:
  - **Method (proposed): reference-period, day-weighted.** Each cycle's reference fortnight is
    split across calendar months by days; a month's value is the day-weighted mean of the published
    cycles that touch it. Columns: `pct`, `se` (√Σ(wᵢ/W)²·seᵢ², treating panels as independent
    samples, stated as an approximation), `ref_days_covered`, `days_in_month`, `n_cycles`,
    `n_suppressed`, `partial` (coverage < 50% of the month), `has_suppression`. Months with no
    covered day (Oct 2025) are absent, never interpolated.
  - Why reference dates: the question asks about the last two weeks, and Ramp's month is a
    calendar month of transactions. Dating by collection start (Ramp's rule) puts the September 2025
    cycles' answers, which mostly describe late August and early September, in September; the
    reference rule puts them where they belong. Nationally the two differ by at most 0.44 pp so far
    (May 2026: 20.05 by collection start, 20.49 by reference days; Dec 2025: 17.57 vs 17.79). The
    reference rule also yields stub months at series edges (Aug 2023: 4 reference days), which
    `partial` marks.
  - Suppression bias: a month that averages over some suppressed cycles averages only the larger
    estimates (suppression hits small, noisy ones). Such months carry `has_suppression = true`;
    (c) should use groups with none in its window.
- **`072_adoption_two_lenses`** (inputs: `ramp_ai_index`, `census_btos`): serves (c).
  - `adoption_two_lenses`: month × scope (`overall` | `sector`) × NAICS × lens, long format, with
    `lens = ramp_paid` (Ramp: share of businesses on Ramp with AI spend in the month,
    `ramp_adoption`) and `lens = btos_use_current` / `btos_use_expected` (from `071`, with SE,
    bounds, wording and flags). Sectors are the seven Ramp adoption sectors (23, 31-33, 44-45, 51,
    52, 62, 72); `naics_assumed` carries Ramp's assumed `51`, and BTOS `54` is included as the
    sensitivity row for "Technology and media". Lenses are rows, never a ratio or a difference: they
    measure different things (§6).
  - `btos_ramp_census_check`: Ramp's `ramp_census_restated` vs our recomputation of Ramp's rules
    (unweighted mean of the national current-use `yes` cycles grouped by the month collection starts,
    and by the month it ends): month, Ramp's value, both recomputations with their cycle counts,
    `matches` (`collection_start` | `collection_end` | `both` | `neither`), `agree` (either rule within
    0.005) and `wording_agrees`. It checks both adapters at once. Built: Ramp used the start rule
    through May 2026 and the end rule from June 2026; all 35 months agree.
  - Sizes: not joined. An analysis shows BTOS's seven classes beside Ramp's three labels as two
    panels; `070`/`071` and `060` already hold both.

A bare `cachereg build` then needs both Ramp and BTOS fetched for `072` (as `051` and `040` do);
`--sources census_btos` builds `070`–`071` alone, which is also (c)'s fallback without Ramp data.

### 5. Tests (synthetic fixtures only, `tests/test_census_btos.py`)

Fixtures are tiny workbooks **written by the tests** (zip + XML strings via a small helper in
`tests/`), with invented numbers and the real layout: wide cycles newest first, `%` strings, `S`,
`.`, a trailing source line, empty rows, serial and text dates.

- `_xlsx` reads shared and inline strings, missing cells and several sheets; refuses a DOCTYPE, an
  oversize part and a non-zip body.
- Each file key stages; national, sector, size and sector × size rows land in the right breakdown;
  `31` maps to `31-33` and `XX` stays unmapped and reported.
- Wording: the same question ID with both texts stages as two series; an AI question with a third
  text fails the stage; a current-wording text inside the original file fails.
- `S` → row with null value and `suppressed`; `.` → no row; `0.0%` → 0 (a real zero, published).
- Dates: reference and publication dates parse from serial numbers and from `MM/DD/YYYY`; shutdown
  rows have `no_data`; a 21-day fortnight is kept as is.
- Fetch: a file with a missing sheet, a changed header or no AI rows is refused with nothing
  written; an unchanged non-national file is not stored again and stage still finds it in an older
  fetch; `National.xlsx` is stored every time.
- `070`: `publication_date ≤ as_of` hides a cycle published after as-of; `btos_revision_check`
  reports a changed cell between two vintages and is empty for identical ones.
- `071`: day weights for a cycle spanning two months; a 21-day fortnight; a month with no covered
  day is absent; a suppressed cycle sets `has_suppression` and is left out of the mean; wordings are
  never averaged together.
- `072`: Ramp-rule recomputation reproduces a synthetic `ramp_census_restated` (two-cycle and
  three-cycle months) and reports a planted difference; Ramp sectors join BTOS by NAICS, including
  the assumed `51`.

### 6. Caveats to carry into analysis (c)

- **Different questions, different populations.** BTOS: *self-reported use* of AI "in any of its
  business functions" in the last two weeks, free tools included, by **all U.S. employer businesses**
  (weighted), voluntary survey. Ramp: *observed paid spend* on AI in a calendar month by businesses
  **on Ramp**. Neither is a measure of the other; (c) shows them side by side, not as one series.
- **Size mix drives the national gap.** BTOS weights by business count, so 1–4 employee firms
  dominate the national figure (size A 23.8% equals the national 23.8% in `202619`, while 250+ is
  44.0%). Ramp's customers skew larger (thresholds unknown). Any overall comparison must show
  BTOS by size next to it.
- **The wording break is a new series.** Never draw one line from `202520` to `202524`; the
  ~7-point jump is mostly the wording. The shutdown leaves Oct 2025 (and late Sep 2025 by reference
  date) empty on both sides.
- Census estimates carry sampling error; monthly values are our averages of independent panels
  (approximate SE), and a month with suppressed cycles is biased upward. Derived figures (monthly
  means, the Ramp-rule check) are Cache Register's, not Census estimates.
- "Do not know" is ~10% (current) and ~26% (expected) of businesses and sits in the denominator.
  Shares of known answers (Yes ÷ (Yes + No)) are a derivation Census warns about; use only as a
  stated sensitivity, if at all.
- Sector `11` excludes agriculture production; `XX` (multi-sector firms) is in the national figure
  but in no sector; Ramp's "Technology and media" → 51 remains an assumption (54 shown beside it).
- Latest-only until `btos_revision_check` says otherwise; new sample each summer.

### 7. Docs to update when built

`SOURCE.md` (all of the above: routes, file layout, wording break and the question-ID trap, dating,
suppression, terms); `config/sources.yaml`; PLAN §2.1 #9 (Excel downloads, no key, the JSON API
exists but is not used, terms verified), §4.4 table (BTOS Latest-only with the upgrade path), §10
status and open items (the revision check after two months; the next fetch after each Thursday
release), and the (c) row in the starter-analyses table (its "needs provisioned key" and "BTOS-only
if a replicator has no Ramp key" predate the manual Ramp import).

## Decisions (author review, 2026-10-07)

1. **Route:** Excel downloads with a stdlib reader (author: "reasonable judgement"). Chosen as
   recommended: no key, no new dependency, every breakdown's full history in five requests. The reader
   streams sheets (`iterparse`; the 120 MB sector × size sheet parses in ~3 s in ~110 MB of memory) and
   refuses a DOCTYPE/ENTITY before parsing (the ruff S314 finding is answered by that guard, not by
   adding `defusedxml`).
2. **Monthly dating:** reference-period, day-weighted (agreed); Ramp's rules only in the check.
3. **Scope:** AI questions only; national, sector, size, sector × size; state later (agreed).
4. **Revisions:** Latest-only now; Exact by publication date if two months of vintages show no
   changes (agreed).
5. **Source id:** `census_btos` (agreed).
6. **"Do not know":** no known-answers variant (author: "reasonable judgement"). Census's published
   share is the only BTOS lens; Yes ÷ (Yes + No) is a derivation Census warns against attributing to it,
   and both answers are staged, so an analysis can still show the "Do not know" share beside the lens.

Implementation notes beyond the plan: `versions.fetch_date` is the UTC fetch date, matching build's
cutoff (a timestamp cast to DATE in DuckDB uses the local time zone; `060`'s Ramp coverage uses that
cast, which can only matter for fetches near midnight UTC east of Greenwich).

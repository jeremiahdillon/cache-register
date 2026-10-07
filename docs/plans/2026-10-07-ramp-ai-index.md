# Plan: Ramp AI Index as a manual import (Phase 2 source, prepares analyses (c) and (e))

Status: DONE · 2026-10-07

Outcome: built as planned after an adversarial review of the plan (4 rounds; six findings fixed:
same-second fetch ids, the duplicated overall series, per-cut coverage, a clipboard seam, and data
checks for the price views and for token volume vs spend). Core gained `input: manual` and
`fetch --from-clipboard/--from-file --cut`; source `ramp_ai_index` (13 cuts); marts `060`–`062`; 72
synthetic tests. The first real import is the author's.

## Goal

1. Add source `ramp_ai_index`: the series behind ramp.com/data/ai-index, imported by hand. The
   page's "Get the data" button copies the selected view to the clipboard; the author runs
   `cachereg fetch ramp_ai_index --from-clipboard --cut <cut>` (or `--from-file <path>`) once per
   view. No Data Partner key, no scraping, no automated clicks (PLAN §10 open item).
2. A small, **generic** manual-input path in `cachereg fetch` (a core change, see §1), so that
   later manual or curated sources reuse it.
3. Staged tables and marts that give monthly adoption (overall, by vendor), AI spend by sector, and
   weekly token volume and daily token price by lab, with canonical vendor ids and NAICS sector
   codes. Done when everything works on synthetic fixtures in CI and on the author's pastes locally.
   No analysis is built here.

Out of scope: the Ramp Data API (#8, key route; the adapter's raw files are the page's TSV, not the
API's JSON, so a key adapter would be a second fetch mode later); Ramp Rate (#8b); BTOS (#9, its
own source; see §6); automating the copy.

## What was measured (2026-10-07: six author pastes, a by-hand read of the page with seven more views' headers, Ramp's public pages; no data kept)

**Clipboard format (every view checked).** UTF-8 **tab-separated text**, one header row, no title
or footer line, no "as of" stamp, no units row, **LF line endings and no trailing newline**. Dates
are ISO (`YYYY-MM-DD`). Missing values are **empty cells** (never `0` or `NA`). Numbers are plain
decimals, sometimes in **scientific notation** (`2.8654995865759356e-9`). Row order differs per view
(the adoption and spend-per-employee views are newest first, the others oldest first), and **column
order differs between wide views with the same columns** (Token spend lists Anthropic first, Token
volume OpenAI first). So neither row nor column order is ever relied on, and CRLF or a trailing
newline are still tolerated.

| Menu (primary : secondary) | Proposed `--cut` | Shape | Grain | Range in paste | Columns / series | Unit |
|---|---|---|---|---|---|---|
| Adoption : Overall | `adoption/overall` | long | month (1st) | 2023-01 → 2026-08 | `Date, Series, Adoption rate (%), Monthly change (pp), Yearly change (pp), Census question version`; series `Ramp Overall`, `Census Estimate` (from 2023-09) | % of businesses; pp |
| Adoption : Overall + Models | `adoption/models` | long | month | 2023-01 → 2026-08 | same without the Census column; series `Ramp Overall` + 6 labs (Anthropic, DeepSeek, Google, Mistral AI, OpenAI, xAI) | % of businesses; pp |
| AI spend per employee : Sector | `spend_per_employee/sector` | long | month | 2023-09 → 2026-08 | `Date, Sector, Median (USD / employee / month)`; 8 sectors, appearing over time | USD per employee per month (median) |
| AI share of business spend : Overall | `spend_share/overall` | **wide** | month | 2023-07 → 2026-08 | `Date`, `AI share of business spend (%)` (overall), then 20 sector columns named `<sector> (%)` | % of spend, full float precision |
| Adoption : Sector | `adoption/sector` | long | month | 2023-01 → 2026-08 | `Date, Sector, Adoption rate (%), Monthly change (pp)` (no yearly change); **7 sectors**, all in one paste (no picker), no gaps | % of businesses; pp |
| Adoption : Business size | `adoption/size` | long | month | 2023-01 → 2026-08 | `Date, Business size, Adoption rate (%), Monthly change (pp)`; Large, Medium, Small | % of businesses; pp |
| AI spend per employee : Overall | `spend_per_employee/overall` | **wide** | month | 2023-09 → 2026-08 | `Date, Median (USD / employee / month), Top 10% (…), Top 1% (…)`; no empty cells | USD per employee per month |
| AI spend per employee : Business size | `spend_per_employee/size` | long | month | 2023-09 → 2026-08 | `Date, Business size, Median (USD / employee / month)`; 3 sizes | USD per employee per month (median) |
| Token volume : By model maker | `token_volume/maker` | **wide** | week (Sunday ending a Mon–Sun week) | 2025-01-12 → 2026-09-27 | `Date` + 14 makers (OpenAI, Anthropic, xAI, Google, Cursor, Moonshot, Z.ai, DeepSeek, Amazon, Meta, Alibaba, Mistral, NVIDIA, MiniMax) | **index: 100 = the largest single cell in the chart** (here OpenAI, 2026-09-27) |
| Token spend : By model maker | `token_spend/maker` | **wide** | week (as volume) | 2025-01-12 → 2026-09-27 | the same 14 makers, **in a different column order** | index, same rule (100 = Anthropic, 2026-08-02; the latest week is below 100 for every maker) |
| Token prices : Blended / Input / Output | `token_price/blended`, `/input`, `/output` | **wide** | day | 2025-01-07 → 2026-09-29 (631 rows each) | `Date, OpenAI & Anthropic, OpenAI, Anthropic`, **the same header for all three**, different data | USD per million tokens (Ramp: total dollars paid ÷ total tokens bought, weighted by volume) |

**Full menu (read from the page, 2026-10-07).** Selection is reflected in the URL (`#adoption#overall`,
`?metric=token-volume&detail=maker&mode=volume`, …), which the import records as the cut's page URL.

| Group | Primary | Secondary | Chart subtitle | Pasted? |
|---|---|---|---|---|
| Economic indicators | Adoption | Overall · Overall + Models · Sector · Business size · Geographies | "Share of businesses with spending on AI models, subscriptions, tokens, and APIs" | all but Geographies |
| | AI spend per employee | Overall (Median, Top 10%, Top 1%) · Business size · Sector · State · Financing status · Filter mode | "Monthly AI spend per employee" (Business size: "Median monthly AI spend per employee by business size") | Overall, Business size, Sector |
| | AI share of business spend | Overall (overall + every sector) · Sector (one sector, picker) | "AI share of business spend excluding payroll" | Overall |
| Tokenomics | Token volume | By model maker · By model; toggle Volumes / Shares | "Total token usage by businesses, indexed" ("…by businesses" in Shares) | By model maker (Volumes; Shares header only) |
| | Token spend | By model maker · By model; toggle Volumes / Shares | "Total token spend by businesses, indexed" | By model maker (Volumes) |
| | Token prices | Blended · Input · Output | "Price per million tokens" | all three |

Chart titles: "Ramp AI Index" (economic indicators), "Top AI Models" (token volume and spend), "AI
Token Price Tracker". The token views also show a leaderboard of the latest complete week ("Sep 21,
2026 – Sep 27, 2026", rank change against four weeks earlier), which is not imported.

Source lines under the charts (verbatim):
- Adoption : Overall: "Source: Ramp AI Index, business spend data from Ramp includes corporate card
  and invoice / ACH payments. Census estimate from Census Business Trends and Outlook Survey." The
  Sector and Business size views drop the Census sentence.
- Spend per employee, share of business spend: "Source: Ramp AI Index, business spend data from Ramp
  includes corporate card and invoice / ACH payments. AI spend includes LLM subscriptions, coding
  agent subscriptions, API tokens, and GPU cloud and infrastructure spend."
- Token volume, spend, prices: "Source: Ramp AI Index, data from Ramp AI Token Spend Management.
  Includes model-attributed API spend from connected AI providers."

So the token views come from a **different population**: Ramp customers who connected their AI
provider accounts to Ramp's token-spend product. They are not the card and bill-pay sample behind
adoption. The page's methodology section says these customers are not representative of Ramp's
total AI spend volume, though results are "directionally similar". Marts keep the two apart
(`dataset: spend | tokens`), and analyses must not mix their denominators.

Findings that shape the design:

- **The paste does not name its view.** Nothing in the text says which menu choice produced it,
  and views do share headers: Token prices Blended, Input and Output have identical headers and
  different data. So the cut is **declared by the author** (`--cut`), never guessed, and checked
  against the expected header **where the header can tell views apart**. It cannot for two groups:
  the three price views (same header), and Token volume vs Token spend (same 14 maker columns in a
  different order, and columns are matched by name). Both groups get data checks in §4
  (`ramp_price_check`, `ramp_token_check`) instead. What those checks can miss is the residual risk,
  stated in `SOURCE.md`.
- **Every paste is the full history** of its view, so one import per view per month loses nothing
  except intermediate revisions.
- **Revised in place.** Ramp writes that it "revised up July spending … after additional July
  transactions entered our dataset" (September 2026 report). The token-price figures quoted in that
  report ("$0.68 as of this week", "March peak of $1.15") match none of the three pasted series on
  those dates, so values or definitions change after publication. The spend-per-employee chart now
  peaks near $8K in July for the top 1%, which matches the revision. → `revisions: revised`,
  **Latest-only**, like Epoch and OpenRouter rankings.
- **The token index re-bases whenever a new peak appears.** The chart's (i) tooltip ("About the
  token index") says 100 is "the peak for any single series in the chart", and stacked bars can
  exceed 100. In Token volume that cell is OpenAI's latest week; in Token spend it is Anthropic in
  the week of 2026-08-02. Each new peak rescales the whole series, so index levels from two vintages
  are not comparable. **Shares within a week are unaffected** (they are ratios), so marts publish
  shares and keep the index only as raw. (The volume chart's tooltip repeats the spend text,
  including the words "Token spend".) The page's Shares toggle pastes fractions that sum to 1; it is
  not imported, since shares are computed from Volumes.
- **Weeks:** a token-week date is the Sunday that **ends** a Monday–Sunday week (the leaderboard's
  "Sep 21 – Sep 27, 2026" is the paste's 2026-09-27).
- **Ramp's adoption view carries a Census series.** `Census Estimate` is BTOS as Ramp restates it
  (monthly, apparently averaged from biweekly waves, e.g. `17.5667`), with a **break in question
  wording** in November 2025 (`pre_`/`post_nov_2025_wording_change`; the level jumps from 9.95 to
  17.3) and an all-empty row for 2025-10. It is a different source inside this one; see §6.
- **Artefacts:** the first month has `Monthly change` `0`, not empty (2023-01, every series);
  vendor rows never carry a yearly change; `Ramp Overall` appears in both adoption views and must
  agree within one import day.
- **Sectors differ by view.** Adoption : Sector has 7 sectors for every month. Spend per
  employee : Sector has 8 (those 7 plus Professional, scientific, and technical services), added as
  they appear (Construction from 2025-01, Retail from 2024-11, Accommodation from 2026-01, assumed to
  be sample thresholds). The spend-share view has all 20. None of the imported views has a picker
  (only AI share : Sector does, and it is not imported).
- **Business sizes** are Large, Medium and Small. The page gives no employee thresholds, so they
  cannot be mapped to BTOS size classes without a definition (§6).
- **Labels:** Ramp's sector names are shortened NAICS 2-digit titles ("Technology and media",
  "Retail", "Health care"); maker names differ between views ("Mistral AI" vs "Mistral");
  **Cursor** is a model maker in token volume (its own models), and there is no `cursor` vendor yet.

**Terms.** No licence was found for the data. The methodology page and Ramp's posts say Ramp "does
not license this data, but provides non-exclusive, opt-in, aggregated data to the public" and that
"Ramp data has always been free". The AI Index page renders client-side, so a plain fetch sees no
content; the menu, source lines and methodology were read from the page by hand, and the visible
page has no licence, "cite as", publication-schedule or revisions text (its collapsed "Historical
data" section was not opened). → `redistribution: unknown` (treated as **forbidden**: raw data is never
committed, inlined in `blog_html` or written to `data.json`), `derived_charts:
allowed-with-attribution` (author policy 2026-10-05). The page credits every chart as "Source: Ramp
AI Index" (source lines above), so the footer attribution is `"Ramp AI Index
(ramp.com/data/ai-index), as of {as_of}"`. A chart that shows Ramp's Census series must also credit
the Census Bureau's BTOS, as Ramp does; §6 keeps that series out of charts anyway. The sample is Ramp customers (card and bill-pay transactions, 70,000+ US businesses
now, 30,000+ in the original methodology note), which skews early-adopter; free tools and personal
accounts are invisible.

## Design

### 1. Core: manual input for `cachereg fetch` (one-time, generic)

PLAN §4.2 says adding a source must not edit core. This does, once, because `fetch` today calls
`fetch(full=...)` with no input channel (`cli.py`). The change is generic (nothing Ramp-specific in
core) and was anticipated in PLAN #8 ("same adapter, local file instead of HTTP; no new command").

- **Registry:** optional field `input: api | manual` (default `api`) in `config/sources.yaml`,
  validated in `load_sources`.
- **CLI:** `cachereg fetch <one source> (--from-clipboard | --from-file PATH) [--cut NAME]`.
  - Allowed only with exactly one source id whose `input` is `manual`; otherwise a clear error.
  - `--from-clipboard` runs `pbpaste` (macOS; no new dependency) through one small function in
    core (`core/manual.py: read_clipboard() -> bytes`), which the tests patch; CI on Linux never
    calls `pbpaste`. Elsewhere, or when the clipboard
    is empty, it errors and suggests `--from-file`. Input over 10 MB is refused.
  - The adapter receives `fetch(full=False, manual=ManualInput(body: bytes, via: "clipboard" |
    "file", cut: str | None))`. Sources without manual input keep their signature untouched.
- **`fetch` with no ids and `fetch --due`** skip manual sources with a `manual` line (`manual
  ramp_ai_index  due <date>; import with --from-clipboard --cut …`). It is never a failure, so the
  launchd agent's exit code still means a real failure. `status` shows the cadence and next due date
  as for any source.
- **Manifest:** the request entry records the public page URL, `"via": "clipboard" | "file"`, the
  cut and `status: null`. It **never records the file path** (it would be an absolute home path,
  PLAN §4.4); a schema test checks this.
- **Unique fetch ids (store):** `fetch_id` has one-second resolution and `RawFetch.write()` refuses
  an existing folder, so two imports in the same second (a scripted `--from-file` loop) would
  collide and the second would fail. `write()` therefore moves `fetched_at` forward one second at a
  time until the folder name is free (at most a few seconds; the fetch id format, sorting and every
  reader stay unchanged). This applies to every source, and is harmless for them because API fetches
  never finish within the same second. Tested with two back-to-back writes.
- **Rejected alternative:** an inbox folder (`data/inbox/ramp_ai_index/*.tsv`) read by a plain
  `fetch` needs no core change but leaves `--due` unable to tell "nothing to import" from "failed",
  and it is not the command the PLAN promised.

### 2. Source `ramp_ai_index` (`src/cachereg/sources/ramp_ai_index/`)

- `cuts.py`: the cut registry, one entry per view: id, menu label, shape (`long` | `wide`), grain
  (`month` | `week` | `day`), unit, and the header rule. **Long cuts require the exact header.
  Wide cuts are matched by column name, never position:** `Date` first, the cut's named anchor
  columns present (`AI share of business spend (%)`; the three `… (USD / employee / month)`;
  `OpenAI`, `Anthropic`), and any other column matching the cut's pattern (spend share: ends in
  ` (%)`). New makers or sectors appear over time and are accepted. Adding a view = one entry + one
  fixture; no core change.
- **Cuts in this build (13):** `adoption/overall`, `adoption/models`, `adoption/sector`,
  `adoption/size`, `spend_per_employee/overall`, `spend_per_employee/sector`,
  `spend_per_employee/size`, `spend_share/overall`, `token_volume/maker`, `token_spend/maker`,
  `token_price/blended`, `token_price/input`, `token_price/output`. Later, when an analysis needs
  them: Geographies, State, Financing status, Filter mode, and the By model views (need a Ramp model
  alias in `models.yaml`). Not imported: the Shares toggle (computed from Volumes) and AI share :
  Sector (one sector at a time, already inside Overall).
- **Monthly routine:** 13 pastes. Running the import without `--cut` (or with an unknown one) prints
  every cut with its menu path and page URL, in order, so the author can work down the list. No extra
  CLI option is needed.
- `fetch.py`: decode UTF-8 (strip a BOM, normalise CRLF, tolerate a trailing newline), parse with the
  stdlib `csv` module (tab dialect), validate fully **before** anything is written: header rule; ISO
  dates on the cut's grain (1st of month, Sundays, any day); finite numbers or empty; no duplicate
  (date, series) key; at least one row. Then one raw file, `<cut with / → __>.tsv`, stored **byte
  for byte as received**. Vintage: `{kind: "content", value: sha256, cut, first_period,
  last_period}`.
  - **Wrong-click guard:** if the bytes equal the latest stored import of **any other cut**, the
    fetch is refused ("clipboard unchanged since the <cut> import — click 'Get the data' again").
    Re-importing an unchanged view of the *same* cut is stored (it is evidence of a check and
    resets `--due`).
  - Unknown `--cut` → error listing the known cuts. A missing `--cut` is an error (no guessing).
- `stage.py`: all imports kept, each row tagged with `cut`, `fetch_id`, `fetched_at`:
  - `adoption`: month, `series_kind` (`overall` | `vendor` | `census` | `sector` | `size`),
    `series_label`, `vendor_id` (vendors only), `naics` (sectors only), `adoption_pct`, `mom_pp`,
    `yoy_pp` (null where the view has none), `census_question_version`. The first month's `mom_pp`
    becomes null.
  - `spend_per_employee`: month, `dimension` (`overall` | `sector` | `size`), `group_label`,
    `naics` (sectors only), `statistic` (`median` | `top_10pct` | `top_1pct`, as Ramp labels them),
    `usd_per_employee_month`.
  - `spend_share`: unpivoted: month, `group` (`overall` | `sector`), `sector_label`, `naics`,
    `ai_share_pct`.
  - `token_index`: week (the Sunday ending it), `measure` (`volume` | `spend`), `maker_label`,
    `vendor_id`, `index_value` (empty → null, not 0).
  - `token_price`: day, `price_kind` (`blended` | `input` | `output`), `series_label`
    (`OpenAI & Anthropic` | `OpenAI` | `Anthropic`), `vendor_id` (null for the combined series),
    `usd_per_mtok`.
  - `imports`: fetch_id, cut, via, rows, first/last period, content hash. Rejected rows are
    counted (`_rejected_rows`), as in the other sources.
- Registry entry: `history: native`, `revisions: revised` (→ Latest-only), `redistribution:
  unknown`, `derived_charts: allowed-with-attribution`, `cadence: monthly`, `input: manual`,
  `requires: []`. Monthly because the adoption and spend views are monthly (August data was
  published on 9 September). The token views move daily or weekly, but each paste carries their
  full history, so a monthly import leaves no gaps.

**Vintage selection.** Build's `cutoff` works per source (latest fetch date ≤ as-of, else the
earliest, flagged). Imports are per cut, so the marts choose the **latest import of each cut on or
before the cutoff**. A cut first imported after the cutoff is absent, never silently filled from
another cut, and is reported in **`ramp_cut_coverage`** (built in `060`, used by all three marts):
one row per cut in `cuts.py` (stage writes the registry as table `cuts`, so a never-imported cut
appears too) with `first_import`, `import_used` (latest on or before the cutoff, or null),
`present_at_cutoff`, `last_period`, and `cut_after_cutoff` (true when the cut exists only after the
cutoff). Build's source-level `vintage_after_as_of` flag keeps its meaning (the cutoff itself fell
back to the earliest fetch date); the per-cut gaps live in this table.

### 3. Entities

- `vendors.yaml`: add `aliases.ramp` (`OpenAI`, `Anthropic`, `Google`, `xAI`, `DeepSeek`,
  `Mistral AI` and `Mistral`, `Moonshot`, `Z.ai`, `Amazon`, `Meta`, `Alibaba`, `NVIDIA`,
  `MiniMax`) and a new vendor **`cursor`** (Anysphere; `open_weights: false`, `hq: US`). An
  unknown label stages with a null `vendor_id` and is reported in coverage, not dropped.
- New `config/entities/sectors.yaml`: Ramp sector label → NAICS 2-digit code and title (the
  20 labels in the spend-share view), so (c) can join BTOS by NAICS. **"Technology and media" → 51
  (Information)** is an assumption to confirm (it may include parts of 54); it is marked as such in
  the file and the mart.

### 4. Marts

- `060_ramp_adoption` (inputs: `ramp_ai_index`): monthly share of US businesses (in Ramp's sample)
  paying for AI, overall, per lab, per sector (NAICS) and per size, from the latest import of each
  cut. **The overall series comes from `adoption/overall` only**; the `Ramp Overall` rows inside
  `adoption/models` are never emitted as series. They feed `ramp_overall_check` (month, both values,
  difference), which reports any month where the two imports disagree (expected when they were
  imported on different days and Ramp revised in between). The vendor series come from
  `adoption/models` only. Per-month vendor rank. Vendor shares do **not** sum to the overall share (firms pay several labs); the mart
  says so. Ramp's Census series
  stays in its own table `ramp_census_restated` with the wording-change flag, never joined across
  the break (§6). Serves **(e) lens 2** and the Ramp side of **(c)**.
- `061_ramp_spend` (inputs: `ramp_ai_index`): AI spend per employee (median, top 10%, top 1%
  overall; median by sector and by size) and AI share of business spend overall and by sector,
  keyed by NAICS. Flags months where a sector first appears. Serves **(c)** (spend intensity as a second Ramp lens next to adoption).
- `062_ramp_tokens` (inputs: `ramp_ai_index`): weekly **share of tokens and of token spend by
  lab** (index ÷ week total, which re-basing does not change) and daily blended, input and output
  price per lab, plus **`ramp_price_check`**: per day and series, whether `input ≤ blended ≤ output`
  holds (blended is a token-weighted mix of input and output, so it should) and whether any two of
  the three series are identical over the whole import. Rows that fail are reported, not dropped:
  they point to a pasted-under-the-wrong-cut import (re-import it) or to a definition change on
  Ramp's side. **`ramp_token_check`**: spend share ÷ volume share per lab and week is proportional to
  that lab's realised price, so the implied Anthropic : OpenAI price ratio
  `(spend_A/vol_A)/(spend_O/vol_O)` is compared with the same ratio from `token_price/blended`
  (weekly mean). A volume↔spend swap inverts the implied ratio; weeks where the two ratios fall on
  opposite sides of 1 while the price ratio is clearly away from 1 (outside 0.8–1.25) are reported.
  The check is blind in weeks where the two labs' prices are close, which is the stated residual
  risk. The
  raw index is not carried into the mart. Ramp's token-spend share is the closest match in the repo to
  OpenRouter's estimated $ share (both are API spend by lab, in different populations). Whether (e)
  uses it is decided when (e) is built; this plan only provides the mart.

### 5. Tests (synthetic fixtures only, `tests/test_ramp_ai_index.py`)

Small invented TSVs in the real shapes (invented labels where the shape allows, invented numbers
always):

- Each cut parses and stages; ascending and descending row order give identical tables, and so
  do two orders of a wide cut's columns.
- The base case is LF with no trailing newline; CRLF, a BOM, a trailing newline and a trailing tab
  are also tolerated. Empty cells → null; scientific notation parses.
- Two price cuts with the same header and different data stage under their declared `price_kind`;
  a synthetic Input pasted as `token_price/output` (and vice versa) shows up in `ramp_price_check`;
  synthetic volume and spend pastes imported under each other's cut show up in `ramp_token_check`.
- Header mismatch for the declared cut, an unknown cut, a missing `--cut`, a duplicate key, a
  non-Sunday week, a non-first-of-month month, a non-numeric value, and an empty paste are each
  refused, with nothing written.
- The wrong-click guard refuses the bytes of another cut's latest import; the same cut's bytes
  are accepted.
- A wide cut with a new maker column is accepted and stages that maker with a null `vendor_id`
  (reported).
- First-month `0` change → null.
- The manifest holds the page URL and `via`, and no local path (`--from-file` from a temp dir).
- CLI: `--from-file` with two sources, with a non-manual source, or with `--due` → error; plain
  `fetch` and `fetch --due` print `manual` for the source and exit 0; `pbpaste` is mocked.
- Marts: the latest import per cut on or before the cutoff wins; a cut imported only after the
  cutoff is absent from the series and shows `present_at_cutoff = false` in `ramp_cut_coverage`;
  a never-imported cut appears there too; `060` emits one overall series per month even when both
  adoption cuts are imported, and `ramp_overall_check` reports a disagreement;
- Store: two writes within one second both land, with distinct, ordered fetch ids; token shares are identical for two vintages that differ only by
  re-basing.
- Registry: an unknown `input` value is rejected.
- Fixtures: the `synthetic_entities` fixture (`tests/conftest.py`) also copies `sectors.yaml`, so
  sector rows stage with NAICS codes in tests.

### 6. Caveats to carry into analyses

- "Share of US businesses in Ramp's sample", never "of US businesses". Ramp customers skew
  towards early adopters, and free tools and personal accounts are invisible.
- Latest-only: a replicator importing later gets revised values. The manifest records each cut's
  import date and content hash.
- **(c) needs BTOS itself (#9).** Ramp's Census series is Ramp's restatement (monthly averages, its
  own handling of the November 2025 wording break and the 2025-10 gap). Use it at most as a
  cross-check of our own BTOS adapter, never as the second lens, and never as one line across the
  wording break.
- (c): Ramp's Large / Medium / Small have no published employee thresholds, so a size comparison
  with BTOS is qualitative unless Ramp defines them. Ramp's 7 adoption sectors are the only ones
  comparable by NAICS.
- (e): Ramp vendor adoption is "share of businesses paying", not spend share. Per the PLAN, it is
  never put on one axis with OpenRouter's estimated $.
- Token volume, spend and price cover only Ramp customers who connected their AI providers to Ramp's
  Token Spend Management, for the labs it lists (Ramp: not representative of its total AI spend). Prices are realised unit values (mix-dependent), not list prices; a falling
  blended price can be a shift in mix.

### 7. Docs to update when built

`SOURCE.md` (all of the above, including the paste format and the import routine); PLAN §2.1 #8 (the
manual route is built, the format and the terms), §4.2 (the one core extension, `input: manual`),
§4.4 table (Ramp Latest-only, per-cut vintages), §4.5 (`--due` prints `manual`), §10 status and open
items.

## Decisions (author review, 2026-10-07)

- Add `cursor` as a vendor (it is a maker in the token views).
- `--cut` is always required and checked against the header; it is never detected.
- The menu and source lines were read from the page by hand. The page renders client-side, so a
  plain HTTP fetch sees no content. A browser may be used for exploration (author, 2026-10-07); the
  pipeline itself never drives a browser (PLAN §1: no web scraping).
- **Recurring pulls stay manual (paste or file) until a Data Partner key exists.** Nothing about
  the import needs a browser beyond the author's own click. Not pursued: driving the click with a
  browser agent (needs a running, signed-in Chrome, so it cannot run under launchd, and it is the
  scraping PLAN §1 excludes), and calling whatever internal endpoint the page loads its data from
  (undocumented, unlicensed, can change without notice; Ramp's supported route is the Data API).
- Not yet checked: whether the Data API's `adoption`, `sectors` and `sizes` match the page's
  adoption views, and whether the API has the token views at all. Check this with the first key.

## Resolved by the page read (2026-10-07)

The four missing headers, the index base, the week convention and the absence of pickers are now in
"What was measured". Still unknown, none blocking the build: the publication schedule and revisions
policy (no text on the page; revisions are confirmed by Ramp's own report), what "Top 10%" and
"Top 1%" measure exactly (a percentile or the mean of that group), the size thresholds, and the
contents of the page's collapsed "Historical data" section.

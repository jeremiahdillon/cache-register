# Plan: the curated disclosures dataset (Tier-1 "our" dataset; lens 3 of analysis (e))

Status: BUILT · 2026-10-09 (planned 2026-10-08; adversarial review converged 2026-10-09)

**As built (differences from the design below):** a second figure from one statement takes the id suffix
`-2`, `-3` …; `fetch` also refuses a copy that edits or drops a row of the newest stored copy (stage still
checks every older copy); an unchanged file stores nothing (`fetch` returns None, the CLI prints `same`).
`disclosure_series` is ordered by the period measured, not by statement date, so a retrospective figure
sits where it belongs (Anthropic's "$9B at the end of 2025", stated in April 2026, precedes February's
$14B). A new entity `_openrouter` (the platform, no aliases) carries OpenRouter's figure. Seed: 50 rows
(45 primary). Beyond the plan's exclusions, CNBC's $13B OpenAI ARR (attribution unconfirmed) and
TechCrunch's "300 million users in December 2024" (not stated as weekly; original not found) are left out;
the OpenRouter row is the stated 100 trillion tokens per month (the candidate's 25 trillion per week was
TechCrunch's arithmetic, which the validator caught); Meta's Q3 2024 row quotes the Q&A as planned.

## Goal

1. A hand-curated, committed, **CC BY 4.0** dataset of dated public AI-market figures (PLAN §2.2, §2.3):
   tokens processed, API throughput, revenue run-rates, active users, and similar, one row per stated
   figure, each cited to the page it came from with a short verbatim quote.
2. Source `curated_disclosures` that validates the file and feeds it through the normal pipeline
   (raw → staged → mart), with **Exact** as-of behaviour: a past as-of sees only the rows the dataset
   held then.
3. A seed of verified rows for the metric families analysis (e) and later analyses need.

Done when the file validates in CI, the source builds locally and the seed rows are in. No analysis here.

## What was measured (2026-10-08: a research pass over company posts, filings and transcripts)

67 candidate rows (statements Aug 2024 → Sep 2026; periods from May 2024), 66 with the quote checked against the page text; spot-checked by
hand: Google Q2 2026 remarks (22B tokens/min, 950M Gemini MAU), Google I/O 2025 (9.7T, 480T, 400M),
Anthropic Series H ($47B run-rate). Candidates are kept outside the repo until the decisions below.

| Family | Points | Sources | Notes |
|---|---|---|---|
| Google tokens processed per month, all surfaces | 5 (9.7T May 2024 → 3.2 quadrillion May 2026) | blog.google keynotes, earnings remarks | scope wording drifts ("products and APIs" → "surfaces"); the 9.7T is restated twice; "≈1 quadrillion" in press is third-party arithmetic |
| Google API tokens per minute | 5 (7B Q3 2025 → 22B Q2 2026) | earnings remarks, Cloud Next, I/O | wording changes at 19B ("first-party models via direct API use" → "our model APIs"); Google itself compares 22B with 16B, so treated as one series |
| Gemini app MAU | 6 (400M → 950M) | blog.google | clean |
| ChatGPT weekly active users | 10 (200M Aug 2024 → 1.2B Sep 2026) | openai.com, press | the "our products" / "our collective" figures go to `openai_products_weekly_active_users`, not the ChatGPT series |
| OpenAI revenue run-rate / ARR | 5 (+ "$2B revenue per month", Mar 2026) | openai.com (retrospective), CNBC | ARR ≠ recognised revenue; mid-2026 press figures from anonymous sources excluded |
| OpenAI API tokens per minute | 2 distinct (6B Oct 2025, 15B Mar 2026) | DevDay (press), openai.com | |
| OpenAI paying business users | 4, mixed units (users vs seats) | openai.com, press | units differ: two metrics, `paying_business_users` and `chatgpt_business_seats` |
| Anthropic run-rate revenue | 6 company (≈$1B start 2025 → $47B May 2026) + $65B (Bloomberg, Aug 2026) | anthropic.com | two are retrospective; $65B is investor data, not a company statement |
| Microsoft AI business run-rate | $13B (Jan 2025), $37B (Apr 2026); a "$10B next quarter" forecast | earnings transcripts | Microsoft's token totals change unit and scope (100T/quarter, then 500T/year Foundry only, then customer counts): no series |
| Meta AI MAU | 3 (500M → almost 1B, Apr 2025) | transcripts, 8-K | none since |
| Others | Amazon AI run-rate ($15B+, secondary), OpenRouter (~25T tokens/week, secondary) | | no primary figures found for xAI, Mistral, DeepSeek, Vercel |

Traps that shape the design: one company figure restated with different scope words; retrospective
figures (stated later about an earlier period); forecasts ("on track to surpass"); units that change
under one label (users vs seats; ARR vs revenue per month); third-party arithmetic presented as company
figures; transcripts with errors (Meta's Q3 2024 remarks say "more than 500 monthly actives"; the same
transcript's Q&A says "it has over 500 million monthly actives", which is the quote the seed row uses).

## Design

### 1. The file: `config/curated/disclosures.csv` (committed)
One row per **stated figure** (a statement that gives two figures is two rows). Columns (PLAN §2.3's list,
extended where the research showed it was needed):

| Column | Meaning |
|---|---|
| `id` | stable row id, `<entity>-<metric>-<statement_date>[-n]`; never reused |
| `statement_date` | the day the figure was published or said |
| `entity` | a vendor id from `config/entities/vendors.yaml` (validated) |
| `metric` | from the controlled vocabulary (below) |
| `value_as_stated` | the figure exactly as written in the quote (`3.2 quadrillion`, `$20B+`, `seven billion`) |
| `value` | that figure normalised to the metric's unit (`3.2e15`); the validator parses `value_as_stated` and requires it to equal `value` |
| `unit` | fixed by the metric (validated) |
| `qualifier` | `exact` \| `over` \| `about` \| `under` \| `up_to`, mapped from the source's words: `over`, `more than`, `above`, `surpassed`, `crossed`, `+` → `over`; `about`, `approximately`, `roughly`, `~` → `about`; `nearly`, `almost`, `just under` → `under`; `up to` → `up_to`; no qualifier → `exact` |
| `period_start`, `period_end` | what the figure measures (a month, a quarter, "as of" = the statement date) |
| `scope` | the stated scope, short ("across our surfaces", "direct API use by customers") |
| `source_url`, `source_kind` | the page read; `primary` (the company, its filings or official channels) \| `secondary` |
| `source_quote` | verbatim, ≤ 25 words, containing the figure (PLAN §7) |
| `recorded_on` | the day the row was added to the dataset (drives as-of) |
| `supersedes` | id of a row this one corrects (empty otherwise) |
| `notes` | definition caveats, conflicts |

**Controlled vocabulary** `config/curated/metrics.yaml`: each metric's unit, definition and the scopes it
may carry. The seed needs: `tokens_processed_monthly` (Google, all surfaces), `api_tokens_per_minute`,
`revenue_run_rate` (USD per year, annualised ARR or run-rate as stated), `revenue_monthly` (USD per month;
never converted to a run-rate here), `ai_revenue_run_rate` (a company's AI business line, e.g. Microsoft),
`chatgpt_weekly_active_users` (ChatGPT only) and `openai_products_weekly_active_users` ("our products",
"our collective"), `gemini_app_monthly_active_users`, `meta_ai_monthly_active_users`,
`paying_business_users` (people) and `chatgpt_business_seats` (seats), `business_customers`
(organisations). A figure whose scope differs materially (all surfaces vs API
only) gets a different metric, never the same one with a note: one metric is one comparable series.

**Append-only.** A published row is never edited or deleted. A correction is a new row with
`supersedes: <old id>` and its own `recorded_on` (a correction of a correction supersedes the newest one).
The mart filters by **`getvariable('as_of')`, never by the source cutoff** (as `030_capex` filters `filed`):
it shows rows with `recorded_on <= as_of` minus those superseded by a row with `recorded_on <= as_of`.
**Stage reads only the newest stored copy** of the file (a superset of every earlier copy, since rows are
only appended) and checks that every row of each older stored copy appears unchanged in it, failing the
stage otherwise; so `disclosures` holds each `id` once and the build cutoff plays no part. So every past as-of is reproducible from the file alone (**Exact** by `recorded_on`), including
for a replicator whose only fetch is today; a row recorded today about an old period is invisible to a
past as-of, by design. Git history is an audit trail, not the mechanism.

**Enforcing append-only.** A function `check_append_only(old_csv, new_csv)` (no edited or removed `id`,
no change to any field of an existing row) runs in **the pre-push hook** against the file at the pushed
range's base (`git show $remote_sha:config/curated/disclosures.csv`; skipped when the file does not exist
there, e.g. the commit that introduces it, or on a new branch) and in **CI** against
`github.event.before` (skipped when that is all zeros or lacks the file). CI's checkout equals the pushed
head, so comparing with `origin/main` there would be vacuous. Unit tests cover the function on synthetic
before/after CSVs.

### 2. Source `curated_disclosures` (`src/cachereg/sources/curated_disclosures/`)
- **`fetch.py`:** reads the committed file (no network), validates it fully, and stores it in raw as is.
  Vintage `{kind: "content", value: sha256, window: [min recorded_on, max recorded_on]}`, which the manifest
  records as the Exact vintage (stage itself always reads the newest copy). `cadence: weekly` with `fetch --due` (a no-op copy when unchanged is skipped).
- **Validation** (shared by fetch and the test): required columns; unique `id`; dates ISO and
  `period_start ≤ period_end`, `statement_date ≤ recorded_on`; `entity` in `vendors.yaml`; `metric` in
  the vocabulary and `unit` matching it; `value` finite and > 0; `qualifier` in its set; `source_url` https;
  `source_quote` non-empty, ≤ 25 words and containing `value_as_stated` (case-insensitive, after
  normalising whitespace and curly quotes); `value_as_stated` parses (digits with optional `$`, `,`, `+`,
  a B/M/T/K suffix or a multiplier word `thousand`…`quadrillion`; or number words from a small map such as
  `seven`) to exactly `value` in the metric's unit, compared as decimals (`Decimal`, never floats: `8.3 × 10¹²` is not exact in binary). Deliberately simple: it catches a quote pasted against
  the wrong row or a mis-normalised value, not a misread source (that is the reviewer's job); `supersedes` names an earlier row.
- **`stage.py`:** `disclosures` (typed, from the newest stored copy only, after the older-copies check
  above), `metrics` (the vocabulary).
- **Registry:** `history: curated`, `revisions: append-only` (→ Exact), `redistribution:
  allowed-with-attribution` and `derived_charts: allowed-with-attribution` (ours, but CC BY 4.0 requires
  credit, as for Epoch; the quotes are short factual excerpts, PLAN §7, never inlined in HTML), attribution `"Cache Register curated disclosures (CC BY 4.0), from the cited
  company statements, as of {as_of}"`. A chart showing a row should also name the company source in its
  notes; the analysis does that.

### 3. Mart `080_disclosures` (inputs: `curated_disclosures`)
- `disclosures`: rows visible at as-of (recorded on or before, not superseded), with the vendor name,
  metric definition and unit.
- `disclosure_series`: per entity × metric, the rows in statement order with the change since the
  previous figure and the days between (descriptive; no interpolation, no unit conversion, e.g. tokens per
  minute are never turned into tokens per month here: that is a stated derivation an analysis may make).
- `disclosure_coverage`: per metric, entities, count, first and last statement, share primary.

### 4. Tests (`tests/test_curated_disclosures.py`)
Synthetic CSVs for every validation rule (one failing row each); supersession at two as-ofs; the Exact
cutoff (a row recorded after as-of is invisible). **Plus a test that validates the real committed file**:
it is our own data, not a recorded third-party API response, so CLAUDE.md's synthetic-only rule (about
licensing) does not apply. `check_append_only` has synthetic before/after tests (edited row, removed row,
added row, first introduction of the file); the real comparison runs in the pre-push hook and CI as above.
Stage: two stored copies where the newer adds a row stage each `id` once; a newer copy that changes a row
fails the stage.

### 5. Adding rows (the routine)
Read the source page; copy the quote; fill a row with `recorded_on` = today; run `cachereg fetch
curated_disclosures` (validates) and `make check`. Corrections are new rows. Secondary sources only when no
primary exists, marked so.

### 6. Caveats to carry into analyses
- Self-reported, unaudited, chosen by the company (figures appear when they flatter); definitions shift
  between statements (surfaces vs API; "over" vs exact); a series is only as regular as the company's
  statements.
- Token counts use each company's tokenizer and scope; Google's monthly tokens are not comparable to
  OpenRouter's or Vercel's.
- Run-rates are annualised from a recent period the company picks.

### 7. Docs to update when built
`SOURCE.md`; `config/sources.yaml`; PLAN §2.2/§2.3 (built, the columns as extended), §3 layout
(`config/curated/metrics.yaml`), §4.4 (curated → Exact by `recorded_on`), §10.

## Seed (proposed)
About 50 rows: every **primary** row in the families above that passes validation, one row per
statement-of-a-period (a later restatement of the same period is kept only if its value differs, and then
as its own row with a note). Retrospective figures are rows with the earlier `period_*` and the later
`statement_date`. Secondary rows only where no primary exists (ChatGPT WAU 2024–2025, OpenAI ARR mid-2025,
OpenAI API 6B/min, OpenRouter tokens), marked `secondary`. Excluded from the seed: forecasts, investor or
anonymous-source figures (Anthropic $65B, mid-2026 OpenAI ARR reports), third-party arithmetic, the
unverified Amazon quote, Microsoft's token totals (no comparable series), retail-segment tokens.

## Decisions (author review, 2026-10-08: the recommendations, as proposed)

1. **Secondary sources** are allowed only where no primary exists, marked `secondary`.
2. **Scope drift:** one metric when the company itself compares the figures (Google's 22B tokens/min "up
   from 16 billion"), with the wording in `scope`; otherwise a separate metric.
3. **Forecasts and investor- or anonymous-source figures are excluded.**
4. **Append-only** rows with `supersedes`; as-of by `recorded_on` (Exact).

Evidence for the seed (candidate rows, extracted page texts and transcripts, the research scripts) is kept
locally, never committed, under `data/research/2026-10-08-disclosures-vercel/disclosures/`
(`seed_rows.csv`). openai.com blocks automated fetches; those pages were read in the author's browser
during research; the author approved this (2026-10-09), so those rows are kept, and pages may be read
via the browser when needed.

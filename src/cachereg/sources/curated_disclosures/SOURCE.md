# Curated disclosures (`curated_disclosures`)

**What:** our own hand-curated dataset of dated public AI-market figures (tokens processed, API
throughput, revenue run-rates, active users, business customers), one row per stated figure, each
cited to the page it came from with a short verbatim quote. Design:
`docs/plans/2026-10-08-curated-disclosures.md`.
**Files:** `config/curated/disclosures.csv` (the rows) and `config/curated/metrics.yaml` (the
controlled vocabulary: each metric's unit, definition and the scope it may carry).
**Auth / network:** none; `fetch` validates the committed files and copies them into raw.
**License:** CC BY 4.0 (ours). Credit: "Cache Register curated disclosures, from the cited company statements,
CC BY 4.0, as of {as_of}". A chart showing a row also names the company source in its notes.
The quotes are short factual excerpts (≤ 25 words, PLAN §7) and are never inlined in HTML.
**Seeded:** 2026-10-09 (50 rows recorded that day).

## Columns
`id` (`<entity>-<metric>-<statement_date>`, then `-2`, `-3` … for further figures from one statement;
never reused), `statement_date` (published or said), `entity` (a vendor id in
`config/entities/vendors.yaml`), `metric`, `value_as_stated` (the figure exactly as in the quote),
`value` (that figure in the metric's unit), `unit`, `qualifier`, `period_start` / `period_end` (what the
figure measures; "as of" = the statement date), `scope` (the stated scope, short), `source_url`,
`source_kind` (`primary`: the company, its filings or official channels; `secondary`: press), `source_quote`,
`recorded_on` (the day the row was added: drives as-of), `supersedes` (the id of a row this one
corrects), `notes`.

Qualifiers map the source's words: over, more than, above, surpassed, crossed, `+` → `over`; about,
approximately, roughly, ~ → `about`; nearly, almost, just under → `under`; up to → `up_to`; none → `exact`.

## Classification
- history: curated · revisions: append-only → **Exact by `recorded_on`**
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution

## Rules (enforced)
- **Validation** (`dataset.validate`, run by `fetch`, `stage` and the tests): exact columns; unique
  ids of the form above; ISO dates with `period_start ≤ period_end` and `statement_date ≤ recorded_on`;
  entity in `vendors.yaml`; metric in the vocabulary and unit matching it; value finite and > 0;
  qualifier and source kind in their sets; https URL; quote ≤ 25 words and containing
  `value_as_stated` (case-insensitive, whitespace and curly quotes normalised); `value_as_stated`
  parses exactly (decimal arithmetic) to `value` (digits with `$`, `,`, `+`, a K/M/B/T suffix or a
  multiplier word up to quadrillion, or a number word such as `six`); a `$` only on usd units; a
  trailing `+` only with `over`; `supersedes` names an earlier-recorded row, superseded at most once.
  It catches a quote pasted against the wrong row or a mis-normalised value, not a misread source.
- **Append-only:** a published row is never edited or deleted; a correction is a new row with
  `supersedes` and its own `recorded_on` (a correction of a correction supersedes the newest one).
  `check_append_only` runs in the pre-push hook (against the file at the remote's commit) and in CI
  (against `github.event.before`); both skip when the base lacks the file. `fetch` refuses a copy that
  edits or drops a row of the newest stored copy, and `stage` checks every older stored copy against
  the newest.
- **As-of:** stage reads only the newest stored copy; mart 080 shows rows with `recorded_on ≤ as_of`,
  minus those superseded by a row recorded by then. A row recorded today about an old period is
  invisible to a past as-of, by design. Git history is an audit trail, not the mechanism.

## Adding rows
Read the source page; copy the quote; fill a row with `recorded_on` = today; run `cachereg fetch
curated_disclosures` (validates; an unchanged file stores nothing) and `make check`. Corrections are new
rows. Secondary sources only when no primary exists, marked so. Excluded: forecasts ("on track to"),
investor or anonymous-source figures, third-party arithmetic (e.g. a monthly figure × 12, or tokens per
month ÷ 4), segment figures under an all-surfaces metric. openai.com blocks automated fetches; its
pages may be read in the author's browser (approved 2026-10-09).

## Seed (2026-10-09)
50 rows from a research pass of 2026-10-08 (67 candidates, quotes checked against the page texts; the
evidence stays local, never committed). Primary rows for every family, one row per statement of a period
(a restatement with the same value is not a row; it is named in `notes`). Secondary rows only where no
primary was found: ChatGPT weekly users 2024–25 (Axios, TechCrunch, tech.eu), OpenAI ARR June 2025
(CNBC, confirmed by a spokesperson), OpenAI API tokens per minute at DevDay 2025, OpenAI paying
enterprise users (Feb 2025), OpenRouter tokens per month (entity `_openrouter`, the platform).
Left out: forecasts (Microsoft's "$10 billion next quarter", Foundry customers "on track" to a trillion
tokens), Bloomberg-reported investor figures (Anthropic $65B), CNBC's $13B OpenAI ARR (attribution
unconfirmed), TechCrunch's "300 million users in December 2024" (not stated as weekly; original not
found), the unverified Amazon quote, Microsoft's token totals (unit and scope change every time: no
series), Google's retail-segment tokens, Claude Code's run-rate and Microsoft's Foundry customer count
(no metric yet; add one to `metrics.yaml` with its rows if wanted).

## Caveats (carry into analyses)
- Self-reported, unaudited and chosen by the company (figures appear when they flatter); definitions
  shift between statements (surfaces vs API; "over" vs exact); a series is only as regular as the
  company's statements.
- Token counts use each company's tokenizer and scope; Google's monthly tokens are not comparable to
  OpenRouter's or Vercel's.
- Run-rates are annualised from a recent period the company picks; ARR is not recognised revenue.

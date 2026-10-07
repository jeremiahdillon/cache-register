# Plan: OpenRouter app rankings and session cost (two Phase 2 sources)

Status: APPROVED · 2026-10-07 (decisions below; not built yet)

## Goal

1. Add source `openrouter_apps`: `GET /api/v1/datasets/app-rankings`, weekly top-200 public apps
   by tokens on OpenRouter since 2025-01-06, Latest-only (like `openrouter_rankings`).
2. Add source `openrouter_session_cost`: `GET /api/v1/datasets/session-cost`, median USD per
   session by harness × model × turn range. **It is a snapshot, not native history** (see below),
   so it is Author-only and accrues history from our first fetch.
3. Marts that give app token volume per week (with OpenRouter's total as the denominator) and
   session cost per snapshot with canonical model ids. Done when both work on synthetic fixtures
   in CI and on real data locally. No analysis is built here.

Out of scope: `sort=trending` (OpenRouter's growth formula needs app volumes outside the top
200, so it cannot be rebuilt or checked; popular history is enough to compute our own growth);
monthly or daily app windows (decision 2); an analysis or exploration; `entities suggest`
for the new sources (core change, backlog); new dependencies (none needed).

## What was measured (2026-10-07: docs plus four live requests; responses not kept)

**Both endpoints.** Any OpenRouter key, 30 req/min per key, 500 req/day per account (shared with
`openrouter_rankings`, which uses ~2/day). CC BY 4.0. `meta.version` is `v1` ("field names and
grain are stable for the life of v1"). `meta.as_of` is when the response was *generated*, not a
data revision: two pages of the same session-cost snapshot came back with as_of 32 minutes apart.

**app-rankings** (`openrouter.ai/apps`)
- Parameters: `start_date`, `end_date` (UTC, inclusive; default the 30 days to the last
  completed day; a start before 2025-01-01 is clamped and echoed in `meta.start_date`, an end
  before it is a 400), `sort` (`popular` | `trending`), `category` (4 groups) / `subcategory` (15),
  `limit` 1–100, `offset` 0–100. **So at most ranks 1–200 per window.**
- One row per app for the **whole window**: `rank` (absolute, also with offset), `app_id`
  (int, "stable numeric identifier"), `app_name`, `total_tokens` (decimal string, prompt +
  completion), `total_requests` (int). No per-day breakdown, no `other` row, no category on
  the row (categories exist only as filters), no slug.
- History reaches 2025-01-01: the window 2025-01-01..07 at offset 100 returned ranks 101–200
  (rank 200 ≈ 5.7 M tokens). Week 2026-09-28..10-04: rank 1 ≈ 14.0 T tokens, rank 100 ≈ 25 B.
- Hidden and private apps are excluded and alias apps are merged into the canonical visible app
  **at query time**, so a past window can change when an app is hidden or merged, not only
  when late events arrive. Data comes from a continuously ingested materialized view.
- Required citation: "Source: OpenRouter (openrouter.ai/apps), as of {as_of}."

**session-cost**
- **No date parameters.** Only `app_slug`, `model` (exact permaslug), `turn_range` (`1-turn`,
  `2-9-turns`, `10-49-turns`, `50-plus-turns`), `limit` 1–500, `offset` 0–5000. Each response
  is the current weekly snapshot: `meta.window_days` 30, `meta.window_end_date` 2026-10-04 (a
  Sunday), generated Monday ~07:00 UTC. `window_*` are null when no snapshot is published.
  **PLAN §2.1 #3 is wrong on this** (it says native history from 2025-01-01); consecutive
  snapshots are 30-day windows a week apart, so they overlap by ~23 days.
- Rows: `app_slug`, `app_name`, `turn_range`, `model_permaslug`, `median_session_cost_usd`
  (float). No session counts, no spread, no token counts.
- Current snapshot: **651 cells**, 4 harnesses — `hermes-agent` 366, `claude-code` 143,
  `kilo-code` 73, `codex` 69; 121 permaslugs; turn ranges 1-turn 159, 2-9 199, 10-49 168,
  50+ 125. (app, model, turn) is unique. Values $0.00001–$21.10. No `:free` slugs.
- Sorted by app_slug, turn_range, then cost descending; 500 rows filled page 1 exactly, so the
  default `limit=100` (and even 500) silently truncates.
- Permaslugs use the same convention as rankings-daily (dated, e.g.
  `anthropic/claude-4.5-sonnet-20250929`): 113 of 121 are already `aliases.openrouter` in
  `models.yaml` (633 of 651 cells, 97%; every Claude Code, Codex and Kilo Code cell). The 8
  unmapped ones are Hermes Agent cells for models never in the daily top 50.
- **Identifiers do not join directly**: session-cost has `app_slug`, app-rankings has numeric
  `app_id`. The four harness names match app-rankings names exactly today (all four are in the
  week's top 5: ranks 1, 2, 3, 5), but names are display labels.
- No citation string is given on this page (decision 4).

**Revision behaviour (from our own rankings-daily vintages, no extra requests).** Across five
rankings fetches 2026-10-02..06, only the last one or two days changed between vintages, by at
most 0.005%; older days were identical. app-rankings is presumably the same pipeline, plus the
hide/merge effect above, which we can only see over time: the trailing re-fetch (below) records
it, and the first month of vintages gets a one-off comparison in SOURCE.md.

## Design

### 1. `openrouter_apps`

**Fetch** (`fetch(full, today)`, same shape as `openrouter_rankings`):
- Windows: ISO weeks Monday–Sunday. First week 2025-01-06 (the 2025-01-01..05 stub is skipped,
  matching the wallet-share receipt's start); last week the latest complete one (ends on or
  before `today − 1`).
- Per week: `sort=popular`, `limit=100`, `offset=0`, then `offset=100` only when the first page is
  full → top 200.
- Category tags (decision 1): for the newest week only, one filter request per subcategory (15)
  and per category group (4), each `limit=100`, plus `offset=100` when the first page is full, so
  each filter covers its top 200 (the API maximum), 19–38 requests. **Tags are per app**: an app
  returned by `subcategory=S` carries tag S, an app returned by `category=G` is in group G. No
  subcategory → group table is assumed (the API publishes none); an app can have several of
  each. Apps outside a filter's top 200 that week, and apps that were in the top 200 only in
  earlier weeks but are absent from the newest week's filters, get no tag (`untagged`; caveat).
- Backfill (first run or `--full`): ~91 weeks × 2 + 19–38 ≈ 200–220 requests. Refresh: the
  trailing 5 weeks (10 requests) + 19–38. Requests are spaced 2.1 s apart (30/min); `http.get` already retries
  429 with Retry-After. A backfill takes ~7 minutes and uses ~40% of the day's budget.
- Validation before storing, else the fetch fails and writes nothing: `meta.version == "v1"`;
  `meta.start_date`/`end_date` equal the request (no clamping); `data` a list; ranks contiguous
  from `offset + 1`; `total_tokens` all digits; `app_id` int and unique within the week.
- Files: `apps_{start:%Y%m%d}_{end:%Y%m%d}_o{offset}.json`,
  `tag_{category|subcategory}_{name}_{start:%Y%m%d}_o{offset}.json`. Vintage `{kind: api_as_of, value: max as_of,
  window: [first week start, last week end]}`.
- Cadence **weekly** (a week only exists once it is complete). Registry: `history: native`,
  `revisions: revised` → Latest-only, `redistribution`/`derived_charts:
  allowed-with-attribution`, attribution `"OpenRouter (openrouter.ai/apps), as of {as_of}"`,
  `requires: [OPENROUTER_API_KEY]`.

**Stage** (all vintages kept, as in rankings):
- `weekly`: `week_start` (Date), `week_end`, `rank` (Int64), `app_id` (Int64), `app_name`,
  `total_tokens` (Int64; parsed from the string, rejected if not digits), `total_requests`
  (Int64), `fetch_id`, `fetched_at`, `api_as_of`.
- `tags`: one row per app × filter: `app_id` (Int64), `app_name`, `tag_kind` (`category` |
  `subcategory`), `tag` (String), `rank_in_tag` (Int64), `tag_week_start` (Date), `fetch_id`,
  `fetched_at`.
- `_rejected_rows`.

### 2. `openrouter_session_cost`

**Fetch:**
- One request per `turn_range` (4 requests, `limit=500`). Each is ~125–200 cells today, far from
  500; if one returns exactly 500, it pages with `offset` until a short page (cap 5000 → error).
  Filtering by turn range avoids the unfiltered sort's cost ties at page boundaries.
- Validation: every response has the same non-null `window_end_date` and `window_days` (else the
  snapshot changed mid-fetch: retry the whole fetch once, then fail); `version == "v1"`;
  (app_slug, permaslug, turn_range) unique; every row's `turn_range` equals the filter; cost a
  finite number ≥ 0. A null window (no snapshot published) fails the fetch without storing.
- Files `session_cost_{turn_range}_o{offset}.json`; vintage `{kind: snapshot, value: <window_end_date>,
  window_days, as_of}`.
- Cadence **weekly** (snapshots are weekly; with a 7-day cadence a fetch can lag a snapshot by a
  week but cannot skip one unless OpenRouter skips a week; gaps show as missing `window_end_date`
  weeks in the mart). Registry: `history: snapshot`, `revisions: none` → Author-only,
  `redistribution`/`derived_charts: allowed-with-attribution`, attribution
  `"OpenRouter session cost by harness (openrouter.ai), as of {as_of}"` (decision 4),
  `requires: [OPENROUTER_API_KEY]`.
- An earlier snapshot can never be fetched again, so **the first fetch should run as soon as the
  adapter lands**, and the launchd agent keeps it going.

**Stage** — `cells`: `window_end_date` (Date), `window_days` (Int64), `app_slug`, `app_name`,
`turn_range`, `turn_min`/`turn_max` (Int64; 1/1, 2/9, 10/49, 50/null), `model_permaslug`,
`median_session_cost_usd` (Float64), `fetch_id`, `fetched_at`, `api_as_of`; plus
`_rejected_rows`.

### 3. Entities

- **Models:** session-cost permaslugs join `dim_model_alias` (source `openrouter`) as they are;
  nothing new in `models.yaml` now. Unmapped cells keep `model_id` null and are counted in the
  mart (coverage = share of cells, per harness). Models that matter for an analysis get added by
  hand (`# manual`) until `entities suggest` learns this source (backlog, core change).
- **Apps:** new `config/entities/apps.yaml`, keyed by session-cost `app_slug`: `app_id`
  (app-rankings), `name`, optional `vendor` (id in `vendors.yaml`, for "first-party harness":
  `claude-code` → anthropic, `codex` → openai). Seeded with the four harnesses, ids checked by
  hand against app-rankings. Read by `openrouter_session_cost`'s stage through
  `core.paths.entities_dir()` (as `sec_edgar` reads `tickers.yaml`), which emits a `harnesses`
  table; core is not edited. A slug missing from `apps.yaml` is not an error: the mart leaves its
  `app_id` null and reports it. A test checks that every `vendor` resolves.

### 4. Marts

**`050_openrouter_apps`** (inputs: `openrouter_apps`)
- Vintage selection is **per week, not per row**: for each week, all rows of the latest fetch on
  or before the cutoff that contains that week. (Picking the latest row per app would keep an
  app that a later vintage hid or merged.)
- `or_app_weekly`: `week_start`, `app_id`, `app_name` (as served that week), `rank`,
  `total_tokens`, `total_requests`, `tokens_per_request`, `fetch_id`; `week_start ≤ as_of − 6`.
- `or_app_dim`: `app_id`, latest name, first/last week seen in the top 200, current
  `categories` and `subcategories` as sorted `VARCHAR[]` lists (empty when untagged), from the
  newest tag fetch on or before the cutoff (**current tags applied to all history**: caveat).
- `or_app_category_weekly`: per week × (`tag_kind`, `tag`): tokens, requests and app count of
  the week's top-200 apps carrying that tag. An app is counted under each of its tags, so rows of
  one `tag_kind` can sum to more than the week's total (column `tags_overlap` documents it); an
  `untagged` row per `tag_kind` holds the apps with no tag of that kind.

**`051_openrouter_app_share`** (inputs: `openrouter_apps`, `openrouter_rankings`)
- `or_app_share_weekly`: per week, OpenRouter total tokens (rankings-daily summed Mon–Sun,
  top 50 + `other`, only weeks with all 7 days), the top-200 app sum, `attributed_share`, and per
  app `share_of_openrouter`. Separate from 050 so app-only analyses do not need rankings
  (the 005/010 split).
- Caveat: OpenRouter's total includes traffic not attributed to any app, private apps and the
  tail beyond rank 200, so app shares are lower bounds of "share of OpenRouter traffic" and the
  rest is not "other apps".

**`055_openrouter_session_cost`** (inputs: `openrouter_session_cost`)
- Snapshot per `window_end_date`: rows of the latest fetch for that window among fetches on or
  before the cutoff; only snapshots with `window_end_date ≤ as_of`.
- `or_session_cost`: every snapshot ≤ as_of, with `model_id` (via `dim_model_alias`), `vendor`
  of the model, harness `app_id`/`vendor` (via the stage's `harnesses`), and
  `is_latest_snapshot`.
- `or_session_cost_coverage`: per snapshot × harness: cells, cells with a `model_id`, distinct
  models, turn ranges present.
- Deliberately **no** harness-level averages: the cells are medians with no session counts, so
  they cannot be pooled across models or turn ranges. Comparisons belong at a fixed (model,
  turn range), which analyses do themselves; the mart docstring says so.

Numbering leaves 040s to the price marts; 05x is the OpenRouter app/harness block.

### 5. Tests (synthetic fixtures only)

Fixtures in `conftest.py`: three synthetic apps (`Harness A` id 101, `Chat B` 102, `Writer C` 103),
the existing synthetic permaslugs, harnesses `harness-a` / `harness-b`.

- Fetch (apps): ISO-week windows from 2025-01-06 to the last complete week; refresh plans the
  trailing 5 weeks; second page only when the first is full; clamped `meta.start_date`,
  non-contiguous ranks, non-digit tokens and duplicate `app_id` refused before storing;
  request spacing (clock patched); tag requests only for the newest week, second tag page only
  when the first is full; session-cost page file names unique per offset.
- Fetch (session cost): four turn-range requests; pagination when a page is full and the
  5000 cap; mismatched `window_end_date` between responses retried once then refused; null
  window refused; duplicate cells refused.
- Stage: tokens parsed from strings beyond 2^53; rejected rows counted; turn bounds; harnesses
  table from a synthetic `apps.yaml`.
- Marts: per-week vintage replacement (an app absent from the newer vintage disappears);
  cutoff respects as_of and Latest-only fallback; incomplete current week excluded; share
  denominator only for full rankings weeks; category overlap and `untagged`; session-cost
  snapshot selection by `window_end_date` with a duplicate fetch of the same window;
  unmapped permaslug and unmapped harness counted, not dropped; build refuses session cost for
  an as_of before the first snapshot (existing snapshot-gap rule).
- Pipeline: `make check` slice gains both sources.

### 6. Docs to update when built

PLAN §2.1 #3 (session-cost is a weekly 30-day snapshot, 4 harnesses; app-rankings top 200 per
window), §4.4 table (session-cost under Author-only), §10 status and open items; a `SOURCE.md`
per source with the facts above; `.env.example` unchanged (same key).

### 7. Caveats to carry into analyses

- OpenRouter traffic only; apps that route through OpenRouter, not each app's total usage
  (Claude Code and Codex mostly run on their vendors' own APIs).
- Tokens come from each provider's tokenizer; top 200 per week only; current category tags.
- Session cost: medians of per-session USD over a 30-day window, four harnesses chosen by
  OpenRouter, no session counts; snapshots overlap by ~23 days, so week-to-week changes are
  smoothed and not independent. History starts at our first fetch (Author-only); a replicator
  cannot reproduce earlier snapshots until the archive (§2.3, decision 5) is published.
- A "session" and a "turn" are OpenRouter's definitions and may differ between harnesses.

## Decisions (author review, 2026-10-07)

1. **Category tags: yes.** The 19–38 tag requests run on every fetch (newest week only).
2. **Window grain: weekly only.** Calendar-month windows can be added later as their own windows
   if an analysis needs monthly ranks (a month's top 200 is not the sum of its weeks' top 200).
3. **Top 200**, not top 100: both pages per week.
4. **Session-cost citation:** `"OpenRouter session cost by harness (openrouter.ai), as of {as_of}"`
   (the endpoint gives none; this names the publisher, the dataset and the date, in the same form
   as the other OpenRouter credits).
5. **Publish the session-cost raw snapshots** in the PLAN §2.3 raw archive (CC BY 4.0, OpenRouter
   attribution), alongside the other OpenRouter datasets, so replicators get Exact history from
   our first snapshot on. The adapter does not change: raw files are stored as served, and the
   archive is built by `export-archive` (backlog, first item after Phase 6). Until then the source
   stays Author-only for replicators. PLAN §2.3 gets one line naming session-cost as the source
   the archive matters most for (it has no other route to history).

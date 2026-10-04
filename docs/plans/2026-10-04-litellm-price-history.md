# Plan: LiteLLM price history (Phase 2, first source)

Status: DRAFT · 2026-10-04 · for adversarial review

## Goal

1. Add `litellm_prices`: the git history of BerriAI/litellm's
   `model_prices_and_context_window.json` as a **native-history, Exact** source (MIT).
2. Price every day of `010_openrouter_usage` from that history instead of one OpenRouter catalog
   snapshot, so `receipts/openrouter-wallet-share` no longer depends on `openrouter_models`
   (Author-only, redistribution forbidden since 2026-10-04). That makes the prices exactly
   reproducible, lets the licence gate commit `blog_html` and `data.json`, and lets the window
   start in January 2025 (rankings history starts 2025-01-01).

## What was measured (2026-10-04)

- A commits-only clone (`git clone --bare --filter=tree:0 --single-branch --branch main`) is
  33 MB and takes ~2 s; `git rev-list --first-parent --since=2024-12-31 main` → 11.6k commits.
- About 2,100 commits since 2025-01-01 touch the file; 417 of them are merge commits. Direct
  commits to `main` also happen, so "the state of `main` at the end of day D" must follow the
  **first-parent** chain, not the GitHub commits API (which mixes in branch commits dated before
  their merge).
- The file is ~3.0 MB (4,473 keys) today, 150 KB gzipped; it had 728 keys on 2025-01-01.
- LiteLLM's `openrouter/<id>` keys mirror OpenRouter's catalog (`"source":
  "https://openrouter.ai/api/v1/models"`), but they were sparse until mid-2026: 50 keys on
  2025-01-01, ~100 through 2026-07, 490 today, and some are stale (e.g.
  `openrouter/deepseek/deepseek-chat` still at $0.14/$0.28). Historical pricing therefore needs
  vendor-direct keys too (`claude-…`, `gpt-…`, `gemini/…`, `xai/…`, `deepseek/…`, …).
- With today's file, `openrouter/<catalog id>` covers 90.9% of non-free, non-`other` top-50
  tokens since 2025-01; the rest are retired or stealth models absent from today's catalog.
- Licence: the repo LICENSE is MIT for everything outside `enterprise/`; the price file is at the
  repo root (MIT).

## Design

### 1. Source `litellm_prices` (`src/cachereg/sources/litellm_prices/`)

Registry entry: `history: native`, `revisions: none` (→ Exact), `redistribution:
allowed-with-attribution`, `derived_charts: allowed-with-attribution`, attribution
`"LiteLLM model prices (github.com/BerriAI/litellm, MIT)"`, `cadence: daily`, `requires: []`.

**Vintage = one commit per UTC day.** `history.py` (shared by fetch and stage) defines
`day_end_commits(first_parent, start, end) -> {date: (sha, committed_at)}`: for each UTC date D,
the first commit in first-parent order (newest first) whose committer time is ≤ D 23:59:59 UTC.
This is a pure function of upstream history, so the author and a replicator who fetches later
resolve the same commit for every past day.

**`fetch.py`** (`fetch(full=False, today=None) -> RawFetch`, same signature as the others):
1. `git clone --bare --filter=tree:0 --single-branch --branch main <repo>` into a temp dir
   (subprocess, fixed argv, no shell; timeout). Requires `git` on PATH (documented).
2. `git log --first-parent --format=%H%x09%ct main --since=<FLOOR − 30 days>` → raw file
   `first_parent.tsv` (what the source returned). Fails if the oldest listed commit is not
   before FLOOR (2025-01-01), so day FLOOR always resolves.
3. Window: `end` = yesterday UTC (complete days only, so a day's commit never changes later);
   `start` = FLOOR on the first or `--full` fetch, else the day after the latest window end in
   earlier fetches' manifests.
4. For each day in the window, the day-end sha; download only shas not already stored by any
   earlier fetch: `GET https://raw.githubusercontent.com/BerriAI/litellm/<sha>/model_prices_and_context_window.json`
   with `Accept-Encoding: gzip`. Stored as returned: `prices_<sha>.json.gz` when the body is
   gzip (magic bytes), else `prices_<sha>.json`. Each body must decode to a JSON object.
   Needs a small, backwards-compatible change to `core/http.get` only if it rejects the header;
   it already passes custom headers and does not decompress.
5. `vintage = {"kind": "git_commit", "value": <sha of day end>, "window": [start, end]}`.
   First fetch: ~640 files, ~100 MB on disk; later fetches: one file a day.

**`stage.py`** → two tables:
- `days`: `date, commit_sha, committed_at` for FLOOR … latest window end, recomputed with
  `day_end_commits` over the newest fetch's `first_parent.tsv`; every sha must have stored
  content in some fetch (else error naming the day).
- `prices`: one row per **interval** in which a key's price tuple is unchanged:
  `key, litellm_provider, mode, input_usd_per_token, output_usd_per_token,
  cache_read_usd_per_token, valid_from (date), valid_to (date, exclusive; null = still present
  on the last staged day), commit_sha (of valid_from)`. Built by walking days in order and
  comparing each key's tuple with the previous day; each distinct sha is parsed once.
  `sample_spec` and non-object entries are skipped; non-numeric prices become null.

`SOURCE.md` per §4.2: URLs, licence (MIT, with links to LICENSE and the file), attribution,
history/revisions, vintage rule, quirks (stale `openrouter/` entries; prices are list prices as
LiteLLM records them, which can lag a vendor's change by days), last verified 2026-10-04.

### 2. Model aliases: `config/entities/models.yaml` (PLAN §4.3, subset)

Only what this mart needs: canonical `model_id` (OpenRouter's current id where one exists) →
`aliases: {openrouter: [permaslugs…], litellm: [keys…]}`. **The `litellm` list is in
preference order.** Other §4.3 fields (vendor, family, release date, variant) come in Phase 3.

```yaml
models:
  anthropic/claude-sonnet-4.5:
    aliases:
      openrouter: [anthropic/claude-4.5-sonnet-20250929]
      litellm: [openrouter/anthropic/claude-sonnet-4.5, claude-sonnet-4-5-20250929]
```

- `build.py` loads it into `dim_model_alias(model_id, source, alias, rank)` beside
  `dim_vendor_alias` (one generic loader; the file path is a module constant so tests can point
  it at a synthetic file). Validation: an `openrouter` alias may belong to one model only.
- **Bootstrap, then review:** `scripts/suggest_model_aliases.py` (author tool; reads the local
  warehouse) proposes entries for every top-50 permaslug, by token volume, with the rule used:
  (a) `openrouter/<catalog id>` via the author's local `openrouter_models` snapshot
  (identifiers only; no prices are committed), (b) `openrouter/<permaslug without :variant>`,
  (c) vendor-direct keys by a per-vendor prefix table (`anthropic`→bare, `openai`→bare,
  `google`→`gemini/`, `x-ai`→`xai/`, `deepseek`→`deepseek/`, `mistralai`→`mistral/`, …) with
  normalisation limited to case and `.`↔`-`. **Date or version suffixes are never stripped
  automatically** (§4.3); such matches are proposals for review only. Any key that ever existed
  in the history is a candidate, not just today's.
- **Check:** for each proposed entry the script prints the LiteLLM price on 2026-10-01 next to
  the OpenRouter snapshot price; entries that differ by more than 10% are reviewed by hand.
- Target: aliases covering ≥ 98% of non-free, non-`other` tokens over the window. The remainder
  stays unpriced and is reported (stealth models without a list price stay unpriced, as today).
- `cachereg entities` stays a Phase 3 stub; the script is folded into `entities suggest` then.

### 3. Mart `010_openrouter_usage` (inputs: `openrouter_rankings, litellm_prices`)

- `or_rankings_daily` unchanged.
- Price per (date, permaslug) from candidates = `dim_model_alias` (openrouter alias =
  permaslug without `:free`) → its `litellm` keys (rank) → `stg_litellm_prices_prices`
  intervals with non-null input and output price. Only data on or before `as_of` is visible:
  intervals with `valid_from > as_of` are dropped and `valid_to > as_of` is read as null, so a
  later fetch cannot change any result.
- Each candidate gets a basis: `current` (valid on that date), `after_removal` (the key's last
  interval ended before the date), `before_listing` (the key's first interval starts after the
  date but on/before `as_of`). Choose per (date, permaslug): basis order current →
  after_removal → before_listing, then alias rank, then the nearest interval. Exactly one row
  per (date, permaslug), asserted by a test (no fan-out).
- `or_model_daily` keeps its columns (`price_matched`, `est_spend_usd`, `blended_usd_per_token`,
  `price_date_stale` = basis ≠ current) and adds `price_key`, `price_basis`, `price_valid_from`,
  `price_commit`; `price_snapshot_date` is removed. `:free` → $0 as before.
- `or_vendor_weekly` adds `stale_priced_tokens`.
- Header comment lists the assumptions (blend 80/20, list prices, caching ignored, basis rules).

### 4. Exact-class vintages in core (PLAN §4.4, generic)

Today `cutoff()` treats every non-snapshot source as Latest-only: a replicator who fetches LiteLLM
after the receipt's `as_of` gets `vintage_after_as_of: true` and a different `content_sha256`,
so `reproduce` reports a difference that isn't one.

- `cutoff()` for **Exact** sources: the earliest fetch whose `vintage.window[1] ≥ as_of`
  (`after = False`; data is selected by source time in the mart); if none covers `as_of`, the
  latest fetch, with `after = False` and the manifest noting `history_ends` = its window end.
- `source_vintages()` for Exact sources: if the source's stage module defines
  `vintage_at(as_of) -> dict`, the manifest records that (LiteLLM: the day-end commit of
  `min(as_of, history end)`) and `content_sha256` hashes it, so author and replicator manifests
  match. Other classes are unchanged.
- No source-specific code in core; the hook is optional.

### 5. Receipt and exploration

- `receipts/openrouter-wallet-share/receipt.yaml`: `sources: [openrouter_rankings,
  litellm_prices]`; `as_of` stays 2026-10-02; config `start: 2025-01-06` (first Monday of 2025;
  every complete week from it) replaces `weeks: 13` (`weeks` remains supported for the
  exploration); `unpriced_flag` applies to unpriced + stale-priced tokens; `race_every_weeks: 4`
  (keyframes every 4th week counted back from the last, ~23 keyframes ≈ 25 s instead of ~85 s).
- `analysis.py`: `start` option, Story `sources` updated, caveat on price history and basis,
  `extra` records stale and unpriced shares.
- `charts.py`: x-axis ticks on month starts when the window exceeds 16 weeks (labels `%b '%y`);
  race keyframe thinning.
- `explore/2026-10-02-openrouter-wallet-share/`: `explore.yaml` and its `analysis.py` sources
  switch to `litellm_prices` (the mart's inputs changed); window unchanged.
- README: new finding numbers, method (price basis), caveats (LiteLLM lag; stale and unpriced
  shares per week; mapping coverage), reproduce section (prices Exact; tokens Latest-only, so
  exact reproduction holds unless OpenRouter revises past days), and a cross-check of the last 13
  weeks: Anthropic share priced from LiteLLM vs the 2026-10-02 snapshot.
- Re-render: the licence gate should then commit `share-lines.blog_html.html` and `data.json`
  (both sources allow redistribution with attribution).

### 6. Tests (synthetic only)

- `day_end_commits`: non-monotonic committer times, days without commits, 23:59:59 boundary.
- fetch with git and HTTP stubbed: window planning, incremental skip of stored shas, gzip vs
  plain bodies, error when history does not reach FLOOR, no shell use.
- stage: intervals for price change, removal, re-add, string numbers, `sample_spec` skipped.
- mart: basis selection (current at rank 2 beats stale at rank 1; after_removal;
  before_listing limited to ≤ as_of; post-as_of interval ignored), `:free` = 0, one row per
  (date, permaslug).
- core: Exact `cutoff` and `vintage_at` (fetch after as_of → `after = False`, identical vintage).
- receipt pipeline: renders with the new sources; `blog_html` and `data.json` written.
- `conftest.synthetic_raw` gains a synthetic LiteLLM fetch and a synthetic `models.yaml`.

## Sequencing (each a commit; checks green at each)

1. This plan.
2. `litellm_prices` source + registry + SOURCE.md + tests.
3. Exact-class vintages in core + tests.
4. `models.yaml` loader + bootstrap script; reviewed `models.yaml`.
5. Mart switch, receipt and exploration updates, tests.
6. Author run: fetch, build, render; README numbers; PLAN §10 status.

Rollback: steps 2–4 are additive; step 5 is one commit that can be reverted as a whole, restoring
the snapshot-priced receipt.

## Out of scope

Full entity resolver and `entities` CLI (Phase 3); using LiteLLM for other marts; caching-aware
spend; per-provider price variance on OpenRouter.

## Risks

- LiteLLM history rewritten upstream (force-push): day-end commits would change. Mitigation: the
  manifest pins the sha; `reproduce` reports a difference.
- LiteLLM prices lag or err for some models: the cross-check and per-week stale share make it
  visible; mapping review flags >10% disagreements on the last day.
- First fetch downloads ~640 files from raw.githubusercontent.com (~100 MB gzipped).

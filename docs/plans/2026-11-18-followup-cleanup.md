# Follow-up clean-up after the source-matters update (2026-11-18)

Status: reviewed (adversarial review with DeepSeek V4.1 Flash, 4 rounds, converged 2026-11-19); approved by the author 2026-11-19. Branch `claude/followup-cleanup` from `origin/main`
(`caae90c`). Context: the source-matters update of 2026-11-18 (commits `dbb90ed..caae90c`) added the
`databricks_ai_index` source and mapped 14 OpenRouter models by hand; it left the items below for later.

## Goals
1. Tests can never write into a real build folder.
2. Every mart dates a fetch by its UTC fetch date, the date `build.cutoff()` uses.
3. OpenRouter spend is priced from current list prices again after LiteLLM dropped its `openrouter/` keys.
4. Every committed receipt still reproduces, or the author sees exactly what changed and decides.
5. Ramp's other 11 views are current; the stale local `_site/` is dealt with.

Non-goals: re-rendering any posted receipt without the author's OK; changing source-matters' method; a
general pricing redesign.

## Findings that motivate the work (measured 2026-11-18)
- **Test isolation.** `tests/conftest.py::data_env` sets `CACHEREG_DATA_DIR` and `CACHEREG_OUTPUTS_DIR` but
  not `CACHEREG_BUILD_DIR`; `core/paths.py` resolves the build folder from `CACHEREG_BUILD_DIR` first. Running
  `make check` with `CACHEREG_BUILD_DIR` exported (as the worktree procedure does) made the tests overwrite
  that folder's `warehouse.duckdb` with synthetic data (happened to a scratch folder on 2026-11-18).
- **Local-time fetch dates.** Eight marts select vintages with `CAST(fetched_at AS DATE)` (12 occurrences:
  005, 050 ×2, 055, 060 ×3, 090 ×2, 100, 101, 102). `fetched_at` is a UTC `timestamptz`; DuckDB casts it in the
  session time zone (local), so a fetch between 00:00 UTC and local midnight is dated a day early, while
  `build.cutoff()` uses the UTC date (`f.fetched_at.date()` on an aware UTC datetime). The two dates disagree
  in either direction: behind UTC (the author's zone), a *later* fetch's local date can fall on a cutoff set
  by an *earlier* fetch, so the later fetch is selected for an as_of before its UTC date; ahead of UTC, the
  cutoff fetch itself can be dated a day later and excluded, so an older vintage is used. Mart 095 already
  uses the fetch id's UTC date. Raw fetches
  made in that window: openrouter_rankings 4, yahoo_prices 3, yahoo_intraday 3, census_btos 2,
  litellm_prices, openrouter_models, sec_edgar, github_innovation_graph, curated_* 1 each (Ramp: 0; Vercel: 0).
  The scheduled fetch (05:47 local = 13:47 UTC) is never affected.
- **OpenRouter prices.** LiteLLM's revision of 2026-10-09 (commit `141dba2…`, first fetched 2026-10-10) drops
  all `openrouter/` keys: 491 priced intervals end on 2026-10-09 in `lp_price_intervals` (PLAN §10's note of
  2026-10-10 counts 494 keys, which includes keys without both prices; the plan cites PLAN's 494 for keys and
  491 for priced intervals). 0 `openrouter/` keys are listed now, of 4,082 current keys. Since then mart 010
  prices those models from a vendor-direct key where the alias list has one, else from their last OpenRouter
  listing (`price_date_stale`: 16–48% of paid tokens per week since 11 October); a model new to OpenRouter's
  top 50 has no price unless mapped by hand (14 were mapped on 2026-11-18, `# manual 2026-11-18`).
- **Reproduction risk of those mappings.** Three receipts read mart 010: china-spend-share (as_of
  2026-10-07), openrouter-wallet-share (2026-10-02) and source-matters (2026-11-18). Of the 14 mappings, only
  `inclusionai/ling-3.1-flash` (first seen 2026-10-03, ~0.09% of tokens) falls inside the first two windows.
  Its only LiteLLM key (`openrouter/inclusionai/ling-3.1-flash`) is priced $0/$0 (PLAN §10, 2026-10-10), so
  the mapping adds no spend but moves its tokens from "unpriced" to "priced at 0": it shifts the unpriced share
  and OpenRouter's sensitivity band and lower bound, not the computed estimate.

## Plan (in order)

### Step 0 — Baseline (no code change)
- On `origin/main`, for **all 11 receipts**: `cachereg reproduce receipts/<r> --no-fetch`, saving (a) the
  status and reasons. `reproduce` keeps no build (its staged data and warehouse live in a
  `TemporaryDirectory`) and reports no fetch ids, so Step 0 adds a small scratch script (outside the repo, not
  committed) that, per receipt, (b) records each source's vintage at the pinned as_of: `build.cutoff()`'s fetch
  date and the fetch id of the latest fetch on that UTC date from `list_fetches` (as `render.source_vintages`
  does), or the Exact revision; (c) records the sha256 of `config/entities/models.yaml` and `vendors.yaml`;
  and (d) runs its **own** private build at the pinned as_of (`CACHEREG_BUILD_DIR` = a scratch folder,
  `cachereg build --as-of <as_of> --sources <receipt's sources>`) and writes every Story frame of the
  receipt's analysis `build()` to Parquet (this covers the 5 receipts that withhold `data.json`), plus, per
  mart table that has one, `SELECT DISTINCT fetch_id` (`import_used` in 060's `ramp_cut_coverage`): the
  vintage the marts actually selected. Item (b) is the vintage `cutoff()` intends, which mart SQL cannot change. Everything
  goes to a scratch folder outside the repo (frames may hold unlicensed data). The same script is re-run after
  Step 2 and after Step 3.
- `reproduce` builds its own temp warehouse at the pinned as_of and runs the current code and entities, then
  compares only the rendered `data_hash` with the committed one (`reproduce.py`): equal → `identical`, so a
  code change that leaves the frames unchanged is `identical`; otherwise `differs`, with a reason per source
  whose raw content differs, or "same source vintages but different results" when only code or entities
  changed the frames. The status alone does not say which frame moved, hence (d).
- Expected: china-spend-share may already `differ` (Ling 3.1 Flash; frames: unpriced share and bound in the
  week ending 2026-10-04 only); source-matters `identical`; the rest `identical`. Any other difference is
  investigated before going on.

### Step 1 — Test isolation (commit 1)
- `data_env`: `monkeypatch.setenv("CACHEREG_BUILD_DIR", str(tmp_path / "data"))` (the default layout: the
  build folder is the data folder), alongside the existing `CACHEREG_DATA_DIR` and `CACHEREG_OUTPUTS_DIR`.
  Only these three path variables (`core/paths.py`) are touched; `CACHEREG_SECRETS_FILE` is left alone (tests
  set it to a non-existent file on purpose where they need secret isolation; clearing it would fall back to
  the repo `.env`).
- Regression test: with `CACHEREG_BUILD_DIR` pointing at a sentinel folder before the fixture runs, a build
  inside the test writes nothing there.
- Check: `make check` with `CACHEREG_BUILD_DIR` exported to a sentinel; the sentinel stays empty.

### Step 2 — UTC fetch dates in marts (commit 2)
- One helper, used by all marts: a DuckDB macro that `build.py` defines with `CREATE OR REPLACE MACRO` on its connection before the
  mart loop (macros persist in `warehouse.duckdb`, and `build()` runs repeatedly on one file; noted in
  `build.py`'s docstring beside the `as_of` / `*_cutoff` variables)
  (every mart runs on that one connection), `fetch_date(fetch_id) := CAST(strptime(left(fetch_id, 8),
  '%Y%m%d') AS DATE)`. Every staged table behind the 12 casts carries `fetch_id` in `RawFetch.fetch_id`'s
  UTC `%Y%m%dT%H%M%SZ` format; replace the 12 casts and 095's inline expression with the macro. Core edit,
  justified as a shared correctness fix. Chosen over `SET TimeZone = 'UTC'` on the build connection for
  explicitness: the macro names the rule at each use and does not depend on session state; the time-zone
  setting would also work today (marts read no other `timestamptz` than `fetched_at`; litellm's
  `committed_at` is unused) and stays a fallback if the macro proves awkward.
- To make the defect testable on a UTC machine (CI), route `build()`'s `duckdb.connect` through a small
  module-level `_connect()` that tests can monkeypatch to run `SET TimeZone = 'America/Los_Angeles'` after
  connecting.
- Regression tests (fail before, pass after, in any machine zone), one per selection pattern (090's `pick`,
  005, 101): two fetches, the first at D−1 13:00 UTC, the second at D 00:30 UTC with different content; build
  at as_of D−1 under the Los Angeles session zone; assert the first fetch's rows are selected (before the fix
  the second fetch is dated D−1 locally and wins). And the other direction, under `Asia/Tokyo`: one fetch at
  D−1 08:00 UTC, one at D 23:00 UTC, as_of D; assert the second fetch is selected (before the fix it is dated
  D+1 locally and excluded).
- Impact check: re-run Step 0's reproduce for every receipt that reads a mart with a cast: china-token-share,
  deepseek-vs-us, open-middle, china-spend-share, openrouter-wallet-share (005/010), source-matters (005/010,
  060 via 062's `ramp_cut_coverage`, 090),
  sox-wave, midterm-split (101/102), coreweave-credit (100/101). Compare the marts' selected fetch ids (Step 0 (d)) and frames with Step 0;
  a changed selected fetch id names the day-early vintage the committed render used.
- Docs: PLAN §4.4 gains one line: fetch dates (cutoffs and mart selection) are UTC dates of the fetch id.

### Step 3 — OpenRouter pricing after 2026-10-09 (commit 3, after a decision)
- **3a Investigate first (no code):** diff LiteLLM's price files across the 2026-10-09 revision (the raw
  price files before and after, in `data/raw/litellm_prices/`) to see whether the `openrouter/` entries moved
  (another key prefix or file) or were dropped; read the upstream commit message. Re-check Ling 3.1 Flash's
  price and Step 5 Preview's keys.
- **3b Options, for the author:**
  1. *If they moved within LiteLLM:* teach `litellm_prices` stage (or the aliases) the new key form; history
     continues; smallest change.
  2. *Vendor-direct (or host) fallback keys:* append a first-party LiteLLM key after a model's `openrouter/`
     key (aliases are in preference order). Mart 010 uses the preference order only between *current* keys;
     a current lower-ranked key beats any stale higher-ranked one, so the fallback changes every day on which
     the `openrouter/` key is not current: after 2026-10-09 (`after_removal`), but also **before** that key
     was first listed (`before_listing`) and after LiteLLM's history ends (`beyond_history`). So it can move
     china-spend-share and openrouter-wallet-share too. Where a model has no first-party key, the fallback is
     a host's list price, not the lab's. Bootstrap with an `entities suggest` extension that proposes keys for
     models whose aliases are all stale, reviewed by hand.
  3. *OpenRouter's own prices from `openrouter_models`* (daily snapshots since 2026-10-02): closest to what
     OpenRouter charges. Its registry entry allows derived charts with attribution but forbids redistribution,
     and it is a snapshot (Author-only) source. Making mart 010 read it adds it to the `sources` of every
     receipt that uses 010, so their re-renders withhold `data.json` / `blog_html` (china-spend-share and
     openrouter-wallet-share publish `data.json` today, openrouter-wallet-share also `blog_html`). And it is a current-state snapshot from 2026-10-02 only: every
     earlier day (both 010 receipts start in 2025-01) would be unpriced or priced from a later snapshot
     (flagged stale). So option 3 is only workable as a hybrid: LiteLLM up to 2026-10-09, OpenRouter's
     snapshots after.
- Recommendation: 1 if available, else 2; 3 only if the author accepts losing inlined data on those receipts.
- **Outcome (2026-11-20):** 3a found the provider dropped, not moved (494 keys removed, none re-added), so
  option 1 was out; the author chose option 2. Measured on a prototype, plain appended keys repriced
  `before_listing` days back to June 2026 (China's share up to +4.5 pp in August, via host keys listed before
  OpenRouter's own), so the keys went into a separate `litellm_fallback` list that mart 010 uses only on days
  when all of a model's `litellm` keys have been removed. Result: no week before 2026-10-05 changes; from
  2026-10-11 the stale share of paid tokens falls from 16–48% to 1–15% a week, Anthropic's OpenRouter spend
  share by 1.2–3.5 pp and China's rises by 1.8–4.9 pp. 15 fallbacks (6 first-party, 9 hosts); 8 models
  stay without one (no listing or no consensus price).
- Measurement, before and after, over the **full history** of the three receipts that read 010 (from
  2025-01, not only since 2026-10): per week, the stale and unpriced shares of paid tokens, and each receipt's
  headline series (Anthropic's and China's OpenRouter spend share). Any posted figure that moves > 1 point is
  reported to the author before anything is re-rendered.
- Docs: replace PLAN §10's "Check whether the keys return…" note with the outcome; mart 010's header states
  the fallback rule.

### Step 4 — Receipts after Steps 2–3
- Reproduce all 11 receipts after Step 2 (separately) and again after Step 3, each time against Step 0's
  vintages and frames, so each difference is attributed to one step (or to the merged mappings, already
  visible at Step 0). For each `differs`: the frame-level diff, the README figure it moves, and a proposal
  (leave as posted, or re-render with the author's OK following the re-render procedure: per-receipt build at
  the pinned as_of, one commit per receipt, re-render after any rebase).
- source-matters (as_of 2026-11-18) is the receipt expected to move in Step 3 (its OpenRouter spend line);
  it is re-rendered only with the author's OK.

### Step 5 — Ramp's other 11 views (data only, no code)
- Import the 11 remaining cuts (`adoption/*`, `spend_per_employee/*`, `spend_share/overall`,
  `token_price/*`) the same way as on 2026-11-18 (Chrome, "Get the data", `cachereg fetch ramp_ai_index
  --from-clipboard --cut …`), one cut per import, checking each header before the next click (the
  wrong-click guard refuses identical clipboards; the price views are told apart only by mart 062's checks).
- `cachereg build --sources ramp_ai_index` and read `ramp_cut_coverage`, `ramp_price_check`,
  `ramp_token_check`. No receipt uses these cuts today (source-matters uses only the token views), so no
  re-render.

### Step 6 — Local `_site/` and notes
- The main checkout's `_site/` (git-ignored, built 2026-10-19) still holds the October source-matters video.
  Delete it or rebuild it (`cachereg site --out _site`): the author chooses.
- Update the memory notes on the worktree build procedure (tests vs `CACHEREG_BUILD_DIR`) and on LiteLLM's
  OpenRouter keys. (PLAN updates are in Steps 2 and 3.)

## Sequencing, failure and rollback
- Each step is its own commit on `claude/followup-cleanup`; `make check` after each; the branch is pushed as
  it goes (pre-push hook: guard, gitleaks, lint, tests). `main` is fast-forwarded only on the author's OK,
  after a rebase on `origin/main` and a fresh `make check`.
- Steps 1–2 are independent of Step 3; if Step 3 stalls on a decision, Steps 1–2 (+ Step 4's reproduce
  report for them) can be merged alone.
- Raw data is never modified; Step 5 only adds imports. Rollback of any code step is a revert commit; no
  committed receipt output changes without an explicit render commit.

## Decisions for the author
1. Step 3's option (after 3a).
2. Per receipt that `differs` in Step 4: leave as posted or re-render.
3. `_site/`: delete or rebuild.

## Checks
`make check`; `cachereg reproduce receipts/<r> --no-fetch` for all receipts (Step 0, after Step 2, after
Step 3); the new regression tests (Steps 1–2); per-week stale/unpriced shares and headline series over full
history (Step 3).

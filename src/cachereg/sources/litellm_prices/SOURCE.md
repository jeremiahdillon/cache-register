# LiteLLM model prices (`litellm_prices`)

**Repository:** https://github.com/BerriAI/litellm (branch `main`)
**File:** [`model_prices_and_context_window.json`](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json)
**Fetched from:** a commits-only clone of `main` (history) and
`https://raw.githubusercontent.com/BerriAI/litellm/<sha>/model_prices_and_context_window.json` (file at each commit)
**Licence:** MIT — [LICENSE](https://github.com/BerriAI/litellm/blob/main/LICENSE): MIT for everything
outside `enterprise/`; the price file is at the repository root. Copyright (c) 2023 Berri AI.
**Attribution:** "LiteLLM model prices (github.com/BerriAI/litellm), MIT"
**Auth:** none. **Requires:** `git` on PATH.
**Last verified:** 2026-10-04

## What it contains
One JSON object keyed by model key: provider-prefixed for most providers (`openrouter/…`,
`gemini/…`, `xai/…`, `deepseek/…`, `bedrock/…`, …), bare for OpenAI and Anthropic (`gpt-…`,
`claude-…`). Each entry has `litellm_provider`, `mode`, and per-token USD prices
(`input_cost_per_token`, `output_cost_per_token`, `cache_read_input_token_cost`, …). Its git
history is a native price time series: 728 keys on 2025-01-01, ~4,500 in Oct 2026.

## Classification
- history: native · revisions: none → **Exact** (PLAN §4.4): every past day resolves to a fixed
  upstream commit, so a replicator who fetches later gets the same prices.
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution (MIT:
  keep the copyright and licence notice with copies of the file; derived figures credit LiteLLM).

## Vintage rule
The price state of UTC day D is the file at the newest commit on `main`'s **first-parent** chain
whose committer time is ≤ D 23:59:59 UTC (`history.day_end_commits`). First-parent matters:
upstream merges branches whose commits are dated before the merge. Only complete UTC days are
fetched. Manifests record `vintage = {kind: git_commit, value: <sha>, window: [start, end]}`;
`stage.vintage_at(as_of)` gives the commit an analysis used.

## Fetch strategy
The first fetch stores `first_parent.tsv` (from 30 days before 2025-01-01) and the file at every
distinct day-end commit since 2025-01-01 (≈555 files, 27 MB gzip as served). Later fetches add
only commits not stored yet (about one a day). Staging rebuilds `days` (date → commit) and
`prices` (one row per interval in which a key's price is unchanged).

## Known quirks and caveats
- **`openrouter/<id>` entries are re-synced from OpenRouter's catalog almost daily** and swing
  with OpenRouter's displayed price (which follows the provider it routes to): e.g.
  `openrouter/deepseek/deepseek-v4.1-flash` input ranged $0.02–$0.30 per million tokens over two
  weeks of Sep 2026. Before mid-2026 there were only 50–100 such entries.
- **Coverage lags launches**: many models appear weeks or months after release (a large batch
  of Chinese-lab models only on 2026-09-05 and 2026-09-18). Marts that need a price before a
  key exists must flag the fallback (see `010_openrouter_usage`).
- List prices as LiteLLM records them, maintained by the community; errors and lags happen.
- Keys are not canonical model ids: mapping to other sources goes through
  `config/entities/models.yaml` (PLAN §4.3).

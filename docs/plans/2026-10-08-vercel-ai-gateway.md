# Plan: Vercel AI Gateway leaderboards as a source (Phase 2 source; the gateway lens (1) of analysis (e))

Status: BUILT · 2026-10-09 (planned 2026-10-08; adversarial review converged 2026-10-09)

**As built (differences from the design below):** days run through *yesterday* (UTC), as the research
requests did (today's rollup is incomplete). Stage keeps every vintage and mart 090 picks, per day (models:
per month window and day), the newest fetch on or before the cutoff, as the other Latest-only marts do; the
period means are their own table, `vercel_lab_share_period` (week and month, with `days` and
`period_days`). Fetching models per month surfaces 70 display names to 2026-10-08, not the 21 of the
full-year request; `models.yaml` maps 64 of them by hand (SOURCE.md lists the six left out). No vendor was
added: every lab with ≥ 1% maps to an existing one. Mart 091 names the volume-weighted OpenRouter token
share as its own lens (`openrouter_tokens_volume_weighted`), keeps Ramp's label for unmapped vendors, and
gives the estimated-spend lens a `coverage_pct` (priced share of non-free tokens).

## Goal

1. Add source `vercel_ai_gateway`: the open data behind vercel.com/ai-gateway/leaderboards, daily share
   by **lab** and by **model** of requests, tokens and **spend** on Vercel's AI Gateway, from the public
   export endpoint. No key, CC BY 4.0.
2. Staged tables and marts that put Vercel's lab shares on canonical vendor ids beside OpenRouter's (tokens
   and estimated spend) and Ramp's (share of businesses paying), for lens 1 (developer gateways)
   of analysis (e) "Developer wallet vs enterprise wallet".

Done when everything works on synthetic fixtures in CI and on a real fetch locally. No analysis is built
here. Out of scope: the `apps` and `providers` datasets (all-time ranked lists, no day dimension: a
snapshot source to add later if wanted), image and video modalities, and Vercel's monthly "production
index" blog posts (narrative; their figures can go into the curated disclosures dataset instead).

## What was measured (2026-10-08: read-only requests, nothing kept in the repo)

| # | Request | What it showed |
|---|---|---|
| 1 | `GET vercel.com/docs/ai-gateway/leaderboards` | Datasets, parameters, licence, the export endpoint (below) |
| 2 | `GET /api/ai/leaderboard-export?dataset=labs&modality=text&from=2025-10-01&to=2025-10-07` | 288 rows; 13–14 labs per day × metric; shares sum to 100.0 |
| 3 | `…dataset=models&modality=text&from=2026-09-01&to=2026-09-30` | 863 rows; 7–11 models per day × metric **plus an `Other` row** (57% of requests on 2026-09-01) |
| 4 | `…dataset=labs&modality=text&from=2025-10-01&to=2026-10-07` (one request, 2.5 MB) | 22,563 rows, 372 days, 33 lab slugs, metrics `requests`, `tokens`, `spend` |
| 5 | `…dataset=models&modality=text&from=2025-10-01&to=2026-10-07` | 3,337 rows; 21 distinct model names over the year; `Other` rows only from June 2026 (median 81% of tokens over those days; 25% in September 2026) |
| 6 | `…dataset=labs&modality=all&from=2026-09-01&to=2026-09-07` | 200; `all` also works for labs |
| 7 | `…dataset=labs&from=2025-09-01&to=2025-09-10` | HTTP status 400 (a range before the earliest date is refused) |
| 8 | requests 3 and 5 compared on 2026-09-01 | **The models list depends on the requested window**: the same models have identical daily shares, but the September request lists `Step 3.7 Flash` (5.6%) that the full-year request folds into `Other` (68.0% vs 73.6%). Labs are identical across windows (2025-10-03 compared) |

The bodies behind requests 2–8 are kept locally (`data/research/2026-10-08-disclosures-vercel/vercel/`,
never committed); the figures here were computed from them on 2026-10-08.

**Endpoint** (documented, public): `GET https://vercel.com/api/ai/leaderboard-export`, parameters
`dataset` (`models` | `labs` | `apps` | `providers`), `modality` (`all` | `text` | `image` | `video`),
`format` (`json` | `csv`), `from` / `to` (`YYYY-MM-DD`; earliest **2025-10-01**, "the point from which the
daily rollups are complete"; default a rolling two months). "Cached for 24 hours." No key, no documented
rate limit. JSON: `{dataset, modality, from, to, earliest_available_date, license: "CC-BY-4.0",
license_url, rows: [{date, group, name, metric, modality, share_percent}]}`.

**Licence:** CC BY 4.0. Required notice: `© 2026 Vercel. "AI Gateway Leaderboard Data" is licensed under
CC BY 4.0.` with a link to the licence. → `redistribution: allowed-with-attribution`, `derived_charts:
allowed-with-attribution`.

**What the data is:** "built from real AI Gateway usage, aggregated daily … anonymized: it shows each
model, lab, app, or provider's percentage **share** or rank, **never absolute volumes**." So:
- Shares only. A day's shares cannot be summed across days by volume; a weekly or monthly share is the
  unweighted mean of daily shares (a busy day counts as much as a quiet one). Stated wherever used.
- **Labs are complete** (shares sum to 100 every day, 12–33 labs) and are the useful comparison level.
  **Models are a top-few list plus `Other`**, and the list is the top models **of the requested window**
  (request 8): too thin for model-level claims; staged, but marts use them only for "largest models"
  context.
- **Spend share is measured by Vercel**, not estimated from list prices as OpenRouter's is. It is the only
  published spend-by-lab series from a gateway that we know of.
- Lab slugs include gateway-specific names: `spacexai` (xAI's models), `stealth` (unnamed models),
  inference providers that ship their own models (`fireworks`, `inference-net`, `morph`), and newer labs
  not yet in `vendors.yaml` (`interfaze`, `meituan`, `mixedbread`, `quiverai`, `sakana`, …).

**A first look** (September 2026, mean of daily shares, text): Anthropic 10.5% of tokens but 45.8% of
spend; DeepSeek 53.3% of tokens, 5.7% of spend; OpenAI 10.7% / 22.1%; Google 5.0% / 8.0% (19.3% of
requests). The tokens-vs-dollars split is the reason to have it beside OpenRouter.

## Design

### 1. Core
**No core change.** A plain HTTP source like `openrouter_apps` (`core.http.get`, JSON).

### 2. Source `vercel_ai_gateway` (`src/cachereg/sources/vercel_ai_gateway/`)
- **`fetch.py`:** `modality=text`, `format=json`. **Labs:** first run `from=2025-10-01` to today (one
  request, 2.5 MB), later runs the trailing 35 days, so revisions are captured as new vintages (as
  OpenRouter rankings). **Models: one request per calendar month** (first run: every month from 2025-10;
  later runs: the current and previous month), because the listed models depend on the window; a month's
  list is then "the top models of that month" whatever day it is fetched, and stage keys models rows by
  (month window, date, name). Validate before
  storing: `license == "CC-BY-4.0"` (a licence change stops the fetch with a clear error), the expected keys,
  ISO dates within the requested range, known `metric` and `group` values, finite shares in 0–100, and
  per day × metric shares summing to 100 ± 0.05 for labs (the samples sum to 100 ± 0.0002). Models days
  need not sum to 100 (the long-range body has no `Other` before June 2026). Store each body as served. Vintage: `{kind:
  "content", value: sha256, window: [from, to], earliest_available_date}`.
- **`stage.py`:** `shares`: `date`, `dataset` (`labs` | `models`), `name` (as published), `metric`
  (`requests` | `tokens` | `spend`), `modality`, `share_pct`, `is_other` (models' `Other` row),
  `window` (models: the requested month), `fetch_id`. Stage adds, per models day × metric, an
  `unlisted_pct` = 100 − Σ listed shares (Vercel's `Other` when present, else the residual), so the
  coverage of the listed models is always known. Each day uses the newest fetch covering it (Latest-only). `labels`: distinct names with
  first/last day and peak share, for entity coverage.
- **Registry:** `history: native`, `revisions: revised` (→ Latest-only until two months of vintages
  show past days unchanged), `redistribution: allowed-with-attribution`, `derived_charts:
  allowed-with-attribution`, `cadence: daily` (the export rolls daily; the launchd agent fetches it with the
  OpenRouter sources), `requires: []`. Attribution (the footer string; it carries the licence's
  required notice, from the docs page read on 2026-10-08: `© 2026 Vercel. "AI Gateway Leaderboard Data" is
  licensed under CC BY 4.0.`): `"© 2026 Vercel, \"AI Gateway Leaderboard Data\", CC BY 4.0
  (vercel.com/ai-gateway/leaderboards), as of {as_of}"`. `SOURCE.md` records the notice verbatim with its
  verification date; the year follows Vercel's notice when it changes.

### 3. Entities
- `vendors.yaml`: `aliases.vercel` for the lab slugs (`openai`, `anthropic`, `google`, `deepseek`,
  `moonshotai` → `moonshot`, `zai`, `alibaba`, `meta`, `mistral`, `amazon`, `nvidia`, `xiaomi`, `minimax`,
  `stepfun`, `bytedance`, `tencent`, `cohere`, `perplexity`, `poolside`, `thinkingmachines`, `arcee-ai`,
  **`spacexai` → `xai`**, `inclusionai` → `ant` (Ant Group's lab), `stealth` → `_stealth`). New vendors only where a lab had ≥ 1% of tokens or spend on any day; the rest
  stay unmapped and are reported in coverage with their peak share, never dropped.
- `models.yaml`: `aliases.vercel` for the 21 published display names (`GPT 5.6 Luna`, `Claude Opus 5.5`,
  …), by hand; `entities suggest --source vercel` is backlog.

### 4. Marts
- **`090_vercel_shares`** (inputs: `vercel_ai_gateway`): `vercel_lab_share` (day × vendor × metric, with
  `vendor_id`, plus weekly and monthly means of daily shares and the number of days averaged);
  `vercel_model_share` (day × model × metric, `Other` kept as its own row); `vercel_label_coverage`
  (unmapped labels with peak shares).
- **`091_gateway_lenses`** (inputs: `vercel_ai_gateway`, `openrouter_rankings`, `litellm_prices`,
  `ramp_ai_index`): the comparison table for (e), monthly by vendor, long format, one row per lens:
  `vercel_tokens`, `vercel_spend` (Vercel's measured share), `openrouter_tokens`, `openrouter_est_spend`
  (from `or_model_daily` in `010_openrouter_usage`; a list-price estimate, caching ignored), `ramp_paying` (share of businesses
  on Ramp paying the lab: adoption, not a share of a total). Lenses are rows, never ratios or
  differences; shares from different populations are never put on one axis as one quantity. Months are
  calendar months; Vercel and OpenRouter as means of daily shares (OpenRouter's monthly token share is
  also available volume-weighted, which the mart keeps beside it, so the two weightings can be compared
  on OpenRouter). Vendor rank per lens per month.
  A bare `cachereg build` then needs all four sources for `091` (as `072`); `--sources vercel_ai_gateway`
  builds `090` alone.

### 5. Tests (synthetic fixtures, `tests/test_vercel_ai_gateway.py`)
- Fetch: a valid body stores; a changed licence string, an unknown metric, shares outside 0–100, a lab
  day summing to 97 and a date outside the window are each refused with nothing written; first run asks for
  the full range from 2025-10-01, later runs the trailing 35 days.
- Stage: labs and models rows land; `Other` is flagged; the newest fetch wins for an overlapping day.
- Marts: monthly mean of daily shares (a two-day month with shares 10 and 30 → 20, not volume-weighted);
  `spacexai` maps to `xai`; an unknown lab is in coverage, not dropped; `091` puts four lenses as rows and
  reproduces a synthetic OpenRouter estimated spend share.

### 6. Caveats to carry into analyses
- **Vercel AI Gateway traffic only**: developers building on Vercel (app backends, coding agents),
  not the market. Different from OpenRouter's population, and both differ from Ramp's businesses.
- **Shares, never volumes**: no way to size Vercel's traffic or weight days; monthly shares are means of
  daily shares.
- Spend is Vercel's measure of what its customers paid through the gateway (Vercel does not say whether
  bring-your-own-key traffic, discounts or caching are included); OpenRouter's spend is our list-price
  estimate; Ramp is a count of paying businesses. Three different things.
- Models are top-few plus `Other`; model-level claims are not supported.
- Tokens are counted by each provider's tokenizer (as on OpenRouter).
- Latest-only until revisions are ruled out; history from 2025-10-01 only.

### 7. Docs to update when built
`SOURCE.md`; `config/sources.yaml`; PLAN §2.1 (new #, Tier 1, verified), §2.2 table (gateway lens), §4.4
(Latest-only list), §10 status and the (e) row (lens 1 becomes "developer gateways: OpenRouter and Vercel").

## Decisions (author review, 2026-10-08: the recommendations, as proposed)

1. **Scope:** labs and models, text modality; `apps`/`providers` (and image/video) later.
2. **Mart `091_gateway_lenses`** is built with this source.
3. **New vendors** only for labs with ≥ 1% of tokens or spend on any day; the rest reported in coverage.

The research samples (export bodies of 2026-10-08) are kept locally under
`data/research/2026-10-08-disclosures-vercel/vercel/`, never committed.

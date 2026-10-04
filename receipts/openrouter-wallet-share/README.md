# Who gets paid on OpenRouter?

*Receipt · [cacheregister.dev/openrouter-wallet-share](https://cacheregister.dev/openrouter-wallet-share) ·
data as of 2026-10-02 · promoted from [`explore/2026-10-02-openrouter-wallet-share`](../../explore/2026-10-02-openrouter-wallet-share/)*

## Question
How is estimated developer spend on OpenRouter split between model makers, and how fast is
it shifting?

## Finding (as of 2026-10-02)
Anthropic's share of estimated weekly spend on OpenRouter's top-50 models fell from **66%**
(week of Jun 29, 2026) to **30%** (week of Sep 21). In that last week **Chinese labs combined
(33%)** — Z.ai, Moonshot AI, Tencent, DeepSeek, Xiaomi and others — edged ahead of both
Anthropic (30%) and **OpenAI (30%)**. Total estimated weekly spend on these models rose from
~$82M to ~$113M (+37%) over the same period, so Anthropic's decline is in *share* while the
pie grew.

*Correction (2026-10-02, before publication):* an earlier draft said 69% → 32%. The price join
counted 84 models twice (each also listed as a half-price `:batch` variant), overstating their
spend ~1.5×; prices are now taken from the base model only, and a test guards against it.

## Visuals
In [`output/`](output/) — `output/manifest.json` records the data versions and hashes:
- `share-lines` — weekly share line chart: `x_png` (1600×900), `linkedin_png` (1080×1350).
- `share-race` — bar-race video: `linkedin_video` (1080×1350), `x_video` (1920×1080).

Not committed: the interactive `blog_html` and `data.json`, because they include the data and
OpenRouter's terms don't permit redistributing its model price list (verified 2026-10-04; see
`src/cachereg/sources/openrouter_models/SOURCE.md`). The manifest's `withheld` section records
this. Render locally to see them.

## Data
- `openrouter_rankings` — daily tokens for the top-50 models (CC BY 4.0, OpenRouter).
- `openrouter_models` — current list prices (snapshot).
- Mart: `010_openrouter_usage` (`or_vendor_weekly`, `dim_vendor_alias`), see
  `src/cachereg/marts/010_openrouter_usage.sql`.

## Method
1. Daily tokens per model × blended list price (80% input / 20% output) = estimated spend.
   `:free` variants count as $0. Models without a current price are excluded and measured.
   Catalog variants that share a model's `canonical_slug` (e.g. `:batch`) are ignored for pricing.
2. Model → developer via `config/entities/vendors.yaml` (author prefix of the permaslug).
   "Chinese labs" = developers headquartered in China.
3. Weekly (ISO weeks, Monday start), last 13 complete weeks; share = developer spend / all
   priced top-50 spend that week.
4. Weeks where more than 3% of tokens couldn't be priced are shaded (Aug 17 and Aug 24: ~14%,
   almost entirely an anonymous pre-release model, `stealth/ox-alpha`, which has no list price).

## Caveats
- **Estimate, not revenue.** List prices; no negotiated discounts; **prompt caching ignored**,
  which overstates spend most for heavily cached coding traffic — so Anthropic's share is
  likely an upper bound.
- **Tokens are counted by each provider's own tokenizer** and aren't strictly comparable.
- **OpenRouter only** — third-party developer routing, not the whole market.
- Top-50 models per day only (the remaining ~4% of tokens has no per-model price).
- One current price snapshot is used for all weeks. Price history (LiteLLM, Phase 2) will
  replace this and lets the window extend back before July 2026.

## Reproduce this receipt on its own
Needs [uv](https://docs.astral.sh/uv/) and an `OPENROUTER_API_KEY` (any OpenRouter key; see
`.env.example`). From a clone of the repo, after installing dependencies with uv:

```sh
cachereg reproduce receipts/openrouter-wallet-share            # this receipt only
cachereg reproduce receipts/openrouter-wallet-share --latest   # same method, your latest data
```

`reproduce` fetches and builds only what this receipt needs, renders into a temporary folder
and compares a fingerprint of the underlying data with the committed run. **Exact reproduction
needs the 2026-10-02 price snapshot**, which only the author has (prices come from a snapshot of
OpenRouter's catalog), so a fresh clone reports *cannot reproduce exactly* and should use
`--latest`. Exact reproduction becomes possible once price history (LiteLLM) replaces the
snapshot.

Author: re-render the committed visuals with `cachereg render receipts/openrouter-wallet-share`.

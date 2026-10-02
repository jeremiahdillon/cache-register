# OpenRouter models (`openrouter_models`)

**Endpoint:** `GET https://openrouter.ai/api/v1/models` (public; no key needed)
**Docs:** https://openrouter.ai/docs/api/api-reference/models/get-models
**Last verified:** 2026-10-02

## What it contains
Current catalog: `id`, `canonical_slug` (joins to rankings `model_permaslug`), name, created
date, context length, and per-token list prices (`pricing.prompt`, `pricing.completion`,
cache read/write where offered) in USD per token.

## Classification
- history: snapshot · revisions: n/a (current state only; history = our daily snapshots)
- redistribution: unknown · derived_charts: allowed-with-attribution (verify in Phase 1)
  → raw is never committed or inlined; only derived estimates are published.

## Caveats
- **List prices only**: no negotiated discounts and no per-provider/host price variance.
- Prices are as of the snapshot date. Pricing a past week with a later snapshot is
  price-date staleness and must be flagged (LiteLLM price history fixes this in Phase 2).

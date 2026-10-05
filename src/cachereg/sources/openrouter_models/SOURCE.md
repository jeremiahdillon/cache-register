# OpenRouter models (`openrouter_models`)

**Endpoint:** `GET https://openrouter.ai/api/v1/models` (public; no key needed)
**Docs:** https://openrouter.ai/docs/api/api-reference/models/get-models
**Terms:** https://openrouter.ai/terms (version "Last Updated: August 31, 2026")
**Licence:** none granted for this endpoint's data (see below)
**Attribution:** "OpenRouter model pricing (openrouter.ai/models)"
**Last verified:** 2026-10-04

## What it contains
Current catalog: `id`, `canonical_slug` (joins to rankings `model_permaslug`), name, created
date, context length, and per-token list prices (`pricing.prompt`, `pricing.completion`,
cache read/write where offered) in USD per token.

## Classification
- history: snapshot · revisions: n/a (current state only; history = our daily snapshots)
- **redistribution: forbidden** · **derived_charts: allowed-with-attribution**
  → raw is never committed or inlined (no `data.json`, no interactive `blog_html`); only
  derived, aggregated estimates (images/video) are published.

## Licence verification (2026-10-04)
- OpenRouter's CC BY 4.0 grant covers the **Datasets** endpoints only. The OpenAPI spec
  describes the `Datasets` tag as "Data returned by these endpoints is licensed under CC BY 4.0
  … reuse and republish it, including commercially, with attribution to OpenRouter"; `/models`
  is under the `Models` tag ("Model information endpoints"), which has no licence statement.
  The spec's own `license: MIT` applies to the API description, not to returned data.
- [Terms](https://openrouter.ai/terms) §12 lists "information, data" among the Service's
  "Materials": "Except as expressly authorized by OpenRouter, you may not make use of the
  Materials. OpenRouter reserves all rights to the Materials not granted expressly in these
  Terms." §7 forbids scraping or copying "any information on the Site or the Services" by
  automated means and transferring "any Materials". Reading the documented public API is the
  authorized way to use it; republishing the catalog or price list is not granted. Hence
  `redistribution: forbidden`.
- Derived charts: published under the author's policy (2026-10-05) that derived works are
  publishable from every source, credited; the raw catalog and price list are not republished.
- Prefer LiteLLM (`litellm_prices`, MIT) for any published price-based figure.

## Caveats
- **List prices only**: no negotiated discounts and no per-provider/host price variance.
- Prices are as of the snapshot date. Pricing a past week with a later snapshot is
  price-date staleness and must be flagged (`litellm_prices` replaces this in
  `010_openrouter_usage`).

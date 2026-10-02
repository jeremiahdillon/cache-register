# OpenRouter rankings (`openrouter_rankings`)

**Endpoint:** `GET https://openrouter.ai/api/v1/datasets/rankings-daily` (`start_date`, `end_date`, `period=day`)
**Docs:** https://openrouter.ai/docs/api/api-reference/datasets/daily-token-totals-for-top-50-models
**Auth:** any OpenRouter API key (`OPENROUTER_API_KEY`). Limits: 30 requests/min per key, 500/day per account.
**License:** CC BY 4.0 — reuse and republish with attribution. Required citation:
"Source: OpenRouter (openrouter.ai/rankings), as of {as_of}."
**Last verified:** 2026-10-02

## What it contains
Per UTC day, the top 50 public models by `total_tokens` (prompt + completion) plus one `other`
row summing everything outside the top 50. Rows are keyed by `model_permaslug` (an exact model
version, e.g. dated snapshots and `:free` variants are distinct). History starts 2025-01-01.

## Classification
- history: native · revisions: revised (treated as Latest-only until revision behaviour is confirmed)
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution

## Known quirks and caveats
- Tokens only: no input/output split, no dollars, no request counts, no caching data.
- **Token counts come from each provider's own tokenizer**, so a token from one vendor is not
  strictly comparable with a token from another.
- Top-50 truncation: the tail is only visible as the aggregated `other` row.
- This is OpenRouter traffic (third-party developer routing), not the whole market.

## Fetch strategy
First run backfills from 2025-01-01 in monthly windows (~21 requests). Later runs re-fetch the
trailing 35 days so late revisions are captured as a new vintage.

# OpenRouter app rankings (`openrouter_apps`)

**Endpoint:** `GET https://openrouter.ai/api/v1/datasets/app-rankings` (`start_date`, `end_date`, `sort=popular`, `limit` ≤ 100, `offset` ≤ 100, `category` / `subcategory`)
**Docs:** https://openrouter.ai/docs/api/api-reference/datasets/top-apps-by-token-usage
**Auth:** any OpenRouter API key (`OPENROUTER_API_KEY`). Limits: 30 requests/min per key, 500/day per
account (shared with the other OpenRouter datasets sources).
**License:** CC BY 4.0 — reuse and republish with attribution. Required citation:
"Source: OpenRouter (openrouter.ai/apps), as of {as_of}."
**Last verified:** 2026-10-07 (docs plus live requests; design in
`docs/plans/2026-10-07-openrouter-apps-session-cost.md`)

## What it contains
For a date window, the top public apps on OpenRouter by `total_tokens` (prompt + completion, a
decimal string) with `total_requests`, `app_id` (stable integer) and `app_name`. One row per app for
the whole window: no per-day rows, no `other` row, no category on the row. Ranks 1–200 at most per
window. Hidden and private apps are excluded and alias apps are merged into the canonical app at
query time. History starts 2025-01-01; we use ISO weeks from 2025-01-06.

Category tags exist only as filters (4 groups, 15 subcategories; the API publishes no mapping
between them). An app returned by `subcategory=S` carries tag S, one returned by `category=G` is in
group G; an app can have several of each.

## Classification
- history: native · revisions: revised (Latest-only), like `openrouter_rankings`
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution

## Known quirks and caveats
- Token counts come from each provider's own tokenizer; apps on different providers are not
  strictly comparable.
- Top 200 per week only; the denominator for shares is rankings-daily's total (mart 051), which
  also holds traffic not attributed to any public app, so app shares are lower bounds.
- Past weeks can change when an app is hidden or merged, not only from late events. Rankings-daily
  vintages 2026-10-02..06 changed only in the last one or two days (≤ 0.005%); compare this
  source's first month of vintages before relying on older weeks being stable.
- Tags are fetched for the newest week only and applied to all history (current tags); apps
  outside a filter's top 200 that week, or absent from it, are `untagged`.
- `meta.as_of` is when the response was generated, not a data revision.
- OpenRouter traffic only: apps that route through OpenRouter, not each app's total usage.

## Fetch strategy
First run (or `--full`) back-fills every ISO week from 2025-01-06 to the last complete week (ends on
or before yesterday): 2 pages per week, ~190 requests, plus 19–38 tag requests. Weekly runs re-fetch
the trailing 5 weeks plus tags (~30–50 requests). Requests are spaced 2.1 s apart. A page whose
window, ranks, ids or counts do not validate fails the whole fetch (nothing written).

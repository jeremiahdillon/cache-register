# OpenRouter session cost (`openrouter_session_cost`)

**Endpoint:** `GET https://openrouter.ai/api/v1/datasets/session-cost` (`turn_range`, `limit` ≤ 500, `offset` ≤ 5000; also `app_slug`, `model`)
**Docs:** https://openrouter.ai/docs/api/api-reference/datasets/cost-per-session-by-harness-and-model
**Auth:** any OpenRouter API key (`OPENROUTER_API_KEY`). Limits: 30 requests/min per key, 500/day per
account (shared with the other OpenRouter datasets sources).
**License:** CC BY 4.0 — reuse and republish with attribution to OpenRouter. The endpoint gives no
citation string; we credit "OpenRouter session cost by harness (openrouter.ai), as of {as_of}".
**Last verified:** 2026-10-07 (docs plus live requests; design in
`docs/plans/2026-10-07-openrouter-apps-session-cost.md`)

## What it contains
One weekly snapshot: for each published harness × model permaslug × turn range, the median USD
spend per session over a 30-day window (`meta.window_days`) ending on `meta.window_end_date` (a
Sunday; published Monday ~07:00 UTC). On 2026-10-07: 651 cells, four harnesses (`hermes-agent`,
`claude-code`, `kilo-code`, `codex`), 121 permaslugs. Turn ranges: `1-turn`, `2-9-turns`,
`10-49-turns`, `50-plus-turns`. Sessions are never pooled across harnesses. No session counts, no
spread, no tokens.

## Classification
- history: **snapshot** — there are no date parameters; only the current snapshot can be fetched.
  History starts at our first fetch (Author-only). Our raw snapshots are to be published in the
  PLAN §2.3 archive, which makes them reproducible for others.
- revisions: none (a snapshot is identified by its window; re-fetches of one window are kept and
  the latest is used)
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution

## Known quirks and caveats
- `meta.as_of` is when the response was generated (two pages of one snapshot differed by 32
  minutes), not a data revision; the snapshot is identified by `window_end_date`.
- The default `limit` (100) silently truncates; the unfiltered list is sorted by harness, turn
  range, then cost (ties possible at page boundaries). The adapter asks per turn range instead.
- Consecutive snapshots overlap by ~23 days: week-to-week changes are smoothed, not independent.
- Medians cannot be averaged across models, turn ranges or harnesses (no session counts).
- Model permaslugs use rankings-daily's convention (dated) and join `models.yaml`
  `aliases.openrouter` directly (113 of 121 on 2026-10-07; the rest only in Hermes Agent cells).
- Harnesses join app-rankings through `config/entities/apps.yaml` (slug → `app_id`); a slug
  missing there is reported in `or_session_cost_coverage`.
- "Session" and "turn" are OpenRouter's definitions and may differ between harnesses. Only traffic
  routed through OpenRouter is covered.

## Fetch strategy
Weekly: four requests (one per turn range, `limit=500`), each followed by `offset` pages while a
page is full. Every response must report the same window, else the fetch is retried once and then
fails (nothing written). The vintage is `{kind: snapshot, value: window_end_date, window_days,
as_of}`. A fetch can lag a new snapshot by up to a week but cannot skip one unless OpenRouter skips
a week; a missing week shows as a missing `window_end_date`.

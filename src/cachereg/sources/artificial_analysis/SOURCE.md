# Artificial Analysis — LLM data (`artificial_analysis`)

**Endpoint:** `GET https://artificialanalysis.ai/api/v2/data/llms/models` (key in the `x-api-key` header)
**Docs:** https://artificialanalysis.ai/api-reference
**Terms:** the Terms of Use and Data Platform Terms linked from the API reference
**Auth:** free API key (`ARTIFICIAL_ANALYSIS_API_KEY`); 1,000 requests/day; the docs ask that responses be cached.
**Licence:** none granted for redistribution of the data (see below)
**Attribution:** "Artificial Analysis (artificialanalysis.ai), as of {as_of}"
**Last verified:** 2026-10-23

## What it contains
One snapshot of every LLM Artificial Analysis lists (709 on 2026-10-23): `id`, `name` (with the
reasoning-effort variant, e.g. "Claude Opus 5.5 (Max, Default Fallback)"), `slug` (unique per
variant), `release_date`, `model_creator` (`name`, `slug`), `evaluations`, `pricing` (USD per
million tokens) and median speed and latency at a 1k-token prompt. `evaluations` holds the
Artificial Analysis Intelligence, Coding and Math indexes (0–100) and single evals as 0–1
fractions, including three Terminal-Bench versions: `terminalbench_hard`, `terminalbench_v2_1`
and `terminalbench_v4_0`. A null means "not evaluated".

## Classification
- history: **snapshot** — only current values can be fetched; there are no date parameters. History
  starts at our first fetch (Author-only, PLAN §4.4).
- revisions: none (each snapshot is kept; a re-fetch the same day is a new fetch and the latest wins).
- redistribution: forbidden · derived_charts: allowed-with-attribution.

## Licence verification (2026-10-23)
The API reference states: "Attribution is required for all use of our free API", crediting
artificialanalysis.ai. No licence for republishing the data itself is granted, so receipts publish
charts with the attribution, and `data.json`/HTML tables stay withheld (the render licence gate).

## Staged tables
`models` (one row per model per fetch) and `evaluations` (long: `fetch_id`, `slug`, `metric`,
`value` as published; nulls left out). Mart `120_artificial_analysis` reads one snapshot (`aa_models`,
`aa_evals`) and counts models without a release date (`aa_undated`).

## Known quirks and caveats
- **Scores are current, not historical.** AA re-runs models and re-versions its index and evals
  (the index has had several versions; Terminal-Bench went Hard → 2.1 → 4.0). A time series built
  from one snapshot places today's scores at each model's release date; it is not what AA showed
  at the time.
- Each reasoning-effort variant is its own model (own slug); choosing one per model is the
  analysis's decision.
- Not every model has every eval: on 2026-10-23, of 613 models released since 2025, 605 had an
  Intelligence Index and 225 had Terminal-Bench 4.0.
- There is no open-weights flag; analyses that need one must tag models themselves.
- Creator names are AA's (e.g. "Kimi" for Moonshot AI, "SpaceXAI").

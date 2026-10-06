# Epoch AI — Capabilities & benchmarking (`epoch_benchmarks`)

**Dataset page:** https://epoch.ai/benchmarks
**Fetched from:** `https://epoch.ai/data/benchmark_data.zip` (one zip, stored as served)
**Licence:** CC BY 4.0 — the zip's `README.md`: "Epoch AI's data is free to use, distribute, and
reproduce provided the source and authors are credited under the Creative Commons Attribution
license." Citation given there: Epoch AI, ‘Capabilities & benchmarking’. Published online at
epoch.ai. Retrieved from ‘https://epoch.ai/benchmarks’ [online resource].
**Attribution:** "Epoch AI, ‘Capabilities & benchmarking’ (epoch.ai/benchmarks), CC BY 4.0"
**Auth:** none. **Last verified:** 2026-10-06

## What it contains
- `epoch_capabilities_index/eci_scores.csv`: the Epoch Capabilities Index (ECI) per model group,
  with a confidence interval, release date, organisation and accessibility (274 models on
  2026-10-06).
- `model_metadata.csv`: every benchmarked **model version** (API id, optionally with a
  reasoning-effort suffix: `claude-sonnet-4-5-20250929`, `gpt-6.1-sol_max`,
  `claude-opus-4-5-20251101_16K`, host-prefixed ids such as `chutes/…`) and its **model group**
  (the ECI `Model` name, e.g. `Claude Sonnet 4.5`).
- `benchmark_metadata.csv`: per benchmark, whether it feeds ECI, the score file and the column to
  read, `scale` (a multiplier to 0–1: 1.0, 0.1 or 0.01), random baseline, ceiling, release date.
- About 80 per-benchmark CSVs keyed by `Model version`.

## Classification
- history: native · revisions: revised → **Latest-only** (PLAN §4.4). The zip is replaced in
  place several times a week with no version history. Each fetch holds the whole dataset (every
  model and date), so a replicator's own fetch is complete, but values may have been revised since
  (ECI especially). Past states exist only as local vintages; `native` + `revised` is the registry
  convention for this (as for `openrouter_rankings`).
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution (CC BY 4.0).

## Vintage rule
Every fetch stores the zip; its vintage is `{kind: content_sha256, value: <sha256 of the zip>}`
(the HTTP client keeps no headers, so the etag is not recorded). Staging parses each distinct
content once; `vintages` maps every fetch to the earliest fetch with the same content
(`vintage_id`). Mart `020_epoch_capabilities` reads one vintage: the latest fetch made on or
before `epoch_benchmarks_cutoff` (the build's Latest-only selection, falling back to the earliest
fetch, flagged).

## Staged tables
`vintages`, `models` (model_metadata), `eci`, `benchmarks` (metadata) and `scores` (long: one row
per published score row, `score` as published, `score_norm = score × scale`, `row`/`row_id` keep
repeated runs apart). Dates keep their precision (`release_date_precision`); the mart counts a
partial date from the end of its period. `_rejected_rows` counts non-numeric cells (including
`NaN`/`inf`), metadata rows with content but no model version, repeated model versions (the first
row is kept; on 2026-10-06 `deepseek-r1-0528-qwen3-8b` was listed twice with different dates) and
ECI rows without a model.

## Known quirks and caveats
- **ECI is re-fitted on every update.** A model's ECI at a past as-of is the value in the vintage
  fetched then, not a historical index; older vintages are not downloadable. Analyses over time
  must say capability scores come from one vintage while dates come from model releases.
- **Repeated rows**: ~1,000 score rows repeat a (benchmark, model version) pair (different agents,
  scaffolds or runs). All are staged; picking one per model is the analysis's decision.
- Some score rows have no `Model version`; they are staged with a null version and do not join.
- About 15 model versions have no release date; their scores cannot be placed before an as-of, so
  mart 020 leaves them out and counts them in `epoch_undated`.
- 27 benchmarks in `benchmark_metadata.csv` name no score file or column; their CSVs (in the zip)
  are not read, because the column is never guessed.
- Model versions are verbatim (a few upstream keys carry trailing spaces).
- Group names include dated variants (`Gemini 2.5 Flash (May 2025)`); mapping to canonical models
  goes through `config/entities/models.yaml` `aliases.epoch` (PLAN §4.3), proposed by
  `cachereg entities suggest --source epoch`.

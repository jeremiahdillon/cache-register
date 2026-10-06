# Epoch AI — Data on AI models (`epoch_models`)

**Dataset page:** https://epoch.ai/data/ai-models
**Fetched from:** `https://epoch.ai/data/ai_models.zip` (one zip, stored as served)
**Licence:** CC BY 4.0 — the zip's `README.md`: "Epoch AI's data is free to use, distribute, and
reproduce provided the source and authors are credited under the Creative Commons Attribution
license." Citation given there: Epoch AI, ‘Data on AI models’. Published online at epoch.ai.
Retrieved from ‘https://epoch.ai/data/ai-models’ [online resource].
**Attribution:** "Epoch AI, ‘Data on AI models’ (epoch.ai/data/ai-models), CC BY 4.0"
**Auth:** none. **Last verified:** 2026-10-06

## What it contains
`all_ai_models.csv` (3,626 models on 2026-10-06, 57 columns, `Model` unique) and three subsets:
`notable_ai_models.csv`, `frontier_ai_models.csv`, `large_scale_ai_models.csv`. Per model:
publication date, organisation, domain, task, parameters, training compute and its cost,
accessibility, open weights, country, base model.

## Classification
- history: native · revisions: revised → **Latest-only** (PLAN §4.4): replaced in place, no
  version history; each fetch is the whole dataset, past states only as local vintages (the same
  convention as `epoch_benchmarks`).
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution (CC BY 4.0).

## Vintage rule
As `epoch_benchmarks`: every fetch stores the zip, vintage = its sha256, staging parses each
distinct content once, and mart `021_epoch_models` reads the latest fetch on or before
`epoch_models_cutoff`.

## Staged table `models`
A fixed column subset of `all_ai_models.csv` plus membership flags `in_notable`, `in_frontier`,
`in_large_scale`. `publication_date` keeps its precision (`day`, `month`, `year`; partial dates
are stored as the first day of the period), and the mart counts a partial date from the **end** of
its period, so a model is never visible before it could have existed; models without a date (12 on
2026-10-06) are left out and counted in `epoch_models_undated`. `_rejected_rows` counts unparseable
cells (not rows). A subset file without a `Model` column fails staging.

## Known quirks and caveats
- A few subset rows are not in `all_ai_models.csv` (3 of 532 large-scale models on 2026-10-06);
  only models in `all_ai_models.csv` are staged.
- Model names are Epoch's display names (`Gemini 4 Argon`); about 50 ECI model groups are named
  differently here (dated or preview variants). Mapping goes through `aliases.epoch`.
- Parameters and compute are Epoch's estimates; their notes and confidence columns are not staged
  (see the dataset page).

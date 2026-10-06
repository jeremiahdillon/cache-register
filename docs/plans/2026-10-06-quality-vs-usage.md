# Plan: analysis (d) "does quality win usage?" (exploration)

Status: EXPLORATION BUILT · 2026-10-06

Outcome: `explore/2026-10-06-quality-vs-usage/` renders `x_png`, `linkedin_png` and `blog_html`. The
typical paid token buys capability the frontier reached ~9 months earlier (13-week median; ~5 months in
H1 2025); 5% of scored paid tokens go to models within 3 ECI points of the best on OpenRouter. Found
while building: `:free` permaslugs carry no `model_id` in `or_model_daily`, so the free-tokens
sensitivity resolves them through the paid model's alias.

## Question

Do OpenRouter tokens go to the most capable models? PLAN §10 starter analysis (d): Epoch
capability scores × OpenRouter `rankings-daily`. Built as an exploration
(`explore/2026-10-06-quality-vs-usage/`); promotion is a separate decision.

## What was measured (2026-10-06)

- `or_model_daily` joined to `epoch_eci` on `model_id`: paid tokens on ECI-scored models are 47–75%
  of each month's non-"other" tokens (about 60% in Sep 2026). The rest is free variants (5–18%) and
  models Epoch does not score (Tencent HY, Xiaomi MiMo, Solar, stealth names, …).
- A strict Pareto test (no other model that week is both at least as capable and at least as cheap)
  is too fragile: the largest model, DeepSeek V4.1 Flash (32% of scored paid tokens in the last
  week), flips in and out of the efficient set as its OpenRouter price swings day to day.
- Two measures are stable enough to report:
  - **Capability of the typical token:** the token-weighted median ECI per week, with the frontier
    (the highest ECI of any model Epoch lists as released by then). The median token's model has
    stayed 8–12 months behind the frontier through 2026, about 12 ECI points.
  - **Share near the frontier:** tokens on models within 3 ECI points of the best model in that
    week's OpenRouter top 50: under 8% of scored paid tokens in every week since June 2026.

## Design

- **Scope:** complete Monday–Sunday weeks from 2025-01-06; paid tokens (`:free` excluded) of models
  with an ECI (one Epoch vintage, as in analysis (a)); OpenRouter's "other" row excluded. Coverage
  (scored paid tokens ÷ all non-"other" tokens, 41–79% by week) reported per week. Sensitivity: free tokens added to
  their model.
- **Frontier:** max ECI over all Epoch models released on or before the week's end, mapped or not
  (the frontier exists whether or not the model is on OpenRouter). Also reported: the best model in
  that week's OpenRouter top 50.
- **Usage distribution:** token-weighted 25th, 50th and 75th percentile ECI per week.
- **Lag:** for the week's median ECI m, months since the first release with ECI ≥ m. Headline: the
  median lag over the last 13 complete weeks.
- **Near-frontier share:** tokens on models within 3 ECI points of the week's best top-50 model
  (sensitivity: 5 points).
- **Price premium** (secondary, table only): each model's price ÷ the cheapest price that week among
  top-50 models with at least its ECI; share of tokens within 2× of that.
- **Visual:** frontier line and median-token line with the interquartile band, on one ECI axis;
  `x_png`, `linkedin_png`, `blog_html`.

## Caveats to carry into the README

- OpenRouter only: developer traffic with free tiers and many cheap open models; first-party APIs
  (where frontier models sell most) are not in this data.
- About 40% of tokens are out of scope (free or unscored); unscored models are mostly cheap
  open-weight models, so including them would likely pull the median further from the frontier.
- One ECI vintage; models are scored at their best setting; tokens are counted by each model's own
  tokenizer.
- The top-50 cut hides small models, which only matters for the near-frontier share's denominator.

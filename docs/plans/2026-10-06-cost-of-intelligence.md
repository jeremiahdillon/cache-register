# Plan: analysis (a) "cost of intelligence" (exploration)

Status: EXPLORATION BUILT · 2026-10-06

Outcome: `explore/2026-10-06-cost-of-intelligence/` renders `x_png`, `linkedin_png` and `blog_html`.
GPT-5-level capability gets ~10× cheaper per token a year (9.6–12.9× across variants). Changes found
while building: a model's daily price is a trailing 28-day median (OpenRouter listings swing several-fold
within days), the headline uses the log-linear rate rather than the end-to-end fold (34× vs 17× with and
without the median), and 17 aliases were added (§3). Motion hero not started.

## Question

What is the cheapest list price at which a given level of capability can be bought, and how fast
has it fallen? PLAN §10 starter analysis (a): LiteLLM price history × Epoch capability scores.

Built as an exploration (`explore/2026-10-06-cost-of-intelligence/`); promotion to a receipt is a
separate decision.

## What was measured (2026-10-06, Epoch vintage of 2026-10-06, LiteLLM to 2026-10-05)

- `epoch_eci`: 274 models released 2023-02 → 2026-09, ECI 55.8–167.3; 154 mapped to a canonical
  model (47 of the top 50 by ECI). Epoch anchors the scale: Claude 3.5 Sonnet = 130.00 and
  GPT-5 = 150.00 exactly (no confidence interval on the anchors).
- `lp_price_intervals`: LiteLLM daily prices from 2025-01-01 (the staged floor), 5,099 keys.
- Of the mapped ECI models, every one with a release date in the window has at least one LiteLLM
  price. Many open-weight models are first listed in LiteLLM weeks or months after release
  (e.g. GLM-5.2: released 2026-06-16, first priced 2026-09-01).
- **Coverage gap that matters:** cheap models near the lower levels are unmapped, e.g.
  DeepSeek-V3 (132.3), DeepSeek-V3 (Mar 2025) (135.9), DeepSeek-V3.1 (139.9), Qwen3-235B-A22B
  (Jul 2025) (138.9), Kimi K2 (Jul 2025) (140.1), Gemini 1.5 Flash (Sep 2024) (129.4), Mistral
  Small 3.2 (131.7). Several already exist as canonical models in `models.yaml` (e.g.
  `deepseek/deepseek-chat-v3-0324`), only the `epoch` alias is missing. Missing cheap models bias
  the cheapest price **upwards** (later and higher), never downwards.

## Design

### 1. Capability measure: Epoch Capabilities Index (ECI), one vintage

- One ECI per Epoch model group, from the vintage selected by the build cutoff (020 mart).
  Epoch re-fits ECI on every update, so the chart is "capability as Epoch scores it today",
  placed at each model's release, not a historical index. The README says so.
- **Levels:** ECI ≥ 130 (Claude 3.5 Sonnet, Jun 2024), ≥ 140 (about o1, Dec 2024) and ≥ 150
  (GPT-5, Aug 2025), configurable in `explore.yaml`. 130 and 150 are Epoch's own anchors, so
  each level has a plain-language name ("Claude 3.5 Sonnet-level").
- Point estimate decides membership. Bound: a model qualifies only if `eci_ci_low ≥ level`
  (conservative) or `eci_ci_high ≥ level` (generous); both reported. Anchors (no CI) use their
  point value.
- One ECI per model group although Epoch scores a group at its best reasoning setting, while the
  price is per token at any setting (caveat below).

### 2. Price definition

- **Blended list price per million tokens** = 0.8 × input + 0.2 × output, the house blend used by
  `010_openrouter_usage` (one definition across analyses). Sensitivities: 3:1 (0.75/0.25) and
  output-only.
- A model's price on day D = the **cheapest** of its mapped LiteLLM keys valid at the end of D
  (`aliases.litellm`: OpenRouter's listing and the vendor's first-party key), then the median of
  that daily price over the trailing 28 days. Prices ≤ 0 (free tiers) are ignored. Sensitivities:
  preferred key only (rank 1); daily price without the median.
- **Cheapest price to reach level L on day D** = min over models with ECI ≥ L, released on or
  before D, with a price on D. The model that sets it is kept for labels.
- **Availability date:** Exact = a model counts from the later of its release and its first
  LiteLLM price (we only know a price from then). Bound: "back-filled", where a model counts from
  release with its first later price (the same rule `010` flags as `before_listing`). The README
  reports how much the two differ per level.
- A model that disappears from LiteLLM stops counting the day after its last entry.

### 3. Coverage

- Targeted alias pass before building: every unmapped ECI model with ECI ≥ 128 (lowest level
  minus a margin) gets an `epoch` alias on an existing canonical model when one unambiguously
  matches (`# manual` with reason), or a new canonical model with its OpenRouter / first-party
  LiteLLM keys. Hosts other than OpenRouter and the vendor are not added (keeps the price
  definition the same for every model). Pro-tier models (GPT-5 Pro, o3-pro, …) cannot set a
  minimum and stay unmapped if they have no key.
- Reported per level: models with ECI ≥ L, how many are mapped, and how many have a price.

### 4. Outputs (exploration)

- Story frames: `daily` (date, level, cheapest price, model), `steps` (each change of the
  setting model), `models` (ECI, release, first price, price now), `coverage`.
- Headline: the per-year rate of decline at the headline level (log-linear fit on the daily step
  series); the fold change from first to last day is reported but is less stable.
- Visual: step lines on a log price axis, one per level, latest setter labelled (`x_png`,
  `linkedin_png`, `blog_html`). Motion hero (lines drawing left to right) after the static chart
  reads well.

### 5. Caveats to carry into the README

- Price per token, not per task: reasoning models spend many more output tokens per task, so a
  cheaper per-token price can cost more per answer.
- List prices, no caching, batch or volume discounts; OpenRouter listings swing with the cheapest
  provider and are re-synced almost daily.
- ECI is one vintage (re-fitted by Epoch); scores are for each model's best published setting.
- Coverage: unmapped or late-listed cheap models make the series an upper bound.

Out of scope: a mart for (b) (promote the computation to `030_cost_of_intelligence.sql` when
analysis (b) needs it); third-party indices other than Epoch; new dependencies.

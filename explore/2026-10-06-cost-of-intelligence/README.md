# The cost of intelligence

*Exploration · started 2026-10-06 · design: [`docs/plans/2026-10-06-cost-of-intelligence.md`](../../docs/plans/2026-10-06-cost-of-intelligence.md)*

## Question
What is the cheapest list price at which a given level of capability can be bought, and how fast is it
falling? (PLAN §10, starter analysis (a).)

## Finding (Epoch vintage of 2026-10-06, prices to 2026-10-05)
- **GPT-5-level capability (ECI ≥ 150) is getting about 10× cheaper per token every year.** The cheapest
  blended list price fell from $3.00 per million tokens (GPT-5, Aug 7, 2025) to $0.088 (DeepSeek V4 Flash
  0731), a log-linear rate of 9.9× a year. Across the alternative definitions below the rate stays between
  9.6× and 12.9× a year (19× if models are counted from release, before LiteLLM lists them).
- **The fall is fastest at the frontier and slowest at the floor.** o1-level (ECI ≥ 140) fell 8× a year,
  from o1 at $24 to $0.05 (Qwen3.7 Flash). Claude 3.5 Sonnet-level (ECI ≥ 130) fell only 3.2× a year:
  DeepSeek-V3 already sold it for $0.17 on Jan 1, 2025, and it now costs $0.041 (gpt-oss-20b).
- **The levels are converging.** In October 2026 all three cost $0.04–$0.09 per million tokens, so
  GPT-5-level capability costs about twice the Claude 3.5 Sonnet-level price. A year earlier the gap was
  roughly 25×.
- The cheapest model is almost always a small or "Flash" tier released months after the level was first
  reached (GPT-5 nano, Gemini 2.5/3 Flash, Qwen and DeepSeek Flash models, gpt-oss-20b), not the model
  that set the level.

## Method
- **Capability:** the Epoch Capabilities Index (ECI) from the `epoch_eci` mart: one vintage, the latest
  Epoch fetch on or before the build cutoff. Epoch re-fits ECI on every update, so this is each model's
  score *as Epoch fits it today*, placed at the model's release date, not a historical index. Epoch
  anchors the scale at Claude 3.5 Sonnet = 130 and GPT-5 = 150, which name two of the levels; 140 sits
  near o1 (141.9). Levels are set in `explore.yaml`.
- **Price:** blended list price = 80% input + 20% output price per token (the house blend also used by
  `010_openrouter_usage`). A model's price on a day is the cheapest of its mapped LiteLLM keys valid that
  day (`aliases.litellm` in `config/entities/models.yaml`: OpenRouter's listing and the vendor's own API),
  then the **median of that daily price over the trailing 28 days**. OpenRouter listings follow the cheapest
  provider and swing several-fold within days (e.g. DeepSeek V4.1 Flash between $0.086 and $0.48 in
  September 2026); without the median the series would be set by one-day dips. Zero prices (free tiers)
  are ignored.
- **Cheapest price at level L on day D** = the lowest price among models with ECI ≥ L released on or before
  D that have a price on D. A model counts from the later of its release and its first LiteLLM listing,
  and stops counting when its last listing ends. A step *up* in a line means the cheapest model's listing
  ended (for example, a preview key renamed), not a price rise.
- **Rate:** the slope of a least-squares fit of log(price) on time over every day of the line, expressed
  as "× cheaper per year". The fold change between the first and last day is also reported; it is less
  stable because it depends on two single days.
- **Window:** from 2025-01-01 (the start of the staged LiteLLM history) to the last LiteLLM day.

### Sensitivity (per-year rate, ×)
One change at a time from the main definition (`story.frames["sensitivity"]`):

| Variant | ECI ≥ 130 | ≥ 140 | ≥ 150 |
|---|---|---|---|
| Main | 3.2 | 8.0 | 9.9 |
| Model qualifies only if its ECI lower CI bound ≥ level | 5.6 | 8.5 | 9.6 |
| Model qualifies if its ECI upper CI bound ≥ level | 2.6 | 7.5 | 12.9 |
| Counted from release, at its first later price | 1.9 | 10.3 | 18.9 |
| Blend 75% input / 25% output | 3.1 | 7.9 | 10.3 |
| Output price only | 2.3 | 8.0 | 12.8 |
| Preferred key only (no cheapest-of-keys) | 3.2 | 12.8 | 10.4 |
| Daily price, no 28-day median | 3.3 | 8.2 | 10.8 |

The GPT-5-level fold change is 34× with the 28-day median and 17× without it (the unsmoothed series ends on
GPT-6 Luna at $0.18, because DeepSeek V4 Flash 0731's OpenRouter price rose to $0.26 on Oct 1). The
headline uses the rate for that reason.

### Coverage
Models with an ECI and a release date, by level, and how many map to a canonical model with a LiteLLM
price (`story.frames["coverage"]`):

| Level | Models | Mapped and priced | Unmapped |
|---|---|---|---|
| ≥ 130 | 159 | 148 | Pro tiers (GPT-5 Pro, o3-pro), GPT-5.5 Instant, Muse Spark, Qwen2.5-Max, QwQ-32B, two R1 distills, three Gemini 2.0 experimental releases |
| ≥ 140 | 116 | 112 | Pro tiers, GPT-5.5 Instant, Muse Spark |
| ≥ 150 | 54 | 52 | Pro tiers, Muse Spark |

Seventeen cheap models near the lower levels were mapped for this analysis (DeepSeek-V3/V3-0324/V3.1,
Gemini 1.5 Flash/Pro 002, Mistral Small 3.2, Qwen3-235B-2507, Kimi K2 and others; `# manual` in
`models.yaml`). GPT-5.2 Pro and GPT-5.4 Pro are mapped too (`# manual`) but, like every Pro tier, never set a
minimum. The other unmapped models (QwQ-32B, Qwen2.5-Max, the R1 distills) have no unambiguous OpenRouter or
first-party key in LiteLLM; if they were cheaper, the ≥ 130 line would be lower early in 2025.

## Caveats
- **Price per token, not per task.** Reasoning models can use many more output tokens per answer, so a
  cheaper per-token price can still cost more per task. ECI is scored at each model's best published
  setting (often high reasoning effort), while the price applies at any setting.
- **List prices only:** no caching, batch or volume discounts.
- **Upper bound.** Unmapped models and late LiteLLM listings (many open-weight models are listed weeks or
  months after release, e.g. GLM-5.2: released Jun 16, listed Sep 1, 2026) can only make the true cheapest
  price lower or earlier. The "counted from release" row shows how much.
- **One ECI vintage.** A later Epoch update can move a model across a level and change the lines.
- DeepSeek's `deepseek-chat` key served successive models (V3, V3-0324, V3.1, …); DeepSeek-V3 is priced
  through it, which is safe for a "level reached" claim because each successor scores higher.

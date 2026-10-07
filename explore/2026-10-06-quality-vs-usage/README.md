# Does quality win usage?

*Exploration · started 2026-10-06 · design: [`docs/plans/2026-10-06-quality-vs-usage.md`](../../docs/plans/2026-10-06-quality-vs-usage.md)*

## Question
Do OpenRouter tokens go to the most capable models? (PLAN §10, starter analysis (d).)

## Finding (OpenRouter to 2026-10-04, Epoch vintage of 2026-10-06)
- **The typical paid token buys capability the frontier reached about 9 months earlier.** Over the 13 weeks
  to Oct 4, 2026, the token-weighted median model scored ECI 155 (DeepSeek V4.1 Flash), 12 points below
  the best model released (Claude Opus 5.5, 167). The frontier first reached 155 in December 2025.
- **The lag has grown.** It was about 5 months in the first half of 2025 (quarterly medians 4.9 and 5.1)
  and has been 8–10 months since mid-2025. The gap in ECI points grew from 6–8 to 12–13.
- **Little usage sits at the frontier.** Models within 3 ECI points of the best model on OpenRouter took 5%
  of scored paid tokens in the last 13 weeks (9% within 5 points). In Q1 2025 it was 44%, when Claude 3.5/3.7
  Sonnet were both the best and the most used.
- **Value matters, but not strictly.** About 59% of scored paid tokens in the last 13 weeks went to models
  within 2× of the cheapest top-50 price for their capability (29–80% by quarter). The largest models are the
  cheap "Flash" tiers: DeepSeek V4.1 Flash, GLM-5.3-Flash, GPT-6 Luna.

## Method
- **Tokens:** `or_model_daily` (OpenRouter rankings, daily top 50) for complete Monday–Sunday weeks from
  2025-01-06. Paid tokens only; OpenRouter's "other" row is excluded.
- **Capability:** Epoch Capabilities Index from `epoch_eci` (one vintage, as in analysis (a)), joined on the
  canonical `model_id`. `:free` permaslugs are resolved through their paid model's alias (used only in the
  free-tokens sensitivity).
- **Frontier:** the highest ECI of any model Epoch lists as released by the end of the week, whether or not
  it is on OpenRouter. The best model in that week's OpenRouter top 50 is also kept (`best_on_openrouter`);
  it was within 0–3 points of the frontier in every week since mid-2025.
- **Distribution:** token-weighted 25th, 50th and 75th percentile ECI of the week's scored paid tokens.
- **Lag:** for the week's median ECI m, the months (30.44 days) from the first release with ECI ≥ m to the end
  of the week. The headline is the median over the last 13 complete weeks (`summary_weeks`).
- **Near-frontier share:** tokens on models within 3 ECI points (`near_points`) of the week's best top-50 model.
- **Within 2× of cheapest:** a model's token-weighted blended price that week (`or_model_daily`, LiteLLM list
  prices, 80% input + 20% output) ÷ the cheapest price among that week's top-50 models with at least its ECI.
  Weekly prices are rounded to $0.000001 per million tokens before comparing, so a model at exactly 2× counts
  as within whenever both prices are whole multiples of that unit (list prices and their 80/20 blends are). Without the rounding, floating-point noise from the parallel sums made models priced at exactly 2×
  (e.g. $2.00 vs $1.00) flip in or out between rebuilds, moving single weeks by up to 9 points. The quarterly and
  13-week figures above did not change.

### Sensitivity (last 13 weeks)

| Variant | Lag (months) | Gap (ECI) | Near-frontier share | Coverage |
|---|---|---|---|---|
| Main | 9.3 | 12.0 | 5.1% | 61% |
| Free tokens included | 9.3 | 12.0 | 4.8% | 65% |
| Near = within 5 points | 9.3 | 12.0 | 8.9% | 61% |

**Coverage:** scored paid tokens ÷ all non-"other" tokens. It was 41–79% by week (61% over the last 13). The
rest is free variants and models Epoch does not score (Tencent HY3/HY4, Xiaomi MiMo, Upstage Solar, stealth
names, …).

## Caveats
- **OpenRouter only.** Developer-heavy traffic with free tiers and many cheap open models. First-party APIs
  and enterprise contracts, where frontier models sell most, are not in this data, so this is not a market-wide
  statement.
- **Out of scope tokens.** About 40% of tokens are free or on unscored models; the unscored ones are mostly
  cheap open-weight models, so including them would likely widen the gap.
- **The lag rises by construction when the frontier jumps** and falls when a cheaper, stronger model takes
  share; weekly values move in steps. The headline uses a 13-week median for that reason.
- **One ECI vintage**, scored at each model's best published setting; models used at low reasoning effort
  deliver less than their ECI suggests.
- **Tokens are counted by each model's own tokenizer**, so volumes are not strictly comparable.
- **Top-50 cut.** Models outside OpenRouter's daily top 50 are invisible; this mainly affects the
  "within 2× of cheapest" comparison set.

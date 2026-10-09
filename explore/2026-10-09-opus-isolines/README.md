# Opus isolines

*Exploration · started 2026-10-09 · follows [`2026-10-06-cost-of-intelligence`](../2026-10-06-cost-of-intelligence/README.md)*

## Question
Take each Claude Opus model as a fixed level of capability. How cheaply could a later model buy the same
capability, and which models set each new low? The original exploration uses round Epoch Capabilities Index
(ECI) levels (130/140/150); this one sets the levels at four Opus models, so each line is an isoline of
capability that starts at an Opus's own launch price.

## Finding (Epoch vintage of 2026-10-06, prices to 2026-10-05)
- **Opus 4, Opus 4.5 and Opus 4.6 were each matched at a tenth of their list price within 9 months** by a
  model released after them. The 10× point came after 2.5 months for Opus 4 (GPT-5 mini, $0.60 against $27),
  8.6 months for Opus 4.5 (GPT-5.6 Luna, $0.40 against $9) and 6.2 months for Opus 4.6 (GPT-5.6 Luna's price
  cut, $2 to $0.40 over Aug 13–14, 2026, against $9; GPT-6 Luna later reached $0.18).
- **Today:** Opus 4-level capability costs $0.05 (Qwen3.7 Flash, 540× below Opus 4's $27), Opus 4.5-level
  $0.088 (DeepSeek V4 Flash 0731, 102×), Opus 4.6-level $0.18 (GPT-6 Luna, 50×).
- **Opus 4.8 (May 2026) is 2.5× cheaper so far:** GPT-5.6 Terra at $5, then GPT-6 Sol at $3.60. GPT-5.6 Sol,
  Claude Sonnet 5.5 and GPT-6.1 Sol later matched $3.60 but did not go lower.
- The new lows come from a mix of vendors. Small and "Flash" tiers dominate (GPT-5 mini, Gemini 3 Flash,
  GPT-5.6/6 Luna, Qwen and DeepSeek Flash models, GLM-5.3-Flash). One is an Anthropic model that is not an Opus
  (Claude Sonnet 5 on the Opus 4.6 line). Seven different models set a new low on the Opus 4 line, five on
  Opus 4.5, four on Opus 4.6 and two on Opus 4.8.

## Method
- **Price:** the same definition as the cost-of-intelligence exploration: blended list price = 80% input +
  20% output per token, the cheapest of a model's mapped LiteLLM keys each day (OpenRouter or the vendor's own
  API), then the median over the trailing 28 days. Only days with a listing count. Zero prices are ignored.
- **Capability:** Epoch Capabilities Index, one vintage (`epoch_eci` mart). A model matches an Opus if its
  ECI point estimate is at least the Opus's.
- **Isoline for Opus A:** from A's first listed day, the lowest price so far among A and every model
  released on or after A's release date that matches it (a running minimum). Models released before A are
  excluded by design (see the sensitivity table for what that changes). At these levels the running minimum
  never sat above the day's cheapest listed price (`summary.days_above_record` = 0), so the line is also the
  cheapest price on offer each day.
- **Labels:** a dot and label mark the Opus itself and each day a *different* model sets a strictly lower
  price. Price cuts by the model already holding the low move the line without a label; a model that only
  ties the current low gets no label. The step down on the Opus 4.6 line in August 2026 is such a cut
  (GPT-5.6 Luna, $2 to $0.40), which is why that line shares a segment with the Opus 4.5 line.
- **10× point:** the first day the line is at or below a tenth of the Opus's launch price.
- **Video** (`isolines-motion`: `x_video`, `linkedin_video`): the lines draw one after another at the same pace
  in days per second, so a longer history takes longer; labels fade in as each new low is reached, finished
  lines dim while the next draws, and the last frame is the static chart. Label positions are computed once on
  the full chart, so nothing moves between frames.
- Anchors are set in `explore.yaml`. `story.frames`: `daily` (each line by day), `events` (labelled points),
  `summary`, `sensitivity`.

### Sensitivity
One change at a time (`story.frames["sensitivity"]`). Fold = Opus launch price ÷ today's line; months to
10× from the Opus's first listed day.

| Variant | Opus 4 | Opus 4.5 | Opus 4.6 | Opus 4.8 |
|---|---|---|---|---|
| Main: later models, ECI point estimate | 540×, 2.5 mo | 102×, 8.6 mo | 50×, 6.2 mo | 2.5×, not yet |
| Later models; candidate's ECI *lower* CI bound must clear the Opus | 307×, 2.5 mo | 102×, 8.6 mo | 6.7×, not yet | 2.5×, not yet |
| Any model, incl. released before the Opus (line starts at the cheapest match on day one) | 35× from $1.76, 9.6 mo | 45× from $4.00, 8.6 mo | 50×, 6.2 mo | 2.5×, not yet |

- **Opus 4.6's 10× depends on the point estimate.** If a model must clear Opus 4.6's ECI with its lower
  confidence bound, the cheapest match is Gemini 3.7 Flash at $1.35 (6.7×): the Luna models score 156.3–156.4
  against Opus 4.6's 155.2, inside each other's intervals. Opus 4 and 4.5 hold under either rule.
- **Older Opus models were not the cheapest way to their own capability at launch.** On Opus 4's first listed
  day, o4-mini (released a month earlier, ECI 145.6) already matched it for $1.76; on Opus 4.5's, Gemini 3 Pro
  (released a week earlier, ECI 152.9) matched it for $4.00. Measured from the cheapest match on that day, the fall is
  35× and 45×, not 540× and 102×. Opus 4.6 and 4.8 were the cheapest match on their first day.

## Caveats
- **Price per token, not per task.** Reasoning models can use many more output tokens per answer, so a
  cheaper per-token price can still cost more per task. ECI is scored at each model's best published
  setting (often high reasoning effort), while the price applies at any setting.
- **List prices only:** no caching, batch or volume discounts. Opus's launch price is its list price on its
  first listed day.
- **Matching on one index.** ECI summarises many benchmarks. A model that matches an Opus on ECI need not
  match it on any given task (coding, long context, tool use).
- **One ECI vintage.** Epoch re-fits ECI on every update; a later fit can move a model across an Opus's
  level and change who set each low.
- **Upper bound.** Unmapped models and late LiteLLM listings can only make a line lower or earlier.
- The window covers Opus 4 onward because staged LiteLLM history starts on 2025-01-01. Claude 3 Opus
  (ECI 126.9, Feb 2024) would need earlier prices.

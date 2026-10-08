# Chinese labs' share of OpenRouter spend

*Receipt · [cacheregister.dev/china-spend-share](https://cacheregister.dev/china-spend-share) · data as of 2026-10-07 ·
promoted from [`explore/2026-10-07-china-spend-share`](../../explore/2026-10-07-china-spend-share/) · token companion:
[`china-token-share`](../china-token-share/)*

## Question
The WSJ (2026-10-07, "The AI Price War Is Heating Up — and OpenAI Is Gaining Ground on Anthropic") charted
OpenRouter business spend split two ways, Anthropic vs OpenAI, converging to roughly even by September. On our
own OpenRouter data, what does that two-way split look like, and what changes when Chinese labs, which the
two-way view leaves out, are put back in?

## Finding (data to the week of Sep 28, 2026)
- **Two-way, our data agrees with the WSJ's endpoint.** Anthropic's share of Anthropic + OpenAI estimated spend
  fell from 98% (week of Jan 6, 2025) and 89% (week of Jan 5, 2026) to 47% in the week of Sep 28. It was 41% at
  its low in the week of Sep 14. (The WSJ's panel starts 2026 at about 75%; it is a different population: 120,000
  companies' billed spend, not public rankings priced at list.)
- **With Chinese labs added, the three are level.** Among Anthropic, OpenAI and Chinese labs, the week of Sep 28
  was OpenAI 35%, Chinese labs 33%, Anthropic 32%. Chinese labs rose from 1% (week of Jan 6, 2025) and 6%
  (week of Jan 5, 2026).
- **Chinese labs were the largest of the three** in the weeks of Aug 24, Aug 31, Sep 7 and Sep 21, 2026.
- **Most of Anthropic's lost share went to Chinese labs before OpenAI's gain.** From the week of Jul 13 to the
  week of Aug 31, Anthropic fell from 60% to 33% of the three while Chinese labs rose from 24% to 46% and OpenAI
  from 16% to 21%. OpenAI's rise is concentrated in September (21% → 35%).

## Visuals
In [`output/`](output/) (`output/manifest.json` records the data versions and hashes; `data.json` holds the
weekly figures behind the visuals):
- `push` — video (`x_video`, `linkedin_video`): the two-way split draws in (OpenAI below, Anthropic above), holds,
  then the Chinese-labs band grows in between them in the accent colour while the stack stays at 100%.
- `stack` — still of the final frame (`x_png`, `linkedin_png`).
- `push-bars` / `stack-bars` — the same video and still as stacked weekly bars: one bar per week with that week's
  actual (unsmoothed) shares. The sweep reveals one bar at a time.

## Data
- `openrouter_rankings` — daily tokens for the top-50 models (CC BY 4.0, OpenRouter).
- `litellm_prices` — LiteLLM's price file as it stood each day (MIT, BerriAI/litellm).
- Marts: `010_openrouter_usage` (`or_vendor_weekly`, `dim_vendor_alias`). Developers map to groups via
  `config/entities/vendors.yaml`; "Chinese labs" = every developer with `hq: CN` (DeepSeek, Alibaba (Qwen),
  Moonshot AI, Z.ai, MiniMax, Xiaomi, Tencent, StepFun, Ant Group, ByteDance Seed).

## Method
1. Estimated spend per developer per week, as in the `openrouter-wallet-share` receipt: daily tokens × that day's
   blended LiteLLM list price (80% input / 20% output); `:free` variants count as $0.
2. Monday–Sunday weeks from Jan 6, 2025 (91 weeks). OpenRouter's data has no rows for Jun 15 and Jul 15, 2025, so
   the weeks of Jun 9 and Jul 14, 2025 are computed from their other six days: these are shares, and a missing
   day removes traffic from all three groups. A week counts with 6 days only if a full week follows it, so a
   partial week at the end of the data never does.
3. Share = group spend ÷ (Anthropic + OpenAI + Chinese labs) spend that week. Google and every other developer
   are left out of the denominator: **14% of all estimated spend in an average week** (mean of the 91 weekly
   shares; the chart's note), 5% in the week of Sep 28, peaking at 33% (week of Nov 17, 2025, Google's high).
4. Display: the area visuals smooth each group's weekly spend 1-2-1 over 3 weeks (as in `open-middle`), then
   renormalise to 100% per week; their note says so. The bar visuals are unsmoothed. Findings use raw weekly
   figures.
5. Animation: the Chinese-labs spend is scaled from 0 to 1 over the push and every frame is renormalised, so the
   band grows from zero thickness at the OpenAI/Anthropic boundary.

## Caveats
- **Estimated spend, not revenue.** List prices, no negotiated discounts, **prompt caching ignored**, which
  overstates spend most for heavily cached coding traffic, so Anthropic's share is likely overstated.
- **Three-way denominator.** These shares are higher than shares of all OpenRouter spend (the receipt
  `openrouter-wallet-share` has those: Anthropic 29%, OpenAI 29%, Chinese labs 35% in the week of Sep 21).
- **OpenRouter only.** A routing marketplace whose users shop across models on price; it over-represents cheap
  and open models compared with first-party APIs, subscriptions (e.g. Claude Code) and cloud-marketplace
  contracts.
- **Prices recorded later.** When LiteLLM had no listing for a model on a day, the nearest-dated listing for the
  same model is used (the chart's method line says "or the nearest date listed"). Among the three groups:
  - **by spend,** up to about 45% of a week (late May – mid-June 2025), almost all Claude Sonnet 4's launch weeks
    before LiteLLM listed it; its price did not change after launch;
  - **by tokens,** up to 54% of a week (week of Aug 10, 2026; about 25% of that week's spend), mostly Chinese-lab
    models LiteLLM listed only in September 2026. A spot check found those listings equal to launch prices for
    the largest launches, except GLM-5.3 Flash (half price until Sep 9, so its spend is overstated about 2× for
    Aug 26 – Sep 9).
- **Unpriced launch traffic.** Xiaomi's MiMo-V2-Pro and MiMo-V2-Omni had no price for their launch weeks
  (Mar 16 – Apr 20, 2026; up to 27% of a week's tokens among the three groups) and count as $0. `open-middle`
  records a free launch week in late March; any paid use in the other weeks is missing, so Chinese labs' share is
  understated then.
- **Tokens are counted by each provider's own tokenizer.** Top-50 models per day only.

## Reproduce
`uv run cachereg reproduce receipts/china-spend-share` (after `cachereg fetch` of openrouter_rankings, litellm_prices and `cachereg build`). Token counts
come from OpenRouter's rankings dataset, which OpenRouter may revise in place, so a later fetch can differ.

Author: re-render the committed visuals with `cachereg render receipts/china-spend-share`.

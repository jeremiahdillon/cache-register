# DeepSeek vs US models on OpenRouter

*Receipt · [cacheregister.dev/deepseek-vs-us](https://cacheregister.dev/deepseek-vs-us) · data as of 2026-10-19
(OpenRouter rankings through Oct 18, 2026; last complete week Oct 12–18) · promoted from
[`explore/2026-10-19-deepseek-vs-us`](../../explore/2026-10-19-deepseek-vs-us/)*

## Question
How large is DeepSeek on OpenRouter compared with US models: with closed US models (by developer), and with every
US model, closed or open-weight? Weekly tokens since the start of 2026.

## Finding (data to the week of Oct 12, 2026)
- **DeepSeek served more tokens than all US models combined in the last two weeks:** 1.18× in the week of Oct 5
  (51.1T, DeepSeek's peak) and 1.09× in the week of Oct 12 (45.9T vs 41.9T). In the week of Sep 28 it was level
  (0.997×).
- **It has served more tokens than all closed US models every week since Sep 14** (5 weeks; 1.44× in the week of
  Oct 12: 45.9T vs 32.0T). It first did so in the week of Aug 3 (1.02×), and again in the week of Aug 17.
- **In the week of Oct 12 it served 3.8× the tokens of Anthropic, the largest US lab that week:** Anthropic 12.1T,
  OpenAI 11.3T, Google 5.0T (closed models only), xAI 0.1T, other closed US models 3.5T (almost all Meta's Muse
  Spark).
- **The rise is recent.** DeepSeek served 14% of closed US models' tokens in the week of Jan 5, 2026 and 67% in the
  week of Jul 6, 2026.

## Visuals
In [`output/`](output/) (`output/manifest.json` records the data versions and hashes; `data.json` holds the weekly
figures behind the visual). One visual, `build`: video for X and LinkedIn (`x_video`, `linkedin_video`, about 19 s),
and its final frame as the stills (`x_png`, `linkedin_png`).
- Grey bars grow one step at a time (Anthropic, + OpenAI, + Google, + other US closed incl. xAI, + US open weights),
  each from the line below, lifting a heavy line; the previous line turns light. Each step holds briefly, then its
  bottom edge wipes up into the line, and the next step grows on from there. Bars are clipped to their bounding
  lines (slices of the band between them; the first and last bars are half width).
- Then lime DeepSeek bars grow from the axis in front of the grey lines, lift the DeepSeek line and wipe up the same
  way.
- The end: thin grey lines for each step, the heavy all-US line and the heavy DeepSeek line. Lines join weekly values
  (unsmoothed); the y-axis is fixed throughout.

## Data
- `openrouter_rankings`: daily tokens for the top-50 models plus an `other` row (CC BY 4.0, OpenRouter).
- Marts: `005_openrouter_tokens` (`or_rankings_daily`). Each model's developer comes from `dim_vendor_alias` (the
  author prefix of the permaslug, from `config/entities/vendors.yaml`): DeepSeek = `deepseek`, US = `hq: US`.

## Method
1. Tokens per model per Monday–Sunday week, from Jan 5, 2026 (41 weeks) to the last complete week. `:free`
   variants are included under their model. Embedding models are excluded (as in `open-middle`).
2. **Open vs closed per model**, not per developer: `us_weights.yaml` lists regular expressions for US open-weight
   models (Gemma, gpt-oss, Llama, Nemotron, Microsoft's Phi/WizardLM/MAI-DS-R1, Arcee Trinity, Poolside Laguna,
   Thinking Machines Inkling), following `receipts/open-middle/tiers.yaml`. Every other US model counts as
   closed, including Meta's Muse models. `extra["us_closed_models"]` lists the closed US models by tokens.
3. The chart's steps: Anthropic, OpenAI, Google, "Other US closed" (xAI, Meta Muse, Amazon Nova, Perplexity) and US
   open-weight models; the findings list xAI on its own. All US = closed US + US open-weight.
4. **Identified models only** (the method line on the chart). Excluded: stealth models (`stealth/…`), OpenRouter
   routers, OpenRouter's `other` row (models outside the daily top 50) and developers without an entry in
   `vendors.yaml`. None of these counts on either side.

## Caveats
- **Tokens, not spend or revenue.** DeepSeek's models (mostly V4.1 Flash) cost far less per token than closed US
  models, so its share of spend is much smaller than its share of tokens.
- **Unattributed traffic is excluded**, and it is large: over the last 4 weeks stealth models served about 57T
  tokens and the `other` row about 43T. If a stealth model belongs to a US lab, the latest crossovers could reverse.
- **DeepSeek fine-tunes by other developers** (TNG's R1T Chimera, Nex-N1; about 2.5T in all) are not counted as
  DeepSeek.
- **Open-weight tags are hand-curated.** A new US model that publishes weights counts as closed until it is added to
  `us_weights.yaml`. Perplexity's `pplx-decider-v1.1-27b` (0.07T) is counted as closed for lack of information.
- **OpenRouter only.** It is a routing marketplace with free tiers, and it over-represents cheap, free and open
  models compared with first-party APIs, subscriptions and enterprise contracts. US labs' own APIs are not here.
- **Tokens are counted by each provider's own tokenizer**, so volumes are not strictly comparable.
- **Top-50 truncation:** a model drops into the `other` row on days it is outside the top 50, so the long tail of
  both groups is undercounted.

## Reproduce
`uv run cachereg reproduce receipts/deepseek-vs-us` (after `cachereg fetch` of openrouter_rankings and
`cachereg build --as-of 2026-10-19 --sources openrouter_rankings`). Token counts come from OpenRouter's rankings
dataset, which OpenRouter may revise in place, so a later fetch can differ.

Author: re-render the committed visuals with `cachereg render receipts/deepseek-vs-us`.

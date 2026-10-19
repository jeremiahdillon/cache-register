# DeepSeek vs US models on OpenRouter

*Exploration · started 2026-10-19 · data as of 2026-10-19 (OpenRouter rankings through Oct 19, 2026; last complete
week Oct 12–18)*

## Question
How large is DeepSeek on OpenRouter compared with US models: with closed US models (by developer), and with every
US model, closed or open-weight? Weekly tokens since the start of 2026.

## Finding (data to the week of Oct 12, 2026)
- **DeepSeek served more tokens than all US models combined in the last two weeks:** 1.18× in the week of Oct 5
  (51.1T, DeepSeek's peak) and 1.09× in the week of Oct 12 (45.9T vs 41.9T). In the week of Sep 28 it was level
  (0.997×).
- **It has served more tokens than all closed US models every week since Sep 14** (5 weeks; 1.44× in the week of
  Oct 12: 45.9T vs 32.0T). It first did so in the week of Aug 3 (1.02×), and again in the week of Aug 17.
- **In the week of Oct 12 it served 3.8× the tokens of Anthropic, the largest US lab that week:** Anthropic 12.1T, OpenAI 11.3T, Google
  5.0T (closed models only), xAI 0.1T, other closed US models 3.5T (almost all Meta's Muse Spark).
- **The rise is recent.** DeepSeek served 14% of closed US models' tokens in the week of Jan 5, 2026 and 67% in the
  week of Jul 6, 2026.

## Visuals
In `outputs/` (gitignored; `cachereg render explore/2026-10-19-deepseek-share`), each as `x_png` and `linkedin_png`:
- `lines` — weekly tokens: DeepSeek, closed US models, all US models.
- `stack` — closed US models as weekly bars stacked by developer (OpenAI, Anthropic, Google, xAI, other), DeepSeek
  as a line over them.
- `latest` — the latest week as three bars: DeepSeek, closed US models by developer, all US models (closed by
  developer plus open-weight).
- `build` — motion (`x_video`, `linkedin_video`, about 19 s; the stills are its final frame). Grey bars grow one
  step at a time (Anthropic, + OpenAI, + Google, + other US closed incl. xAI, + US open weights), each from the line
  below, lifting a heavy line; the previous line turns light. Each step holds 0.5 s, then its bottom edge wipes up into
  the line, and the next step grows on from there. Bars are clipped to their bounding lines (slices of the band
  between them; the first and last bars are half width). After a 1.5 s pause, lime DeepSeek bars grow from the axis
  in front, lift the DeepSeek line, hold and wipe up the same way. The end: thin grey lines for each step, the heavy
  all-US line and the heavy DeepSeek line. Labels settle once and never move: each step's label slides
  out from behind the previous one (DeepSeek's from behind "All US"). Lines join weekly values (unsmoothed); the y-axis is fixed throughout.

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
3. Closed US models are grouped as OpenAI, Anthropic, Google, xAI and "Other US closed" (Meta Muse, Amazon Nova,
   Perplexity). All US = closed US + US open-weight.
4. **Identified models only** (the method line on the charts). Excluded: stealth models (`stealth/…`), OpenRouter routers, OpenRouter's `other` row (models outside the
   daily top 50) and developers without an entry in `vendors.yaml`. None of these counts on either side.

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

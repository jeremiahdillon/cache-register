# Who gets paid on OpenRouter?

*Receipt · [cacheregister.dev/openrouter-wallet-share](https://cacheregister.dev/openrouter-wallet-share) ·
data as of 2026-10-02 · promoted from [`explore/2026-10-02-openrouter-wallet-share`](../../explore/2026-10-02-openrouter-wallet-share/)*

## Question
How is estimated developer spend on OpenRouter split between model makers, and how fast is
it shifting?

## Finding (as of 2026-10-02)
Anthropic took **93%** of estimated weekly spend on OpenRouter's top-50 models in the first
complete week of 2025 (week of Jan 6) and **29%** in the week of Sep 21, 2026. The fall is
recent: from March 2025 to June 2026 Anthropic's share stayed between 53% and 94% (its low was
the week of Nov 17, 2025, when Google peaked at 22%), and it was still **61%** in the week of
Jun 29, 2026. Over the same 87 weeks **Chinese labs combined** — Z.ai, Moonshot AI, Tencent,
DeepSeek, Xiaomi and others — rose from under 1% to **35%**, and **OpenAI** from 2% to **29%**.
Total estimated weekly spend on these models grew from ~$1.4M to ~$116M, so Anthropic's
decline is in *share* while the pie grew.

*Revision (2026-10-04):* the first version of this receipt (2026-10-02) priced every week with
one OpenRouter catalog snapshot and covered 13 weeks (Anthropic 66% → 30%). Each day is now
priced from LiteLLM's price history; for the same 13 weeks that gives Anthropic 61% → 29%,
OpenAI 29% and Chinese labs 35% in the last week (was 30% and 33%), and weekly spend ~$90M →
~$116M (was ~$82M → ~$113M). Earlier, before publication, a draft had said 69% → 32% because
84 models were counted twice through half-price `:batch` catalog variants; a test guards
against it.

## Visuals
In [`output/`](output/) — `output/manifest.json` records the data versions and hashes:
- `share-lines` — weekly share line chart: `x_png` (1600×900), `linkedin_png` (1080×1350),
  `blog_html` (interactive, with the weekly table).
- `share-race` — bar-race video, one keyframe every 4 weeks: `linkedin_video` (1080×1350),
  `x_video` (1920×1080).
- `data.json` — the weekly shares, spend and coverage behind the visuals.

## Data
- `openrouter_rankings` — daily tokens for the top-50 models (CC BY 4.0, OpenRouter).
- `litellm_prices` — LiteLLM's model price file as it stood at the end of each UTC day, from
  its git history (MIT, BerriAI/litellm); see `src/cachereg/sources/litellm_prices/SOURCE.md`.
- `config/entities/models.yaml` — which LiteLLM keys price each OpenRouter model (permaslug),
  in preference order.
- Mart: `010_openrouter_usage` (`or_model_daily`, `or_vendor_weekly`, `dim_vendor_alias`), see
  `src/cachereg/marts/010_openrouter_usage.sql`.

## Method
1. Daily tokens per model × that day's blended list price (80% input / 20% output) = estimated
   spend. `:free` variants count as $0.
2. Price of a model on day D: the first of its LiteLLM keys (OpenRouter's own listing
   `openrouter/<id>` first, then the developer's first-party key) that LiteLLM listed at the end
   of D. If none was listed that day, the listing nearest D among all of the model's keys is
   used and the row is flagged: the last listing before D if the keys were later removed,
   otherwise the **first listing after D** (the model was on OpenRouter before LiteLLM added it).
   Nothing LiteLLM recorded after the as-of date is used.
3. Model → developer via `config/entities/vendors.yaml` (author prefix of the permaslug).
   "Chinese labs" = developers headquartered in China.
4. Weekly (ISO weeks, Monday start), every complete week from Jan 6, 2025; share = developer
   spend / all priced top-50 spend that week.
5. Weeks where more than 3% of tokens have no price at all are shaded (26 of 88 weeks; mostly
   anonymous "stealth" models, which have no list price, and models LiteLLM never listed).

**Coverage, Jan 6, 2025 – Sep 27, 2026** (share of top-50, non-free tokens / of estimated spend):

| Price basis | Tokens | Est. spend |
|---|---|---|
| LiteLLM's listing on that day | 70% | 89% |
| First LiteLLM listing *after* that day (flagged) | 26% | 11% |
| No price (excluded) — of which stealth models 3.0 points | 4.0% | — |

The flagged share peaks at 46% of a week's tokens (week of Aug 10, 2026): LiteLLM added most
Chinese-lab models only on 2026-09-05 and 2026-09-18, weeks or months after their launch, so
their earlier weeks are priced at those listings. Their list prices are low, so this affects
much less of the spend than of the tokens.

## Caveats
- **Estimate, not revenue.** List prices; no negotiated discounts; **prompt caching ignored**,
  which overstates spend most for heavily cached coding traffic — so Anthropic's share is
  likely an upper bound.
- **Prices recorded later.** About a quarter of tokens (a tenth of estimated spend) are priced
  with a model's first LiteLLM listing after the day, for models LiteLLM hadn't listed yet (see
  Coverage). If those models were cheaper or dearer at launch, their share is mis-stated by that
  difference. A spot check of the largest Chinese-lab launches (2026-10-05) found the fallback
  prices equal to launch list prices for DeepSeek V4 Flash and V4 Pro (V4 Pro launched with a 75%
  discount, $0.435/$0.87, which DeepSeek extended and then made permanent; that is the price used),
  DeepSeek V4.1 Flash (off-peak rate; peak hours cost double), GLM-5.2, GLM-5.3 and Kimi K3. One
  exception: GLM-5.3 Flash launched at half its list price until Sep 9, 2026, so its spend is
  overstated about 2× for Aug 26 – Sep 9.
- **Promotions and peak pricing aren't in LiteLLM**, which records list prices; time-of-day
  pricing (e.g. DeepSeek's peak rate) and launch discounts are not modelled.
- **LiteLLM's OpenRouter prices move day to day.** Its `openrouter/` entries are re-synced from
  OpenRouter's catalog almost daily and follow the provider OpenRouter shows (e.g. one DeepSeek
  model's input price ranged $0.02–$0.30 per million tokens within two weeks of Sep 2026), so
  daily estimates for some open-weight models are noisy; weekly totals smooth part of it.
- **LiteLLM is community-maintained**: its prices can lag a vendor's change or be wrong.
- **Tokens are counted by each provider's own tokenizer** and aren't strictly comparable.
- **OpenRouter only** — third-party developer routing, not the whole market.
- Top-50 models per day only (the remaining ~4% of tokens has no per-model data).

## Reproduce this receipt on its own
Needs [uv](https://docs.astral.sh/uv/), `git`, and an `OPENROUTER_API_KEY` (any OpenRouter
key; see `.env.example`). From a clone of the repo, after installing dependencies with uv:

```sh
cachereg reproduce receipts/openrouter-wallet-share            # this receipt only
cachereg reproduce receipts/openrouter-wallet-share --latest   # same method, your latest data
```

`reproduce` fetches and builds only what this receipt needs, renders into a temporary folder
and compares a fingerprint of the underlying data with the committed run. **Prices reproduce
exactly**: every day maps to a fixed LiteLLM commit (the manifest pins the commit used for the
as-of date), whenever you fetch. **Token counts** come from OpenRouter's rankings dataset, which
OpenRouter may revise in place (Latest-only), so the result is identical unless OpenRouter has
revised past days since 2026-10-02; `reproduce` then names that source.

Author: re-render the committed visuals with `cachereg render receipts/openrouter-wallet-share`.

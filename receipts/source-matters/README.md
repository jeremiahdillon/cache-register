# Anthropic's share of AI spend and tokens, by data source

*Receipt · [cacheregister.dev/source-matters](https://cacheregister.dev/source-matters) · data as of 2026-11-20
(Ramp imported 2026-11-20, to the week ending 15 November; Databricks to the week of 2 November; gateways to
15 November) · promoted from
[`explore/2026-10-10-anthropic-share-by-source`](../../explore/2026-10-10-anthropic-share-by-source/) · design:
[`docs/plans/2026-10-10-anthropic-share-by-source.md`](../../docs/plans/2026-10-10-anthropic-share-by-source.md)*

## Question
Do the datasets that measure AI spend tell the same story about one lab? The author's thesis: each source sees
a different segment of the market, so none is fully representative of a lab's position. Taking each source's
figures as accurate for its own population, this receipt charts **Anthropic's share of all spend** and
**of all tokens** that each of four sources reports, weekly, on one axis per chart: Ramp (AI Token Spend
Management), Databricks (Unity Gateway; added 2026-11-18), Vercel AI Gateway and OpenRouter. Every line is the
same measure, a lab's share of its source's reported total, so the sources share one axis (author decision;
analysis (e)'s "never on one axis" rule concerned different measures).

## Findings (data as of 2026-11-20)
- **The sources still disagree on the level.** Latest 4-week averages, each source to its own latest week:
  spend **63% on Databricks** (to 8 November; 58–66% across the open-weight price range below), **55% on
  Ramp**, **39% on Vercel** and **35% on OpenRouter** (to 15 November). Tokens: **58% on Ramp, 45% on
  Databricks, 12% on Vercel, 7% on OpenRouter** (free models included; frame `weekly`, `rolling4_pct`). In the
  last week all four cover (ending 8 November): spend 63.3 / 55.0 / 37.1 / 35.3 (Databricks, Ramp, Vercel,
  OpenRouter), tokens 57.9 / 44.9 / 12.5 / 6.9 (Ramp, Databricks, Vercel, OpenRouter).
- **Ramp and OpenRouter fell together through 2025 Q3, then parted.** Spend: Ramp fell from 72% (2025 Q1 mean
  of weeks) to 46% (Q3) and OpenRouter from 93% to 70%; from 2025 Q4 Ramp rose to 69% (2026 Q2) while
  OpenRouter held at 62–64%. Tokens: Ramp fell from 62% to 30% (Q1 to Q3 2025), then rose to 66% (2026 Q2),
  while OpenRouter fell from 42% to 15% (free models included; 45% to 16% paid only) and Vercel from 52%
  (2025 Q4) to 31%. (Until Ramp's revision of 2026-11-20, below, Ramp rose through 2025.)
- **Since mid-2026 every source shows Anthropic's spend share falling, from different levels.** From 2026 Q2 to
  the weeks of Q4 so far: Ramp 69.4 → 55.9, Vercel 64.0 → 39.0, OpenRouter 63.8 → 34.7. Databricks, whose
  series starts in July, fell from 84% (week ending 26 July) to 64% (8 November), with Anthropic's share of
  proprietary spend down from 85.6% to 70.1% and open-weight models up to ~31% of its tokens.
- **Databricks sits highest on spend and second on tokens.** Its enterprises put 63% of spend on Anthropic,
  above every other source, but 45% of tokens, below Ramp's 58%: on Databricks, open-weight models carry ~31%
  of tokens but, at list prices, only ~8% of spend.
- **Ramp has revised its token history twice in November.** The import of 2026-11-18 raised Anthropic's token
  share by 10–14 points per quarter in 2026 Q2–Q3 against the 2026-10-07 import (OpenAI's token volume revised
  down; spend ≤ 1.6 points). The import of 2026-11-20 rewrote 2025: Anthropic's spend share in the week ending
  12 January 2025 went from 34% to 73% and its token share from 14% to 59%; 2025 Q1 spend from 38% to 72%,
  Q3 from 45% to 46%; recent weeks moved 1–3 points. The new paste matches Ramp's own page (58.7% of token
  spend in the week ending 15 November). Ramp does not say why; its customers who connect provider accounts
  may bring their history with them, which would rewrite past weeks as the population changes.
- **Free variants hardly move Anthropic's OpenRouter token share** (0.4–3.3 pp lower per quarter with them):
  Anthropic has no free models, so free tokens only enlarge the denominator.
- **What this shows and does not show.** The same measure at different levels says the sources see different
  slices of the market, or measure spend differently (below); it does not say which is closest to the whole
  market, and it does not size any slice. Part of the spend gap is likely method: OpenRouter's and
  Databricks' spend are list-price estimates that ignore caching (which probably overstates Anthropic), and
  Databricks' all-model share rests on our estimate of the open-weight share of its spend. The token gap is
  method-free in that sense (counts, not prices), apart from tokenizers and Databricks' rescaling (published
  shares only).

## Visuals
In page order (`tokens-with-free` first: it leads the receipt page and the root reel and is the share card;
author, 2026-10-10):
- `tokens-with-free`: Anthropic's share of all reported tokens, Ramp / Databricks / Vercel / OpenRouter,
  weekly dots and a trailing 4-week line per source on one 0–100% axis, OpenRouter including its free models
  (author decision 1). A paid-only token view was dropped on 2026-10-10 (author: it did not change the story);
  its series stays in frame `weekly` (`variant = paid`).
- `spend`: the same for spend; OpenRouter's band is its sensitivity to unpriced tokens, Databricks' band its
  sensitivity to the open-weight price estimate (× ½ to × 2).

**Each line runs to its own source's latest week** (author, 2026-11-18; before, every line stopped at the latest
week all sources covered). The end labels stand in one column after the latest week; a line that ends earlier
(on 2026-11-20, Databricks) reaches its label by a thin grey leader. The subtitle gives each source's latest 4-week
value with the week it ends. Both share one headline, "Different data sources tell different stories about the
AI economy" (author's framing); the measure is stamped on the chart's face (upper right). Colours are fixed per
source and close to each source's brand, tuned for the dark canvas and legibility: Ramp yellow-green
(`#C4D00A`), OpenRouter purple (`#9C6BFF`), Vercel sky blue (`#0AA3D6`), Databricks rose (`#F0466E`, its
"lava" red `#FF3621` moved away from Anthropic's orange; validator, dark canvas, all pairs: CVD worst ΔE 9.2,
normal 19.7, contrast ≥ 3:1). None is Anthropic's orange, since every line is Anthropic.

**Videos** (both visuals; `x_video`, `linkedin_video`, `web_video`, 30 fps): the weekly dots sweep in bright
from left to right; each line then draws in turn, Ramp, OpenRouter, Vercel, Databricks, at one calendar speed
(so shorter histories draw faster); once a line is drawn, its dots dim and its end label (and leader) fades
in; on `spend`, OpenRouter's and Databricks' bands fade in after their lines; a 5-second hold on the final
frame, which is byte-identical to the static chart. Every frame keeps the final frame's fitted size.

The visuals carry the short link `cacheregister.dev/source-matters`. The token visuals credit Ramp, Vercel,
OpenRouter and Databricks (they use no prices); `spend` also credits LiteLLM. Rendered as PNG and video; no
target inlines the data (see Licence).

## Tables

**Quarterly means of weekly values (%)** (frame `weekly`; each source on its own weeks; 2026 Q4 = weeks to
15 November, Databricks to 8 November):

| Quarter | Ramp spend | Databricks spend (est.) | OpenRouter est. spend | Vercel spend | Ramp tokens | Databricks tokens | OpenRouter tokens, paid | OpenRouter tokens, all | Vercel tokens |
|---|---|---|---|---|---|---|---|---|---|
| 2025 Q1 | 72.3 | — | 92.7 | — | 61.6 | — | 45.0 | 41.7 | — |
| 2025 Q2 | 53.2 | — | 77.7 | — | 48.0 | — | 26.0 | 22.8 | — |
| 2025 Q3 | 45.6 | — | 69.8 | — | 30.1 | — | 22.6 | 19.6 | — |
| 2025 Q4 | 60.9 | — | 62.1 | 76.8 | 45.3 | — | 15.7 | 14.3 | 52.2 |
| 2026 Q1 | 65.3 | — | 63.8 | 77.4 | 54.5 | — | 16.4 | 14.9 | 44.0 |
| 2026 Q2 | 69.4 | — | 63.8 | 64.0 | 65.9 | — | 16.1 | 14.6 | 30.8 |
| 2026 Q3 | 62.2 | 73.9 | 40.7 | 59.4 | 61.3 | 54.3 | 8.2 | 7.2 | 21.7 |
| 2026 Q4 | 55.9 | 63.9 | 34.7 | 39.0 | 58.0 | 45.1 | 6.6 | 6.2 | 12.7 |

(Databricks 2026 Q3 = its 10 weeks from the week ending 26 July.)

**OpenRouter spend estimate: bound and sensitivity, quarterly means of weekly values (%)** (frame
`or_bound_quarterly`):

| Quarter | Computed (upper bound) | Sensitivity (unpriced at mean price) | Lower bound (unpriced at dearest price) | Unpriced share of paid tokens |
|---|---|---|---|---|
| 2025 Q1 | 92.7 | 87.4 | 70.8 | 5.7 |
| 2025 Q2 | 77.7 | 70.5 | 49.4 | 9.1 |
| 2025 Q3 | 69.8 | 63.8 | 33.1 | 8.5 |
| 2025 Q4 | 62.1 | 56.4 | 35.9 | 9.3 |
| 2026 Q1 | 63.8 | 56.3 | 40.1 | 11.8 |
| 2026 Q2 | 63.8 | 54.0 | 34.2 | 15.4 |
| 2026 Q3 | 40.7 | 37.0 | 20.1 | 9.5 |
| 2026 Q4 | 34.7 | 32.3 | 15.7 | 7.1 |

**Databricks: the spend-mix estimate, latest week (week of 2 November, ending 8 November)** (frames
`dbx_weekly`, `dbx_coverage`): Anthropic 61.5% of proprietary tokens × proprietary 69.1% of tokens = 42.5% of
all tokens; 70.1% of proprietary spend × (1 − 8.2% open-weight share of spend) = 64.4% of all spend (59.5–67.1%
with open-weight prices × 2 to × ½). Mean list prices behind the 8.2%: proprietary $5.75 per million tokens,
open-weight $1.15 (blended); the named, priced models carry 86.6% of proprietary and 96.4% of open-weight
tokens. From the week of 20 July to 2 November the open-weight share of tokens rose from 7.3% to 30.9%, and its
estimated share of spend from 1.7% to 8.2%.

**Checks** (frames `first_last`, `partial_weeks_dropped`, `coverage`, `checks`, `dbx_coverage`): Ramp's maker
shares sum to 100% every week; Anthropic is present in every week drawn for each source (lowest weekly spend
share: Ramp 36.0% over 97 weeks, OpenRouter 24.5% over 97, Vercel 34.1% over 58, Databricks 61.1% over 16).
Ramp and OpenRouter from the week ending 2025-01-12, Vercel from 2025-10-12, Databricks from 2026-07-26; last
weeks: Databricks 2026-11-08, Ramp, OpenRouter and Vercel 2026-11-15. Dropped as partial: the first
weeks (OpenRouter 2025-01-05, Vercel 2025-10-05, 5 days each) and the current week. No week drawn has unpriced
Anthropic tokens on OpenRouter (Claude Fable 5.2, on OpenRouter from 2026-11-09, mapped to LiteLLM's
`claude-fable-5-2` on 2026-11-18; the analysis stops once a week drawn has any).

## Method
- **Weeks:** Monday–Sunday, dated by the Sunday (Ramp's convention); a gateway week needs at least 6 of its 7
  days (`min_days`). Databricks' weeks are its own ("week of" a Monday), dated by that week's Sunday.
- **Ramp:** `ramp_token_share` (mart 062): Anthropic's share of the week's token spend (`spend`) or token
  volume (`volume`) over every maker Ramp reports (13–14 a week in the 2026-11-20 import, including TypeSafe
  and Thinking Machines Lab; the 2026-11-18 import listed 8). Shares sum to 100% every week.
- **Databricks:** marts 095/096 (`dbx_vendor_share_week`, `dbx_vendor_spend_week`). The page publishes shares
  *within* proprietary and *within* open-weight models (to 0.1 point) and the proprietary / open-weight mix of
  tokens. **Tokens:** Anthropic's share of proprietary tokens × the proprietary share of all tokens.
  **Spend:** the page gives no spend mix, so it is estimated: within a segment, a model's wallet share ÷ its
  token share is its list price ÷ the segment's mean price, so the segment's mean price is Σ tokens × price ÷
  Σ wallet over its named models with a LiteLLM price (0.8 × input + 0.2 × output, the week's Sunday; the
  nearest listing when none that day, flagged). The open-weight share of spend is then T_open × P_open ÷
  (T_open × P_open + T_prop × P_prop), and Anthropic's share of all spend its share of proprietary spend × (1 −
  that). The band repeats this with open-weight prices doubled and halved.
- **Vercel:** `vercel_lab_share` (mart 090): the mean of the week's daily Anthropic shares of spend or tokens.
- **OpenRouter:** `or_model_daily` (mart 010): Anthropic's tokens or estimated spend in the week ÷ the week's
  total (volume-weighted). Spend and the `paid` token variant exclude free models; the `all` variant includes
  them. Tokens with no price count as no spend.
- **OpenRouter spend estimate:** tokens × (0.8 × input + 0.2 × output) LiteLLM list price, caching ignored.
  LiteLLM dropped every `openrouter/…` key on 2026-10-09. Since then a model is priced from a **fallback**
  key (`litellm_fallback` in `config/entities/models.yaml`: the lab's own LiteLLM key, else a host's key at
  the most common host price; 15 models) on days when all its `litellm` keys have been removed, else from its
  last OpenRouter listing (`price_date_stale`: 1–15% of paid tokens per week since 11 October, 16–48% before
  the fallbacks); days before the removal are priced as before. 14 models that reached OpenRouter's top 50
  after 2026-10-09 were mapped on 2026-11-18 (`# manual 2026-11-18`). **Upper bound** = as computed; **lower
  bound** = unpriced paid tokens at the week's dearest priced blended price; **sensitivity** = unpriced paid
  tokens at the week's mean priced price. The chart shades [sensitivity, computed] (author decision 4).
- **Smoothing:** trailing mean over 4 consecutive weeks; a missing week would break the line for four weeks.
- **Headline:** each chart's values are each source's 4-week mean at its own latest week.

## Licence
Ramp's and Databricks' redistribution rights are unknown, so no target inlines their data: no `blog_html` or
`data.json` (Ramp: derived charts allowed with attribution; Databricks: no licence or terms stated, author
policy 2026-11-18: derived charts with attribution as fair use, no republication of the series; Vercel and
OpenRouter rankings: CC BY 4.0; LiteLLM: MIT). The frames are not published.

## Caveats
- **Four populations, none of them the market.** Ramp: businesses on Ramp that connected their AI provider
  accounts to Ramp (Ramp: not representative of its total AI spend, though directionally similar).
  Databricks: enterprises routing model calls through Unity Gateway (external providers included). Vercel and
  OpenRouter: developers who route through that gateway; first-party API use is invisible to all three
  gateways, and each one's mix of apps shapes its shares.
- **Spend is measured four ways.** Ramp: realised spend (cached-token discounts apparently included). Vercel:
  Vercel's measure (whether bring-your-own-key traffic, discounts or caching are included is not stated).
  Databricks: its list-price "wallet share" (not what it bills), rescaled by our list-price estimate of the
  open-weight share. OpenRouter: our list-price estimate, caching ignored, partly from stale prices since
  October 2026 (above). Some of the spend gap between sources may therefore be method, not segment.
- **Databricks** is new (weeks from 20 July 2026), published to 0.1 point, read from the page's embedded chart
  data (no download or API), and its all-model shares are our rescaling of its proprietary-only shares (the
  page's headline figures are of proprietary models only: Anthropic 61.5% of proprietary tokens in the week of
  2 November is ~42% of all tokens).
- **Weighting:** Ramp and OpenRouter weeks are volume-weighted; Vercel's are means of daily shares; Databricks'
  are as published.
- **Denominators** are each source's own reported total: Ramp's 8 makers, every Vercel lab, every Databricks
  model (with its "Other" buckets), OpenRouter's top 50 models plus its tail.
- **Tokens** are counted by each provider's tokenizer, so token shares compare labs only roughly.
- All four sources are Latest-only (revised): figures move with each fetch and import, as Ramp's token history
  did on 2026-11-18 and again on 2026-11-20. Vercel's history starts in October 2025, Databricks' in July 2026.

## Output
In [`output/`](output/): `tokens-with-free` and `spend`, each as `x_png`, `linkedin_png`, `x_video`,
`linkedin_video` and `web_video`. `output/manifest.json` records the data versions and hashes; `data.json` is
withheld (Ramp's and Databricks' redistribution rights are unknown; the manifest's `withheld` says why).

## Reproduce
`uv run cachereg reproduce receipts/source-matters` (after `cachereg fetch` of ramp_ai_index, vercel_ai_gateway,
openrouter_rankings, litellm_prices and databricks_ai_index, and `cachereg build`). All four share sources are
Latest-only (revised), so a later fetch can differ from the committed render.

Author: re-render the committed visuals with `cachereg render receipts/source-matters`.

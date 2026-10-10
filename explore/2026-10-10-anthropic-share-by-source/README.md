# Anthropic's share of AI spend and tokens, by data source

*Exploration · started 2026-10-10 · design: [`docs/plans/2026-10-10-anthropic-share-by-source.md`](../../docs/plans/2026-10-10-anthropic-share-by-source.md)*

## Question
Do the datasets that measure AI spend tell the same story about one lab? The author's thesis: each source sees
a different segment of the market, so none is fully representative of a lab's position. Taking each source's
figures as accurate for its own population, this exploration charts **Anthropic's share of all spend** and
**of all tokens** that each of three sources reports, weekly, on one axis per chart: Ramp (AI Token Spend
Management), Vercel AI Gateway and OpenRouter. Every line is the same measure, a lab's share of its
source's reported total, so the sources share one axis (author decision; analysis (e)'s "never on one axis"
rule concerned different measures).

## Findings (Ramp import of 2026-10-07; gateways to 2026-10-08; latest common week ending 27 September 2026)
- **The sources disagree on the level.** Anthropic's share of spend over the four weeks to 27 September 2026:
  **53% on Ramp, 47% on Vercel, 28% on OpenRouter** (frame `weekly`, `rolling4_pct`). Of tokens: **42% on
  Ramp, 11% on Vercel, 4% on OpenRouter** (3% with OpenRouter's free models included).
- **They disagreed on the direction for most of 2025.** Spend: Ramp rose from 38% (2025 Q1 mean of weeks) to
  55% (Q4) while OpenRouter fell from 93% to 62%. Tokens: Ramp rose from 18% (2025 Q1) to 53% (2026 Q2)
  while OpenRouter fell from 45% to 16% (paid tokens) and Vercel from 52% (2025 Q4) to 31%.
- **In 2026 the spend lines move together but stay apart.** From 2026 Q2 to Q3 all three fell (Ramp 64.9 →
  58.6, Vercel 64.0 → 59.4, OpenRouter 63.8 → 40.7); in September the gap between Ramp and OpenRouter was
  ~25 points.
- **Free variants hardly move Anthropic's OpenRouter token share** (1.0–3.3 pp lower per quarter with them):
  Anthropic has no free models, so free tokens only enlarge the denominator.
- **What this shows and does not show.** The same measure at different levels and in different directions
  says the sources see different slices of the market, or measure spend differently (below); it does not say
  which is closest to the whole market, and it does not size any slice. Part of the spend gap is likely
  method: OpenRouter's spend is a list-price estimate that ignores caching, which probably overstates
  Anthropic: while OpenRouter is the lower line (as in September 2026), correcting for caching would
  probably widen its gap to Ramp, not close it; in early 2025, when OpenRouter was the higher line, the same
  correction would narrow the gap (the lower bound still leaves OpenRouter above Ramp in 2025 Q1). The token gap
  is method-free in that sense (counts, not prices), apart from tokenizers.

## Visuals
- `spend`: Anthropic's share of all reported spend, Ramp / Vercel / OpenRouter, weekly dots and a trailing
  4-week line per source on one 0–100% axis; OpenRouter's band is its sensitivity to unpriced tokens.
- `tokens`: the same for tokens, OpenRouter paid models only.
- `tokens-with-free`: the same, OpenRouter including free models (author decision 1).
All three share one headline, "Different data sources tell different stories about the AI economy": Anthropic
is a large part of AI spend and tokens, so if the sources disagree this much about it, they tell different
stories about the whole (author's framing). The subtitle gives each chart's values; the measure is stamped on
the chart's face (upper right), with how to read dots and lines. Each line ends at the latest week all three
sources cover (the subtitle's week); colours are fixed per
source (Ramp cyan, Vercel magenta, OpenRouter gold; not Anthropic's orange, since every line is Anthropic).
The visuals carry the reserved short link `cacheregister.dev/source-matters`, which redirects here until a
receipt promoted from this exploration takes it over. The token visuals credit only Ramp, Vercel and
OpenRouter (they use no prices); `spend` also credits LiteLLM. Rendered as `x_png` and `linkedin_png` only
(see Licence). Every chart's PNG equals its plot box exactly
(measured for all six visual × target pairs).

## Tables

**Quarterly means of weekly values (%)** (frame `weekly`; each source on its own weeks with ≥ 6 days):

| Quarter | Ramp spend | OpenRouter est. spend | Vercel spend | Ramp tokens | OpenRouter tokens, paid | OpenRouter tokens, all | Vercel tokens |
|---|---|---|---|---|---|---|---|
| 2025 Q1 | 38.0 | 92.7 | — | 18.2 | 45.0 | 41.7 | — |
| 2025 Q2 | 44.4 | 77.7 | — | 23.2 | 26.0 | 22.8 | — |
| 2025 Q3 | 43.8 | 69.8 | — | 25.7 | 22.6 | 19.6 | — |
| 2025 Q4 | 55.0 | 62.1 | 76.8 | 33.1 | 15.7 | 14.3 | 52.2 |
| 2026 Q1 | 62.0 | 63.8 | 77.4 | 43.6 | 16.4 | 14.9 | 44.0 |
| 2026 Q2 | 64.9 | 63.8 | 64.0 | 52.5 | 16.1 | 14.6 | 30.8 |
| 2026 Q3 | 58.6 | 40.7 | 59.4 | 45.7 | 8.2 | 7.2 | 21.7 |

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

Even the lower bound puts OpenRouter's 2025 Q1 share (70.8%) above Ramp's (38.0%), and the sensitivity keeps
OpenRouter's 2025 fall (87 → 56%) against Ramp's rise.

**Checks** (frames `first_last`, `partial_weeks_dropped`, `coverage`, `checks`): Ramp's maker shares sum to 100% every
week; Anthropic is present in every week drawn for each source (lowest weekly spend share: Ramp 31.2% over 90
weeks, OpenRouter 24.5% over 91, Vercel 37.3% over 52).
 Ramp and OpenRouter from the week
ending 2025-01-12, Vercel from 2025-10-12; Ramp's last week ends 2026-09-27, the gateways' 2026-10-04 (not
drawn). OpenRouter's rankings miss two days (2025-06-15 and 2025-07-15), so its weeks ending 2025-06-15 and
2025-07-20 have 6 days and are kept (config `min_days: 6`; flagged by `days` in frame `weekly`). Dropped as
partial: the first weeks (OpenRouter 2025-01-05, Vercel 2025-10-05, 5 days each) and the current week. No
week drawn has unpriced Anthropic tokens on OpenRouter (Claude Haiku 5.5, unmapped since 2026-10-08, falls
in the current partial week; the analysis stops once a week drawn has any).

## Method
- **Weeks:** Monday–Sunday, dated by the Sunday (Ramp's convention); a gateway week needs at least 6 of its 7
  days (`min_days`): a share over six days is a fair estimate of the week's (OpenRouter's is volume-weighted
  over the days present, Vercel's the mean of the daily shares present).
- **Ramp:** `ramp_token_share` (mart 062): Anthropic's share of the week's token spend (`spend`) or token
  volume (`volume`) over every maker Ramp reports (3 in January 2025, up to 14 by mid-2026; shares sum to
  100% every week; makers added from August to November 2025 held ≤ 0.1% of spend in their first week:
  Cursor 0.06%, the rest ≤ 0.001%; frame `checks`).
- **Vercel:** `vercel_lab_share` (mart 090): the mean of the week's daily Anthropic shares of spend or
  tokens (Vercel publishes no volumes); a day without an Anthropic row would count 0.
- **OpenRouter:** `or_model_daily` (mart 010): Anthropic's tokens or estimated spend in the week ÷ the
  week's total (volume-weighted, like Ramp; author decision 3). Spend and the `paid` token variant exclude
  free models; the `all` variant includes them. The total includes OpenRouter's `other` (long tail),
  stealth and router rows; tokens with no price count as no spend.
- **OpenRouter spend estimate:** tokens × (0.8 × input + 0.2 × output) LiteLLM list price, caching ignored;
  9–30% of paid tokens per quarter are priced from a model's nearest listing (`price_date_stale`).
  **Upper bound** = as computed (Anthropic's tokens all priced, checked per week); **lower bound** = unpriced
  paid tokens at the week's dearest priced blended price (assumes no unpriced model is dearer);
  **sensitivity** = unpriced paid tokens at the week's mean priced price. The chart shades
  [sensitivity, computed] (author decision 4).
- **Smoothing:** trailing mean over 4 consecutive weeks; a missing week would break the line for four weeks.
- **Headline:** each chart's values are the 4-week means at the latest week all three sources cover.

## Licence
Ramp's redistribution right is unknown, so no target inlines its data: PNGs only (Ramp: derived charts allowed
with attribution; Vercel and OpenRouter rankings: CC BY 4.0; LiteLLM: MIT). Frames go only to the gitignored
`outputs/…/story_frames.json`.

## Caveats
- **Three populations, none of them the market.** Ramp: businesses on Ramp that connected their AI provider
  accounts to Ramp (Ramp: not representative of its total AI spend, though directionally similar). Vercel and
  OpenRouter: developers who route through that gateway; first-party API use is invisible to both, and each
  gateway's mix of apps (coding agents, chat apps) shapes its shares.
- **Spend is measured three ways.** Ramp: realised spend (cached-token discounts apparently included: Anthropic's blended price on Ramp has run below its
  input price since mid-2025, falling from ~1.3× input in January 2025 to ~0.3× in September 2026, which caching
  explains). Vercel: Vercel's measure (whether bring-your-own-key
  traffic, discounts or caching are included is not stated). OpenRouter: our list-price estimate, caching
  ignored. Some of the spend gap between sources may therefore be method, not segment.
- **Weighting:** Ramp and OpenRouter weeks are volume-weighted; Vercel's are means of daily shares.
- **Denominators** are each source's own reported total: Ramp's 3–14 makers, every Vercel lab, OpenRouter's
  top 50 models plus its tail.
- **Tokens** are counted by each provider's tokenizer, so token shares compare labs only roughly.
- Ramp, Vercel and OpenRouter's rankings are Latest-only (revised); figures move with each fetch and import.
  Vercel's history starts in October 2025.

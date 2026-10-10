# Plan: Anthropic's share of spend and tokens, by data source (exploration)

Status: EXPLORATION BUILT · 2026-10-10 (plan review: adversarial review converged in 3 rounds, 9 findings accepted; all decisions below taken)

**As built:** `explore/2026-10-10-anthropic-share-by-source/` renders `spend`, `tokens` and `tokens-with-free`
(`x_png`, `linkedin_png`), each PNG measured equal to its plot box. Differences from the design: every line
ends at the latest week all three sources cover (the headline's week, today 27 September 2026), so the end
labels equal the headline; the gateways' one later full week is in the frames but not drawn. The OpenRouter
band breaks where its line breaks (weeks missing a day). The bound and sensitivity are also reported per
quarter (`or_bound_quarterly`). The headline names all three sources, ordered by value. No legend: the direct end labels name each line
and the subtitle explains dots (weekly) vs lines (4-week). The `checks` frame holds Ramp's share sums,
each later maker's first week and first-week share, and Anthropic's full weeks and lowest weekly share per
source.

**Revised 2026-10-10 (author feedback after the build):** one title for all visuals ("Different data sources
tell different stories about the AI economy"); subtitles in one pattern giving each chart's 4-week values at
the latest common week; the measure stamped in the chart's upper right with a dots/lines key (the population
note dropped from the footer; the README keeps it); quarterly ticks through October; per-visual `sources`
(core change; token visuals credit no LiteLLM); the reserved link `source-matters` (core change: an
exploration may reserve its future short link). Second round of feedback: the stamp is one larger line
just below the 100% gridline; OpenRouter's free-model scope moved into the footer note; the dots/lines key
dropped (the subtitle says 4-week averages); a gateway week needs ≥ 6 days (`min_days`), so OpenRouter's two
6-day weeks (missing 2025-06-15 and 2025-07-15) no longer break its line; the brand wordmark is back to the
lime square and text colour of the first receipt (brand.yaml, every visual).

## Question

Do the datasets that measure AI spend tell the same story about one lab? The author's thesis: each
source sees a different segment of the market, so none is fully representative of a lab's true position.
Taking each source's figures as accurate for its own population, Anthropic's share of spend (and of
tokens) moving at different levels and in different directions across sources shows that they capture
different segments. This exploration charts Anthropic's share of **all reported spend** and of **all
reported tokens** in three sources, on a like-for-like basis, on one axis per chart.

Exploration `explore/2026-10-10-anthropic-share-by-source/`; follows analysis (e) (`2026-10-09-wallet-lenses`)
but is separate from it. (e)'s rule "never on one axis" was about lenses measuring *different* things
(spend share vs share of businesses paying); here every line is the *same* measure, a lab's share of its
source's total, so one axis is the point of the chart (author decision, 2026-10-10). Ramp's
paying-businesses lens is not used.

## The three sources (all in existing marts; no source or mart change)

| Source | Population | Spend | Tokens | Grain | From | Mart |
|---|---|---|---|---|---|---|
| **Ramp** AI Token Spend Management | Ramp customers who connected their AI providers (Ramp: "not representative of total AI spend, though directionally similar") | realised spend by model maker | token volume by model maker | week (Mon–Sun, dated by its Sunday) | week ending 2025-01-12 | `062` `ramp_token_share` (`measure` = `spend` / `volume`) |
| **Vercel** AI Gateway | developers routing through Vercel's gateway | Vercel's measure of what customers paid | tokens | day | 2025-10-01 | `090` `vercel_lab_share` (`metric` = `spend` / `tokens`) |
| **OpenRouter** | developers routing through OpenRouter | **our estimate**: tokens × list price (0.8 × input + 0.2 × output), caching ignored | tokens, with or without free variants | day | 2025-01-01 | `010` `or_model_daily` |

"All reported" in each: Ramp's shares are of the makers Ramp reports (the roster grew from 3 makers in January
2025 to 14 by mid-2026, gradually and fluctuating 9–14 through 2026; the shares sum to exactly 100% every
week; makers added from August to November 2025 held ≤ 0.1% of spend in their first week (≤ 0.001% for the
Aug–Oct entrants; Cursor 0.06% from 2025-11-02), and makers beyond Anthropic,
OpenAI and Google hold ≤ 2.9% of weekly spend even in September 2026, so the expansion does not break
Anthropic's series). Vercel: every lab on the gateway (shares sum
to 100 daily). OpenRouter: the top 50 models per day plus its `other` row (the long tail), stealth and
router models; for spend, tokens with no price (`price_matched` false) count as no spend.

## What was measured (2026-10-10; Ramp import of 2026-10-07; gateways to 2026-10-08)

Anthropic's share, quarterly mean of weekly values (%; weeks dated by their Sunday; each source on its own
full weeks, so Vercel's 5-day first week and OpenRouter's weeks with a missing day are left out):

| Quarter | Ramp spend | OpenRouter est. spend | Vercel spend | Ramp tokens | OpenRouter tokens, paid | OpenRouter tokens, all | Vercel tokens |
|---|---|---|---|---|---|---|---|
| 2025 Q1 | 38.0 | 92.7 | — | 18.2 | 45.1 | 41.8 | — |
| 2025 Q2 | 44.4 | 77.9 | — | 23.2 | 26.0 | 22.8 | — |
| 2025 Q3 | 43.8 | 69.3 | — | 25.7 | 22.0 | 19.2 | — |
| 2025 Q4 | 55.0 | 61.9 | 76.8 | 33.1 | 15.7 | 14.3 | 52.2 |
| 2026 Q1 | 62.0 | 63.5 | 77.4 | 43.6 | 16.3 | 14.8 | 44.0 |
| 2026 Q2 | 64.9 | 63.5 | 64.0 | 52.5 | 16.0 | 14.5 | 30.8 |
| 2026 Q3 | 58.6 | 40.3 | 59.4 | 45.7 | 8.1 | 7.2 | 21.7 |

(OpenRouter here is the mean of daily shares; the build uses volume-weighted weeks, decision 3.)

1. **Spend, 2025: opposite directions.** Ramp rose (38 → 55% from Q1 to Q4) while OpenRouter fell (93 → 62%).
2. **Spend, 2026: same direction, different levels.** From Q2 to Q3 2026 all three fell (Ramp 65 → 59,
   Vercel 64 → 59, OpenRouter 64 → 40). In the three weeks ending 13–27 September 2026 (Ramp's latest):
   Ramp 48.6–53.7%, Vercel 37.3–51.3%, OpenRouter 25.2–29.4%.
3. **Tokens: opposite directions for 18 months.** Ramp's token share rose from 18% (2025 Q1) to 53% (2026 Q2)
   while OpenRouter's fell from 45% to 16% (paid) and Vercel's from 52% (2025 Q4) to 31%. In 2026 Q2 the
   three sources put Anthropic at 53%, 31% and 16% of tokens.
4. **Free variants matter little to Anthropic's OpenRouter token share** (0.9–3.3 pp lower per quarter with them; Anthropic
   has no free models, so including free tokens only enlarges the denominator).
5. Week-to-week noise (mean absolute weekly change): Ramp ~2 pp, OpenRouter ~2–2.5 pp, Vercel ~4.3 pp.

Coverage of the OpenRouter estimate, per quarter 2025 Q1 – 2026 Q3: priced share of paid tokens 85–95%;
9–30% of paid tokens are priced from a model's nearest LiteLLM listing (`price_date_stale`); free variants
are 8–13% of all tokens. Anthropic's own tokens are never free and are priced in every full week (one day,
2026-10-08, left 20% unpriced: Claude Haiku 5.5, new in the top 50 and not yet in `models.yaml`; it falls
in the current partial week, and the build checks this per week).

## Design

### Weekly series (frame `weekly`)
- **Weeks:** Monday–Sunday, dated by the Sunday (Ramp's convention). Only full weeks: 7 days of data for
  Vercel and OpenRouter (a partial week, e.g. the current one, is dropped).
- **Ramp:** `ramp_token_share.share` for `anthropic` (week total ÷ week total over makers, i.e.
  volume-weighted by construction).
- **OpenRouter:** per week, Anthropic's tokens (or estimated spend) ÷ all tokens (or all estimated spend)
  in the week, **volume-weighted** like Ramp (decision 3). Tokens in two variants: paid only (`NOT
  is_free`, both numerator and denominator) and all.
- **Vercel:** the mean of the week's daily shares (Vercel publishes no volumes, so it cannot be
  volume-weighted; stated in the footnote).
- **Smoothing (decision 2):** weekly points drawn faint, a trailing 4-week mean drawn as the line (needs
  4 full weeks; the first three weeks of each source have points but no line).
- Columns: `week`, `source` (`ramp`, `vercel`, `openrouter`), `measure` (`spend`, `tokens`), `variant`
  (`paid`, `all`; OpenRouter tokens only), `share_pct`, `days`, `rolling4_pct`.

### Bound and sensitivity for OpenRouter's spend estimate (frame `or_bound`)
PLAN rule: spend figures are estimates with bounds. Per week:
- **Upper bound** = the share as computed (unpriced paid tokens cost nothing), valid while all of
  Anthropic's tokens are priced; the analysis checks this per week and stops (or drops the week, decision
  4) if not.
- **Lower bound** = unpriced paid tokens priced at the week's highest blended price among priced paid
  models. It is a bound under one stated assumption: no unpriced model is dearer than the dearest priced
  model that week (the unpriced tail is mostly `_other`, `_stealth` and `_router`; a new flagship model
  missing from `models.yaml` could break it, and the per-week check catches that only for Anthropic's own
  models). It is very wide (e.g. week ending 2026-08-23: computed 34.2%, bound 8.4%,
  with 19.8% of paid tokens unpriced), because the unpriced tail is mostly `_other`, `_stealth` and
  `_router` traffic, unlikely to cost as much as the dearest model.
- **Sensitivity** = unpriced paid tokens at the week's mean price per priced paid token (a central
  estimate, not a bound; e.g. 27.5% in that week).
The chart draws [sensitivity, computed] as a faint band labelled as a sensitivity; the README reports the
hard lower bound per quarter (decision 4). Caching cannot be bounded from these data; it is a footnote.

### Frames
`weekly`, `or_bound`, `coverage` (per week: OpenRouter priced and stale share of paid tokens, free share of
all tokens; Ramp makers with data; Vercel days), `checks` (one row: first and last week per source, weeks
dropped as partial, Ramp share sums = 100, Anthropic present every week in each source).

### Visuals (each `x_png`, `linkedin_png`; identical formatting)
1. **`spend`**: Anthropic's share of all reported spend; three lines (Ramp, Vercel, OpenRouter) on one 0–100%
   axis, weekly from the week ending 2025-01-12; faint weekly points, 4-week line, OpenRouter's bound band;
   direct labels at line ends with the last 4-week value, plus a legend. Headline states the finding
   plainly from the data and names all three lines (today, e.g. from the latest 4-week values: "Anthropic's
   share of AI spend depends on whose data you read: 53% on Ramp, 43% on Vercel, 28% on OpenRouter").
2. **`tokens`**: the same for tokens, OpenRouter paid tokens only.
3. **`tokens-with-free`**: the same as `tokens`, OpenRouter including free variants (author decision 1).
Colours: three categorical slots for the three sources (not Anthropic's brand orange, since every line is
Anthropic); the same source keeps the same colour in every chart. Notes (footer): the OpenRouter estimate
and its band; Vercel's mean of daily shares; Ramp's population. Charts build through `cachereg.viz.fit`,
and every visual × target is measured (PNG == plot box).

### Licence and attribution
Sources: `ramp_ai_index`, `vercel_ai_gateway`, `openrouter_rankings`, `litellm_prices`. Ramp's
redistribution is unknown, so PNG targets only (no `blog_html`, no `data.json`); frames go only to the
gitignored `outputs/…/story_frames.json`.

## Caveats (README; the first two as on-image notes)
- **Three populations.** Ramp: businesses on Ramp that connected their AI provider accounts (a subset of
  Ramp's customers; Ramp says not representative of its total AI spend). Vercel and OpenRouter: developers
  who route through that gateway; first-party API traffic is invisible to both. None of the three is the
  market.
- **Spend is measured three ways.** Ramp: realised spend (cached-token discounts apparently included: Anthropic's blended price on Ramp has run below its
  input price since mid-2025, falling from ~1.3× input in January 2025 to ~0.3× in September 2026, which caching
  explains). Vercel: Vercel's measure (whether BYOK, discounts or
  caching are included is not stated). OpenRouter: our list-price estimate with caching ignored, which likely
  overstates labs whose users cache heavily (Anthropic's coding-agent traffic), so some of the gap between
  OpenRouter and the others may be method, not segment.
- **Weighting:** Ramp and OpenRouter weeks are volume-weighted; Vercel's is a mean of daily shares.
- **Denominators:** each source's own reported total: Ramp's 3–14 makers, Vercel's labs, OpenRouter's top 50
  plus its tail; OpenRouter's unpriced tokens count as no spend (bounded).
- **Tokens** are counted by each provider's tokenizer, so token shares compare labs only roughly.
- Ramp and Vercel are Latest-only (revised); OpenRouter's rankings are Latest-only; figures move with each
  fetch and import. Vercel's history starts 2025-10-01.
- What the chart can and cannot show: different levels and directions in the same measure show the
  sources see different segments (or measure spend differently); they do not show which is closest to the
  market, and they do not size any segment.

## Code
`explore/2026-10-10-anthropic-share-by-source/` (`analysis.py`, `charts.py`, `explore.yaml`, `README.md`).
Reads marts `010`, `062`, `090` only. No core change expected. The render contract does not pass the
visual's name to its chart function, so each visual has its own thin function (`spend`, `tokens`,
`tokens_with_free`) calling one shared helper with the measure and variant. If a core change is needed, stop and ask.

## Decisions
Taken by the author in conversation (2026-10-10):
1. Tokens in both versions: OpenRouter with and without free variants (two visuals, same formatting).
2. Weekly points with a trailing 4-week line.

Taken after the review (2026-10-10): the recommendations of 3–5 (volume-weighted OpenRouter weeks; the
sensitivity band with the hard lower bound in the README; stop until a new Anthropic model is mapped; each
source from its first full week). The options as they were put:
3. **OpenRouter weekly weighting:** volume-weighted, matching Ramp (recommended), or the mean of daily shares,
   matching Vercel (the measured table above; differences are small).
4. **OpenRouter spend uncertainty:** draw the [mean-price sensitivity, computed] band and report the hard
   lower bound in the README (recommended); or draw the hard bound [highest-price, computed] (honest but
   so wide it swamps the line); or footnote the weekly priced coverage only. And when a week has unpriced
   Anthropic tokens (a new model not yet mapped): stop the analysis until `models.yaml` is updated
   (recommended), or drop that week.
5. **Start:** each source from its first full week (recommended: Ramp and OpenRouter from January 2025,
   Vercel from October 2025), or all three from October 2025 only.

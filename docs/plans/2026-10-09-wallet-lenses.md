# Plan: analysis (e) "Developer wallet vs enterprise wallet" (exploration)

Status: EXPLORATION BUILT · 2026-10-09 (plan review: adversarial review converged in 2 rounds, 11 findings accepted; author decisions below)

**As built (differences from the design below):** `explore/2026-10-09-wallet-lenses/` renders `ranks`,
`leaders`, `tokens-spend` and `run-rates` (`x_png`, `linkedin_png`); the outcome is as planned (11 agree, 1
unsettled, 1 disagrees, 2 not comparable). `tokens-spend` shows every lab with ≥ 3% in any of its four
lenses (StepFun has 11% of Vercel's tokens) ranked among all named labs on that gateway, not `ranks`' rows.
`ranks` shows no rank for values under the 1% floor. `tokens-spend` is one row of four panels in both targets, not a 2 × 2 grid (ten rows per
panel need the height; the 2 × 2 branch remains for boxes narrower than 1.2:1). `leaders` uses the brand's vendor colours (Anthropic,
OpenAI, Google) and lays its panels side by side in `x_png` (three stacked panels cannot fit its 305 px box).
`pair_history` excludes partial months. `cachereg.viz.fit` changed while building: vl-convert truncates the
SVG size to whole PNG pixels (measured), so `fit` now aims at [box, box + 1) (the old ±0.45 window left
`tokens-spend` 1 px short); and Vega rounds each concat panel's size, so `split()` gives the remainder to
one panel (equal panels moved the outer size in 3 px steps and skipped the box). Two-lenses still fits
exactly; its PNGs changed by sub-pixel amounts only. Every visual × target was measured: PNG == plot box.

## Question

Do the labs that win developers' gateway spend also win businesses' wallets, and the revenue the labs
themselves report? Three **separately labelled lenses** on the same vendors (PLAN §10, starter analysis
(e)):

1. **Developer gateways:** Vercel AI Gateway's *measured* spend share and OpenRouter's *estimated* spend
   share (list prices), each with its token share alongside for context (mart `091_gateway_lenses`).
2. **Enterprise adoption:** the share of businesses on Ramp paying each lab (`091`, lens `ramp_paying`).
3. **Reported revenue run-rates:** the labs' own statements (`080_disclosures`).

The lenses are never put on one axis, never converted into each other and never turned into ratios or
differences, across lenses or within one. The output is a vendor rank comparison across the lenses and
where they disagree, or, if the lenses do not support a ranking claim, "three views" (PLAN's fallback).
Built as an exploration, `explore/2026-10-09-wallet-lenses/`; promotion is a separate decision.

## What was measured (2026-10-09; warehouse built 08:14 local from that morning's fetches; Ramp import of 2026-10-07)

### Coverage

| Lens (`091` / `080`) | Months | Vendors | Partial months | Notes |
|---|---|---|---|---|
| `vercel_spend`, `vercel_tokens` | 2025-10 → 2026-10 | 23 named (+ `_stealth`, `_unmapped`) | 2026-10 (8 of 31 days) | means of daily shares; labs complete (100%/day) |
| `openrouter_est_spend` | 2025-01 → 2026-10 | 25 named (+ `_other`, `_stealth`, `_router`, `_unmapped`) | 2026-10 (8 days) | `coverage_pct` (priced share of non-free tokens) 80.0–93.2% since 2025-10 (Aug 2026: 87.6; Sep: 93.2) |
| `openrouter_tokens` (+ `_volume_weighted`) | 2025-01 → 2026-10 | same | 2026-10 | includes `_other` (~6%) and `_stealth` (4–5%) |
| `ramp_paying` | 2023-01 → 2026-08 | **6**: Anthropic, OpenAI, Google, xAI, DeepSeek, Mistral | none | not a share of a total (rows do not sum to 100) |
| `revenue_run_rate` (`080`) | statements 2025-06 → 2026-05 | **2**: Anthropic (6 rows), OpenAI (4 rows) | n/a | + Microsoft's `ai_revenue_run_rate` (a business line, not a lab), OpenAI's `revenue_monthly` (1 row) |

**Common window of lenses 1 and 2: Oct 2025 → Aug 2026, 11 complete months.** Vercel starts 2025-10; Ramp
ends 2026-08 (September is due with the next import, ~2026-11-07). The latest common complete month is
**August 2026**. Ramp names six labs only: Moonshot, Z.ai, Xiaomi, Tencent, MiniMax and StepFun, which
hold real gateway shares, are **not reported** by Ramp (absent, not zero).

The unpriced OpenRouter tokens (7–14% of paid tokens) sit almost entirely in `_other`, `_stealth` and
`_router` in Jun–Sep 2026 (68%, 22% and 9% of them; Alibaba, Ant and `_unmapped` under 1% each), and none
in Ramp's six. So pricing them
would rescale the six labs' estimated-spend shares together and leave their order unchanged.

### August 2026 (latest common month): values, rank among Ramp's six labs, rank among all named vendors

| Lab | Vercel spend | OpenRouter est. spend | Ramp paying | Vercel tokens | OpenRouter tokens |
|---|---|---|---|---|---|
| Anthropic | 64.1 (1; 1) | 37.5 (1; 1) | 43.8 (1) | 22.1 (2) | 5.9 (4) |
| OpenAI | 12.7 (2; 2) | 18.3 (2; 2) | 39.8 (2) | 14.8 (3) | 11.0 (2) |
| Google | 7.5 (3; 3) | 8.4 (3; 5) | 6.2 (3) | 5.4 (4) | 7.6 (3) |
| DeepSeek | 2.9 (4; 6) | 6.4 (4; 6) | 0.3 (5) | 30.1 (1) | 23.1 (1) |
| xAI | 0.8 (5) | 1.3 (5) | 4.6 (4) | 0.5 (5) | 0.5 (5) |
| Mistral | 0.1 (6) | 0.0 (6) | 0.2 (6) | 0.1 (6) | 0.1 (6) |
| *Not reported by Ramp:* Moonshot | 4.5 | 8.7 | — | 3.2 | 1.8 |
| Z.ai | 4.8 | 8.7 | — | 6.8 | 6.4 |
| Xiaomi | 0.0 | 6.0 | — | 0.8 | 8.3 |

(%, mean of daily shares for the gateways; ranks among the six in the first parenthesis, among all named
vendors after the semicolon. The token columns rank among the six.)

### How the pairwise orders run, month by month (Oct 2025 → Sep 2026; `>` = first lab higher; `~` = both under 1%; `absent` = a lab has no row in that lens and month)

| Pair | Vercel spend | OpenRouter est. spend | Ramp paying (to Aug) |
|---|---|---|---|
| Anthropic vs OpenAI | `>` all 12 | `>` all 12 | `<` Oct–Apr, `>` May–Aug |
| Anthropic vs Google, DeepSeek, Mistral | `>` all | `>` all | `>` all |
| Anthropic vs xAI | `absent` Oct, `>` Nov–Sep | `>` all | `>` all |
| OpenAI vs Google | `>` Oct–Nov, `<` Dec–Jun, `>` Jul–Sep | `<` Oct–Mar, `>` Apr–Sep | `>` all |
| Google vs DeepSeek | `>` all | `>` Oct–Aug, `<` Sep | `>` all |
| **xAI vs DeepSeek** | `absent` Oct, `~` Nov–Mar, `>` Apr, `<` May–Sep | `>` Oct–Jan, `<` Feb–Sep | **`>` all** |
| OpenAI vs xAI | `absent` Oct, `>` Nov–Sep | `<` Oct–Nov, `>` Dec–Sep | `>` all |
| DeepSeek vs Mistral | `~` to Apr, `>` May–Sep | `>` all | `~` all |

Rank correlation across the six (Spearman, per month) is 0.60–0.94 between Ramp and either spend lens,
but with six labs, two of them near zero in every lens, ρ mostly measures that Mistral is last everywhere.
The pairwise orders above carry the information.

### Findings this supports

1. **The top of the order agrees in August 2026.** Among Ramp's six labs, all three spend/adoption lenses
   put Anthropic first, OpenAI second and Google third (Vercel's OpenAI-vs-Google order flipped in
   July, so it is not settled there).
2. **The agreement at the top is recent on Ramp.** Both gateways put Anthropic's spend share first in
   every month since October 2025; Ramp put OpenAI first through April 2026 and Anthropic first from May
   2026.
3. **The one settled disagreement is DeepSeek vs xAI**, two labs low in every lens: on both gateways
   DeepSeek's spend share has been above xAI's since May 2026 (Vercel) and February 2026 (OpenRouter); on
   Ramp, xAI has been above DeepSeek in every month. (Both are small on Ramp; the 1% floor keeps xAI in
   the comparison only because xAI is above 1% there.) Within the gateways, DeepSeek has the **largest
   token share** (Aug 2026) and is 4th in spend among the six. That is mostly arithmetic, not a
   disagreement: spend is tokens × price and DeepSeek's models are among the cheapest per token, so its
   spend share must sit well below its token share. It is shown as context, not as a finding about
   wallets.
4. **Ramp does not report two of OpenRouter's top four labs by estimated spend** in August 2026
   (Moonshot 3rd, Z.ai 4th; Xiaomi 7th), nor Vercel's 4th and 5th (Z.ai, Moonshot): the enterprise lens
   is silent on most open-weight labs, so "absent from Ramp" must never be read as "no business pays
   them".
5. **Lens 3 cannot rank.** Only Anthropic and OpenAI state run-rates. OpenAI's "$20B+ in 2025" (ARR,
   period 2025-01-01 → 2025-12-31; the point in the year is not stated) spans the year, so it overlaps all
   three of Anthropic's 2025 figures (about $1B at the start, over $5B in August, about $9B at the end)
   without matching any one point; there is no like-for-like point comparison. OpenAI has stated no run-rate since; its
   "$2B in revenue per month" (March 2026) is a different measure and is never multiplied by 12 (third-party
   arithmetic, excluded by the dataset's rules). Anthropic's stated run-rate: about $1B (start of 2025) →
   over $5B (Aug 2025) → about $9B (end 2025) → $14B (Feb 2026) → over $30B (Apr 2026) → over $47B (May
   2026). Both are company-wide revenue (OpenAI's mostly ChatGPT subscriptions; neither splits API), so
   this lens measures a third wallet, not either of the others.

## Comparison method (proposed)

**Verdict: a limited ranking claim for lenses 1 and 2; lens 3 as a separate view with no ranking claim.**
Why: lenses 1 and 2 share six labs and eleven complete months, every pair's order is observable in each,
and the orders are stable enough to state (table above). Lens 3 has two labs, no common period after
2025, statements whose timing the company chooses, and two definitions (Anthropic's "run-rate revenue",
OpenAI's "ARR"); a rank of two labs from one ambiguous period is not a ranking claim.

- **Common set:** Ramp's six named labs (the only vendors every lens 1–2 measures). Ranks among all named
  vendors are shown for the gateways as context, never compared with Ramp's ranks.
- **Unit of comparison: the pairwise order** of two labs within a lens, never a value, gap or ratio.
- **Settled order:** a pair's order is *settled* in a lens when it holds in each of the three months
  ending at the headline month (config `settle_months: 3`); otherwise *unsettled*.
- **Floor:** two labs both under 1% in any of those months are *not ranked* against each other (config
  `floor_pct: 1.0`): tenths of a percent on Ramp, or a gateway day's long tail, are not an order.
- **Order values** per lens and month: `>`, `<`, `tie` (equal values), `unranked` (both under the floor)
  or `absent` (a lab has no row in that lens and month; not read as 0). Over the settle window a pair is
  *settled* when the same `>`/`<` holds in every month, *unranked* when any month is `unranked` or
  `absent`, otherwise *unsettled*.
- **Agreement (developer vs enterprise):** a pair is *comparable* only when it is ranked on Ramp and on at
  least one gateway. A comparable pair *agrees* when it is settled in every lens it is ranked in and the
  orders match; *disagrees* when two settled orders differ; otherwise it is *unsettled*. A pair not
  ranked on Ramp (today DeepSeek vs Mistral) or on neither gateway (xAI vs Mistral) is *not comparable*. The README reports
  the counts over the 15 pairs and names each disagreement.
- **Gateway vs gateway** (Vercel vs OpenRouter) is compared the same way and reported separately: two
  developer populations, measured vs estimated spend.
- **Headline month:** the latest month where `vercel_spend`, `openrouter_est_spend` and `ramp_paying` are
  all complete (`days = period_days`; Ramp has no partial months) (config `headline_month: latest` or
  `YYYY-MM`). Today: August 2026.
- **Weighting:** OpenRouter as the mean of daily shares (matching Vercel, which publishes no volumes);
  the volume-weighted token share is a README sensitivity (it changes no order among the six in Aug 2026).
- Run-rates: plotted by the period measured (`period_start`–`period_end` from `080`), as stated
  (qualifier kept: "over", "about"), never interpolated, annualised or converted.

Expected outcome today (Jun–Aug 2026 settle window, prototyped outside the repo), over 15 pairs: 11
agree (Anthropic above each of the other five; OpenAI and Google each above xAI, DeepSeek and Mistral); 1
is unsettled (OpenAI vs Google: settled `>` on OpenRouter and Ramp, unsettled on Vercel); 1 disagrees
(**xAI vs DeepSeek**); 2 are not comparable (xAI vs Mistral, DeepSeek vs Mistral). The analysis computes these; the figures above
are for the plan only.

## Frames (`analysis.py`; reads marts `091` and `080` only)

| Frame | Grain | Columns (main) | From |
|---|---|---|---|
| `lenses` | month × lens × vendor | `lens`, `vendor_id`, `vendor_name`, `value_pct`, `rank_six`, `rank_all` (gateways), `days`, `period_days`, `partial`, `coverage_pct`, `in_ramp` | `gateway_lenses`; display names from `dim_vendor_alias.vendor_name` (one canonical name per `vendor_id`, from `vendors.yaml`, so Ramp's "Mistral AI" and Vercel's "Mistral" both read "Mistral") |
| `pairs` | headline month × pair × lens | `a`, `b`, `lens`, `order` over the window (`>`/`<`/`unsettled`/`unranked`), then per pair `status` (`agree`/`disagree`/`unsettled`/`not comparable`) | `lenses` |
| `pair_history` | month × pair × lens | `order` (`>`/`<`/`tie`/`unranked`/`absent`; the monthly table above) | `lenses` |
| `run_rates` | disclosure row | `vendor_id`, `metric`, `value`, `value_as_stated`, `qualifier`, `period_start`, `period_end`, `statement_date`, `source_kind`, `plotted` (false for `revenue_monthly`) | `disclosures` (metrics `revenue_run_rate`, `revenue_monthly`; **no `source_quote`, no `source_url`**) |
| `checks` | one row per check | OpenRouter `coverage_pct` per month, unpriced tokens by vendor share (must stay outside the six; the analysis fails if a lab of the six holds > 1% of unpriced tokens), `_unmapped` share per gateway, partial months dropped, headline month | `gateway_lenses`, `or_model_daily` |

`or_model_daily` (mart 010) is read only for the unpriced-token check; all lens values come from `091`.

## Visuals (`x_png`, `linkedin_png` each; all lenses in separate panels, each with its own unit)

1. **`ranks`** (main; small multiples): three panels side by side, **Vercel: share of spend** ·
   **OpenRouter: share of estimated spend** · **Ramp: share of businesses paying**, headline month. Same
   rows in every panel: Ramp's six labs in Ramp's order, a gap, then gateway labs not reported by Ramp
   with ≥ 3% of spend on either gateway (today Moonshot, Z.ai, Xiaomi), whose Ramp cell reads "not
   reported". A dot per lab with "#rank · value%" beside it (as `two-lenses` `sectors`); each panel its own
   0–100% axis (all three are percentages of different totals; a shared range avoids stretching one lens
   but the panels are never joined). Labs in a *disagreeing* pair in the accent, others grey. Headline
   states the finding (today: "Gateway spend and Ramp's businesses put the same three labs on top; they
   split on DeepSeek and xAI").
2. **`leaders`** (time): three stacked panels on one time axis (Oct 2025 → each lens's latest complete
   month), each with its own y-scale and unit: Vercel spend, OpenRouter est. spend, Ramp paying; lines
   for Anthropic and OpenAI in two accent-family colours, Google in grey, labelled at the line ends.
   Headline (today): "Gateways have put Anthropic first in spend since October 2025; Ramp's businesses
   since May 2026".
3. **`tokens_spend`** (gateways only, headline month): four panels in a 2 × 2 grid, one per `091` lens
   (Vercel tokens, Vercel spend; OpenRouter tokens, OpenRouter est. spend), each with its own axis and
   unit; same rows in every panel (the six plus the not-reported labs of `ranks`), a dot and "#rank ·
   value%" per row, as in `ranks`. Tokens and spend are never on one axis, and no mark joins them.
   Only ranks are compared across panels. Headline (today): "DeepSeek ranks first in tokens on both
   gateways and fourth in spend"; the note says why (spend is tokens × price; DeepSeek is cheap per
   token).
4. **`run_rates`** (lens 3 alone): stated run-rates for Anthropic and OpenAI on a log dollar axis by the
   period measured; point-in-time figures as dots, OpenAI's year figures as horizontal spans over the year
   (the point is not stated); each labelled as stated ("$47B+", "~$9B"); `over`/`about` shown by the
   label; no connecting lines. OpenAI's "$2B in revenue per month" appears only as a text note, not a
   point. Headline: a plain description, no ranking (today: "Anthropic's stated run-rate passed $47B in
   May 2026; OpenAI's last stated run-rate is $20B+ for 2025").

Charts fit their plot box through `cachereg.viz.fit` (below); every visual × target is measured after
rendering (PNG plot area == `page().plot_box`).

## Code changes beyond the exploration

- **`_fit` → `cachereg.viz.fit`** (second use, PLAN §5 rule): `fit(make, width, height)` as in
  `two-lenses/charts.py`, with the `_size` fallback for non-numeric sizes (HTML). `two-lenses` imports it
  and drops its copy. A test renders a small hconcat with a long title and asserts the outer SVG size is
  within 0.45 px of the box, and that an impossible box raises. Check: the two-lenses PNGs are
  byte-identical before and after the move.
- **A plot-box measurement** for the build: a scratch script (not committed) that, for each visual ×
  target, renders the spec, compares the vl-convert PNG size with `page(story, target, rec).plot_box`,
  and reports any mismatch. Committed as a test only if the author wants it general (decision 6).
- No mart or core change. If the build finds one is needed, stop and ask.

## Licence and attribution

- Sources (`explore.yaml`): `vercel_ai_gateway`, `openrouter_rankings`, `litellm_prices`, `ramp_ai_index`,
  `curated_disclosures`. Ramp's redistribution is unknown, so **every visual is PNG only** (no
  `blog_html`, no `data.json`); explorations write frames only to the gitignored
  `outputs/…/story_frames.json`.
- The footer credits all five sources on every visual (the receipt footer is per folder). This
  over-credits `run_rates` (Ramp and the gateways) and `ranks` (disclosures), which is harmless but not
  exact (decision 5).
- Disclosure quotes and URLs are not in any frame. The `run_rates` notes name the company sources
  ("Anthropic news posts; OpenAI CFO post, Jan 2026; CNBC, Jun 2025 (secondary)"), as the dataset's
  SOURCE.md asks.

## Caveats (README; the on-image notes carry the first two per visual)

- **Three populations, three measures.** Vercel: what developers paid through Vercel's gateway (Vercel's
  measure; BYOK, discounts and caching unstated). OpenRouter: our list-price estimate of OpenRouter spend
  (caching ignored, so labs whose users cache heavily are overstated; unpriced tokens count as no
  spend). Ramp: the share of businesses on Ramp with a card or bill payment to the lab in the month,
  which counts a $20 seat like a large API contract, and cannot see labs bought through a cloud
  (Bedrock, Azure, Vertex) or a gateway. Run-rates: company-wide, self-reported, annualised from a period
  the company picks.
- Ranks, not levels: no value, gap or ratio is compared across lenses or panels.
- OpenRouter's estimate prices every token at a fixed 0.8 × input + 0.2 × output list-price blend; a
  model with no LiteLLM price that day takes its nearest listing (flagged `price_date_stale` in mart
  010). Tokens are counted by each provider's tokenizer, so token shares compare labs only roughly.
- Gateways publish shares only: monthly figures are unweighted means of daily shares; Vercel moves a lot
  day to day (Anthropic's daily spend share in August 2026: 56.7–73.2%).
- Ramp names six labs; others are "not reported", not zero. Ramp revises past months (Latest-only);
  Vercel is Latest-only too.
- Ramp's businesses skew to early adopters; gateway users are developers who chose a gateway (a minority
  of API traffic; first-party API use is invisible to both gateways).
- Disclosures: sparse, selective (figures appear when they flatter), definitions differ (run-rate vs
  ARR), and a series is only as regular as the statements.
- Six labs, three months: settled orders are a description, not a test.

## Decisions (author review, 2026-10-09: the recommendations, as proposed)

All seven recommendations were chosen. The options as they were put:

1. **Verdict:** limited ranking claim (pairwise settled orders among Ramp's six labs, lenses 1–2) plus lens
   3 as a separate view (recommended); or "three views" with no ranking claim at all; or include lens 3
   in the ranking (not recommended: two labs, no like-for-like point in time).
2. **Settle rule:** three months ending at the headline month, 1% floor (recommended); or the headline
   month alone (fragile: Vercel's OpenAI/Google order flips month to month); or all 11 common months
   (strict: Anthropic vs OpenAI on Ramp would be unsettled).
3. **Visuals:** `ranks`, `leaders`, `run_rates` (recommended) plus `tokens_spend` (recommended, as lens
   1's token context)? Drop any?
4. **Not-reported labs in `ranks`:** show gateway labs Ramp does not report (≥ 3% of spend on either
   gateway) below the six, marked "not reported" (recommended); or the six only.
5. **Footer:** accept all five credits on every visual (recommended for the exploration; no core change);
   or add per-visual `sources` to `Story.by_visual` and the render gate (a core change, worth doing at
   promotion if a single-source visual is published).
6. **Plot-box check:** a scratch measurement for this build (recommended), or a general test over every
   exploration and receipt (bigger; PLAN's chart-fit item says the others are unmeasured and
   `open-middle` must not change).
7. **Out of scope:** Ramp's token-spend-by-maker view (mart 062: three makers, a self-selected
   population, an index) stays out (recommended); OpenRouter's volume-weighted share is a sensitivity
   only.

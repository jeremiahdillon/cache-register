# Developer wallet vs enterprise wallet

*Exploration · started 2026-10-09 · design: [`docs/plans/2026-10-09-wallet-lenses.md`](../../docs/plans/2026-10-09-wallet-lenses.md)*

## Question
Do the AI labs that lead developers' gateway spend also lead among businesses that pay for AI, and in the
revenue the labs report? Three **separately labelled lenses** on the same labs (PLAN §10, starter analysis
(e)):

1. **Developer gateways:** Vercel AI Gateway's *measured* share of spend and OpenRouter's *estimated* share
   of spend, with each gateway's token share as context (mart `091_gateway_lenses`).
2. **Enterprise adoption:** the share of businesses on Ramp paying each lab (`091`, lens `ramp_paying`).
3. **Reported revenue run-rates:** the labs' own statements (mart `080_disclosures`).

The lenses measure different things in different populations. They are never put on one axis, converted
into each other, or turned into ratios or differences. Only the **order of two labs within a lens** is
compared across lenses 1 and 2. Lens 3 is a separate view with no ranking claim (author decision 1).

## Findings (Vercel and OpenRouter to 2026-10-09; Ramp import of 2026-10-07; headline month August 2026)
- **The top three agree.** Among the six labs Ramp reports, Vercel's spend share, OpenRouter's estimated
  spend share and Ramp's share of businesses paying all put **Anthropic, OpenAI and Google** on top in
  August 2026. Anthropic is above every other lab in every lens in each month June–August 2026; OpenAI
  vs Google is settled on OpenRouter and Ramp but not on Vercel, where the order flipped in July.
- **11 of 15 pairs agree, 1 disagrees, 1 is unsettled, 2 cannot be compared** (settle window June–August
  2026; frame `pairs`). The not-comparable pairs both involve Mistral: DeepSeek vs Mistral is under 1% for
  both on Ramp, and xAI vs Mistral is under 1% for both on each gateway in at least one month.
- **The one disagreement is xAI vs DeepSeek, two small labs.** On both gateways DeepSeek's spend share is
  above xAI's in every month of the window (Vercel 1.7–2.9% vs 0.2–0.8%; OpenRouter 2.9–6.4% vs
  0.05–1.3%); on Ramp, xAI is paid by more businesses (3.0–4.6% vs 0.3%). Over the longer history the
  gateway order flipped earlier in 2026 (OpenRouter from February, Vercel from May), while Ramp has had xAI
  above DeepSeek in every month since October 2025 (frame `pair_history`).
- **The agreement at the top is recent on Ramp.** Both gateways have put Anthropic first in spend in every
  complete month since October 2025 (through September 2026). Ramp put OpenAI first through April 2026
  and Anthropic first from May 2026 (43.8% vs 39.8% of businesses in August). OpenRouter's September
  figures are close (Anthropic 28.3%, OpenAI 27.6%, list-price estimate), so its lead there is not robust
  beyond August.
- **DeepSeek carries the most tokens on both gateways and ranks sixth in spend on both** (August 2026,
  among all named labs). That is mostly arithmetic: spend is tokens × price, and DeepSeek's models are
  among the cheapest per token. It is context for lens 1, not a finding about wallets.
- **Ramp does not report most open-weight labs.** Moonshot AI and Z.ai each hold 8.7% of OpenRouter's
  estimated spend (3rd and 4th) and 4.5–4.8% of Vercel's; Xiaomi 6.0% of OpenRouter's. Ramp lists none of
  them: absent from Ramp is not "no business pays them".
- **Lens 3 cannot rank.** Only Anthropic and OpenAI state run-rates. Anthropic's stated run-rate: about $1B
  (start of 2025), over $5B (August 2025), about $9B (end of 2025), $14B (February 2026), over $30B (April
  2026), over $47B (May 2026). OpenAI: $2B, $6B and "$20B+" ARR for 2023, 2024 and 2025 (the point in the
  year is not stated) and $10B ARR in June 2025 (CNBC, confirmed by a spokesperson). OpenAI's 2025 figure
  spans the year, so it overlaps all three of Anthropic's 2025 figures without matching any one point;
  OpenAI has stated no run-rate since (its "$2B in revenue per month", March 2026, is a different measure
  and is never multiplied by 12). Both are company-wide revenue, mostly not API spend.
- Context: Spearman ρ across Ramp's six labs, per month October 2025 – August 2026, is 0.60–0.94 between
  Ramp and OpenRouter and 0.66–0.94 between Ramp and Vercel. With six labs, two of them near zero
  everywhere, ρ mostly says the tail is last in every lens; the pairwise orders carry the information.

## Visuals
- `ranks`: three panels (Vercel spend · OpenRouter est. spend · Ramp paying), August 2026; Ramp's six labs in
  Ramp's order with "#rank · value" (rank among the six; no rank under 1%), then the gateway labs Ramp does
  not report (≥ 3% of spend on either gateway). Each panel its own 0–100% axis; labs in a disagreeing pair
  in the accent.
- `leaders`: the same three lenses monthly from October 2025, each panel its own y-scale; Anthropic, OpenAI
  and Google in their brand colours. Side by side in `x_png`, stacked in `linkedin_png`.
- `tokens-spend`: four panels (Vercel tokens, Vercel spend, OpenRouter tokens, OpenRouter est. spend),
  August 2026, every lab with ≥ 3% in any of them; ranks among all named labs on that gateway; the lab with
  the most tokens on both gateways in the accent.
- `run-rates`: the stated run-rates on a log dollar axis by the period described; year figures as spans,
  point figures as dots, each labelled as stated; no connecting lines.
Rendered as `x_png` and `linkedin_png` only (see Licence). Every chart's PNG equals its plot box exactly
(measured for all eight visual × target pairs; charts build through `cachereg.viz.fit`).

## Tables

**August 2026, values (%) and rank among Ramp's six labs** (frame `lenses`; no rank under 1%):

| Lab | Vercel spend | OpenRouter est. spend | Ramp paying |
|---|---|---|---|
| Anthropic | 64.1 (1) | 37.5 (1) | 43.8 (1) |
| OpenAI | 12.7 (2) | 18.3 (2) | 39.8 (2) |
| Google | 7.5 (3) | 8.4 (3) | 6.2 (3) |
| DeepSeek | 2.9 (4) | 6.4 (4) | 0.3 |
| xAI | 0.8 | 1.3 (5) | 4.6 (4) |
| Mistral | 0.1 | <0.1 | 0.2 |
| *Not reported by Ramp:* Moonshot AI | 4.5 | 8.7 | — |
| Z.ai | 4.8 | 8.7 | — |
| Xiaomi | <0.1 | 6.0 | — |

**Settled orders, June–August 2026** (frame `pairs`): `>` the first lab is higher in all three months;
`unsettled` the order flips; `unranked` both labs under 1% in a month.

| Pair | Vercel | OpenRouter | Ramp | Status |
|---|---|---|---|---|
| Anthropic vs OpenAI, Google, xAI, DeepSeek, Mistral (5 pairs) | > | > | > | agree |
| OpenAI vs xAI, DeepSeek, Mistral (3) | > | > | > | agree |
| Google vs xAI, DeepSeek, Mistral (3) | > | > | > | agree |
| OpenAI vs Google | unsettled | > | > | unsettled |
| **xAI vs DeepSeek** | **<** | **<** | **>** | **disagree** |
| xAI vs Mistral | unranked | unranked | > | not comparable |
| DeepSeek vs Mistral | > | > | unranked | not comparable |

**Checks** (frame `checks`): none of Ramp's six labs holds any of OpenRouter's unpriced tokens in the window
(they sit in `_other` 55%, `_stealth` 30%, `_router` 12%), so pricing them would rescale the six together,
not reorder them; the analysis stops if a lab of the six ever holds over 1%. OpenRouter's priced share of
non-free tokens is 86.5–92.2% in the window. Unmapped labs hold 0.04% of Vercel's spend in August and none
of OpenRouter's. October 2026 (8 days) is dropped from the gateway lenses as partial.

## Method
- **Lenses** from mart `091_gateway_lenses`: calendar months; Vercel and OpenRouter shares are unweighted
  means of daily shares (OpenRouter's volume-weighted token share is in the frame as a sensitivity and
  changes no order among the six in August 2026); Ramp's is the share of businesses on Ramp with a payment
  to the lab in the month. Display names from `dim_vendor_alias`.
- **Headline month:** the latest month where Vercel spend, OpenRouter est. spend and Ramp are all complete
  (config `headline_month`).
- **Common set:** the labs Ramp reports in the headline month (six). Ranks among them per month and lens.
- **Pairwise order** per month and lens: `>`/`<`, `tie`, `unranked` (both labs under `floor_pct`, 1%) or
  `absent` (a lab has no row; never read as 0). A pair is **settled** in a lens when the same `>`/`<` holds
  in each of the `settle_months` (3) months ending at the headline month; `unranked` when any month is
  unranked or absent; otherwise `unsettled`. A pair is **comparable** when ranked on Ramp and on at least one
  gateway; it **agrees** when every ranked lens is settled the same way, **disagrees** when two settled
  orders differ, and is otherwise **unsettled**. Gateway vs gateway is reported separately
  (`gateways_status`: the two gateways agree on 13 of the 14 pairs both rank; OpenAI vs Google is unsettled).
- **Leaders:** per lens, the first-ranked named lab in its latest complete month and the first month of its
  unbroken run.
- **Run-rates** (mart `080`, metrics `revenue_run_rate` and `revenue_monthly`): as stated, by the period
  described, never interpolated, annualised or converted. Quotes and URLs are not in any frame.
- **Not reported:** gateway labs Ramp does not list, shown when ≥ `not_reported_min_pct` (3%) of spend on
  either gateway in the headline month.

## Licence
Ramp's redistribution right is unknown, so no target inlines its data: only PNGs are declared (Ramp:
derived charts allowed with attribution; Vercel and OpenRouter rankings: CC BY 4.0; LiteLLM: MIT; curated
disclosures: ours, CC BY 4.0, quotes never inlined). The footer credits all five sources on every visual
(the footer is per folder; author decision 5). Every render writes the aggregated frames to the gitignored
`outputs/…/story_frames.json` for local inspection; that is never published.

## Caveats
- **Three populations, three measures.** Vercel: what developers paid through Vercel's gateway (Vercel's
  measure; whether bring-your-own-key traffic, discounts and caching are included is not stated).
  OpenRouter: Cache Register's list-price estimate (0.8 × input + 0.2 × output; caching ignored, so labs
  whose users cache heavily are overstated; a model without a LiteLLM price that day takes its nearest
  listing; unpriced tokens count as no spend). Ramp: businesses on Ramp with a card or bill payment to the
  lab in the month, so a $20 seat counts like a large API contract, and labs bought through a cloud
  marketplace (Bedrock, Azure, Vertex) or a gateway are invisible. Run-rates: company-wide, self-reported,
  annualised from a period the company picks; Anthropic's "run-rate revenue" and OpenAI's "ARR" may differ.
- **Ranks, not levels.** No value, gap or ratio is compared across lenses or panels; the panels' shared
  0–100% range in `ranks` is only so no lens is stretched.
- **Gateways publish shares only:** monthly figures are means of daily shares and Vercel moves a lot day to
  day (Anthropic's daily share of Vercel spend in August 2026: 56.7–73.2%). Both gateways are developer
  populations that chose a gateway; first-party API traffic is invisible to them.
- **Ramp** reports six labs (others are not reported, not zero), skews to early-adopting businesses, and
  revises past months. Ramp, Vercel and OpenRouter are Latest-only: figures move with each fetch and import.
- **Disclosures** are sparse and selective (figures appear when they flatter); a series is only as regular
  as the statements.
- Tokens are counted by each provider's tokenizer, so token shares compare labs only roughly.
- Six labs and three months: the settled orders are a description, not a test. The disagreement involves
  shares under 7% in every lens.

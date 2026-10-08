# Two lenses on adoption

*Exploration · started 2026-10-08 · design: [`docs/plans/2026-10-08-two-lenses-adoption.md`](../../docs/plans/2026-10-08-two-lenses-adoption.md)*

## Question
How does Ramp's **paid** AI adoption (share of businesses on Ramp with AI spend in the month) compare with
the Census Bureau's **self-reported** AI use (BTOS: share of U.S. employer businesses that used AI in any
business function in the last two weeks), overall, by Ramp's seven sectors and, for BTOS, by size class?
(PLAN §10, starter analysis (c).)

## Findings (Ramp import of 2026-10-07; BTOS through cycle 202619; headline month August 2026)
- **The two lenses rank the sectors almost the same way, and have for three years.** Spearman ρ across
  Ramp's seven sectors is 0.89 in August 2026 and 0.79–0.89 in every month from August 2023, each month
  computed within one BTOS wording. Technology and media (taken as Information) and finance are always the
  top two. Accommodation and construction are the bottom two in every month but March 2026, when Ramp's
  health care was 0.02 pp below construction. The persistent differences: **health care** ranks higher on
  BTOS (3rd) than on Ramp (5th–6th), and **manufacturing** higher on Ramp (3rd) than on BTOS (4th–5th).
  Retail differs by one place in some months. This is the most consistent finding, not a tested one (7
  groups), and both lenses may be ordering sectors by a common trait (firm size, office work) rather than
  confirming each other.
- **The levels are far apart in every sector:** Ramp 33–81%, BTOS 9–46% (overall 56.1% vs 23.1%). The
  lenses differ in question (paid vs used), population, window and weighting, so this is not an adoption
  gap.
- **Size mix cannot account for the overall difference on its own.** BTOS's seven size classes run from
  20.9% (5–9 employees) to 40.3% (250+; 90% interval 37.8–42.7), so any reweighting of BTOS by size stays in
  that range, while Ramp's overall level and each of its size bands (Small 50.1, Medium 62.5, Large 66.8)
  sit above it. *Our derivation:* even an all-250+ mix leaves Ramp's overall level at least 13.4 pp above
  BTOS's upper bound; a reweighting could close at most ~52% of the national difference (point estimate),
  ~59% on the upper bound. By sector (table below) the bound holds for manufacturing, health care and
  accommodation, marginally for finance, weakly for retail, and not for information or construction.
- **Both lenses rise.** Since November 2025 (the first month of the new BTOS wording): Ramp 45.9 → 56.1%,
  BTOS 17.3 → 23.1%, up in every sector on both. Ramp was flat from July to December 2025, then climbed ~2 pp
  a month to May 2026; BTOS rose steadily (no jump at the new sample year, 202616). No claim is made about
  which grew faster. Sector growth agrees only weakly: accommodation +8.0 pp on Ramp but +0.6 on BTOS; retail
  +11.7 vs +2.9.
- **BTOS expected vs current use.** Expected use runs about 4 pp above current use (27.0 vs 23.1%
  nationally). Six months later, current use lands close to what was expected: national mean +0.03 pp over 4
  complete current-wording pairs, −0.88 pp over 19 original-wording pairs. Too few pairs for a chart.

## Visuals
- `sectors`: two dot panels, same rows (Ramp's order), same 0–100% scale; BTOS with its 90% interval;
  rank and value beside each dot; sectors ranked differently in the accent.
- `trends`: Ramp above, BTOS below, monthly, same scales; BTOS's two wordings as separate lines with a
  break marker; the new-wording period shaded.
- `sizes`: BTOS's seven size classes beside Ramp's three bands, same 0–100% scale; the BTOS class range
  is the only mark carried across both panels.
Rendered as `x_png` and `linkedin_png` only (no `blog_html`: see Licence).

## Tables (August 2026)

| Sector (NAICS) | Ramp paid | BTOS used (90%) | Rank Ramp / BTOS | Since Nov 2025, pp (Ramp / BTOS) |
|---|---|---|---|---|
| Technology and media* (51) | 80.9 | 45.6 (43.8–47.5) | 1 / 1 | +7.6 / +9.1 |
| Finance and insurance (52) | 73.7 | 38.7 (36.8–40.6) | 2 / 2 | +13.5 / +9.0 |
| Manufacturing (31–33) | 61.1 | 21.5 (20.5–22.4) | 3 / 4 | +14.4 / +9.9 |
| Retail (44–45) | 48.8 | 15.7 (14.8–16.6) | 4 / 5 | +11.7 / +2.9 |
| Health care (62) | 43.4 | 24.7 (23.9–25.5) | 5 / 3 | +10.7 / +5.0 |
| Construction (23) | 42.2 | 15.4 (14.5–16.2) | 6 / 6 | +10.3 / +7.0 |
| Accommodation and food services (72) | 33.1 | 8.9 (8.4–9.5) | 7 / 7 | +8.0 / +0.6 |
| All businesses | 56.1 | 23.1 (22.8–23.4) | | +10.2 / +5.9 |
| *Sensitivity: BTOS 54, professional services* | — | 43.0 (42.2–43.9) | | — / +9.7 |

\* Ramp's "Technology and media", taken as NAICS 51 (Information). With BTOS 54 instead, the top two are
unchanged.

**Size bound by sector** (BTOS sector × size; the highest class by value, which is not always 250+):

| Sector | BTOS highest class | its value (SE; 90% upper) | Ramp | Ramp above the upper bound? |
|---|---|---|---|---|
| Manufacturing | 250+ | 38.5 (3.7; 44.6) | 61.1 | yes |
| Health care | 250+ | 31.1 (4.5; 38.5) | 43.4 | yes |
| Accommodation and food services | 100–249 | 21.6 (2.7; 26.0) | 33.1 | yes |
| Finance and insurance | 250+ | 60.5 (7.4; 72.7) | 73.7 | marginally (1.0 pp) |
| Retail | 250+ | 32.8 (9.4; 48.3) | 48.8 | barely (0.4 pp); the cell averages over a suppressed cycle, so it leans high |
| Construction | 250+ | 42.1 (10.6; 59.5) | 42.2 | no |
| Technology and media* | 250+ | 83.1 (9.3; 98.4) | 80.9 | no |

**Checks** (frame `checks`): `btos_ramp_census_check` agrees in 35 of 35 months; `btos_revision_check`
is empty (weak evidence so far: only one workbook has a second stored version); none of the BTOS series
used has a suppressed cycle in the window (national, the seven sectors, 54, the seven size classes).

## Method
- **Ramp:** `ramp_adoption` / `adoption_two_lenses` (mart 060/072), the latest import of each adoption
  view: share of businesses on Ramp with AI spend in the month.
- **BTOS:** `btos_ai_monthly` (mart 071): the `yes` share of the current-use question, by calendar
  month as **Cache Register's day-weighted average of Census's biweekly estimates over each cycle's
  reference fortnight** (not a Census estimate), with an approximate 90% interval treating cycles as
  independent panels. Partial months (under half covered: Aug 2023, Sep 2026) are not drawn or used for
  ranks, headline or expectation pairs. The two wordings are never averaged, ranked or differenced
  together.
- **Headline month:** the latest month with a Ramp value and a complete BTOS month (config
  `headline_month`).
- **Ranks:** per month, the seven sectors ranked within each lens (ties averaged); Spearman ρ from the
  rank differences. Months where either lens lacks a sector are skipped.
- **Size bound:** BTOS's class range at the headline month; Ramp compared with the highest class's 90%
  upper bound. Size-class employee bounds from `btos_ai_use` (mart 070); Ramp's bands from
  `ramp_adoption`.
- **Expectations:** expected use at month m beside current use at m + 6, same group and wording, both
  months complete.
- **Fallback:** without Ramp imports, set `config.ramp: false`, `sources: [census_btos]` and visuals
  `trends` and `sizes`; the charts then draw their BTOS panel only.

## Licence
Ramp's redistribution right is unknown, so no target inlines its data: only PNGs are declared (Ramp:
derived charts allowed with attribution; BTOS: public domain). Every render writes the aggregated frames to
`outputs/…/story_frames.json` for local inspection; that folder is gitignored and never published.

## Caveats
- **Different questions and populations.** Ramp observes paid AI spend (cards, bill pay) by businesses on
  Ramp, which skew to early adopters; free tools and personal accounts are invisible. BTOS asks all U.S.
  employer businesses (voluntary survey) about use, free tools included, weighted by business count, with
  "Do not know" (~10%) in the denominator. Neither is a measure of the other.
- **Windows differ:** a calendar month of transactions vs a two-week reference period (dated by reference
  days).
- **The November 2025 BTOS wording change started a new series** (~7 pp level shift); October 2025 has no
  BTOS data (shutdown). BTOS panels change every cycle and the sample every summer.
- **Ramp revises past months** (Latest-only); BTOS is Latest-only until two months of vintages show no
  revisions. Figures move with each import and release.
- Ramp's size bands have no published thresholds, and BTOS's business-count weights per class are not
  published, so only the range bound is claimed, not a reweighted estimate.
- "Technology and media" → NAICS 51 is assumed; BTOS 62 includes social assistance; BTOS sector 11 and
  multi-sector firms are outside the seven rows. Seven groups make ranks coarse.
- Sector × size cells are noisy (SE up to ~11 pp). Retail's 250+ cell (its highest class) and
  accommodation's 250+ cell (not its highest) average over a suppressed cycle, which biases them upward.

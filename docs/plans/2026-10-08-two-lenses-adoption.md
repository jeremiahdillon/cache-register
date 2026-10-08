# Plan: analysis (c) "Two lenses on adoption" (exploration)

Status: EXPLORATION BUILT · 2026-10-08

Outcome: `explore/2026-10-08-two-lenses-adoption/` renders `sectors`, `trends` and `sizes` as `x_png` and
`linkedin_png`; every figure below reproduces from its frames. Plan reviewed adversarially before building
(2 rounds, converged, 13 findings accepted). Found while building: one Story carried one headline for all
visuals, so `Story.by_visual` (title, subtitle, notes per visual name; `render` rejects names not in the
folder's yaml) was added to core with two tests; and `render` writes every exploration's frames to the
gitignored `outputs/…/story_frames.json`, so Ramp's aggregated figures do exist locally (never published).
Charts are fitted to the frame's plot box by measuring the rendered spec, since the frame resizes plots to
the box exactly.

## Question

How does Ramp's **paid** AI adoption (share of businesses on Ramp with AI spend in the month) compare
with the Census Bureau's **self-reported** AI use (share of U.S. employer businesses that used AI in the
last two weeks), overall, by Ramp's seven sectors and, for BTOS, by size class? PLAN §10 starter
analysis (c), mart `072`. Built as an exploration (`explore/2026-10-08-two-lenses-adoption/`); promotion
is a separate decision.

## What was measured (2026-10-08; Ramp import of 2026-10-07, BTOS through cycle `202619`)

Checks first: `btos_revision_check` is empty (only `National.xlsx` has a second stored version, and it is
byte-identical, so this proves little yet); `btos_ramp_census_check` agrees in all 35 Ramp months (29 by
collection start, 3 by collection end, 3 both; 2025-10 is the empty shutdown row); `ramp_overall_check`
is clean. None of the BTOS series used (national, the seven Ramp sectors, 54, the seven size classes)
has a suppressed cycle in the window (other sectors do: 11, 21, 22, 48–49, 55). Cycle `202620`
(scheduled 8 Oct) was not yet on census.gov at the 03:17 UTC fetch.

Latest month both lenses cover in full: **August 2026** (Ramp ends there; BTOS Sep 2026 is a 6-day stub).

| Group (NAICS) | Ramp paid | BTOS used (90% CI) | Rank Ramp / BTOS | Δ since Nov 2025, pp (Ramp / BTOS) |
|---|---|---|---|---|
| Information (51; Ramp "Technology and media", assumed) | 80.9 | 45.6 (43.8–47.5) | 1 / 1 | +7.6 / +9.1 |
| Finance and insurance (52) | 73.7 | 38.7 (36.8–40.6) | 2 / 2 | +13.5 / +9.0 |
| Manufacturing (31–33) | 61.1 | 21.5 (20.5–22.4) | 3 / 4 | +14.4 / +9.9 |
| Retail (44–45) | 48.8 | 15.7 (14.8–16.6) | 4 / 5 | +11.7 / +2.9 |
| Health care (62) | 43.4 | 24.7 (23.9–25.5) | 5 / 3 | +10.7 / +5.0 |
| Construction (23) | 42.2 | 15.4 (14.5–16.2) | 6 / 6 | +10.3 / +7.0 |
| Accommodation and food (72) | 33.1 | 8.9 (8.4–9.5) | 7 / 7 | +8.0 / +0.6 |
| **Overall** | **56.1** | **23.1 (22.8–23.4)** | | +10.2 / +5.9 |
| *Sensitivity: BTOS 54 (Professional services)* | — | 43.0 | | / +9.7 |

1. **Level gap.** Ramp's level is far above BTOS's in every sector (33–81% vs 9–46%). It cannot be read
   as an adoption gap:
   different questions (paid vs used), populations (Ramp's customers vs all employer firms), windows
   (calendar month vs two weeks) and weights (Ramp's sample vs business counts).
2. **The sector ranking agrees, and has for three years.** Spearman ρ across the seven sectors is
   0.79–0.89 in every month from Aug 2023 to Aug 2026, computed per month within one wording (no month
   holds both). Information and finance are always the top two; accommodation and construction are the
   bottom two in every month but one (Mar 2026, when Ramp's health care sits 0.02 pp below construction).
   The persistent disagreement is **health care** (BTOS 3rd, Ramp 5th–6th) and **manufacturing** (Ramp
   3rd, BTOS 4th–5th); retail differs by one place in some months (Aug 2026: Ramp 4th, BTOS 5th). This
   is the most consistent of the findings, not a tested one: with 7 groups, ρ ≈ 0.8 is a coarse
   statistic, and agreement may be partly mechanical, since both lenses could be ordering sectors by a
   common trait (typical firm size, share of office work, digital intensity) rather than confirming each
   other's measurement.
3. **Trends since the wording change (Nov 2025 → Aug 2026).** Both rise in every sector and overall.
   Ramp was flat from Jul to Dec 2025 (44–46%), then climbed ~2 pp a month from January to May 2026,
   slowing in the summer; BTOS rose steadily (~0.6 pp a month nationally, no jump at the new sample year
   `202616`). No claim is made about which lens grew faster: the answer depends on the yardstick (pp or
   relative) and the bases differ. Sector growth ranks agree only weakly (ρ ≈ 0.3):
   accommodation is +8.0 pp on Ramp but flat on BTOS (+0.6, SE ≈ 0.5); retail +11.7 vs +2.9.
   The original-wording window (Sep 2023 → Sep 2025) shows the same picture: Ramp 29.0 → 45.2, BTOS
   3.7 → 10.0.
4. **BTOS current vs expected.** Expected use runs ~4 pp above current use (Aug 2026: 27.0 vs 23.1
   nationally; "Do not know" is ~26% for expected). Six months on, current use lands close to what was
   expected: national mean (current at m+6 − expected at m) 0.0 pp over the 4 current-wording pairs and
   −0.9 pp over 19 original-wording pairs (slightly optimistic). Accommodation and health care undershoot
   (−2.3, −1.3 pp). Too few current-wording pairs, and different panels each cycle, for a chart.
5. **Size mix cannot account for the overall gap on its own.** BTOS by size class
   (Aug 2026): 1–4 employees 23.3, 5–9 20.9, 10–19 21.7, 20–49 23.2, 50–99 26.8, 100–249 33.2, 250+ 40.3
   (37.8–42.7). Because the class values run 20.9–40.3, **any** reweighting of BTOS by size stays inside
   that range, while Ramp's overall (56.1) and each of its bands (Small 50.1, Medium 62.5, Large 66.8)
   sit above it. Even if every Ramp business had 250+ employees, BTOS would reach ~40%, leaving ≥ 13 pp
   (56.1 vs the 90% upper bound 42.7) unexplained (so a reweighting could close at most ~52% of the national gap on the point estimate, ~59% on
   the upper bound); for any mix under 250 employees, BTOS stays ≤ 33% (35.2% on the 90% upper bound). By
   sector, against each sector's **highest** size class (sector × size, Aug 2026): the bound holds
   clearly for manufacturing (Ramp 61.1 vs 250+ 38.5, SE 3.7), health care (43.4 vs 250+ 31.1, SE 4.5)
   and accommodation (33.1 vs 100–249 21.6, SE 2.7, upper bound 26.0; its 250+ cell, 19.0, averages over a
   suppressed cycle), and marginally for finance (73.7 vs 250+ 60.5, upper bound 72.7); not for
   information (250+ 83.1 > Ramp) or construction (250+ 42.1, equal). Retail is marginal and weak
   (48.8 vs 250+ 32.8, SE 9.4, upper bound 48.3, averaged over a suppressed cycle, so biased up).

## Design

**Window:** months both lenses cover; headline month = the latest month where Ramp has a value and BTOS
is not `partial` (Aug 2026 today). BTOS series: `ai_current`, `yes`, per wording; partial months
(the Aug 2023 and latest stubs) dropped from charts and kept in frames with their flag.

**Frames `analysis.py` returns** (reads only marts `072` `adoption_two_lenses` and
`btos_ramp_census_check`, `071` `btos_ai_monthly`, `070` `btos_ai_use` (size-class employee bounds, via
`SELECT DISTINCT size_class, min_employees, max_employees`), `btos_series_breaks` and
`btos_revision_check`, and `060` `ramp_adoption` (Ramp's size bands, `series_kind = 'size'`); never
`cachereg.sources`):

| Frame | Grain | Columns (main) |
|---|---|---|
| `levels` | group × lens at the headline month | group (overall + 7 sectors + 54 sensitivity), naics, naics_assumed, role, lens, pct, low90, high90, rank |
| `rank_agreement` | month × wording (BTOS wording of that month; never both) | spearman, n_sectors, the sectors whose ranks differ |
| `trend` | month × lens × wording × group | pct, low90, high90, partial, has_suppression, segment (wording); plus the break dates from `btos_series_breaks` |
| `sizes` | BTOS class A–G and Ramp Small/Medium/Large at the headline month | lens, size_label, min/max employees (BTOS only), pct, low90, high90 |
| `size_bound` | overall and per sector | BTOS national; the min and max class by value (with CI and which class it is: per sector this is not always 250+); Ramp level; `ramp_above_btos_max` (on the 90% upper bound); suppression flag |
| `expectations` | group × wording × month pair | expected at m, current at m+6, n_pairs; only pairs where neither month is `partial` (README table only) |
| `changes` | group × lens | value at Nov 2025 and headline month, pp change (README table only; never a cross-lens ratio) |
| `checks` | one row | revision-check rows, Ramp-Census check months agree/total, cycles used, Ramp import date |

**Visuals** (`x_png`, `linkedin_png` each; no `blog_html`, see licence):

1. **`sectors`: two side-by-side dot panels, one row per sector, same row order (Ramp's rank)**. Left
   panel: Ramp, share of businesses on Ramp paying for AI. Right: BTOS, share of employer businesses
   using AI, with 90% CI whiskers. Rank numbers at each dot; every sector whose rank differs in the
   shown month in the accent (Aug 2026: health care, manufacturing, retail), the rest grey. Overall as a separated bottom row. Headline claim: the two
   lenses order the sectors almost the same way (ρ for the month, and that it has held since 2023);
   subtitle: definitions of both lenses and the month.
   *Scale (argued):* both panels use the same 0–100% axis. Both are shares of businesses in percent, and
   a shared scale is the only one that exaggerates neither; but they are separate panels with no connecting
   lines, no gap labels and no ratio, so the chart claims order agreement, not a difference. Alternative if
   wanted: independent axes per panel (rejected: it hides the level gap).
2. **`trends`: two stacked panels, same 0–70% axis, monthly, overall only**. Top: Ramp paid (Jan 2023 →).
   Bottom: BTOS current use as **two separately labelled series** (original wording to Sep 2025, current
   from Nov 2025) with a visible gap and a break marker "new question wording, new Census series"; never
   one line across 2025-11. 90% band on BTOS. Nov 2025 → headline month shaded in both. Headline claim:
   both lenses rise; no rate comparison.
3. **`sizes`: BTOS's seven size classes beside Ramp's three bands**, two panels, same 0–100% axis. BTOS
   bars with CI; a shaded band marking the BTOS class range (min–max), carried across both panels as the
   only cross-panel mark. Ramp bands labelled "thresholds not published by Ramp". Headline claim: every
   Ramp band sits above BTOS's largest size class, so BTOS's weighting by business count cannot account
   for the level difference on its own.
   *The one cross-lens claim (argued):* this is an ordering bound, not a ratio or difference: it needs
   only that a size-reweighted BTOS cannot leave its class range. The README may state the residual in
   pp as a bound ("≥ 13 pp above the upper CI"), labelled as our derivation.

Tables (sector levels and ranks, changes since Nov 2025, expectations, sector × 250+) go in the README;
`table_png` is not built yet (Phase 4).

**Config** (`explore.yaml`): `headline_month: latest` (or a fixed month), `trend_start: 2023-01`,
`ci: 0.90`, `ramp: true` (see fallback). Sources: `[ramp_ai_index, census_btos]` (footer credits both
automatically).

## Caveats each visual carries (subtitle/METHOD line, plus README)

- **All:** Ramp = observed paid AI spend (cards, bill pay) by businesses on Ramp, early-adopter skew,
  free tools invisible, revised in place (Latest-only). BTOS = self-reported use "in any of its business
  functions", last two weeks, all U.S. employer businesses weighted by firm count; "Do not know" in the
  denominator. **Monthly BTOS values are Cache Register's day-weighted averages of Census's biweekly
  estimates, not Census estimates** (METHOD line). Not one measure of the other.
- **`sectors`:** "Technology and media" → NAICS 51 is assumed (BTOS 54, 43.0%, would not change the
  top two; noted in subtitle or footnote); BTOS 62 includes social assistance; BTOS sector 11 and
  multi-sector firms (`XX`) are outside the seven rows; a rank of 7 groups is coarse, and agreement may
  reflect a common driver of both lenses (firm size, office work) rather than mutual confirmation.
- **`trends`:** the two wordings are separate Census series (~7 pp level shift at the change); Oct 2025
  is a shutdown gap; panels and sample years change, with no visible jump at `202616`; month windows
  differ (calendar month vs two-week reference period, dated by reference days).
- **`sizes`:** Ramp's Small/Medium/Large have no published thresholds; BTOS's business-count mix is not
  published, so only the range bound is claimed, not a reweighted estimate; BTOS size classes are national
  (not by sector) in the chart; the sector-level bound holds only where the table says so.

## Licence

Ramp's `redistribution` is `unknown` → the receipt gate would withhold `blog_html` and `data.json`.
Explorations do not run the gate, so `blog_html` is simply **not declared** (no target inlines Ramp
data; the gitignored `story_frames.json` that `render` writes for every exploration does hold the frames). PNGs are allowed (Ramp `derived_charts: allowed-with-attribution`; BTOS public domain);
the footer credits both from `SOURCE.md`.

**Fallback without Ramp imports** (`cachereg build --sources census_btos`, PLAN §10): mart `072` and
`ramp_adoption` are then absent, and `render` refuses a Story whose sources differ from `explore.yaml`'s.
So the fallback is an explicit config switch, not a silent degrade: `config.ramp: false` with
`sources: [census_btos]` and visuals `[trends, sizes]`. The analysis then reads only `070`/`071`, sets
`Story.sources = ["census_btos"]`, skips `levels`, `rank_agreement`, `changes`' Ramp rows and the
Ramp checks, and the two charts draw their BTOS panel alone. With `ramp: true` (default) and no `072`
table, the analysis stops with an error naming the missing Ramp import and the switch.

## Decisions (author review, 2026-10-08: the recommendations, as proposed)

1. **Shared 0–100% scale** on `sectors` and `sizes`, in separate panels with no connecting lines, gap
   labels or ratios. The charts claim order agreement and an ordering bound, never a difference.
2. **`trends` is a visual**, claiming only that both lenses rise; no rate comparison. The sector changes
   since Nov 2025 stay a README table.
3. **The size bound may be stated in pp in the README** (the one cross-lens derivation, labelled as Cache
   Register's, computed against BTOS's 90% upper bound); the chart states only the range ordering.

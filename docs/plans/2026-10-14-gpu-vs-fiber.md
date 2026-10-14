# Plan: GPUs vs dark fiber, residual value after a bust (exploration)

Status: EXPLORATION BUILT · 2026-10-14

Outcome: `explore/2026-10-14-gpu-vs-fiber/` renders four visuals (lives, prices, recovery, generations)
from 249 cited rows. So far GPUs look like the fiber's electronics, not its glass (2–6-year book lives),
yet their rents have held up far better than bandwidth prices did. Not promoted.

## Question
In the dot-com bust the carriers failed but the fiber stayed useful: later owners bought it cheaply
and lit it as demand grew. If the AI buildout busts, does anything keep value the same way? An open
test: the piece reports whichever way the data fall.

Two assets stand in for "the fiber" (author, 2026-10-14):
- **GPUs**, the short-lived equipment. In the fiber analogy they correspond to the optics at each end
  (lasers, DWDM), which were replaced while the glass stayed.
- **Infrastructure**: data-centre shells, power contracts and grid interconnects, the long-lived
  assets that may play the part of the glass.

"Value" has two meanings that must stay separate: **value to the original investor** (what they
recovered) and **usefulness to the next owner** (whether the asset kept working and earning). The fiber
story is a loss on the first measure and a win on the second.

## Measures (all four chosen by the author)
1. **Market price decay.** Price as % of its level at launch against years since launch: GPU rental
   $/GPU-hour and resale prices (A100 from 2020, H100 from 2023) against long-haul bandwidth and
   dark-fiber IRU prices after 1998. The headline chart if the data hold up.
2. **Book useful life.** The depreciation lives companies state in their 10-Ks: servers and network
   equipment (Microsoft and Alphabet extended to 6 years in 2022–23, Meta to 5.5, Amazon cut from 6 to 5 in
   2025, CoreWeave 6) against fiber and conduit (typically 20–30 years in carriers' 10-Ks around 2000)
   and buildings (≈ 25–40 years). The lives are stated in the notes' text, not as reliable XBRL facts, so
   they are curated and cited (see Data). They show what companies assume, not what assets fetch.
3. **Bankruptcy recovery.** Sale price against capital invested for dot-com carriers (Global Crossing,
   360networks, Williams Communications, others where a filing or court record gives both figures),
   set beside GPU-era distress where it exists (GPU-backed loans, their stated collateral and
   advance rates, any liquidation or resale disclosed). If there is no GPU-era distress yet, the
   chart says so instead of standing in a guess.
4. **Obsolescence per generation.** Performance per dollar by GPU generation (A100 → H100 → B200 →
   Rubin) against the capacity of one fiber pair as DWDM generations upgraded it. New GPU generations
   make old GPUs worth less; new optics made the same old fiber worth more. This measure explains
   why the curves in 1 differ.

## Data (public sources and our own curation only; author, 2026-10-14)
- **New curated source `curated_asset_values`**, our own CC BY 4.0 dataset on the
  `curated_disclosures` pattern (one row per stated figure, cited, a verbatim quote of ≤ 25 words,
  `recorded_on` driving as-of, append-only). `curated_disclosures` can't hold these rows: its entity must
  be an AI vendor in `vendors.yaml` and its metrics are about usage. Columns: `asset` (controlled:
  `gpu_a100`, `gpu_h100`, `gpu_b200`, `dark_fiber`, `lit_bandwidth`, `dc_shell`, …), `entity` (free
  text with an optional ticker; dot-com carriers are not in `vendors.yaml`), `metric` (controlled:
  `rental_price`, `resale_price`, `iru_price`, `bandwidth_price`, `book_useful_life`,
  `capital_invested`, `distressed_sale_price`, `utilization`, `perf_per_dollar`, `capacity_per_pair`),
  value, unit, dates, `source_kind` (primary/secondary), URL, quote. It is a new source folder under the
  contract, with no core changes. (As built, the vocabulary is in `config/curated/asset_vocab.yaml`.)
- **SEC EDGAR** (already ingested): current companies' 10-K text for useful lives; full-text search
  and filing indexes for dot-com carriers (pre-XBRL, so curated by hand rather than staged from facts).
- **Public secondary figures** (press and research citing GPU rental prices, dark-fiber utilization in
  2001, bandwidth price indices) enter only as cited `secondary` rows, and charts mark them.

## Risks to the open test
- **No licensed GPU price history.** Free public points are sparse and mostly secondary (press quoting
  brokers or indices). Measure 1 may end up with a few dozen dated points per GPU, not a daily
  series; the chart then shows points with bounds, not a smooth curve.
- **Survivorship in the fiber record.** Prices from 1998–2005 survive in press and filings unevenly.
  Each figure is used with its stated scope (route, capacity, IRU term), and figures with different
  scopes are not combined into one index.
- **Different clocks.** Fiber's story ran about 10 years from build to absorption; the H100's has run
  about 3. The comparison is aligned on years since launch, and the horizon we cannot see yet for GPUs
  is left blank.
- **Infrastructure has little price data.** Data-centre and power values come mostly from book lives
  and stated contract terms (PPA and lease lengths), not from market prices.

## Deliverables
1. `src/cachereg/sources/curated_asset_values/` (SOURCE.md, fetch, stage, validation, synthetic tests)
   plus seed rows, each cited.
2. A mart only if a second analysis needs it; otherwise the exploration reads the staged table.
3. `explore/2026-10-14-gpu-vs-fiber/` (explore.yaml, analysis.py, charts.py, README with method and
   caveats). Draft visuals: (a) value-decay curves on a years-since-launch axis; (b) book useful life,
   asset by asset; (c) recovery in cents per dollar invested; (d) generations: GPU perf/$ against
   capacity per fiber pair.

Out of scope: paid or ToS-restricted price data (unless the author decides otherwise later), any
forecast of an AI bust, a link reservation, promotion. Kept separate from the CoreWeave credit
exploration (analyses never import each other); a figure both need goes into the curated source.

## Decisions (author, 2026-10-14)
- A new curated source, `curated_asset_values` (built: `src/cachereg/sources/curated_asset_values/`,
  mart `110_asset_values`). The shared rules of both curated datasets moved to `sources/_curated.py`.
- Press may carry headlines, and sourcing should be broad: research notes, published indices and
  archived pages are all welcome, marked `secondary`.
- Values stay in the unit the source stated (each metric lists its allowed units); the analysis
  converts and says how.

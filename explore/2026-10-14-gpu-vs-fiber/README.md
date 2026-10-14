# GPUs vs dark fiber, value after a bust

*Exploration · started 2026-10-14 · design: [`docs/plans/2026-10-14-gpu-vs-fiber.md`](../../docs/plans/2026-10-14-gpu-vs-fiber.md)*

## Question
In the dot-com bust the carriers failed, but their fiber stayed useful: later owners bought it cheaply
and lit it as traffic grew. If the AI build-out busts, does anything keep its value the same way? This
is an open test that compares GPUs, and the AI infrastructure around them, with the fiber of 1998–2012 on
four measures: book useful lives, market prices, what bankrupt networks fetched, and what each new
generation did to the old one.

## Findings (curated_asset_values, 249 rows recorded 2026-10-14)
- **Book lives put GPUs with the electronics, not the glass.** The AI servers of Microsoft, Alphabet,
  Amazon, Meta, Oracle, CoreWeave and Nebius are written off over 2–6 years (most say 6; Amazon cut a
  subset from 6 to 5 for 2025, citing the pace of AI). The 2000–01 carriers wrote off their network
  electronics over 2–14 years and their fiber, conduit and rights-of-way over 7–57 (typically 20–25).
  The long-lived AI assets are the buildings (5–60 years, mostly 25–40) and the power contracts
  (Microsoft's and Meta's nuclear PPAs: 20 years each).
- **So far, GPU rents have held up far better than bandwidth prices did.** About three years after the
  first quote, a New York–Los Angeles OC-3 circuit cost 12.6% of its 2000 price, and US IP transit fell to
  0.4% of its 1998 price by 2010. The H100's market rate stood at 59% of its launch-era $4.70 by
  June 2026, after a low of 43% in December 2025. At Lambda, on-demand prices in October 2026 were
  above each GPU's first listing there: A100 186% (since 2023), V100 144% (since 2022), H100 114% (since 2024).
- **The dot-com investors lost almost everything; the networks did not.** Global Crossing raised about
  $20bn, owed $12.4bn at its January 2002 filing, sold 61.5% of itself for $250m in August 2002, and
  was bought whole by Level 3 for about $3bn in 2011. Velocita's 14,000-mile network went to AT&T for
  $37m against $827m of debt. Williams Communications owed $7.15bn and was bought for $680m in 2005. No
  GPU fleet has been sold out of bankruptcy as of this dataset. The GPU-backed loans so far are sized
  against customer contracts, and CoreWeave's DDTL 2.0 agreement depreciates the GPU collateral over six
  years.
- **New optics made old glass worth more; new GPUs make old ones worth less.** One fiber pair carried
  800 Gbps with 2001 optics and 20–21 Tbps on the transatlantic and African cables of 2017–2025, 26×
  more. NVIDIA claims each GPU generation is up to 10–30× better than the last on its chosen workloads.
  For now, demand has outrun that obsolescence: old GPUs still rent near or above their earlier prices.

## Method
- **Data:** the `asset_values` mart (110) of our curated source `curated_asset_values`, one row per
  stated figure, each with its source URL and a quote of ≤ 25 words. Every point on a chart is picked by
  row id in `explore.yaml`.
- **Prices:** each series is shown as a % of its own first quote, against years since that quote.
  Only quotes from one source are joined into a line, except the H100 market line, which joins Latent
  Space's 2023–24 quotes to Silicon Data's neocloud H100 index. Lambda's 8-GPU instance prices are
  divided by 8 to get a per-GPU price. A quote covering a period is placed at the period's midpoint.
- **Lives:** a company's stated range (low and high rows of one filing) is one bar; a single figure is a dot.
- **Recovery:** dollars as stated, at the date each figure refers to.
- **Generations:** capacity per pair as stated (Tbps converted to Gbps); NVIDIA's "up to" multiples as stated.

## Caveats
- The price figures are scattered quotes from different venues, tiers and configurations, not
  continuous series. Hyperscalers' list prices barely moved (AWS's 8-GPU V100 instance cost $24.48 an
  hour in both 2018 and 2024), while marketplace prices swung.
- Lit bandwidth is priced per unit of capacity, and the optics kept multiplying that capacity. So its
  fall overstates what happened to the fiber itself. There is no public dark-fiber price series for
  1998–2010; the only per-mile prices found are from 2012 (CTC: $500–$3,000 per strand-mile long-haul).
- Book useful lives are accounting choices, not observed lifetimes. A stated range spans asset classes
  within one line of the accounts (Microsoft's 2–6 years covers its servers and network equipment), and
  buildings' lives include offices.
- The bankruptcy figures differ in scope. Global Crossing's $250m bought 61.5% of the company and the
  2011 $3bn bought all of it, after years of new investment. Velocita's $37m bought the network only.
- NVIDIA's multiples are marketing claims on workloads it chose.
- About 43% of the rows are press or research (`secondary`); the rest come from filings, company
  releases and court records.
- Three years of GPU history is set against twelve of fiber. The GPU side's later years have not
  happened yet.

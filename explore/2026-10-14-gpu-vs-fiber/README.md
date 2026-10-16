# GPUs vs dark fiber, value after a bust

*Exploration · started 2026-10-14 · design: [`docs/plans/2026-10-14-gpu-vs-fiber.md`](../../docs/plans/2026-10-14-gpu-vs-fiber.md)*

## Question
In the dot-com bust the carriers failed, but their fiber stayed useful: later owners bought it cheaply
and lit it as traffic grew. If the AI build-out busts, does anything keep its value the same way? This
is an open test that compares GPUs, and the AI infrastructure around them, with the fiber of 1998–2012:
how long each is assumed to last, what happens to its price, what bankrupt owners recovered, and who
could buy the assets now.

## Findings (curated_asset_values to 2026-10-16; SEC filings to 2026-10-13)
Six visuals, in story order.
- **lives: GPUs look like the electronics on the fiber, not the glass.** The AI servers of Microsoft,
  Alphabet, Amazon, Meta, Oracle, CoreWeave and Nebius are written off over 2–6 years (most say 6;
  Amazon cut a subset from 6 to 5 for 2025, citing the pace of AI). The 2000–01 carriers wrote off
  their network electronics over 2–14 years and their fiber, conduit and rights-of-way over 7–57
  (typically 20–25). The long-lived AI assets are the buildings (5–60 years, mostly 25–40) and the
  power contracts (Microsoft's and Meta's nuclear PPAs: 20 years each).
- **book-life: six years on the books, three newer generations.** From NVIDIA's announcement, a
  six-year book life (the servers' life at Microsoft, Alphabet, Oracle and CoreWeave, and the GPU
  collateral's in CoreWeave's DDTL 2.0 loan) took the A100 to May 2026. In that time NVIDIA announced
  the H100, Blackwell and Rubin. An H100 stays on the books to 2028 and has two newer generations so
  far. Chips bought after launch stay on the books longer.
- **ladder: every generation got dearer to rent in 2026.** Lambda's on-demand price per GPU-hour
  (8-GPU machines), January to October 2026: V100 $0.55 → $0.79 (+44%), A100 $1.79 → $2.79 (+56%),
  H100 $2.99 → $3.99 (+33%), B200 $4.99 → $6.69 (+34%).
- **glut: no glut signal in GPU rents yet.** In 2001 the glut showed in prices within a year. A New
  York–LA OC-3 line lost 67% of its price in its first year, when Merrill Lynch put the use of carriers'
  lit capacity at about 2.7%. The H100's market rate fell to 43% of its launch-era $4.70 by December 2025,
  then rose to 59% by June 2026.
- **recovery: investors lost almost everything; the networks lived on.** Global Crossing raised about
  $20bn, owed $12.4bn at its January 2002 filing, sold 61.5% of itself for $250m that August, and
  was bought whole by Level 3 for about $3bn in 2011. Velocita's 14,000-mile network went to AT&T for
  $37m against $827m of debt. Williams Communications owed $7.15bn and was bought for $680m in 2005. No
  GPU fleet has been sold out of bankruptcy as of this dataset.
- **buyers: the likely buyers have the cash.** On their latest balance sheets (May–July 2026),
  Alphabet, Amazon, Meta, Microsoft and NVIDIA hold $589bn in cash and short-term investments
  (Alphabet $242bn). Oracle owes $130bn against $32bn (4×) and CoreWeave $36bn against $6bn (6×), before
  leases. In 2002–05 the buyers of bankrupt networks were survivors with cash (Level 3, AT&T,
  Hutchison and ST Telemedia, Reliance). The lenders that would take GPU collateral first include
  Blackstone and Magnetar (CoreWeave), Apollo (the xAI-related compute deal) and Macquarie (Lambda).

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
- **Book life:** each generation from the date of the cited NVIDIA release that announced it, plus six years.
  Later generations are counted only when already announced (no roadmaps).
- **Ladder:** two prices per generation from one venue and configuration (Lambda on-demand, 8-GPU
  machines, per GPU), read from archived pricing pages on 2026-01-09 and 2026-10-01.
- **Glut:** the price paths' first five years, from the same rows as the price analysis.
- **Buyers:** mart 111 (SEC XBRL): cash and cash equivalents plus short-term investments; debt as
  `LongTermDebt` (current and non-current) or its parts, else `DebtInstrumentCarryingAmount`; leases
  excluded. Each company's latest balance sheet with both measures, as filed by the build's as-of.
  "Stretched" means debt is at least 2× cash and short-term investments.

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
- The ladder is one venue on two dates; hyperscalers' list prices barely move, and Lambda's prices may
  reflect its own capacity.
- Announcement dates mark generations; volume shipments came months later.
- Balance sheets: Alphabet's cash and short-term investments doubled in its Q2 2026 10-Q (equity rose by
  about $160bn in the same quarter); leases, large for CoreWeave ($16bn operating) and Oracle, are not
  counted as debt; cash on hand is not the same as willingness to buy.
- About 43% of the rows are press or research (`secondary`); the rest come from filings, company
  releases and court records.
- Three years of GPU history is set against twelve of fiber. The GPU side's later years have not
  happened yet.

# GPUs vs dark fiber, value after a bust

*Exploration · started 2026-10-14 · design: [`docs/plans/2026-10-14-gpu-vs-fiber.md`](../../docs/plans/2026-10-14-gpu-vs-fiber.md)*

## Question
In the dot-com bust the carriers failed, but their fiber stayed useful: later owners bought it cheaply
and lit it as traffic grew. If the AI build-out busts, does anything keep its value the same way? This
is an open test that compares GPUs, and the AI infrastructure around them, with the fiber of 1998–2012:
how long each is assumed to last, what happens to its price, what bankrupt owners recovered, and who
could buy the assets now.

## Terms
On the charts, **glass** is literal: the fiber, with its conduit and rights-of-way. **Gear** is the
short-lived electronics written off within a decade: the dot-com era's lasers, switches and routers; today's
**GPU servers** (the filings' "servers and network equipment": mostly GPU servers, with CPU servers, storage
and network gear; the filings do not split GPUs out). The **powered shell** is the AI era's long-lived site: land and buildings, with the power
plants and grid behind them. The fiber between today's data centres is left out: under 2% of the AI
builders' annual property additions, and not the dot-com build-out.

## Findings (curated_asset_values to 2026-10-16; SEC filings to 2026-10-13)
The three story visuals, in posting order (each with a still, a video and an HTML version), then the
earlier exploration views.
- **years (gpus-are-not-glass): dot-com glass went on the books for 22.5 years; today's GPU servers get
  5.5.** One square per year: the median across companies of the midpoint of each stated life. Dot-com:
  network electronics 7 (2–14 across Genuity, Level 3, Qwest and WorldCom), fiber, conduit and rights-of-way
  22.5 (7–57). AI: GPU servers and network gear 5.5 (2–6 at Microsoft, Alphabet, Amazon, Meta, Oracle,
  CoreWeave and Nebius), data-centre buildings 23.5 (5–60), power plants and grid 46 (stated total lives at
  Constellation, Dominion, AEP and Exelon: gas 40–45, nuclear 54–64, transmission and distribution 5–85). In
  lime, the asset each build-out is remembered for; the video builds the dot-com era, pauses, then the AI era.
- **split (glass-then-gear-now): in 2000, fiber builders put 60% of known spending into long-lived glass; AI
  builders now put 65% into short-lived GPU servers.** Additions to gross property and equipment in one year: $12.8bn at four fiber
  carriers that report fiber and electronics apart (Level 3, Williams, Genuity, Metromedia Fiber; 2000) —
  glass 60%, buildings 16%, gear 24% of the known part — against $521bn at Microsoft, Alphabet, Amazon,
  Meta, Oracle and CoreWeave in their latest year (41×): GPU servers and network gear 65%, powered shell 35%.
  Counting the unassigned additions (construction in progress, lumped lines) all one way, glass is 42–72% of
  the 2000 additions and GPU servers 48–74% of today's.
  A Harvard Business School case (2001) puts trenching and laying conduit and fiber at over 70% of a dark
  network's cost. Nationally the picture differs: US spending on communications equipment ran several times
  fiber cable and telecom structures in 2000 (BEA via the Richmond Fed; Doms, San Francisco Fed).
- **exposure (own-the-shell): CoreWeave's property is 62% GPU servers and 8% buildings, and it owes 6× its
  cash.** Gross property and equipment on each latest 10-K, by kind, with debt ÷ cash and short-term
  investments (leases excluded), sorted by the GPU-server share: CoreWeave 62% GPU servers, 8% shell (6.4×);
  Microsoft 50%, 49% (0.5×); Oracle 49%, 18% (4.1×); Meta 42%, 29% (0.9×); Alphabet 35%, 38% (both partly
  estimated; 0.4×); Amazon 32%, 29% (1.1×). CoreWeave rents its data centres, so its landlords own the shell;
  Oracle's construction in progress is mostly servers awaiting deployment. The two most indebted hold the
  least shell.

### Earlier views (exploration only)
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
- **Years:** per group, the median across companies of the midpoint of each company's stated life (a part
  square for a half year); the stated ranges are in the HTML tooltips. Power: stated total lives only (left
  out: remaining lives, Talen's fresh-start basis, Entergy's tax-note average, AEP's 20–162-year generation
  range, "up to" figures, wind and solar).
- **Glass:** gross property and equipment by class from each company's latest 10-K note (both columns
  are in the dataset), in three buckets: servers and network equipment (short-lived); land, buildings
  and leasehold improvements (long-lived); construction in progress and lines that mix kinds or hold
  other equipment (mixed). Gross, so fully depreciated assets still in use count.
- **Recovery:** dollars as stated, at the date each figure refers to.
- **Book life:** each generation from the date of the cited NVIDIA release that announced it, plus six years.
  Later generations are counted only when already announced (no roadmaps).
- **Ladder:** two prices per generation from one venue and configuration (Lambda on-demand, 8-GPU
  machines, per GPU), read from archived pricing pages on 2026-01-09 and 2026-10-01.
- **Glut:** the price paths' first five years, from the same rows as the price analysis.
- **Alphabet's technical infrastructure** (servers and data centres in one line) is split 60/40 into gear
  and powered shell by Alphabet's own statement of where that investment goes; drawn lighter as an estimate.
  Its 40% includes networking equipment, so the shell share is an upper bound.
- **Split:** for each company, the change in gross PP&E by kind between two balance sheets a year apart
  (latest filing's figures where a year was restated; the dot-com carriers at 1999-12-31 and 2000-12-31,
  Touch America only on the books as it has no 1999 column), summed per era. "Known" excludes the mixed
  line (construction in progress, lumped lines). A change in gross PP&E is additions net of retirements and
  impairments.
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

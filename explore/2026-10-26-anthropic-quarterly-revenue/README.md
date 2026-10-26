# Anthropic quarterly revenue

*Exploration · started 2026-10-26 · prompted by a chart of the quarterly table in Anthropic's S-1, shared with
the author the day the S-1 was filed; this replicates that chart's analysis from the filing itself.*

## Question
How fast has Anthropic's recognised revenue grown, quarter by quarter, in the figures it filed with the SEC?

## Finding (S-1 filed 2026-10-26; as of 2026-10-26)
- **Revenue in 2026 Q2 was $11,555M, 14.7× the $787M of 2025 Q2.** The S-1 states the same growth in its own
  words ("grew 1,368% year over year for the three months ended June 30, 2026"); 11,555 ÷ 787 − 1 = 1,368%.
  2026 Q1 was 12.6× 2025 Q1 ($4,731M vs $376M).
- **Growth from the previous quarter slowed through 2025, then sped up in 2026:** +109%, +76%, +48%, +132%,
  +144% (2025 Q2 to 2026 Q2). The two latest quarters are the fastest in the table.
- **Over five quarters revenue rose 30.7×** ($376M in 2025 Q1 to $11,555M in 2026 Q2).
- **No quarter tripled.** The quarter-on-quarter multiples are 2.1×, 1.8×, 1.5×, 2.3× and 2.4×. The source
  chart's title borrows "triple, triple, double, double, double" (T2D3, a growth path for software companies
  measured in *years*: 72× over five years); Anthropic's five quarterly steps multiply to 30.7×, in five quarters.
- **The filed quarters agree with Anthropic's earlier run-rate statements** (mart 080, `revenue_run_rate`;
  context only, not a series): four times a quarter's revenue (our arithmetic) is $5.5B for 2025 Q3 against
  "over $5 billion" in August 2025, $8.2B for 2025 Q4 against "about $9 billion" at the end of 2025, and $46.2B
  for 2026 Q2 against "over $30 billion" on April 6 and "over $47 billion" by late May 2026. A run-rate taken
  late in a fast-growing quarter is expected to exceed four times that quarter's average.

## Method
- **Data:** the S-1's *Quarterly Consolidated Statements of Operations* (Revenue row, in millions), recorded in
  the curated disclosures dataset as six `revenue_quarterly` rows (`config/curated/disclosures.csv`, ids
  `anthropic-revenue_quarterly-2026-10-26[-n]`; unit `usd_millions_per_quarter`, as the table states it).
  The S-1 has no XBRL revenue facts (only the filing-fee exhibit is tagged), so the `sec_edgar` source cannot
  supply them. The analysis reads mart 080 (`disclosures`) only.
- **Change from the previous quarter** = quarter ÷ previous quarter − 1; quarters must be contiguous calendar
  quarters (checked). **Year over year** = quarter ÷ the same quarter a year earlier, so it exists only for
  2026 Q1 and Q2.
- **Run-rate comparison:** quarterly revenue × 4 set beside stated run-rates. It is a consistency check, not
  a conversion: the two metrics stay separate (`config/curated/metrics.yaml`).

## Caveats
- Quarterly figures are unaudited (the annual statements in the same filing are audited).
- An S-1 can be amended before the offering. The filing leaves the quarter to September 30, 2026 blank; when
  an amendment fills it, it can be added as a new row (and any changed quarter as a superseding row).
- Six quarters is a short series: two year-over-year points and five quarter-on-quarter ones. Percent changes
  from small bases (2025 Q1–Q2) move a lot on small absolute amounts.
- Recognised revenue only: the same table shows operating expenses (compute and infrastructure, personnel, a
  $1.5B legal settlement in 2025 Q3) that this exploration does not analyse.

## Reproduce
`cachereg fetch curated_disclosures && cachereg build && cachereg render explore/2026-10-26-anthropic-quarterly-revenue --as-of 2026-10-26`

# Anthropic quarterly revenue

*Exploration · started 2026-10-26 · prompted by a chart of the quarterly table in Anthropic's S-1, shared with
the author the day the S-1 was filed; this replicates that chart's analysis from the filing itself.*

## Questions
1. How fast has Anthropic's recognised revenue grown, quarter by quarter, in the figures it filed with the SEC?
2. Does its slower growth in 2025 Q3 (+76%) and Q4 (+48%) match a seasonal pattern in engineering work
   (summer time off, then Thanksgiving, year-end holidays and code freezes), as the author asked?

## Finding 1: revenue (S-1 filed 2026-10-26; as of 2026-10-26)
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

## Finding 2: seasonality (as of 2026-10-26; seasonal base 2021–2024)
- **Seasonal patterns do not explain the 2025 Q4 slowdown.** Removing each comparator's typical quarter
  pattern, Q4 stays the slowest quarter every time: +48% as filed, +52% per US working day, +38% with
  GitHub's pattern removed, +47% with cloud usage revenue's pattern removed (`adjusted` visual).
- **Public GitHub pushes have a strong, regular season, but only the Q3 half matches the hypothesis.** US git
  pushes run 8% below the year's average quarter in Q3 (every base year between −7% and −9%) and 7% *above*
  it in Q4 (+4% to +9%), then +5% in Q1 (`seasonal` visual; world totals: −7% in Q3, +4% in Q4). Removing that
  pattern lifts Anthropic's Q3 2025 from +76% to +91% but lowers Q4 from +48% to +38%, and Q1 2026 from
  +132% to +121%.
- **Usage-priced cloud revenue barely has a season.** The summed revenue of Snowflake, Datadog, MongoDB,
  Cloudflare, DigitalOcean, Twilio and Fastly moves at most 2% from its year's average quarter; its one
  visible effect, Q1 at −2%, is the length of the quarter (90 days against Q4's 92). Those companies grew
  +6.5% in 2025 Q3 and +7.0% in Q4, about as fast as in 2024 (+6.9%, +5.2%): no late-2025 slowdown in
  developer infrastructure spending either.
- **Working days move growth by 3% at most** (61 to 64 a quarter; Q4 2025 had 62 against Q3's 64).
- **Size, not just direction:** the largest seasonal swing measured (GitHub, Q3 to Q4, about 15 points)
  is far smaller than Anthropic's (+76% to +48% to +132%). A holiday dip the size of the S-1's own example
  (spend about 20% lower for the two weeks to January 2, 2026) is about 3% of a quarter.
- **The one co-movement is the other way round:** US pushes per developer jumped in 2025 Q4 (1.35, from
  1.20) and again in 2026 Q1 (1.77; pushes +40% in a quarter, developers +7%), the quarter Anthropic's
  growth re-accelerated. The data cannot say why; coding agents pushing on developers' behalf would fit.

## Method
- **Data:** the S-1's *Quarterly Consolidated Statements of Operations* (Revenue row, in millions), recorded in
  the curated disclosures dataset as six `revenue_quarterly` rows (`config/curated/disclosures.csv`, ids
  `anthropic-revenue_quarterly-2026-10-26[-n]`; unit `usd_millions_per_quarter`, as the table states it).
  The S-1 has no XBRL revenue facts (only the filing-fee exhibit is tagged), so the `sec_edgar` source cannot
  supply them. The analysis reads mart 080 (`disclosures`) only.
- **Change from the previous quarter** = quarter ÷ previous quarter − 1; quarters must be contiguous calendar
  quarters (checked). **Year over year** = quarter ÷ the same quarter a year earlier, so it exists only for
  2026 Q1 and Q2.
- **Comparators** (marts `130_github_activity` and `031_revenue`; config in `explore.yaml`):
  - US git pushes from the GitHub Innovation Graph (CC0; release of 2026-07-07, quarters to 2026 Q1); `_world`
    (all economies except the EU aggregate) as a sensitivity.
  - The summed revenue of the `devinfra` group in `config/entities/tickers.yaml`, in quarters where all seven
    report (XBRL company facts; Q4 = fiscal year − nine months; Snowflake's and MongoDB's November–January
    quarters count as Q4, by midpoint).
  - US working days: weekdays minus New Year's Day, Martin Luther King Jr. Day, Presidents' Day, Memorial
    Day, Juneteenth, Independence Day, Labor Day, Thanksgiving and the day after, Christmas Eve and Christmas
    (observed on the nearest weekday when they fall on a weekend).
- **Seasonal factor** of a calendar quarter = the mean over 2021–2024 of (that quarter's log growth from
  the previous quarter − the mean log growth of its year), shown as a % (whiskers: lowest and highest year).
  The base stops before 2025, when pushes began rising far faster than developers. Base 2021–2023 or
  2022–2024 changes Anthropic's adjusted growth by at most one point.
- **Removing a pattern:** adjusted growth = (1 + growth as filed) ÷ (1 + the comparator's factor for that
  calendar quarter) − 1. Per working day uses each quarter's actual working days instead.
- **Run-rate comparison:** quarterly revenue × 4 set beside stated run-rates. It is a consistency check, not
  a conversion: the two metrics stay separate (`config/curated/metrics.yaml`).

## Caveats
- **GitHub counts public repositories only.** Most company work is private, and public activity has its
  own calendar: October's Hacktoberfest and December's Advent of Code may lift Q4. A private-repository
  series would test the hypothesis better; none is public.
- Quarterly data cannot show a two-week holiday dip; a weekly series (e.g. npm registry downloads) could.
- Anthropic has one year of each quarter, so its own seasonality cannot be estimated, only compared with
  others'; releases, compute and pricing changes (see the S-1) move its growth far more.
- The cloud companies sell under annual contracts that smooth usage, and their customers are not only
  engineers.
- Quarterly figures are unaudited (the annual statements in the same filing are audited).
- An S-1 can be amended before the offering. The filing leaves the quarter to September 30, 2026 blank; when
  an amendment fills it, it can be added as a new row (and any changed quarter as a superseding row).
- Six quarters is a short series: two year-over-year points and five quarter-on-quarter ones. Percent changes
  from small bases (2025 Q1–Q2) move a lot on small absolute amounts.
- Recognised revenue only: the same table shows operating expenses (compute and infrastructure, personnel, a
  $1.5B legal settlement in 2025 Q3) that this exploration does not analyse.

## Reproduce
`cachereg fetch curated_disclosures github_innovation_graph sec_edgar && cachereg build && cachereg render explore/2026-10-26-anthropic-quarterly-revenue --as-of 2026-10-26`

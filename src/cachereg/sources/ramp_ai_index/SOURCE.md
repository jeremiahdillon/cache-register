# Ramp AI Index (`ramp_ai_index`)

**Page:** https://ramp.com/data/ai-index (methodology and "Sources and Definitions" on the same page;
background: https://ramp.com/data/how-we-built-the-ramp-ai-index)
**Access:** manual. Each view's "Get the data" button copies the view's full history to the clipboard;
the author imports it with `cachereg fetch ramp_ai_index --from-clipboard --cut <cut>` (or
`--from-file PATH`). The automated route is the Ramp Data API (Data Partner Program key), not built.
**License:** none granted. Ramp "does not license this data, but provides non-exclusive, opt-in,
aggregated data to the public". The page has no licence, "cite as" or terms text. Charts credit
"Source: Ramp AI Index", so we credit "Ramp AI Index (ramp.com/data/ai-index), as of {as_of}".
**Last verified:** 2026-10-07 (pastes of every imported view and a read of the page; design in
`docs/plans/2026-10-07-ramp-ai-index.md`)

## What it contains

Two populations, never mixed in one denominator:

- **Economic indicators** (corporate card and invoice/ACH payments, 70,000+ US businesses on Ramp):
  monthly adoption (share of businesses with AI spend: overall, per lab, by sector, by business
  size), AI spend per employee (median, top 10%, top 1%; median by sector and size) and AI share of
  business spend excluding payroll (overall and 20 sectors). From 2023-01 (adoption), 2023-07 (share)
  or 2023-09 (per employee).
- **Tokenomics** ("Ramp AI Token Spend Management": model-attributed API spend of customers who
  connected their AI providers; Ramp says these are not representative of its total AI spend, though
  directionally similar): weekly token volume and token spend by model maker as an **index**, and daily
  blended, input and output price per million tokens (OpenAI, Anthropic, and both). From 2025-01.

## Classification
- history: native (every paste is the view's full history)
- revisions: **revised** — Ramp revises past months as late transactions arrive (stated in its
  September 2026 report) → **Latest-only**
- redistribution: **unknown** (treated as forbidden: raw data is never committed, inlined or written to
  `data.json`) · derived_charts: allowed-with-attribution (author policy 2026-10-05)

## The cuts (`--cut`, in the order of the monthly routine)

Run the import without `--cut` to list them with their page URLs.

| Cut | Menu | Shape | Grain |
|---|---|---|---|
| `adoption/overall` | Adoption : Overall | long | month |
| `adoption/models` | Adoption : Overall + Models | long | month |
| `adoption/sector` | Adoption : Sector (7 sectors) | long | month |
| `adoption/size` | Adoption : Business size (Large, Medium, Small) | long | month |
| `spend_per_employee/overall` | AI spend per employee : Overall | wide | month |
| `spend_per_employee/sector` | AI spend per employee : Sector (8 sectors) | long | month |
| `spend_per_employee/size` | AI spend per employee : Business size | long | month |
| `spend_share/overall` | AI share of business spend : Overall (overall + 20 sectors) | wide | month |
| `token_volume/maker` | Token volume : By model maker (Volumes) | wide | week |
| `token_spend/maker` | Token spend : By model maker (Volumes) | wide | week |
| `token_price/blended`, `/input`, `/output` | Token prices : Blended / Input / Output | wide | day |

Not imported: Geographies, State, Financing status, Filter mode, the By model views, the Shares toggle
(shares are computed from Volumes) and AI share : Sector (one sector at a time, already in Overall).

## Paste format
Tab-separated UTF-8, one header row, no title, units row or "as of" stamp, LF line endings, no trailing
newline. ISO dates: months on the 1st, token weeks on the **Sunday that ends** a Monday–Sunday week,
prices daily. Missing values are empty cells; numbers may be in scientific notation. Row order differs
by view (adoption and spend per employee newest first) and column order differs between Token volume
and Token spend, so neither is relied on.

## Known quirks and caveats
- **The paste does not name its view.** The cut is declared and checked against the header, but the
  header cannot tell apart the three price views (identical headers) or Token volume from Token spend
  (same columns). Mart 062 checks those with the data: `ramp_price_check` (input ≤ blended ≤ output)
  and `ramp_token_check` (spend ÷ volume implies a price ratio between labs, which a swap inverts).
  Residual risk: a swap in weeks when Anthropic and OpenAI are priced alike, or on days when input
  and output prices coincide, is not detectable.
- **Wrong-click guard:** an import identical to the latest import of any other cut is refused (the
  clipboard did not change).
- **The token index** is 0–100 where 100 is "the peak for any single series in the chart"; stacked
  bars can exceed 100. Each new peak rescales the whole series, so index levels from two imports are
  not comparable; marts use shares within a week. The volume chart's (i) tooltip repeats the spend
  text ("Token spend").
- `Monthly change` is `0` (not empty) in the first month of every series; staged as null.
- Adoption : Overall carries `Census Estimate`, Ramp's monthly restatement of the Census Bureau's BTOS,
  with a wording break in November 2025 (`pre_`/`post_nov_2025_wording_change`) and an empty 2025-10.
  It is kept in its own table and never used as a lens; the BTOS source (PLAN #9) is.
- Vendor adoption shares do not sum to the overall share (businesses pay several labs). `Ramp
  Overall` appears in both adoption views; mart 060 takes it from `adoption/overall` only.
- Sectors are shortened NAICS 2-digit titles (`config/entities/sectors.yaml`); "Technology and media"
  → 51 (Information) is assumed. Sectors appear in a view as Ramp's sample allows. Business sizes have
  no published employee thresholds. What "Top 10%" and "Top 1%" measure exactly is not defined.
- Prices are realised unit values (total dollars ÷ total tokens), so a falling price can be a shift in
  mix, not a price cut. No smoothing note is published.
- No publication schedule is published; August data appeared on 9 September 2026.

## Fetch strategy
Monthly (`cadence: monthly`, `input: manual`): `cachereg fetch` and `fetch --due` list the source as
`manual` with its due date and never fail on it. One import per cut; each is validated in full
before anything is written and stored byte for byte. Vintage: `{kind: content, value: sha256, cut,
first_period, last_period}`. Marts use the latest import of each cut on or before the build cutoff and
report per-cut gaps in `ramp_cut_coverage`.

# Curated asset values (`curated_asset_values`)

**What:** our own hand-curated dataset of dated, cited figures on what assets cost, fetched, were
assumed to last or recovered in a bust: GPUs and AI infrastructure (data-centre buildings, power), and
the fiber of the dot-com build-out (fiber and conduit, the transmission electronics that light it, lit
bandwidth, carriers' whole networks). One row per stated figure, cited to the page it came from with a
short verbatim quote. Design: `docs/plans/2026-10-14-gpu-vs-fiber.md`.
**Files:** `config/curated/asset_values.csv` (the rows) and `config/curated/asset_vocab.yaml` (the
controlled vocabulary: assets with their era and layer; metrics with the units they may be stated in).
**Auth / network:** none; `fetch` validates the committed files and copies them into raw.
**License:** CC BY 4.0 (ours). Credit: "Cache Register curated asset values, from the cited filings
and press, CC BY 4.0, as of {as_of}". The quotes are short factual excerpts (≤ 25 words, PLAN §7)
and are never inlined in HTML.

## Columns
`id` (`<asset>-<metric>-<statement_date>`, then `-2`, `-3` … for further figures from one statement;
never reused), `statement_date` (published, filed or said), `asset` and `metric` (in the vocabulary),
`entity` (free text: the company, index or "market"; dot-com carriers are not AI vendors, so there is
no join to `vendors.yaml`), `value_as_stated` (the figure exactly as in the quote), `value` (that figure,
**in the stated unit**: nothing is converted here), `unit` (one of the metric's units), `qualifier`,
`period_start` / `period_end` (what the figure measures), `scope` (exactly what it covers: GPU model and
form factor, on-demand or reserved, per GPU or per node, route, IRU term), `source_url`, `source_kind`
(`primary`: the company, its filings, court records or official channels; `secondary`: press, research
and indices), `source_quote`, `recorded_on` (drives as-of), `supersedes`, `notes`.

Qualifiers as in `curated_disclosures` (over, about, under, up_to, exact), plus `range_low` and
`range_high`: a stated range ("20 to 25 years") is two rows, one per end.

## Classification
- history: curated · revisions: append-only → **Exact by `recorded_on`**
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution

## Rules (enforced, `dataset.validate`)
The `curated_disclosures` rules (shared in `sources/_curated.py`: exact columns, unique ids, ISO dates,
https URL, quote ≤ 25 words containing `value_as_stated`, `value_as_stated` parsing exactly to `value`,
`$` only on usd units, a trailing `+` only with `over`, supersession), except that the entity is free
text and the unit must be one the metric lists. A figure may end in `%`, and then (only then) its unit
is `percent`. **Append-only** as for `curated_disclosures`: fetch, stage, the pre-push hook and CI
(`python -m cachereg.sources.curated_asset_values.dataset --base <sha>`) refuse an edited or removed row.

## Adding rows
Read the source page; copy the quote; fill a row with `recorded_on` = today; run `cachereg fetch
curated_asset_values` and `make check`. Press, research notes and published indices are welcome
(author, 2026-10-14) and marked `secondary`; dead pages are cited through web.archive.org. Excluded:
forecasts, our own arithmetic (a node price ÷ 8 is done in the analysis, which says so).

## Caveats (carry into analyses)
- Prices are scattered quotes, not a series: different configurations (SXM or PCIe, on-demand or
  reserved, per GPU or per node), venues and regions. Compare only like with like (`scope`).
- Book useful lives are accounting assumptions chosen by the company, not observed lifetimes.
- Dot-com figures survive unevenly (what press chose to report); bankruptcy "sale prices" may cover
  only part of a company or come with assumed liabilities (see `scope` and `notes`).
- Vendor performance multiples (`perf_multiple`) are marketing claims on the vendor's chosen workload.

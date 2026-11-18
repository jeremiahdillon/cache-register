# Databricks AI Index (`databricks_ai_index`)

**Page:** https://developers.databricks.com/ai-index (launch post, 2026-11-16:
https://databricks.com/blog/introducing-databricks-ai-index-state-enterprise-ai-tokenomics)
**Access:** the public page; no key, no API, no download. The weekly series are read from the chart props
embedded in the page's Next.js payload (`parse.py`). `robots.txt` allows all paths. One request per run.
**License:** none stated. The page has no licence, terms or "cite as" text; databricks.com's general Terms of
Use do not address this data. Author policy (2026-11-18): with no published use guidelines, assume no
restriction was placed on it and use it consistently with fair use: derived charts with attribution, no
republication of the series (redistribution `unknown`, so raw stays local and nothing inlines it). Charts
credit "Databricks AI Index (developers.databricks.com/ai-index), as of {as_of}".
**Last verified:** 2026-11-18 (page read; first fetch 2026-11-18).

## What it contains
Aggregated, anonymised traffic of the enterprises that route model calls through **Unity Gateway**
(Databricks' governance and routing layer; "thousands of enterprises", "10,000+ companies" in the launch
post), including calls routed to external providers. Weekly, from the week of 2026-07-20; the page says it
is updated weekly. Charts read (`parse.CHARTS`):

| canvasId | Measure | Within |
|---|---|---|
| `tokenShareChart` | % of token volume (input + output) | proprietary models |
| `walletShareChart` | % of spend ("wallet share") | proprietary models |
| `ossTokenShareChart` | % of token volume | open-weight models |
| `ossWalletShareChart` | % of spend | open-weight models |
| `openWeightShareChart` | proprietary vs open-weight % of token volume | all models |

Each chart has layers `{label, group, values}`: a model (`Opus 5.5`, `GLM 5.3`), a lab bucket (`Older
Anthropic Models`) or an "other" bucket (`Gemini, Grok` in "Other proprietary"; `Other` in "Other
open-weight"), grouped by provider. **Wallet share is Databricks' estimate at providers' published list
prices, not what Databricks bills.** Not read: companies using 2+/3+/4+ providers, user spend percentiles,
the coding benchmark.

## Classification
- history: native (the page carries the whole series) · revisions: unknown → **revised** (Latest-only)
- redistribution: unknown (author policy above) · derived_charts: allowed-with-attribution

## Fetch strategy
Daily (`cadence: daily`; the data is weekly, so most fetches repeat the last vintage). The page is stored as
served (`ai-index.html`) only after `parse.records` reads every chart: a missing chart, a week label that
does not match its date, a non-Monday week start, a share outside 0–100 or a week whose layers do not sum to
100 ± 1 fails the fetch, so a changed layout is noticed, not half-read. Vintage: `{kind: content, value:
sha256 of the parsed records, updated, window}` (the HTML carries deployment ids that change on their own).

## Parsing (`parse.py`)
The `self.__next_f.push([1, "…"])` chunks concatenate to "flight" rows `<id>:<json>`. A chart is the object
with `canvasId` and `layers`; a later chart may give `weeks` as a reference `$<row>:<path>` into an earlier
row (React elements are `["$", type, key, props]`; the path steps through `props` by name). Labels have no
year ("Jul 20"): the chart's "Updated Nov 2, 2026" line dates the last label, and earlier labels must fall
exactly 7 days apart.

## Staged tables
- `layers`: `week_start` (Monday), `chart`, `metric` (`tokens` | `spend`), `segment` (`proprietary` |
  `open_weight` | `split`), `provider_group`, `label`, `share_pct`, `updated`, `fetch_id`, `fetched_at`. All
  vintages are kept; mart 095 picks per week the latest fetch on/before the cutoff.

## Entities
`vendors.yaml` `aliases.databricks` maps provider groups (`Anthropic`, `OpenAI`, `DeepSeek`, `Moonshot`,
`Zhipu` → `zai`); "Other proprietary" and "Other open-weight" stay `_other`. `models.yaml`
`aliases.databricks` maps the 18 named models seen on 2026-11-18 (`Opus 5.5` → `anthropic/claude-opus-5.5`,
`DS V4.1 Flash` → `deepseek/deepseek-v4.1-flash`, `GLM 5.3 Flash` → `z-ai/glm-5.3-flash`, …); the buckets are
never mapped. A new model on the page lands in its lab's share at once (by provider group) but is left out of
mart 096's price estimate until it is mapped.

## Marts
- **095** (`dbx_layer_week`, `dbx_segment_mix_week`, `dbx_vendor_share_week`): shares within each segment
  and, for tokens, of all tokens (share within the segment × the segment's token share).
- **096** (with `litellm_prices`; `dbx_model_price_week`, `dbx_segment_price_week`, `dbx_spend_mix_week`,
  `dbx_vendor_spend_week`): the page has no spend mix between segments, so it is estimated from list
  prices: within a segment, wallet_i / tokens_i = p_i / P, so P = Σ tokens_i p_i / Σ wallet_i over the named,
  priced models (LiteLLM, 0.8 × input + 0.2 × output); open-weight spend share S = T_open P_open / (T_open
  P_open + T_prop P_prop); a proprietary lab's share of all spend = its wallet share × (1 − S). Sensitivity:
  P_open × 2 and × ½.

## Known quirks and caveats
- **Unity Gateway customers only**: enterprises on Databricks that route through its gateway; first-party
  API use outside it is invisible. A different population from Ramp's, Vercel's and OpenRouter's.
- **Shares only** to 0.1 point (a lab's share sums its layers' rounding, ≤ ~0.05 × layers).
- **The page's headline shares are of proprietary models only** (Anthropic 61.5% of proprietary tokens in the
  week of 2026-11-02, about 42% of all tokens); only the token mix between segments is published.
- History from the week of 2026-07-20 only (16 weeks on 2026-11-18). Revision behaviour unknown.
- **Fragile by construction**: a redesign of the page breaks the fetch (by design, loudly).

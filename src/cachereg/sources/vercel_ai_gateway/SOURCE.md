# Vercel AI Gateway leaderboards (`vercel_ai_gateway`)

**Endpoint:** `GET https://vercel.com/api/ai/leaderboard-export` (`dataset` = `models` | `labs` |
`apps` | `providers`, `modality` = `all` | `text` | `image` | `video`, `format` = `json` | `csv`,
`from` / `to` = `YYYY-MM-DD`; earliest `2025-10-01`, default a rolling two months)
**Docs:** https://vercel.com/docs/ai-gateway/leaderboards · data page: vercel.com/ai-gateway/leaderboards
**Auth:** none. No documented rate limit; responses are "cached for 24 hours". A `from` before the
earliest day is refused with HTTP 400.
**License:** CC BY 4.0. Required notice (docs page, read 2026-10-08), verbatim:
`© 2026 Vercel. "AI Gateway Leaderboard Data" is licensed under CC BY 4.0.` with a link to the
licence. The footer string carries it; the year follows Vercel's notice when it changes.
**Last verified:** 2026-10-08 (docs plus read-only requests; design in
`docs/plans/2026-10-08-vercel-ai-gateway.md`); first real fetch 2026-10-09.

## What it contains
Each body: `{dataset, modality, from, to, earliest_available_date, license: "CC-BY-4.0", license_url,
rows: [{date, group, name, metric, modality, share_percent}]}`. Daily rows, metrics `requests`,
`tokens` and `spend`, each a **percentage share** of that day's gateway traffic: "anonymized … never
absolute volumes".

- **Labs** (`group: lab`) are complete: shares sum to 100 per day × metric (12–33 labs a day).
  Slugs are Vercel's own: `spacexai` holds xAI's models, `stealth` unnamed models; inference
  providers that ship their own models (`fireworks`, `inference-net`, `morph`) and small labs
  (`sakana`, `interfaze`, `meituan`, …) appear too.
- **Models** (`group: model`) are the top few of the **requested window** plus `Other` (published
  from June 2026 only; before that the named models do not sum to 100). The same day gets a
  different list in a different window (2026-09-01: a September request lists `Step 3.7 Flash`, the
  full-year request folds it into `Other`). So models are fetched one calendar month per request.
- **Spend** is Vercel's measure of what customers paid through the gateway. Vercel does not say
  whether bring-your-own-key traffic, discounts or caching are included.

## Classification
- history: native · revisions: revised (Latest-only until two months of vintages show past days
  unchanged; then consider `append-only`)
- redistribution: allowed-with-attribution · derived_charts: allowed-with-attribution

## Fetch strategy
`modality=text`, `format=json`, days through yesterday (UTC). First run (or `--full`): labs from
2025-10-01 in one request (~2.5 MB), models one request per calendar month. Daily runs: labs for the
trailing 35 days, models for the previous and current month. Before anything is stored every body
must carry `license: CC-BY-4.0` (a licence change stops the fetch), echo the requested dataset,
modality and window, have dates in the window, known metric and group, finite shares in 0–100, and
(labs) shares summing to 100 ± 0.05 per day × metric. Bodies are stored as served. Vintage:
`{kind: content, value: sha256 of the bodies, window, earliest_available_date}`.

## Staged tables
- `shares`: `date`, `dataset`, `name`, `metric`, `modality`, `share_pct`, `is_other`,
  `window_start` (models: the requested month), `unlisted_pct` (models: 100 − Σ named models, i.e.
  `Other` when published, else the residual), `fetch_id`, `fetched_at`. All vintages are kept; mart
  090 picks per day the latest fetch on/before the cutoff.
- `labels`: each published name with first/last day and peak shares (all vintages).

## Entities
`vendors.yaml` `aliases.vercel` maps 24 lab slugs (`spacexai` → `xai`, `inclusionai` → `ant`,
`moonshotai` → `moonshot`, `arcee-ai` → `arcee`, `stealth` → `_stealth`). Every lab with ≥ 1% of tokens
or spend on any day maps to an existing vendor, so no vendor was added; the rest (peak < 0.4%) are
reported in `vercel_label_coverage`. `models.yaml` `aliases.vercel` maps display names by hand (63 of
the 69 named models seen to 2026-10-08, besides `Other`). `Gemini 3 Flash` → `google/gemini-3-flash-preview` (the only Gemini 3
Flash in our entities; Epoch's group of the same name maps there too); both `Grok 4.1 Fast` variants
(reasoning on/off) → `x-ai/grok-4.1-fast`. Left unmapped as ambiguous or absent from our entities: the image models `Nano Banana` and
`Nano Banana Pro`, `MiMo M2.5`, `Nova Lite`, `Ministral 3B` and `GPT 5.1 Thinking`.

## Known quirks and caveats
- Vercel AI Gateway traffic only: developers building on Vercel. Not the market, and a different
  population from OpenRouter's and from Ramp's businesses.
- Shares, never volumes: days cannot be weighted, so a week's or month's share is the unweighted
  mean of daily shares; Vercel's traffic cannot be sized.
- Model-level claims are not supported (top-few lists that depend on the window).
- Tokens are counted by each provider's tokenizer.
- History from 2025-10-01 only. The `apps` and `providers` datasets (all-time ranked lists, no day
  dimension) and the image/video modalities are not fetched.

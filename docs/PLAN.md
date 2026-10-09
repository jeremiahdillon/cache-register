# Cache Register — Project Plan

Status: DRAFT v5 · 2026-10-02

## 1. Purpose

A public, reproducible toolkit for analyzing the AI market from **public/published data**:
token usage and pricing, model benchmarks, business adoption, task-level usage, and the capital
spending behind it. The goal is to rapidly find insightful trends — especially *cross-dataset*
intersections — and turn each into compelling content (interactive blog embeds on
jeremiahdillon.com, autoplay video for X/LinkedIn, static images) that carries a link back to the
exact code that produced it.

**Non-goals:** writing post copy, captions or social text of any kind — the project does
analysis and synthesis and produces the visuals; the author writes the words. **Non-goals (v1):**
the author's private usage/spend data; web scraping; paid data products
(SemiAnalysis, Similarweb, Sensor Tower); real-time dashboards.

**Guiding principles**

1. Public repo, private data: code, config, entity mappings, and curated disclosures are
   committed; downloaded source data is not (unless its license explicitly allows).
2. Anyone with their own API keys can reproduce every dataset, analysis, and visual.
3. Prefer sources with **native time series** (history downloadable today) over sources that
   only expose current state and must be snapshotted.
4. One canonical analysis → many renderings.
5. Extend by adding folders, not by editing core.

---

## 2. Data sources

Every source gets classified on the fields below, recorded in its `SOURCE.md` and the source registry:

- `history`: `native` (full series downloadable) | `snapshot` (current state only; we build
  history by fetching on a schedule) | `curated` (hand-entered from published documents)
- `redistribution` (raw/bulk data, incl. data inlined in interactive HTML): `allowed` |
  `allowed-with-attribution` | `forbidden` | `unknown` (unknown is treated as forbidden)
- `derived_charts` (publishing images/videos derived from the data): `allowed` |
  `allowed-with-attribution` | `forbidden` | `unknown`. **Author policy (2026-10-05):** derived
  works may be published from every source, credited; only an explicit `forbidden` blocks them.
  Raw data is still gated by `redistribution`.
- `attribution`: exact required credit string (and link), used verbatim by the footer stamp
- `revisions`: `none` | `append-only` | `revised` (values for past periods can change later),
  which drives the reproducibility class in §4.4

### 2.1 Tier 1 (v1)

| # | Source | Content | Access | history | Redistribution (to verify) |
|---|---|---|---|---|---|
| 1 | **LiteLLM `model_prices_and_context_window.json`** | Per-model input/output/cache prices, context windows, ~2023→today | Public GitHub file; replay its **git history** for a native price time series | native | allowed (MIT) |
| 2 | **OpenRouter models API** (`/api/v1/models`) | Catalog, pricing (prompt/completion), context, modality, created date | Public; key optional | snapshot | **forbidden** (verified 2026-10-04: no licence for `/models`; derived charts only) |
| 3 | **OpenRouter datasets API** (verified 2026-10-02) — `GET /api/v1/datasets/rankings-daily` (top-50 models by tokens per day/week/month + one `other` row; `total_tokens` only, no input/output split, no $), `GET /api/v1/datasets/app-rankings` (top public apps by tokens per date window, ranks ≤ 200, incl. `trending`), `GET /api/v1/datasets/session-cost` (median **USD per session** by harness × model × turn range; **verified 2026-10-07: no date parameters, only the current weekly 30-day snapshot**, 4 harnesses) | Market token share by model/vendor/app; real per-session spend for coding harnesses | Any OpenRouter API key; 30 req/min per key, 500 req/day per account; history from **2025-01-01** (rankings, app-rankings) | native (session-cost: **snapshot**) | **CC BY 4.0** — reuse and republish with attribution to OpenRouter |
| 4 | **Artificial Analysis API** | Intelligence index, per-eval scores, price, output speed, latency | Free API key; attribution required | snapshot (verify whether historical endpoints exist) | attribution required; raw redistribution likely forbidden |
| 5 | **LMArena leaderboard** | Arena scores over time | Public (HF datasets / published leaderboard files) — VERIFY historical availability | native? | verify |
| 6 | **Epoch AI datasets** | Notable models, training compute, params, release dates, benchmark hub, GPU clusters | CSV downloads | native | CC-BY |
| 7 | **Hugging Face Hub API** | Downloads/likes for open-weight models | Public API | snapshot (only rolling 30-day downloads) | verify |
| 8 | **Ramp AI Index API** (verified 2026-10-02) — base `https://api.ramp.com/v1/public/ai-index`: `GET /adoption` (overall `ai_adoption_share` + vendor breakdown), `GET /adoption/sectors`, `GET /adoption/sizes`; `months` param 1–120 | Monthly % of US businesses paying for AI, by vendor, NAICS sector, company size (50k+ firms) | `Authorization: Bearer $RAMP_DATA_API_KEY`; **provisioned key via the Ramp Data Partner Program** (free, but requires application — replicators must apply). Distinct from the Ramp customer Developer API. **Tested 2026-10-02:** REST without a key → 401 `RampDataApiKeyRequired`; the Ramp Data MCP (`mcp.ramp.com/ramp-data/mcp`) accepts unauthenticated sessions but its tools proxy to the same REST API → 401; the unauthenticated *Developer MCP* serves docs only, no data. **Built 2026-10-07 as a manual import** (source `ramp_ai_index`, `docs/plans/2026-10-07-ramp-ai-index.md`): the page's "Get the data" copies a view's full history as TSV; `cachereg fetch ramp_ai_index --from-clipboard \| --from-file PATH --cut <cut>`, 13 views (adoption overall/labs/sector/size, spend per employee, AI share of spend, token volume/spend by lab, token prices) — anyone can replicate without a key. The API key route stays unbuilt | native (revised monthly → Latest-only) | **unknown** (verified 2026-10-07: no licence, cite-as or terms text; Ramp "does not license this data") → raw never committed or inlined; derived charts with attribution "Ramp AI Index (ramp.com/data/ai-index)" |
| 8b | **Ramp Rate API** — base `https://api.ramp.com/v1/public/ramp-rate`: categories, category vendor leaderboards, vendor profiles, vendor compare | Software vendor adoption, growth, new-adopter and **switch rates** within categories (trailing 12 months), incl. AI vendors | Same Ramp Data key | snapshot (trailing-12-month window) | as #8 |
| 9 | **US Census BTOS** (Business Trends & Outlook Survey) (verified 2026-10-07) | Share of U.S. employer businesses using AI in the last two weeks and expecting to in six months, biweekly from Sep 2023, national / sector / size class / sector × size (also state, MSA), with standard errors; **new series from 17 Nov 2025** (wording change, same question IDs) | Public Excel downloads (`census.gov/hfp/btos/downloads/`), no key; api.census.gov has no BTOS. **Built 2026-10-08** (source `census_btos`, `docs/plans/2026-10-07-census-btos.md`): 5 workbooks, stdlib Excel reader | native (files replaced in place → Latest-only until vintages show no revisions) | allowed (public domain, 17 U.S.C. §105); credit "U.S. Census Bureau, Business Trends and Outlook Survey" |
| 10 | **Anthropic Economic Index** | Claude usage by task/occupation (O*NET), automation vs augmentation, over releases | HF dataset | native (release-over-release) | CC-BY |
| 12 | **Vercel AI Gateway leaderboards** (verified 2026-10-08) — `GET vercel.com/api/ai/leaderboard-export` (`dataset=labs\|models`, `modality`, `from`/`to`) | Daily **share** by lab and model of requests, tokens and **spend** on Vercel's AI Gateway (shares only, never volumes; labs complete, models top-few + `Other`) | Public, no key; history from **2025-10-01**. **Built 2026-10-09** (source `vercel_ai_gateway`, `docs/plans/2026-10-08-vercel-ai-gateway.md`): labs (one request) and models (one request per calendar month, since the listed models depend on the window), text modality; marts `090_vercel_shares` and `091_gateway_lenses`. A second developer-gateway lens beside OpenRouter, with Vercel's *measured* spend share | native (Latest-only until revisions are ruled out) | **CC BY 4.0** — required notice: © 2026 Vercel. "AI Gateway Leaderboard Data" is licensed under CC BY 4.0 |
| 11 | **SEC EDGAR XBRL `companyfacts` / `frames` APIs** | Structured quarterly financials: capex (`PaymentsToAcquirePropertyPlantAndEquipment`), revenue, etc. for MSFT, GOOGL, AMZN, META, ORCL, NVDA, … | Public JSON; requires a descriptive `User-Agent` with contact email (kept in local env, never committed) | native | public domain |

**EDGAR scope limit (per author):** only standardized XBRL tags from `companyfacts`. Segment-level
numbers (e.g. Nvidia *Data Center* revenue, Azure growth) live in dimensional/segment facts or
filing text and are **out of scope for v1**; if wanted later they go in the curated disclosures
dataset (§2.3).

### 2.2 Answer: other sources of token usage / spend

There is no single public, authoritative "tokens consumed by the market" dataset. Options,
ranked by value-to-effort:

| Source | What | Verdict |
|---|---|---|
| **Curated disclosures dataset** (ours, §2.3) | Hyperscaler/lab statements: Google monthly tokens processed (I/O and earnings calls), OpenAI/Anthropic revenue run-rates, Microsoft AI run-rate, weekly and monthly active users, API tokens/minute (Microsoft's token totals change unit and scope every time: no series) | **Tier 1, built 2026-10-09** (50 seed rows). Highest-signal public numbers on market-wide token volume and spend; small, hand-maintained, each row cited. This becomes *our* licensable dataset |
| OpenRouter `rankings-daily` / `app-rankings` (#3) | Token volume & share by model, vendor, app — daily since 2025-01-01 | **Tier 1, verified, CC BY 4.0** |
| Vercel AI Gateway leaderboards (#12) | Daily share of requests, tokens and *measured* spend by lab and model on Vercel's gateway | **Tier 1, built 2026-10-09, CC BY 4.0**: the second developer-gateway lens (shares only, never volumes) |
| OpenRouter `session-cost` (#3) | Actual median USD per session by harness × model — the only *published dollar* usage figure found | **Tier 1, verified** |
| Ramp AI Index + Ramp Rate (#8, #8b) | Spend *adoption* (share of businesses paying) by vendor/sector/size; vendor switch rates | **Tier 1, verified** (key via partner program) |
| Stock prices ("ticker trends") | Daily OHLC for AI-exposed tickers (NVDA, MSFT, GOOGL, AMD, AVGO, TSM, CRWV, …) | **Tier 2.** Licensing is the issue: Yahoo/yfinance ToS forbids this use; options are Alpha Vantage / Tiingo (free keys, non-redistributable) or Stooq CSVs. Use for overlays (e.g. "price-per-intelligence vs NVDA") |
| Census construction spending (data center category) / FRED | US data-center construction $ monthly | Tier 2; public domain, native series |
| Kalshi / Polymarket AI markets | Market-implied odds (e.g. "top model on LMArena at month end") | Tier 2; public APIs |
| Stanford AI Index | Annual compiled data | Tier 2; annual, good for context |
| Vast.ai marketplace API | GPU rental prices | Tier 3; snapshot only |
| SemiAnalysis | Token/compute/GPU models | **Excluded**: paid subscription, redistribution forbidden |
| Menlo / a16z / OpenRouter reports | Enterprise spend share, usage studies | Use as curated disclosures (cite specific figures), not as feeds |

Spend derivation (`rankings-daily` publishes tokens, not dollars): `est_spend = Σ tokens × blended_price`,
`blended_price = 0.8 × prompt_price + 0.2 × completion_price`, using price at that date (LiteLLM
history / OpenRouter models snapshot). **Join keys:** `rankings-daily.model_permaslug` ↔
`/api/v1/models.canonical_slug`; LiteLLM keys
(provider-prefixed, e.g. `bedrock/…`) reach the same rows only through the entity resolver
(§4.3), which maps both to a canonical `model_id` + `variant`. Unmatched permaslugs are
reported with their token share, never silently dropped.
Known biases: caching ignored (overstates spend, most for heavily-cached coding traffic); list
prices only (no negotiated discounts, no per-provider/host price variance); top-50 truncation
(tail in `other`); `:free` variants have zero price and are reported separately, not blended;
**price-date staleness** — pricing history from a single current `/models` pull misprices past
weeks, so historical weeks use LiteLLM price history or our own daily `/models` snapshots, and
weeks priced with a later price are flagged. Must be presented as an
**estimate with bounds**: input/output split may be unknown (use published split or a bounded
range), cache discounts and per-provider price variance ignored or bounded. Each derived metric
documents its assumptions in its mart.

### 2.3 "Our" datasets (author-owned, shareable)

1. **Curated disclosures** — `config/curated/disclosures.csv`, committed, **CC-BY 4.0**; source
   `curated_disclosures`, mart `080_disclosures` (built 2026-10-09,
   `docs/plans/2026-10-08-curated-disclosures.md`). One row per stated figure. Columns: `id,
   statement_date, entity, metric, value_as_stated, value, unit, qualifier, period_start, period_end,
   scope, source_url, source_kind, source_quote, recorded_on, supersedes, notes`; metrics and units
   from the controlled vocabulary `config/curated/metrics.yaml`. Validated on every fetch and in tests
   (the quote must contain `value_as_stated`, which must parse exactly to `value`). **Append-only**:
   corrections are new rows with `supersedes`, enforced by fetch, stage, the pre-push hook and CI; as-of
   by `recorded_on` (Exact).
2. **Raw archive** — accumulated raw pulls of `snapshot` sources **and of native sources that
   are revised in place** (Latest-only class). Can be published
   (e.g. separate HF dataset / Zenodo / GitHub release) **only for sources whose
   `redistribution` permits it**. Publication tooling (`cachereg export-archive`, backlog) filters by that
   flag automatically and attaches per-source attribution/license files. Default: not published,
   **except OpenRouter datasets (CC BY 4.0)**: their raw vintages (above all session-cost, which has
   no other route to history) are the first archive to be
   published (GitHub Release asset or HF dataset, with OpenRouter attribution), which upgrades
   OpenRouter-based figures to *Exact* for replicators who download it. `export-archive` is
   therefore the first backlog item scheduled after Phase 6.
3. **Derived aggregates** — mart outputs that are sufficiently transformed (e.g. monthly
   price-per-intelligence index) may be publishable where licenses allow; same flag-driven export.

---

## 3. Repository layout

```
cache-register/
├── README.md                     # what, how to reproduce, license matrix
├── LICENSE                       # code: Apache-2.0
├── LICENSE-content               # charts/text/curated data: CC-BY 4.0
├── SECURITY.md
├── pyproject.toml / uv.lock      # Python 3.12+, pinned
├── Makefile                      # thin wrappers over the CLI
├── .env.example                  # every variable, documented, no values
├── .gitignore                    # data/, outputs/, .env*, *.duckdb, logs
├── .pre-commit-config.yaml
├── CLAUDE.md                     # rules for AI collaborators (layers, conventions, security)
├── .claude/skills/               # v1: new-analysis, render-check (add-source, promote: backlog)
├── .github/workflows/ci.yml      # lint/type/test/render-on-synthetic; no secrets
├── config/
│   ├── sources.yaml              # registry: id, history, redistribution, derived_charts,
│   │                             #   attribution, revisions, cadence, enabled
│   ├── entities/
│   │   ├── models.yaml           # canonical model IDs ↔ per-source aliases
│   │   ├── vendors.yaml          # canonical vendors, open/closed weights, HQ country
│   │   └── tickers.yaml          # vendor ↔ ticker/CIK (for EDGAR & prices)
│   ├── curated/                  # §2.3, committed: disclosures.csv + metrics.yaml (vocabulary)
│   └── brand/                    # brand.yaml, fonts (OFL), logo SVG
├── src/cachereg/
│   ├── core/                     # http, snapshot store, settings/secrets, lineage, logging
│   ├── sources/<id>/             # one package per source (contract §4)
│   ├── entities/                 # resolver + `entities check`
│   ├── marts/                    # *.sql + mart registry (inputs, assumptions)
│   ├── story/                    # Story model, render targets, renderers (§6)
│   ├── viz/                      # theme, chart helpers, stamp, motion
│   └── cli.py                    # `cachereg …`
├── explore/                      # dated explorations, no short links: 2026-10-02-<slug>/
├── receipts/                     # promoted topics; folder name = short link; committed output/
├── docs/
│   ├── PLAN.md
│   ├── playbook.md               # lessons learned: chart patterns, what performed, pitfalls
│   └── sources/                  # (generated) source catalog
├── ops/launchd/cachereg.fetch.plist.template   # placeholders only; installed by script
├── tests/
│   └── fixtures/                 # SYNTHETIC data only (no recorded real responses)
├── data/                         # gitignored
│   ├── raw/<source>/<YYYY-MM-DD>/<fetch_id>/…   # immutable, as fetched + manifest.json
│   ├── staged/<source>/<table>/snapshot_date=…/part.parquet
│   └── warehouse.duckdb          # views over staged + marts (rebuildable)
└── outputs/                      # gitignored render outputs
```

**Brand:** Cache Register. **Package / CLI:** `cachereg`. **Repo:**
`github.com/jeremiahdillon/cache-register` (public). **Domain:** `cacheregister.dev`.
The stamp URL is derived from config (`config/brand/brand.yaml`).

---

## 4. Data pipeline & core rules

### 4.1 Layers (one-way flow)

`raw → staged → marts → analyses`

- **raw**: exactly what the source returned, written once, never modified. Each fetch writes
  `manifest.json` (source id, URL template — no secrets, timestamp, HTTP status, content hash,
  adapter version).
- **staged**: tidy, typed Parquet with a declared schema (pandera/polars validation), adds
  `snapshot_date` / `observed_at`, source-native IDs preserved.
- **marts**: cross-source SQL views/tables in DuckDB using canonical entity IDs. Each mart
  declares its inputs and documented assumptions. Analyses read **marts only** (enforced by a
  lint rule / import check: analyses may not import `cachereg.sources`).
- `cachereg build` is idempotent and fully rebuilds staged + marts from raw.

### 4.2 Source contract

Each `src/cachereg/sources/<id>/` contains:

- `SOURCE.md` — description, URLs, ToS link, license, attribution string, history type,
  `derived_charts`, `revisions` (reproducibility class),
  redistribution flag, known quirks, last verified date.
- `fetch.py` — `fetch(ctx) -> FetchResult`; writes to raw; handles pagination, rate limits,
  retries; respects `ctx.as_of` for native-history backfills.
- `stage.py` — `stage(raw_paths) -> dict[table, DataFrame]` + schema definitions.
- `tests/` — schema/contract tests on synthetic fixtures.

Registered in `config/sources.yaml`. Adding a source touches only its folder + one registry
entry (+ entity aliases). Core is never edited for a new source. **One generic extension (2026-10-07):**
sources with `input: manual` in the registry are imported by the author with `cachereg fetch <id>
--from-clipboard | --from-file PATH --cut NAME`; the adapter's `fetch` then receives a `ManualInput`
(`core/manual.py`). The manifest records how the input arrived, never a local path. In v1 a new source is scaffolded by copying an existing source folder; `cachereg add-source <id>` is backlog.

### 4.3 Entity resolution (cross-source joins)

- `models.yaml`: canonical `model_id` (e.g. `anthropic/claude-sonnet-4.5`), vendor, family,
  release date, open_weights, plus `aliases: {openrouter: [...], artificial_analysis: [...],
  lmarena: [...], litellm: [...], epoch: [...], hf: [...]}`. `epoch` lists Epoch **model groups**
  (the ECI `Model` name; versions reach their group through Epoch's own metadata), one group per
  canonical model.
- Resolver: exact alias match → normalized-string match (lowercasing, punctuation, provider
  prefixes; date/version suffixes are **preserved**, never normalized away) → **unresolved queue**. No fuzzy auto-accept; fuzzy candidates
  are *suggested* by `cachereg entities check` for human/Claude confirmation.
- Variants (thinking/non-thinking, dated snapshots, quantizations, provider-hosted versions)
  map to a canonical model with a `variant` field so analyses choose granularity.
- **Bootstrap, not hand-typing**: `cachereg entities suggest` generates candidate aliases from
  every source's distinct model keys (LiteLLM's thousands of provider-prefixed keys collapse via
  rules: strip provider prefixes such as `bedrock/`, `azure/`, `vertex_ai/` and region
  qualifiers). Only provider-prefix/region collapses are applied automatically. **Date or version
  suffixes are never stripped automatically**: dated snapshots (e.g. `…-20240620` vs
  `…-20241022`) are distinct priced/benchmarked models, so they are kept as separate `variant`
  entries under a canonical `model_id` (proposed by `suggest`, confirmed by a human/Claude) or
  queued as unresolved. Unmapped keys are written to `data/entities/unresolved_<source>.csv` for triage.
- Not every key needs mapping: only models that appear in a mart an analysis uses. Long-tail
  keys stay source-native and are excluded from cross-source joins (and reported).
- **Coverage metric (defined)**: for each cross-source mart, the share of the *measure* that
  resolves — e.g. share of OpenRouter tokens, or share of the top-50 Artificial Analysis models
  by intelligence index, or share of LiteLLM keys for the top-15 vendors. Target: ≥95% per
  mart measure; marts warn below threshold and record coverage in the manifest.

### 4.4 Time & reproducibility

- Every render takes `--as-of DATE` (default: latest). Marts are computed from data observed
  ≤ as-of.
- Every fetch records a **vintage**: `fetched_at` plus the most specific source revision
  available (git commit SHA for LiteLLM, dataset version/commit for HF datasets, release id for
  BTOS/Epoch/Economic Index, `filed`/accession number per EDGAR fact, response content hash
  otherwise). Staged rows carry `vintage_id`. `--as-of` selects data by **source time, not fetch time**:
  - **Exact** (`revisions: none | append-only`, native history): the latest *source revision*
    dated on or before as-of (LiteLLM commit date, EDGAR `filed` date, dataset/release
    publication date) — so a replicator fetching today still resolves any past as-of;
  - **Latest-only** (`revisions: revised`): the latest local vintage *fetched* on or before
    as-of; if none exists (e.g. a replicator's only fetch is today), the earliest available
    vintage is used and the manifest records `vintage_after_as_of: true`. Observations are
    still filtered to periods ≤ as-of;
  - **Author-only** (snapshot): the latest snapshot *fetched* on or before as-of; none →
    the analysis reports the gap rather than substituting later data.
- **Reproducibility classes** (declared per source, shown in each analysis README and in the
  public manifest) — the guarantee is stated honestly, not uniformly:

  | Class (selection key) | Sources (expected) | Author can regenerate a past figure | A replicator can |
  |---|---|---|---|
  | **Exact** (source revision date) | LiteLLM (pinned commit SHAs), EDGAR (facts carry filing accession; restatements are new facts), curated disclosures (append-only rows selected by `recorded_on`, corrections by `supersedes`), versioned HF datasets (Economic Index, possibly LMArena) | yes | yes, same values |
  | **Latest-only** (fetch date, fallback to earliest vintage) | BTOS (until `btos_revision_check` shows no revisions; then Exact by each cycle's publication date), Epoch, Ramp AI Index, OpenRouter rankings-daily and app-rankings, Vercel AI Gateway leaderboards, until their revision behavior is confirmed (revised/replaced in place) | yes, from local raw vintages | gets current values; differences explained by the vintage recorded in the public manifest — **unless the published archive (§2.3) is used, which makes them Exact (OpenRouter datasets first)** |
  | **Author-only** (fetch date, no fallback) | Snapshot sources (OpenRouter models, OpenRouter session-cost, Artificial Analysis, HF downloads, Ramp Rate) | yes, from local raw archive | only from their own first snapshot onward, unless the archive is publishable (§2.3) |

- "Anyone can reproduce" therefore means: identical code, identical method, identical results
  for *Exact* sources; same method on current or self-collected data otherwise. Analyses should
  prefer *Exact* sources for headline claims.
- Each render writes `run_manifest.json`: git SHA, dirty flag, as-of, per-source snapshot
  dates + vintage ids + content hashes, package lock hash, reproducibility class per source.
  It contains **no** absolute paths, hostnames, usernames, or timestamps finer than the date
  (all paths repo-relative; a schema test enforces this).
- Receipts commit their visuals **and** manifest in `receipts/<topic>/output/` (see §5), so the
  manifest a posted image refers to is always in the repo; explorations render to gitignored
  `outputs/`.
- Snapshot sources: missing days are explicit gaps (never forward-filled silently in marts).

### 4.5 Scheduling

- A `launchd` agent runs `cachereg fetch --due` daily. Each source declares a cadence
  (daily/weekly/monthly) in `sources.yaml`; `--due` fetches a source when that cadence has passed
  since its latest fetch in the raw store, judged by the fetch folder's UTC date (`daily`: the date
  changed; `weekly`: 7 days; `monthly`: one calendar month, clamped to month end). Never-fetched
  sources are due; a failed fetch writes nothing and is retried next run. Sources not yet due print
  `wait … next due <date>`. Under `--due` a missing secret is reported (`skip`) but is not an error, so
  the exit code means a real failure; plain `fetch` still exits 1 on it. Logic: `core/schedule.py`.
  Manual sources (`input: manual`, §4.2) are never fetched by a run: `fetch` and `fetch --due` print
  `manual <id> due <date>` with the import command, and never fail on them.
- The plist is a **template** (`ops/launchd/cachereg.fetch.plist.template`, label
  `dev.cacheregister.fetch`, placeholders only). `make install-schedule` renders it into
  `~/Library/LaunchAgents/` (time via `SCHEDULE_HOUR`/`SCHEDULE_MINUTE`), lints it, shows which
  secrets the agent's bare environment can see, and prints the `launchctl` commands to load, run and
  unload it; it never loads the agent. The agent runs the project's `.venv/bin/cachereg` (so run
  `make setup` after dependency changes). The rendered plist is never committed.
- Logs go to `~/Library/Logs/cachereg/fetch.log` (outside the repo; not rotated).
- `cachereg status` lists each enabled source's cadence, last fetch date (raw store), next due date and
  last error, then which secrets are set. A failed fetch writes nothing to `data/raw`, so `fetch` records
  each source's outcome in `data/state/fetch.json` (gitignored, outside the raw store; messages redacted
  and cut to one line; a success clears the error; `build` never reads it). Logic: `core/fetch_state.py`.
- Still to do: coverage and disk usage in `status`.

---

## 5. Explorations and receipts

*Decided 2026-10-03; full design in `docs/plans/2026-10-03-explore-and-receipts.md`.*

- `explore/YYYY-MM-DD-<slug>/` — explorations: dated by start, cheap, free-form, may be
  abandoned. No short link; renders go to gitignored `outputs/`; CI only checks they compile.
- `receipts/<topic>/` — topics promoted as post-worthy. **The folder name is the short link**
  (`cacheregister.dev/<topic>`); one link per topic, carried on every visual's footer. A receipt
  has one analysis and one or more visuals, and commits its rendered visuals + manifest in
  `output/` (licence-gated: see §7). The repo knows nothing about where visuals get posted.

Receipt folder:

```
README.md        # question, finding(s), method, caveats, how to reproduce (no post copy — see §1)
receipt.yaml     # title, sources, as_of (pinned), promoted_from, config, visuals
analysis.py      # build(con, as_of, config) -> Story   (the single canonical analysis)
charts.py        # chart functions named by receipt.yaml visuals (contract in render.py)
output/          # committed: <visual>.<target>.<ext>, manifest.json (+ data.json if licences allow)
```

**Promotion** (manual; `promote` command is backlog): copy the exploration's `analysis.py`,
`charts.py` and README into `receipts/<topic>/`, write `receipt.yaml`, clean up, and add a
"Promoted to receipts/<topic>" line to the exploration's README (the exploration stays).

**Standalone reproduction:** `cachereg reproduce receipts/<topic> [--latest]` fetches only the
receipt's sources, checks vintages, builds only the marts whose inputs those sources cover,
renders into a temp folder and compares a canonical data hash with the committed manifest
(identical / differs with reason / cannot reproduce exactly).

**Short links:** `cachereg site` builds a static redirect site from `receipts/*/` that a Pages
workflow publishes; renamed/retired topics stay alive via `config/link-aliases.yaml`. The root
(and 404) is a branded splash page from `assets/templates/site.html`, open to search and AI crawlers
(`robots.txt` allows all, `sitemap.xml` lists the root).

**Learning across analyses**: `docs/playbook.md` captures reusable lessons (chart forms that
worked, engagement notes, data pitfalls). Reusable code graduates into `cachereg.viz` / `cachereg.marts`
(rule: second use → extract). Analyses never import each other.

---

## 6. One canonical analysis → many renderings

### 6.1 Story model

`analysis.py` returns a `Story`:

- `frames`: tidy polars DataFrames (the *only* data any rendering uses; aggregated, minimal)
- `title`, `subtitle`, `takeaway` (one-sentence headline claim), `annotations` (callouts tied to
  data points)
- `time_field` (optional; enables motion), `highlight` (entities to emphasize)
- `by_visual` (optional): per-visual `title`, `subtitle` and `notes`, keyed by the visual's name, when
  one analysis's visuals make different claims; frames stay shared
- `sources`: **auto-derived** from mart lineage → attribution strings from each `SOURCE.md`
- `as_of`, `analysis_url` (computed from repo URL + path)

### 6.2 Render targets (declared in `story.yaml`)

| Target | Format | Size | Notes |
|---|---|---|---|
| `blog_html` | Single-file HTML (Vega-Embed + data inlined; brand fonts from Google Fonts, system fallback) | responsive | tooltips, hover, legend toggles; data inlined = aggregated frames only |
| `blog_svg` | SVG | responsive | static fallback / RSS — **backlog** (needs vector chrome + footer) |
| `x_video` | MP4 H.264 yuv420p, 30fps | 1920×1080 (16:9) | autoplay-muted safe: all text in-frame; ends with 3s hold on final frame |
| `linkedin_video` | MP4 | 1080×1350 (4:5) | same |
| `square_video` | MP4 | 1080×1080 | backlog |
| `web_video` | WebM VP9 | any | for blog autoplay `<video>` |
| `gif` | GIF (palettegen) | ≤ 1080 wide | backlog |
| `x_png` / `linkedin_png` / `square_png` | PNG (WebP, square: backlog) | 1600×900 / 1080×1350 / 1080×1080 | 2× pixel density |
| `table_png` | PNG via great_tables | per preset | for ranking tables |

`cachereg render <analysis> [--targets …] [--as-of …]` → `outputs/<analysis>/<as_of>/<target>.*`
plus `run_manifest.json`.

### 6.3 Rendering engines

- **Altair (Vega-Lite) is the single chart engine** for static (vl-convert → PNG/SVG; WebP via
  Pillow is backlog), interactive HTML, **and** motion.
- **Motion = frame sequences of the same Altair chart function, fed precomputed frame data.**
  Vega-Lite has no tweening, so all motion is computed in Python *before* rendering:
  1. **Keyframes**: one per `time_field` value from the Story frame.
  2. **Interpolation**: values interpolated between keyframes (linear for values, log-linear
     for prices spanning orders of magnitude) with an easing curve (ease-in-out cubic) at N
     frames per keyframe.
  3. **Explicit positions**: for rank-ordered charts (bar races), each frame carries a
     continuous `y_pos` = interpolated rank, encoded as a *quantitative* position (not a sorted
     nominal axis), so bars slide smoothly when they overtake; labels are text marks at the same
     `y_pos`. For line reveals, each frame filters to `t ≤ current` plus an interpolated
     partial final segment.
  4. **Fixed scales**: domains for value axes and colour are computed once over all frames
     (`scale=alt.Scale(domain=…)`), so nothing jitters.
  5. **Render**: each frame rendered via vl-convert to PNG at target size (parallel, cached by
     frame-data hash), then ffmpeg encodes; final frame held 3s.
  Two motion primitives in v1: `bar_race` and `line_reveal`. Anything else is an explicit
  matplotlib story (`motion_backend: matplotlib`, same theme tokens).
- **Alternative B (same spec, different driver)**: B loads the *same Altair
  spec* in a headless Playwright page via vega-embed, and a small generic `setFrame(i)` shim
  swaps in precomputed frame *i*'s rows (`view.data('frame', rows).run()`) and exports the view
  to PNG. Frame data comes from the same Python step 1–4 above, so there is still one chart
  definition; A and B differ only in how frames are rasterized (vl-convert process vs one live
  Vega view). No custom JS chart code is allowed in either.
- **A-vs-B decision rule** (spike output): both must produce visually identical frames
  (pixel diff within tolerance) at both v1 video sizes (1920×1080 and 1080×1350; re-checked if square is promoted); choose the one with lower total render
  time for a 12s/30fps video; tie → A (fewer moving parts, no browser). Encoding uses ffmpeg
  (cross-platform), not AVFoundation.
- **Phase-gated**: this approach is proven by a spike (Phase 0.5 slice) rendering one
  `line_reveal` and one `bar_race` at 1080×1350, 12s/30fps, before the target matrix is built.
  If frame rendering exceeds ~2 min per video or quality is poor, matplotlib becomes the motion
  backend and the plan is updated.
- **Spike result (2026-10-02, Phase 0.5):** 426-frame bar race at 1080×1350 — A (vl-convert)
  5.6 s, B (live Vega view in headless Chrome) 2.6 s, mean pixel difference 0.6% (anti-aliasing).
  Both are far under the gate and encoding dominates total time (~14 s per video), so the
  difference is treated as a tie → **A is the motion renderer**: no browser dependency for
  replicators or CI. B stays reproducible via `scripts/spike_motion_b.py`; revisit if videos get
  long enough for render time to matter.
- **Chrome vs. layout:** the chart comes from Vega; the headline, subtitle and receipt footer are
  drawn by `cachereg.viz.layout` (Pillow) for raster targets and by an HTML template for the blog,
  so every format shares one chart definition and one footer source.
- **Single source per chart, per format family**: `charts.py` defines a chart function used by
  HTML, static, and motion targets (motion adds the frame-data step). Tables are a separate
  `table(story)` function (great_tables), since a table is a different form, not a rendering.
- Tables: great_tables with the brand theme.
- ffmpeg is a system dependency (documented; `cachereg status` checks it).

### 6.4 Stamp / footer (every output)

Auto-generated receipt lines: `SOURCE` (attributions + data as-of), `METHOD`, and `RECEIPTS` —
`cacheregister.dev/<topic>` for receipts, the long GitHub URL for explorations — plus the brand
wordmark. Attribution text comes from
`SOURCE.md`, so license-required credits can't be forgotten. Video: footer persists all frames.

---

## 7. Licensing & what may be published

- Code: Apache-2.0. Charts/text/curated data: CC-BY 4.0.
- The licence gate (applied by `cachereg render` to everything written into
  `receipts/<topic>/output/`) evaluates two rights independently, for every source in the
  receipt's `sources`:
  - **Images/video** (PNG, SVG, WebP, MP4, WebM): allowed unless a source has
    `derived_charts: forbidden` (author policy: derived works are publishable from every source);
    required attributions must appear in the stamp (checked against the rendered footer text).
  - **Inlined data** (blog_html embeds the Story frames as JSON): every source must have
    `redistribution ∈ {allowed, allowed-with-attribution}`; the same applies to `data.json`.
    Otherwise neither is written and the manifest's `withheld` section names the blocking
    source. (A "no-data" vector blog version is backlog, together with `blog_svg`.)
  - Curated disclosures: `source_quote` is a short factual excerpt (≤ 25 words); the figure
    itself is a fact. Quotes are not inlined in published HTML.
  - `unknown` on any right = blocked, with a message naming the source and right.
- Artificial Analysis attribution format followed exactly per their terms.

---

## 8. Security (public from day one)

- **Secrets**: the loader reads environment variables only. Locally they come from a file
  outside the repo whose path is set by `CACHEREG_SECRETS_FILE` (never named in the repo);
  replicators can instead use a repo-local `.env` (gitignored). Variables: `OPENROUTER_API_KEY`,
  `ARTIFICIAL_ANALYSIS_API_KEY`, `RAMP_DATA_API_KEY`, `SEC_EDGAR_USER_AGENT`, optional `HF_TOKEN`. macOS Keychain backend is backlog.
  Secrets never logged; HTTP client redacts auth headers/query params in errors and manifests.
- **Pre-commit**: gitleaks; block `data/`, `outputs/`, `*.parquet`, `*.duckdb`, `.env*`; block
  files > 1 MB outside `published/`; block absolute home paths, usernames, hostnames, local IPs
  (`/Users/`, `/home/`, machine name patterns) in committed text.
- **Workflow (decided 2026-10-02): solo, straight to `main`, no branches or PRs.** Commits are
  pushed directly to `main`. The gate is the local **pre-push
  hook** (`.githooks/pre-push`): guard + pinned gitleaks over exactly the commits being
  pushed, then lint + tests. GitHub **push protection** blocks known secret formats server-side
  regardless. CI is a single backstop job after the push (full-history guard + gitleaks, lint,
  tests), with the author's machine/user patterns supplied via an *encrypted CI secret*.
  Residual risk (accepted): a non-secret leak (e.g. a home path) reaches public `main` if the
  hook is bypassed with `--no-verify`; SECURITY.md has the clean-up steps.
- **GitHub**: secret scanning + push protection on; Dependabot; Actions pinned by SHA,
  `contents: read`; CI never receives API keys and runs only on synthetic fixtures; `main`
  blocks force-pushes and deletion (lift temporarily only to purge a leak).
- **Operational opsec**: no machine names, paths, schedules-with-local-detail, IPs, or account
  identifiers in commits; launchd plist only as template; EDGAR contact email from env only.
- **Supply chain**: new deps checked for supply-chain risk before adding; lockfile committed;
  minimal dependency set.
- `SECURITY.md` with reporting instructions.

---

## 9. Brand proposal (swappable via `config/brand/brand.yaml`)

Goal: stop the scroll on white (LinkedIn) and dark (X) feeds.

- **Canvas**: near-black `#0A0B0F` (stands out on LinkedIn's light feed; native on X dark mode).
  Light variant available for blog.
- **Neon palette** (agreed direction; multiple colours allowed):
  - Primary signal: electric lime `#C8FF2E`
  - Categorical neons: cyan `#00E5FF`, hot magenta `#FF2BD6`, signal orange `#FF6A3D`,
    ultraviolet `#9D7BFF`, laser yellow `#FFE14D`
  - Context/greys: `#5B6070`, `#8A90A2`; text `#F2F4F8`
  - Default rule: highlight what the takeaway is about in neon, put the rest in grey. Up to 6
    neon categories when a comparison needs it (e.g. vendors). Vendor colours are **fixed
    across all charts** (`brand.yaml: vendor_colors`) so OpenAI/Anthropic/Google/etc. stay
    recognizable from post to post.
  - Validated for contrast on the dark canvas and colour-vision deficiency in Phase 0.5/4 (dataviz
    palette validator); hues adjusted if they fail, with direct labels (not legends) as backup.
- **Type**: *Space Grotesk* (headlines, big numbers) + *Inter* (labels) + *JetBrains Mono*
  (data/footer). All SIL OFL → fonts vendored in repo for reproducible renders.
- **Layout**: big takeaway headline as the title (the claim, not the chart description), small
  subtitle with metric definition, huge annotated end-value, footer stamp.
- **Name: Cache Register** (chosen 2026-10-02 after availability checks). Puns on *cash
  register* (money, spend, "ringing up" the market) and *cache* (prompt caching drives AI token
  economics); *register* = the official dated record. Tagline candidates: "Receipts for the AI
  economy" / "Ringing up the AI economy".
- **Receipt motif**: every post "comes with receipts" — the footer stamp is styled as a receipt
  line (sources, data date, repo link); ranking tables can use an itemized-receipt style.
  Series names: *Rung Up* (weekly moves), *Z-Report* (monthly summary), *Price Check*,
  *No Sale* (flops).
- **Footer URL**: `cacheregister.dev` (splash page; `/<topic>` redirects to the analysis) once registered;
  `github.com/jeremiahdillon/cache-register` until then. Handle/URL in footer: `jeremiahdillon.com` + repo link.

---

## 10. Build phases

### Status (2026-10-09)

| Phase | State |
|---|---|
| 0. Scaffold & security | **Done** — guard + pinned gitleaks in the pre-push hook (the gate; straight-to-main workflow), CI backstop, push protection, Pages short links on cacheregister.dev |
| 0.5 Vertical slice | **Done** — OpenRouter rankings + model prices, marts, first receipt `receipts/openrouter-wallet-share`; motion renderer A chosen (§6.3) |
| Layout | **Done** — explorations vs receipts, scoped build, `reproduce` (`docs/plans/2026-10-03-explore-and-receipts.md`) |
| 1. Source verification | **In progress** — `openrouter_models` verified 2026-10-04: `redistribution: forbidden` (CC BY covers only the Datasets endpoints; Terms §12 reserves the rest), derived charts publishable (author policy); the receipt's `blog_html` and `data.json` stay withheld while it uses this source. Remaining Tier-1 sources are verified as each adapter is built |
| 2. Tier-1 adapters | **In progress** — `litellm_prices` done 2026-10-04 (`docs/plans/2026-10-04-litellm-price-history.md`): `010_openrouter_usage` prices each day from LiteLLM history via `config/entities/models.yaml`; the receipt's prices are Exact, its window starts 2025-01-06 and its `blog_html`/`data.json` are committed. `epoch_benchmarks` + `epoch_models` done 2026-10-06 (`docs/plans/2026-10-06-epoch.md`; CC BY 4.0, Latest-only, weekly): marts `020_epoch_capabilities` (ECI, scores, alias coverage) and `021_epoch_models`. `sec_edgar` done 2026-10-06 (`docs/plans/2026-10-06-sec-edgar.md`; XBRL companyfacts for `config/entities/tickers.yaml`, Exact by filing date): mart `030_capex` (quarterly cash capex per company and group, calendar quarters by midpoint, completeness flags). `openrouter_session_cost` + `openrouter_apps` done 2026-10-07 (`docs/plans/2026-10-07-openrouter-apps-session-cost.md`; CC BY 4.0; weekly): session-cost is a weekly 30-day snapshot (Author-only, history from our first fetch 2026-10-07), mart `055_openrouter_session_cost`; app-rankings weekly top 200 since 2025-01-06 plus current category tags (Latest-only), marts `050_openrouter_apps` and `051_openrouter_app_share`; harnesses map to apps via `config/entities/apps.yaml`. `ramp_ai_index` done 2026-10-07 (`docs/plans/2026-10-07-ramp-ai-index.md`; manual import of 13 views, monthly, Latest-only, redistribution unknown): marts `060_ramp_adoption` (per-cut coverage, adoption overall/labs/sectors/sizes), `061_ramp_spend`, `062_ramp_tokens` (token shares by lab, prices, swap checks); sectors map to NAICS via `config/entities/sectors.yaml`. `census_btos` done 2026-10-08 (`docs/plans/2026-10-07-census-btos.md`; public-domain Excel downloads, no key, weekly, Latest-only): marts `070_btos_ai_use` (per cycle, with breaks, coverage and a revision check), `071_btos_ai_monthly` (reference days → calendar months) and `072_adoption_two_lenses` (Ramp beside BTOS by NAICS, plus a check that reproduces Ramp's Census series). Analysis (c) exploration built 2026-10-08. `vercel_ai_gateway` done 2026-10-09 (`docs/plans/2026-10-08-vercel-ai-gateway.md`; CC BY 4.0, no key, daily, Latest-only): marts `090_vercel_shares` (daily lab and model shares, weekly/monthly means of daily shares, label coverage) and `091_gateway_lenses` (analysis (e)'s lenses by vendor and month: Vercel tokens and spend, OpenRouter tokens and estimated spend, Ramp paying). Curated disclosures done 2026-10-09 (`docs/plans/2026-10-08-curated-disclosures.md`; ours, CC BY 4.0, Exact by `recorded_on`): source `curated_disclosures`, mart `080_disclosures`, 50 seed rows |
| 3. Entities & marts | **Started** 2026-10-06 — `cachereg entities suggest --source openrouter\|epoch` (replaces the bootstrap script); `aliases.epoch` maps 173 of 274 ECI models, 49 of the top 50 (98%; target 95% met — Muse Spark has no LiteLLM key); 17 cheap models near ECI 130–150 and GPT-5.2/5.4 Pro mapped by hand |
| 4–5, 7 | Not started (Phase 5: explorations for analyses (a), (b) and (d) built 2026-10-06) |
| 6. Scheduling & ops | **Started** 2026-10-06 — `cachereg fetch --due`, launchd template and `make install-schedule` (§4.5); the author loads the agent by hand (loaded 2026-10-07; first run fetched the daily sources). 2026-10-07: `status` shows cadence, last fetch, next due and last error per source. Next: a week unattended with no gaps |

**Open items carried between sessions**
- **Ramp AI Index (2026-10-07):** imported by hand, monthly: run `cachereg fetch ramp_ai_index
  --from-clipboard` (no `--cut`) for the list of 13 views with their page URLs, then one import per
  view. First real import 2026-10-07 (all 13 cuts, checks clean after the price-check fix); next due
  2026-11-07. The token views (Ramp Token Spend Management) are a different population from adoption;
  never mix the denominators. Blended prices run below Input (cached tokens, apparently), so never
  treat Blended as a mix of Input and Output. Check `ramp_cut_coverage`, `ramp_price_check` and
  `ramp_token_check` after each round of imports. The Data Partner key remains
  the automated route; with a key, check whether the API covers the token views.
- **Census BTOS (2026-10-08):** fetched weekly by the launchd agent; Census releases a cycle every second
  Thursday. Check `btos_revision_check` after each release: if it stays empty until ~2026-12-08, switch
  `census_btos` to `revisions: append-only` and select cycles by `publication_date` (Exact; needs a
  `vintage_at` hook). `btos_ramp_census_check` must stay all-`agree` after each Ramp import: Ramp moved
  from collection-start to collection-end months in June 2026, and a `neither` means a revision, another
  method change or a wrong import. The two AI wordings are separate series (break at 17 Nov 2025);
  never draw a line across them. Stage parses every stored workbook version (~3 s per sector × size
  version), so build time grows by about a minute a year; add a parse cache if that starts to matter.
  Mart `072` reads Ramp and BTOS, so a bare `cachereg build` needs both.
- Backlog: embedded/subset fonts for `blog_html` (now Google Fonts with system fallback); vector
  `blog_svg` with chrome + footer (also enables a no-data blog version); `promote` command.
- `config/entities` is read through `core.paths.entities_dir()` by `build`, `entities` and
  `sec_edgar` alike, so tests redirect all of them with one patch (`sec_edgar`'s vendor check used to
  read the shipped `vendors.yaml` in tests). A test checks that every `vendor` in `tickers.yaml` resolves.
- LiteLLM lists many models late (most Chinese-lab models only from 2026-09-05/18): ~26% of top-50 tokens (10% of est. spend) are priced with a model's first later listing, flagged per row and reported. Re-check when Phase 3 entities land; Gemini 2.5 Flash preview `:thinking` variants stay unpriced (own price, not in LiteLLM).
- **Analysis (a) "cost of intelligence": exploration built** 2026-10-06
  (`explore/2026-10-06-cost-of-intelligence/`, `docs/plans/2026-10-06-cost-of-intelligence.md`):
  cheapest blended list price per ECI level (130/140/150) per day, static chart + sensitivity and
  coverage tables. Next: decide on promotion to a receipt, then the motion hero; move the computation
  into a mart when (b) needs it.
- **Analysis (d) "does quality win usage?": exploration built** 2026-10-06
  (`explore/2026-10-06-quality-vs-usage/`, `docs/plans/2026-10-06-quality-vs-usage.md`): token-weighted
  ECI of OpenRouter paid tokens vs the frontier, lag in months, near-frontier share. Not promoted.
  Note: `or_model_daily` leaves `model_id` null on `:free` permaslugs (resolve via the paid alias).
- Analysis (a)/(d) top-50 coverage: GPT-5.4 Pro and GPT-5.2 Pro mapped by hand (`# manual`; not in
  OpenRouter's rankings, so `suggest` never proposes them) → `eci_top50` 49/50 (98%). Neither changes (a)
  (never cheapest; charts identical) or (d) (not on OpenRouter). Muse Spark stays unmapped (no LiteLLM key);
  GPT-5 Pro (rank 51) is unmapped too.
- **(d) `within_2x_cheapest` boundary: fixed** 2026-10-07. Several models are priced at exactly 2× the
  cheapest (e.g. $2.00 vs $1.00), and DuckDB's parallel `sum()` left ~1e-15 noise in `usd_per_mtok`, so
  rebuilds moved single weeks by up to 9 points (13-week and quarterly medians unchanged). Weekly prices are
  now rounded to $0.000001/Mtok in SQL (exactly 2× counts as within when both prices are whole multiples of that unit); repeated rebuilds give identical (d)
  frames (same `data_hash`).
- **Analysis (c) "two lenses on adoption": exploration built** 2026-10-08
  (`explore/2026-10-08-two-lenses-adoption/`, `docs/plans/2026-10-08-two-lenses-adoption.md`): Ramp's
  paid adoption beside BTOS current use. The lenses rank Ramp's seven sectors alike (ρ 0.79–0.89 every
  complete month since Sep 2023; health care and manufacturing differ); every Ramp size band sits above BTOS's
  largest size class. PNGs only (Ramp licence unknown). Not promoted. Its figures move with each Ramp
  import and BTOS release; re-render after both. Plan and build each passed an adversarial review.
- **Vercel AI Gateway (built 2026-10-09):** fetched daily by the launchd agent from its next run (`fetch --due`
  reads the registry each time; `curated_disclosures` weekly, a no-op while the file is unchanged). First real fetch 2026-10-09 reproduced the
  plan's September 2026 first look exactly. Compare two months of vintages (are days older than the
  trailing window ever revised?) and record it in its SOURCE.md before switching to `append-only`.
  `models.yaml` maps 64 of 70 Vercel model names by hand; check `vercel_label_coverage` for new unmapped
  labs or models after each month (`entities suggest --source vercel` is backlog). Lab slugs with ≥ 1% of
  tokens or spend on any day all map to existing vendors. Mart `091` reads Vercel, OpenRouter rankings,
  LiteLLM and Ramp, so a bare `cachereg build` needs all four.
- **Curated disclosures (built 2026-10-09):** 50 seed rows (45 primary) recorded 2026-10-09; the evidence
  (candidate rows, page texts, transcripts) stays local in `data/research/2026-10-08-disclosures-vercel/`.
  Add rows by the routine in its SOURCE.md (`recorded_on` = the day added; corrections supersede, never
  edit). The pre-push hook and CI refuse an edited or removed row. Left out on purpose (SOURCE.md lists
  why): forecasts, investor or anonymous-source figures, CNBC's $13B OpenAI ARR, TechCrunch's "300 million
  users", the Amazon quote, Microsoft's token totals, Google's retail-segment tokens; Claude Code's
  run-rate and Microsoft's Foundry customers need a metric first. `fetch` may now return None
  (nothing new to store); the CLI prints `same`.
- **Chart fit (found 2026-10-08):** `Frame.compose` resizes a chart's PNG to the plot box exactly, so a chart
  whose outer size (axes, titles) differs from the box is stretched or squeezed (the two-lenses LinkedIn
  sectors chart was ~10% compressed before the fix; Vega widens a concat panel to its title). The
  two-lenses `charts._fit` renders, measures and corrects to a sub-pixel fit, or raises. The other
  explorations and receipts have not been measured; check them (PNG size vs `page().plot_box`) before
  promoting any, and move `_fit` into `cachereg.viz` on its second use. `open-middle` must not change.
- **Analysis (b) "capex vs price collapse": exploration built** 2026-10-06
  (`explore/2026-10-06-capex-vs-price/`, `docs/plans/2026-10-06-capex-vs-price.md`): quarterly
  hyperscaler capex (`030_capex`) beside the cheapest price per ECI level (`040_eci_model_prices`,
  (a)'s series as a mart). Not promoted. When (a) is promoted, switch its main series to `040`.
  Quarters, headline, sensitivity and price-setter shares were recomputed independently from the
  SEC facts and mart extracts (no mismatches); a derived quarter absorbs any restatement of only
  one of its two year-to-date legs (documented in `030_capex`).
  Since `040` reads LiteLLM and Epoch, a bare `cachereg build` refuses to run when LiteLLM has
  fetches and Epoch has none (a partly covered mart); fetch both, or scope with `--sources`.
- **Epoch aliases left out on purpose** (`entities suggest --source epoch` still proposes them; drop
  them if `--write` is used again): `Qwen2.5-72B` → `qwen/qwen2.5-vl-72b-instruct` (Epoch's group
  includes the VL model), and new model `openai/gpt-3.5-turbo-0613` (its keys mix the 16k variant).
  E3 candidates (same model if the date is ignored) are never written; confirm them by hand.
- **Scheduling (Phase 6):** `fetch --due` and the launchd template are built (§4.5). Once the agent is
  loaded, OpenRouter rankings and LiteLLM accrue daily history; until then fetch them by hand before
  rendering. Check `~/Library/Logs/cachereg/fetch.log` after the first runs.
  `load_sources` rejects an unknown `cadence` with the source's id and the allowed values.
- **OpenRouter apps and session cost (2026-10-07):** the launchd agent fetches both weekly; a missed
  session-cost week can never be fetched later, so check `cachereg status` after each Monday.
  Compare the first month of app-rankings vintages (is anything older than the trailing weeks
  revised?) and record the result in its SOURCE.md. 8 session-cost permaslugs (Hermes Agent only,
  never in the daily top 50) have no `models.yaml` entry; `entities suggest` does not read these
  sources yet (backlog). Mart `051` reads apps and rankings, so a bare `cachereg build` needs both.
- Published receipts are left as rendered unless the author asks: `open-middle` must not change;
  `openrouter-wallet-share`'s committed PNGs predate the 2026-10-05 layout changes, so a re-render
  would change its visuals. Rendered floats are rounded to 9 significant digits (after
  `data_hash`), so re-renders of unchanged data no longer churn `data.json`.
- Dependency supply-chain re-check of the Phase 0.5 dependencies is still pending (the scoring
  service was unavailable on 2026-10-06, also on a retry). The Epoch work added no dependencies.
- After new models enter the OpenRouter top 50 or Epoch's index, run `cachereg entities suggest
  --source openrouter` / `--source epoch` and review the proposals before `--write` (new models are
  appended; aliases are inserted without rewriting reviewed lines).

| Phase | Deliverable | Done when |
|---|---|---|
| **0. Scaffold & security** | git init, uv project, CLI skeleton, settings/secrets loader, gitignore, pre-commit + CI guards (gitleaks + custom), LICENSEs, SECURITY.md, CLAUDE.md, public GitHub repo with push protection + branch protection | CI green; a deliberate fake secret / data file / home path is blocked by **CI** (not just pre-commit) |
| **0.5 Vertical slice** | OpenRouter `rankings-daily` adapter (native, CC BY 4.0, verified) + OpenRouter models adapter (snapshot, redistribution to verify; prices only) — CI runs the slice on synthetic fixtures, the author runs it with a key → staged → `usage_share` mart → a wallet-share analysis as the first explore → `x_png` + `blog_html` + one `bar_race` MP4, stamped, with manifest; plus the motion spike (A vs B) | One command renders all three from a clean clone; motion spike meets the §6.3 gate or the backend decision is changed |
| **1. Source verification** | For each Tier-1 source: confirm endpoints, auth, rate limits, ToS, license, `redistribution`, `derived_charts`, `revisions`, historical availability → fill `SOURCE.md` + registry | All `unknown` flags resolved or explicitly deferred; Phase-5 analysis list re-confirmed |
| **2. Tier-1 adapters** | Native-history first: LiteLLM, Epoch, Ramp AI Index, OpenRouter `app-rankings`/`session-cost`, BTOS, Anthropic Economic Index, EDGAR, LMArena; then snapshot: Artificial Analysis, Ramp Rate, HF; curated disclosures seeded | `cachereg fetch && cachereg build` works from a clean clone with keys |
| **3. Entities & marts** | Resolver + `entities suggest/check`; marts: `model_dim`, `price_history`, `benchmarks`, `usage_share`, `adoption`, `capex`, `disclosures` | Coverage ≥95% per mart measure as defined in §4.3 |
| **4. Story & viz kit (full)** | Generalize the slice: theme, remaining v1 targets, `table`, `publish` (with its check), `_template` | Template analysis renders every v1 target on synthetic data in CI |
| **5. Starter analyses** | See table below | Each has README findings + v1 targets rendered |
| **6. Scheduling & ops** | launchd install script, `fetch --due`, `status` | Runs unattended a week with no gaps |
| **7. Claude skills & playbook** | `/new-analysis`, `/render-check` (render all targets and eyeball them); playbook seeded | New exploration scaffolded and rendered in one command |

**Starter analyses: dependencies and fallbacks** (built in this order; each is contingent on
Phase 1 only where marked):

| Analysis | Primary sources | Depends on unverified? | Fallback |
|---|---|---|---|
| (a) **Cost of intelligence** — motion hero: cheapest price to reach a given capability level, over time | LiteLLM price history × Epoch benchmark hub / LMArena scores (native history) | No (Exact/native) | Artificial Analysis index used as the *current* cross-section only, not for history |
| (b) **Capex vs price collapse** | EDGAR hyperscaler capex × (a) | No | — |
| (c) **Two lenses on adoption** | BTOS AI use × Ramp AI Index (by sector & size), mart `072` | No (both built; Ramp is a manual import, no key) | BTOS-only (`--sources census_btos` with config `ramp: false`) if a replicator has no Ramp imports |
| (d) **Does quality win usage?** | Benchmarks × OpenRouter `rankings-daily` | No (verified) | — |
| (e) **Developer wallet vs enterprise wallet** — three *separately labelled* lenses on the same vendors, never put on one axis or converted into each other: (1) developer gateways: share of estimated $ on OpenRouter and Vercel AI Gateway's measured spend share (#12), (2) share of US businesses paying (Ramp), (3) reported revenue run-rates (curated disclosures). Lenses (1) and (2) side by side in mart `091_gateway_lenses`; lens (3) in `080_disclosures` (built 2026-10-09). Output: vendor **rank/share comparison** across lenses (small multiples or slope chart) plus where they disagree | OpenRouter est. spend; Ramp AI Index vendor breakdown; curated disclosures | No | If lenses aren't comparable enough for a claim, publish as "three views" without a ranking claim |

**v1 scope vs backlog** (to keep the first weeks lean):
- v1 render targets: `blog_html`, `x_png`, `linkedin_png`, `x_video` (MP4 16:9),
  `linkedin_video` (MP4 4:5), `web_video` (WebM), `table_png`.
- Backlog: GIF, WebP, square formats, `export-archive`, Keychain backend, marimo notebooks,
  `/add-source` and `/promote` skills (do manually until needed), `doctor` (fold into `status`),
  Tier-2 sources.
- v1 CLI: `fetch`, `build`, `render`, `publish`, `status`, `entities` (6 commands).

## 11. Risks & open questions

1. **OpenRouter datasets** cover only OpenRouter traffic (third-party developer routing), top-50
   models per period, tokens without input/output split; 500 requests/day per account limits
   backfill speed (plan backfills in monthly windows). Every chart must say "on OpenRouter",
   not "the market".
2. **Artificial Analysis history**: if no historical API, AA-based time series start at our
   first snapshot (unreplicable by others before that date; cannot be republished).
   Mitigation: LMArena/Epoch benchmark history as native-history alternatives.
3. **Entity resolution drift** as vendors rename/alias models — ongoing maintenance cost.
4. **Ramp Data access** requires a provisioned key from the Ramp Data Partner Program; replicators
   must apply. API is marked "subject to change". Analyses using Ramp state this in their README.
5. **Licensing of derived charts** — settled by author policy (2026-10-05): derived works are
   published from every source, credited; raw data only where `redistribution` allows.
6. **vl-convert motion performance** (hundreds of frames) — mitigated by caching + parallel
   render; matplotlib fallback.
7. **Spend estimates** are model-derived; risk of overclaiming — require bounds + method note
   on every spend figure.

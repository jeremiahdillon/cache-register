# Plan: explorations and receipts

Status: APPROVED · 2026-10-03 · adversarial review converged (3 rounds) · supersedes the `analyses/explore` / `analyses/series` layout in PLAN §3 and §5.

## Goal

Separate cheap, dated, possibly-abandoned **explorations** from the subset of work that is
promoted as a **receipt** (a topic worth showing publicly). Only receipts get a short link and
committed visuals, and any one receipt can be reproduced on its own without fetching or building
data that other receipts or explorations use.

The repo knows nothing about social posts: a receipt is a topic with one analysis and one or more
visuals; where those visuals end up is outside the repo.

## Layout

```
explore/                                   scratch work; dated by start date; no short links
  2026-10-02-openrouter-wallet-share/
    README.md                              question, notes, findings so far
    analysis.py  charts.py  explore.yaml   optional; same Story contract as receipts
receipts/                                  promoted topics; each = one short link
  openrouter-wallet-share/                 cacheregister.dev/openrouter-wallet-share
    README.md                              finding(s), method, caveats, "reproduce this receipt"
    receipt.yaml                           title, sources, as_of, visuals, promoted_from
    analysis.py  charts.py                 maintained version (copied from the exploration, cleaned up)
    output/                                committed: rendered visuals + manifest (+ data file if licences allow)
      share-lines.x_png.png
      share-lines.linkedin_png.png
      share-lines.blog_html.html           only if every source allows redistribution (data is inlined)
      share-race.linkedin_video.mp4
      share-race.x_video.mp4
      manifest.json
      data.json                            only if every source allows redistribution
src/cachereg/  config/  tests/  docs/  assets/   unchanged roles
outputs/  data/                            gitignored (exploration renders, raw/staged data)
```

`analyses/` (including `series/` and `_template/`) is removed.

## Rules

1. **Explorations** (`explore/YYYY-MM-DD-<slug>/`): free-form, no short link, never referenced by
   the short-link site. Renders go to gitignored `outputs/`. CI only checks their Python compiles.
2. **Receipts** (`receipts/<topic>/`): the folder name *is* the short link
   (`cacheregister.dev/<topic>`): lowercase words joined by `-`, ≤ 32 chars, unique. Renamed or
   retired topics keep resolving via `config/link-aliases.yaml`. Every visual's footer carries the
   topic link: for anything under `receipts/`, `render` passes the folder name as the link (no
   `link:` field to drift). Explorations have no short link; their footer shows the long GitHub URL.
3. **Promotion** copies an exploration into `receipts/<topic>/` by hand (the exploration stays as
   the record, with a "Promoted to receipts/<topic>" line added to its README): copy
   `analysis.py`, `charts.py`, README; write `receipt.yaml`. A `promote` command stays in the
   backlog (PLAN §10) until promotions become frequent.
4. **Multiple visuals per receipt**: `receipt.yaml` lists visuals, each naming a chart function in
   `charts.py` and its render targets:
   ```yaml
   title: Who gets paid on OpenRouter?
   sources: [openrouter_rankings, openrouter_models]
   as_of: 2026-10-02            # data date of the committed outputs
   promoted_from: explore/2026-10-02-openrouter-wallet-share
   config: {weeks: 13, unpriced_flag: 0.03, race_top_n: 8}
   visuals:
     - {name: share-lines, chart: line_chart, targets: [x_png, linkedin_png, blog_html]}
     - {name: share-race,  chart: race,       targets: [linkedin_video, x_video]}
   ```
   `render` replaces today's hard-coded "line chart for static/HTML, bar race for video".

   **Chart contract** (functions in `charts.py`, named by `chart:`):
   - *static* chart — `chart(story, width, height, font_scale, interactive=False) -> alt.Chart`;
     used for PNG targets and (with `interactive=True`, `width="container"`) for `blog_html`.
   - *motion* chart — `<chart>_specs(story, width, height, font_scale, cfg) -> (list[dict], fps)`:
     the chart module owns everything chart-specific (keyframes, interpolation via
     `cachereg.viz.motion` helpers, scales such as `x_max`, `top_n`, group maps) and returns one
     Vega-Lite spec per frame; `render` only rasterises the specs and encodes the video.
     `render` validates that each visual's chart supports its targets' kind before rendering.
   - *data table* for `blog_html` — optional `table(story) -> pl.DataFrame` in `analysis.py`; the
     HTML template formats it generically (floats in `[0, 1]` columns listed in `percent_columns`
     as %, others as numbers). No analysis-specific code in `render.py`.
5. **Committed outputs**: `cachereg render receipts/<topic>` writes into `receipts/<topic>/output/`
   at the pinned `as_of` (or `--as-of`, which updates `receipt.yaml`). To limit repo growth it
   rewrites outputs only when the canonical data hash or the **render-inputs hash** (rule 7)
   differs from the committed manifest, unless `--force`. The guard allows files over 1 MB only for paths matching the regex
   `^receipts/[^/]+/output/`; `outputs/` and `data/` stay blocked. File names are deterministic:
   `<visual>.<target>.<ext>`.
6. **Licence gate before writing anything into `output/`** (PLAN §7, both rights):
   - images/video are written only if every source has `derived_charts ∈ {allowed,
     allowed-with-attribution}`;
   - `data.json` (the Story frames) and `blog_html` (which inlines them) are written only if every
     source also has `redistribution ∈ {allowed, allowed-with-attribution}`; otherwise they are
     not written and the manifest records which source blocked them. This **supersedes PLAN §7's
     "no-data mode"** for now: that mode needs a vector chart with chrome and footer (the
     `blog_svg` work, in the backlog); until it exists, skipping is the honest option. PLAN §7 is
     updated to match.
   - The current unconditional `story_frames.json` write is removed; for explorations (gitignored
     `outputs/`) the frames are still written there for inspection.
   Today `openrouter_models` has `redistribution: unknown`, so the first receipt ships PNG + MP4
   only until Phase 1 verifies its terms.
7. **Manifest** (`output/manifest.json`): git SHA, as_of, per-source class / fetch date / vintage /
   `vintage_after_as_of`, the **canonical data hash**, the **render-inputs hash** (sha256 over the
   receipt's `analysis.py`, `charts.py`, `receipt.yaml`, `config/brand/brand.yaml`, `assets/fonts/*`
   and `src/cachereg/{render.py,viz/*.py,story/*.py}`, in sorted path order), per-output file
   hashes, and any outputs withheld by the licence gate with the reason. No absolute paths, hostnames or usernames.
   *Canonical data hash*: for each Story frame (frames in name order), sort columns by name and rows
   by all columns; dates as ISO strings; integers as-is; floats rounded to 7 significant digits (float32-safe);
   serialise each frame as CSV with fixed options; sha256 over `name\ncsv\n` for all frames.
   Defined once in `cachereg.story` and unit-tested for order/dtype invariance.

## Standalone reproduction

`cachereg reproduce receipts/<topic> [--latest]`:

1. Read `receipt.yaml` → `sources`, `as_of`.
2. `fetch` only those sources (skip with `--no-fetch` if raw data is already present). A failed
   fetch (e.g. missing key) stops with the source and reason.
3. **Pre-flight** (after fetching, before building): for every source, compute the vintage
   `cutoff()` would choose for `as_of`. If a snapshot (Author-only) source has no fetch on or
   before `as_of`, report **cannot reproduce exactly: <source> is a snapshot source and you have
   no snapshot on or before <as_of>** and stop, suggesting `--latest`. (Latest-only sources fall
   back to the earliest fetch and are reported as such.)
4. `build --sources …` (see Marts below): only marts whose declared inputs are among these sources.
5. Render every visual into a temporary folder (never over the committed outputs).
6. Compare the canonical data hash and source vintages with the committed manifest: report
   **identical**, or **differs** with the reason (e.g. a Latest-only source revised its data;
   `vintage_after_as_of` was needed).

`--latest` reproduces the *method* on the replicator's own latest data (as_of = today), renders
into a temporary folder, and reports how the result differs from the committed one. This is the
expected path for receipts priced from snapshot sources until LiteLLM price history (Phase 2,
Exact) replaces the snapshot, or a published archive exists (PLAN §2.3).

A replicator needs: clone, `uv sync`, the keys for that receipt's sources (listed in its README),
and one command. Nothing from other receipts or explorations is fetched or built.

## Marts (per-source build)

- A **mart is one SQL file** in `src/cachereg/marts/`. Its header declares
  `-- inputs: <source ids>`; the file may create several tables, all of which depend on all of its
  inputs. `010_openrouter_usage.sql` declares `openrouter_rankings, openrouter_models`.
- **Variables are generic**: before running marts, `build` sets one DuckDB variable per staged
  source, `<source_id>_cutoff` (the fetch date chosen by `cutoff()` for `as_of`), plus `as_of`.
  Mart SQL reads only these (`getvariable('openrouter_rankings_cutoff')`, …), replacing today's
  ad-hoc `rankings_fetch_cutoff` / `price_snapshot` set in Python.
- `build --sources a,b` stages only those sources and runs only marts whose inputs ⊆ {a, b};
  a mart with some-but-not-all inputs available is an error; tables of skipped marts are dropped
  so stale tables can't be reused. Without `--sources`, all sources with fetches are used.
- A receipt's `sources` must cover the inputs of every mart its analysis reads; `reproduce`
  checks this up front and fails with a clear message otherwise.

## Short-link site

Built from `receipts/*/` only (plus aliases); the slug is the folder name (validated as now). `cacheregister.dev/<topic>` redirects to
`github.com/jeremiahdillon/cache-register/tree/main/receipts/<topic>`. The Pages workflow
triggers on `receipts/**`, `config/**`, `src/cachereg/site.py`.

## Migration of current work (one commit, one push)

The short link must never 404, so the code change and the move land together:

1. Implement the code changes below (site reads `receipts/`, Pages filter `receipts/**`, render,
   build, guard, tests) with the test fixtures pointing at `receipts/`.
2. In the same working tree: `git mv analyses/explore/2026-10-02-openrouter-wallet-share
   explore/…`; rename its `story.yaml` → `explore.yaml` and drop `link:`; create
   `receipts/openrouter-wallet-share/` from it (copy, then clean up) with the two visuals.
3. Render the receipt's outputs (PNG + MP4) into `receipts/openrouter-wallet-share/output/`.
4. Remove `analyses/`. Run the full test suite and `cachereg site` locally, check that
   `_site/openrouter-wallet-share/index.html` points at `receipts/openrouter-wallet-share`.
5. Commit and push once; the Pages workflow (now triggered by `receipts/**`) redeploys; verify
   `cacheregister.dev/openrouter-wallet-share` resolves to the new path.

## Code changes

- `site.py`: links from `receipts/*/` folder names; aliases as now.
- `render.py`: read `receipt.yaml`/`explore.yaml`; loop visuals × targets; output dir per rule 5;
  licence gate (rule 6); manifest additions (rule 7); generic `chart` dispatch for static/HTML vs
  motion charts (a chart function returning a Vega-Lite spec vs a motion spec).
- `build.py`: mart registry from SQL headers; `sources=` filter; per-mart input check (replaces
  the current all-or-nothing OpenRouter check).
- `cli.py`: `fetch` accepts several sources; `build --sources`; `render <receipt|exploration>`;
  new `reproduce` (`promote` stays in the backlog).
- `scripts/guard.py`: size exception regex changes from `^analyses/.+/published/` to
  `^receipts/[^/]+/output/`.
- `story/`: canonical data hash (rule 7).
- Existing tests that hard-code `analyses/explore/...` (`test_pipeline.py`, `test_site.py`) move to
  `receipts/…`; render tests use `receipt.yaml`.
- New tests: site uses receipts only; slug = folder; guard size regex; canonical hash invariance;
  `build --sources` skips/drops unrelated marts and rejects partial inputs; reproduce on synthetic
  data (identical → revise a synthetic Latest-only vintage → differs; snapshot gap → "cannot
  reproduce exactly"); licence gate withholds `data.json`/`blog_html` and never writes
  `story_frames.json` under `receipts/`; explorations compile.
- Docs: PLAN §3, §5, §6.2, §7, §10; CLAUDE.md; README.

## Out of scope

Posts/social copy; per-post links; landing pages (the redirect target can become one later);
LiteLLM and other Phase 2 sources.

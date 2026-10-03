# Cache Register — rules for AI collaborators

The plan of record is `docs/PLAN.md`. Read the relevant section before changing architecture.

## Non-negotiables

- **Public repo.** Never commit secrets, downloaded data, rendered outputs (outside
  `receipts/*/output/`, which only `cachereg render` writes, behind the licence gate), absolute home paths, hostnames, usernames, IPs, or the name or
  location of the author's local secrets file. Run `make guard` before committing.
- **Never read secret files** or print secret values. Use `cachereg status` to see what is set.
- **One-way data flow:** `data/raw` (immutable) → staged → marts → analyses (receipts and
  explorations). Analyses read marts only and never import `cachereg.sources`.
- **Sources follow the contract** in PLAN §4.2 (`SOURCE.md`, `fetch.py`, `stage.py`, tests on
  synthetic fixtures). Adding a source must not require editing core.
- **Tests use synthetic fixtures only** — never recorded real API responses (licensing).
- **Every derived number states its method and caveats** in the analysis README; spend figures
  are estimates with bounds.
- **Analysis and synthesis only — never draft post copy**, captions, hooks or social text. An
  analysis README ends at findings and caveats; the visuals' own headline/subtitle state the
  finding plainly.
- **Charts credit sources** via the auto-generated footer; never hand-write attributions.

## Conventions

- Python 3.12, uv, ruff (`make format`), pytest. Installs go through `sfw` on the author's machine.
- Score new dependencies (Socket `depscore`) before adding them; keep the dependency set small.
- **Explorations** go in `explore/YYYY-MM-DD-<slug>/` (date = start date; `explore.yaml`; no short
  link; may be abandoned). **Receipts** are promoted topics in `receipts/<topic>/` (`receipt.yaml`,
  committed `output/`); promote by copying the exploration and noting it in the exploration's
  README. Charts follow the contract at the top of `src/cachereg/render.py`. Never hand-edit
  `output/`; re-render with `cachereg render receipts/<topic>`. The repo does not track posts.
- Code ported from the author's earlier projects is re-implemented to these contracts and
  reviewed — never copied verbatim (PLAN §2.4).
- **No branches or PRs.** Commit in small logical steps and push straight to `main`; the
  pre-push hook runs the guard, gitleaks, lint and tests.
- **Short links** belong to receipts only: the receipt folder name (lowercase-hyphenated, ≤ 32
  chars) is `cacheregister.dev/<topic>`. Never reuse or rename a posted topic; if you must, add the
  old name to `config/link-aliases.yaml`.

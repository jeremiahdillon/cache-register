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

- Python 3.12, uv, ruff (`make format`), pytest.
- Check new dependencies for supply-chain risk before adding them; keep the dependency set small.
- **Explorations** go in `explore/YYYY-MM-DD-<slug>/` (date = start date; `explore.yaml`; no short
  link; may be abandoned). **Receipts** are promoted topics in `receipts/<topic>/` (`receipt.yaml`,
  committed `output/`); promote by following the **Promotion** steps in PLAN §5 (they cover the
  short link, `receipt.yaml` visuals order = the receipt page's slide order, rendering and checking
  the site). Charts follow the contract at the top of `src/cachereg/render.py`. Never hand-edit
  `output/`; re-render with `cachereg render receipts/<topic>`, which updates the root reel and the
  receipt page once it reaches `main`. The repo does not track posts.
- **One branch per piece of work, no PRs.** Several agents work in this repo, so never commit to `main`
  directly: start a branch from the latest `origin/main` (`claude/<topic>`), commit in small logical steps
  and push the branch as you go. When the author OKs the work, rebase it on `origin/main`, re-run the
  checks and fast-forward `main` to it (linear history; no merge commits, no PRs). The pre-push hook runs
  the guard, gitleaks, lint and tests on every push.
- **Short links** belong to receipts: the receipt folder name (lowercase-hyphenated, ≤ 32
  chars) is `cacheregister.dev/<topic>`, the receipt's page on the site. An exploration may reserve its future topic with `link:` in
  `explore.yaml` (it redirects to the exploration until a receipt of that name, `promoted_from` it,
  takes over). Never reuse or rename a posted topic; if you must, add the old name to
  `config/link-aliases.yaml`.

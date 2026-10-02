# Cache Register — rules for AI collaborators

The plan of record is `docs/PLAN.md`. Read the relevant section before changing architecture.

## Non-negotiables

- **Public repo.** Never commit secrets, downloaded data, rendered outputs (outside
  `analyses/**/published/`), absolute home paths, hostnames, usernames, IPs, or the name or
  location of the author's local secrets file. Run `make guard` before committing.
- **Never read secret files** or print secret values. Use `cachereg status` to see what is set.
- **One-way data flow:** `data/raw` (immutable) → staged → marts → analyses. Analyses read
  marts only and never import `cachereg.sources`.
- **Sources follow the contract** in PLAN §4.2 (`SOURCE.md`, `fetch.py`, `stage.py`, tests on
  synthetic fixtures). Adding a source must not require editing core.
- **Tests use synthetic fixtures only** — never recorded real API responses (licensing).
- **Every derived number states its method and caveats** in the analysis README; spend figures
  are estimates with bounds.
- **Charts credit sources** via the auto-generated footer; never hand-write attributions.

## Conventions

- Python 3.12, uv, ruff (`make format`), pytest. Installs go through `sfw` on the author's machine.
- Score new dependencies (Socket `depscore`) before adding them; keep the dependency set small.
- Analyses: `analyses/explore/YYYY-MM-DD-<slug>/` for new questions; promote to
  `analyses/series/<slug>/` with `git mv`, leaving a stub README at the old path.
- Code ported from the author's earlier projects is re-implemented to these contracts and
  reviewed — never copied verbatim (PLAN §2.4).
- **No branches or PRs.** Everything goes straight to `main`. **Don't commit unless asked**:
  leave changes in the working tree and end with a short summary grouped into suggested
  commits. The author sequences and pushes commits (typically 6–8am); the pre-push hook runs
  the guard, gitleaks, lint and tests.

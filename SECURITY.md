# Security

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security tab → "Report a
vulnerability"). Do not open a public issue for anything involving credentials or data
exposure.

## What this repository protects against

- **Secrets in git.** API keys live only in the environment, a file outside the repo, or a
  gitignored `.env`. The guard (`scripts/guard.py`) and gitleaks run in the pre-push hook and
  again in CI after every push; GitHub secret scanning and push protection are enabled.
- **Licensed data in git.** `data/`, `outputs/`, Parquet/DuckDB files and large files are
  blocked by path, type and size.
- **Operational details.** Absolute home paths, local hostnames, private IP addresses and
  machine-specific identifiers (supplied privately to CI) are blocked.

This is a solo project that pushes straight to `main`, so the local **pre-push hook** is the
gate (run `make setup` once to install the hooks). GitHub push protection blocks known secret
formats server-side, and CI re-checks the full history after every push as a backstop.

## If something leaks

1. **Rotate the credential immediately** at the provider. Assume it is compromised the moment
   it is pushed; removing it from history does not un-leak it.
2. Remove it from history (`git filter-repo`), temporarily allow force-pushes on `main` (repo
   settings → Branches), force-push, re-block, and ask GitHub support to purge
   cached views if needed.
3. Add a guard rule or test so the same class of leak is caught next time.

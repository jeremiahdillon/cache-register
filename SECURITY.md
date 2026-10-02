# Security

## Reporting a vulnerability

Please use GitHub's **private vulnerability reporting** (Security tab → "Report a
vulnerability"). Do not open a public issue for anything involving credentials or data
exposure.

## What this repository protects against

- **Secrets in git.** API keys live only in the environment, a file outside the repo, or a
  gitignored `.env`. The guard (`scripts/guard.py`) and gitleaks run in CI on every push and
  pull request; GitHub secret scanning and push protection are enabled.
- **Licensed data in git.** `data/`, `outputs/`, Parquet/DuckDB files and large files are
  blocked by path, type and size.
- **Operational details.** Absolute home paths, local hostnames, private IP addresses and
  machine-specific identifiers (supplied privately to CI) are blocked.

CI is the enforcement of record: the local pre-commit hook can be bypassed with
`--no-verify`, so `main` only accepts changes through pull requests that pass CI.

## If something leaks

1. **Rotate the credential immediately** at the provider. Assume it is compromised the moment
   it is pushed; removing it from history does not un-leak it.
2. Remove it from history (`git filter-repo`), force-push, and ask GitHub support to purge
   cached views if needed.
3. Add a guard rule or test so the same class of leak is caught next time.

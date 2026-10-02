# Cache Register

**Receipts for the AI economy.** Reproducible analysis of public AI-market data — token
usage, model prices, benchmarks, business adoption and the capital behind it — turned into
charts and videos. Every published visual links back to the exact code that made it.

> **Status:** Phase 0 (scaffold and security). Nothing fetches data yet. The full plan is in
> [`docs/PLAN.md`](docs/PLAN.md).

## How it works

```
sources (APIs) ──fetch──▶ data/raw ──build──▶ staged ──▶ marts ──▶ analyses ──render──▶ HTML · PNG · MP4
                         (gitignored; never committed)                     (committed code + published outputs)
```

- **Data is not in this repo.** Most sources' terms don't allow redistribution, so you
  download your own copy with your own API keys. Code, configuration, model-name mappings and
  a small curated dataset of public disclosures are committed.
- **Reproducibility is stated honestly per source.** Some sources keep full history (anyone
  gets identical numbers); some revise past values; some only expose the current state, so
  history exists only from the day you start collecting. See `docs/PLAN.md` §4.4.
- **Analyses are independent folders** under `analyses/explore/` (dated, exploratory) and
  `analyses/series/` (recurring). Each has a README with the question, method and caveats.

## Reproduce

Requirements: [uv](https://docs.astral.sh/uv/), git, Python 3.12 (uv installs it).

```sh
git clone https://github.com/jeremiahdillon/cache-register
cd cache-register
make setup          # installs dependencies and the pre-commit guard
cp .env.example .env   # then fill in the keys you have
make status         # shows which keys are configured (never their values)
make check          # guard + lint + tests
```

Keys are needed only for the sources you use; `.env.example` lists them and where to get
them. You can also keep them outside the repo and point `CACHEREG_SECRETS_FILE` at that file.

## Licenses

| What | License |
|---|---|
| Source code | [Apache-2.0](LICENSE) |
| Charts, text, documentation, curated datasets | [CC BY 4.0](LICENSE-content) |
| Third-party data | Each source's own terms — see `src/cachereg/sources/<id>/SOURCE.md`. Not covered by either license above. |

Charts credit their data sources in the footer, as each source requires.

## Security

Secrets, downloaded data and machine-specific details are blocked from commits by a local
hook and, authoritatively, by CI. See [SECURITY.md](SECURITY.md).

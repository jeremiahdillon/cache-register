# Cache Register

**Receipts for the AI economy.** Reproducible analysis of public AI-market data — token
usage, model prices, benchmarks, business adoption and the capital behind it — turned into
charts and videos. Every published visual links back to the exact code that made it.

> **Status:** early. Twelve sources across eight families (OpenRouter, LiteLLM prices, Epoch AI, SEC
> EDGAR, Census BTOS, Ramp AI Index, Vercel AI Gateway, curated disclosures) and six receipts. The plan
> is in [`docs/PLAN.md`](docs/PLAN.md).
>
> | Receipt | Short link | Finding |
> |---|---|---|
> | [`openrouter-wallet-share`](receipts/openrouter-wallet-share/) | [cacheregister.dev/openrouter-wallet-share](https://cacheregister.dev/openrouter-wallet-share) | Who gets paid on OpenRouter: Anthropic's share of estimated weekly spend fell from 93% (week of Jan 6, 2025) to 29% (week of Sep 21, 2026) as Chinese labs and OpenAI rose. |
> | [`open-middle`](receipts/open-middle/) | [cacheregister.dev/open-middle](https://cacheregister.dev/open-middle) | Mid-size open-weight models (100B–1T parameters) accounted for 74% of OpenRouter's token growth from Mar 30 to Oct 4, 2026. |
> | [`china-spend-share`](receipts/china-spend-share/) | [cacheregister.dev/china-spend-share](https://cacheregister.dev/china-spend-share) | Among Anthropic, OpenAI and Chinese labs, estimated OpenRouter spend was level in the week of Sep 28, 2026: OpenAI 35%, Chinese labs 33%, Anthropic 32%. |
> | [`china-token-share`](receipts/china-token-share/) | [cacheregister.dev/china-token-share](https://cacheregister.dev/china-token-share) | Chinese labs served 78% of those three groups' OpenRouter tokens in the week of Sep 28, 2026, up from 10% in the week of Jan 6, 2025. |
> | [`opus-tenth-life`](receipts/opus-tenth-life/) | [cacheregister.dev/opus-tenth-life](https://cacheregister.dev/opus-tenth-life) | Claude Opus 4, 4.5 and 4.6 were each matched in capability (Epoch ECI) at a tenth of their list price after 5.8 months on average. |
> | [`source-matters`](receipts/source-matters/) | [cacheregister.dev/source-matters](https://cacheregister.dev/source-matters) | Anthropic's share of spend in the four weeks to Sep 27, 2026 was 53% on Ramp, 47% on Vercel AI Gateway and 28% on OpenRouter (of tokens: 42%, 11% and 4%); the sources also disagreed on its direction for most of 2025. |

## How it works

```
sources (APIs) ──fetch──▶ data/raw ──build──▶ staged ──▶ marts ──▶ explore/ · receipts/ ──render──▶ PNG · MP4 · HTML
                         (gitignored; never committed)                   (committed code; receipts also commit their visuals)
```

- **Data is not in this repo.** Most sources' terms don't allow redistribution, so you
  download your own copy with your own API keys. Code, configuration, model-name mappings and
  a small curated dataset of public disclosures are committed.
- **Reproducibility is stated honestly per source.** Some sources keep full history (anyone
  gets identical numbers); some revise past values; some only expose the current state, so
  history exists only from the day you start collecting. See `docs/PLAN.md` §4.4.
- **Explorations** live in `explore/` (dated, scratch). Work worth showing is promoted to
  **`receipts/<topic>/`**: each has a README (question, findings, method, caveats), its code, and
  its rendered visuals in `output/`. Every visual links back to `cacheregister.dev/<topic>`.
- **Reproduce one receipt on its own:** `cachereg reproduce receipts/<topic>` fetches only that
  receipt's sources, builds only what it needs and compares the result with the committed run.

## Reproduce

Requirements: [uv](https://docs.astral.sh/uv/), git, Python 3.12 (uv installs it).

```sh
git clone https://github.com/jeremiahdillon/cache-register
cd cache-register
make setup          # installs dependencies and the pre-commit guard
cp .env.example .env   # then fill in the keys you have
make status         # per source: cadence, last fetch, next due, last error; which keys are set (never values)
make check          # guard + lint + tests
```

Keys are needed only for the sources you use; `.env.example` lists them and where to get
them. You can also keep them outside the repo and point `CACHEREG_SECRETS_FILE` at that file.

On a Mac, `make install-schedule` writes a launchd agent that runs `cachereg fetch --due` daily
(only sources whose cadence has passed) and prints the `launchctl` command to load it.

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

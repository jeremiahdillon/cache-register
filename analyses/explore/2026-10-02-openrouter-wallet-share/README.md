# Who gets paid on OpenRouter?

*Explore · started 2026-10-02 · status: first draft (Phase 0.5 vertical slice)*

## Question
How is estimated developer spend on OpenRouter split between model makers, and how fast is
it shifting?

## Finding (as of 2026-10-02)
Anthropic's share of estimated weekly spend on OpenRouter's top-50 models fell from **69%**
(week of Jun 29, 2026) to **32%** (week of Sep 21) — a near three-way tie with **OpenAI (31%)**
and **Chinese labs combined (31%)**: Z.ai, Moonshot AI, Tencent, DeepSeek, Xiaomi and others.
Total estimated weekly spend on these models rose from ~$118M to ~$161M (+36%) over the same
period, so Anthropic's decline is in *share* while the pie grew.

## Data
- `openrouter_rankings` — daily tokens for the top-50 models (CC BY 4.0, OpenRouter).
- `openrouter_models` — current list prices (snapshot).
- Marts: `or_vendor_weekly`, `dim_vendor_alias` (see `src/cachereg/marts/010_openrouter_usage.sql`).

## Method
1. Daily tokens per model × blended list price (80% input / 20% output) = estimated spend.
   `:free` variants count as $0. Models without a current price are excluded and measured.
2. Model → developer via `config/entities/vendors.yaml` (author prefix of the permaslug).
   "Chinese labs" = developers headquartered in China.
3. Weekly (ISO weeks, Monday start), last 13 complete weeks; share = developer spend / all
   priced top-50 spend that week.
4. Weeks where more than 3% of tokens couldn't be priced are shaded (Aug 17 and Aug 24: ~10%,
   almost entirely an anonymous pre-release model, `stealth/ox-alpha`, which has no list price).

## Caveats
- **Estimate, not revenue.** List prices; no negotiated discounts; **prompt caching ignored**,
  which overstates spend most for heavily cached coding traffic — so Anthropic's share is
  likely an upper bound.
- **Tokens are counted by each provider's own tokenizer** and aren't strictly comparable.
- **OpenRouter only** — third-party developer routing, not the whole market.
- Top-50 models per day only (the remaining ~4% of tokens has no per-model price).
- One current price snapshot is used for all weeks. Price history (LiteLLM, Phase 2) will
  replace this and lets the window extend back before July 2026.

## Reproduce
```sh
cachereg fetch openrouter_rankings && cachereg fetch openrouter_models
cachereg build
cachereg render analyses/explore/2026-10-02-openrouter-wallet-share
```

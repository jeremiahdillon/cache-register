# Chinese labs' share of OpenRouter tokens

*Receipt · [cacheregister.dev/china-token-share](https://cacheregister.dev/china-token-share) · data as of 2026-10-07 ·
promoted from [`explore/2026-10-07-china-token-share`](../../explore/2026-10-07-china-token-share/) · spend companion:
[`china-spend-share`](../china-spend-share/)*

## Question
The same chart as the spend receipt, measured in tokens instead of estimated spend: among Anthropic, OpenAI and
Chinese labs, how are OpenRouter's tokens split, first two ways and then with Chinese labs put back in?

## Finding (data to the week of Sep 28, 2026)
- **Chinese labs served 78% of the three groups' tokens** in the week of Sep 28 (OpenAI 17%, Anthropic 6%), up from
  10% in the week of Jan 6, 2025 and 46% in the week of Jan 5, 2026.
- **More than Anthropic and OpenAI combined every week since the week of Feb 2, 2026** (35 weeks), and earlier in
  the weeks of Aug 4, Dec 22 and Dec 29, 2025.
- **Two-way, OpenAI leads on tokens.** Anthropic had 25% of Anthropic + OpenAI tokens in the week of Sep 28, while
  it had 47% of their estimated spend: Anthropic's tokens cost more.
- **Tokens and spend tell different stories.** Chinese labs are 78% of the three groups' tokens but 33% of their
  estimated spend, because their models are much cheaper per token.

## Visuals
In [`output/`](output/) (`output/manifest.json` records the data versions and hashes; `data.json` holds the
weekly figures behind the visuals). Same visuals as the
spend companion; `charts.py` is identical in both folders:
- `push` — video (`x_video`, `linkedin_video`): the two-way token split, then the Chinese-labs band grows in
  between OpenAI and Anthropic while the stack stays at 100%.
- `stack` — still of the final frame (`x_png`, `linkedin_png`).
- `push-bars` / `stack-bars` — the same video and still as stacked weekly bars: one bar per week with that week's
  actual (unsmoothed) shares. The sweep reveals one bar at a time.

## Data
- `openrouter_rankings` — daily tokens for the top-50 models plus an `other` row (CC BY 4.0, OpenRouter).
- Marts: `005_openrouter_tokens` (`or_rankings_daily`); developers via `dim_vendor_alias` (author prefix of the
  permaslug, from `config/entities/vendors.yaml`). "Chinese labs" = every developer with `hq: CN`, as in the
  spend companion.

## Method
1. Tokens per developer per week, as reported by OpenRouter. `:free` variants are included under their developer.
   Embedding models are excluded (as in `open-middle`).
2. Monday–Sunday weeks from Jan 6, 2025 (91 weeks). OpenRouter's data has no rows for Jun 15 and Jul 15, 2025, so
   the weeks of Jun 9 and Jul 14, 2025 are computed from their other six days: these are shares, and a missing
   day removes traffic from all three groups. A week counts with 6 days only if a full week follows it, so a
   partial week at the end of the data never does.
3. Share = group tokens ÷ (Anthropic + OpenAI + Chinese labs) tokens that week.
4. Left out of the denominator: together, **43% of all tokens in an average week** (mean of the 91 weekly shares;
   the chart's note), 41% in the week of Sep 28. Of which:
   - **Google and other named developers:** 14% of attributed tokens in the week of Sep 28 (median 40% a week, peak
     67% in the week of Nov 24, 2025).
   - **Tokens not attributed to a developer:** OpenRouter's `other` row (models outside the daily top 50) and
     models under stealth names: 31% of all tokens in the week of Sep 28 (median 8% a week). That week is the
     highest because of one stealth model, `stealth/space-bunny-alpha` (38.7T tokens that week, 13.9T the week
     before), more than Anthropic and OpenAI combined. Its lab is unknown.
5. Display: the area visuals smooth each group's weekly tokens 1-2-1 over 3 weeks, then renormalise to 100% per
   week; their note says so. The bar visuals are unsmoothed. Findings use raw weekly figures.

## Caveats
- **Tokens, not spend or revenue.** A token of a cheap model and a token of a frontier model count the same; see
  the spend receipt for estimated spend.
- **Three-way denominator,** so these shares are higher than shares of all OpenRouter tokens.
- **The stealth model could move the latest weeks.** If `space-bunny-alpha` belongs to one of the three groups, its
  share in the weeks of Sep 21 and Sep 28 is understated by up to ~38.7T tokens a week. It is free pre-release
  traffic, so it has no effect on the spend receipt.
- **OpenRouter only.** A routing marketplace with free tiers; it over-represents cheap, free and open models compared
  with first-party APIs, subscriptions and enterprise contracts.
- **Free variants are included**, so promotional free launches count in full.
- **Tokens are counted by each provider's own tokenizer**, so volumes are not strictly comparable across labs.
- The `other` row may contain Chinese-lab models outside the daily top 50.

## Reproduce
`uv run cachereg reproduce receipts/china-token-share` (after `cachereg fetch` of openrouter_rankings and `cachereg build`). Token counts
come from OpenRouter's rankings dataset, which OpenRouter may revise in place, so a later fetch can differ.

Author: re-render the committed visuals with `cachereg render receipts/china-token-share`.

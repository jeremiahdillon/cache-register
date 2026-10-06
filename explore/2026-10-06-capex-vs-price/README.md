# Capex vs price collapse

*Exploration · started 2026-10-06 · design: [`docs/plans/2026-10-06-capex-vs-price.md`](../../docs/plans/2026-10-06-capex-vs-price.md)*

## Question
While the largest cloud companies' capital spending climbs, how fast is the price of a fixed level of
model capability falling over the same quarters? (PLAN §10, starter analysis (b).) The two series are
shown side by side; the analysis makes no causal claim.

## Finding (capex filings to 2026-09-11, Epoch vintage of 2026-10-06, prices to 2026-10-05)
- **Hyperscaler capex grew 2.3× from 2025 Q1 to 2026 Q2.** Quarterly cash capex of Microsoft, Alphabet, Amazon,
  Meta and Oracle rose from $78bn (2025 Q1) to $182bn (2026 Q2), every quarter higher than the last
  ($97bn, $106bn, $131bn, $148bn in between). 2026 Q3 is incomplete: only Oracle has reported ($28.5bn).
- **Over the same quarters, o1-level capability (ECI ≥ 140) got 11× cheaper per token**: quarterly
  median of the cheapest blended list price $1.76 → $0.16 per million tokens. Claude 3.5 Sonnet-level
  (ECI ≥ 130) fell 4.4× ($0.16 → $0.036). GPT-5-level (ECI ≥ 150) was not reached until 2025 Q3; from
  there to 2026 Q2 it fell 3× ($3.00 → $1.00), and to $0.088 by October.
- **The cheapest prices mostly come from outside the five.** Since 2025 Q1, a capex-group company (only
  Google, in practice) set the o1-level floor on 9% of days; Alibaba's Qwen models set it on 38%, xAI on
  21%, OpenAI on 20% and DeepSeek on 13%. Google set the GPT-5-level floor on 56% of days (Gemini 3
  Flash) and the Claude 3.5 Sonnet-level floor on 21% (Gemini 2.0 Flash); OpenAI's gpt-oss-20b and GPT-5
  nano set it on 64%.

## Method
- **Capex** (`030_capex`): cash paid for property and equipment from 10-K/10-Q XBRL facts, selected by
  filing date on or before as-of (restatements replace earlier values from their filing date).
  Year-to-date facts are differenced into quarters (Q4 = full year − nine months; a restatement of
  only one year-to-date figure lands entirely in that quarter), and each fiscal
  quarter is placed in the calendar quarter containing its midpoint (Oracle's June–August quarter is
  Q3). The group is `hyperscaler` in `config/entities/tickers.yaml`. Only quarters in which all five
  have reported are compared or drawn.
- **Price** (`040_eci_model_prices`, the same definition as the cost-of-intelligence exploration):
  80% input + 20% output list price, the cheapest of a model's mapped LiteLLM keys, trailing 28-day
  median per model; the cheapest such price among models with ECI ≥ level on each day, counted from a
  model's first LiteLLM listing.
- **Comparison:** for each quarter, the median of the daily cheapest price; fold change between the first
  and last complete capex quarter (2025 Q1 and 2026 Q2). The median is used because a step inside a
  quarter makes the mean depend on a few days (see below).
- **Who sets the price:** the organization of the cheapest model each day (Epoch's `Organization`), and
  whether its vendor id (from the model id) is one of the capex group's `vendor` ids in
  `tickers.yaml` (Microsoft, Google, Amazon, Meta; Oracle has no models).

### Sensitivity (`story.frames["sensitivity"]`)
One change at a time from the main definition:

| Variant | Capex growth | ECI ≥ 130 fall | ECI ≥ 140 fall |
|---|---|---|---|
| Main (quarterly median price, cash capex, 2025 Q1 → 2026 Q2) | 2.33× | 4.4× | 11× |
| Quarterly mean price | 2.33× | 4.5× | 57× |
| Last-day price of each quarter | 2.33× | 4.4× | 11× |
| Capex including tagged finance-lease additions | 2.32× | 4.4× | 11× |
| Plus CoreWeave (neocloud) | 2.37× | 4.4× | 11× |
| A model qualifies only if its ECI lower CI bound ≥ level | 2.33× | 4.4× | — (no model in 2025 Q1) |
| From 2025 Q2 instead of Q1 | 1.87× | 4.4× | 7.5× |

The mean-price row is inflated by o1 ($24) being the cheapest o1-level model for the first weeks of
2025; the headline uses the median, which matches the quarter-end value.

## Caveats
- **Side by side, not cause and effect.** Most of the cheapest models come from labs outside these five
  companies, several of them open-weight models served by third-party hosts. The capex buys capacity for
  the companies' own clouds and products, of which serving these models is a small part.
- **Company-wide cash capex.** It includes warehouses and logistics (Amazon), offices and devices, not
  only AI data centres; no segment split exists in the standardized facts. Assets acquired under finance
  leases are excluded, though Microsoft and Amazon include them in the capex they present; the tagged
  finance-lease additions add little (Meta stopped tagging them after 2023).
- **Calendar alignment.** Oracle's quarters end in February/May/August/November and are placed by
  midpoint; its quarters are offset by a month from the other four.
- **Price per token, not per task; list prices only** (no caching, batch or volume discounts).
- **ECI is Epoch's current fit**, placed at each model's release; unmapped or late-listed cheap models
  make the price lines an upper bound (see the cost-of-intelligence exploration's coverage table).
- **Short window.** Five quarter-on-quarter steps; LiteLLM's staged price history starts 2025-01-01, so
  the comparison cannot start earlier.

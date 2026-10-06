# Plan: analysis (b) "capex vs price collapse" (exploration)

Status: EXPLORATION BUILT · 2026-10-06

Outcome: `explore/2026-10-06-capex-vs-price/` renders `x_png`, `linkedin_png` and `blog_html`.
Hyperscaler cash capex grew 2.3× from 2025 Q1 to 2026 Q2 while o1-level capability got 11× cheaper
per token (quarterly median). Not promoted.

## Question
PLAN §10 starter analysis (b): EDGAR hyperscaler capex × analysis (a)'s cheapest price of fixed
capability, over the same quarters.

## Design
1. **Data from marts only.** Capex from `030_capex` (`docs/plans/2026-10-06-sec-edgar.md`). (a)'s
   price series moved into mart `040_eci_model_prices` (Epoch + LiteLLM only, no OpenRouter
   dependency), with (a)'s definitions; on the 2026-10-06 data it equals the exploration's own
   computation row for row. The (a) exploration keeps its own code for its sensitivity variants;
   switch it to the mart when it is promoted.
2. **Window:** complete capex quarters (all five reported) from 2025 Q1, the first quarter with
   LiteLLM price history, to the latest complete quarter.
3. **Comparison:** fold change of quarterly capex and of the quarterly **median** of the daily cheapest
   price, first to last quarter of the window. Headline level ECI ≥ 140 (o1-level): the highest level
   reached before the window starts, so it covers every quarter. Sensitivities: mean and quarter-end
   price, finance-lease additions, adding CoreWeave, conservative ECI bound, a later start.
4. **Who sets the price:** organization of each day's cheapest model, flagged when its vendor is one
   of the capex group's (`tickers.yaml` `vendor`).
5. **Visual:** two panels on one time axis, each with one y-axis (no dual axis): capex bars per
   calendar quarter (complete quarters only), and (a)'s step lines on a log price axis, headline level
   in the accent.

Out of scope: an index or ratio combining capex and price into one number (they measure different
things and the price setters are mostly other companies); revenue; promotion and motion.

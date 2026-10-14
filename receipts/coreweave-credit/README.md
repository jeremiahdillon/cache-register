# CoreWeave bond yield vs stock price

*Receipt · [cacheregister.dev/coreweave-credit](https://cacheregister.dev/coreweave-credit) · data as of 2026-10-14
(FINRA TRACE to 2026-10-13; Yahoo closes to 2026-10-14) · promoted from
[`explore/2026-10-14-coreweave-credit`](../../explore/2026-10-14-coreweave-credit/) · prompted by CNBC, "CoreWeave
shares tumble as bond yields near 15% on concern about AI borrowing binge" (2026-10-14), which quoted FactSet
yields of 14.8% (9.625% notes due 2032) and 14.9% (9.75% notes due 2031)*

## Question
How far have CoreWeave's borrowing costs in the bond market moved while its stock fell? The chart puts the
daily yield of CoreWeave's highest-yielding senior note next to the daily close of CRWV, on the same dates.

## Findings (FINRA TRACE to 2026-10-13; Yahoo closes to 2026-10-14)
- **The 9.75% notes due October 2031 are CoreWeave's highest-yielding senior notes:** 14.68% on 13 October
  (price 83), against 14.60% on the 9.625% notes due 2032 (price 81), 13.76% on the 9.00% notes due February
  2031 and 13.05% on the 9.25% notes due 2030 (frame `notes_by_yield`). FINRA's figures run ~0.1–0.2 pt
  below the FactSet figures CNBC quoted, with the same ordering.
- **Since the 2031 notes began trading (14 April 2026) their yield rose 5.7 points**, from 9.02% (price
  102.6) to 14.68%. Most of the rise came after June: the yield was 9.22% on 18 June.
- **Over the same span CRWV fell 44%**, from $117.20 to $65.78, including a 15.5% drop on 14 October; its
  peak was $137.98 on 6 May. The stock's fall was not steady: it recovered above $100 several times while
  the yield kept climbing.
- **Every senior note moved, not just one.** On 14 April the 2030 and February 2031 notes yielded 8.63% and
  8.83%; on 13 October 13.05% and 13.76%.

## Visuals
- `panels`: two side-by-side line charts on the same dates (14 April to 14 October 2026), each with its own
  axis: the 2031 notes' yield (left) and CRWV's daily close (right). Start, end and the stock's peak are
  labelled. `x_png` (16:9) has the panels side by side; `linkedin_png` (4:5) stacks them, yield on top, on one
  date axis. A dashed slope from each line's first to last point carries the change (+5.7 pts, −44%).
- Videos (`x_video` 16:9, `linkedin_video` 4:5, ~13 s): the yield line draws, then the stock line; then both
  slopes flash in within 0.2 s as solid white beams, hold while their change labels fade in, and fade into
  the dashed grey guides; a 3 s hold on the final frame, which the PNGs equal. Change labels are placed in
  code clear of the lines, the other labels and the dots, at every size.

## Method
- **Yield:** FINRA's end-of-day summary of TRACE, the yield at the price of each day's last reported trade
  (mart `bond_eod`, source `finra_trace`), 144A notes. Days without a trade have no point. The note is picked
  by `cusip: auto` in `explore.yaml`: the highest yield on the latest date every note traded.
- **Stock:** Yahoo Finance's daily close, split-adjusted, completed sessions only (mart `stock_daily`, source
  `yahoo_prices`).
- **Bond terms** (coupon, maturity) are from CoreWeave's pricing releases; each CUSIP was matched to its
  terms by recomputing FINRA's 13 October yield from its price (within 0.01 pt).

## Caveats
- Two series side by side, each on its own axis; the chart does not claim one drives the other.
- A last-sale yield is one trade's yield, often from a small trade: single days can jump and reverse
  (29 July: 12.20% → 13.52% → 12.03%).
- FINRA's yield is not FactSet's evaluated yield, so the levels differ slightly from those in the CNBC article.
- FINRA's bond data and Yahoo's prices may not be redistributed: the raw data stays local, and nothing
  inlines it (no HTML target, no `data.json`). Both are used for personal, non-commercial analysis.
- Both endpoints are unofficial, so a fetch may fail if either service changes.

## Reproduce
`cachereg reproduce receipts/coreweave-credit` (both sources are disabled on the daily schedule, so
this is the way to refetch them). Both are Latest-only: a refetch can differ from the pinned render if FINRA
revises a day or Yahoo re-adjusts for a split.

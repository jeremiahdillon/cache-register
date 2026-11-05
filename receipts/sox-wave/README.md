# The SOX and its 30 members

*Receipt · [cacheregister.dev/sox-wave](https://cacheregister.dev/sox-wave) · data through the close of 2026-11-05, fetched
2026-11-06 UTC · promoted from [`explore/2026-11-05-sox-members`](../../explore/2026-11-05-sox-members/) · prompted by the
author, as a companion to [`explore/2026-11-05-chip-selloff`](../../explore/2026-11-05-chip-selloff/)*

## Question
How widely did the two-day chip selloff after the 2026 midterms spread within the PHLX Semiconductor Index (SOX)? The
chart follows all 30 members and the index from Tuesday's close (November 3) through Thursday's close (November 5).

## Findings (Yahoo Finance, sessions of 2026-11-04 and 2026-11-05)
- **All 30 members fell over the two days, by 4.7% to 25.6%. The index fell 15.0%.**
- **Thursday did most of the damage.** The index fell 3.1% on Wednesday and 12.2% on Thursday. All 30 members fell on
  Thursday, by 7.4% (Qnity) to 19.6% (Astera Labs); four rose on Wednesday (Qualcomm, Lattice, NXP, AMD).
- **The largest two-day drops:** Credo −25.6%, Micron −23.2%, Astera Labs −23.2%, Marvell −22.3%, Teradyne −21.0%.
- **The smallest two-day drops:** Qualcomm −4.7%, NXP −7.0%, Lattice −7.4%, Qnity −7.4%, Texas Instruments −11.0%.
- **17 members fell more than the index and 13 fell less.** Nvidia (−12.1%), Broadcom (−12.2%) and TSMC (−12.8%) are
  among those that fell less.

## Visual
- `members`: one line per member, in % from Tuesday's close, with a dashed rule at Wednesday's close and a heavy white
  line for the index, drawn on top. Thirty labels do not fit, so the chart names the index, the largest and most
  recognizable members (Nvidia, Broadcom, TSMC, Intel, AMD, Micron, Qualcomm) and the largest drop (Credo), and draws
  the named lines stronger. Micron is also among the largest drops and Qualcomm is the smallest. Every other member is
  a thinner line. Label leaders are grey so that they do not read as data. There is no key or caption. `x_png` is 16:9,
  `linkedin_png` 4:5.
- Videos (`x_video` 16:9, `linkedin_video` 4:5, ~13 s): the members fade in one after another, from the smallest two-day
  drop to the largest, each label with its line; the index then draws across both sessions and its label fades in; a
  5 s hold on the final frame, which the PNGs equal.
- A thin line's width does not show its weight in the index. Nasdaq's methodology is modified market-cap weighting,
  with the top three members capped, so the index line is not a simple average of the lines around it.

## Method
- **Members:** Nasdaq's SOX weighting page for 2026-11-05, supplied by the author as a list of names and symbols,
  without weights. Compared with Nasdaq's report of 2026-05-01, four members changed: Lattice,
  Qnity, SiTime and Tower replaced Nova, Qorvo, Rambus and Skyworks.
- **Cross-check:** a weighted average of the 25 largest members, using the weights of Invesco's PHLX Semiconductor ETF
  (SOXQ) for 2026-11-04 from StockAnalysis, gives −12.26% on Thursday against −12.25% for the index, and −14.89% against
  −14.99% over the two days.
- **Start and end points:** Yahoo's closes (mart `stock_daily`, source `yahoo_prices`), including the index as `^SOX`.
- **Path:** the close of each 5-minute bar from 09:35 to 15:55 (mart `stock_intraday`, source `yahoo_intraday`); each
  session's last bar's end is replaced by the official close. The x axis counts trading minutes, with a short overnight
  gap, not clock time.
- **The footer's "as of 2026-11-06" is the fetch's UTC date.** The chart stops at the November 5 close.

## Caveats
- Two sessions: this shows how far the selloff spread within the index and does not explain it.
- Prices do not show why a stock moved. Same-day coverage ties the selloff to fears that the midterm results will slow
  data center construction, and also cites worries that the AI trade was overextended, hedge fund profit-taking and
  doubts about returns on AI spending. The whole market fell.
- Earnings fall inside this window for many members. Nasdaq's calendar, which may include projected dates, lists 13 of
  the 30 for November 2 to 5: ON Semiconductor, Tower and Lattice (November 2); AMD and Astera Labs (November 3); Arm,
  Qualcomm, Coherent, Qnity, GlobalFoundries and SiTime (November 4); MACOM and Microchip (November 5, Microchip after
  the close). Qualcomm's small two-day drop follows a 5.3% rise on Wednesday and a 9.5% fall on Thursday, which CNBC
  ties to its outlook.
- The index's first prints of a session can lag its members, so its line may be slightly off in the first few minutes
  of each session. Its closes are official.
- Yahoo's data may not be redistributed: the raw data stays local and nothing inlines it (no HTML target, no
  `data.json`). Used for personal, non-commercial analysis. Yahoo serves about 60 days of 5-minute bars, so these
  sessions can be rebuilt later only from our own fetch.

## Reproduce
`cachereg fetch yahoo_prices yahoo_intraday` (both are disabled on the daily schedule), then
`cachereg build --as-of 2026-11-06 --sources yahoo_prices,yahoo_intraday` and
`cachereg render receipts/sox-wave`.

# Chip and data center selloff

*Exploration · started 2026-11-05 · prompted by the author, after same-day coverage of chip stocks falling on fears of
a slower AI buildout. Follows [`receipts/midterm-split`](../../receipts/midterm-split/), which covers the session before.*

## Question
How far did chip and data center supply chain stocks fall after the 2026 midterms? One chart follows the basket and the
S&P 500 from Wednesday's close (November 4) through Thursday's close (November 5). A second starts at Tuesday's close
(November 3), before the results, and gives each session's change.

## Findings (Yahoo Finance, session of 2026-11-05)
- **16 of 17 stocks fell more than the S&P 500 (SPY −4.4%).** Constellation (−2.5%) is the exception.
- **The eight chip stocks fell 9% to 17% (median −10.7%):** Micron −17.5%, AMD −17.3%, Analog Devices −11.1%, TSMC
  −10.8%, Texas Instruments −10.7%, Broadcom −10.4%, ASML −9.3%, Nvidia −9.3%.
- **The nine supply chain stocks fell 2% to 15% (median −9.8%):** Dell −14.9%, Vertiv −14.0%, Quanta Services −12.3%,
  Arista −10.8%, CoreWeave −9.8%, GE Vernova −7.5%, Eaton −7.4%, Vistra −6.2%, Constellation −2.5%.
- **Chip stocks ended at their lows.** All eight closed within about 0.5% of their lowest 5-minute price. CoreWeave recovered
  the most, closing 6.8% above its low.
- **Over two days all 17 fell more than the S&P 500 (SPY −2.8%).** Chip stocks lost 11.0% to 23.2% (median −12.7%) and
  supply chain stocks lost 6.3% to 25.1% (median −18.8%). Vertiv −25.1%, Micron −23.2% and Quanta Services −22.5% lost
  the most; Arista −6.3% and Constellation −9.0% the least.
- **The supply chain fell first, then chips.** On Wednesday, when SPY rose 1.7%, the median supply chain stock fell 9.9%
  and the median chip stock 2.7%. On Thursday the medians were −9.8% and −10.7%, against −4.4% for SPY.
- **Two stocks rose on Wednesday and then fell:** Arista (+5.0%, then −10.8%) and AMD (+1.0%, then −17.3%). Nasdaq's
  calendar lists both for earnings on November 3, so Wednesday's gains may reflect results rather than the election.
- **There is no upside group here.** Of 114 AI-exposed, power and clean energy tickers scanned, five rose: Sunrun
  +12.3%, Albemarle +3.6%, First Solar +0.6%, Duke +0.4%, Southern +0.2%. None is a data center supply chain stock in
  this basket's sense, and Nasdaq's calendar lists all but First Solar for earnings on November 4 or 5.

## Visual
- `session`: one line per stock, in % from Wednesday's close, on one axis. Magenta is chips, orange is the supply chain
  (as on the midterm-split chart), and the S&P 500 is a dimmed white. A short, steep segment of each line crosses the
  overnight gap and the first 5 minutes. Each line is named at its end with its close-to-close change.
  `x_png` is 16:9, `linkedin_png` 4:5.
- `two-day`: the same basket as a continuous path from Tuesday's close through Thursday's close, in % from Tuesday's
  close, with a dashed rule at Wednesday's close. The lines end in a table of each stock's change on Wednesday, on
  Thursday and over the two days, sorted by the two-day change. The session columns compound to the two-day column, so
  they do not add exactly.
- Videos (`x_video` 16:9, `linkedin_video` 4:5, for both visuals): the S&P 500 draws, a caption gives its move and fades away, and it
  dims; the chip stocks draw together, then a caption; the supply chain draws together, then a caption; the key fades
  in once the captions are gone; a 5 s hold on the final frame, which the PNGs equal.

## Method
- **Selection, chips:** the eight largest holdings of the VanEck Semiconductor ETF (SMH) as of 2026-11-04, per
  StockAnalysis, with no regard to how they moved. This brings in analog makers with less AI exposure (Texas
  Instruments, Analog Devices). SMH holds about 26 names, so this is the top of the index.
- **Selection, supply chain:** the author's "data center supply chain" label from midterm-split. Its five stocks stay
  (Vistra, Vertiv, Quanta Services, CoreWeave, GE Vernova), and one large name was added per under-represented layer:
  Constellation (power), Eaton (electrical equipment), Arista (networking), Dell (AI servers). These additions are a
  judgment call, made knowing the day's moves, though they include the basket's smallest drop.
- **No hyperscalers,** at the author's request. They fell less than the S&P on the day: Amazon −2.2%, Alphabet −2.2%,
  Microsoft −3.6%, Meta −4.0%. Oracle fell more (−6.9%).
- **Start and end points:** Yahoo's closes (mart `stock_daily`, source `yahoo_prices`). Yahoo served the November 5 daily
  bar empty after the close, so stage took that close from the same response's `regularMarketPrice`. It matches the
  daily bars Yahoo served earlier the same evening for every stock in the basket.
- **Path:** the close of each 5-minute bar from 09:35 to 15:55 (mart `stock_intraday`, source `yahoo_intraday`); the
  last bar's end is replaced by the official close. The two-day path rebases Thursday's bars to Tuesday's close and
  draws the overnight gap as a short, steep segment; the x axis counts trading minutes, not clock time.
- **S&P 500:** SPY, as on midterm-split. SPY fell 4.41%; CNBC reports the index down 4.36%.
- **The footer's "as of 2026-11-06" is the fetch's UTC date,** which fell on the 6th. The chart stops at the November 5 close.

## Caveats
- Two sessions, with part of the basket chosen after the move: this illustrates the selloff and does not measure it.
- The supply chain's larger two-day drop partly reflects selection: its five original stocks were picked on Wednesday
  because they fell, while the chip stocks were picked by ETF weight.
- Prices do not show why a stock moved. CNBC and Yahoo tie the selloff to fears that the midterm results will slow data
  center construction. Coverage also cites worries that the AI trade was overextended, hedge fund profit-taking, doubts
  about returns on AI spending and tighter financing for smaller firms. The whole market fell (Dow −3.4%, Russell 2000
  −4.5%).
- Nasdaq's earnings calendar may include projected dates. It lists none of the 17 for November 4 or 5, and AMD and
  Arista for November 3, so Thursday would be their second session after results. Vistra is listed for the morning of
  November 6.
- A Bloomberg report, relayed by Stock Titan, described a near halt at a Micron plant in Taiwan, which Micron disputes.
  This may have added to Micron's drop.
- Yahoo's data may not be redistributed: the raw data stays local and nothing inlines it (no HTML target, no
  `data.json`). Used for personal, non-commercial analysis. Yahoo serves about 60 days of 5-minute bars, so this
  session can be rebuilt later only from our own fetch.

## Reproduce
`cachereg fetch yahoo_prices yahoo_intraday` (both are disabled on the daily schedule), then
`cachereg build --as-of 2026-11-06 --sources yahoo_prices,yahoo_intraday` and
`cachereg render explore/2026-11-05-chip-selloff --as-of 2026-11-06`.

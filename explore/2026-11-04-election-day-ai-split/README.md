# Election-day split in AI stocks

*Exploration · started 2026-11-04 · short link reserved: cacheregister.dev/midterm-split · prompted by the author, after same-day coverage of hyperscalers rising and
data center stocks falling on the midterm results*

## Question
How did the AI trade split the day after the 2026 midterms? The chart follows three hyperscalers that rose, five
data center supply chain stocks that fell and the S&P 500 from Tuesday's close (November 3) through Wednesday's
close (November 4).

## Findings (Yahoo Finance, session of 2026-11-04)
- **Three hyperscalers beat the S&P 500 (SPY +1.7%):** Microsoft +6.7%, Amazon +6.1%, Alphabet +3.2%. All three
  stayed above the S&P all session.
- **Five supply chain stocks fell 9% to 14% on a day the market rose:** Vistra −13.8%, Vertiv −12.9%, Quanta Services −11.7%,
  CoreWeave −9.9%, GE Vernova −9.3%.
- **The groups separated within minutes and did not cross all day.** Five minutes in, every stock that ended
  lower was already down at least 6%.
- **Tuesday's rally makes Wednesday's drops look larger.** Every stock that fell had risen 3.7% to 7.2% on
  Tuesday. Over the two days, GE Vernova and CoreWeave are down about 3.4%, Quanta 6.6%, Vertiv 8.3% and Vistra
  10.6% (frame `summary`).

## Visual
- `session`: one line per stock, in % from Tuesday's close, on one axis. Blue rose, orange fell, and the
  S&P 500 is a dimmed white. A short, steep segment of each line crosses the overnight gap and the first 5
  minutes. Each line is named at its end with its close-to-close change. `x_png` is 16:9, `linkedin_png` 4:5.
- Videos (`x_video` 16:9, `linkedin_video` 4:5, ~27 s): the S&P 500 draws, a caption gives its move and fades away,
  and it dims; the hyperscalers draw together, then a caption; the supply chain stocks draw together, then a
  caption; the key fades in once the captions are gone; a 5 s hold on the final frame, which the PNGs equal.
- The hyperscaler and supply chain captions report investors' reasons as given in same-day coverage (Reuters, Seeking
  Alpha, Yahoo Finance). They are one reading of the move: coverage also credits more valuable existing data
  centers and rules that favor incumbents, and prices alone do not show why a stock moved.

## Method
- **Start and end points:** Yahoo's official daily closes (mart `stock_daily`, source `yahoo_prices`).
- **Path:** the close of each 5-minute bar from 09:35 to 15:55 (mart `stock_intraday`, source `yahoo_intraday`);
  the last bar's end is replaced by the official close.
- **The line starts at 09:35, not 09:30.** The first bar's open is a single print and is not reliable here:
  GE Vernova's is −4.5% while Yahoo's daily open is −6.9%, and Quanta prints −4.6% and stands at −11.5% five
  minutes later.
- **S&P 500:** SPY, the ETF that tracks the index, because the index's own first prints lag at the open. SPY rose
  1.65%; Reuters reports the index up 1.6%.
- **Selection:** the author's choice, from a wider basket of about 60 AI-exposed tickers checked the same day.
  "Data center supply chain" is the author's label for power (Vistra), equipment and construction (Vertiv, GE
  Vernova, Quanta) and rented compute (CoreWeave). Left out as stock-specific or off-thesis: Hut 8 and Cipher
  (earnings listed around the date on Nasdaq's calendar), Arista and AMD (likewise), Apple (not a data center
  story), solar names (a separate clean energy trade).
- **Not every hyperscaler rose with these three:** Meta (+1.4%) lagged the S&P and Oracle (−1.9%) fell. Data center
  landlords Equinix (+3.9%) and Digital Realty (+2.6%) also beat the S&P, but only from early afternoon.

## Caveats
- One session, with stocks chosen after the move: this illustrates the split and does not measure it.
- Prices do not show why a stock moved. Tying the split to the election follows same-day press coverage, which
  emphasises the Texas governor's race and local data center votes as well as Congress.
- Other forces moved these stocks that day: the Dow rose 3%, consumer discretionary (Amazon's sector) 4.3%, and
  energy fell 4.8% as crude dropped, which may weigh on Vistra.
- Nasdaq's earnings calendar may include projected dates, and none of the eight charted stocks is listed as
  reporting on November 3 or 4. Vistra was due to report later in the week, per TIKR.
- Yahoo's data may not be redistributed: the raw data stays local and nothing inlines it (no HTML target, no
  `data.json`). Used for personal, non-commercial analysis. Yahoo serves about 60 days of 5-minute bars, so this
  session can be rebuilt later only from our own fetch.

## Reproduce
`cachereg fetch yahoo_prices yahoo_intraday` (both are disabled on the daily schedule), then
`cachereg build --sources yahoo_prices,yahoo_intraday` and
`cachereg render explore/2026-11-04-election-day-ai-split --as-of 2026-11-04`.

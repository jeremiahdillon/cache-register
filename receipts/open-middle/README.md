# The open middle

*Receipt · [cacheregister.dev/open-middle](https://cacheregister.dev/open-middle) · data as of 2026-10-04*

## Question
Reflection AI announced Beam on 2026-10-05: an open-weight model with 501B total / 23B active parameters.
Reflection has promised Apache 2.0 weights for October and compares Beam to GLM 5.2. How much of OpenRouter's
token volume goes to the class Beam is entering, **mid-size open-weight models**, and how fast is that class
growing?

## Finding (data to 2026-10-04)
- **Mid-size open-weight models accounted for 3 out of every 4 new tokens in the past 6 months**, or 74.3%
  of the growth in weekly tokens. Average weekly tokens rose from 20.4T (4 weeks from Mar 30) to 119.6T
  (4 weeks to Oct 4). Over the same period mid-size open went from 6.5T to 80.2T.
- In the week of Sep 28 mid-size open models served **78.1T tokens**. That is more than twice every closed
  model combined: OpenAI 16.0T, Other closed 6.5T, Anthropic 5.5T, Google 5.1T. Flagship open models served
  4.3T and small open models 1.7T.
- That week's largest mid-size models were DeepSeek V4.1 Flash (25.6T), GLM-5.3 Flash (9.7T), MiMo-V2.6-Flash
  (9.6T), Tencent HY4-preview (6.5T) and DeepSeek V4 Flash (6.0T).
- Beam (501B) would sit in the middle of this band.

## Who drove the growth
Each model family's share of the rise in weekly tokens, comparing the 4 weeks from Mar 30 with the 4 weeks to
Oct 4 (total rise: 99T a week).

| Model family | Band | Share of growth |
|---|---|---|
| DeepSeek V4 / V4.1 Flash | mid-size open | 29% |
| Tencent HY3 / HY4-preview | mid-size open | 15% |
| GPT Luna / Terra | closed (OpenAI) | 13% |
| GLM-5.3 Flash | mid-size open | 13% |
| MiMo-V2.5 / V2.6-Flash | mid-size open | 8% |
| Nemotron 3 Ultra | mid-size open | 5% |
| GLM-5.x | mid-size open | 3% |
| GPT Sol / Astra, Gemini, DeepSeek V4 Pro | closed / flagship open | 1–2% each |
| Opus, Fable, Sonnet, Kimi | closed / flagship open | under 1% each |
| MiniMax, MiMo Pro, StepFun | open | declined |

- **Growth is concentrated.** Five mid-size open families supplied about 70% of the growth, and all of them
  launched or relaunched in the window.
- **Flagships didn't drive growth.** Flagship open models (1T+ parameters: Kimi, DeepSeek V4 Pro, MiMo Pro)
  added about 2% between them. The closed labs' flagship models, Opus, Fable, Sol and Astra, added about 5%.
- **One closed exception.** OpenAI's smaller models (GPT-5.6 Luna and Terra, GPT-6 Luna) took 13% of the
  growth, as much as GLM-5.3 Flash. Mid-size open is the large majority, but not the only growth story.
- **The band turns over fast.** MiniMax M3 grew, but the M2 versions declined by more. StepFun's Flash models
  faded as newer mid-size models arrived.

The visuals (stacked-area video and stills for X and LinkedIn) and `data.json` are in [`output/`](output/).

## Data
- `openrouter_rankings`: daily tokens for the top 50 models plus an `other` row (CC BY 4.0, OpenRouter).
- [`tiers.yaml`](tiers.yaml): hand-curated facts for every model with real volume. Each entry records weight
  status (published, or announced by the lab) and total and active parameters, checked against Hugging Face
  model cards and lab posts on 2026-10-05. Closed models record which band they go in. Unclear cases carry a
  note.

## Method
- **Weeks:** complete Monday–Sunday weeks from 2025-01-06. `:free` variants are merged with their paid model.
- **Bands:** open-weight models are banded by total parameters:
  - **small:** under 100B;
  - **mid-size:** 100B to under 1T;
  - **flagship:** 1T and above.
- **Closed models** are banded by developer: Anthropic, OpenAI, Google, and other closed (which includes xAI,
  Meta's Muse Spark, closed Qwen/GLM variants and Upstage).
- **Long tail:** models not in `tiers.yaml` total 2.2T (0.1% of shown tokens). They go to their lab's band
  if the lab is closed, and otherwise to small open. Closed or mid-size exceptions are listed explicitly.
- **Excluded:**
  - models served under stealth names (`stealth/*`, `openrouter/*`), whether revealed later or not
    (101T). These are free pre-release testing, not production use.
  - OpenRouter's `other` row (134T), which does not attribute tokens to a model or lab.
  - embedding models (3.5T).
  - Together, stealth and `other` are 235T, 12% of all tokens, as the chart's note says.
- **Growth share** = change in mid-size open's average weekly tokens ÷ change in the total. The averages are
  the 4 weeks from Mar 30 and the 4 weeks to Oct 4 (`growth_weeks: 26`). It is computed from raw weekly data.
- **Display smoothing:** a 1-2-1 weighted 3-week average, (previous + 2 × this + next) / 4, with end weeks at
  (2 × end + neighbour) / 3, drawn with monotone interpolation.

### Why a size band
The first exploration used a capability rule: open models scoring at least half of the best open model on a
public benchmark index, re-judged weekly. It tracked this size band closely (weekly share correlation 0.97).
We chose the size band because:
- one sentence explains it;
- anyone can check it against a model card;
- models don't fall out of the band as the frontier moves;
- it doesn't depend on third-party benchmark data.

## Caveats
- **Lens:** OpenRouter is a developer marketplace with free tiers. It over-represents cheap and open-model
  traffic compared with first-party APIs and enterprise contracts.
- **Size is a proxy for the class, not a capability score.** Older or weaker mid-size models stay in the band
  (e.g. Llama 4 Maverick, Nemotron 3 Ultra), but they carry little volume.
- **Tokens:** each model counts tokens with its own tokenizer, so volumes aren't strictly comparable.
- **Free tiers are kept** under real model names (e.g. MiMo-V2-Pro's free launch week in late March 2026, the
  bump in "other closed").
- **Judgement calls:**
  - Inkling (975B) counts as mid-size.
  - Muse Spark counts as closed: Meta has promised an open version but not said which.
  - Ling-3.1 Flash, which entered the top 50 on 2026-10-02, is assumed to match Ling-3.0 Flash (124B, open).
    That is unverified.
- **Missing days:** OpenRouter's data is missing one day in each of the weeks of 2025-06-09 and 2025-07-14
  (4.0T together). Those weeks are left out and the chart bridges them.

## Reproduce
`uv run cachereg reproduce receipts/open-middle` (after `cachereg fetch openrouter_rankings` and `cachereg build`).

# Mid-size open-weight models on OpenRouter

*Exploration · started 2026-10-05 · **Promoted to [`receipts/open-middle`](../../receipts/open-middle/)**, which is the maintained version (cacheregister.dev/open-middle).*

## Question
Reflection AI announced Beam on 2026-10-05: an open-weight model with 501B total / 23B active parameters,
with Apache 2.0 weights promised for October. Reflection compares it to GLM 5.2. How much of
OpenRouter's token volume goes to the class Beam is entering, **mid-size open-weight models**, and how fast
is it growing?

## Finding (data to 2026-10-04)
- **Three out of every four new tokens in the past 6 months went to mid-size open-weight models.** They
  took 74% of the rise in weekly tokens, comparing the 4 weeks from Mar 30 with the 4 weeks to Oct 4. This excludes
  OpenRouter's 'other' row and models served under stealth names.
- They grew from **~0.04T tokens/week in January 2025 to ~80T a week by late September**. That is more than
  every closed model combined.
- Most of the volume is DeepSeek V4/V4.1 Flash, GLM-5.3 Flash, Tencent HY4-preview and HY3,
  MiMo-V2.5/2.6-Flash, MiniMax M3 and GLM-5.x.

## Method
- **Data:** weekly tokens per model from the `or_rankings_daily` mart (`openrouter_rankings`), for complete
  Monday–Sunday weeks from 2025-01-06.
- **Cleaning:** `:free` variants are merged with their paid model, and embedding models are dropped.
- **Banding:** each model's band comes from `tiers.yaml`, which lists every model with its facts. Open-weight
  models are banded by **total parameters**:
  - **small:** under 100B;
  - **mid-size:** 100B to under 1T;
  - **flagship:** 1T and above.
- **Open weights** means the weights are published, or the lab has announced it will publish them. This was
  checked against Hugging Face and lab posts on 2026-10-05.
- **Closed models** are banded by developer: Anthropic, OpenAI, Google, and other closed (which includes xAI).
- **Excluded:**
  - every model served under a stealth name (`stealth/*`, `openrouter/*`), whether revealed later or not.
    These are free pre-release test traffic, 62T tokens in the window.
  - OpenRouter's `other` row (everything outside the daily top 50, 8% of the latest week). Set
    `show_unattributed: true` to show it as a band.

**Long tail:** models not listed in `tiers.yaml` (<0.2% of tokens) go to their lab's band if the lab is
closed (Anthropic, OpenAI, Google, xAI, Amazon, Cohere, …), and otherwise to small open. Closed or mid-size
exceptions (e.g. Muse Spark 1.1/1.2, Qwen Max/Plus, DeepSeek V3 base) are listed explicitly. Embedding models
are dropped by name.

**Display smoothing:** the charts use a 1-2-1 weighted 3-week average, (previous + 2 × this + next) / 4,
with end weeks at (2 × end + neighbour) / 3, drawn with monotone interpolation. The growth share is computed
from the raw weekly data.

**Growth share** = (change in mid-size open's 4-week average weekly tokens) ÷ (change in the total), with the
window set in `explore.yaml` (`growth_weeks: 26`). The headline uses the total including unattributed tokens
when that band is shown (`show_unattributed: true`), and excludes them otherwise.

### Earlier draft: capability-based tier
The first pass defined a capability-based "Beam-class": open models scoring at least half of the open
frontier's Artificial Analysis Intelligence Index lift, re-judged each week. We replaced it with the size band
because:
- one sentence explains it;
- the boundaries are stable, since models don't fall out of the band as the frontier moves;
- it doesn't depend on publishing third-party benchmark data.

The two track each other closely (weekly share correlation 0.97). The size band runs a little higher (Q3 2026:
61% vs 52% of all tokens), because it keeps older mid-size models. The AA scores remain in `tiers.yaml` for
reference only.

## Visuals
- `push-together` (X 16:9, LinkedIn 4:5, 12 s):
  1. a fast (2.5 s) left-to-right sweep of the closed bands, with the y-axis capped at the closed peak;
  2. a 1.5 s beat;
  3. a 5 s push: the open bands rise from the x-axis (small open on the axis, then mid-size, then flagship)
     and lift the closed bands, with a slow-start, long-settle ease, while the axis expands to fit;
  4. a 3 s hold.
  Greys follow one lightness ramp: other closed (top) is darkest, then lightest to darkest going down from
  Anthropic. Labels stay at the right edge and blend between two solved layouts, so they never jump.
  In-between gridlines fade out during the push.
- `stack`: the final frame as a still.

## Caveats
- **Lens:** OpenRouter is a developer marketplace with free tiers. It over-represents cheap and open-model
  traffic compared with first-party APIs.
- **Tokens:** each model counts tokens with its own tokenizer, so volumes aren't strictly comparable.
- **Size is a proxy:** the band measures size, not capability. Older or weaker mid-size models stay in the band
  (e.g. Llama 4 Maverick, Nemotron 3 Ultra), but they carry little volume.
- **Free launch traffic is kept.** Only stealth names are dropped, so free promo weeks remain under real names
  (e.g. MiMo-V2-Pro's launch spike in late March 2026, ~10T in 'other closed').
- **Near the 1T line:** Inkling (975B) counts as mid-size. Kimi K-series, DeepSeek V4 Pro (1.6T), Qwen3.8-Max
  and MiMo Pro count as flagship.
- **Judgement calls on weight status:**
  - Muse Spark is closed: Meta has promised an open version but not said which.
  - Ling-3.0 Flash Fin/Santé are closed: they are API-only tunes.

## Reproduce
`uv run cachereg render explore/2026-10-05-beam-class-share` (after `cachereg fetch` and `cachereg build`).
Outputs go to `outputs/2026-10-05-beam-class-share/<as_of>/`.

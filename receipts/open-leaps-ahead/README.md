# Open weights lead Terminal-Bench

*Receipt · cacheregister.dev/open-leaps-ahead · promoted from
[`explore/2026-10-23-frontier-by-lab`](../../explore/2026-10-23-frontier-by-lab/) · data as of 2026-10-23 (one
Artificial Analysis snapshot, fetched that day)*

## Question
How does the best open-weight model, from anyone, compare over 2026 with the best models from Anthropic, OpenAI,
Google and Meta on Terminal-Bench 4.0?

## Finding (Artificial Analysis snapshot of 2026-10-23)
- **The best open-weight model leads all four labs.** Kimi K3.1 Pro (Moonshot, released 2026-10-23, weights
  announced) solves 67.2% of tasks. Claude Sonnet 5.5 solves 63.6%, GPT-6 Astra 59.6%, and Gemini 4 Argon and Muse
  Wonder Full 57.1% each.
- **It is the first time in 2026 the open-weight line is on top.** In April DeepSeek V4 Pro drew level with GPT-5.5
  at 14.6% but did not lead. Until 2026-10-22 the best open-weight model was GLM-5.3 at 41.9%, 21.7 points behind
  Anthropic.
- **The open-weight record passed between four model families in 2026**: Qwen, then GLM, DeepSeek, GLM again, and
  Kimi. All come from Chinese labs; no US open-weight model (gpt-oss, Gemma, Llama) set it.

## Visuals
One slide, `terminal-bench`: video for X and LinkedIn (`x_video`, `linkedin_video`, about 18 s), and its final
frame as the stills (`x_png`, `linkedin_png`), in the committed `output/`. `receipt.yaml` pins
`as_of: 2026-10-23`: build with `cachereg build --as-of 2026-10-23 --sources artificial_analysis`, then
`cachereg render receipts/open-leaps-ahead`.
- Step lines from January to October 23, 2026: the four labs in greys (distinct, but telling them apart is not the
  point) and the best open-weight line in the accent, heavier. A dot marks each new record; each line ends in a dot
  labelled with its current model and score; a legend names the lines.
- Motion: empty axes; the four grey lines draw in together, left to right, and their end labels fade in; a pause;
  then the open-weight line draws in. One calendar clock drives every line, so they stay in step: when it passes a
  record, that line's riser grows upward (grey 0.13–0.47 s, taller jumps taking longer) and the new horizontal
  stretch rides up with its tip, so no riser snaps in. The open-weight line draws faster across and climbs slower
  (0.27–0.67 s). At each handover to a new model family its clock pauses while the riser climbs; when the riser
  lands, a ring pulses from the dot, the family's name pops in oversized and settles, and the clock holds 0.8 s.
  Each name fades when the next family's riser lands; the last gives way to the open-weight end label, so the
  final frame and the stills show end labels only. A handover at a score of 0 is not announced.

## Data
- `artificial_analysis`: one snapshot of AA's LLM data API (attribution required, redistribution forbidden, so
  `data.json` and HTML tables are withheld).
- Mart `120_artificial_analysis` (`aa_models`, `aa_evals`): `terminalbench_v4_0` (0–1, plotted as %).

## Method
1. **A line is the best score among models released so far** (AA's release date). It steps up only when beaten;
   ties do not step. Each reasoning-effort variant is its own AA model, so a lab's line takes its best variant.
   Labels drop AA's variant suffix (e.g. "(Max, Default Fallback)").
2. **Labs are AA's creator names**: Anthropic, OpenAI, Google and Meta. Any of their models counts, open or
   closed.
3. **Best open-weight is any creator's best open-weight model.** `open_weights.yaml` holds creator rules and a
   status for each contender. The rules: Anthropic, Amazon, Perplexity and SpaceXAI are closed; OpenAI, Google and
   Meta are closed except gpt-oss, Gemma, Llama and Muse Glimmer. Statuses come from official Hugging Face repos or
   model cards where they exist, otherwise press coverage, checked 2026-10-23. `analysis.py` fails if a model that
   would set the line has no status, so new contenders must be tagged.
4. **The window starts on 2026-01-01**, and each line enters at the record it held then.
5. **Model families** (the names on the open-weight line) are the leading letters of AA's model name (GLM, Qwen,
   DeepSeek, Kimi).

## Caveats
- **Today's scores, placed at past release dates.** AA re-runs models and re-versions its evals, so the lines show
  how models released at each date score now, not what the leaderboard showed then. AA offers no history; our
  snapshots start on 2026-10-23.
- **Terminal-Bench 4.0 is new and hard.** Models from 2025 score near zero on it, so the chart starts in 2026.
- **AA's own runs, with AA's harness.** They differ from labs' self-reported figures: Moonshot reports 65.7% for
  Kimi K3.1 Pro with the Claude Code harness, and 66.4% for Claude Opus 5.5, which AA scores at 59.6%. They also
  differ from the tbench.ai leaderboard, which compares agents.
- **Kimi K3.1 Pro counts as open-weight on announcement** (the author's call). Its weights are promised by
  November 4, 2026 and were not out on 2026-10-23. Without it, the open-weight line ends at GLM-5.3 (41.9%).
- **Open-weight dates are AA release dates**, even where weights came later (GLM-5.3's about 2 weeks after its
  API).
- **Qwen3.8 Max counts as closed**, as AA lists it. Alibaba published a related text-only checkpoint, and some
  trackers count it as open; counted as open it would hold the open-weight record from 2026-08-03 (18.7%) until
  GLM-5.3. Today's standings would not change.
- **Meta's line since April 2026 is its closed Muse models** (Meta Superintelligence Labs), not Llama.
- **A lab's best model may be expensive or slow**; price and speed are not shown.

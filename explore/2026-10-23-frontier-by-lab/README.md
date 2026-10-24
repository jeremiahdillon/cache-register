# Frontier by lab vs the best open-weight model

*Exploration · started 2026-10-23 · data as of 2026-10-23 (one Artificial Analysis snapshot, fetched that day)*

## Question
How do the best models from Anthropic, OpenAI, Google and Meta compare over time with the best open-weight model
from anyone, on the Artificial Analysis Intelligence Index and on Terminal-Bench? Kimi K3.1 Pro (released
2026-10-23, weights announced) prompted the question.

## Finding (Artificial Analysis snapshot of 2026-10-23)
- **Terminal-Bench 4.0: the best open-weight model leads all four labs.** Kimi K3.1 Pro solves 67.2% of tasks,
  against Claude Sonnet 5.5 at 63.6, GPT-6 Astra at 59.6, and Gemini 4 Argon and Muse Wonder Full at 57.1 each. In
  the window it is the first time the open-weight line is on top. In April 2026 DeepSeek V4 Pro drew level with
  GPT-5.5 at 14.6 but never led.
- **Intelligence Index: it is third of the five lines, 2.5 points behind Anthropic.** Claude Opus 5.5 scores 57.6,
  Muse Wonder Full 55.8, Kimi K3.1 Pro 55.1, GPT-6 Astra 52.7 and Gemini 4 Argon 52.6. Across all models AA ranks
  Kimi K3.1 Pro fourth, since Claude Sonnet 5.5 also scores above it, but only each lab's best model is a line here.
- **The gap is the narrowest in the window.** Until 2026-10-22 the best open-weight model (MiMo-V2.6-Pro, 46.3) was
  11.3 points behind the leader. The previous closest was 2.9 points, Kimi K2 Thinking behind OpenAI in November
  2025. The widest was 19.2 points, from 2026-06-09 (Claude Fable 5) until GLM-5.2 a week later.
- **The open-weight lead changes hands often.** It moves between DeepSeek, Moonshot (Kimi), Z AI (GLM), MiniMax
  and Xiaomi (MiMo): 17 records on the Intelligence Index and 5 on Terminal-Bench since January 2025. All of them come from Chinese labs.
  No US open-weight model (gpt-oss, Gemma, Llama) set the record in the window.

## Visuals
Two visuals in `outputs/` (gitignored), each as `x_png`, `linkedin_png` and `blog_html`. Build first:
`cachereg build --as-of 2026-10-23 --sources artificial_analysis`, then
`cachereg render explore/2026-10-23-frontier-by-lab`.
- `intelligence`: the Intelligence Index, January 2025 to October 23, 2026.
- `terminal-bench`: Terminal-Bench 4.0, January 2026 to October 23, 2026. Before 2026 every model scores about 0.
- Step lines: the four labs in greys (distinct, but telling them apart is not the point) and the best open-weight
  line in the accent, heavier. A dot marks each new record; each line ends in a dot labelled with its current model
  and score; a legend names the lines.
- On `terminal-bench` the open-weight line names the model family each time the record changes hands (Qwen, GLM,
  DeepSeek, GLM), except the last (Kimi), whose model the end label names. `intelligence` has no such labels:
  the record changes hands 14 times, five of them in September–November 2025, and labels there collide. Thinning
  them would leave a label over a stretch held by another family. A motion version could flash each name in
  as it takes the record and out again, ending on the current holder only.

## Data
- `artificial_analysis`: one snapshot of AA's LLM data API (attribution required, redistribution forbidden, so
  the data table and `data.json` are withheld from any published render).
- Mart `120_artificial_analysis` (`aa_models`, `aa_evals`): `artificial_analysis_intelligence_index` (0–100) and
  `terminalbench_v4_0` (0–1, plotted as %).

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
4. **Windows start on 2025-01-01 (index) and 2026-01-01 (Terminal-Bench)** (`config.start` in `explore.yaml`), and
   each line enters at the record it held then. A lab with no score before then starts at its first scored model.
5. **Labs are named as companies** where AA uses a brand: Moonshot for AA's "Kimi", Z.ai for "Z AI".

## Caveats
- **Today's scores, placed at past release dates.** AA re-runs models and re-versions its index and evals, so the
  lines show how models released at each date score now, not what the leaderboard showed then. AA offers no
  history; our snapshots start on 2026-10-23.
- **Terminal-Bench 4.0 is new and hard.** Models from 2025 score near zero on it, so its chart starts in 2026
  (a flat 2025 would reflect the benchmark, not a lack of progress). These are AA's own runs, all with AA's harness.
  They differ from labs' self-reported figures: Moonshot reports 65.7% for Kimi K3.1 Pro with the Claude Code harness, and 66.4% for
  Claude Opus 5.5, which AA scores at 59.6. They also differ from the tbench.ai leaderboard, which compares agents.
- **Kimi K3.1 Pro counts as open-weight on announcement** (the author's call). Its weights are promised by
  November 4, 2026 and were not out on 2026-10-23. Without it, the open-weight line ends at MiMo-V2.6-Pro (46.3 on
  the index) and GLM-5.3 (41.9% on Terminal-Bench).
- **Open-weight dates are AA release dates**, even where weights came later. Kimi K3's came about 10 days after the
  API, GLM-5.3's about 2 weeks after. The MiMo-V2-Flash February update is counted as open, though its updated
  weights were not confirmed.
- **Qwen3.8 Max counts as closed**, as AA lists it. Alibaba published a related text-only checkpoint
  (Qwen3.8-2.4T-A95B), and some trackers count it as open. Counted as open, it would briefly hold the open-weight
  record: on Terminal-Bench from 2026-08-03 (18.7%) until GLM-5.3, and on the index from 2026-09-02 (45.4) until
  MiMo-V2.6-Pro. Today's standings would not change.
- **Meta's line since April 2026 is its closed Muse models** (Meta Superintelligence Labs), not Llama.
- **One lab's best model may be expensive or slow**; price and speed are not shown.

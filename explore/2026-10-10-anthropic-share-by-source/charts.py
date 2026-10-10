"""Charts for the Anthropic-share-by-source exploration (render contract: src/cachereg/render.py).

One layout for three visuals: Anthropic's share of each source's reported total, three sources on one 0–100%
axis (same measure in each; author decision), weekly dots and a trailing 4-week line per source, labelled at
the line ends. On `spend`, a faint band shows OpenRouter's sensitivity to its unpriced tokens. The render
contract passes no visual name, so each visual has a thin function over the shared helper.

Video (`<visual>_specs`): the weekly dots sweep in bright from left to right; then each source's line draws in
turn (Ramp, OpenRouter, Vercel) at one calendar speed, its dots dimming as it starts and its end label fading in
once it is drawn; on `spend`, OpenRouter's band fades in after its line; a long hold on the final frame, which
equals the static chart. Every frame draws every mark (hidden ones at opacity 0) at the final frame's fitted
size, so the canvas never moves.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import altair as alt
import polars as pl

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit, fit_size
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX = 17, 15
NAMES = {"ramp": "Ramp", "vercel": "Vercel", "openrouter": "OpenRouter"}
# One colour per source, close to its brand but tuned for the dark canvas and each other (author, 2026-10-10:
# brand-aligned, legibility first). OpenRouter: its "Grape" logo fill #7624F4, lifted to OKLCH L 0.60 (label
# contrast 3.1 -> 4.5:1). Ramp: its yellow-green #E4F222 (site CSS), darkened to L 0.82 so it does not outshine
# the others; it stays above the dark-mode lightness band on purpose (inside it the hue turns olive). Vercel has
# no colour brand (black and white; near-white would rival the text), so a sky blue clear of both hues and of
# Anthropic's orange. OpenRouter brightened to L 0.65 (contrast 5.6:1) with its hue nudged 4° toward violet and
# Vercel's toward cyan, which keeps the two apart. Validator (dark, all pairs): CVD worst ΔE 9.2, normal 19.7,
# contrast >= 3:1 for all.
SOURCE_COLOR = {"ramp": "#C4D00A", "openrouter": "#9C6BFF", "vercel": "#0AA3D6"}
LINE_PX = 3.4  # 4-week lines (scaled by font_scale); heavier for small screens
END_LABEL_PX = 20  # line-end labels, sized for small screens
LINE_ORDER = ["ramp", "openrouter", "vercel"]  # the video draws the lines in this order (author)
DOT_SIZE, DOT_OP = 16, 0.35  # weekly dots as in the static chart (dim)
DOT_SIZE_BRIGHT, DOT_OP_BRIGHT = 30, 0.9  # as they sweep in
BAND_OP = 0.18
# video timing (s)
FPS = 30
INTRO_S, SWEEP_S, LINE_S, PAUSE_S, DIM_S, LABEL_S, BAND_S, FINAL_HOLD_S = 0.5, 2.5, 3.0, 0.4, 0.3, 0.3, 0.5, 5.0
MONTH_LABEL = "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"


def _ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _color(source: str) -> str:
    return SOURCE_COLOR[source]


def spend(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    return fit(lambda w, h: _share(story, w, h, font_scale, "spend"), width, height)


def tokens(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    return fit(lambda w, h: _share(story, w, h, font_scale, "tokens"), width, height)


def tokens_with_free(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False):
    return fit(lambda w, h: _share(story, w, h, font_scale, "tokens-with-free"), width, height)


def spend_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict):
    return _specs(story, width, height, font_scale, "spend")


def tokens_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict):
    return _specs(story, width, height, font_scale, "tokens")


def tokens_with_free_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict):
    return _specs(story, width, height, font_scale, "tokens-with-free")


def _smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _series(story: Story, visual: str) -> pl.DataFrame:
    """The visual's weekly rows, every line ending at the week the subtitle describes."""
    measure, variant = {"spend": ("spend", None), "tokens": ("tokens", "paid"), "tokens-with-free": ("tokens", "all")}[
        visual
    ]
    end = date.fromisoformat(story.extra["visuals"][visual]["week"])
    w = story.frames["weekly"].filter((pl.col("measure") == measure) & (pl.col("week") <= end))
    if measure == "tokens":
        w = w.filter((pl.col("source") != "openrouter") | (pl.col("variant") == variant))
    return w.with_columns(t=pl.col("week").map_elements(_ms, return_dtype=pl.Int64)).sort("t")


def _specs(story: Story, width: int, height: int, fs: float, visual: str) -> tuple[list[dict], int]:
    """Frame states → one spec per frame, all at the final frame's fitted size (see the module docstring)."""
    w, h = fit_size(lambda a, b: _share(story, a, b, fs, visual), width, height)
    rows = _series(story, visual)
    first, last = rows["t"].min(), rows["t"].max()
    lines = {
        src: (g.drop_nulls("rolling4_pct")["t"].min(), g.drop_nulls("rolling4_pct")["t"].max())
        for src in LINE_ORDER
        for g in [rows.filter(pl.col("source") == src)]
    }
    # one calendar speed for every line: the time Ramp's line takes sets it, so a shorter history draws faster
    ms_per_frame = (lines["ramp"][1] - lines["ramp"][0]) / (LINE_S * FPS)
    state = {
        "cut": None,
        "dot": {src: (0.0, DOT_SIZE_BRIGHT) for src in LINE_ORDER},
        "line": {src: None for src in LINE_ORDER},
        "label": {src: 0.0 for src in LINE_ORDER},
        "band": 0.0,
    }
    states: list[dict] = []

    def snap() -> None:
        states.append({k: dict(v) if isinstance(v, dict) else v for k, v in state.items()})

    def frames(seconds: float) -> int:
        return max(int(round(seconds * FPS)), 1)

    for _ in range(frames(INTRO_S)):
        snap()
    state["dot"] = {src: (DOT_OP_BRIGHT, DOT_SIZE_BRIGHT) for src in LINE_ORDER}
    n = frames(SWEEP_S)
    for i in range(n):
        state["cut"] = first + (last - first) * _smooth((i + 1) / n)
        snap()
    for k, src in enumerate(LINE_ORDER):
        t0, t1 = lines[src]
        n = max(int(round((t1 - t0) / ms_per_frame)), 1)
        dim = frames(DIM_S)
        for i in range(n):
            u = _smooth((i + 1) / dim)  # its dots cross-fade from bright to dim as its line starts
            state["dot"][src] = (
                DOT_OP_BRIGHT + (DOT_OP - DOT_OP_BRIGHT) * u,
                DOT_SIZE_BRIGHT + (DOT_SIZE - DOT_SIZE_BRIGHT) * u,
            )
            state["line"][src] = t0 + (t1 - t0) * _smooth((i + 1) / n)
            snap()
        for i in range(frames(LABEL_S)):
            state["label"][src] = _smooth((i + 1) / frames(LABEL_S))
            snap()
        if src == "openrouter" and visual == "spend":  # its band fades in once its line is drawn
            for i in range(frames(BAND_S)):
                state["band"] = _smooth((i + 1) / frames(BAND_S))
                snap()
        if k < len(LINE_ORDER) - 1:
            for _ in range(frames(PAUSE_S)):
                snap()
    state["band"] = 1.0
    for _ in range(frames(FINAL_HOLD_S)):
        snap()
    return [_share(story, w, h, fs, visual, state=st).to_dict() for st in states], FPS


def _drawn(points: list[tuple[int, float | None]], until: float) -> list[dict]:
    """A line's points up to time `until`, ending at an interpolated tip (no tip across a gap)."""
    out = []
    for (ta, va), (tb, vb) in zip(points, points[1:] + [(None, None)], strict=True):
        if ta > until:
            break
        out.append({"t": ta, "v": va})
        if tb is not None and tb > until and va is not None and vb is not None:
            k = (until - ta) / (tb - ta)
            out.append({"t": ta + (tb - ta) * k, "v": va + (vb - va) * k})
            break
    return out


def _share(story: Story, width: float, height: float, fs: float, visual: str, state: dict | None = None):
    """The chart, finished (state None: the static chart and the video's final frame) or as one video frame.

    state: {"cut": dots shown up to this time (ms) or None for none, "dot": {source: (opacity, size)},
    "line": {source: drawn up to this time (ms) or None}, "label": {source: opacity}, "band": opacity}.
    """
    fonts = brand()["fonts"]
    measure = "spend" if visual == "spend" else "tokens"
    # every line ends at the week the subtitle describes (the latest week all three sources cover)
    end = date.fromisoformat(story.extra["visuals"][visual]["week"])
    w = _series(story, visual)
    first, last = w["week"].min(), w["week"].max()
    label_px = (len("OpenRouter 100%") * 0.55 * END_LABEL_PX + 28) * fs
    plot_w = max(width - 60 * fs, 1.0)  # first guess; fit corrects for the axes
    plot_h = max(height - 40 * fs, 1.0)
    span = _ms(last) - _ms(first)
    x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(last) + span * label_px / max(plot_w - label_px, 1.0)])
    y_scale = alt.Scale(domain=[0, 100], nice=False)
    # quarterly ticks through the first month after the last week (e.g. Oct after 27 Sep), which the axis
    # reaches because it extends past the last week for the end labels
    after = date(last.year + last.month // 12, last.month % 12 + 1, 1)
    ticks = [date(y, m, 1) for y in range(first.year, last.year + 2) for m in (1, 4, 7, 10)]
    x_axis = alt.Axis(
        values=[_ms(t) for t in ticks if first <= t <= after],
        labelExpr=MONTH_LABEL,
        labelFontSize=AXIS_PX * fs,
        grid=False,
        title=None,
    )
    # fixed ticks: automatic ones change with the height and make the outer size jump during fitting
    y_axis = alt.Axis(
        values=[0, 25, 50, 75, 100], labelExpr="datum.value + '%'", labelFontSize=AXIS_PX * fs, title=None
    )
    x = alt.X("t:T", scale=x_scale, axis=x_axis)

    rows = w
    layers = []
    if measure == "spend":
        b = story.frames["or_bound"].filter(pl.col("week") <= end).sort("week")
        # one area per unbroken run of 4-week values, so the band breaks where the line does
        b = b.with_columns(run=pl.col("computed_r4").is_null().cum_sum()).drop_nulls(["computed_r4", "sensitivity_r4"])
        for (_,), part in b.group_by("run", maintain_order=True):
            band = alt.Data(
                values=part.select(
                    t=pl.col("week").map_elements(_ms, return_dtype=pl.Int64), lo="sensitivity_r4", hi="computed_r4"
                ).to_dicts()
            )
            layers.append(
                alt.Chart(band)
                .mark_area(color=_color("openrouter"), opacity=BAND_OP * (1.0 if state is None else state["band"]))
                .encode(x=x, y=alt.Y("lo:Q", scale=y_scale, axis=y_axis), y2="hi:Q")
            )
    ends = []
    for src in ("ramp", "vercel", "openrouter"):
        s = rows.filter(pl.col("source") == src)
        c = _color(src)
        dot_op, dot_size = (DOT_OP, DOT_SIZE) if state is None else state["dot"][src]
        cut = None if state is None else state["cut"]
        dots = s.select("t", "share_pct").with_columns(
            op=pl.lit(dot_op) if state is None or cut is not None else pl.lit(0.0)
        )
        if cut is not None:  # dots not yet swept in are drawn invisible, so the canvas keeps its size
            dots = dots.with_columns(op=pl.when(pl.col("t") <= cut).then(pl.col("op")).otherwise(0.0))
        points = list(zip(s["t"].to_list(), s["rolling4_pct"].to_list(), strict=True))
        until = None if state is None else state["line"][src]
        line = (
            s.select("t", v="rolling4_pct").to_dicts()
            if state is None
            else (_drawn(points, until) if until is not None else [])
        )
        layers += [
            alt.Chart(alt.Data(values=dots.to_dicts()))
            .mark_circle(size=dot_size * fs**2, color=c)
            .encode(x=x, y=alt.Y("share_pct:Q", scale=y_scale, axis=y_axis), opacity=alt.Opacity("op:Q", scale=None)),
            alt.Chart(alt.Data(values=line))
            .mark_line(color=c, strokeWidth=LINE_PX * fs)
            .encode(x=x, y=alt.Y("v:Q", scale=y_scale, axis=y_axis)),
        ]
        e = s.drop_nulls("rolling4_pct").row(-1, named=True)
        ends.append({"t": e["t"], "v": e["rolling4_pct"], "src": src, "name": f"{NAMES[src]} {e['rolling4_pct']:.0f}%"})

    # end labels, nudged apart in pixels so close lines stay legible
    gap = END_LABEL_PX * fs * 1.25 / plot_h * 100
    placed: list[float] = []
    for e in sorted(ends, key=lambda r: r["v"], reverse=True):
        y = e["v"] if not placed else min(e["v"], placed[-1] - gap)
        placed.append(y)
        e["ly"] = y
    low = min(placed)
    for e in ends:
        e["ly"] = e["ly"] - min(low, 0)
    for e in ends:
        c = _color(e["src"])
        d = alt.Data(values=[e])
        op = 1.0 if state is None else state["label"][e["src"]]  # drawn at opacity 0 until shown
        layers += [
            alt.Chart(d)
            .mark_circle(size=100 * fs**2, opacity=op, color=c, stroke=color("canvas"), strokeWidth=2, strokeOpacity=op)
            .encode(x=x, y=alt.Y("v:Q", scale=y_scale, axis=y_axis)),
            alt.Chart(d)
            .mark_text(
                align="left",
                baseline="middle",
                dx=10 * fs,
                fontSize=END_LABEL_PX * fs,
                font=fonts["body"],
                fontWeight="bold",
                color=c,
                opacity=op,
            )
            .encode(x=x, y=alt.Y("ly:Q", scale=y_scale, axis=y_axis), text="name:N"),
        ]
    # the measure, stamped on the chart's face (upper right), just below the 100% gridline
    layers.append(
        alt.Chart(alt.Data(values=[{"s": story.extra["stamp"][visual]}]))
        .mark_text(
            align="right",
            baseline="top",
            fontSize=(LABEL_PX + 3) * fs,
            fontWeight="bold",
            font=fonts["body"],
            color=color("text"),
        )
        .encode(x=alt.value(plot_w), y=alt.value(10 * fs), text="s:N")
    )
    return alt.layer(*layers).properties(width=plot_w, height=plot_h).configure(**vl_config(fs))

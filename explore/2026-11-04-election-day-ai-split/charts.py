"""Charts for the election-day split exploration (render contract: src/cachereg/render.py).

`session`: every stock as a % change from Tuesday's close on one time axis. A short, steep segment of each line
crosses the overnight gap and the first 5 minutes, from the previous close to the first bar's end. Colour carries
the group (the accent for the hyperscalers, categorical slot 2 for the supply chain; no vendor appears here), the
S&P baseline is a dimmed text colour, and each line is named at its end, with labels spread apart and tied back
by thin leaders.

Video (`session_specs`): the S&P draws, its label fades in, a caption narrates it and fades away, and the S&P dims;
the hyperscalers draw together, then their caption; the supply chain draws together, then its caption; the key
fades in once the captions are gone, and the video holds on the final frame, which the PNG targets equal. Captions
are large and use the band under the 0% line that the key takes up only at the end.
Every frame draws every mark
(hidden ones at opacity ~0) at the final frame's fitted size, so the canvas never moves.
"""

from __future__ import annotations

import math
import textwrap

import altair as alt
from analysis import SESSION_MIN

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit_size
from cachereg.viz.theme import vl_config

OVERNIGHT = -3  # x position of the previous close, in minutes before the open
LABEL_GAP_MIN = 10  # minutes of x between the close and its label
LABEL_PX, AXIS_PX, LEGEND_PX, NOTE_PX = 17, 16, 17, 30
NOTE_CHAR_EM = 0.48  # average advance of the body font, for wrapping a note to the room it has
TICKS = {OVERNIGHT: "Tue close", 90: "11:00", 210: "1:00", 330: "3:00", 390: "4:00"}
GROUPS = ("baseline", "rose", "fell")  # the order they draw in
LEGEND = {"rose": ("Hyperscalers", -2.4), "fell": ("Data center supply chain", -4.2)}
NOTE_Y, NOTE_MIN = -2.7, 40  # the captions' center and left edge: the band under the 0% line, clear of the first dip
DIM_LINE, DIM_LABEL = 0.4, 0.6  # the S&P's opacity once dimmed

FPS = 30
INTRO_S, BASE_DRAW_S, GROUP_DRAW_S, LABEL_S, DIM_S, FINAL_HOLD_S = 0.5, 2.2, 2.6, 0.4, 0.6, 3.0
NOTE_FADE_S, NOTE_HOLD_S = 0.4, 3.0
FINAL = {  # the final frame (and the PNGs)
    "baseline": {"until": math.inf, "legend": 1.0, "label": 1.0, "dim": 1.0, "note": 0.0},
    "rose": {"until": math.inf, "legend": 1.0, "label": 1.0, "dim": 0.0, "note": 0.0},
    "fell": {"until": math.inf, "legend": 1.0, "label": 1.0, "dim": 0.0, "note": 0.0},
}


def _op(v: float) -> float:
    """A hidden mark stays at an invisible opacity, never 0: Vega leaves 0-opacity marks out of the chart's
    bounds, so a mark appearing would resize the canvas and the video would jump."""
    return max(v, 0.002)


def _smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _drawn(points: list[dict], until: float) -> list[dict]:
    """A line's points up to minute `until`, ending at an interpolated tip."""
    out = []
    for a, b in zip(points, [*points[1:], None], strict=True):
        if a["minute"] > until:
            break
        out.append(a)
        if b is not None and b["minute"] > until:
            k = (until - a["minute"]) / (b["minute"] - a["minute"])
            out.append({"minute": until, "pct": a["pct"] + (b["pct"] - a["pct"]) * k})
            break
    return out or points[:1]


def _spread(values: list[float], gap: float) -> list[float]:
    """Label positions, in the order given (descending), at least `gap` apart and as near their values as possible."""
    out = list(values)
    for _ in range(200):
        moved = False
        for i in range(len(out) - 1):
            short = gap - (out[i] - out[i + 1])
            if short > 1e-9:
                out[i] += short / 2
                out[i + 1] -= short / 2
                moved = True
        if not moved:
            break
    return out


def _chart(story: Story, w: float, h: float, fs: float, state: dict) -> alt.LayerChart:
    fonts = brand()["fonts"]
    paths = story.frames["paths"]
    summary = story.frames["summary"].to_dicts()
    hues = {"rose": color("accent"), "fell": color("categorical")[1], "baseline": color("text")}

    top = 5.0 * ((paths["pct"].max() // 5) + 1)
    bottom = float(paths["pct"].min() // 1) - 1
    y_ticks = [v for v in range(int(5 * (bottom // 5)), int(top) + 1, 5) if v >= bottom]
    x_end = SESSION_MIN + (SESSION_MIN - OVERNIGHT) * 0.3  # room for the end labels
    x_scale = alt.Scale(domain=[OVERNIGHT, x_end], nice=False, zero=False)
    y_scale = alt.Scale(domain=[bottom, top], nice=False)
    expr = " : ".join(f"datum.value == {k} ? '{v}'" for k, v in TICKS.items()) + " : ''"
    x = alt.X("minute:Q", title=None, scale=x_scale,
              axis=alt.Axis(values=list(TICKS), labelExpr=expr, grid=False, labelFontSize=AXIS_PX * fs,
                            labelFlush=False, labelOverlap=False, labelColor=color("text_secondary")))  # fmt: skip
    y = alt.Y("pct:Q", title=None, scale=y_scale,
              axis=alt.Axis(values=y_ticks, labelFontSize=AXIS_PX * fs,
                            labelExpr="(datum.value > 0 ? '+' : datum.value < 0 ? '−' : '') + abs(datum.value) + '%'",
                            labelColor=color("text_secondary"), grid=True, gridColor=color("panel")))  # fmt: skip

    def line_opacity(group: str) -> float:
        return 1 - (1 - DIM_LINE) * state[group]["dim"]

    zero = (
        alt.Chart(alt.Data(values=[{"y": 0}]))
        .mark_rule(color=color("muted"), strokeWidth=1.5 * fs)
        .encode(y=alt.Y("y:Q", scale=y_scale))
    )
    layers = [zero]
    for group in GROUPS:
        st = state[group]
        for s in (r for r in summary if r["group"] == group):
            rows = paths.filter(paths["ticker"] == s["ticker"]).sort("minute").to_dicts()
            points = [{"minute": OVERNIGHT, "pct": 0.0}, *({"minute": r["minute"], "pct": r["pct"]} for r in rows)]
            started = st["until"] >= OVERNIGHT
            layers.append(
                alt.Chart(alt.Data(values=_drawn(points, st["until"])))
                .mark_line(
                    color=hues[group],
                    strokeWidth=(3.5 if group == "baseline" else 2.2) * fs,
                    opacity=_op(line_opacity(group) if started else 0),
                )
                .encode(x=x, y=y)
            )

    per_pt = h / (top - bottom)
    ordered = sorted(summary, key=lambda r: -r["close_pct"])
    placed = _spread([r["close_pct"] for r in ordered], (LABEL_PX + 7) * fs / per_pt)
    label_x = SESSION_MIN + LABEL_GAP_MIN
    for s, at in zip(ordered, placed, strict=True):
        st = state[s["group"]]
        fade = st["label"] * (1 - (1 - DIM_LABEL) * st["dim"])
        leader = [{"minute": SESSION_MIN, "pct": s["close_pct"]}, {"minute": label_x - 2, "pct": at}]
        layers.append(
            alt.Chart(alt.Data(values=leader))
            .mark_line(color=hues[s["group"]], strokeWidth=1.2 * fs, opacity=_op(fade))
            .encode(x=x, y=y)
        )
        value = f"{s['close_pct']:+.1f}%".replace("-", "−")
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": label_x, "pct": at, "t": f"{s['name']} {value}"}]))
            .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=LABEL_PX * fs,
                       color=color("text"), opacity=_op(fade))
            .encode(x=x, y=y, text="t:N")
        )  # fmt: skip

    for group, (text, at) in LEGEND.items():
        shown = _op(state[group]["legend"])
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": 110, "pct": at}, {"minute": 128, "pct": at}]))
            .mark_line(color=hues[group], strokeWidth=4 * fs, opacity=shown)
            .encode(x=x, y=y)
        )
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": 134, "pct": at, "t": text}]))
            .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=LEGEND_PX * fs,
                       color=color("text_secondary"), opacity=shown)
            .encode(x=x, y=y, text="t:N")
        )  # fmt: skip
    note_px = NOTE_PX * fs
    room_px = (x_end - NOTE_MIN) / (x_end - OVERNIGHT) * w
    chars = int(room_px / (NOTE_CHAR_EM * note_px))
    for group, text in story.extra["notes"].items():
        lines = textwrap.wrap(text, chars)
        for i, line in enumerate(lines):
            layers.append(
                alt.Chart(alt.Data(values=[{"minute": NOTE_MIN, "pct": NOTE_Y, "t": line}]))
                .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=note_px, fontWeight=600,
                           color=color("text"), opacity=_op(state[group]["note"]),
                           dy=(i - (len(lines) - 1) / 2) * note_px * 1.3)
                .encode(x=x, y=y, text="t:N")
            )  # fmt: skip
    return alt.layer(*layers).properties(width=w, height=h).configure(**vl_config(fs))


def session_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    """Frame states → one spec per frame, all at the final frame's fitted size (see the module docstring)."""
    fs = font_scale
    w, h = fit_size(lambda a, b: _chart(story, a, b, fs, FINAL), width, height)
    state = {g: {"until": -math.inf, "legend": 0.0, "label": 0.0, "dim": 0.0, "note": 0.0} for g in GROUPS}
    states: list[dict] = []

    def snap() -> None:
        states.append({k: dict(v) for k, v in state.items()})

    def frames(seconds: float) -> int:
        return max(int(round(seconds * FPS)), 1)

    def draw(group: str, seconds: float) -> None:
        n = frames(seconds)
        fade_in = frames(LABEL_S)
        for i in range(n):
            state[group]["until"] = OVERNIGHT + (SESSION_MIN - OVERNIGHT) * _smooth((i + 1) / n)
            snap()
        state[group]["until"] = math.inf
        for i in range(fade_in):
            state[group]["label"] = _smooth((i + 1) / fade_in)
            snap()

    def narrate(group: str) -> None:
        n = frames(NOTE_FADE_S)
        for i in range(n):
            state[group]["note"] = _smooth((i + 1) / n)
            snap()
        for _ in range(frames(NOTE_HOLD_S)):
            snap()
        for i in range(n):
            state[group]["note"] = 1 - _smooth((i + 1) / n)
            snap()

    for _ in range(frames(INTRO_S)):
        snap()
    draw("baseline", BASE_DRAW_S)
    narrate("baseline")
    n = frames(DIM_S)
    for i in range(n):
        state["baseline"]["dim"] = _smooth((i + 1) / n)
        snap()
    draw("rose", GROUP_DRAW_S)
    narrate("rose")
    draw("fell", GROUP_DRAW_S)
    narrate("fell")
    n = frames(LABEL_S)
    for i in range(n):  # the key comes last, once every caption is gone
        for group in GROUPS:
            state[group]["legend"] = _smooth((i + 1) / n)
        snap()
    for _ in range(frames(FINAL_HOLD_S)):
        snap()
    if states[-1] != FINAL:
        raise ValueError("election-day split: the final frame must equal the still")
    return [_chart(story, w, h, fs, st).to_dict() for st in states], FPS

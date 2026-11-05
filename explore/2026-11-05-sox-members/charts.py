"""Charts for the sox-members exploration (render contract: src/cachereg/render.py).

`members`: all 30 members and the index as a % change from Tuesday's close, across two sessions, with a rule at
Wednesday's close. Members are thin lines in one colour (categorical slot 3, the chip colour of the chip-selloff
charts); the index is a heavy line in the text colour, drawn on top. Thirty labels will not fit, so only the index,
the largest member and the three smallest and three largest drops are named, and those lines are stronger.

Video (`members_specs`): the members draw together, their labels fade in and a caption narrates them; the index draws,
its label fades in and a caption narrates it; the key fades in once the captions are gone, and the video holds on the
final frame, which the PNG targets equal. Every frame draws every mark (hidden ones at opacity ~0) at the final frame's
fitted size, so the canvas never moves.
"""

from __future__ import annotations

import math
import textwrap

import altair as alt
from analysis import SECOND_OPEN, SESSION_MIN

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit_size
from cachereg.viz.theme import vl_config

OVERNIGHT = -3  # x position of Tuesday's close, in minutes before Wednesday's open
END = SECOND_OPEN + SESSION_MIN
TICKS = {OVERNIGHT: "Tue close", SESSION_MIN: "Wed close", END: "Thu close"}
LABEL_ROOM = 0.24  # room for the end labels, as a share of the axis
LABEL_GAP_MIN = 20  # minutes of x between the close and its label
LABEL_PX, AXIS_PX, LEGEND_PX, NOTE_PX = 17, 16, 17, 30
NOTE_CHAR_EM = 0.47  # average advance of the body font, for wrapping a note to the room it has
GROUPS = ("members", "index")  # the order they draw in
LEGEND = {"members": ("The 30 stocks in the index", 5.8), "index": ("PHLX Semiconductor Index (SOX)", 2.6)}
BAND, NOTE_Y, NOTE_MIN, BOTTOM_ROOM = 8.0, 4.2, 80, 2  # the captions' band above the highest line
THIN, NAMED, HEAVY = 1.4, 2.2, 5.5  # line widths at font scale 1
THIN_OPACITY = 0.55

FPS = 30
INTRO_S, MEMBERS_DRAW_S, INDEX_DRAW_S, LABEL_S, FINAL_HOLD_S = 0.5, 4.0, 3.0, 0.4, 5.0
NOTE_FADE_S, NOTE_HOLD_S = 0.4, 3.0
FINAL = {  # the final frame (and the PNGs)
    "members": {"until": math.inf, "legend": 1.0, "label": 1.0, "note": 0.0},
    "index": {"until": math.inf, "legend": 1.0, "label": 1.0, "note": 0.0},
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
    hues = {"members": color("categorical")[2], "index": color("text")}

    foot = max(0.0, float(math.ceil(paths["pct"].max())))  # the band above the highest line
    top = foot + BAND
    bottom = float(paths["pct"].min() // 1) - BOTTOM_ROOM
    y_ticks = [v for v in range(int(5 * (bottom // 5)), int(foot) + 1, 5) if v >= bottom]
    span = END - OVERNIGHT
    x_end = END + span * LABEL_ROOM
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

    layers = [
        alt.Chart(alt.Data(values=[{"minute": OVERNIGHT, "pct": 0}, {"minute": END, "pct": 0}]))
        .mark_line(color=color("muted"), strokeWidth=1.5 * fs)
        .encode(x=x, y=y),
        alt.Chart(alt.Data(values=[{"minute": SESSION_MIN, "pct": bottom}, {"minute": SESSION_MIN, "pct": foot}]))
        .mark_line(color=color("muted"), strokeWidth=1 * fs, strokeDash=[4 * fs, 4 * fs])
        .encode(x=x, y=y),
    ]
    # Thin lines first, so the named lines and then the index draw over them.
    order = sorted(summary, key=lambda r: (r["group"] == "index", r["labelled"]))
    for s in order:
        st = state[s["group"]]
        rows = paths.filter(paths["ticker"] == s["ticker"]).sort("minute").to_dicts()
        points = [{"minute": OVERNIGHT, "pct": 0.0}, *({"minute": r["minute"], "pct": r["pct"]} for r in rows)]
        started = st["until"] >= OVERNIGHT
        heavy = s["group"] == "index"
        width = HEAVY if heavy else NAMED if s["labelled"] else THIN
        full = 1.0 if heavy or s["labelled"] else THIN_OPACITY
        layers.append(
            alt.Chart(alt.Data(values=_drawn(points, st["until"])))
            .mark_line(color=hues[s["group"]], strokeWidth=width * fs, opacity=_op(full if started else 0))
            .encode(x=x, y=y)
        )

    named = [r for r in sorted(summary, key=lambda r: -r["close_pct"]) if r["labelled"]]
    row = (LABEL_PX + 7) * fs / (h / (top - bottom))
    placed = _spread([r["close_pct"] for r in named], row)
    lift = max(0.0, bottom + row / 2 - placed[-1])  # keep the stack above the time axis
    label_x = END + LABEL_GAP_MIN
    for s, at in zip(named, [p + lift for p in placed], strict=True):
        fade = state[s["group"]]["label"]
        heavy = s["group"] == "index"
        leader = [{"minute": END, "pct": s["close_pct"]}, {"minute": label_x - 4, "pct": at}]
        layers.append(
            alt.Chart(alt.Data(values=leader))
            .mark_line(color=hues[s["group"]], strokeWidth=1.2 * fs, opacity=_op(fade))
            .encode(x=x, y=y)
        )
        value = f"{s['close_pct']:+.1f}%".replace("-", "−")
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": label_x, "pct": at, "t": f"{s['name']} {value}"}]))
            .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=LABEL_PX * fs,
                       fontWeight=700 if heavy else 400, color=color("text"), opacity=_op(fade))
            .encode(x=x, y=y, text="t:N")
        )  # fmt: skip

    stretch = span / (SESSION_MIN - OVERNIGHT)
    for group, (text, at) in LEGEND.items():
        shown = _op(state[group]["legend"])
        at_y = foot + at
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": 110, "pct": at_y}, {"minute": 110 + 18 * stretch, "pct": at_y}]))
            .mark_line(color=hues[group], strokeWidth=(HEAVY if group == "index" else 3) * fs, opacity=shown)
            .encode(x=x, y=y)
        )
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": 110 + 24 * stretch, "pct": at_y, "t": text}]))
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
                alt.Chart(alt.Data(values=[{"minute": NOTE_MIN, "pct": foot + NOTE_Y, "t": line}]))
                .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=note_px, fontWeight=600,
                           color=color("text"), opacity=_op(state[group]["note"]),
                           dy=(i - (len(lines) - 1) / 2) * note_px * 1.3)
                .encode(x=x, y=y, text="t:N")
            )  # fmt: skip
    return alt.layer(*layers).properties(width=w, height=h).configure(**vl_config(fs))


def members_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    """Frame states → one spec per frame, all at the final frame's fitted size (see the module docstring)."""
    fs = font_scale
    w, h = fit_size(lambda a, b: _chart(story, a, b, fs, FINAL), width, height)
    state = {g: {"until": -math.inf, "legend": 0.0, "label": 0.0, "note": 0.0} for g in GROUPS}
    states: list[dict] = []

    def snap() -> None:
        states.append({k: dict(v) for k, v in state.items()})

    def frames(seconds: float) -> int:
        return max(int(round(seconds * FPS)), 1)

    def draw(group: str, seconds: float) -> None:
        n = frames(seconds)
        fade_in = frames(LABEL_S)
        for i in range(n):
            state[group]["until"] = OVERNIGHT + (END - OVERNIGHT) * _smooth((i + 1) / n)
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
    draw("members", MEMBERS_DRAW_S)
    narrate("members")
    draw("index", INDEX_DRAW_S)
    narrate("index")
    n = frames(LABEL_S)
    for i in range(n):  # the key comes last, once every caption is gone
        for group in GROUPS:
            state[group]["legend"] = _smooth((i + 1) / n)
        snap()
    for _ in range(frames(FINAL_HOLD_S)):
        snap()
    if states[-1] != FINAL:
        raise ValueError("sox-members: the final frame must equal the still")
    return [_chart(story, w, h, fs, st).to_dict() for st in states], FPS

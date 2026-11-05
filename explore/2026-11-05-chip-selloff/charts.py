"""Charts for the chip-selloff exploration (render contract: src/cachereg/render.py).

`session`: every stock as a % change from Wednesday's close on one time axis. A short, steep segment of each line
crosses the overnight gap and the first 5 minutes, from the previous close to the first bar's end. Colour carries
the group (categorical slots 3 and 2; orange is the supply chain, as on Wednesday's chart; no vendor appears here), the
S&P baseline is a dimmed text colour, and each line is named at its end, with labels spread apart and tied back
by thin leaders.

`two_day`: the same, from Tuesday's close through Thursday's across both sessions, with a rule at Wednesday's close.
Its lines end in a small table: each stock's change on Wednesday, on Thursday and over the two days.

Video (`session_specs`, `two_day_specs`): the S&P draws, its label fades in, a caption narrates it and fades away,
and the S&P dims;
the chip stocks draw together, then their caption; the supply chain draws together, then its caption; the key
fades in once the captions are gone, and the video holds on the final frame, which the PNG targets equal. Captions
are large and use the band above the highest line that the key takes up only at the end.
Every frame draws every mark
(hidden ones at opacity ~0) at the final frame's fitted size, so the canvas never moves.
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

OVERNIGHT = -3  # x position of the previous close, in minutes before the open
LABEL_GAP_MIN = 10  # minutes of x between the close and its label
LABEL_PX, AXIS_PX, LEGEND_PX, NOTE_PX = 17, 16, 17, 30
NOTE_CHAR_EM = 0.47  # average advance of the body font, for wrapping a note to the room it has
TWO_DAY_END = SECOND_OPEN + SESSION_MIN
VIEWS = {
    "session": {"paths": "paths", "summary": "summary", "end": SESSION_MIN, "divider": None,
                "band": 5.0, "note_y": 2.6, "legend_y": {"semis": 3.6, "supply": 1.6}, "bottom_room": 4,
                "ticks": {OVERNIGHT: "Wed close", 90: "11:00", 210: "1:00", 330: "3:00", 390: "4:00"}},
    "two_day": {"paths": "two_day_paths", "summary": "two_day_summary", "end": TWO_DAY_END, "divider": SESSION_MIN,
                "band": 8.0, "note_y": 4.2, "legend_y": {"semis": 5.8, "supply": 2.6}, "bottom_room": 1,
                "ticks": {OVERNIGHT: "Tue close", SESSION_MIN: "Wed close", TWO_DAY_END: "Thu close"}},
}  # fmt: skip
NAME_COL_PX, NUM_COL_PX = 158, 70  # the two-day table: the name's width and each number column's, at font scale 1
TABLE_COLS = (("first_pct", "Wed"), ("second_pct", "Thu"), ("close_pct", "2 days"))
GROUPS = ("baseline", "semis", "supply")  # the order they draw in
LEGEND = {"semis": "Largest chip ETF holdings", "supply": "Data center supply chain"}
NOTE_MIN = 40  # the captions' left edge
DIM_LINE, DIM_LABEL = 0.4, 0.6  # the S&P's opacity once dimmed

FPS = 30
INTRO_S, BASE_DRAW_S, GROUP_DRAW_S, LABEL_S, DIM_S, FINAL_HOLD_S = 0.5, 2.2, 2.6, 0.4, 0.6, 5.0
NOTE_FADE_S, NOTE_HOLD_S = 0.4, 3.0
FINAL = {  # the final frame (and the PNGs)
    "baseline": {"until": math.inf, "legend": 1.0, "label": 1.0, "dim": 1.0, "note": 0.0},
    "semis": {"until": math.inf, "legend": 1.0, "label": 1.0, "dim": 0.0, "note": 0.0},
    "supply": {"until": math.inf, "legend": 1.0, "label": 1.0, "dim": 0.0, "note": 0.0},
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


def _pct(v: float) -> str:
    return f"{v:+.1f}%".replace("-", "−")


def _chart(story: Story, w: float, h: float, fs: float, state: dict, name: str = "session") -> alt.LayerChart:
    fonts = brand()["fonts"]
    view = VIEWS[name]
    table = name == "two_day"
    end = view["end"]
    paths = story.frames[view["paths"]]
    summary = story.frames[view["summary"]].to_dicts()
    hues = {"semis": color("categorical")[2], "supply": color("categorical")[1], "baseline": color("text")}

    foot = max(0.0, float(math.ceil(paths["pct"].max())))  # the band above the highest line
    top = foot + view["band"]
    bottom = float(paths["pct"].min() // 1) - view["bottom_room"]  # room for the lowest end labels above the time axis
    y_ticks = [v for v in range(int(5 * (bottom // 5)), int(foot) + 1, 5) if v >= bottom]
    span = end - OVERNIGHT
    label_gap = LABEL_GAP_MIN * span / (SESSION_MIN - OVERNIGHT)
    if table:
        room_px = (NAME_COL_PX + NUM_COL_PX * len(TABLE_COLS) + 8) * fs + label_gap * w / span
        x_end = end + span * room_px / (w - room_px)
    else:
        x_end = end + span * 0.3  # room for the end labels
    per_min_px = (x_end - OVERNIGHT) / w  # minutes of x per pixel
    ticks = view["ticks"]
    x_scale = alt.Scale(domain=[OVERNIGHT, x_end], nice=False, zero=False)
    y_scale = alt.Scale(domain=[bottom, top], nice=False)
    expr = " : ".join(f"datum.value == {k} ? '{v}'" for k, v in ticks.items()) + " : ''"
    x = alt.X("minute:Q", title=None, scale=x_scale,
              axis=alt.Axis(values=list(ticks), labelExpr=expr, grid=False, labelFontSize=AXIS_PX * fs,
                            labelFlush=False, labelOverlap=False, labelColor=color("text_secondary")))  # fmt: skip
    y = alt.Y("pct:Q", title=None, scale=y_scale,
              axis=alt.Axis(values=y_ticks, labelFontSize=AXIS_PX * fs,
                            labelExpr="(datum.value > 0 ? '+' : datum.value < 0 ? '−' : '') + abs(datum.value) + '%'",
                            labelColor=color("text_secondary"), grid=True, gridColor=color("panel")))  # fmt: skip

    def line_opacity(group: str) -> float:
        return 1 - (1 - DIM_LINE) * state[group]["dim"]

    zero = (
        alt.Chart(alt.Data(values=[{"minute": OVERNIGHT, "pct": 0}, {"minute": end, "pct": 0}]))
        .mark_line(color=color("muted"), strokeWidth=1.5 * fs)
        .encode(x=x, y=y)
    )
    layers = [zero]
    if view["divider"] is not None:
        layers.append(
            alt.Chart(
                alt.Data(values=[{"minute": view["divider"], "pct": bottom}, {"minute": view["divider"], "pct": foot}])
            )
            .mark_line(color=color("muted"), strokeWidth=1 * fs, strokeDash=[4 * fs, 4 * fs])
            .encode(x=x, y=y)
        )
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
    row = (top - bottom) / (len(ordered) + 1)  # the two-day table: evenly spaced rows, under a header, filling the plot
    if table:
        placed = [top - (i + 1.5) * row for i in range(len(ordered))]
    else:
        placed = _spread([r["close_pct"] for r in ordered], (LABEL_PX + 5) * fs / per_pt)
    label_x = end + label_gap
    col_right = [label_x + (NAME_COL_PX + NUM_COL_PX * (i + 1)) * fs * per_min_px for i in range(len(TABLE_COLS))]
    for s, at in zip(ordered, placed, strict=True):
        st = state[s["group"]]
        fade = st["label"] * (1 - (1 - DIM_LABEL) * st["dim"])
        leader = [
            {"minute": end, "pct": s["close_pct"]},
            {"minute": label_x - 2 * span / (SESSION_MIN - OVERNIGHT), "pct": at},
        ]
        layers.append(
            alt.Chart(alt.Data(values=leader))
            .mark_line(color=hues[s["group"]], strokeWidth=1.2 * fs, opacity=_op(fade))
            .encode(x=x, y=y)
        )
        text = s["name"] if table else f"{s['name']} {_pct(s['close_pct'])}"
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": label_x, "pct": at, "t": text}]))
            .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=LABEL_PX * fs,
                       color=color("text"), opacity=_op(fade))
            .encode(x=x, y=y, text="t:N")
        )  # fmt: skip
        if table:
            for (col, _), right in zip(TABLE_COLS, col_right, strict=True):
                layers.append(
                    alt.Chart(alt.Data(values=[{"minute": right, "pct": at, "t": _pct(s[col])}]))
                    .mark_text(align="right", baseline="middle", font=fonts["body"], fontSize=LABEL_PX * fs,
                               color=color("text"), opacity=_op(fade), fontWeight=600 if col == "close_pct" else 400)
                    .encode(x=x, y=y, text="t:N")
                )  # fmt: skip
    if table:
        head_y = top - 0.5 * row
        for (_, head), right in zip(TABLE_COLS, col_right, strict=True):
            layers.append(
                alt.Chart(alt.Data(values=[{"minute": right, "pct": head_y, "t": head}]))
                .mark_text(align="right", baseline="middle", font=fonts["body"], fontSize=LABEL_PX * fs,
                           color=color("text_secondary"), opacity=_op(state["baseline"]["label"]))
                .encode(x=x, y=y, text="t:N")
            )  # fmt: skip

    stretch = span / (SESSION_MIN - OVERNIGHT)
    for group, text in LEGEND.items():
        at = foot + view["legend_y"][group]
        shown = _op(state[group]["legend"])
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": 110, "pct": at}, {"minute": 110 + 18 * stretch, "pct": at}]))
            .mark_line(color=hues[group], strokeWidth=4 * fs, opacity=shown)
            .encode(x=x, y=y)
        )
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": 110 + 24 * stretch, "pct": at, "t": text}]))
            .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=LEGEND_PX * fs,
                       color=color("text_secondary"), opacity=shown)
            .encode(x=x, y=y, text="t:N")
        )  # fmt: skip
    note_px = NOTE_PX * fs
    room_px = ((end if table else x_end) - NOTE_MIN) / (x_end - OVERNIGHT) * w
    chars = int(room_px / (NOTE_CHAR_EM * note_px))
    for group, text in story.extra["notes"][name].items():
        lines = textwrap.wrap(text, chars)
        for i, line in enumerate(lines):
            layers.append(
                alt.Chart(alt.Data(values=[{"minute": NOTE_MIN, "pct": foot + view["note_y"], "t": line}]))
                .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=note_px, fontWeight=600,
                           color=color("text"), opacity=_op(state[group]["note"]),
                           dy=(i - (len(lines) - 1) / 2) * note_px * 1.3)
                .encode(x=x, y=y, text="t:N")
            )  # fmt: skip
    return alt.layer(*layers).properties(width=w, height=h).configure(**vl_config(fs))


def _specs(story: Story, width: int, height: int, fs: float, name: str) -> tuple[list[dict], int]:
    """Frame states → one spec per frame, all at the final frame's fitted size (see the module docstring)."""
    end = VIEWS[name]["end"]
    w, h = fit_size(lambda a, b: _chart(story, a, b, fs, FINAL, name), width, height)
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
            state[group]["until"] = OVERNIGHT + (end - OVERNIGHT) * _smooth((i + 1) / n)
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
    draw("semis", GROUP_DRAW_S)
    narrate("semis")
    draw("supply", GROUP_DRAW_S)
    narrate("supply")
    n = frames(LABEL_S)
    for i in range(n):  # the key comes last, once every caption is gone
        for group in GROUPS:
            state[group]["legend"] = _smooth((i + 1) / n)
        snap()
    for _ in range(frames(FINAL_HOLD_S)):
        snap()
    if states[-1] != FINAL:
        raise ValueError("chip-selloff: the final frame must equal the still")
    return [_chart(story, w, h, fs, st, name).to_dict() for st in states], FPS


def session_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    return _specs(story, width, height, font_scale, "session")


def two_day_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    return _specs(story, width, height, font_scale, "two_day")

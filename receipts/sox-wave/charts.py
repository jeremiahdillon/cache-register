"""Charts for the sox-wave receipt (render contract: src/cachereg/render.py).

`members`: all 30 members and the index as a % change from Tuesday's close, across two sessions, with a rule at
Wednesday's close. Members are thin lines in one colour (categorical slot 3, the chip colour of the chip-selloff
charts); the index is a heavy line in the text colour, drawn on top. Thirty labels will not fit, so only the index and
the members in the config's `label` list are named, and those lines are stronger. Leaders are grey so that they do not
read as data. There is no key and there are no captions: the headline and the labels carry the chart.

Video (`members_specs`): the members fade in one after another, from the smallest two-day drop to the largest, each
label with its line; the index then draws across both sessions, and its label fades in; the video holds on the final
frame, which the PNG targets equal. Every frame draws every mark (hidden ones at opacity ~0) at the final frame's
fitted size, so the canvas never moves.
"""

from __future__ import annotations

import math

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
LABEL_PX, AXIS_PX = 17, 16
TOP_ROOM, BOTTOM_ROOM = 0.5, 2  # % points above the highest line and below the lowest
THIN, NAMED, HEAVY = 1.4, 2.2, 5.5  # line widths at font scale 1
THIN_OPACITY = 0.55

FPS = 30
INTRO_S, STAGGER_S, FADE_S, PAUSE_S, INDEX_DRAW_S, LABEL_S, FINAL_HOLD_S = 0.5, 0.12, 0.25, 0.3, 3.0, 0.4, 5.0
FINAL = {"members": {}, "index_until": math.inf, "index_label": 1.0}  # the final frame (and the PNGs); no entry = shown


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

    def shown(s: dict) -> float:
        """How far a line and its label have faded in."""
        if s["group"] == "index":
            return state["index_label"]
        return state["members"].get(s["ticker"], 1.0)

    top = float(math.ceil(paths["pct"].max())) + TOP_ROOM
    bottom = float(paths["pct"].min() // 1) - BOTTOM_ROOM
    y_ticks = [v for v in range(int(5 * (bottom // 5)), int(top) + 1, 5) if v >= bottom]
    x_end = END + (END - OVERNIGHT) * LABEL_ROOM
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
        alt.Chart(alt.Data(values=[{"minute": SESSION_MIN, "pct": bottom}, {"minute": SESSION_MIN, "pct": top}]))
        .mark_line(color=color("muted"), strokeWidth=1 * fs, strokeDash=[4 * fs, 4 * fs])
        .encode(x=x, y=y),
    ]
    # Thin lines first, so the named lines and then the index draw over them.
    for s in sorted(summary, key=lambda r: (r["group"] == "index", r["labelled"])):
        rows = paths.filter(paths["ticker"] == s["ticker"]).sort("minute").to_dicts()
        points = [{"minute": OVERNIGHT, "pct": 0.0}, *({"minute": r["minute"], "pct": r["pct"]} for r in rows)]
        if s["group"] == "index":
            until = state["index_until"]
            line, width, opacity = _drawn(points, until), HEAVY, 1.0 if until >= OVERNIGHT else 0.0
        else:
            full = 1.0 if s["labelled"] else THIN_OPACITY
            line, width, opacity = points, NAMED if s["labelled"] else THIN, full * shown(s)
        layers.append(
            alt.Chart(alt.Data(values=line))
            .mark_line(color=hues[s["group"]], strokeWidth=width * fs, opacity=_op(opacity))
            .encode(x=x, y=y)
        )

    named = [r for r in sorted(summary, key=lambda r: -r["close_pct"]) if r["labelled"]]
    row = (LABEL_PX + 7) * fs / (h / (top - bottom))
    placed = _spread([r["close_pct"] for r in named], row)
    lift = max(0.0, bottom + row / 2 - placed[-1])  # keep the stack above the time axis
    label_x = END + LABEL_GAP_MIN
    for s, at in zip(named, [p + lift for p in placed], strict=True):
        fade = shown(s)
        leader = [{"minute": END, "pct": s["close_pct"]}, {"minute": label_x - 4, "pct": at}]
        layers.append(
            alt.Chart(alt.Data(values=leader))
            .mark_line(color=color("muted"), strokeWidth=1.2 * fs, opacity=_op(fade))
            .encode(x=x, y=y)
        )
        value = f"{s['close_pct']:+.1f}%".replace("-", "−")
        layers.append(
            alt.Chart(alt.Data(values=[{"minute": label_x, "pct": at, "t": f"{s['name']} {value}"}]))
            .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=LABEL_PX * fs,
                       fontWeight=700 if s["group"] == "index" else 400, color=color("text"), opacity=_op(fade))
            .encode(x=x, y=y, text="t:N")
        )  # fmt: skip
    return alt.layer(*layers).properties(width=w, height=h).configure(**vl_config(fs))


def members_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    """Frame states → one spec per frame, all at the final frame's fitted size (see the module docstring)."""
    fs = font_scale
    w, h = fit_size(lambda a, b: _chart(story, a, b, fs, FINAL), width, height)
    summary = story.frames["summary"].to_dicts()
    order = [s["ticker"] for s in summary if s["group"] == "members"]  # the frame is sorted, smallest drop first
    states: list[dict] = []

    def frames(seconds: float) -> int:
        return max(int(round(seconds * FPS)), 1)

    def snap(members: dict, until: float = -math.inf, label: float = 0.0) -> None:
        states.append({"members": dict(members), "index_until": until, "index_label": label})

    hidden = dict.fromkeys(order, 0.0)
    for _ in range(frames(INTRO_S)):
        snap(hidden)
    for i in range(frames(STAGGER_S * len(order) + FADE_S)):
        t = (i + 1) / FPS
        snap({k: _smooth((t - j * STAGGER_S) / FADE_S) for j, k in enumerate(order)})
    done = dict.fromkeys(order, 1.0)
    for _ in range(frames(PAUSE_S)):
        snap(done)
    n = frames(INDEX_DRAW_S)
    for i in range(n):
        snap(done, OVERNIGHT + (END - OVERNIGHT) * _smooth((i + 1) / n))
    n = frames(LABEL_S)
    for i in range(n):
        snap(done, math.inf, _smooth((i + 1) / n))
    for _ in range(frames(FINAL_HOLD_S)):
        snap({}, math.inf, 1.0)
    if states[-1] != FINAL:
        raise ValueError("sox-wave: the final frame must equal the still")
    return [_chart(story, w, h, fs, st).to_dict() for st in states], FPS

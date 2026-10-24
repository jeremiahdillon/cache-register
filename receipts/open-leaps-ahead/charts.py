"""Charts for the open-leaps-ahead receipt (render contract: src/cachereg/render.py).

One chart, `terminal_bench`, still and motion. Each line is a step line of the best score
released so far: the four labs in greys (distinct, but telling them apart is not the point), the best open-weight
model in the accent and heavier. A dot marks each new record; each line ends in a dot labelled with its current
model and score; a legend above names the lines.

Motion (`<chart>_specs`): the grey lines draw in together, then the open-weight line. One calendar clock drives every
line, so all lines stay in step. When the clock passes a record, that line's riser grows upward over a fraction of a
second (taller jumps take a little longer), and the new horizontal stretch rides up with its tip, so no riser snaps
in. On the open-weight line the clock pauses at each handover to a new model family: the riser climbs, a ring
pulses from the dot, and the family's name (GLM, Qwen, ...) pops in and fades when the next family takes over. The
last name gives way to the end label, so the final frame (also the still) shows end labels only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import altair as alt
import polars as pl
from analysis import OPEN, TB

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit, fit_size
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX, NAME_PX = 16, 14, 13
# The labs in greys (distinct, but telling them apart is not the point); the open-weight line in the accent, heavier.
GREYS = {"Anthropic": "#C3C8D3", "OpenAI": "#9AA0AE", "Google": "#7A8090", "Meta": "#5F6575"}
LAB_STROKE, OPEN_STROKE = 2.0, 4.0
FPS = 30


@dataclass(frozen=True)
class Pace:
    """Seconds per phase of the motion."""

    grey: float  # grey lines drawing in
    open: float  # open-weight line drawing in, not counting the holds
    hold: float  # pause at each handover once its riser has landed (the pulse and the name)
    intro: float = 0.5  # empty axes
    grey_labels: float = 0.5  # grey end labels fading in
    pause: float = 1.0  # between the grey lines and the open-weight line (the labels fade in during it)
    end_label: float = 0.5  # the open-weight end label fading in, the last name fading out
    final_hold: float = 3.0


PACE = {TB: Pace(grey=3.5, open=3.5, hold=0.8)}


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _ink(series: str) -> str:
    return color("accent") if series == OPEN else GREYS[series]


def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _clamp(t: float) -> float:
    return min(max(t, 0.0), 1.0)


def _spread(values: list[float], gap: float, lo: float) -> list[float]:
    """Label positions (same order as values, sorted high to low) at least `gap` apart, pushed up from `lo`."""
    out: list[float] = []
    for v in values:
        out.append(min(v, out[-1] - gap) if out else v)
    shift = lo - out[-1] if out and out[-1] < lo else 0.0
    return [y + shift for y in out]


# ---- static -----------------------------------------------------------------------------------------------------


def terminal_bench(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    return fit(lambda w, h: _frame(story, TB, w, h, font_scale, final_state(story, TB), interactive), width, height)


def terminal_bench_specs(story: Story, width, height, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    return _specs(story, TB, width, height, font_scale)


# ---- data shared by every frame ---------------------------------------------------------------------------------


def _lines(story: Story, metric: str) -> dict[str, list[dict]]:
    """Per series, its steps in date order: {t, score, model, family, variant, carried}."""
    d = story.frames["steps"].filter(pl.col("metric") == metric).sort("date")
    return {
        s: [r | {"t": _ms(r["date"])} for r in d.filter(pl.col("series") == s).iter_rows(named=True)]
        for s in story.extra["series"]
    }


def _top(story: Story, metric: str) -> int:
    hi = float(story.frames["steps"].filter(pl.col("metric") == metric)["score"].max())
    return (int(hi / 10) + 2) * 10  # headroom for the top end label


def final_state(story: Story, metric: str) -> dict:
    """Everything drawn, no names: the last frame of the motion and the static chart."""
    end = _ms(story.as_of)
    lines, dots = {}, []
    for s, steps in _lines(story, metric).items():
        pts = [(steps[0]["t"], steps[0]["score"])]
        for prev, r in zip(steps, steps[1:], strict=False):
            pts += [(r["t"], prev["score"]), (r["t"], r["score"])]
        lines[s] = [*pts, (end, steps[-1]["score"])]
        dots += [
            {"series": s, "t": r["t"], "score": r["score"], "op": 1.0, **_meta(r)} for r in steps if not r["carried"]
        ]
    return {"lines": lines, "dots": dots, "head": [], "names": [], "rings": [], "end_op": {s: 1.0 for s in lines}}


def _meta(r: dict) -> dict:
    return {"variant": r["variant"], "lab": r["lab"], "released": str(r["date"])}


# ---- one frame --------------------------------------------------------------------------------------------------


def _frame(story: Story, metric: str, width: float, height: float, fs: float, st: dict, interactive=False) -> alt.Chart:
    fonts = brand()["fonts"]
    series = story.extra["series"]
    d = story.frames["steps"].filter(pl.col("metric") == metric)
    first, last = d["date"].min(), story.as_of

    clr = alt.Color("series:N", scale=alt.Scale(domain=series, range=[_ink(s) for s in series]), legend=None)
    legend = alt.Legend(
        orient="top", direction="horizontal", title=None, labelFontSize=LABEL_PX * fs, symbolType="stroke",
        symbolSize=260 * fs, symbolStrokeWidth=3 * fs, columnPadding=22 * fs, offset=14 * fs, labelColor=color("text"),
        labelLimit=0,
    )  # fmt: skip
    ends = d.sort("date").group_by("series", maintain_order=True).last()
    label_chars = max(len(f"{m}  00.0") for m in ends["model"])
    label_px = (12 + label_chars * 0.56 * LABEL_PX + 6) * fs
    plot_px = max(width - label_px, 1.0)
    pad = (last - first) * (label_px / plot_px)
    x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(last + pad)])
    months = (1, 4, 7, 10) if plot_px >= 1000 * fs or last.year == first.year else (1, 7)
    ticks = [
        q for y in range(first.year, last.year + 1) for m in months if first <= (q := datetime(y, m, 1).date()) <= last
    ]  # fmt: skip
    top = _top(story, metric)
    x_axis = alt.Axis(
        values=[_ms(q) for q in ticks],
        labelExpr=(
            "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
        ),
        labelFontSize=AXIS_PX * fs,
        grid=False,
    )
    y_axis = alt.Axis(
        values=list(range(0, top + 1, 10)),
        labelFontSize=AXIS_PX * fs,
        title=story.extra["y_titles"][metric],
        titlePadding=12 * fs,
        grid=True,
    )
    x = alt.X("t:T", title=None, scale=x_scale, axis=x_axis)
    y_scale = alt.Scale(domain=[0, top], nice=False)
    y = alt.Y("score:Q", scale=y_scale, axis=y_axis)
    op = alt.Opacity("op:Q", scale=None)

    def data(rows: list[dict]) -> alt.Data:
        return alt.Data(values=rows)

    def line_rows(names: list[str]) -> list[dict]:
        return [
            {"series": s, "i": i, "t": t, "score": v} for s in names for i, (t, v) in enumerate(st["lines"].get(s, []))
        ]

    greys = [s for s in series if s != OPEN]
    # Lines and dots are not clipped: clipping at the plot edge would cut the half of a stroke that runs along 0.
    # The grey layer carries the legend (one shared colour scale, so it lists every series); the open line on top.
    grey_lines = (
        alt.Chart(data(line_rows(greys)))
        .mark_line(strokeWidth=LAB_STROKE * fs)
        .encode(x=x, y=y, color=clr.legend(legend), detail="series:N", order="i:Q")
    )
    open_line = (
        alt.Chart(data(line_rows([OPEN])))
        .mark_line(strokeWidth=OPEN_STROKE * fs)
        .encode(x=x, y=y, color=clr, detail="series:N", order="i:Q")
    )
    grey_dots = (
        alt.Chart(data([r for r in st["dots"] if r["series"] != OPEN]))
        .mark_circle(size=26 * fs**2)
        .encode(x=x, y=y, color=clr, opacity=op)
    )
    open_dots = (
        alt.Chart(data([r for r in st["dots"] if r["series"] == OPEN]))
        .mark_circle(size=60 * fs**2)
        .encode(x=x, y=y, color=clr, opacity=op)
    )
    if interactive:
        tips = [
            alt.Tooltip("series:N", title="Line"),
            alt.Tooltip("variant:N", title="Model"),
            alt.Tooltip("lab:N", title="Lab"),
            alt.Tooltip("released:N", title="Released"),
            alt.Tooltip("score:Q", title="Score", format=".1f"),
        ]
        grey_dots, open_dots = grey_dots.encode(tooltip=tips), open_dots.encode(tooltip=tips)
    head = alt.Chart(data(st["head"])).mark_circle(size=70 * fs**2, color=color("accent"), opacity=1).encode(x=x, y=y)
    rings = (
        alt.Chart(data(st["rings"]))
        .mark_point(shape="circle", filled=False, color=color("accent"), strokeWidth=2 * fs, clip=True)
        .encode(x=x, y=y, size=alt.Size("size:Q", scale=None), opacity=op)
    )

    # Model family names: centred over the dot, lifted clear of it, with a canvas-coloured halo drawn first so a grey
    # line passing behind breaks around the letters. Size and opacity per frame (the pop-in, the fade).
    style = {"align": "center", "baseline": "bottom", "dy": -10 * fs, "font": fonts["body"], "fontWeight": 600,
             "clip": True}  # fmt: skip
    size = alt.Size("px:Q", scale=None)
    names = data(st["names"])
    halo = (
        alt.Chart(names)
        .mark_text(**style, color=color("canvas"), stroke=color("canvas"), strokeWidth=5 * fs, strokeJoin="round")
        .encode(x=x, y=y, text="family:N", size=size, opacity=op)
    )
    name_text = (
        alt.Chart(names)
        .mark_text(**style, color=color("accent"))
        .encode(x=x, y=y, text="family:N", size=size, opacity=op)
    )

    # End labels, one line each: "<model> <score>" in the line's colour (the legend names the lines). Positions are
    # fixed (laid out for all five), so a label never moves when it fades in.
    lab = ends.sort("score", descending=True)
    gap = 1.3 * LABEL_PX * fs * top / height
    lab = lab.with_columns(
        label_y=pl.Series(_spread([min(v, top - 0.5 * gap) for v in lab["score"]], gap, 0.5 * gap)),
        text=pl.col("model") + "  " + pl.col("score").round(1).cast(pl.String),
        t=pl.lit(_ms(last)),
        op=pl.col("series").replace_strict(st["end_op"], return_dtype=pl.Float64),
    ).select("series", "score", "label_y", "text", "t", "op")
    lab_data = data(lab.to_dicts())
    end_dot = (
        alt.Chart(lab_data)
        .mark_circle(size=70 * fs**2, stroke=color("canvas"), strokeWidth=2)
        .encode(x=x, y=y, color=clr, opacity=op)
    )
    text = (
        alt.Chart(lab_data)
        .mark_text(align="left", baseline="middle", dx=12 * fs, fontSize=LABEL_PX * fs, font=fonts["body"],
                   fontWeight=600)
        .encode(x=x, y=alt.Y("label_y:Q", scale=y_scale, axis=y_axis), text="text:N", color=clr, opacity=op)
    )  # fmt: skip
    chart = alt.layer(
        grey_lines, grey_dots, open_line, open_dots, rings, head, end_dot, text, halo, name_text
    ).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))


# ---- motion -----------------------------------------------------------------------------------------------------


def _frames(s: float) -> int:
    return max(round(s * FPS), 1)


def _riser_frames(dy: float, top: float, slow: bool = False) -> int:
    """Frames a riser takes to grow: grey 0.13 s plus up to 0.33 s more for a full-height jump; the open-weight line
    (``slow``) 0.27 s plus up to 0.4 s more, so its climbs read as the event."""
    if slow:
        return min(max(round(8 + 12 * abs(dy) / top), 8), 20)
    return min(max(round(4 + 10 * abs(dy) / top), 4), 14)


def _crossings(clock: list[float | None], steps: list[dict]) -> list[int | None]:
    """The first frame at which the clock reaches each step's date (None: never in this phase)."""
    out = []
    for r in steps:
        out.append(next((f for f, c in enumerate(clock) if c is not None and c >= r["t"]), None))
    return out


def _draw(
    steps: list[dict], cross: list[int | None], clock: float | None, f: int, top: float, slow: bool
) -> tuple[list, list]:
    """The line's vertices and its record dots at frame f: risers grow from their crossing frame, the tip rides up."""
    if clock is None:
        return [], []
    vis = [(r, cf) for r, cf in zip(steps, cross, strict=True) if cf is not None and cf <= f]
    if not vis:
        return [], []
    levels, dots = [], []
    for k, (r, cf) in enumerate(vis):
        if k == 0:
            p = 1.0
            lvl = r["score"]
        else:
            p = ease_out(_clamp((f - cf) / _riser_frames(r["score"] - vis[k - 1][0]["score"], top, slow)))
            lvl = vis[k - 1][0]["score"] + (r["score"] - vis[k - 1][0]["score"]) * p
        levels.append(lvl)
        if not r["carried"]:
            dots.append((r, lvl, p))
    pts = [(vis[0][0]["t"], levels[0])]
    for k in range(1, len(vis)):
        pts += [(vis[k][0]["t"], levels[k - 1]), (vis[k][0]["t"], levels[k])]
    pts.append((clock, levels[-1]))
    return pts, dots


def _schedule(story: Story, metric: str) -> dict:
    """Per frame: the grey clock, the open-weight clock, and the frames of the phase boundaries and handovers."""
    pace = PACE[metric]
    lines = _lines(story, metric)
    t0, t1 = float(min(r["t"] for st in lines.values() for r in st)), float(_ms(story.as_of))

    grey: list[float | None] = [None] * _frames(pace.intro)
    g = _frames(pace.grey)
    grey += [t0 + (t1 - t0) * ease_in_out(k / (g - 1)) for k in range(g)]
    grey_done = len(grey)
    open_start = grey_done + _frames(pace.pause)
    opn: list[float | None] = [None] * open_start

    # Handovers: the open line's first step and every step that passes the record to another family.
    steps = lines[OPEN]
    # A score of 0 is no record to announce (on Terminal-Bench every model scored 0 before 2026).
    events = [i for i, r in enumerate(steps) if r["score"] > 0 and (i == 0 or r["family"] != steps[i - 1]["family"])]
    # The clock pauses at each handover while its riser climbs, then for the hold; the pulse and the name fire on the
    # frame the riser lands (event_frames).
    hold, v, top = _frames(pace.hold), (t1 - t0) / _frames(pace.open), _top(story, metric)
    event_frames, c, k = {}, t0, 0
    while True:
        while k < len(events) and steps[events[k]]["t"] <= c:
            i = events[k]
            rise = _riser_frames(steps[i]["score"] - steps[i - 1]["score"], top, slow=True) if i > 0 else 0
            event_frames[i] = len(opn) + rise
            opn += [c] * (rise + hold)
            k += 1
        if c >= t1:
            break
        nxt = steps[events[k]]["t"] if k < len(events) else t1
        c = min(c + v, t1, max(nxt, c))
        opn.append(c)
    open_done = len(opn)
    total = open_done + _frames(pace.end_label) + _frames(pace.final_hold)
    grey += [t1] * (total - len(grey))
    opn += [t1] * (total - len(opn))
    return {
        "lines": lines, "grey": grey, "open": opn, "grey_done": grey_done, "open_done": open_done,
        "events": event_frames, "total": total, "t0": t0, "t1": t1,
    }  # fmt: skip


def _state(story: Story, metric: str, sch: dict, f: int, cross: dict) -> dict:
    pace, top = PACE[metric], _top(story, metric)
    lines, dots, head, names, rings = {}, [], [], [], []
    for s, steps in sch["lines"].items():
        clock = (sch["open"] if s == OPEN else sch["grey"])[f]
        pts, ds = _draw(steps, cross[s], clock, f, top, slow=s == OPEN)
        lines[s] = pts
        dots += [{"series": s, "t": r["t"], "score": lvl, "op": p, **_meta(r)} for r, lvl, p in ds]
        if s == OPEN and pts and f < sch["open_done"]:
            head.append({"t": pts[-1][0], "score": pts[-1][1]})

    # Handover emphasis, from the frame its riser lands: a ring pulses out from the record; the name pops in oversized,
    # settles, and fades when the next family's riser lands (the last one when the end label fades in).
    steps = sch["lines"][OPEN]
    order = sorted(sch["events"].items(), key=lambda kv: kv[1])
    for n, (i, fe) in enumerate(order):
        if f < fe:
            continue
        r = steps[i]
        fade_at = order[n + 1][1] if n + 1 < len(order) else sch["open_done"]
        opacity = _clamp((f - fe) / 4) * (1 - _clamp((f - fade_at) / 8))
        tip = next((d["score"] for d in dots if d["series"] == OPEN and d["t"] == r["t"]), r["score"])
        if opacity > 0:
            pop = 1 + 0.5 * (1 - ease_out(_clamp((f - fe) / 10)))
            # A name at the window's start is nudged right so its centred text is not clipped by the plot edge.
            t = max(r["t"], sch["t0"] + 0.025 * (sch["t1"] - sch["t0"]))
            names.append({"t": t, "score": tip, "family": r["family"], "op": opacity, "px": NAME_PX * pop})
        k = f - fe
        if k <= 14:
            e = ease_out(k / 14)
            rings.append({"t": r["t"], "score": r["score"], "size": 60 + 1100 * e, "op": 0.85 * (1 - e)})

    grey_op = _clamp((f - sch["grey_done"]) / _frames(pace.grey_labels))
    open_op = _clamp((f - sch["open_done"]) / _frames(pace.end_label))
    end_op = {s: open_op if s == OPEN else grey_op for s in sch["lines"]}
    return {"lines": lines, "dots": dots, "head": head, "names": names, "rings": rings, "end_op": end_op}


def _specs(story: Story, metric: str, width, height, fs: float) -> tuple[list[dict], int]:
    # Fit once on the final frame; every frame keeps its layers and fixed scales, so its outer size is the same.
    w, h = fit_size(lambda a, b: _frame(story, metric, a, b, fs, final_state(story, metric)), width, height)
    sch = _schedule(story, metric)
    cross = {s: _crossings(sch["open"] if s == OPEN else sch["grey"], steps) for s, steps in sch["lines"].items()}
    fin = final_state(story, metric)
    specs = []
    for f in range(sch["total"]):
        st = _state(story, metric, sch, f, cross)
        if f == sch["total"] - 1:
            st = fin  # the last frame is exactly the static chart
        st["rings"] = [r | {"size": r["size"] * fs**2} for r in st["rings"]]
        specs.append(_frame(story, metric, w, h, fs, st).to_dict())
    return specs, FPS

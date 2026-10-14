"""Charts for the CoreWeave credit exploration (render contract: src/cachereg/render.py).

Two panels on the same dates, each with its own single y-axis (never a dual axis): side by side in
landscape (X), stacked on one date axis in portrait (LinkedIn). The bond's daily yield and the stock's
daily close, both in the accent, with the start, end (and the stock's peak) labelled directly. A dashed
slope from each line's first to its last point carries the change ("+5.7 pts", "−44%"), placed by `_place`
clear of every other mark.

Video (`panels_specs`): the yield line draws, its end labels fade in; then the stock line; then both
slopes flash from start to end in a few frames as solid white beams, hold while their change labels fade in,
and fade into the dashed grey guides.
A hold on the final frame, which equals the static chart. Every frame draws every mark (hidden ones at
opacity 0) at the final frame's fitted size, so the canvas never moves.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import altair as alt

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit, fit_size
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX, TITLE_PX, SUB_PX, SLOPE_PX = 24, 17, 26, 19, 21
BEAM, GUIDE = "#FFFFFF", "#5B6070"  # the flash: a solid white beam; what stays: a muted dashed guide
FPS = 30
INTRO_S, LINE_S, LABEL_S, PAUSE_S = 0.6, 3.0, 0.5, 0.5
FLASH_S, BEAM_HOLD_S, FADE_S, FINAL_HOLD_S = 0.2, 0.35, 0.9, 3.0
FINAL = {  # the final frame (and the static chart)
    "yield": {"until": math.inf, "start": 1.0, "end": 1.0, "slope": 1.0, "beam": 0.0, "guide": 1.0, "change": 1.0},
    "stock": {"until": math.inf, "start": 1.0, "end": 1.0, "slope": 1.0, "beam": 0.0, "guide": 1.0, "change": 1.0},
}


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _smooth(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _y_range(pts: list[tuple[float, float]], x0: float, x1: float) -> tuple[float, float] | None:
    """Min and max y of a pixel polyline (sorted by x) over x0..x1, or None if it does not reach there."""
    ys = []
    for (xa, ya), (xb, yb) in zip(pts, pts[1:], strict=False):
        if xb < x0 or xa > x1:
            continue
        for xx in (max(xa, x0), min(xb, x1)):
            ys.append(ya + (yb - ya) * ((xx - xa) / (xb - xa) if xb != xa else 0.0))
    return (min(ys), max(ys)) if ys else None


def _place(line_px, slope_px, avoid, text: str, font_px: float, w: float, h: float, fs: float):
    """A spot for a slope's change label: the candidate nearest mid-slope whose box clears the data line, the
    slope, every other label, dot and leader (`avoid`, pixel boxes) and the plot edge. Returns (fraction along
    the slope, dy in px from it)."""
    tw, th, m = len(text) * 0.6 * font_px, font_px, 10 * fs  # monospace advance: 0.6 em; m = clearance
    (ax, ay), (bx, by) = slope_px
    fracs = sorted((f / 20 for f in range(3, 18)), key=lambda f: abs(f - 0.5))
    for gap in (10 * fs, 20 * fs, 34 * fs, 52 * fs):
        for f in fracs:
            sx, sy = ax + (bx - ax) * f, ay + (by - ay) * f
            for side in (-1, 1):
                cy = sy + side * (th / 2 + gap)
                box = (sx - tw / 2 - m, cy - th / 2 - m, sx + tw / 2 + m, cy + th / 2 + m)
                if box[0] < 0 or box[2] > w or box[1] < 0 or box[3] > h:
                    continue
                if any(
                    (r := _y_range(poly, box[0], box[2])) and r[0] - 4 * fs < box[3] and r[1] + 4 * fs > box[1]
                    for poly in (line_px, slope_px)
                ):
                    continue
                if any(box[0] < o[2] and box[2] > o[0] and box[1] < o[3] and box[3] > o[1] for o in avoid):
                    continue
                return f, cy - sy
    raise ValueError(f"no clear spot for the change label {text!r}")


def _label_box(px: float, py: float, text: str, align: str, baseline: str, dx: float, dy: float, font_px: float):
    """The pixel box of a text label (monospace)."""
    tw, th = len(text) * 0.6 * font_px, font_px
    x0 = px + dx - (tw if align == "right" else tw / 2 if align == "center" else 0)
    y0 = py + dy - (0 if baseline == "top" else th / 2)
    return (x0, y0, x0 + tw, y0 + th)


def _drawn(points: list[dict], field: str, until: float) -> list[dict]:
    """A line's points up to time `until`, ending at an interpolated tip."""
    out = []
    for a, b in zip(points, points[1:] + [None], strict=True):
        if a["t"] > until:
            break
        out.append(a)
        if b is not None and b["t"] > until:
            k = (until - a["t"]) / (b["t"] - a["t"])
            out.append({"t": until, field: a[field] + (b[field] - a[field]) * k})
            break
    return out


def _panel(rows, field, title, subtitle, fmt_axis, domain, labels, change, t_dom, w, h, fs, st, x_labels=True):
    """One panel in frame state `st` (see FINAL). labels: (row, text, align, dx, dy, at, group); `at` = a y
    value to drop the label to on a leader line; group = which state opacity shows it (start | end)."""
    fonts = brand()["fonts"]
    y_scale = alt.Scale(domain=domain, nice=False, zero=False)
    x_scale = alt.Scale(type="utc", domain=list(t_dom))

    def px(t: float) -> float:
        return (t - t_dom[0]) / (t_dom[1] - t_dom[0]) * w

    def py(v: float) -> float:
        return h * (1 - (v - domain[0]) / (domain[1] - domain[0]))

    x = alt.X("t:T", title=None, scale=x_scale,
              axis=alt.Axis(format="%b", tickCount="month", labelFontSize=AXIS_PX * fs, labels=x_labels))  # fmt: skip
    y = alt.Y(f"{field}:Q", title=None, scale=y_scale,
              axis=alt.Axis(tickCount=5, labelFontSize=AXIS_PX * fs, labelExpr=fmt_axis,
                            minExtent=52 * fs))  # same axis width in both panels, so stacked plots align  # fmt: skip
    pts_all = [{"t": _ms(r["date"]), field: r[field]} for r in rows]
    drawn = _drawn(pts_all, field, st["until"]) or [pts_all[0]]
    line = (
        alt.Chart(alt.Data(values=drawn))
        .mark_line(color=color("accent"), strokeWidth=3 * fs, opacity=1 if st["until"] >= pts_all[0]["t"] else 0)
        .encode(x=x, y=y)
    )

    # slope: first → last point, drawn to fraction st["slope"]: a solid white beam with a soft glow that
    # cross-fades into the dashed grey guide that stays
    a, b = pts_all[0], pts_all[-1]
    p = st["slope"]
    tip = {"t": a["t"] + (b["t"] - a["t"]) * p, field: a[field] + (b[field] - a[field]) * p}
    seg, shown = alt.Data(values=[a, tip]), p > 0
    glow = alt.Chart(seg).mark_line(color=BEAM, strokeWidth=16 * fs, strokeCap="round",
                                    opacity=0.22 * st["beam"] if shown else 0).encode(x=x, y=y)  # fmt: skip
    beam = alt.Chart(seg).mark_line(color=BEAM, strokeWidth=5 * fs, strokeCap="round",
                                    opacity=st["beam"] if shown else 0).encode(x=x, y=y)  # fmt: skip
    guide = alt.Chart(seg).mark_line(color=GUIDE, strokeWidth=2 * fs, strokeDash=[10 * fs, 7 * fs],
                                     opacity=st["guide"] if shown else 0).encode(x=x, y=y)  # fmt: skip

    pts = [{"t": _ms(r["date"]), field: r[field], "label": text, "dx": dx, "dy": dy, "align": al,
            "at": r[field] if at is None else at, "op": st[group]}
           for r, text, al, dx, dy, at, group in labels]  # fmt: skip
    dots = (
        alt.Chart(alt.Data(values=pts))
        .mark_circle(size=140 * fs**2, color=color("accent"), stroke=color("canvas"), strokeWidth=3)
        .encode(x=x, y=y, opacity=alt.Opacity("op:Q", scale=None))
    )
    leaders = (
        alt.Chart(alt.Data(values=[p for p in pts if p["at"] != p[field]] or [pts[0] | {"op": 0}]))
        .mark_rule(color=color("muted"), strokeWidth=1.5 * fs)
        .encode(x=x, y=alt.Y("at:Q", scale=y_scale), y2=f"{field}:Q", opacity=alt.Opacity("op:Q", scale=None))
    )
    texts = [
        alt.Chart(alt.Data(values=[p]))
        .mark_text(align=p["align"], baseline="top" if p["at"] != p[field] else "middle", dx=p["dx"] * fs,
                   dy=p["dy"] * fs, fontSize=LABEL_PX * fs, font=fonts["mono"], fontWeight="bold", color=color("text"),
                   opacity=p["op"])
        .encode(x=x, y=alt.Y("at:Q", scale=y_scale), text="label:N")
        for p in pts
    ]  # fmt: skip
    avoid = []  # pixel boxes of every other label, dot and leader in the panel
    for q in pts:
        r, qx, qy = 8 * fs, px(q["t"]), py(q[field])
        avoid.append((qx - r, qy - r, qx + r, qy + r))
        base = "top" if q["at"] != q[field] else "middle"
        avoid.append(_label_box(qx, py(q["at"]), q["label"], q["align"], base, q["dx"] * fs, q["dy"] * fs,
                                LABEL_PX * fs))  # fmt: skip
        if q["at"] != q[field]:
            avoid.append((qx - 3 * fs, qy, qx + 3 * fs, py(q["at"])))
    line_px = [(px(q["t"]), py(q[field])) for q in pts_all]
    slope_px = [(px(a["t"]), py(a[field])), (px(b["t"]), py(b[field]))]
    at, dy = _place(line_px, slope_px, avoid, change, SLOPE_PX * fs, w, h, fs)
    mid = {"t": a["t"] + (b["t"] - a["t"]) * at, field: a[field] + (b[field] - a[field]) * at, "label": change}
    change_text = (
        alt.Chart(alt.Data(values=[mid]))
        .mark_text(align="center", baseline="middle", dy=dy, fontSize=SLOPE_PX * fs, font=fonts["mono"],
                   fontWeight="bold", color=color("text"), opacity=st["change"])
        .encode(x=x, y=y, text="label:N")
    )  # fmt: skip
    t = alt.TitleParams(title, subtitle=subtitle, anchor="start", fontSize=TITLE_PX * fs, font=fonts["body"],
                        fontWeight=600, color=color("text"), subtitleFont=fonts["body"], subtitleFontSize=SUB_PX * fs,
                        subtitleColor=color("text_secondary"), offset=22 * fs, subtitlePadding=6 * fs)  # fmt: skip
    layers = [leaders, line, guide, glow, beam, dots, change_text, *texts]
    return alt.layer(*layers).properties(width=w, height=h, title=t)


def _panels(story: Story, width, height, fs: float, state: dict | None = None) -> alt.HConcatChart:
    state = state or FINAL
    bond = story.frames["bond"].to_dicts()
    stock = story.frames["stock"].to_dicts()
    t_dom = (_ms(bond[0]["date"]), _ms(stock[-1]["date"]))
    # LinkedIn (plot box ~1.3:1): stacked on one date axis; X (~2.9:1): side by side
    tall = width < 2 * height
    spacing = (56 if tall else 110) * fs
    if tall:
        w, h = max(width - 70 * fs, 1.0), max((height - spacing) / 2 - 90 * fs, 1.0)  # first guess; fit corrects
    else:
        w, h = max((width - spacing) / 2 - 60 * fs, 1.0), max(height - 110 * fs, 1.0)

    ys = [r["yield_pct"] for r in bond]
    y_dom = [math.floor(min(ys)) - 1, 2 * (max(ys) // 2 + 1)]  # room under the start label
    rise = bond[-1]["yield_pct"] - bond[0]["yield_pct"]
    left = _panel(bond, "yield_pct", "Bond yield", story.extra["bond_label"], "datum.value + '%'", y_dom,
                  [(bond[0], f"{bond[0]['yield_pct']:.1f}%", "left", 4, 30, None, "start"),
                   (bond[-1], f"{bond[-1]['yield_pct']:.1f}%", "right", -14, -24, None, "end")],
                  f"{rise:+.1f} pts", t_dom, w, h, fs, state["yield"],
                  x_labels=not tall)  # fmt: skip

    closes = [r["close"] for r in stock]
    s_dom = [20 * (min(closes) // 20) - 20, 20 * (max(closes) // 20 + 1)]
    peak = max(stock, key=lambda r: r["close"])
    drop = stock[0]["close"] - 0.3 * (s_dom[1] - s_dom[0])  # into the clear space under the early peak
    labels = [(stock[0], f"${stock[0]['close']:.2f}", "left", 8, 4, drop, "start"),
              (stock[-1], f"${stock[-1]['close']:.2f}", "right", -14, 32, None, "end")]  # fmt: skip
    if peak is not stock[0] and peak is not stock[-1]:
        labels.append((peak, f"${peak['close']:.2f}", "left", 14, 0, None, "end"))
    change = story.extra["stock_change_pct"]
    right = _panel(stock, "close", "Stock price", "CRWV daily close (US$)", "'$' + datum.value", s_dom, labels,
                   f"{'−' if change < 0 else '+'}{abs(change):.0f}%", t_dom, w, h, fs,
                   state["stock"])  # fmt: skip
    if tall:
        return alt.vconcat(left, right, spacing=spacing).configure(**vl_config(fs))
    return alt.hconcat(left, right, spacing=spacing).configure(**vl_config(fs))


def panels(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.HConcatChart:
    return fit(lambda w, h: _panels(story, w, h, font_scale), width, height)


def panels_specs(story: Story, width: int, height: int, font_scale: float, cfg: dict) -> tuple[list[dict], int]:
    """Frame states → one spec per frame, all at the final frame's fitted size (see the module docstring)."""
    fs = font_scale
    w, h = fit_size(lambda a, b: _panels(story, a, b, fs), width, height)
    t0, t1 = _ms(story.frames["bond"]["date"][0]), _ms(story.frames["stock"]["date"][-1])
    blank = {"until": -math.inf, "start": 0.0, "end": 0.0, "slope": 0.0, "beam": 1.0, "guide": 0.0, "change": 0.0}
    state = {"yield": dict(blank), "stock": dict(blank)}
    states: list[dict] = []

    def snap() -> None:
        states.append({k: dict(v) for k, v in state.items()})

    def frames(seconds: float) -> int:
        return max(int(round(seconds * FPS)), 1)

    for _ in range(frames(INTRO_S)):
        snap()
    for key in ("yield", "stock"):
        state[key]["start"] = 1.0
        n = frames(LINE_S)
        for i in range(n):  # one calendar speed: both lines span the same dates
            state[key]["until"] = t0 + (t1 - t0) * _smooth((i + 1) / n)
            snap()
        state[key]["until"] = math.inf
        n = frames(LABEL_S)
        for i in range(n):
            state[key]["end"] = _smooth((i + 1) / n)
            snap()
        for _ in range(frames(PAUSE_S)):
            snap()
    n = frames(FLASH_S)  # the beams shoot from start to end in a few frames
    for i in range(n):
        for key in state:
            state[key]["slope"] = (i + 1) / n
        snap()
    n = frames(BEAM_HOLD_S)  # they hold while the change labels fade in
    for i in range(n):
        for key in state:
            state[key]["change"] = _smooth((i + 1) / n)
        snap()
    n = frames(FADE_S)  # then fade into the dashed guides
    for i in range(n):
        u = _smooth((i + 1) / n)
        for key in state:
            state[key]["beam"], state[key]["guide"] = 1 - u, u
        snap()
    for _ in range(frames(FINAL_HOLD_S)):
        snap()
    if states[-1] != FINAL:
        raise ValueError("coreweave-credit: the final frame must equal the static chart")
    return [_panels(story, w, h, fs, state=st).to_dict() for st in states], FPS

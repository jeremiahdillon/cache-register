"""Charts for the CoreWeave credit exploration (render contract: src/cachereg/render.py).

Two panels on the same dates, each with its own single y-axis (never a dual axis): side by side in
landscape (X), stacked on one date axis in portrait (LinkedIn). The bond's daily yield and the stock's
daily close, both in the accent, with the start, end (and the stock's peak) labelled directly.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import altair as alt

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit
from cachereg.viz.theme import vl_config

LABEL_PX, AXIS_PX, TITLE_PX, SUB_PX = 24, 17, 26, 19


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _panel(rows, field, title, subtitle, fmt_axis, domain, labels, x_scale, w, h, fs, x_labels=True):
    fonts = brand()["fonts"]
    x = alt.X("t:T", title=None, scale=x_scale,
              axis=alt.Axis(format="%b", tickCount="month", labelFontSize=AXIS_PX * fs, labels=x_labels))  # fmt: skip
    y = alt.Y(f"{field}:Q", title=None, scale=alt.Scale(domain=domain, nice=False, zero=False),
              axis=alt.Axis(tickCount=5, labelFontSize=AXIS_PX * fs, labelExpr=fmt_axis,
                            minExtent=52 * fs))  # same axis width in both panels, so stacked plots align  # fmt: skip
    data = [{"t": _ms(r["date"]), field: r[field]} for r in rows]
    line = alt.Chart(alt.Data(values=data)).mark_line(color=color("accent"), strokeWidth=3 * fs).encode(x=x, y=y)
    # labels: (row, text, align, dx, dy[, at]); `at` = a y value to drop the label to, on a leader line
    pts = [{"t": _ms(r["date"]), field: r[field], "label": text, "dx": dx, "dy": dy, "align": a,
            "at": rest[0] if rest else r[field]} for r, text, a, dx, dy, *rest in labels]  # fmt: skip
    dots = (
        alt.Chart(alt.Data(values=pts))
        .mark_circle(size=140 * fs**2, color=color("accent"), opacity=1, stroke=color("canvas"), strokeWidth=3)
        .encode(x=x, y=y)
    )
    leaders = (
        alt.Chart(alt.Data(values=[p for p in pts if p["at"] != p[field]]))
        .mark_rule(color=color("muted"), strokeWidth=1.5 * fs)
        .encode(x=x, y=alt.Y("at:Q", scale=alt.Scale(domain=domain, nice=False, zero=False)), y2=f"{field}:Q")
    )
    texts = [
        alt.Chart(alt.Data(values=[p]))
        .mark_text(align=p["align"], baseline="top" if p["at"] != p[field] else "middle", dx=p["dx"] * fs,
                   dy=p["dy"] * fs, fontSize=LABEL_PX * fs, font=fonts["mono"], fontWeight="bold", color=color("text"))
        .encode(x=x, y=alt.Y("at:Q", scale=alt.Scale(domain=domain, nice=False, zero=False)), text="label:N")
        for p in pts
    ]  # fmt: skip
    t = alt.TitleParams(title, subtitle=subtitle, anchor="start", fontSize=TITLE_PX * fs, font=fonts["body"],
                        fontWeight=600, color=color("text"), subtitleFont=fonts["body"], subtitleFontSize=SUB_PX * fs,
                        subtitleColor=color("text_secondary"), offset=22 * fs, subtitlePadding=6 * fs)  # fmt: skip
    return alt.layer(leaders, line, dots, *texts).properties(width=w, height=h, title=t)


def _panels(story: Story, width, height, fs: float) -> alt.HConcatChart:
    bond = story.frames["bond"].to_dicts()
    stock = story.frames["stock"].to_dicts()
    x_scale = alt.Scale(type="utc", domain=[_ms(bond[0]["date"]), _ms(stock[-1]["date"])])
    # LinkedIn (plot box ~1.3:1): stacked on one date axis; X (~2.9:1): side by side
    tall = width < 2 * height
    spacing = (56 if tall else 110) * fs
    if tall:
        w, h = max(width - 70 * fs, 1.0), max((height - spacing) / 2 - 90 * fs, 1.0)  # first guess; fit corrects
    else:
        w, h = max((width - spacing) / 2 - 60 * fs, 1.0), max(height - 110 * fs, 1.0)

    ys = [r["yield_pct"] for r in bond]
    y_dom = [math.floor(min(ys)) - 1, 2 * (max(ys) // 2 + 1)]  # room under the start label
    left = _panel(bond, "yield_pct", "Bond yield", story.extra["bond_label"], "datum.value + '%'", y_dom,
                  [(bond[0], f"{bond[0]['yield_pct']:.1f}%", "left", 4, 30),
                   (bond[-1], f"{bond[-1]['yield_pct']:.1f}%", "right", -14, -24)],
                  x_scale, w, h, fs, x_labels=not tall)  # fmt: skip

    closes = [r["close"] for r in stock]
    s_dom = [20 * (min(closes) // 20) - 20, 20 * (max(closes) // 20 + 1)]
    peak = max(stock, key=lambda r: r["close"])
    drop = stock[0]["close"] - 0.3 * (s_dom[1] - s_dom[0])  # into the clear space under the early peak
    labels = [(stock[0], f"${stock[0]['close']:.2f}", "left", 8, 4, drop),
              (stock[-1], f"${stock[-1]['close']:.2f}", "right", -14, 32)]  # fmt: skip
    if peak is not stock[0] and peak is not stock[-1]:
        labels.append((peak, f"${peak['close']:.2f}", "left", 14, 0))
    right = _panel(stock, "close", "Stock price", "CRWV daily close (US$)", "'$' + datum.value", s_dom, labels,
                   x_scale, w, h, fs)  # fmt: skip
    if tall:
        return alt.vconcat(left, right, spacing=spacing).configure(**vl_config(fs))
    return alt.hconcat(left, right, spacing=spacing).configure(**vl_config(fs))


def panels(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.HConcatChart:
    return fit(lambda w, h: _panels(story, w, h, font_scale), width, height)

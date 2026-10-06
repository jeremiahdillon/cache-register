"""Charts for the cost-of-intelligence exploration (render contract: src/cachereg/render.py).

Step lines on a log price axis, one per capability level: the headline level in the accent, the
others in greys. Each line ends in a dot with a direct label (level name and current price); the
start of each line names the model that set the first price in the window.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

import altair as alt
import polars as pl
from analysis import fmt_usd

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.theme import vl_config

GREYS = ["#858B9B", "#C3C8D3"]  # lower levels, darker to lighter (one lightness ramp)
LABEL_PX, AXIS_PX = 17, 15


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _ticks(lo: float, hi: float) -> list[float]:
    out = []
    for e in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1):
        for m in (1, 3):
            v = m * 10**e
            if lo <= v <= hi:
                out.append(v)
    return out


def steps(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    fs = font_scale
    fonts = brand()["fonts"]
    levels, names, hero = story.extra["levels"], story.extra["names"], story.extra["headline_level"]
    d = story.frames["daily"].sort("level", "day")
    first, last = d["day"].min(), d["day"].max()

    ink = dict(zip(sorted(x for x in levels if x != hero), GREYS, strict=False)) | {hero: color("accent")}
    order = [names[lv] for lv in levels]
    clr = alt.Color("name:N", scale=alt.Scale(domain=order, range=[ink[lv] for lv in levels]), legend=None)

    # Room on the right for end labels, in days on this chart's x scale.
    label_chars = max(len(f"{names[lv]}") for lv in levels) + 2
    label_px = (16 + label_chars * 0.55 * LABEL_PX + 12) * fs
    px = width if isinstance(width, int | float) else 900
    plot_px = max(px - 80 * fs - label_px, 1.0)
    pad = (last - first) * (label_px / plot_px)
    x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(last + pad)])
    quarters = [q for y in (2025, 2026) for m in (1, 4, 7, 10) if (q := datetime(y, m, 1).date()) <= last]
    x_axis = alt.Axis(
        values=[_ms(q) for q in quarters],
        labelExpr=(
            "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
        ),
        labelFontSize=AXIS_PX * fs,
        grid=False,
    )
    lo, hi = d["usd_per_mtok"].min() * 0.3, d["usd_per_mtok"].max() * 2.5
    y_scale = alt.Scale(type="log", domain=[lo, hi], nice=False)
    y_axis = alt.Axis(
        values=_ticks(lo, hi),
        labelExpr="datum.value >= 1 ? '$' + format(datum.value, ',.0f') : '$' + format(datum.value, '.2~f')",
        labelFontSize=AXIS_PX * fs,
        title="List price per million tokens (log scale)",
        titlePadding=14 * fs,
    )

    def xenc(field: str = "t") -> alt.X:
        return alt.X(f"{field}:T", title=None, scale=x_scale, axis=x_axis)

    def yenc(field: str = "usd_per_mtok") -> alt.Y:
        return alt.Y(f"{field}:Q", scale=y_scale, axis=y_axis)

    rows = d.with_columns(t=pl.col("day").map_elements(_ms, return_dtype=pl.Int64)).select(
        "t", "name", "level", "usd_per_mtok", "display_name"
    )
    data = alt.Data(values=rows.to_dicts())
    line = (
        alt.Chart(data)
        .mark_line(interpolate="step-after", strokeWidth=2.6 * fs)
        .encode(x=xenc(), y=yenc(), color=clr, detail="name:N")
    )
    if interactive:
        line = line.encode(
            tooltip=[
                alt.Tooltip("name:N", title="Level"),
                alt.Tooltip("t:T", title="Date", format="%b %-d, %Y"),
                alt.Tooltip("usd_per_mtok:Q", title="$ / M tokens", format=".3f"),
                alt.Tooltip("display_name:N", title="Cheapest model"),
            ]
        )

    # End labels: dot at the last value, "<level>" and "<price> · <model>" on two lines, nudged apart.
    ends = rows.group_by("name", maintain_order=True).last().sort("usd_per_mtok", descending=True)
    plot_h = max((height if isinstance(height, int | float) else 520) - 70 * fs, 1.0)
    span = math.log10(hi) - math.log10(lo)
    gap = 2.5 * LABEL_PX * fs * span / plot_h  # two text lines between labels, in log10 units
    ys, prev = [], None
    for v in ends["usd_per_mtok"]:
        y = math.log10(v)
        if prev is not None:
            y = min(y, prev - gap)
        ys.append(y)
        prev = y
    ends = ends.with_columns(
        label_y=pl.Series([10**y for y in ys]),
        price=pl.col("usd_per_mtok").map_elements(fmt_usd, return_dtype=pl.String),
    ).with_columns(sub=pl.col("price") + " · " + pl.col("display_name"))
    end_data = alt.Data(values=ends.to_dicts())
    dots = (
        alt.Chart(end_data)
        .mark_circle(size=80 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
        .encode(x=xenc(), y=yenc(), color=clr)
    )
    head = (
        alt.Chart(end_data)
        .mark_text(align="left", baseline="bottom", dx=14 * fs, dy=-1, fontSize=LABEL_PX * fs, font=fonts["body"])
        .encode(x=xenc(), y=yenc("label_y"), text="name:N", color=clr)
    )
    sub = (
        alt.Chart(end_data)
        .mark_text(align="left", baseline="top", dx=14 * fs, dy=3, fontSize=(LABEL_PX - 2) * fs, font=fonts["body"])
        .encode(x=xenc(), y=yenc("label_y"), text="sub:N", color=alt.value(color("text_secondary")))
    )

    # Start of each line: the model that first reached the level in the window.
    start = (
        rows.group_by("name", maintain_order=True)
        .first()
        .with_columns(
            txt=pl.col("display_name") + " " + pl.col("usd_per_mtok").map_elements(fmt_usd, return_dtype=pl.String)
        )
    )
    start_data = alt.Data(values=start.to_dicts())
    s_dot = (
        alt.Chart(start_data)
        .mark_circle(size=60 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
        .encode(x=xenc(), y=yenc(), color=clr)
    )
    s_txt = (
        alt.Chart(start_data)
        .mark_text(
            align="left", baseline="bottom", dx=2 * fs, dy=-8 * fs, fontSize=(LABEL_PX - 2) * fs, font=fonts["body"]
        )
        .encode(x=xenc(), y=yenc(), text="txt:N", color=alt.value(color("text_secondary")))
    )

    chart = alt.layer(line, dots, head, sub, s_dot, s_txt).properties(width=width, height=height)
    return chart.configure(**vl_config(fs))

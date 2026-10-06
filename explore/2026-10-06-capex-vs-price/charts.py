"""Charts for the capex-vs-price exploration (render contract: src/cachereg/render.py).

Two panels on one time axis, each with its own single y-axis (never a dual axis): quarterly
hyperscaler capex as bars spanning their calendar quarter (complete quarters only), and below it
the cheapest price per capability level as step lines on a log axis (the headline level in the
accent, the others in greys), each ending in a direct label.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import altair as alt
import polars as pl
from analysis import fmt_usd

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.theme import vl_config

GREYS = ["#858B9B", "#C3C8D3"]  # lower levels, darker to lighter (as the cost-of-intelligence chart)
BAR = "#5B6070"  # capex bars: recessive, so the accent line stays the one highlighted series
LABEL_PX, AXIS_PX = 17, 15
GAP = 0.32  # panel split: capex share of the plot height


def _ms(d) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _ticks(lo: float, hi: float) -> list[float]:
    return [
        m * 10**e
        for e in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1)
        for m in (1, 3)
        if lo <= m * 10**e <= hi
    ]


def _quarter_end(q):
    nxt = datetime(q.year + (q.month == 10), q.month + 3 if q.month < 10 else 1, 1).date()
    return nxt - timedelta(days=1)


def panels(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.VConcatChart:
    fs = font_scale
    fonts = brand()["fonts"]
    levels, names, hero = story.extra["levels"], story.extra["names"], story.extra["headline_level"]
    width = width if isinstance(width, int | float) else 880
    height = height if isinstance(height, int | float) else 560
    spacing = 28 * fs
    top_h = (height - spacing) * GAP
    bot_h = height - spacing - top_h

    d = story.frames["daily"].sort("level", "day")
    first, last = d["day"].min(), d["day"].max()
    label_chars = max(len(n) for n in names.values()) + 2
    label_px = (16 + label_chars * 0.55 * LABEL_PX + 12) * fs
    plot_px = max(width - 80 * fs - label_px, 1.0)
    pad = (last - first) * (label_px / plot_px)
    x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(last + pad)])
    quarters = [
        q
        for y in range(first.year, last.year + 1)
        for m in (1, 4, 7, 10)
        if first <= (q := datetime(y, m, 1).date()) <= last
    ]
    x_axis = alt.Axis(
        values=[_ms(q) for q in quarters],
        labelExpr=(
            "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
        ),
        labelFontSize=AXIS_PX * fs,
        grid=False,
    )
    no_x = alt.Axis(labels=False, grid=False, title=None)

    # --- top: capex bars, complete quarters only -------------------------------------------
    cap = story.frames["capex"].filter(pl.col("complete"))
    gap_days = 6
    bars = cap.with_columns(
        t0=pl.col("cal_quarter").map_elements(lambda q: _ms(q + timedelta(days=gap_days)), return_dtype=pl.Int64),
        t1=pl.col("cal_quarter").map_elements(
            lambda q: _ms(_quarter_end(q) - timedelta(days=gap_days)), return_dtype=pl.Int64
        ),
        bn=pl.col("capex_usd") / 1e9,
    ).with_columns(
        label=pl.format("${}bn", pl.col("bn").round(0).cast(pl.Int64)), tmid=((pl.col("t0") + pl.col("t1")) // 2)
    )
    bar_data = alt.Data(values=bars.select("t0", "t1", "tmid", "bn", "label").to_dicts())
    cap_scale = alt.Scale(domain=[0, bars["bn"].max() * 1.25])
    y_cap = alt.Y(
        "bn:Q",
        title="Capex per quarter ($bn)",
        axis=alt.Axis(labelFontSize=AXIS_PX * fs, tickCount=3, titlePadding=14 * fs),
        scale=cap_scale,
    )
    rect = (
        alt.Chart(bar_data)
        .mark_rect(color=BAR, cornerRadiusTopLeft=4 * fs, cornerRadiusTopRight=4 * fs)
        .encode(x=alt.X("t0:T", scale=x_scale, axis=no_x), x2="t1:T", y=y_cap, y2=alt.datum(0))
    )
    if interactive:
        rect = rect.encode(
            tooltip=[alt.Tooltip("label:N", title="Capex"), alt.Tooltip("t0:T", title="Quarter", format="%b %Y")]
        )
    ends = bars.filter((pl.col("t0") == bars["t0"].min()) | (pl.col("t0") == bars["t0"].max()))
    vals = (
        alt.Chart(alt.Data(values=ends.select("tmid", "bn", "label").to_dicts()))
        .mark_text(
            baseline="bottom",
            dy=-6 * fs,
            fontSize=(LABEL_PX - 1) * fs,
            font=fonts["body"],
            color=color("text_secondary"),
        )
        .encode(x=alt.X("tmid:T", scale=x_scale, axis=no_x), y=alt.Y("bn:Q", scale=cap_scale), text="label:N")
    )
    top = alt.layer(rect, vals).properties(width=width, height=top_h)

    # --- bottom: cheapest price per level ----------------------------------------------------
    ink = dict(zip(sorted(x for x in levels if x != hero), GREYS, strict=False)) | {hero: color("accent")}
    order = [names[lv] for lv in levels]
    clr = alt.Color("name:N", scale=alt.Scale(domain=order, range=[ink[lv] for lv in levels]), legend=None)
    lo, hi = d["usd_per_mtok"].min() * 0.25, d["usd_per_mtok"].max() * 2.0
    y_scale = alt.Scale(type="log", domain=[lo, hi], nice=False)
    y_axis = alt.Axis(
        values=_ticks(lo, hi),
        labelExpr="datum.value >= 1 ? '$' + format(datum.value, ',.0f') : '$' + format(datum.value, '.2~f')",
        labelFontSize=AXIS_PX * fs,
        title="Cheapest price per M tokens (log)",
        titlePadding=14 * fs,
    )

    def xenc(field: str = "t") -> alt.X:
        return alt.X(f"{field}:T", title=None, scale=x_scale, axis=x_axis)

    def yenc(field: str = "usd_per_mtok") -> alt.Y:
        return alt.Y(f"{field}:Q", scale=y_scale, axis=y_axis)

    rows = d.with_columns(t=pl.col("day").map_elements(_ms, return_dtype=pl.Int64)).select(
        "t", "name", "usd_per_mtok", "display_name"
    )
    line = (
        alt.Chart(alt.Data(values=rows.to_dicts()))
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
    last_rows = rows.group_by("name", maintain_order=True).last().sort("usd_per_mtok", descending=True)
    span = math.log10(hi) - math.log10(lo)
    gap = 2.5 * LABEL_PX * fs * span / max(bot_h, 1.0)
    ys, prev = [], None
    for v in last_rows["usd_per_mtok"]:
        y = math.log10(v) if prev is None else min(math.log10(v), prev - gap)
        ys.append(y)
        prev = y
    floor = math.log10(lo) + 0.8 * gap  # keep the lowest two-line label inside the plot
    for i in range(len(ys) - 1, -1, -1):
        ys[i] = max(ys[i], floor if i == len(ys) - 1 else ys[i + 1] + gap)
    last_rows = last_rows.with_columns(
        label_y=pl.Series([10**y for y in ys]),
        sub=pl.col("usd_per_mtok").map_elements(fmt_usd, return_dtype=pl.String) + " · " + pl.col("display_name"),
    )
    end_data = alt.Data(values=last_rows.to_dicts())
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
    bottom = alt.layer(line, dots, head, sub).properties(width=width, height=bot_h)

    chart = alt.vconcat(top, bottom, spacing=spacing).resolve_scale(x="shared")
    return chart.configure(**vl_config(fs))

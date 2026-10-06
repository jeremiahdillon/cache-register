"""Charts for the quality-vs-usage exploration (render contract: src/cachereg/render.py).

One ECI axis: the frontier (best model released so far) as a grey step line, the median paid token
in the accent with the middle half of tokens as a band, and a dashed bracket at the latest median
reaching back to when the frontier first got there (the lag; labelled with the headline's
13-week median, so it can differ slightly from the drawn latest week).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import altair as alt
import polars as pl

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.theme import vl_config

FRONTIER = "#C3C8D3"
LABEL_PX, AXIS_PX = 17, 15


def _ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def gap(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    fs = font_scale
    fonts = brand()["fonts"]
    w = story.frames["weekly"].sort("week")
    first, last = w["week"].min(), w["week"].max()
    end = w.row(-1, named=True)
    lag_start = last + timedelta(days=6) - timedelta(days=round(end["lag_months"] * 30.44))

    label_px = (16 + 22 * 0.55 * LABEL_PX + 12) * fs
    px = width if isinstance(width, int | float) else 900
    plot_px = max(px - 80 * fs - label_px, 1.0)
    pad = (last - first) * (label_px / plot_px)
    x0 = date(first.year, first.month, 1)  # start the axis on the month so its first tick is labelled
    x_scale = alt.Scale(type="utc", domain=[_ms(x0), _ms(last + pad)])
    quarters = [q for y in (2025, 2026) for m in (1, 4, 7, 10) if x0 <= (q := date(y, m, 1)) <= last]
    x_axis = alt.Axis(
        values=[_ms(q) for q in quarters],
        labelExpr=(
            "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
        ),
        labelFontSize=AXIS_PX * fs,
        grid=False,
    )
    lo = 5 * ((min(w["p25"].min(), w["frontier"].min()) - 3) // 5)
    hi = 5 * ((w["frontier"].max() + 7) // 5)
    y_scale = alt.Scale(domain=[lo, hi], nice=False, zero=False)
    y_axis = alt.Axis(tickCount=6, labelFontSize=AXIS_PX * fs, title="Epoch Capabilities Index", titlePadding=14 * fs)

    def xenc(field: str = "t") -> alt.X:
        return alt.X(f"{field}:T", title=None, scale=x_scale, axis=x_axis)

    def yenc(field: str) -> alt.Y:
        return alt.Y(f"{field}:Q", scale=y_scale, axis=y_axis)

    rows = w.with_columns(t=pl.col("week").map_elements(_ms, return_dtype=pl.Int64)).select(
        "t", "frontier", "best_on_openrouter", "p25", "p50", "p75", "lag_months", "near_frontier_share"
    )
    data = alt.Data(values=rows.to_dicts())
    accent = color("accent")
    band = (
        alt.Chart(data)
        .mark_area(interpolate="step-after", color=accent, opacity=0.18)
        .encode(x=xenc(), y=yenc("p25"), y2="p75:Q")
    )
    med = (
        alt.Chart(data)
        .mark_line(interpolate="step-after", color=accent, strokeWidth=2.6 * fs)
        .encode(x=xenc(), y=yenc("p50"))
    )
    front = (
        alt.Chart(data)
        .mark_line(interpolate="step-after", color=FRONTIER, strokeWidth=2.2 * fs)
        .encode(x=xenc(), y=yenc("frontier"))
    )
    layers = [band, front, med]
    if interactive:
        layers.append(
            alt.Chart(data)
            .mark_rule(opacity=0)
            .encode(
                x=xenc(),
                tooltip=[
                    alt.Tooltip("t:T", title="Week of", format="%b %-d, %Y"),
                    alt.Tooltip("frontier:Q", title="Frontier ECI"),
                    alt.Tooltip("p50:Q", title="Median token ECI"),
                    alt.Tooltip("lag_months:Q", title="Lag (months)", format=".1f"),
                    alt.Tooltip("near_frontier_share:Q", title="Near-frontier share", format=".0%"),
                ],
            )
        )

    # Lag bracket at the latest median ECI: from the frontier's first release at that level to now.
    bracket = pl.DataFrame({"t0": [_ms(lag_start)], "t1": [_ms(last)], "y": [end["p50"]]})
    b_data = alt.Data(values=bracket.to_dicts())
    layers.append(
        alt.Chart(b_data)
        .mark_rule(color=color("text_secondary"), strokeDash=[5 * fs, 4 * fs], strokeWidth=1.4 * fs)
        .encode(x=xenc("t0"), x2="t1:T", y=yenc("y"))
    )
    layers.append(
        alt.Chart(b_data)
        .mark_text(align="center", baseline="top", dy=8 * fs, fontSize=(LABEL_PX - 1) * fs, font=fonts["body"])
        .encode(
            x=alt.X("tm:T", scale=x_scale, axis=x_axis, title=None),
            y=yenc("y"),
            text=alt.value(f"≈{round(story.extra['summary']['lag_months'])} months"),
            color=alt.value(color("text_secondary")),
        )
        .transform_calculate(tm="(datum.t0 + datum.t1) / 2")
    )

    ends = pl.DataFrame(
        {
            "t": [_ms(last), _ms(last)],
            "y": [end["frontier"], end["p50"]],
            "name": ["Frontier", "Median paid token"],
            "sub": [f"ECI {end['frontier']:.0f} · best released", f"ECI {end['p50']:.0f} · middle half shaded"],
            "c": [FRONTIER, accent],
        }
    )
    e_data = alt.Data(values=ends.to_dicts())
    clr = alt.Color("c:N", scale=None, legend=None)
    layers += [
        alt.Chart(e_data)
        .mark_circle(size=80 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
        .encode(x=xenc(), y=yenc("y"), color=clr),
        alt.Chart(e_data)
        .mark_text(align="left", baseline="bottom", dx=14 * fs, dy=-1, fontSize=LABEL_PX * fs, font=fonts["body"])
        .encode(x=xenc(), y=yenc("y"), text="name:N", color=clr),
        alt.Chart(e_data)
        .mark_text(align="left", baseline="top", dx=14 * fs, dy=3, fontSize=(LABEL_PX - 2) * fs, font=fonts["body"])
        .encode(x=xenc(), y=yenc("y"), text="sub:N", color=alt.value(color("text_secondary"))),
    ]
    return alt.layer(*layers).properties(width=width, height=height).configure(**vl_config(fs))

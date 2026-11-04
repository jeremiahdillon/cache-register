"""Charts for the election-day split exploration (render contract: src/cachereg/render.py).

`session`: every stock as a % change from Tuesday's close on one time axis. A short, steep segment of each line
crosses the overnight gap and the first 5 minutes, from the previous close to the first bar's end. Colour
carries the group (categorical slots 1 and 2, validated on the canvas; no vendor appears here), the S&P
baseline is the text colour, and each line is named at its end, with labels spread apart and tied back by
thin leaders.
"""

from __future__ import annotations

import altair as alt
from analysis import SESSION_MIN

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit
from cachereg.viz.theme import vl_config

OVERNIGHT = -3  # x position of the previous close, in minutes before the open
LABEL_GAP_MIN = 10  # minutes of x between the close and its label
LABEL_PX, AXIS_PX, LEGEND_PX = 17, 16, 17
TICKS = {OVERNIGHT: "Tue close", 90: "11:00", 210: "1:00", 330: "3:00", 390: "4:00"}


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


def session(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    fs = font_scale
    fonts = brand()["fonts"]
    paths = story.frames["paths"]
    summary = story.frames["summary"].to_dicts()
    hues = {"rose": color("categorical")[0], "fell": color("categorical")[1], "baseline": color("text")}

    top = 5.0 * ((paths["pct"].max() // 5) + 1)
    bottom = float(paths["pct"].min() // 1) - 1
    y_ticks = [v for v in range(int(5 * (bottom // 5)), int(top) + 1, 5) if v >= bottom]

    def make(w: float, h: float) -> alt.LayerChart:
        x_end = SESSION_MIN + (SESSION_MIN - OVERNIGHT) * 0.3  # room for the end labels
        x_scale = alt.Scale(domain=[OVERNIGHT, x_end], nice=False, zero=False)
        y_scale = alt.Scale(domain=[bottom, top], nice=False)
        expr = " : ".join(f"datum.value == {k} ? '{v}'" for k, v in TICKS.items()) + " : ''"
        x = alt.X("minute:Q", title=None, scale=x_scale,
                  axis=alt.Axis(values=list(TICKS), labelExpr=expr, grid=False, labelFontSize=AXIS_PX * fs,
                                labelFlush=False, labelOverlap=False, labelColor=color("text_secondary")))  # fmt: skip
        y = alt.Y("pct:Q", title=None, scale=y_scale,
                  axis=alt.Axis(values=y_ticks, labelFontSize=AXIS_PX * fs,
                                labelExpr="(datum.value > 0 ? '+' : datum.value < 0 ? '−' : '') "
                                          "+ abs(datum.value) + '%'",
                                labelColor=color("text_secondary"), grid=True, gridColor=color("panel")))  # fmt: skip

        zero = (
            alt.Chart(alt.Data(values=[{"y": 0}]))
            .mark_rule(color=color("muted"), strokeWidth=1.5 * fs)
            .encode(y=alt.Y("y:Q", scale=y_scale))
        )
        layers = [zero]
        groups = ("fell", "rose", "baseline")  # the baseline draws on top
        for group in groups:
            for s in (r for r in summary if r["group"] == group):
                rows = paths.filter(paths["ticker"] == s["ticker"]).sort("minute").to_dicts()
                width_px = (3.5 if group == "baseline" else 2.2) * fs
                points = [{"minute": OVERNIGHT, "pct": 0.0}, *({"minute": r["minute"], "pct": r["pct"]} for r in rows)]
                layers.append(
                    alt.Chart(alt.Data(values=points))
                    .mark_line(color=hues[group], strokeWidth=width_px, opacity=1 if group == "baseline" else 0.9)
                    .encode(x=x, y=y)
                )

        per_pt = h / (top - bottom)
        ordered = sorted(summary, key=lambda r: -r["close_pct"])
        placed = _spread([r["close_pct"] for r in ordered], (LABEL_PX + 7) * fs / per_pt)
        label_x = SESSION_MIN + LABEL_GAP_MIN
        for s, at in zip(ordered, placed, strict=True):
            hue = hues[s["group"]]
            leader = [{"minute": SESSION_MIN, "pct": s["close_pct"]}, {"minute": label_x - 2, "pct": at}]
            layers.append(
                alt.Chart(alt.Data(values=leader)).mark_line(color=hue, strokeWidth=1.2 * fs).encode(x=x, y=y)
            )
            value = f"{s['close_pct']:+.1f}%".replace("-", "−")
            weight = "bold" if s["group"] == "baseline" else "normal"
            layers.append(
                alt.Chart(alt.Data(values=[{"minute": label_x, "pct": at, "t": f"{s['name']} {value}"}]))
                .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=LABEL_PX * fs,
                           fontWeight=weight, color=color("text"))
                .encode(x=x, y=y, text="t:N")
            )  # fmt: skip

        legend = [("rose", "Hyperscalers", -2.4),
                  ("fell", "Data center supply chain", -4.2)]  # fmt: skip
        for group, text, at in legend:
            layers.append(
                alt.Chart(alt.Data(values=[{"minute": 110, "pct": at}, {"minute": 128, "pct": at}]))
                .mark_line(color=hues[group], strokeWidth=4 * fs)
                .encode(x=x, y=y)
            )
            layers.append(
                alt.Chart(alt.Data(values=[{"minute": 134, "pct": at, "t": text}]))
                .mark_text(align="left", baseline="middle", font=fonts["body"], fontSize=LEGEND_PX * fs,
                           color=color("text_secondary"))
                .encode(x=x, y=y, text="t:N")
            )  # fmt: skip
        return alt.layer(*layers).properties(width=w, height=h).configure(**vl_config(fs))

    return fit(make, width, height)

"""Charts for the two-lenses exploration (render contract: src/cachereg/render.py).

Every chart puts each lens in its own panel; no mark joins or differences the two. Panels that sit side by
side share one 0–100% scale (both are shares of businesses; author decision 1), so neither lens is
stretched. BTOS's two question wordings are separate layers, so no line can cross the 2025-11 break.

* ``sectors``: two dot panels with the same rows (Ramp's order): Ramp's paid adoption, BTOS's current use
  with its 90% interval; rank and value beside each dot; sectors ranked differently in the accent.
* ``trends``: Ramp above, BTOS below, monthly, on one time axis and one y-scale; BTOS's original wording in
  grey, the current wording in the accent, a break marker between them; the new-wording period shaded.
* ``sizes``: BTOS's seven size classes beside Ramp's three bands; the BTOS class range is the only mark
  carried across both panels.
"""

from __future__ import annotations

import math
from datetime import UTC, date, datetime

import altair as alt
import polars as pl

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit
from cachereg.viz.theme import vl_config

RAMP, CUR = "ramp_paid", "btos_use_current"
LIGHT, DARK = "#C3C8D3", "#858B9B"  # context greys (as the other explorations)
SHADE = "#161922"  # the new-wording period: a step above the canvas
LABEL_PX, AXIS_PX = 17, 15
OVERALL = "All businesses"


def _ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _wrap(sub: str, fs: float, max_px: float | None) -> str | list[str]:
    """The panel subtitle as one line, or as lines no wider than max_px (Vega widens a panel to its title)."""
    px = (LABEL_PX - 3) * fs * 0.56  # rough Inter advance per character
    if max_px is None or len(sub) * px <= max_px:
        return sub
    lines: list[str] = []
    for word in sub.replace(" · ", " ·\u00a0").split(" "):
        if lines and len(lines[-1]) + 1 + len(word) <= max_px / px:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return [ln.replace("\u00a0", " ") for ln in lines]


def _title(text: str, sub: str, fs: float, max_px: float | None = None) -> alt.TitleParams:
    fonts = brand()["fonts"]
    return alt.TitleParams(
        text=text,
        subtitle=_wrap(sub, fs, max_px),
        anchor="start",
        font=fonts["body"],
        fontSize=LABEL_PX * fs,
        fontWeight="bold",
        color=color("text"),
        subtitleFont=fonts["body"],
        subtitleFontSize=(LABEL_PX - 3) * fs,
        subtitleColor=color("text_secondary"),
        offset=12 * fs,
    )


def _pct_axis(
    fs: float, title: str | None = None, grid: bool = True, flush: bool = False, sparse: bool = False
) -> alt.Axis:
    return alt.Axis(
        values=[0, 50, 100] if sparse else [0, 25, 50, 75, 100],
        labelExpr="datum.value + '%'",
        labelFontSize=AXIS_PX * fs,
        labelFlush=flush,
        grid=grid,
        title=title,
    )


# ---- sectors ----------------------------------------------------------------------------------


def sectors(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.HConcatChart:
    return fit(lambda w, h: _sectors(story, w, h, font_scale), width, height)


def _sectors(story: Story, width: float, height: float, font_scale: float) -> alt.HConcatChart:
    fs = font_scale
    fonts = brand()["fonts"]
    lv = story.frames["levels"].filter(pl.col("role") == "matched")
    ramp_order = lv.filter((pl.col("lens") == RAMP) & (pl.col("scope") == "sector")).sort("rank")["label"].to_list()
    domain = [*ramp_order, " ", OVERALL]  # a blank row separates the overall from the sectors

    rows = lv.with_columns(
        c=pl.when(pl.col("rank_differs").fill_null(False)).then(pl.lit(color("accent"))).otherwise(pl.lit(LIGHT)),
        text=pl.when(pl.col("rank").is_not_null())
        .then(pl.format("#{} · {}%", pl.col("rank").cast(pl.Int64), pl.col("pct").round(0).cast(pl.Int64)))
        .otherwise(pl.format("{}%", pl.col("pct").round(0).cast(pl.Int64))),
        text_x=pl.coalesce("high90", "pct"),
    ).select("label", "lens", "pct", "low90", "high90", "c", "text", "text_x")

    label_px = (max(len(x) for x in domain) * 0.55 * AXIS_PX + 18) * fs
    spacing = 36 * fs
    panel_w = max((width - label_px - spacing) / 2, 1.0)
    panel_h = max(height - 90 * fs, 1.0)  # first guess; fit corrects for the titles and axis
    x_scale = alt.Scale(domain=[0, 118], nice=False)  # 0–100% axis; the margin holds the value labels
    axis = _pct_axis(fs, sparse=panel_w < 300 * fs)
    clr = alt.Color("c:N", scale=None, legend=None)

    def panel(lens: str, first: bool) -> alt.LayerChart:
        data = alt.Data(values=rows.filter(pl.col("lens") == lens).to_dicts())
        y = alt.Y(
            "label:N",
            scale=alt.Scale(domain=domain, paddingInner=0.35),
            sort=domain,
            title=None,
            axis=alt.Axis(
                labels=first,
                labelFontSize=AXIS_PX * fs,
                labelFont=fonts["body"],
                labelColor=color("text"),
                grid=False,
                labelLimit=0,
            )
            if first
            else None,
        )
        x = alt.X("pct:Q", scale=x_scale, axis=axis)
        layers = []
        if lens == CUR:
            layers.append(
                alt.Chart(data)
                .mark_rule(strokeWidth=3 * fs, opacity=0.55, strokeCap="round")
                .encode(x=alt.X("low90:Q", scale=x_scale, axis=axis), x2="high90:Q", y=y, color=clr)
            )
        layers += [
            alt.Chart(data)
            .mark_circle(size=170 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
            .encode(x=x, y=y, color=clr),
            alt.Chart(data)
            .mark_text(
                align="left",
                dx=12 * fs,
                fontSize=(LABEL_PX - 1) * fs,
                font=fonts["mono"],
                color=color("text_secondary"),
            )
            .encode(x=alt.X("text_x:Q", scale=x_scale, axis=axis), y=y, text="text:N"),
        ]
        if lens == CUR:
            t = _title("Census BTOS: used AI", "U.S. employer businesses, last two weeks · 90% interval", fs, panel_w)
        else:
            t = _title("Ramp: paid for AI", "Businesses on Ramp, AI spend in the month", fs, panel_w + label_px)
        return alt.layer(*layers).properties(width=panel_w, height=panel_h, title=t)

    left, right = panel(RAMP, True), panel(CUR, False)
    return alt.hconcat(left, right, spacing=spacing).resolve_scale(color="independent").configure(**vl_config(fs))


# ---- trends -----------------------------------------------------------------------------------


def trends(
    story: Story, width, height, font_scale: float = 1.0, interactive: bool = False
) -> alt.VConcatChart | alt.LayerChart:
    return fit(lambda w, h: _trends(story, w, h, font_scale), width, height)


def _trends(story: Story, width: float, height: float, font_scale: float) -> alt.VConcatChart | alt.LayerChart:
    fs = font_scale
    fonts = brand()["fonts"]
    accent = color("accent")
    tr = story.frames["trend"].filter((pl.col("scope") == "overall") & ~pl.col("partial").fill_null(False))
    start = date.fromisoformat(str(story.extra.get("trend_start", "2023-01-01")))
    tr = tr.filter(pl.col("month") >= start).sort("month")
    base = date.fromisoformat(story.extra["base_month"])
    has_ramp = tr.filter(pl.col("lens") == RAMP).height > 0
    first, last = tr["month"].min(), tr["month"].max()

    label_px = (16 + 12 * 0.55 * LABEL_PX + 12) * fs
    plot_px = max(width - 60 * fs, 1.0)  # first guess; fit corrects for the y-axis
    pad = (last - first) * (label_px / max(plot_px - label_px, 1.0))
    x0 = date(first.year, first.month, 1)
    x_scale = alt.Scale(type="utc", domain=[_ms(x0), _ms(last + pad)])
    months = (1, 7) if plot_px > 1000 * fs else (1,)  # half-yearly ticks only where they fit
    ticks = [date(y, m, 1) for y in range(x0.year, last.year + 1) for m in months if x0 <= date(y, m, 1) <= last]
    x_axis = alt.Axis(
        values=[_ms(t) for t in ticks],
        labelExpr=(
            "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"
        ),
        labelFontSize=AXIS_PX * fs,
        grid=False,
    )
    no_x = alt.Axis(labels=False, grid=False, title=None)
    hi = 10 * math.ceil((tr["high90"].fill_null(tr["pct"]).max() if not has_ramp else tr["pct"].max()) / 10) + 10
    y_scale = alt.Scale(domain=[0, min(hi, 100)], nice=False)
    y_axis = alt.Axis(tickCount=4, labelExpr="datum.value + '%'", labelFontSize=AXIS_PX * fs, title=None)

    rows = tr.with_columns(t=pl.col("month").map_elements(_ms, return_dtype=pl.Int64)).select(
        "t", "lens", "wording", "pct", "low90", "high90"
    )
    spacing = 30 * fs
    n = 2 if has_ramp else 1
    panel_h = max((height - spacing * (n - 1) - 60 * fs * n) / n, 1.0)

    def shade(axis) -> alt.Chart:
        d = alt.Data(values=[{"t0": _ms(base), "t1": _ms(last)}])
        return (
            alt.Chart(d)
            .mark_rect(color=SHADE)
            .encode(
                x=alt.X("t0:T", scale=x_scale, axis=axis),
                x2="t1:T",
                y=alt.datum(0, scale=y_scale),
                y2=alt.datum(y_scale.domain[1]),
            )
        )

    def line(df: pl.DataFrame, c: str, axis, band: bool) -> list[alt.Chart]:
        data = alt.Data(values=df.to_dicts())
        x = alt.X("t:T", scale=x_scale, axis=axis, title=None)
        out = []
        if band:
            out.append(
                alt.Chart(data)
                .mark_area(color=c, opacity=0.22)
                .encode(x=x, y=alt.Y("low90:Q", scale=y_scale, axis=y_axis), y2="high90:Q")
            )
        out.append(
            alt.Chart(data)
            .mark_line(color=c, strokeWidth=2.6 * fs)
            .encode(x=x, y=alt.Y("pct:Q", scale=y_scale, axis=y_axis))
        )
        return out

    def end_label(row: dict, name: str, c: str, axis, dy: float = 0) -> list[alt.Chart]:
        d = alt.Data(values=[{"t": row["t"], "pct": row["pct"], "v": f"{row['pct']:.0f}%", "name": name}])
        x, y = alt.X("t:T", scale=x_scale, axis=axis, title=None), alt.Y("pct:Q", scale=y_scale, axis=y_axis)
        return [
            alt.Chart(d)
            .mark_circle(size=80 * fs**2, opacity=1, color=c, stroke=color("canvas"), strokeWidth=2)
            .encode(x=x, y=y),
            alt.Chart(d)
            .mark_text(
                align="left",
                baseline="bottom",
                dx=12 * fs,
                dy=dy - 1,
                fontSize=LABEL_PX * fs,
                font=fonts["body"],
                color=color("text"),
            )
            .encode(x=x, y=y, text="v:N"),
            alt.Chart(d)
            .mark_text(
                align="left",
                baseline="top",
                dx=12 * fs,
                dy=dy + 3,
                fontSize=(LABEL_PX - 2) * fs,
                font=fonts["body"],
                color=color("text_secondary"),
            )
            .encode(x=x, y=y, text="name:N"),
        ]

    panels = []
    if has_ramp:
        r = rows.filter(pl.col("lens") == RAMP)
        top = alt.layer(
            shade(no_x), *line(r, accent, no_x, False), *end_label(r.row(-1, named=True), "paid for AI", accent, no_x)
        )
        panels.append(
            top.properties(
                width=plot_px,
                height=panel_h,
                title=_title("Ramp: paid for AI", "Businesses on Ramp, AI spend in the month", fs),
            )
        )

    b_axis = x_axis
    btos_rows = rows.filter(pl.col("lens") == CUR)
    half = ((btos_rows["high90"] - btos_rows["low90"]) / 2).max()
    b_layers = [shade(b_axis)]
    orig = rows.filter((pl.col("lens") == CUR) & (pl.col("wording") == "original"))
    cur = rows.filter((pl.col("lens") == CUR) & (pl.col("wording") == "current"))
    b_layers += line(orig, DARK, b_axis, True) + line(cur, accent, b_axis, True)
    if orig.height:
        o = orig.row(-1, named=True)
        lbl = alt.Data(values=[{"t": o["t"], "pct": o["pct"], "name": "original wording"}])
        b_layers.append(
            alt.Chart(lbl)
            .mark_text(
                align="right",
                baseline="bottom",
                dx=-6 * fs,
                dy=-10 * fs,
                fontSize=(LABEL_PX - 2) * fs,
                font=fonts["body"],
                color=DARK,
            )
            .encode(
                x=alt.X("t:T", scale=x_scale, axis=b_axis, title=None),
                y=alt.Y("pct:Q", scale=y_scale, axis=y_axis),
                text="name:N",
            )
        )
    if orig.height and story.extra.get("wording_break"):
        brk_day = date.fromisoformat(story.extra["wording_break"])
        brk = alt.Data(values=[{"t": _ms(brk_day), "label": "new wording: a new Census series"}])
        b_layers += [
            alt.Chart(brk)
            .mark_rule(color=color("text_secondary"), strokeDash=[4 * fs, 4 * fs], strokeWidth=1.3 * fs)
            .encode(
                x=alt.X("t:T", scale=x_scale, axis=b_axis, title=None),
                y=alt.datum(0, scale=y_scale),
                y2=alt.datum(y_scale.domain[1]),
            ),
            alt.Chart(brk)
            .mark_text(
                align="right",
                baseline="top",
                dx=-8 * fs,
                dy=6 * fs,
                fontSize=(LABEL_PX - 2) * fs,
                font=fonts["body"],
                color=color("text_secondary"),
            )
            .encode(
                x=alt.X("t:T", scale=x_scale, axis=b_axis, title=None),
                y=alt.datum(y_scale.domain[1], scale=y_scale),
                text="label:N",
            ),
        ]
    if cur.height:
        b_layers += end_label(cur.row(-1, named=True), "used AI", accent, b_axis)
    bottom = alt.layer(*b_layers).properties(
        width=plot_px,
        height=panel_h,
        title=_title(
            "Census BTOS: used AI",
            f"U.S. employer businesses, last two weeks · 90% interval within ±{half:.1f} pp (shaded)",
            fs,
        ),
    )
    panels.append(bottom)
    if len(panels) == 1:
        return panels[0].configure(**vl_config(fs))
    return alt.vconcat(*panels, spacing=spacing).resolve_scale(x="shared", y="shared").configure(**vl_config(fs))


# ---- sizes ------------------------------------------------------------------------------------


def sizes(
    story: Story, width, height, font_scale: float = 1.0, interactive: bool = False
) -> alt.HConcatChart | alt.LayerChart:
    return fit(lambda w, h: _sizes(story, w, h, font_scale), width, height)


def _sizes(story: Story, width: float, height: float, font_scale: float) -> alt.HConcatChart | alt.LayerChart:
    fs = font_scale
    fonts = brand()["fonts"]
    accent = color("accent")
    sz = story.frames["sizes"]
    nat = story.frames["size_bound"].row(0, named=True)
    btos, ramp = sz.filter(pl.col("lens") == CUR).sort("order"), sz.filter(pl.col("lens") == RAMP).sort("order")
    y_scale = alt.Scale(domain=[0, 100], nice=False)
    spacing = 40 * fs
    y_axis_px = 60 * fs
    n_bars = btos.height + ramp.height
    step = max((width - y_axis_px - (spacing if ramp.height else 0)) / max(n_bars, 1), 1.0)
    panel_h = max(height - 110 * fs, 1.0)

    def band(n: int, y_axis) -> list[alt.Chart]:
        d = alt.Data(values=[{"lo": nat["min_pct"], "hi": nat["max_pct"]}])
        x = alt.value(0)
        return [
            alt.Chart(d)
            .mark_rect(color=LIGHT, opacity=0.10)
            .encode(x=x, x2=alt.value(step * n), y=alt.Y("lo:Q", scale=y_scale, axis=y_axis), y2="hi:Q"),
            alt.Chart(d)
            .mark_rule(color=LIGHT, strokeDash=[4 * fs, 4 * fs], strokeWidth=1.2 * fs, opacity=0.8)
            .encode(x=x, x2=alt.value(step * n), y=alt.Y("hi:Q", scale=y_scale, axis=y_axis)),
            alt.Chart(d)
            .mark_rule(color=LIGHT, strokeDash=[4 * fs, 4 * fs], strokeWidth=1.2 * fs, opacity=0.8)
            .encode(x=x, x2=alt.value(step * n), y=alt.Y("lo:Q", scale=y_scale, axis=y_axis)),
        ]

    def bars(df: pl.DataFrame, c: str, x_title: str, y_axis, with_ci: bool) -> list[alt.Chart]:
        data = alt.Data(
            values=df.with_columns(
                v=pl.format("{}%", pl.col("pct").round(0).cast(pl.Int64)), top=pl.coalesce("high90", "pct")
            )
            .select("size_label", "pct", "low90", "high90", "v", "top")
            .to_dicts()
        )
        x = alt.X(
            "size_label:N",
            sort=df["size_label"].to_list(),
            scale=alt.Scale(paddingInner=0.3, paddingOuter=0.15),
            axis=alt.Axis(
                labelFontSize=AXIS_PX * fs, labelAngle=0, title=x_title, titlePadding=12 * fs, labelFont=fonts["mono"]
            ),
        )
        out = [
            alt.Chart(data)
            .mark_bar(color=c, cornerRadiusTopLeft=4 * fs, cornerRadiusTopRight=4 * fs)
            .encode(x=x, y=alt.Y("pct:Q", scale=y_scale, axis=y_axis))
        ]
        if with_ci:
            out.append(
                alt.Chart(data)
                .mark_rule(color=color("text"), strokeWidth=1.6 * fs, opacity=0.8)
                .encode(x=x, y=alt.Y("low90:Q", scale=y_scale, axis=y_axis), y2="high90:Q")
            )
        out.append(
            alt.Chart(data)
            .mark_text(
                baseline="bottom",
                dy=-6 * fs,
                fontSize=(LABEL_PX - 1) * fs,
                font=fonts["mono"],
                color=color("text_secondary"),
            )
            .encode(x=x, y=alt.Y("top:Q", scale=y_scale, axis=y_axis), text="v:N")
        )
        return out

    y_left = _pct_axis(fs, flush=True)
    note = alt.Data(
        values=[
            {"y": nat["max_pct"], "t": f"BTOS range across size classes: {nat['min_pct']:.0f}–{nat['max_pct']:.0f}%"}
        ]
    )
    note_mark = (
        alt.Chart(note)
        .mark_text(
            align="left", baseline="bottom", dy=-8 * fs, fontSize=(LABEL_PX - 3) * fs, font=fonts["body"], color=LIGHT
        )
        .encode(x=alt.value(6 * fs), y=alt.Y("y:Q", scale=y_scale, axis=y_left), text="t:N")
    )
    left = alt.layer(*band(btos.height, y_left), *bars(btos, DARK, "Employees", y_left, True), note_mark).properties(
        width=step * btos.height,
        height=panel_h,
        title=_title(
            "Census BTOS: used AI", "U.S. employer businesses, by employees · 90% interval", fs, step * btos.height
        ),
    )
    if not ramp.height:
        return left.configure(**vl_config(fs))
    y_right = alt.Axis(labels=False, grid=True, title=None, values=[0, 25, 50, 75, 100])
    right = alt.layer(*band(ramp.height, y_right), *bars(ramp, accent, "Ramp size band", y_right, False)).properties(
        width=step * ramp.height,
        height=panel_h,
        title=_title("Ramp: paid for AI", "Businesses on Ramp, by size band", fs, step * ramp.height),
    )
    return alt.hconcat(left, right, spacing=spacing).configure(**vl_config(fs))

"""Charts for the Anthropic quarterly revenue exploration (render contract: src/cachereg/render.py).

Two panels on one quarter axis (two scales, never one dual axis): revenue per quarter on top, in
Anthropic's vendor colour with the latest quarter at full strength, and the change from the previous
quarter below, in grey. A bracket joins the latest quarter to the same quarter a year earlier and carries
the year-over-year multiple. Values are labelled on every bar (six bars: few enough to read).

`seasonal`: each comparator's typical growth by calendar quarter (grouped bars with min–max whiskers).
`adjusted`: Anthropic's growth by quarter as filed and with each comparator's pattern removed. Colour follows
the comparator in both: GitHub cyan, cloud revenue gold (categorical slots 1 and 4; orange is Anthropic's),
working days grey; Anthropic as filed in its vendor colour.
"""

from __future__ import annotations

import altair as alt
import polars as pl
from analysis import SERIES, VARIANTS, fmt_musd

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit, size_or
from cachereg.viz.theme import vl_config

LABEL_PX, NOTE_PX = 17, 19
TOP_SHARE = 0.64  # of the plot height, for the revenue panel


def _vendor() -> str:
    return brand()["colors"]["vendor_colors"]["anthropic"]


def quarters(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    fs = font_scale
    fonts = brand()["fonts"]
    q = story.frames["quarters"]
    ex = story.extra
    order = q["quarter"].to_list()
    last = order[-1]
    peak = q["revenue_musd"].max()
    bracket_y = peak * 1.3  # the year-over-year bracket, above the tallest bar and its label

    rows = q.with_columns(
        rev_label=pl.col("revenue_musd").map_elements(fmt_musd, return_dtype=pl.String),
        qoq_label=pl.when(pl.col("qoq_pct").is_not_null())
        .then(
            pl.col("qoq_pct")
            .round(0)
            .cast(pl.Int64)
            .cast(pl.String)
            .map_elements(lambda s: f"+{s}%" if not s.startswith("-") else f"{s}%", return_dtype=pl.String)
        )
        .otherwise(None),
        latest=pl.col("quarter") == last,
    ).select("quarter", "revenue_musd", "qoq_pct", "yoy_multiple", "rev_label", "qoq_label", "latest")
    data = alt.Data(values=rows.to_dicts())

    def make(w: float, h: float) -> alt.VConcatChart:
        gap = 34 * fs
        top_h = (h - gap) * TOP_SHARE
        bot_h = h - gap - top_h

        x = alt.X(
            "quarter:N",
            sort=order,
            title=None,
            scale=alt.Scale(paddingInner=0.28, paddingOuter=0.14),
            axis=alt.Axis(
                labelFont=fonts["mono"], labelFontSize=15 * fs, labelColor=color("text_secondary"), labelAngle=0
            ),
        )
        xc = alt.X("quarter:N", sort=order, bandPosition=0.5, title=None)

        # ---- revenue panel
        rev_scale = alt.Scale(domain=[0, bracket_y * 1.08], nice=False)
        rev_axis = alt.Axis(
            labelExpr="'$' + format(datum.value / 1000, ',.0f') + 'B'",
            values=[v * 1000 for v in range(0, int(bracket_y / 1000) + 1, 2 if peak < 12000 else 4)],
            title="Revenue per quarter",
            titlePadding=12 * fs,
        )

        def yr(field: str) -> alt.Y:
            return alt.Y(f"{field}:Q", scale=rev_scale, axis=rev_axis)

        y_rev = yr("revenue_musd")
        bar_color = alt.condition(alt.datum.latest, alt.value(_vendor()), alt.value(_vendor() + "99"))
        tooltip = (
            [
                alt.Tooltip("quarter:N", title="Quarter"),
                alt.Tooltip("revenue_musd:Q", title="Revenue ($M)", format=",.0f"),
                alt.Tooltip("qoq_pct:Q", title="vs previous quarter (%)", format="+.0f"),
                alt.Tooltip("yoy_multiple:Q", title="vs a year earlier (×)", format=".1f"),
            ]
            if interactive
            else alt.Undefined
        )
        rev_bars = (
            alt.Chart(data)
            .mark_bar(cornerRadiusTopLeft=4 * fs, cornerRadiusTopRight=4 * fs)
            .encode(x=x, y=y_rev, color=bar_color, tooltip=tooltip)
        )
        rev_text = (
            alt.Chart(data)
            .mark_text(baseline="bottom", dy=-8 * fs, fontSize=LABEL_PX * fs, font=fonts["mono"])
            .encode(x=x, y=y_rev, text="rev_label:N", color=alt.value(color("text")))
        )

        # Year-over-year bracket: up from the earlier quarter's label, across, down to the latest quarter's label.
        frm, to = ex["yoy_from"], ex["yoy_to"]
        lab = {r["quarter"]: r["revenue_musd"] for r in rows.iter_rows(named=True)}
        rise = peak * 0.17  # clear of the value labels
        legs = alt.Data(
            values=[
                {"quarter": frm, "y0": lab[frm] + rise, "y1": bracket_y},
                {"quarter": to, "y0": lab[to] + rise, "y1": bracket_y},
            ]
        )
        y_leg = yr("y0")
        bracket_legs = (
            alt.Chart(legs)
            .mark_rule(strokeWidth=2 * fs, color=color("text_secondary"))
            .encode(x=xc, y=y_leg, y2="y1:Q")
        )
        span = alt.Data(values=[{"a": frm, "b": to, "y": bracket_y}])
        bracket_top = (
            alt.Chart(span)
            .mark_rule(strokeWidth=2 * fs, color=color("text_secondary"))
            .encode(
                x=alt.X("a:N", sort=order, bandPosition=0.5, title=None, scale=alt.Scale(domain=order)),
                x2="b:N",
                y=yr("y"),
            )
        )
        i, j = order.index(frm), order.index(to)
        # The bracket's midpoint: a band centre when i + j is even, else the boundary between two bands.
        mid, mid_pos = (order[(i + j) // 2], 0.5) if (i + j) % 2 == 0 else (order[(i + j + 1) // 2], 0.0)
        yoy_text = (
            alt.Chart(
                alt.Data(values=[{"quarter": mid, "y": bracket_y, "t": f"{ex['yoy_multiple']:.1f}× year over year"}])
            )
            .mark_text(
                baseline="middle",
                fontSize=NOTE_PX * fs,
                font=fonts["mono"],
                fontWeight="bold",
                color=color("text"),
            )
            .encode(
                x=alt.X("quarter:N", sort=order, bandPosition=mid_pos, title=None),
                y=yr("y"),
                text="t:N",
            )
        )
        # A canvas-coloured box behind the label breaks the bracket line around it.
        label_box = (
            alt.Chart(alt.Data(values=[{"quarter": mid, "y": bracket_y}]))
            .mark_rect(
                color=color("canvas"),
                width=(len(f"{ex['yoy_multiple']:.1f}× year over year") * 0.62 * NOTE_PX + 24) * fs,
                height=NOTE_PX * 1.6 * fs,
            )
            .encode(
                x=alt.X("quarter:N", sort=order, bandPosition=mid_pos, title=None),
                y=yr("y"),
            )
        )
        top = alt.layer(rev_bars, rev_text, bracket_legs, bracket_top, label_box, yoy_text).properties(
            width=w, height=top_h
        )

        # ---- change panel
        y_chg = alt.Y(
            "qoq_pct:Q",
            scale=alt.Scale(domain=[0, max(q["qoq_pct"].max() or 0, 50) * 1.25], nice=False),
            axis=alt.Axis(
                labelExpr="format(datum.value, '.0f') + '%'",
                values=[0, 50, 100, 150],
                title="vs previous quarter",
                titlePadding=12 * fs,
            ),
        )
        chg_bars = (
            alt.Chart(data)
            .transform_filter("isValid(datum.qoq_pct)")
            .mark_bar(cornerRadiusTopLeft=4 * fs, cornerRadiusTopRight=4 * fs, color=color("muted"))
            .encode(x=x, y=y_chg, tooltip=tooltip)
        )
        chg_text = (
            alt.Chart(data)
            .transform_filter("isValid(datum.qoq_pct)")
            .mark_text(baseline="bottom", dy=-8 * fs, fontSize=LABEL_PX * fs, font=fonts["mono"])
            .encode(x=x, y=y_chg, text="qoq_label:N", color=alt.value(color("text_secondary")))
        )
        bottom = alt.layer(chg_bars, chg_text).properties(width=w, height=max(bot_h, 60))

        return alt.vconcat(top, bottom, spacing=gap).resolve_scale(x="shared").configure(**vl_config(fs))

    return fit(make, width, height, default=(size_or(width, 900), size_or(height, 560)))


def _ink() -> dict[str, str]:
    cat = brand()["colors"]["categorical"]
    return {"github": cat[0], "peers": cat[3], "workdays": color("text_secondary"), "filed": _vendor()}


def _signed(v: float) -> str:
    return f"{v:+.0f}%"


def _grouped(
    rows: pl.DataFrame,
    *,
    x: str,
    x_order: list[str],
    key: str,
    labels: dict[str, str],
    value: str,
    width,
    height,
    fs: float,
    y_title: str,
    whiskers: tuple[str, str] | None = None,
    label_px: float = LABEL_PX,
    interactive: bool = False,
) -> alt.Chart:
    """Grouped bars (one group per x, one bar per key) with value labels and an optional min–max whisker."""
    fonts = brand()["fonts"]
    ink = _ink()
    keys = [k for k in labels if k in set(rows[key])]
    data = alt.Data(
        values=rows.with_columns(
            name=pl.col(key).replace_strict(labels),
            text=pl.col(value).map_elements(_signed, return_dtype=pl.String),
            up=pl.col(value) >= 0,
        ).to_dicts()
    )
    lo = min(rows[whiskers[0]].min() if whiskers else 0, rows[value].min(), 0)
    hi = max(rows[whiskers[1]].max() if whiskers else 0, rows[value].max(), 0)
    pad = (hi - lo) * 0.12
    scale = alt.Scale(domain=[lo - (pad if lo < 0 else 0), hi + pad], nice=False)
    clr = alt.Color(
        "name:N",
        scale=alt.Scale(domain=[labels[k] for k in keys], range=[ink[k] for k in keys]),
        legend=alt.Legend(title=None, labelFontSize=15 * fs, symbolSize=140 * fs**2, labelLimit=0, columns=2),
        sort=[labels[k] for k in keys],
    )
    xo = alt.XOffset("name:N", sort=[labels[k] for k in keys], scale=alt.Scale(paddingInner=0.12))

    def make(w: float, h: float) -> alt.LayerChart:
        xe = alt.X(
            f"{x}:N",
            sort=x_order,
            title=None,
            scale=alt.Scale(paddingInner=0.24, paddingOuter=0.1),
            axis=alt.Axis(labelAngle=0, labelFontSize=15 * fs, labelPadding=14 * fs, orient="bottom"),
        )
        ye = alt.Y(
            f"{value}:Q",
            scale=scale,
            axis=alt.Axis(labelExpr="format(datum.value, '+.0f') + '%'", title=y_title, titlePadding=12 * fs),
        )
        tip = (
            [alt.Tooltip(f"{x}:N"), alt.Tooltip("name:N", title="Series"), alt.Tooltip(f"{value}:Q", format="+.1f")]
            if interactive
            else alt.Undefined
        )
        bars = alt.Chart(data).mark_bar(cornerRadius=3 * fs).encode(x=xe, xOffset=xo, y=ye, color=clr, tooltip=tip)
        layers = [bars]
        if whiskers:
            layers.append(
                alt.Chart(data)
                .mark_rule(strokeWidth=1.6 * fs, color=color("text"), opacity=0.7)
                .encode(x=xe, xOffset=xo, y=alt.Y(f"{whiskers[0]}:Q", scale=scale), y2=f"{whiskers[1]}:Q")
            )
        # Labels sit beyond the bar's end (or its whisker): above for gains, below for falls.
        hi_f, lo_f = (f"datum.{whiskers[1]}", f"datum.{whiskers[0]}") if whiskers else (f"datum.{value}",) * 2
        for up, base, dy in ((True, "bottom", -6), (False, "top", 6)):
            layers.append(
                alt.Chart(data)
                .transform_filter(alt.datum.up if up else ~alt.datum.up)
                .transform_calculate(at=hi_f if up else lo_f)
                .mark_text(fontSize=label_px * fs, font=fonts["mono"], color=color("text"), baseline=base, dy=dy * fs)
                .encode(x=xe, xOffset=xo, y=alt.Y("at:Q", scale=scale), text="text:N")
            )
        zero = (
            alt.Chart(alt.Data(values=[{"z": 0}]))
            .mark_rule(color=color("muted"), strokeWidth=1.5)
            .encode(y=alt.Y("z:Q", scale=scale))
        )
        return alt.layer(*layers, zero).properties(width=w, height=h).configure(**vl_config(fs))

    return fit(make, width, height)


def seasonal(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    d = story.frames["seasonal"].with_columns(quarter="Q" + pl.col("k").cast(pl.String))
    return _grouped(
        d,
        x="quarter",
        x_order=["Q1", "Q2", "Q3", "Q4"],
        key="series",
        labels=SERIES,
        value="factor_pct",
        width=width,
        height=height,
        fs=font_scale,
        y_title="Growth vs the year's average quarter",
        whiskers=("min_pct", "max_pct"),
        interactive=interactive,
    )


def adjusted(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.Chart:
    d = story.frames["adjusted"]
    order = d["quarter"].unique(maintain_order=True).to_list()
    return _grouped(
        d,
        x="quarter",
        x_order=order,
        key="variant",
        labels=VARIANTS,
        value="growth_pct",
        width=width,
        height=height,
        fs=font_scale,
        y_title="Growth from the previous quarter",
        label_px=13,
        interactive=interactive,
    )

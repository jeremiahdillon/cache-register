"""Charts for the wallet-lenses exploration (render contract: src/cachereg/render.py).

Every lens has its own panel, axis and unit; no mark joins two lenses, and no value, gap or ratio is drawn
across panels. Rows are the same in every panel of a chart, so a lab's *order* can be read across them.

* ``ranks``: Vercel spend · OpenRouter est. spend · Ramp paying, headline month. Ramp's labs (ranked among
  themselves) in Ramp's order, then gateway labs Ramp does not report. Labs in a disagreeing pair in the accent.
* ``leaders``: the same three lenses stacked on one time axis, each with its own y-scale; Anthropic, OpenAI and
  Google in their brand colours.
* ``tokens_spend``: the two gateways' token and spend shares, four panels (one per lens), ranks among all named
  labs on that gateway; the lab with the most tokens on both gateways in the accent.
* ``run_rates``: the labs' stated revenue run-rates on a log dollar axis by the period described; year figures as
  spans; no connecting lines.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import altair as alt
import polars as pl

from cachereg.story.model import Story
from cachereg.viz.brand import brand, color
from cachereg.viz.fit import fit, split
from cachereg.viz.theme import vl_config

VERCEL, OPENROUTER, RAMP = "vercel_spend", "openrouter_est_spend", "ramp_paying"
LIGHT, DARK = "#C3C8D3", "#858B9B"  # context greys (as the other explorations)
LABEL_PX, AXIS_PX = 17, 15
PANEL = {
    VERCEL: ("Vercel AI Gateway", "share of spend (Vercel's measure)"),
    OPENROUTER: ("OpenRouter", "share of estimated spend (list prices)"),
    RAMP: ("Ramp", "share of businesses paying the lab"),
    "vercel_tokens": ("Vercel AI Gateway", "share of tokens"),
    "openrouter_tokens": ("OpenRouter", "share of tokens"),
}
LEAD_LABS = ["anthropic", "openai", "google"]
MONTH_LABEL = "utcFormat(datum.value, '%b') + (utcmonth(datum.value) == 0 ? ' ' + utcFormat(datum.value, '%Y') : '')"


def _ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() * 1000)


def _pct(v: float) -> str:
    if v == 0:
        return "0%"
    if v < 0.05:
        return "<0.1%"
    return f"{v:.0f}%" if v >= 9.95 else f"{v:.1f}%"


def _subs(subs: list[str], widths: list[float], fs: float) -> list[list[str]]:
    """Panel subtitles wrapped to their panel widths and padded to one line count, so panel tops align."""
    lines = [_wrap(s, fs, w) for s, w in zip(subs, widths, strict=True)]
    lines = [[x] if isinstance(x, str) else x for x in lines]
    n = max(len(x) for x in lines)
    return [x + [" "] * (n - len(x)) for x in lines]


def _title(text: str, sub: str | list[str], fs: float) -> alt.TitleParams:
    fonts = brand()["fonts"]
    return alt.TitleParams(
        text=text,
        subtitle=sub,
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


def label_px_of(domain: list[str], fs: float) -> float:
    return (max(len(x) for x in domain) * 0.55 * AXIS_PX + 18) * fs


def _names(story: Story) -> dict[str, str]:
    lv = story.frames["lenses"]
    return dict(lv.select("vendor_id", "vendor_name").unique("vendor_id").iter_rows())


def _row_axis(fs: float, show: bool) -> alt.Axis | None:
    if not show:
        return None
    return alt.Axis(
        labelFontSize=AXIS_PX * fs,
        labelFont=brand()["fonts"]["body"],
        labelColor=color("text"),
        grid=False,
        labelLimit=0,
        title=None,
    )


def _dot_panel(rows: list[dict], domain: list[str], width: float, height: float, fs: float, first: bool, title):
    """One lens: a dot per lab on the lens's own 0–100% axis, its label beside it; rows on a shared domain."""
    fonts = brand()["fonts"]
    data = alt.Data(values=rows)
    x_scale = alt.Scale(domain=[0, 135], nice=False)  # 0–100% axis; the margin holds the labels
    axis = alt.Axis(
        values=[0, 50, 100] if width < 300 * fs else [0, 25, 50, 75, 100],
        labelExpr="datum.value + '%'",
        labelFontSize=AXIS_PX * fs,
        title=None,
    )
    y = alt.Y(
        "label:N",
        scale=alt.Scale(domain=domain, paddingInner=0.35),
        sort=domain,
        title=None,
        axis=_row_axis(fs, first),
    )
    measured = [r for r in rows if r.get("pct") is not None]
    layers = [
        alt.Chart(alt.Data(values=measured))
        .mark_circle(size=150 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
        .encode(x=alt.X("pct:Q", scale=x_scale, axis=axis), y=y, color=alt.Color("c:N", scale=None, legend=None)),
        alt.Chart(data)
        .mark_text(align="left", dx=12 * fs, fontSize=(LABEL_PX - 1) * fs, font=fonts["mono"])
        .encode(
            x=alt.X("text_x:Q", scale=x_scale, axis=axis),
            y=y,
            text="text:N",
            color=alt.Color("tc:N", scale=None, legend=None),
        ),
    ]
    return alt.layer(*layers).properties(width=width, height=height, title=title)


# ---- ranks ------------------------------------------------------------------------------------


def ranks(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.HConcatChart:
    box_w = width if isinstance(width, int | float) else 900
    return fit(lambda w, h: _ranks(story, w, h, font_scale, box_w), width, height)


def _ranks(story: Story, width: float, height: float, fs: float, box_w: float) -> alt.HConcatChart:
    month = date.fromisoformat(story.extra["month"])
    labs, extra = story.extra["labs"], story.extra["not_reported"]
    names = _names(story)
    apart = story.frames["pairs"].filter(pl.col("status") == "disagree")
    hot = set(apart["a"]) | set(apart["b"])
    at = story.frames["lenses"].filter(pl.col("month") == month)
    floor = float(story.extra["floor_pct"])
    domain = [names[v] for v in labs] + ([" "] + [names[v] for v in extra] if extra else [])
    base_w = (box_w - label_px_of(domain, fs) - 2 * 30 * fs) / 3
    subs = _subs(
        [PANEL[x][1] for x in (VERCEL, OPENROUTER, RAMP)], [base_w + label_px_of(domain, fs), base_w, base_w], fs
    )

    label_px = label_px_of(domain, fs)
    spacing = 30 * fs
    widths = split(max(width - label_px - 2 * spacing, 3.0), 3)  # Vega rounds panel sizes: one takes the rest
    panel_h = max(height - 110 * fs, 1.0)  # first guess; fit corrects for the titles and axis

    panels = []
    for i, lens in enumerate((VERCEL, OPENROUTER, RAMP)):
        v = {r["vendor_id"]: r for r in at.filter(pl.col("lens") == lens).iter_rows(named=True)}
        rows = []
        for lab in [*labs, *extra]:
            r = v.get(lab)
            c = color("accent") if lab in hot else LIGHT
            if lab in labs and r is not None:
                ranked = r["value_pct"] >= floor  # under the floor, labs are not ranked against each other
                text = f"#{r['rank_six']} · {_pct(r['value_pct'])}" if ranked else _pct(r["value_pct"])
                rows.append(
                    {
                        "label": names[lab],
                        "pct": r["value_pct"],
                        "text_x": r["value_pct"],
                        "c": c,
                        "tc": color("text_secondary"),
                        "text": text,
                    }
                )
            elif r is not None:  # a gateway lab Ramp does not report: value only (ranks are among Ramp's labs)
                rows.append(
                    {
                        "label": names[lab],
                        "pct": r["value_pct"],
                        "text_x": r["value_pct"],
                        "c": DARK,
                        "tc": DARK,
                        "text": _pct(r["value_pct"]),
                    }
                )
            else:
                rows.append(
                    {
                        "label": names[lab],
                        "pct": None,
                        "text_x": 0,
                        "c": DARK,
                        "tc": DARK,
                        "text": "not reported" if lens == RAMP else "—",
                    }
                )
        # subtitles wrap from the box, not the size being fitted: a line-count change mid-fit would jump the outer size
        panels.append(_dot_panel(rows, domain, widths[i], panel_h, fs, i == 0, _title(PANEL[lens][0], subs[i], fs)))
    return alt.hconcat(*panels, spacing=spacing).resolve_scale(color="independent").configure(**vl_config(fs))


def _wrap(sub: str, fs: float, max_px: float) -> str | list[str]:
    """A panel subtitle as lines no wider than max_px (Vega widens a panel to its title)."""
    px = (LABEL_PX - 3) * fs * 0.56  # rough Inter advance per character
    if len(sub) * px <= max_px:
        return sub
    lines: list[str] = []
    for word in sub.split(" "):
        if lines and len(lines[-1]) + 1 + len(word) <= max_px / px:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return lines


# ---- leaders ----------------------------------------------------------------------------------


def leaders(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False):
    box = (width, height) if isinstance(width, int | float) and isinstance(height, int | float) else (900, 520)
    return fit(lambda w, h: _leaders(story, w, h, font_scale, box), width, height)


def _leaders(story: Story, width: float, height: float, fs: float, box: tuple[float, float]):
    """Side by side in a wide box (x_png), stacked in a tall one (linkedin_png); layout fixed from the box."""
    fonts = brand()["fonts"]
    vc = brand()["colors"]["vendor_colors"]
    names = _names(story)
    lv = story.frames["lenses"].filter(
        pl.col("lens").is_in([VERCEL, OPENROUTER, RAMP]) & pl.col("vendor_id").is_in(LEAD_LABS) & ~pl.col("partial")
    )
    first, last = lv["month"].min(), lv["month"].max()
    wide = box[0] / box[1] > 2.5
    spacing = (40 if wide else 26) * fs
    label_px = (13 * 0.55 * (LABEL_PX - 2) + 22) * fs  # "Anthropic 46%"
    if wide:
        plot_ws = split(max(width - 3 * 50 * fs - 2 * spacing, 3.0), 3)  # first guess; fit corrects for the axes
        heights = [max(height - 90 * fs, 1.0)] * 3
    else:
        plot_ws = [max(width - 60 * fs, 1.0)] * 3
        heights = split(max(height - 2 * spacing - 3 * 56 * fs, 3.0), 3)
    if min(heights) < 70 * fs:
        raise ValueError(f"leaders: panels {min(heights):.0f}px tall are too short to read; shorten the page text")
    box_pw = (box[0] - 3 * 50 * fs - 2 * spacing) / 3
    subs = _subs([PANEL[x][1] for x in (VERCEL, OPENROUTER, RAMP)], [box_pw] * 3, fs) if wide else None
    months = sorted(set(lv["month"]))
    ticks = [m for m in months if m.month in ((1, 7) if wide else (1, 4, 7, 10))]
    x_axis = alt.Axis(
        values=[_ms(t) for t in ticks],
        labelExpr=MONTH_LABEL,
        labelFontSize=AXIS_PX * fs,
        grid=False,
        title=None,
    )
    no_x = alt.Axis(labels=False, ticks=False, grid=False, title=None, domain=False)

    panels = []
    for i, lens in enumerate((VERCEL, OPENROUTER, RAMP)):
        pw, ph = plot_ws[i], heights[i]
        span = _ms(last) - _ms(first)
        x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(last) + span * label_px / max(pw - label_px, 1.0)])
        d = lv.filter(pl.col("lens") == lens).sort("month")
        top = 10 * ((d["value_pct"].max() // 10) + 1)
        y_scale = alt.Scale(domain=[0, top], nice=False)
        # fixed ticks: Vega's automatic ones change with the height, which makes the outer size jump during fitting
        y_axis = alt.Axis(
            values=[0, top / 2, top], labelExpr="datum.value + '%'", labelFontSize=AXIS_PX * fs, title=None
        )
        axis = x_axis if (wide or i == 2) else no_x
        rows = d.select(t=pl.col("month").map_elements(_ms, return_dtype=pl.Int64), v="vendor_id", pct="value_pct")
        ends = rows.group_by("v").agg(pl.all().sort_by("t").last()).sort("pct", descending=True)
        gap = (LABEL_PX - 2) * fs * 1.2 / ph * top  # one label height, in data units
        placed: list[float] = []
        end_rows = []
        for r in ends.iter_rows(named=True):
            y = r["pct"] if not placed else min(r["pct"], placed[-1] - gap)
            placed.append(y)
            end_rows.append({**r, "ly": y, "name": f"{names[r['v']]} {r['pct']:.1f}%"})  # one decimal: near-ties
        low = min(placed)
        if low < 0:  # push the stack up so the lowest label stays inside the panel
            end_rows = [{**e, "ly": e["ly"] - low} for e in end_rows]
        layers = []
        x = alt.X("t:T", scale=x_scale, axis=axis)
        for lab in LEAD_LABS:
            c = vc.get(lab, LIGHT)
            mine = [e for e in end_rows if e["v"] == lab]
            layers += [
                alt.Chart(alt.Data(values=rows.filter(pl.col("v") == lab).to_dicts()))
                .mark_line(color=c, strokeWidth=2.6 * fs)
                .encode(x=x, y=alt.Y("pct:Q", scale=y_scale, axis=y_axis)),
                alt.Chart(alt.Data(values=mine))
                .mark_circle(size=70 * fs**2, opacity=1, color=c, stroke=color("canvas"), strokeWidth=2)
                .encode(x=x, y=alt.Y("pct:Q", scale=y_scale, axis=y_axis)),
                alt.Chart(alt.Data(values=mine))
                .mark_text(
                    align="left",
                    baseline="middle",
                    dx=10 * fs,
                    fontSize=(LABEL_PX - 2) * fs,
                    font=fonts["body"],
                    color=color("text"),
                )
                .encode(x=x, y=alt.Y("ly:Q", scale=y_scale, axis=y_axis), text="name:N"),
            ]
        head, sub = PANEL[lens]
        panels.append(
            alt.layer(*layers).properties(width=pw, height=ph, title=_title(head, subs[i] if wide else sub, fs))
        )
    if wide:
        return (
            alt.hconcat(*panels, spacing=spacing)
            .resolve_scale(y="independent", x="independent")
            .configure(**vl_config(fs))
        )
    return alt.vconcat(*panels, spacing=spacing).resolve_scale(y="independent").configure(**vl_config(fs))


# ---- tokens_spend -----------------------------------------------------------------------------


def tokens_spend(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.VConcatChart:
    box = (width, height) if isinstance(width, int | float) and isinstance(height, int | float) else (900, 520)
    return fit(lambda w, h: _tokens_spend(story, w, h, font_scale, box), width, height)


def _tokens_spend(story: Story, width: float, height: float, fs: float, box: tuple[float, float]):
    month = date.fromisoformat(story.extra["month"])
    names = _names(story)
    labs = story.extra["token_rows"]
    at = story.frames["lenses"].filter(pl.col("month") == month)
    domain = [names[v] for v in labs]
    top_tok = {
        at.filter((pl.col("lens") == t) & pl.col("named")).sort("value_pct", descending=True)["vendor_id"][0]
        for t in ("vercel_tokens", "openrouter_tokens")
    }
    hot = top_tok if len(top_tok) == 1 else set()

    def rows_for(lens: str) -> list[dict]:
        v = {r["vendor_id"]: r for r in at.filter(pl.col("lens") == lens).iter_rows(named=True)}
        out = []
        for lab in labs:
            r = v.get(lab)
            c = color("accent") if lab in hot else LIGHT
            if r is None:
                out.append({"label": names[lab], "pct": None, "text_x": 0, "c": c, "tc": DARK, "text": "—"})
            else:
                out.append(
                    {
                        "label": names[lab],
                        "pct": r["value_pct"],
                        "text_x": r["value_pct"],
                        "c": c,
                        "tc": color("text_secondary"),
                        "text": f"#{r['rank_all']} · {_pct(r['value_pct'])}",
                    }
                )
        return out

    order = ["vercel_tokens", VERCEL, "openrouter_tokens", OPENROUTER]
    wide = box[0] / box[1] > 1.2  # layout from the box, fixed during fitting
    label_px = (max(len(x) for x in domain) * 0.55 * AXIS_PX + 18) * fs
    spacing = 26 * fs
    if wide:  # one row of four panels
        widths = split(max(width - label_px - 3 * spacing, 4.0), 4)
        panel_h = max(height - 110 * fs, 1.0)
        panels = []
        base = (box[0] - label_px - 3 * spacing) / 4
        subs = _subs([PANEL[x][1] for x in order], [base + label_px, base, base, base], fs)
        for i, lens in enumerate(order):
            panels.append(
                _dot_panel(rows_for(lens), domain, widths[i], panel_h, fs, i == 0, _title(PANEL[lens][0], subs[i], fs))
            )
        return alt.hconcat(*panels, spacing=spacing).resolve_scale(color="independent").configure(**vl_config(fs))
    widths = split(max(width - label_px - spacing, 2.0), 2)
    heights = split(max(height - spacing - 2 * 110 * fs, 2.0), 2)
    grid = []
    for j, pair in enumerate((order[:2], order[2:])):
        row = []
        base = (box[0] - label_px - spacing) / 2
        subs = _subs([PANEL[x][1] for x in order], [base + label_px, base, base + label_px, base], fs)
        for i, lens in enumerate(pair):
            k = order.index(lens)
            row.append(
                _dot_panel(
                    rows_for(lens), domain, widths[i], heights[j], fs, i == 0, _title(PANEL[lens][0], subs[k], fs)
                )
            )
        grid.append(alt.hconcat(*row, spacing=spacing).resolve_scale(color="independent"))
    return alt.vconcat(*grid, spacing=spacing).resolve_scale(color="independent").configure(**vl_config(fs))


# ---- run_rates --------------------------------------------------------------------------------


def run_rates(story: Story, width, height, font_scale: float = 1.0, interactive: bool = False) -> alt.LayerChart:
    return fit(lambda w, h: _run_rates(story, w, h, font_scale), width, height)


def _run_rates(story: Story, width: float, height: float, fs: float) -> alt.LayerChart:
    fonts = brand()["fonts"]
    vc = brand()["colors"]["vendor_colors"]
    rr = story.frames["run_rates"].filter(pl.col("plotted"))
    first = date(rr["period_start"].min().year, 1, 1)
    last = rr["period_end"].max()
    end = date(last.year, last.month, 1) + timedelta(days=62)
    x_scale = alt.Scale(type="utc", domain=[_ms(first), _ms(end)])
    y_scale = alt.Scale(type="log", domain=[1e9 * 0.8, 7e10], nice=False)
    x_axis = alt.Axis(
        values=[_ms(date(y, 1, 1)) for y in range(first.year, end.year + 1)],
        labelExpr="utcFormat(datum.value, '%Y')",
        labelFontSize=AXIS_PX * fs,
        grid=False,
        title=None,
    )
    y_axis = alt.Axis(
        values=[1e9, 3e9, 1e10, 3e10],
        labelExpr="'$' + format(datum.value / 1e9, ',') + 'B'",
        labelFontSize=AXIS_PX * fs,
        title=None,
    )
    rows = rr.with_columns(
        t0=pl.col("period_start").map_elements(_ms, return_dtype=pl.Int64),
        t1=pl.col("period_end").map_elements(_ms, return_dtype=pl.Int64),
        c=pl.col("vendor_id").replace_strict(vc, default=LIGHT),
    ).select("vendor_id", "vendor_name", "value", "label", "span", "t0", "t1", "c")
    x0 = alt.X("t0:T", scale=x_scale, axis=x_axis)
    x1 = alt.X("t1:T", scale=x_scale, axis=x_axis)
    y = alt.Y("value:Q", scale=y_scale, axis=y_axis)
    clr = alt.Color("c:N", scale=None, legend=None)
    spans = alt.Data(values=rows.filter(pl.col("span")).to_dicts())
    points = alt.Data(values=rows.filter(~pl.col("span")).to_dicts())
    text = dict(fontSize=(LABEL_PX - 1) * fs, font=fonts["mono"], color=color("text_secondary"))
    # the company name once, beside its latest figure
    latest = rows.sort("t1").group_by("vendor_id", maintain_order=True).last()
    names = alt.Data(values=latest.to_dicts())
    layers = [
        alt.Chart(spans)
        .mark_rule(strokeWidth=5 * fs, strokeCap="round", opacity=0.9)
        .encode(x=x0, x2="t1:T", y=y, color=clr),
        alt.Chart(spans)
        .mark_text(align="center", baseline="bottom", dy=-8 * fs, **text)
        .encode(x=alt.X("tm:T", scale=x_scale, axis=x_axis), y=y, text="label:N")
        .transform_calculate(tm="(datum.t0 + datum.t1) / 2"),
        alt.Chart(points)
        .mark_circle(size=110 * fs**2, opacity=1, stroke=color("canvas"), strokeWidth=2)
        .encode(x=x1, y=y, color=clr),
        alt.Chart(points)
        .mark_text(align="right", baseline="middle", dx=-10 * fs, **text)
        .encode(x=x1, y=y, text="label:N"),
        alt.Chart(names)
        .mark_text(
            align="left", baseline="middle", dx=12 * fs, fontSize=LABEL_PX * fs, font=fonts["body"], fontWeight="bold"
        )
        .encode(x=x1, y=y, text="vendor_name:N", color=clr),
    ]
    return (
        alt.layer(*layers)
        .properties(width=max(width - 70 * fs, 1.0), height=max(height - 40 * fs, 1.0))
        .configure(**vl_config(fs))
    )

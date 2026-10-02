"""Altair/Vega-Lite config for the Cache Register look: dark canvas, recessive axes, text in ink."""

from __future__ import annotations

from cachereg.viz.brand import brand, color


def vl_config(font_scale: float = 1.0) -> dict:
    fonts = brand()["fonts"]
    ink, ink2, muted = color("text"), color("text_secondary"), color("muted")

    def px(n: float) -> float:
        return round(n * font_scale, 1)

    return {
        "background": color("canvas"),
        "font": fonts["body"],
        "padding": 0,
        "view": {"stroke": None},
        "axis": {
            "domain": False,
            "ticks": False,
            "grid": True,
            "gridColor": "#1C1F27",
            "gridWidth": 1,
            "labelColor": ink2,
            "labelFont": fonts["mono"],
            "labelFontSize": px(15),
            "labelPadding": 10,
            "titleColor": muted,
            "titleFont": fonts["body"],
            "titleFontSize": px(14),
            "titleFontWeight": "normal",
        },
        "axisX": {"grid": False},
        "legend": {
            "labelColor": ink2,
            "labelFont": fonts["body"],
            "labelFontSize": px(15),
            "symbolType": "circle",
            "symbolSize": px(120),
            "titleColor": muted,
            "orient": "top",
            "direction": "horizontal",
            "columnPadding": 22,
            "padding": 0,
            "offset": 18,
        },
        "text": {"color": ink, "font": fonts["body"]},
        "line": {"strokeWidth": 3, "strokeCap": "round", "strokeJoin": "round"},
    }

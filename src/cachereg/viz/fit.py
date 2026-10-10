"""Fit a chart's rendered outer size to the plot box it is pasted into.

``Frame.compose`` resizes a chart's PNG to the plot box exactly, so a chart whose outer size (axes,
titles, concat spacing) differs from the box would be stretched or squeezed. Charts build themselves
through ``fit`` to avoid that (PLAN §10, "Chart fit"; moved here from the two-lenses exploration on its
second use).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import altair as alt
import vl_convert as vlc

TOLERANCE_PX = 1.0  # vl-convert truncates the SVG size to whole PNG pixels: any outer size in [box, box + 1) is the box


def size_or(v, default: float) -> float:
    """``v`` when it is a number, else ``default`` (HTML targets pass non-numeric sizes such as "container")."""
    return v if isinstance(v, int | float) else default


def outer_size(chart: alt.TopLevelMixin) -> tuple[float, float]:
    """The rendered outer width and height of a chart (from vl-convert's SVG)."""
    svg = vlc.vegalite_to_svg(vl_spec=json.dumps(chart.to_dict()))
    return tuple(float(re.search(rf'{k}="([\d.]+)"', svg).group(1)) for k in ("width", "height"))


def split(total: float, n: int) -> list[float]:
    """``total`` over n panels: n − 1 whole-pixel panels and one that takes the remainder (see ``fit``)."""
    base = float(int(total / n))
    return [total - base * (n - 1), *[base] * (n - 1)]


def fit(make: Callable[[float, float], alt.TopLevelMixin], width, height, *, default=(900, 520)):
    """Build ``make(w, h)`` so its rendered outer size (axes and titles included) is width × height.

    Render, measure and correct the inner size until the outer size is in [box, box + 1): the PNG is the SVG
    size truncated to whole pixels (measured 2026-10-09), so that is exactly the box. Vega rounds each concat
    panel's size to whole pixels, so charts with n equal panels should give the remainder to one panel
    (``split``) or their outer size moves in n-pixel steps and may skip the box. A chart that
    cannot shrink to the box (a floor set by titles or labels) is an error, never a silent stretch.
    Non-numeric sizes (HTML) skip fitting and use ``default``.
    """
    if not isinstance(width, int | float) or not isinstance(height, int | float):
        return make(size_or(width, default[0]), size_or(height, default[1]))

    def ok(r: float, target: float) -> bool:
        return target <= r < target + TOLERANCE_PX

    # Per dimension: step by the measured overshoot, then bisect once the target is bracketed (outer sizes
    # move in steps, e.g. when an axis label's width changes, so plain steps can oscillate).
    size, bounds = [float(width), float(height)], [[None, None], [None, None]]
    for _ in range(12):
        rw, rh = outer_size(make(*size))
        if ok(rw, width) and ok(rh, height):
            return make(*size)
        for i, (r, target) in enumerate(((rw, width), (rh, height))):
            if ok(r, target):
                continue
            lo, hi = bounds[i]
            if r >= target + TOLERANCE_PX:
                hi = size[i] if hi is None else min(hi, size[i])
            else:
                lo = size[i] if lo is None else max(lo, size[i])
            bounds[i] = [lo, hi]
            aim = target + TOLERANCE_PX / 2
            size[i] = (lo + hi) / 2 if lo is not None and hi is not None else size[i] - (r - aim)
        if min(size) < 1:
            break
    raise ValueError(
        f"chart cannot fit its {width:.0f}×{height:.0f} box (renders {rw:.0f}×{rh:.0f}): shorten its titles or labels"
    )

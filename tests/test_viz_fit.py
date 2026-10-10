"""cachereg.viz.fit: a chart's rendered outer size matches its plot box, or fitting fails loudly."""

import io
import json

import altair as alt
import pytest
import vl_convert as vlc
from PIL import Image

from cachereg.viz.fit import TOLERANCE_PX, fit, fit_size, outer_size, split

DATA = alt.Data(values=[{"x": "a", "y": 1}, {"x": "b", "y": 3}])


def _panels(w: float, h: float) -> alt.HConcatChart:
    """Two bar panels whose titles and axes make the outer size differ from the inner one."""
    half = max(w / 2, 1.0)

    def panel(title: str) -> alt.Chart:
        return alt.Chart(DATA).mark_bar().encode(x="x:N", y="y:Q").properties(width=half, height=h, title=title)

    return alt.hconcat(panel("A panel title"), panel("A second, rather longer panel title"))


@pytest.mark.parametrize("box", [(800, 450), (517, 733)])
def test_fit_matches_box(box):
    w, h = box
    assert outer_size(_panels(w, h)) != pytest.approx((w, h), abs=TOLERANCE_PX)  # unfitted, it misses
    chart = fit(_panels, w, h)
    rw, rh = outer_size(chart)
    assert w <= rw < w + TOLERANCE_PX and h <= rh < h + TOLERANCE_PX
    png = vlc.vegalite_to_png(vl_spec=json.dumps(chart.to_dict()), scale=1)
    assert Image.open(io.BytesIO(png)).size == (w, h)  # the PNG truncates the SVG size: exactly the box


def test_fit_refuses_a_box_the_chart_cannot_shrink_to():
    def titled(w: float, h: float) -> alt.Chart:
        return alt.Chart(DATA).mark_bar().encode(x="x:N", y="y:Q").properties(width=w, height=h, title="T" * 200)

    with pytest.raises(ValueError, match="cannot fit"):
        fit(titled, 300, 200)


def test_fit_passes_through_non_numeric_sizes():
    chart = fit(lambda w, h: alt.Chart(DATA).mark_bar().properties(width=w, height=h), "container", 400)
    assert chart.to_dict()["width"] == 900 and chart.to_dict()["height"] == 400


@pytest.mark.parametrize(("total", "n"), [(100.5, 3), (10, 4), (7, 1), (1488.25, 2)])
def test_split_gives_whole_pixels_and_one_remainder(total, n):
    parts = split(total, n)
    assert len(parts) == n and sum(parts) == pytest.approx(total)
    assert all(p == int(p) for p in parts[1:]) and parts[0] >= parts[1 % n]


def test_fit_reaches_a_box_three_equal_panels_would_skip():
    """Vega rounds each panel's size, so three equal panels move the outer width in 3 px steps."""

    def three(w: float, h: float) -> alt.HConcatChart:
        return alt.hconcat(
            *[alt.Chart(DATA).mark_bar().encode(x="x:N", y="y:Q").properties(width=pw, height=h) for pw in split(w, 3)]
        )

    for box in (601, 602, 603):
        rw, _ = outer_size(fit(three, box, 300))
        assert box <= rw < box + TOLERANCE_PX


def test_fit_size_gives_the_arguments_fit_uses():
    w, h = fit_size(_panels, 800, 450)
    assert outer_size(_panels(w, h)) == outer_size(fit(_panels, 800, 450))

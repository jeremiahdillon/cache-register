from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from cachereg.viz.motion import Timing, bar_race_frames, ease_in_out_cubic


def test_easing_endpoints_and_monotonic():
    assert ease_in_out_cubic(0) == 0 and ease_in_out_cubic(1) == 1
    xs = [ease_in_out_cubic(i / 20) for i in range(21)]
    assert xs == sorted(xs)


def test_bar_race_overtake_is_continuous():
    k = pl.DataFrame(
        {
            "week": [date(2026, 1, 5)] * 2 + [date(2026, 1, 12)] * 2,
            "name": ["A", "B", "A", "B"],
            "share": [0.6, 0.4, 0.3, 0.7],
        }
    )
    t = Timing(fps=10, move_frames=10, hold_frames=2, final_hold_s=0.5)
    f = bar_race_frames(k, "name", "share", "week", top_n=2, timing=t)
    assert f["frame"].max() + 1 == 2 + 10 + 5  # hold, move, final hold
    a = f.filter(pl.col("name") == "A").sort("frame")
    assert a["rank_pos"][0] == 1 and a["rank_pos"][-1] == 2
    steps = a["rank_pos"].diff().drop_nulls().abs()
    assert steps.max() < 0.25  # slides, never jumps
    assert a["share"][-1] == pytest.approx(0.3)


def test_missing_keyframe_values_enter_from_offscreen():
    k = pl.DataFrame(
        {
            "week": [date(2026, 1, 5), date(2026, 1, 12), date(2026, 1, 12)],
            "name": ["A", "A", "C"],
            "share": [1.0, 0.5, 0.5],
        }
    )
    f = bar_race_frames(k, "name", "share", "week", top_n=1, timing=Timing(10, 4, 1, 0.1))
    c = f.filter(pl.col("name") == "C").sort("frame")
    assert c["share"][0] == 0 and c["rank_pos"][0] == 2  # starts off-screen (top_n + 1)

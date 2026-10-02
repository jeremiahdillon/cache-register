"""Motion: precomputed frame data → per-frame chart renders → ffmpeg (PLAN §6.3).

Vega-Lite has no tweening, so all motion is computed here *before* rendering:
keyframes → eased interpolation → explicit positions → fixed domains. Each frame is then
rendered from the same chart function used for static and HTML targets.
"""

from __future__ import annotations

import json
import multiprocessing
import subprocess
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg
import polars as pl

from cachereg.viz.brand import register_fonts
from cachereg.viz.layout import Frame


def ease_in_out_cubic(t: float) -> float:
    return 4 * t**3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


@dataclass(frozen=True)
class Timing:
    fps: int = 30
    move_frames: int = 20  # frames spent moving between two keyframes
    hold_frames: int = 8  # frames resting on each keyframe
    final_hold_s: float = 3.0


def bar_race_frames(
    keyframes: pl.DataFrame, key: str, value: str, time: str, top_n: int, timing: Timing | None = None
) -> pl.DataFrame:
    """Interpolate a ranked bar race.

    ``keyframes`` has one row per (time, key). Returns one row per (frame, key) with
    ``value`` interpolated, ``rank_pos`` (continuous, 1 = top; off-screen = top_n + 1)
    and ``label_time`` (the keyframe currently shown).
    """
    timing = timing or Timing()
    times = sorted(keyframes[time].unique().to_list())
    keys = sorted(keyframes[key].unique().to_list())
    full = (
        pl.DataFrame({time: times})
        .join(pl.DataFrame({key: keys}), how="cross")
        .join(keyframes.select(time, key, value), on=[time, key], how="left")
        .with_columns(pl.col(value).fill_null(0.0))
        .with_columns(pl.col(value).rank("ordinal", descending=True).over(time).alias("_rank"))
        .with_columns(pl.min_horizontal(pl.col("_rank"), pl.lit(top_n + 1)).cast(pl.Float64).alias("_rank"))
    )
    by_time = {t: full.filter(pl.col(time) == t).sort(key) for t in times}

    rows, frame = [], 0

    def emit(a, b, t, label):
        nonlocal frame
        e = ease_in_out_cubic(t)
        va, vb = a[value].to_list(), b[value].to_list()
        ra, rb = a["_rank"].to_list(), b["_rank"].to_list()
        for i, k in enumerate(keys):
            rows.append(
                {
                    "frame": frame,
                    key: k,
                    value: va[i] + (vb[i] - va[i]) * e,
                    "rank_pos": ra[i] + (rb[i] - ra[i]) * e,
                    "label_time": label,
                }
            )
        frame += 1

    for i, t0 in enumerate(times):
        a = by_time[t0]
        hold = timing.hold_frames if i < len(times) - 1 else int(timing.final_hold_s * timing.fps)
        for _ in range(hold):
            emit(a, a, 0.0, t0)
        if i < len(times) - 1:
            b = by_time[times[i + 1]]
            for f in range(1, timing.move_frames + 1):
                t = f / timing.move_frames
                emit(a, b, t, times[i + 1] if t >= 0.5 else t0)
    return pl.DataFrame(rows)


# ---- renderer A: vl-convert per frame (parallel processes) -----------------------------


def _init_worker() -> None:
    register_fonts()


def _render_png(spec_json: str) -> bytes:
    import vl_convert as vlc

    return vlc.vegalite_to_png(vl_spec=spec_json, scale=1)


def render_frames_vlconvert(specs: list[dict], workers: int = 8) -> list[bytes]:
    payload = [json.dumps(s) for s in specs]
    # "spawn", never fork: forking after polars/DuckDB have started threads can deadlock (Linux default).
    ctx = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, mp_context=ctx) as pool:
        return list(pool.map(_render_png, payload, chunksize=4))


# ---- encoding ---------------------------------------------------------------------------


def encode(frames: list[bytes], page: Frame, out: Path, fps: int, fmt: str = "mp4") -> Path:
    """Compose each plot render into the page and encode with the bundled ffmpeg."""
    w, h = page.base.size
    codec = (
        ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "slow", "-movflags", "+faststart"]
        if fmt == "mp4"
        else ["-c:v", "libvpx-vp9", "-pix_fmt", "yuv420p", "-b:v", "0", "-crf", "32", "-row-mt", "1"]
    )
    cmd = [
        imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
        *codec, str(out),
    ]  # fmt: skip
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for png in frames:
            proc.stdin.write(page.compose(png).tobytes())
    finally:
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed encoding {out.name}")
    return out


def build_specs(frame_data: pl.DataFrame, chart_fn: Callable[[pl.DataFrame], dict]) -> list[dict]:
    return [chart_fn(frame_data.filter(pl.col("frame") == i)) for i in range(frame_data["frame"].max() + 1)]

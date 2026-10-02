"""The Story: the single canonical output of an analysis (PLAN §6.1), and render targets (§6.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import polars as pl


@dataclass
class Story:
    slug: str
    title: str  # the claim, not a description of the chart
    subtitle: str  # metric definition / scope
    frames: dict[str, pl.DataFrame]  # the only data any rendering may use (aggregated)
    sources: list[str]  # registry ids; attributions come from config/sources.yaml
    as_of: date
    method: str  # one line, shown in the footer
    caveats: list[str] = field(default_factory=list)  # shown in README / HTML, not on images
    notes: list[str] = field(default_factory=list)  # short on-image notes (e.g. shading legend)
    notes_by_kind: dict[str, list[str]] = field(default_factory=dict)  # override notes for "video" etc.

    def notes_for(self, kind: str) -> list[str]:
        return self.notes_by_kind.get(kind, self.notes)

    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Target:
    name: str
    kind: str  # "static" | "html" | "video"
    width: int
    height: int
    title_px: int = 52
    subtitle_px: int = 26
    footer_px: int = 16
    pad: int = 56
    font_scale: float = 1.0
    fmt: str = "png"  # png | svg | mp4 | webm | html


TARGETS = {
    t.name: t
    for t in [
        Target("x_png", "static", 1600, 900, 50, 24, 15, 56, 1.15),
        Target("linkedin_png", "static", 1080, 1350, 54, 26, 16, 56, 1.15),
        Target("blog_html", "html", 960, 560, fmt="html"),
        Target("x_video", "video", 1920, 1080, 56, 26, 17, 64, 1.3, fmt="mp4"),
        Target("linkedin_video", "video", 1080, 1350, 54, 26, 16, 56, 1.2, fmt="mp4"),
        Target("web_video", "video", 1080, 1350, 54, 26, 16, 56, 1.2, fmt="webm"),
    ]
}

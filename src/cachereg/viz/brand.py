"""Brand settings (config/brand/brand.yaml) and vendored fonts."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

from cachereg.core.paths import REPO_ROOT

FONT_DIR = REPO_ROOT / "assets" / "fonts"
FONT_FILES = {
    "display": "SpaceGrotesk-Bold.ttf",
    "display_medium": "SpaceGrotesk-Medium.ttf",
    "body": "Inter-Regular.ttf",
    "body_semibold": "Inter-SemiBold.ttf",
    "mono": "JetBrainsMono-Regular.ttf",
    "mono_bold": "JetBrainsMono-Bold.ttf",
}


@cache
def brand() -> dict:
    return yaml.safe_load((REPO_ROOT / "config" / "brand" / "brand.yaml").read_text())


def color(name: str) -> str:
    return brand()["colors"][name]


def font_path(role: str) -> Path:
    return FONT_DIR / FONT_FILES[role]


@cache
def register_fonts() -> None:
    """Make the vendored fonts available to vl-convert (once per process)."""
    import vl_convert as vlc

    vlc.register_font_directory(str(FONT_DIR))

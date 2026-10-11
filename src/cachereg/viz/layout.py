"""Raster layout: headline, subtitle, plot and receipt footer composed at an exact pixel size.

The chart itself comes from the shared Altair spec (rendered by vl-convert); the "chrome"
around it is drawn here so every static image and every video frame shares one layout.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from cachereg.story.model import Story, Target
from cachereg.viz.brand import brand, color, font_path
from cachereg.viz.stamp import Receipt


def _font(role: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(role)), size)


def _split_long(draw: ImageDraw.ImageDraw, word: str, font, width: int) -> list[str]:
    """Break a word wider than the line (e.g. a URL) after '/' characters."""
    if draw.textlength(word, font=font) <= width:
        return [word]
    parts, cur = [], ""
    for chunk in word.replace("/", "/\0").split("\0"):
        if cur and draw.textlength(cur + chunk, font=font) > width:
            parts.append(cur)
            cur = chunk
        else:
            cur += chunk
    return parts + ([cur] if cur else [])


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, cur = [], ""
    # Split on ordinary whitespace only, so a non-breaking space (U+00A0) keeps a phrase on one line.
    words = [p for w in re.split(r"[ \t\n]+", text.strip()) for p in _split_long(draw, w, font, width)]
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def _wrap_balanced(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    """Wrap into the fewest lines, then narrow the measure as far as it goes without adding a line, so
    the lines come out roughly even (no long first line over a short orphan)."""
    lines = _wrap(draw, text, font, width)
    if len(lines) < 2:
        return lines
    lo, hi = width // len(lines), width
    while hi - lo > 4:
        mid = (lo + hi) // 2
        if len(_wrap(draw, text, font, mid)) <= len(lines):
            hi = mid
        else:
            lo = mid
    return _wrap(draw, text, font, hi)


@dataclass
class Frame:
    """A pre-rendered page with an empty plot box; paste each chart render into ``plot_box``."""

    base: Image.Image
    plot_box: tuple[int, int, int, int]  # left, top, width, height

    def compose(self, plot_png: bytes) -> Image.Image:
        img = self.base.copy()
        plot = Image.open(io.BytesIO(plot_png)).convert("RGB")
        left, top, w, h = self.plot_box
        if plot.size != (w, h):
            plot = plot.resize((w, h), Image.LANCZOS)
        img.paste(plot, (left, top))
        return img


def page(story: Story, target: Target, receipt: Receipt) -> Frame:
    W, H, pad = target.width, target.height, target.pad
    img = Image.new("RGB", (W, H), color("canvas"))
    d = ImageDraw.Draw(img)
    inner = W - 2 * pad
    y = pad

    # Wordmark: optional lime glyph + name, in the brand's wordmark colour
    mark = brand().get("wordmark", {})
    mark_px = max(14, target.footer_px)
    x = pad
    if mark.get("glyph", True):
        d.rectangle([pad, y + 2, pad + mark_px - 2, y + mark_px], fill=color("signal"))
        x += mark_px + 10
    mark_fill = mark.get("color", color("text"))
    d.text((x, y), brand()["name"].upper(), font=_font("mono_bold", mark_px), fill=mark_fill)
    y += mark_px + int(target.title_px * 0.6)

    title_font = _font("display", target.title_px)
    for line in _wrap_balanced(d, story.title, title_font, inner):
        d.text((pad, y), line, font=title_font, fill=color("text"))
        y += int(target.title_px * 1.12)
    y += int(target.subtitle_px * 0.35)
    sub_font = _font("body", target.subtitle_px)
    for line in _wrap_balanced(d, story.subtitle, sub_font, inner):
        d.text((pad, y), line, font=sub_font, fill=color("text_secondary"))
        y += int(target.subtitle_px * 1.35)
    plot_top = y + int(target.subtitle_px * 0.9)

    # Footer (receipt), laid out bottom-up
    foot_font = _font("mono", target.footer_px)
    label_font = _font("mono_bold", target.footer_px)
    label_w = int(d.textlength("RECEIPTS  ", font=label_font))
    rows = []
    for label, text in receipt.lines():
        wrapped = _wrap_balanced(d, text, foot_font, inner - label_w)
        rows.append((label, wrapped))
    for note in story.notes_for(target.kind):
        rows.insert(0, ("NOTE", _wrap_balanced(d, note, foot_font, inner - label_w)))
    line_h = int(target.footer_px * 1.5)
    footer_h = sum(len(w) for _, w in rows) * line_h
    fy = H - pad - footer_h
    rule_y = fy - int(line_h * 0.9)
    dash = int(target.footer_px * 0.6)
    for x in range(pad, W - pad, dash * 2):
        d.line([(x, rule_y), (min(x + dash, W - pad), rule_y)], fill=color("muted"), width=1)
    for label, wrapped in rows:
        d.text((pad, fy), label, font=label_font, fill=color("muted"))
        for line in wrapped:
            d.text((pad + label_w, fy), line, font=foot_font, fill=color("text_secondary"))
            fy += line_h

    plot_bottom = rule_y - int(line_h * 1.2)
    return Frame(img, (pad, plot_top, inner, plot_bottom - plot_top))

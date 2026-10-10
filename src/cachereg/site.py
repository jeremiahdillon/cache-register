"""`cachereg site`: the static short-link site published to GitHub Pages (cacheregister.dev).

Receipts get short links: the folder name *is* the link, so `receipts/<topic>/` is
`cacheregister.dev/<topic>`, which redirects to that folder on GitHub. An exploration may reserve one with
`link:` in its explore.yaml (so its visuals can carry the link before promotion); it redirects to the
exploration until a receipt promoted from it (`promoted_from`) takes the same name over.
Retired or renamed links live on in config/link-aliases.yaml so URLs on posted images never break.
The root is a splash page (assets/templates/site.html, also the 404) open to search and AI crawlers.
Below the splash, the root shows a scroll-snapped reel of the newest receipts, built from their
committed output/: one slide each, in the shape that fits the viewport (portrait → linkedin_*,
landscape → x_*), with the motion visual played by assets/site/reel.js while on screen.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from string import Template

import yaml

from cachereg.core.paths import REPO_ROOT
from cachereg.story.model import TARGETS
from cachereg.viz.brand import FONT_FILES, brand, color, font_path, register_fonts

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG = 32
RESERVED = {"index", "404", "assets", "about", "api", "static", "media"}
TEMPLATES = REPO_ROOT / "assets" / "templates"
SITE_SCRIPTS = REPO_ROOT / "assets" / "site"
REEL_SIZE = 6  # newest receipts that get a full slide; older ones are listed as text
SHAPES = {"portrait": "linkedin", "landscape": "x"}  # viewport orientation → render target prefix
SPLASH_FONTS = ("display", "body", "mono")  # the faces site.html declares
# Splash intro timing (ms): cursor alone, then one keystroke per letter (a fixed, slightly uneven
# rhythm so it reads as typed), a pause, then the rest of the page fades in.
TYPE_START = 2000
KEYSTROKES = (95, 70, 110, 80, 125, 75, 90, 105)
WORD_GAP = 180
REVEAL_PAUSE = 1100


@dataclass(frozen=True)
class Link:
    slug: str
    analysis: str  # repo-relative folder
    title: str


def _title(folder: Path) -> str:
    cfg = yaml.safe_load((folder / "receipt.yaml").read_text()) or {}
    if cfg.get("title"):
        return str(cfg["title"])
    readme = folder / "README.md"
    if readme.is_file():
        for line in readme.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return folder.name


def collect_links(root: Path = REPO_ROOT) -> list[Link]:
    """Every receipt (folder name = link), every link an exploration reserves, plus aliases, validated:
    well-formed, unique, and pointing at real folders."""
    links: dict[str, Link] = {}
    promoted: dict[str, str] = {}  # receipt slug -> the exploration it was promoted from
    for spec in sorted((root / "receipts").glob("*/receipt.yaml")):
        folder = spec.parent
        check_slug(folder.name, folder)
        rel = folder.relative_to(root).as_posix()
        links[folder.name] = Link(folder.name, rel, _title(folder))
        src = (yaml.safe_load(spec.read_text()) or {}).get("promoted_from")
        if src:
            promoted[folder.name] = str(src).rstrip("/")
    reserved: dict[str, str] = {}
    for spec in sorted((root / "explore").glob("*/explore.yaml")):
        cfg = yaml.safe_load(spec.read_text()) or {}
        slug = cfg.get("link")
        if slug is None:
            continue
        slug, folder = str(slug), spec.parent
        check_slug(slug, spec)
        rel = folder.relative_to(root).as_posix()
        if slug in reserved:
            raise ValueError(f"link {slug!r} is reserved by both {reserved[slug]} and {rel}")
        reserved[slug] = rel
        if slug in links:
            if promoted.get(slug) == rel:
                continue  # promoted: the receipt now owns the link
            raise ValueError(f"link {slug!r} reserved by {rel} is already a receipt not promoted from it")
        links[slug] = Link(slug, rel, str(cfg.get("title") or folder.name))
    aliases_file = root / "config" / "link-aliases.yaml"
    aliases = (yaml.safe_load(aliases_file.read_text()) or {}).get("aliases") or {} if aliases_file.is_file() else {}
    for slug, target in aliases.items():
        check_slug(slug, aliases_file)
        if slug in links:
            raise ValueError(f"alias {slug!r} collides with a live link")
        if target not in links:
            raise ValueError(f"alias {slug!r} points at unknown link {target!r}")
        links[slug] = Link(slug, links[target].analysis, links[target].title)
    return sorted(links.values(), key=lambda link: link.slug)


@dataclass(frozen=True)
class ReelItem:
    slug: str
    title: str
    as_of: date
    still: dict[str, Path]  # shape → file in output/; both shapes always present (fallback: the other)
    video: dict[str, Path] | None


def _pick(folder: Path, visuals: list[dict], kind: str) -> dict[str, Path] | None:
    """The first visual rendered to a `kind` ("png" | "video") target, as shape → existing file."""
    for visual in visuals:
        files = {}
        for shape, prefix in SHAPES.items():
            target = f"{prefix}_{kind}"
            path = folder / "output" / f"{visual['name']}.{target}.{TARGETS[target].fmt}"
            if target in (visual.get("targets") or []) and path.is_file():
                files[shape] = path
        if files:
            return {shape: files.get(shape) or next(iter(files.values())) for shape in SHAPES}
    return None


def collect_reel(root: Path = REPO_ROOT) -> list[ReelItem]:
    """Every receipt with a rendered still, newest as_of first. Aliases never get slides."""
    items = []
    for spec in sorted((root / "receipts").glob("*/receipt.yaml")):
        folder = spec.parent
        check_slug(folder.name, folder)
        cfg = yaml.safe_load(spec.read_text()) or {}
        visuals = cfg.get("visuals") or []
        still = _pick(folder, visuals, "png")
        if still is None:
            continue
        as_of = date.fromisoformat(str(cfg["as_of"]))
        items.append(ReelItem(folder.name, _title(folder), as_of, still, _pick(folder, visuals, "video")))
    return sorted(items, key=lambda item: (-item.as_of.toordinal(), item.slug))


def _attr(text: object) -> str:
    """Escape for markup built here: `_template` passes `raw` fields through as-is."""
    return html.escape(str(text), quote=True)


def _media_urls(item: ReelItem, files: dict[str, Path]) -> dict[str, str]:
    return {shape: _attr(f"/media/{item.slug}/{path.name}") for shape, path in files.items()}


def _reel_markup(items: list[ReelItem]) -> str:
    """Slides for the newest REEL_SIZE receipts, a text list of the rest, and the player script."""
    if not items:
        return ""
    host = brand()["short_link_host"]
    slides = []
    for i, item in enumerate(items[:REEL_SIZE]):
        still, video = _media_urls(item, item.still), ""
        if item.video:
            src = _media_urls(item, item.video)
            video = (
                f'<video muted loop playsinline preload="none" aria-hidden="true" tabindex="-1"'
                f' data-portrait="{src["portrait"]}" data-landscape="{src["landscape"]}"></video>'
            )
        slides.append(
            f'<section class="slide" aria-label="{_attr(item.title)}"><div class="media">'
            f'<picture><source media="(orientation: portrait)" srcset="{still["portrait"]}">'
            f'<img src="{still["landscape"]}" alt="{_attr(item.title)}"'
            f' loading="lazy" decoding="async"></picture>{video}</div>'
            f'<div class="meta"><span>#{len(items) - i:03d} · As of {item.as_of.isoformat()}</span>'
            f'<span class="dots" aria-hidden="true"></span>'
            f'<a href="/{_attr(item.slug)}">{_attr(host)}/{_attr(item.slug)} →</a></div></section>'
        )
    older = ""
    if len(items) > REEL_SIZE:
        rows = "".join(
            f'<li><a href="/{_attr(item.slug)}">{_attr(item.slug)}</a><span class="dots" aria-hidden="true"></span>'
            f"<span>{_attr(item.title)}</span></li>"
            for item in items[REEL_SIZE:]
        )
        older = f'<section class="older"><p class="label">Older receipts</p><ul>{rows}</ul></section>'
    return "\n".join(slides) + older + '\n<script src="/assets/reel.js" defer></script>'


def _copy_media(out: Path, items: list[ReelItem]) -> None:
    """Only the files the slides use, under /media/<slug>/ (a reserved slug)."""
    for item in items[:REEL_SIZE]:
        dest = out / "media" / item.slug
        dest.mkdir(parents=True, exist_ok=True)
        for path in {*item.still.values(), *(item.video or {}).values()}:
            shutil.copyfile(path, dest / path.name)


def check_slug(slug: str, where: Path) -> None:

    if not SLUG_RE.match(slug) or len(slug) > MAX_SLUG or slug in RESERVED:
        raise ValueError(f"bad link {slug!r} in {where}: lowercase words joined by '-', ≤ {MAX_SLUG} chars")


def short_url(slug: str) -> str:
    return f"{brand()['short_link_host']}/{slug}"


def _redirect_page(target: str, title: str) -> str:
    t, h = html.escape(target, quote=True), html.escape(title)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h} · {html.escape(brand()["name"])}</title>
<link rel="canonical" href="{t}">
<meta http-equiv="refresh" content="0; url={t}">
<script>location.replace({json.dumps(target)});</script>
<style>body{{margin:0;padding:48px 16px;background:{color("canvas")};color:{color("text")};
font:16px/1.5 system-ui,sans-serif}}a{{color:{color("signal")}}}</style>
</head><body><p>{h}</p><p>Redirecting to <a href="{t}">{t}</a></p></body></html>
"""


def _template(name: str, raw: dict[str, str] | None = None, **values: str) -> str:
    """Fill assets/templates/<name> with brand colours plus `values` (HTML-escaped) and `raw` (markup built here)."""
    b = brand()
    fields = {**b["colors"], "name": b["name"], "tagline": b["tagline"], **values}
    escaped = {k: html.escape(str(v), quote=True) for k, v in fields.items() if isinstance(v, str)}
    return Template((TEMPLATES / name).read_text(encoding="utf-8")).substitute(escaped, **(raw or {}))


def _bare(url: str) -> str:
    return re.sub(r"^https?://", "", url).rstrip("/")


def _typed(text: str) -> tuple[str, int]:
    """Wrap each character in a span that appears at its keystroke time; returns (markup, typing ms)."""
    spans, t = [], 0
    for i, ch in enumerate(text):
        t += WORD_GAP if ch == " " else KEYSTROKES[i % len(KEYSTROKES)]
        spans.append(f'<span class="k" style="--t:{TYPE_START + t}ms">{html.escape(ch)}</span>')
    return "".join(spans), t


def _splash_page(kicker: str, heading: str, lede: str, page_title: str, indexable: bool = True, reel: str = "") -> str:
    b = brand()
    home = html.escape(b["site_url"].rstrip("/") + "/", quote=True)
    index_meta = f'<link rel="canonical" href="{home}">' if indexable else '<meta name="robots" content="noindex">'
    heading_typed, typing_ms = _typed(heading)
    return _template(
        "site.html",
        raw={
            "index_meta": index_meta,
            "heading_typed": heading_typed,
            "type_start_ms": str(TYPE_START),
            "typing_ms": str(typing_ms),
            "reveal_ms": str(TYPE_START + typing_ms + REVEAL_PAUSE),
            "reel": reel,
            "body_class": "reel" if reel else "",
            "scroll_hint": '<p class="hint reveal" aria-hidden="true">Latest receipts</p>' if reel else "",
        },
        kicker=kicker,
        heading=heading,
        lede=lede,
        page_title=page_title,
        description=" ".join(b["description"].split()),
        site_url=b["site_url"].rstrip("/"),
        repo_url=b["repo_url"],
        repo_label=_bare(b["repo_url"]).removeprefix("github.com/"),
        author_url=b["author_url"],
        author_label=_bare(b["author_url"]),
        **{f"font_{role}": FONT_FILES[role] for role in SPLASH_FONTS},
    )


def _write_assets(out: Path) -> None:
    """Favicon, Open Graph card and the self-hosted fonts, under /assets (a reserved slug)."""
    import vl_convert as vlc

    assets = out / "assets"
    (assets / "fonts").mkdir(parents=True)
    for role in SPLASH_FONTS:
        shutil.copyfile(font_path(role), assets / "fonts" / FONT_FILES[role])
    shutil.copyfile(SITE_SCRIPTS / "reel.js", assets / "reel.js")
    favicon = _template("favicon.svg")
    (assets / "favicon.svg").write_text(favicon, encoding="utf-8")
    register_fonts()
    (assets / "apple-touch-icon.png").write_bytes(vlc.svg_to_png(favicon, scale=180 / 64))
    card = _template("og-card.svg", name_upper=brand()["name"].upper(), host_upper=brand()["short_link_host"].upper())
    (assets / "og.png").write_bytes(vlc.svg_to_png(card, scale=1))


def _crawler_files(out: Path) -> None:
    """Open to every crawler, search and AI alike; the sitemap lists the one real page (short links redirect)."""
    site = brand()["site_url"].rstrip("/")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n")
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"  <url><loc>{html.escape(site)}/</loc></url>\n"
        "</urlset>\n"
    )


def build_site(out: Path, root: Path = REPO_ROOT) -> list[Link]:
    b = brand()
    repo = b["repo_url"].rstrip("/")
    links = collect_links(root)
    reel = collect_reel(root)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    host = b["short_link_host"]
    (out / "index.html").write_text(
        _splash_page(
            kicker=host, heading=b["name"], lede=f"{b['tagline']}.", page_title=b["name"], reel=_reel_markup(reel)
        ),
        encoding="utf-8",
    )
    (out / "404.html").write_text(
        _splash_page(
            kicker="Error 404",
            heading="No sale",
            lede="That link isn’t on the register.",
            page_title=f"Not found · {b['name']}",
            indexable=False,
        ),
        encoding="utf-8",
    )
    _write_assets(out)
    _copy_media(out, reel)
    _crawler_files(out)
    for link in links:
        page = out / link.slug / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(_redirect_page(f"{repo}/tree/main/{link.analysis}", link.title))
    return links

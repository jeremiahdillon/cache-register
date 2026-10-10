"""`cachereg site`: the static site published to GitHub Pages (cacheregister.dev).

Receipts get short links: the folder name *is* the link, so `receipts/<topic>/` is
`cacheregister.dev/<topic>`, the receipt's page: its charts (one slide per chart, in receipt.yaml order;
a chart's still and video share a slide) built from its committed output/, with its folder on GitHub one
click away. A receipt with nothing rendered yet redirects to that folder instead. An exploration may
reserve a link with `link:` in its explore.yaml (so its visuals can carry the link before promotion); it
redirects to the exploration on GitHub until a receipt promoted from it (`promoted_from`) takes the same
name over. Retired or renamed links live on in config/link-aliases.yaml (redirecting to the receipt's
page) so URLs on posted images never break.
The root is a splash page (assets/templates/site.html, also the 404) open to search and AI crawlers.
Below the splash, a scroll-snapped reel shows the newest receipts, one slide each. Every slide is in the
shape that fits the viewport (portrait → linkedin_*, landscape → x_*), with the motion visual played by
assets/site/reel.js while on screen.
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
SITE_STATIC = REPO_ROOT / "assets" / "site"  # served as-is under /assets: shared stylesheet, reel player
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
class Slide:
    """One chart of a receipt: its still and/or its motion version, each as shape → file in output/ (both
    shapes always present; a missing one falls back to the other). A chart rendered only as video borrows
    the receipt's first still as its no-JS / failed-video fallback (`borrowed`)."""

    name: str
    still: dict[str, Path]
    video: dict[str, Path] | None
    borrowed: bool = False


@dataclass(frozen=True)
class Receipt:
    slug: str
    title: str
    as_of: date
    slides: list[Slide]

    @property
    def hero(self) -> Slide:
        """The slide that stands for the receipt in the root page's reel: the first with motion, else the first."""
        return next((slide for slide in self.slides if slide.video), self.slides[0])

    @property
    def card(self) -> Path:
        """The share image: the landscape still of the first chart that has a still of its own."""
        return next(slide for slide in self.slides if not slide.borrowed).still["landscape"]


def _rendered(folder: Path, visual: dict, kind: str) -> dict[str, Path] | None:
    """A visual's files for its `kind` ("png" | "video") targets, as shape → existing file, or None."""
    files = {}
    for shape, prefix in SHAPES.items():
        target = f"{prefix}_{kind}"
        path = folder / "output" / f"{visual['name']}.{target}.{TARGETS[target].fmt}"
        if target in (visual.get("targets") or []) and path.is_file():
            files[shape] = path
    return {shape: files.get(shape) or next(iter(files.values())) for shape in SHAPES} if files else None


def _slides(folder: Path, visuals: list[dict]) -> list[Slide]:
    """One slide per chart, in receipt.yaml order; a chart's still and video share one slide."""
    charts: dict[str, dict] = {}
    for visual in visuals:
        chart = charts.setdefault(str(visual.get("chart") or visual["name"]), {"name": visual["name"]})
        for kind, key in (("png", "still"), ("video", "video")):
            if key not in chart and (files := _rendered(folder, visual, kind)):
                chart[key] = files
    first_still = next((chart["still"] for chart in charts.values() if "still" in chart), None)
    if first_still is None:
        return []  # nothing to fall back on: the link keeps redirecting to the folder on GitHub
    return [
        Slide(chart["name"], chart.get("still", first_still), chart.get("video"), borrowed="still" not in chart)
        for chart in charts.values()
        if "still" in chart or "video" in chart
    ]


def collect_receipts(root: Path = REPO_ROOT) -> list[Receipt]:
    """Every receipt with rendered visuals, newest as_of first. Aliases never get pages or slides of their own."""
    receipts = []
    for spec in sorted((root / "receipts").glob("*/receipt.yaml")):
        folder = spec.parent
        check_slug(folder.name, folder)
        cfg = yaml.safe_load(spec.read_text()) or {}
        slides = _slides(folder, cfg.get("visuals") or [])
        if slides:
            receipts.append(Receipt(folder.name, _title(folder), date.fromisoformat(str(cfg["as_of"])), slides))
    return sorted(receipts, key=lambda receipt: (-receipt.as_of.toordinal(), receipt.slug))


def _attr(text: object) -> str:
    """Escape for markup built here: `_template` passes `raw` fields through as-is."""
    return html.escape(str(text), quote=True)


def _media_urls(slug: str, files: dict[str, Path]) -> dict[str, str]:
    return {shape: _attr(f"/media/{slug}/{path.name}") for shape, path in files.items()}


def _slide_markup(receipt: Receipt, slide: Slide, label: str, meta: str, attrs: str = "") -> str:
    """A snap slide: the still (shaped by orientation) with the video reel.js plays over it; `meta` is markup."""
    still, video = _media_urls(receipt.slug, slide.still), ""
    if slide.video:
        src = _media_urls(receipt.slug, slide.video)
        video = (
            f'<video muted loop playsinline preload="none" aria-hidden="true" tabindex="-1"'
            f' data-portrait="{src["portrait"]}" data-landscape="{src["landscape"]}"></video>'
        )
    borrowed = ' data-still="borrowed"' if slide.borrowed else ""
    return (
        f'<section class="slide"{attrs}{borrowed} aria-label="{_attr(label)}"><div class="media">'
        f'<picture><source media="(orientation: portrait)" srcset="{still["portrait"]}">'
        f'<img src="{still["landscape"]}" alt="{_attr(receipt.title)}" loading="lazy" decoding="async"></picture>'
        f'{video}</div><div class="meta">{meta}</div></section>'
    )


def _reel_markup(receipts: list[Receipt]) -> str:
    """Root page: a slide for each of the newest REEL_SIZE receipts, a text list of the rest, the player."""
    if not receipts:
        return ""
    host = brand()["short_link_host"]
    slides = []
    for i, receipt in enumerate(receipts[:REEL_SIZE]):
        slug = _attr(receipt.slug)
        meta = (
            f"<span>#{len(receipts) - i:03d} · As of {receipt.as_of.isoformat()}</span>"
            f'<span class="dots" aria-hidden="true"></span><a href="/{slug}/">{_attr(host)}/{slug} →</a>'
        )
        attrs = ' id="receipts"' if i == 0 else ""
        slides.append(_slide_markup(receipt, receipt.hero, receipt.title, meta, attrs))
    older = ""
    if len(receipts) > REEL_SIZE:
        rows = "".join(
            f'<li><a href="/{_attr(r.slug)}/">{_attr(r.slug)}</a><span class="dots" aria-hidden="true"></span>'
            f"<span>{_attr(r.title)}</span></li>"
            for r in receipts[REEL_SIZE:]
        )
        older = f'<section class="older"><p class="label">Older receipts</p><ul>{rows}</ul></section>'
    return "\n".join(slides) + older + '\n<script src="/assets/reel.js" defer></script>'


def _receipt_slides(receipt: Receipt) -> str:
    """A receipt page: every chart, one slide each, in receipt.yaml order."""
    n = len(receipt.slides)
    return "\n".join(
        _slide_markup(
            receipt,
            slide,
            f"{receipt.title}, chart {i} of {n}",
            (f"<span>{i} / {n}</span>" if n > 1 else "") + '<span class="dots" aria-hidden="true"></span>',
        )
        for i, slide in enumerate(receipt.slides, 1)
    )


def _copy_media(out: Path, receipts: list[Receipt]) -> None:
    """The files the slides use, under /media/<slug>/ (a reserved slug)."""
    for receipt in receipts:
        dest = out / "media" / receipt.slug
        dest.mkdir(parents=True, exist_ok=True)
        for slide in receipt.slides:
            for path in {*slide.still.values(), *(slide.video or {}).values()}:
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


def _github_icon() -> str:
    return (TEMPLATES / "github.svg").read_text(encoding="utf-8").strip()


def _page_fields() -> dict[str, str]:
    """Values every page template uses besides the brand colours."""
    b = brand()
    return {
        "description": " ".join(b["description"].split()),
        "site_url": b["site_url"].rstrip("/"),
        "repo_url": b["repo_url"],
        "repo_label": _bare(b["repo_url"]).removeprefix("github.com/"),
        "author_url": b["author_url"],
        "author_label": _bare(b["author_url"]),
        **{f"font_{role}": FONT_FILES[role] for role in SPLASH_FONTS},
    }


def _splash_page(kicker: str, heading: str, lede: str, page_title: str, indexable: bool = True, reel: str = "") -> str:
    home = html.escape(brand()["site_url"].rstrip("/") + "/", quote=True)
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
            "scroll_hint": '<a class="hint reveal" href="#receipts">Latest receipts</a>' if reel else "",
            "github_icon": _github_icon(),
        },
        kicker=kicker,
        heading=heading,
        lede=lede,
        page_title=page_title,
        **_page_fields(),
    )


def _receipt_page(receipt: Receipt) -> str:
    """cacheregister.dev/<topic>: the receipt's charts in a snap scroll, with its folder on GitHub one click away."""
    b = brand()
    site, card = b["site_url"].rstrip("/"), receipt.card
    card_target = TARGETS[card.name.split(".")[-2]]  # <visual>.<target>.<ext>
    as_of = receipt.as_of.isoformat()
    return _template(
        "receipt.html",
        raw={"slides": _receipt_slides(receipt), "github_icon": _github_icon()},
        page_title=f"{receipt.title} · {b['name']}",
        page_description=f"{receipt.title}: a {b['name']} receipt, data as of {as_of}. {b['tagline']}.",
        title=receipt.title,
        as_of=as_of,
        canonical=f"{site}/{receipt.slug}/",
        card_url=f"{site}/media/{receipt.slug}/{card.name}",
        card_width=str(card_target.width),
        card_height=str(card_target.height),
        source_url=f"{b['repo_url'].rstrip('/')}/tree/main/receipts/{receipt.slug}",
        **_page_fields(),
    )


def _write_assets(out: Path) -> None:
    """Favicon, Open Graph card and the self-hosted fonts, under /assets (a reserved slug)."""
    import vl_convert as vlc

    assets = out / "assets"
    (assets / "fonts").mkdir(parents=True)
    for role in SPLASH_FONTS:
        shutil.copyfile(font_path(role), assets / "fonts" / FONT_FILES[role])
    for name in ("site.css", "reel.js"):
        shutil.copyfile(SITE_STATIC / name, assets / name)
    favicon = _template("favicon.svg")
    (assets / "favicon.svg").write_text(favicon, encoding="utf-8")
    register_fonts()
    (assets / "apple-touch-icon.png").write_bytes(vlc.svg_to_png(favicon, scale=180 / 64))
    card = _template("og-card.svg", name_upper=brand()["name"].upper(), host_upper=brand()["short_link_host"].upper())
    (assets / "og.png").write_bytes(vlc.svg_to_png(card, scale=1))


def _crawler_files(out: Path, receipts: list[Receipt]) -> None:
    """Open to every crawler, search and AI alike; the sitemap lists the real pages: the root and each receipt's."""
    site = html.escape(brand()["site_url"].rstrip("/"))
    urls = [f"{site}/", *(f"{site}/{html.escape(r.slug)}/" for r in receipts)]
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site}/sitemap.xml\n")
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{url}</loc></url>\n" for url in urls)
        + "</urlset>\n"
    )


def build_site(out: Path, root: Path = REPO_ROOT) -> list[Link]:
    b = brand()
    repo = b["repo_url"].rstrip("/")
    links = collect_links(root)
    receipts = collect_receipts(root)
    pages = {f"receipts/{receipt.slug}": receipt for receipt in receipts}
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    host = b["short_link_host"]
    (out / "index.html").write_text(
        _splash_page(
            kicker=host, heading=b["name"], lede=f"{b['tagline']}.", page_title=b["name"], reel=_reel_markup(receipts)
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
    _copy_media(out, receipts)
    _crawler_files(out, receipts)
    site = b["site_url"].rstrip("/")
    for link in links:
        page = out / link.slug / "index.html"
        page.parent.mkdir(parents=True)
        receipt = pages.get(link.analysis)
        if receipt is None:  # an exploration's reserved link, or a receipt with nothing rendered yet
            page.write_text(_redirect_page(f"{repo}/tree/main/{link.analysis}", link.title))
        elif link.slug == receipt.slug:
            page.write_text(_receipt_page(receipt), encoding="utf-8")
        else:  # an alias: on to the receipt's page
            page.write_text(_redirect_page(f"{site}/{receipt.slug}/", link.title))
    return links

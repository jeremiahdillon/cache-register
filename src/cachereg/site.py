"""`cachereg site`: the static short-link site published to GitHub Pages (cacheregister.dev).

Only receipts get short links: the folder name *is* the link, so `receipts/<topic>/` is
`cacheregister.dev/<topic>`, which redirects to that folder on GitHub. Explorations never get one.
Retired or renamed links live on in config/link-aliases.yaml so URLs on posted images never break.
The root is a splash page (assets/templates/site.html, also the 404) open to search and AI crawlers.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from string import Template

import yaml

from cachereg.core.paths import REPO_ROOT
from cachereg.viz.brand import FONT_FILES, brand, color, font_path, register_fonts

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG = 32
RESERVED = {"index", "404", "assets", "about", "api", "static"}
TEMPLATES = REPO_ROOT / "assets" / "templates"
SPLASH_FONTS = ("display", "body", "mono")  # the faces site.html declares
# Splash intro timing (ms): cursor alone, then one keystroke per letter (a fixed, slightly uneven
# rhythm so it reads as typed), a pause, then the rest of the page fades in.
TYPE_START = 1100
KEYSTROKES = (95, 70, 110, 80, 125, 75, 90, 105)
WORD_GAP = 180
REVEAL_PAUSE = 650


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
    """Every receipt (folder name = link) plus aliases, validated: well-formed and pointing at real receipts."""
    links: dict[str, Link] = {}
    for spec in sorted((root / "receipts").glob("*/receipt.yaml")):
        folder = spec.parent
        _check_slug(folder.name, folder)
        rel = folder.relative_to(root).as_posix()
        links[folder.name] = Link(folder.name, rel, _title(folder))
    aliases_file = root / "config" / "link-aliases.yaml"
    aliases = (yaml.safe_load(aliases_file.read_text()) or {}).get("aliases") or {} if aliases_file.is_file() else {}
    for slug, target in aliases.items():
        _check_slug(slug, aliases_file)
        if slug in links:
            raise ValueError(f"alias {slug!r} collides with a live link")
        if target not in links:
            raise ValueError(f"alias {slug!r} points at unknown link {target!r}")
        links[slug] = Link(slug, links[target].analysis, links[target].title)
    return sorted(links.values(), key=lambda link: link.slug)


def _check_slug(slug: str, where: Path) -> None:
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


def _splash_page(kicker: str, heading: str, lede: str, page_title: str, indexable: bool = True) -> str:
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
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    host = b["short_link_host"]
    (out / "index.html").write_text(
        _splash_page(kicker=host, heading=b["name"], lede=f"{b['tagline']}.", page_title=b["name"]),
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
    _crawler_files(out)
    for link in links:
        page = out / link.slug / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(_redirect_page(f"{repo}/tree/main/{link.analysis}", link.title))
    return links

"""`cachereg site`: the static short-link site published to GitHub Pages (cacheregister.dev).

Only receipts get short links: the folder name *is* the link, so `receipts/<topic>/` is
`cacheregister.dev/<topic>`, which redirects to that folder on GitHub. Explorations never get one.
Retired or renamed links live on in config/link-aliases.yaml so URLs on posted images never break.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

from cachereg.core.paths import REPO_ROOT
from cachereg.viz.brand import brand, color

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_SLUG = 32
RESERVED = {"index", "404", "assets", "about", "api", "static"}


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


def build_site(out: Path, root: Path = REPO_ROOT) -> list[Link]:
    repo = brand()["repo_url"].rstrip("/")
    links = collect_links(root)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "index.html").write_text(_redirect_page(repo, brand()["name"]))
    (out / "404.html").write_text(_redirect_page(repo, "Not found"))
    for link in links:
        page = out / link.slug / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(_redirect_page(f"{repo}/tree/main/{link.analysis}", link.title))
    return links

from __future__ import annotations

from pathlib import Path

import pytest

from cachereg.site import build_site, collect_links, short_url


def make_receipt(root: Path, topic: str) -> None:
    d = root / "receipts" / topic
    d.mkdir(parents=True)
    (d / "receipt.yaml").write_text(f"title: Title of {topic}\n")


def make_exploration(root: Path, folder: str) -> None:
    d = root / "explore" / folder
    d.mkdir(parents=True)
    (d / "explore.yaml").write_text("title: scratch\n")


def test_repo_links_come_from_receipts():
    links = {link.slug: link for link in collect_links()}  # the real repo
    assert links["openrouter-wallet-share"].analysis == "receipts/openrouter-wallet-share"
    assert not any(link.analysis.startswith("explore/") for link in links.values())


def test_explorations_never_get_links(tmp_path):
    make_exploration(tmp_path, "2026-01-01-some-idea")
    make_receipt(tmp_path, "a-topic")
    assert [link.slug for link in collect_links(tmp_path)] == ["a-topic"]


@pytest.mark.parametrize("bad", ["Has-Caps", "under_score", "trailing-", "a" * 40, "index"])
def test_malformed_receipt_folder_rejected(tmp_path, bad):
    make_receipt(tmp_path, bad)
    with pytest.raises(ValueError, match="bad link"):
        collect_links(tmp_path)


def test_alias_keeps_old_link_alive(tmp_path):
    make_receipt(tmp_path, "new-name")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "link-aliases.yaml").write_text("aliases:\n  old-name: new-name\n")
    out = tmp_path / "_site"
    links = build_site(out, tmp_path)
    assert {link.slug for link in links} == {"new-name", "old-name"}
    page = (out / "old-name" / "index.html").read_text()
    assert "/tree/main/receipts/new-name" in page and "Title of new-name" in page
    assert (out / "index.html").exists() and (out / "404.html").exists()


def test_alias_to_unknown_receipt_rejected(tmp_path):
    make_receipt(tmp_path, "real")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "link-aliases.yaml").write_text("aliases:\n  old: missing\n")
    with pytest.raises(ValueError, match="unknown link"):
        collect_links(tmp_path)


def test_short_url_is_short():
    assert short_url("openrouter-wallet-share") == "cacheregister.dev/openrouter-wallet-share"


def test_splash_and_404_read_brand_and_keep_redirects(tmp_path):
    from cachereg.site import TEMPLATES
    from cachereg.viz.brand import brand

    b = brand()
    make_receipt(tmp_path, "a-topic")
    out = tmp_path / "_site"
    build_site(out, tmp_path)

    index = (out / "index.html").read_text(encoding="utf-8")
    assert f"<h1>{b['name']}<" in index and f"{b['tagline']}." in index
    assert f'href="{b["repo_url"]}"' in index and b["colors"]["canvas"] in index and b["colors"]["signal"] in index
    for tag in ('name="description"', 'property="og:title"', 'property="og:image"', 'rel="icon"'):
        assert tag in index
    assert f"{b['site_url']}/assets/og.png" in index and "noindex" not in index
    assert f'rel="canonical" href="{b["site_url"]}/"' in index and "Content-Security-Policy" in index
    assert "$" not in index  # every template placeholder filled

    not_found = (out / "404.html").read_text(encoding="utf-8")
    assert 'content="noindex"' in not_found and f'href="{b["repo_url"]}"' in not_found
    assert 'rel="canonical"' not in not_found
    assert 'http-equiv="refresh"' not in index + not_found  # splash pages no longer redirect

    for asset in ("favicon.svg", "apple-touch-icon.png", "og.png"):
        assert (out / "assets" / asset).stat().st_size > 0
    assert (out / "assets" / "og.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    for font in index.split("url(/assets/fonts/")[1:]:
        assert (out / "assets" / "fonts" / font.split(")")[0]).is_file()

    # Crawlable by everyone, search and AI bots alike.
    robots = (out / "robots.txt").read_text()
    assert "User-agent: *\nAllow: /" in robots and "Disallow" not in robots
    assert f"Sitemap: {b['site_url']}/sitemap.xml" in robots
    assert f"<loc>{b['site_url']}/</loc>" in (out / "sitemap.xml").read_text()

    # Short links still redirect to their receipt folder.
    page = (out / "a-topic" / "index.html").read_text()
    assert 'http-equiv="refresh"' in page and "/tree/main/receipts/a-topic" in page

    # Brand values live in brand.yaml, not the templates.
    for name in ("site.html", "og-card.svg", "favicon.svg"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert not any(hex_ in text for hex_ in b["colors"].values() if isinstance(hex_, str))
        assert b["name"] not in text

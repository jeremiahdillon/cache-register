from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cachereg.site import REEL_SIZE, build_site, collect_links, collect_reel, short_url

FULL = {"chart": ["x_png", "linkedin_png"], "chart-motion": ["x_video", "linkedin_video"]}
EXT = {"png": "png", "video": "mp4"}


def make_receipt(root: Path, topic: str, as_of: str | None = None, visuals: dict | None = None, title: str = ""):
    """A receipt folder; `visuals` maps visual name → targets, each written as a placeholder output file."""
    d = root / "receipts" / topic
    d.mkdir(parents=True)
    lines = [f"title: {json.dumps(title or f'Title of {topic}')}"]
    if as_of:
        lines.append(f"as_of: {as_of}")
    if visuals:
        lines.append("visuals:")
        (d / "output").mkdir()
        for name, targets in visuals.items():
            lines.append(f"  - {{name: {name}, chart: c, targets: [{', '.join(targets)}]}}")
            for target in targets:
                (d / "output" / f"{name}.{target}.{EXT[target.split('_')[-1]]}").write_bytes(b"synthetic")
    (d / "receipt.yaml").write_text("\n".join(lines) + "\n")


def make_exploration(root: Path, folder: str, link: str | None = None) -> None:
    d = root / "explore" / folder
    d.mkdir(parents=True)
    (d / "explore.yaml").write_text("title: scratch\n" + (f"link: {link}\n" if link else ""))


def test_repo_links_come_from_receipts_and_reserving_explorations():
    links = {link.slug: link for link in collect_links()}  # the real repo
    assert links["openrouter-wallet-share"].analysis == "receipts/openrouter-wallet-share"
    explored = {link.slug for link in links.values() if link.analysis.startswith("explore/")}
    assert explored <= {"source-matters"}  # only explorations that reserve a link


def test_explorations_without_a_reserved_link_get_none(tmp_path):
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
    from cachereg.site import REVEAL_PAUSE, TEMPLATES
    from cachereg.viz.brand import brand

    b = brand()
    make_receipt(tmp_path, "a-topic")
    out = tmp_path / "_site"
    build_site(out, tmp_path)

    index = (out / "index.html").read_text(encoding="utf-8")
    assert f'<h1 aria-label="{b["name"]}">' in index and f"{b['tagline']}." in index
    typed = re.findall(r'<span class="k" style="--t:(\d+)ms">([^<])</span>', index)
    assert "".join(ch for _, ch in typed) == b["name"]  # the title types in, letter by letter
    times = [int(t) for t, _ in typed]
    assert times == sorted(times) and f"reveal .8s ease-out {times[-1] + REVEAL_PAUSE}ms" in index
    # Letters must hide *until* --t and then fall back to their own style. A fill mode would hold the
    # end keyframe, and Chrome finishes a 1 ms step animation at progress 0.9999… (stays hidden).
    letter_rule = re.search(r"h1 \.k\{animation:([^}]*)\}", index).group(1)
    assert "var(--t)" in letter_rule and not re.search(r"\b(both|forwards)\b", letter_rule)
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


def test_exploration_reserves_a_link_until_promoted(tmp_path):
    make_exploration(tmp_path, "2026-01-01-idea", link="an-idea")
    out = tmp_path / "_site"
    links = {link.slug: link for link in build_site(out, tmp_path)}
    assert links["an-idea"].analysis == "explore/2026-01-01-idea"
    assert "/tree/main/explore/2026-01-01-idea" in (out / "an-idea" / "index.html").read_text()
    receipt = tmp_path / "receipts" / "an-idea"
    receipt.mkdir(parents=True)
    (receipt / "receipt.yaml").write_text("title: Promoted\npromoted_from: explore/2026-01-01-idea\n")
    assert {link.slug: link for link in collect_links(tmp_path)}["an-idea"].analysis == "receipts/an-idea"


def test_reserved_link_clashes_are_rejected(tmp_path):
    make_receipt(tmp_path, "taken")
    make_exploration(tmp_path, "2026-01-01-a", link="taken")
    with pytest.raises(ValueError, match="already a receipt"):
        collect_links(tmp_path)
    other = tmp_path / "other"
    make_exploration(other, "2026-01-01-a", link="same")
    make_exploration(other, "2026-01-02-b", link="same")
    with pytest.raises(ValueError, match="reserved by both"):
        collect_links(other)
    bad = tmp_path / "bad"
    make_exploration(bad, "2026-01-01-a", link="Not_A_Slug")
    with pytest.raises(ValueError, match="bad link"):
        collect_links(bad)


def test_reel_newest_first_with_both_shapes(tmp_path):
    make_receipt(tmp_path, "older", "2026-01-01", FULL)
    make_receipt(tmp_path, "newer", "2026-02-01", FULL)
    make_receipt(tmp_path, "also-newer", "2026-02-01", FULL)
    reel = collect_reel(tmp_path)
    assert [item.slug for item in reel] == ["also-newer", "newer", "older"]  # as_of desc, then slug
    item = reel[0]
    assert {p.name for p in item.still.values()} == {"chart.x_png.png", "chart.linkedin_png.png"}
    assert item.video["portrait"].name == "chart-motion.linkedin_video.mp4"
    assert item.video["landscape"].name == "chart-motion.x_video.mp4"


def test_reel_shape_fallback_and_stills_only(tmp_path):
    make_receipt(tmp_path, "landscape-only", "2026-01-02", {"chart": ["x_png"], "motion": ["x_video"]})
    make_receipt(tmp_path, "stills-only", "2026-01-01", {"chart": ["x_png", "linkedin_png"]})
    make_receipt(tmp_path, "no-outputs", "2026-01-03")
    reel = {item.slug: item for item in collect_reel(tmp_path)}
    assert set(reel) == {"landscape-only", "stills-only"}  # nothing rendered → no slide
    fallback = reel["landscape-only"]
    assert set(fallback.still) == set(fallback.video) == {"portrait", "landscape"}
    assert fallback.still["portrait"] == fallback.still["landscape"]
    assert reel["stills-only"].video is None


def test_reel_on_index_only_with_media_for_slides(tmp_path):
    for i in range(REEL_SIZE + 2):
        make_receipt(tmp_path, f"topic-{i}", f"2026-01-{i + 1:02d}", FULL)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "link-aliases.yaml").write_text("aliases:\n  old-name: topic-0\n")
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    index = (out / "index.html").read_text(encoding="utf-8")

    slides = re.findall(r'<section class="slide" aria-label="([^"]+)"', index)
    assert slides == [f"Title of topic-{i}" for i in range(REEL_SIZE + 1, 1, -1)]  # aliases never get slides
    older = re.search(r'<section class="older">(.*?)</section>', index).group(1)
    assert re.findall(r'<a href="/([^"]+)">', older) == ["topic-1", "topic-0"]
    assert '<script src="/assets/reel.js" defer></script>' in index and (out / "assets" / "reel.js").is_file()
    assert 'data-portrait="/media/topic-7/chart-motion.linkedin_video.mp4"' in index
    assert "#008 · As of 2026-01-08" in index and "cacheregister.dev/topic-7 →" in index
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', index).group(1)
    assert "media-src 'self'" in csp and "script-src 'self'" in csp and "unsafe-inline" not in csp.split("style-src")[0]

    copied = {p.parent.name for p in (out / "media").glob("*/*")}
    assert copied == {f"topic-{i}" for i in range(2, REEL_SIZE + 2)}  # text-list receipts get no media
    assert len(list((out / "media" / "topic-7").iterdir())) == 4

    not_found = (out / "404.html").read_text(encoding="utf-8")
    for markup in ('class="slide"', 'src="/assets/reel.js"', 'class="hint', 'body class="reel"'):
        assert markup not in not_found
    assert '<div class="tear"' in not_found  # the footer stays


def test_reel_without_older_receipts_has_no_list(tmp_path):
    make_receipt(tmp_path, "only", "2026-01-01", FULL)
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert index.count('class="slide"') == 1 and 'class="older"' not in index


def test_reel_escapes_titles(tmp_path):
    make_receipt(tmp_path, "tricky", "2026-01-01", FULL, title='A & B <i>"quoted"</i>')
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert 'aria-label="A &amp; B &lt;i&gt;&quot;quoted&quot;&lt;/i&gt;"' in index and "<i>" not in index


def test_media_is_a_reserved_slug(tmp_path):
    make_receipt(tmp_path, "media")
    with pytest.raises(ValueError, match="bad link"):
        collect_links(tmp_path)

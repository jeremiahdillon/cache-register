from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cachereg.site import build_site, collect_links, collect_receipts, short_url

VIDEOS, STILLS = ["x_video", "linkedin_video"], ["x_png", "linkedin_png"]
FULL = {"chart": STILLS, "chart-motion": VIDEOS}
MIXED = {"push": VIDEOS, "stack": STILLS, "lines": STILLS, "lines-motion": VIDEOS}  # one video-only chart
EXT = {"png": "png", "video": "mp4"}


def make_receipt(
    root: Path,
    topic: str,
    as_of: str | None = None,
    visuals: dict | None = None,
    title: str = "",
    blurb: str = "",
    texts: dict | None = None,
):
    """A receipt folder; `visuals` maps visual name → targets, each written as a placeholder output file;
    `texts` is the manifest's visual → title/subtitle/source, as `cachereg render` writes it."""
    d = root / "receipts" / topic
    d.mkdir(parents=True)
    lines = [f"title: {json.dumps(title or f'Title of {topic}')}"]
    if as_of:
        lines.append(f"as_of: {as_of}")
    if blurb:
        lines.append(f"blurb: {json.dumps(blurb)}")
    if visuals:
        lines.append("visuals:")
        (d / "output").mkdir()
        for name, targets in visuals.items():
            chart = name.removesuffix("-motion")  # the repo's convention: x and x-motion are one chart
            lines.append(f"  - {{name: {name}, chart: {chart}, targets: [{', '.join(targets)}]}}")
            for target in targets:
                (d / "output" / f"{name}.{target}.{EXT[target.split('_')[-1]]}").write_bytes(b"synthetic")
    if texts is not None:
        (d / "output" / "manifest.json").write_text(json.dumps({"visuals": texts}))
    (d / "receipt.yaml").write_text("\n".join(lines) + "\n")


def make_exploration(root: Path, folder: str, link: str | None = None) -> None:
    d = root / "explore" / folder
    d.mkdir(parents=True)
    (d / "explore.yaml").write_text("title: scratch\n" + (f"link: {link}\n" if link else ""))


def test_repo_links_come_from_receipts_and_reserving_explorations():
    links = {link.slug: link for link in collect_links()}  # the real repo
    assert links["openrouter-wallet-share"].analysis == "receipts/openrouter-wallet-share"
    explored = {link.slug for link in links.values() if link.analysis.startswith("explore/")}
    assert explored <= {"source-matters", "coreweave-credit", "deepseek-vs-us"}  # only explorations that reserve a link


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
    from cachereg.site import REVEAL_PAUSE, SITE_STATIC, TEMPLATES
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

    # Brand values live in brand.yaml, not the templates or the shared stylesheet.
    assert (out / "assets" / "site.css").is_file() and 'href="/assets/site.css"' in index
    for path in [TEMPLATES / n for n in ("site.html", "og-card.svg", "favicon.svg")] + [SITE_STATIC / "site.css"]:
        text = path.read_text(encoding="utf-8")
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


def test_receipts_newest_first_still_and_video_of_a_chart_share_a_slide(tmp_path):
    make_receipt(tmp_path, "older", "2026-01-01", FULL)
    make_receipt(tmp_path, "newer", "2026-02-01", FULL)
    make_receipt(tmp_path, "also-newer", "2026-02-01", FULL)
    receipts = collect_receipts(tmp_path)
    assert [r.slug for r in receipts] == ["also-newer", "newer", "older"]  # as_of desc, then slug
    [slide] = receipts[0].slides
    assert {p.name for p in slide.still.values()} == {"chart.x_png.png", "chart.linkedin_png.png"}
    assert slide.video["portrait"].name == "chart-motion.linkedin_video.mp4"
    assert slide.video["landscape"].name == "chart-motion.x_video.mp4"
    assert not slide.borrowed and receipts[0].hero is slide


def test_slides_follow_yaml_order_and_video_only_charts_borrow_a_still(tmp_path):
    make_receipt(tmp_path, "mixed", "2026-01-01", MIXED)
    [receipt] = collect_receipts(tmp_path)
    assert [slide.name for slide in receipt.slides] == ["push", "stack", "lines"]
    push, stack, lines = receipt.slides
    assert push.borrowed and push.still == stack.still and push.video  # video-only: the first still as fallback
    assert not stack.borrowed and stack.video is None
    assert not lines.borrowed and lines.video["landscape"].name == "lines-motion.x_video.mp4"
    assert receipt.hero is push and receipt.card.name == "stack.x_png.png"


def test_shape_fallback_stills_only_and_nothing_rendered(tmp_path):
    make_receipt(tmp_path, "landscape-only", "2026-01-02", {"chart": ["x_png"], "chart-motion": ["x_video"]})
    make_receipt(tmp_path, "stills-only", "2026-01-01", {"chart": ["x_png", "linkedin_png"]})
    make_receipt(tmp_path, "videos-only", "2026-01-04", {"push": ["x_video", "linkedin_video"]})
    make_receipt(tmp_path, "no-outputs", "2026-01-03")
    receipts = {r.slug: r for r in collect_receipts(tmp_path)}
    assert set(receipts) == {"landscape-only", "stills-only"}  # no still to fall back on → no page, no slide
    [fallback] = receipts["landscape-only"].slides
    assert set(fallback.still) == set(fallback.video) == {"portrait", "landscape"}
    assert fallback.still["portrait"] == fallback.still["landscape"]
    assert receipts["stills-only"].slides[0].video is None


def test_reel_on_index_only_with_media_for_every_receipt(tmp_path, monkeypatch):
    size = 3  # a small cap, so the receipts beyond it go to the older list
    monkeypatch.setattr("cachereg.site.REEL_SIZE", size)
    newest = f"topic-{size + 1}"
    for i in range(size + 2):
        make_receipt(tmp_path, f"topic-{i}", f"2026-01-{i + 1:02d}", FULL)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "link-aliases.yaml").write_text("aliases:\n  old-name: topic-0\n")
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    index = (out / "index.html").read_text(encoding="utf-8")

    slides = re.findall(r'<section class="slide" id="[^"]+" aria-label="([^"]+)"', index)
    assert slides == [f"Title of topic-{i}" for i in range(size + 1, 1, -1)]  # aliases never get slides
    # each slide's "More" leads to the next screen: the next slide, then the older list
    ids = re.findall(r'<section class="slide" id="([^"]+)"', index)
    mores = re.findall(r'<a class="more" href="#([^"]+)">More</a>', index)
    assert ids[0] == "receipts" and len(set(ids)) == size and mores == [*ids[1:], "older"]
    older = re.search(r'<section class="older" id="older">(.*?)</section>', index).group(1)
    assert re.findall(r'<a href="/([^"]+)/">', older) == ["topic-1", "topic-0"]
    assert '<script src="/assets/reel.js" defer></script>' in index and (out / "assets" / "reel.js").is_file()
    assert f'data-portrait="/media/{newest}/chart-motion.linkedin_video.mp4?v=' in index
    assert f"#{size + 2:03d} · As of 2026-01-{size + 2:02d}" in index
    assert f'<a href="/{newest}/">cacheregister.dev/{newest} →</a>' in index
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', index).group(1)
    assert "media-src 'self'" in csp and "script-src 'self'" in csp and "unsafe-inline" not in csp.split("style-src")[0]

    copied = {p.parent.name for p in (out / "media").glob("*/*")}
    assert copied == {f"topic-{i}" for i in range(size + 2)}  # every receipt has a page that needs its media
    assert len(list((out / "media" / newest).iterdir())) == 4

    not_found = (out / "404.html").read_text(encoding="utf-8")
    for markup in ('class="slide"', 'src="/assets/reel.js"', 'class="hint', 'body class="reel"'):
        assert markup not in not_found
    assert '<div class="tear"' in not_found  # the footer stays

    # The scroll hint links to the first slide; the repo is the last call to action, after the reel.
    assert '<a class="hint reveal" href="#receipts">' in index
    assert index.count('id="receipts"') == 1
    assert f'<section class="slide" id="receipts" aria-label="Title of {newest}"' in index
    main = index.split("<main>")[1].split("</main>")[0]
    assert 'class="cta' not in main
    assert index.index('class="older"') < index.index('class="cta') < index.index("<footer")


def test_short_links_lead_to_receipt_pages(tmp_path):
    from cachereg.viz.brand import brand

    b = brand()
    site, repo = b["site_url"].rstrip("/"), b["repo_url"].rstrip("/")
    make_receipt(tmp_path, "mixed", "2026-01-01", MIXED)
    make_receipt(tmp_path, "unrendered", "2026-01-02")
    make_exploration(tmp_path, "2026-01-03-idea", link="an-idea")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "link-aliases.yaml").write_text("aliases:\n  old-mixed: mixed\n")
    out = tmp_path / "_site"
    build_site(out, tmp_path)

    page = (out / "mixed" / "index.html").read_text(encoding="utf-8")
    assert "$" not in page and 'http-equiv="refresh"' not in page
    labels = re.findall(r'<section class="slide" id="chart-\d"( data-still="borrowed")? aria-label="([^"]+)"', page)
    assert labels == [
        (' data-still="borrowed"', "Title of mixed, chart 1 of 3"),
        ("", "Title of mixed, chart 2 of 3"),
        ("", "Title of mixed, chart 3 of 3"),
    ]
    assert re.findall(r'<a class="more" href="#([^"]+)">More</a>', page) == ["chart-2", "chart-3", "end"]
    assert page.count('id="end"') == 1
    source = f"{repo}/tree/main/receipts/mixed"
    assert page.count(f'href="{source}"') == 2  # the bar and the closing screen
    assert "Source on GitHub" in page and '<a class="back" href="/">' in page
    assert f'<link rel="canonical" href="{site}/mixed/">' in page
    assert f'property="og:image" content="{site}/media/mixed/stack.x_png.png?v=' in page  # first chart with a still
    assert 'og:image:width" content="1600"' in page and 'og:image:height" content="900"' in page
    assert '<script src="/assets/reel.js" defer></script>' in page and 'href="/assets/site.css"' in page
    csp = re.search(r'Content-Security-Policy" content="([^"]+)"', page).group(1)
    assert "media-src 'self'" in csp and "script-src 'self'" in csp
    assert {p.name for p in (out / "media" / "mixed").iterdir()} == {
        f"{v}.{t}.{'mp4' if 'video' in t else 'png'}" for v, ts in MIXED.items() for t in ts
    }

    alias = (out / "old-mixed" / "index.html").read_text()  # an alias goes on to the receipt's page
    assert f"url={site}/mixed/" in alias
    for slug, folder in (("unrendered", "receipts/unrendered"), ("an-idea", "explore/2026-01-03-idea")):
        redirect = (out / slug / "index.html").read_text()  # nothing to show yet: the folder on GitHub
        assert 'http-equiv="refresh"' in redirect and f"/tree/main/{folder}" in redirect

    sitemap = (out / "sitemap.xml").read_text()
    assert f"<loc>{site}/</loc><lastmod>2026-01-01</lastmod>" in sitemap
    assert f"<loc>{site}/mixed/</loc><lastmod>2026-01-01</lastmod>" in sitemap
    assert "unrendered" not in sitemap and "old-mixed" not in sitemap and "an-idea" not in sitemap


def test_reel_gives_every_receipt_a_slide_under_the_default_cap(tmp_path):
    for i in range(8):
        make_receipt(tmp_path, f"topic-{i}", f"2026-01-{i + 1:02d}", FULL)
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    index = (out / "index.html").read_text(encoding="utf-8")
    slides = re.findall(r'<section class="slide" id="[^"]+" aria-label="([^"]+)"', index)
    assert slides == [f"Title of topic-{i}" for i in range(7, -1, -1)]  # newest first, none left over
    mores = re.findall(r'<a class="more" href="#([^"]+)">More</a>', index)
    assert mores[-1] == "end" and 'class="older"' not in index


def test_reel_without_older_receipts_has_no_list(tmp_path):
    make_receipt(tmp_path, "only", "2026-01-01", FULL)
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert index.count('class="slide"') == 1 and 'class="older"' not in index
    assert '<a class="more" href="#end">More</a>' in index and index.count('id="end"') == 1


def test_share_card_size_is_the_still_s_own(tmp_path):
    from PIL import Image

    make_receipt(tmp_path, "moving", "2026-01-01", {"push": [*STILLS, *VIDEOS]})
    still = tmp_path / "receipts" / "moving" / "output" / "push.x_png.png"
    Image.new("RGB", (1920, 1080)).save(still)  # a still that is its video's final frame
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    page = (out / "moving" / "index.html").read_text(encoding="utf-8")
    assert 'og:image:width" content="1920"' in page and 'og:image:height" content="1080"' in page


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


def test_rerender_reaches_the_root_reel_and_the_receipt_page(tmp_path):
    make_receipt(tmp_path, "topic", "2026-01-01", FULL)
    out = tmp_path / "_site"

    def urls():
        build_site(out, tmp_path)
        pages = [(out / "index.html").read_text(encoding="utf-8"), (out / "topic" / "index.html").read_text()]
        return [set(re.findall(r"/media/topic/chart\.x_png\.png\?v=([0-9a-f]{12})", page)) for page in pages]

    before = urls()
    assert all(len(found) == 1 for found in before)
    (tmp_path / "receipts" / "topic" / "output" / "chart.x_png.png").write_bytes(b"re-rendered")  # cachereg render
    after = urls()
    assert all(len(found) == 1 for found in after) and before[0] != after[0] and after[0] == after[1]
    assert (out / "media" / "topic" / "chart.x_png.png").read_bytes() == b"re-rendered"


def test_receipt_page_text_comes_from_the_charts_and_the_blurb(tmp_path):
    texts = {
        "chart": {"title": "Share rose & held", "subtitle": "Weekly share of tokens", "source": "OpenRouter; LiteLLM"},
        "other": {"title": "Second claim.", "subtitle": "", "source": "LiteLLM; Epoch AI"},
    }
    visuals = {"chart": STILLS, "other": STILLS}
    make_receipt(tmp_path, "worded", "2026-01-01", visuals, blurb="What the chart measures.", texts=texts)
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    page = (out / "worded" / "index.html").read_text(encoding="utf-8")
    assert "$" not in page
    described = "Share rose &amp; held. Weekly share of tokens"  # the first chart's headline and subtitle
    assert f'<meta name="description" content="{described}">' in page
    assert f'property="og:description" content="{described}"' in page
    assert f'alt="{described}"' in page and 'alt="Second claim."' in page
    about = re.search(r'<div class="about">(.*?)</div>', page).group(1)
    assert about.startswith("<h1>Title of worded</h1>")
    assert '<p class="blurb">What the chart measures.</p>' in about
    assert re.findall(r"<h2>([^<]+)</h2>", about) == ["Share rose &amp; held", "Second claim."]  # as drawn
    assert '<p class="credits">Source: OpenRouter; LiteLLM; Epoch AI</p>' in about  # each credit once
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page).group(1))
    assert ld["@type"] == "Article" and ld["headline"] == "Title of worded" and ld["dateModified"] == "2026-01-01"
    assert ld["description"] == "Share rose & held. Weekly share of tokens"


def test_receipt_page_without_manifest_texts_or_blurb_falls_back(tmp_path):
    make_receipt(tmp_path, "plain", "2026-01-01", FULL, title="</script><b>T</b>")
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    page = (out / "plain" / "index.html").read_text(encoding="utf-8")
    assert 'alt="&lt;/script&gt;&lt;b&gt;T&lt;/b&gt;"' in page and 'class="blurb"' not in page
    assert 'class="charts"' not in page and 'class="credits"' not in page
    assert "a Cache Register receipt, data as of 2026-01-01" in page  # the generic description
    ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1)
    assert "</script>" not in ld and json.loads(ld)["headline"] == "</script><b>T</b>"


def test_charts_sharing_a_headline_list_it_once(tmp_path):
    same = {"title": "One finding", "subtitle": "Weekly share", "source": "OpenRouter"}
    texts = {
        "bars": same,
        "lines": same,
        "tokens": {**same, "subtitle": "Weekly tokens"},
        "other": {**same, "title": "Another finding"},  # the same subtitle under a second headline
        "bare": {"title": "Headline only", "subtitle": "", "source": "OpenRouter"},
        "untitled": {"title": "", "subtitle": "Subtitle only", "source": "OpenRouter"},
    }
    make_receipt(tmp_path, "twice", "2026-01-01", {name: STILLS for name in texts}, texts=texts)
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    page = (out / "twice" / "index.html").read_text(encoding="utf-8")
    charts = re.search(r'<ul class="charts">(.*?)</ul>', page).group(1)
    assert charts == (
        "<li><h2>One finding</h2><p>Weekly share</p><p>Weekly tokens</p></li>"
        "<li><h2>Another finding</h2><p>Weekly share</p></li>"
        "<li><h2>Headline only</h2></li>"
        "<li><p>Subtitle only</p></li>"
    )
    assert 'alt="Subtitle only"' in page  # the alt and the closing block show the same words


def test_without_chart_texts_the_blurb_is_the_description(tmp_path):
    make_receipt(tmp_path, "blurbed", "2026-01-01", FULL, blurb="What the chart  measures.")
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    page = (out / "blurbed" / "index.html").read_text(encoding="utf-8")
    assert '<meta name="description" content="What the chart measures.">' in page  # whitespace collapsed
    assert 'property="og:description" content="What the chart measures."' in page
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page).group(1))
    assert ld["description"] == "What the chart measures."


@pytest.mark.parametrize(
    ("manifest", "blurb", "error"),
    [
        ("{not json", "", "not a render manifest"),
        ("[1, 2]", "", "not a render manifest"),
        ('{"visuals": [{"title": "x"}]}', "", "must map each visual"),
        ('{"visuals": {"chart": "x"}}', "", "must map each visual"),
        ('{"visuals": {"chart": {"title": 5}}}', "", "must map each visual"),
        (None, "[a, b]", "blurb must be a line of text"),
    ],
)
def test_malformed_manifest_or_blurb_stops_the_build(tmp_path, manifest, blurb, error):
    make_receipt(tmp_path, "broken", "2026-01-01", FULL)
    folder = tmp_path / "receipts" / "broken"
    if manifest is not None:
        (folder / "output" / "manifest.json").write_text(manifest)
    if blurb:
        (folder / "receipt.yaml").write_text((folder / "receipt.yaml").read_text() + f"blurb: {blurb}\n")
    with pytest.raises(ValueError, match=error):
        build_site(tmp_path / "_site", tmp_path)

from __future__ import annotations

from pathlib import Path

import pytest

from cachereg.site import build_site, collect_links, short_url


def make_analysis(root: Path, folder: str, link: str | None) -> None:
    d = root / "analyses" / "explore" / folder
    d.mkdir(parents=True)
    (d / "story.yaml").write_text(f"link: {link}\n" if link else "targets: []\n")
    (d / "README.md").write_text(f"# Title of {folder}\n")


def test_repo_links_are_valid_and_unique():
    links = collect_links()  # the real repo
    assert "openrouter-wallet-share" in {link.slug for link in links}


def test_duplicate_link_rejected(tmp_path):
    make_analysis(tmp_path, "2026-01-01-a", "same-name")
    make_analysis(tmp_path, "2026-01-02-b", "same-name")
    with pytest.raises(ValueError, match="used by both"):
        collect_links(tmp_path)


@pytest.mark.parametrize("bad", ["Has-Caps", "under_score", "trailing-", "a" * 40, "index"])
def test_malformed_link_rejected(tmp_path, bad):
    make_analysis(tmp_path, "2026-01-01-a", bad)
    with pytest.raises(ValueError, match="bad link"):
        collect_links(tmp_path)


def test_alias_keeps_old_link_alive(tmp_path):
    make_analysis(tmp_path, "2026-01-01-a", "new-name")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "link-aliases.yaml").write_text("aliases:\n  old-name: new-name\n")
    out = tmp_path / "_site"
    links = build_site(out, tmp_path)
    assert {link.slug for link in links} == {"new-name", "old-name"}
    page = (out / "old-name" / "index.html").read_text()
    assert "/tree/main/analyses/explore/2026-01-01-a" in page
    assert (out / "index.html").exists() and (out / "404.html").exists()


def test_short_url_is_short():
    assert short_url("openrouter-wallet-share") == "cacheregister.dev/openrouter-wallet-share"

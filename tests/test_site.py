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

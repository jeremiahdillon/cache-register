from __future__ import annotations

import pytest

from cachereg import indexnow
from cachereg.site import build_site
from cachereg.viz.brand import brand

SITE = brand()["site_url"].rstrip("/")


def make_receipt(root, topic: str, as_of: str) -> None:
    """A receipt with one rendered still (placeholder bytes), enough for a page of its own."""
    d = root / "receipts" / topic
    (d / "output").mkdir(parents=True)
    (d / "receipt.yaml").write_text(
        f"title: Title of {topic}\nas_of: {as_of}\nvisuals:\n  - {{name: chart, chart: chart, targets: [x_png]}}\n"
    )
    (d / "output" / "chart.x_png.png").write_bytes(b"synthetic")


def built(tmp_path):
    make_receipt(tmp_path, "one", "2026-01-01")
    make_receipt(tmp_path, "two", "2026-01-02")
    out = tmp_path / "_site"
    build_site(out, tmp_path)
    return out


def test_site_serves_its_key(tmp_path):
    out = built(tmp_path)
    key = indexnow.key()
    assert key and indexnow.KEY_RE.match(key)
    assert (out / f"{key}.txt").read_text(encoding="utf-8") == key


def test_pages_come_from_the_sitemap(tmp_path):
    out = built(tmp_path)
    assert indexnow.pages(out) == {
        f"{SITE}/": out / "index.html",
        f"{SITE}/two/": out / "two" / "index.html",
        f"{SITE}/one/": out / "one" / "index.html",
    }


def test_only_changed_or_new_pages_are_listed(tmp_path):
    out = built(tmp_path)
    live = {url: path.read_bytes() for url, path in indexnow.pages(out).items()}
    assert indexnow.changed(out, live.get) == []
    live[f"{SITE}/one/"] = b"the old page"
    del live[f"{SITE}/two/"]  # not live yet: a new page
    assert indexnow.changed(out, live.get) == [f"{SITE}/two/", f"{SITE}/one/"]


def test_submission_names_the_host_key_and_its_location():
    sent = []
    status, meaning = indexnow.submit([f"{SITE}/one/"], send=lambda body: sent.append(body) or 202)
    key = indexnow.key()
    assert (status, meaning) == (202, "received; key validation pending")
    assert sent == [
        {
            "host": SITE.removeprefix("https://"),
            "key": key,
            "keyLocation": f"{SITE}/{key}.txt",
            "urlList": [f"{SITE}/one/"],
        }
    ]


@pytest.mark.parametrize(("status", "meaning"), [(403, "key not valid"), (429, "too many"), (500, "unexpected")])
def test_a_rejected_submission_raises_with_its_meaning(status, meaning):
    with pytest.raises(RuntimeError, match=f"IndexNow {status}: {meaning}"):
        indexnow.submit([f"{SITE}/"], send=lambda body: status)


def test_bad_or_missing_key(tmp_path):
    config = tmp_path / "indexnow.yaml"
    assert indexnow.key(config) is None  # no config: the site does not use IndexNow
    config.write_text("key: bad key!\n")
    with pytest.raises(ValueError, match="indexnow.yaml key"):
        indexnow.key(config)


def test_cli_lists_then_submits(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from cachereg.cli import app

    out = built(tmp_path)
    monkeypatch.setattr(indexnow, "live", lambda url: None)  # nothing live yet: every page is new
    urls = tmp_path / "urls.txt"
    result = CliRunner().invoke(app, ["indexnow-changed", "--site", str(out), "--out", str(urls)])
    assert result.exit_code == 0 and "3 page(s) to submit" in result.output
    sent = []
    monkeypatch.setattr(indexnow, "post", lambda body: sent.append(body["urlList"]) or 200)
    result = CliRunner().invoke(app, ["indexnow-submit", str(urls)])
    assert result.exit_code == 0 and "IndexNow 200" in result.output
    assert sent == [[f"{SITE}/", f"{SITE}/two/", f"{SITE}/one/"]]
    urls.write_text("")
    result = CliRunner().invoke(app, ["indexnow-submit", str(urls)])
    assert result.exit_code == 0 and "nothing submitted" in result.output

"""IndexNow: tell participating search engines (Bing, Yandex, Seznam, Naver, Yep and others; one submission is
shared with all of them) which cacheregister.dev pages changed in a deploy. Google does not take part.

The key in config/indexnow.yaml is public by design: `cachereg site` serves it at /<key>.txt, where the engines check
that the submitter controls the host. The Pages workflow runs `changed` before deploying (the new build
against the live pages) and `submit` after, so only pages whose HTML changed are sent; a re-render changes a
page's media URLs, so it counts. Never run locally: both steps use the network.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

import yaml

from cachereg.core.paths import REPO_ROOT
from cachereg.viz.brand import brand

CONFIG = REPO_ROOT / "config" / "indexnow.yaml"  # not brand.yaml, which is a render input
ENDPOINT = "https://api.indexnow.org/indexnow"
KEY_RE = re.compile(r"^[A-Za-z0-9-]{8,128}$")  # the protocol's key rules
TIMEOUT = 20
USER_AGENT = "cachereg-indexnow (+https://cacheregister.dev)"
STATUS = {  # the protocol's responses
    200: "accepted",
    202: "received; key validation pending",
    400: "bad request (invalid format)",
    403: "key not valid (key file missing or wrong)",
    422: "URLs do not belong to the host, or the key does not match the schema",
    429: "too many requests (submitted too often)",
}

Fetch = Callable[[str], bytes | None]  # URL → body, or None if the page is not live


def key(config: Path | None = None) -> str | None:
    """The IndexNow key, validated; None when the site does not use IndexNow (no config file)."""
    config = config or CONFIG
    if not config.is_file():
        return None
    value = str((yaml.safe_load(config.read_text()) or {}).get("key") or "")
    if not KEY_RE.match(value):
        raise ValueError(f"{config.name} key: 8–128 letters, digits or dashes")
    return value


def pages(site_dir: Path) -> dict[str, Path]:
    """The built site's real pages, from its sitemap: URL → the HTML file that serves it."""
    site = brand()["site_url"].rstrip("/")
    urls = re.findall(r"<loc>([^<]+)</loc>", (site_dir / "sitemap.xml").read_text(encoding="utf-8"))
    out = {}
    for url in urls:
        rel = url.removeprefix(site).strip("/")
        if url == rel:
            raise ValueError(f"sitemap URL {url!r} is not on {site}")
        out[url] = site_dir / rel / "index.html" if rel else site_dir / "index.html"
    return out


def live(url: str) -> bytes | None:
    """The page as served now; None if it is not there (a new page)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 (our own https site)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def changed(site_dir: Path, fetch: Fetch | None = None) -> list[str]:
    """The URLs whose built HTML differs from what is live (new pages included), in sitemap order."""
    fetch = fetch or live
    return [url for url, path in pages(site_dir).items() if fetch(url) != path.read_bytes()]


def payload(urls: list[str]) -> dict:
    site, k = brand()["site_url"].rstrip("/"), key()
    if k is None:
        raise ValueError(f"no IndexNow key ({CONFIG.name})")
    host = re.sub(r"^https?://", "", site)
    return {"host": host, "key": k, "keyLocation": f"{site}/{k}.txt", "urlList": urls}


def post(body: dict) -> int:
    """POST the submission; returns the HTTP status (errors included)."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(  # noqa: S310 (fixed https endpoint)
        ENDPOINT, data=data, headers={"Content-Type": "application/json; charset=utf-8", "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


def submit(urls: list[str], send: Callable[[dict], int] | None = None) -> tuple[int, str]:
    """Submit `urls` (at most 10,000, the protocol's limit); returns (status, meaning). Raises on a failure."""
    if len(urls) > 10_000:
        raise ValueError("IndexNow takes at most 10,000 URLs per submission")
    status = (send or post)(payload(urls))
    meaning = STATUS.get(status, "unexpected response")
    if status not in (200, 202):
        raise RuntimeError(f"IndexNow {status}: {meaning}")
    return status, meaning

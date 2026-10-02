"""Minimal HTTP client: retries with backoff on 429/5xx, and secrets redacted from every error."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from cachereg import __version__
from cachereg.core.settings import redact

USER_AGENT = f"cache-register/{__version__} (+https://cacheregister.dev)"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    def __init__(self, status: int | None, message: str):
        super().__init__(redact(message))
        self.status = status


@dataclass(frozen=True)
class Response:
    url: str  # without query-string secrets; safe to log
    status: int
    body: bytes

    def json(self):
        return json.loads(self.body)


def get(
    url: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    *,
    retries: int = 4,
    timeout: float = 60.0,
    backoff: float = 2.0,
) -> Response:
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", **(headers or {})}
    delay = backoff
    for attempt in range(retries + 1):
        req = urllib.request.Request(full, headers=req_headers)  # noqa: S310 (https URLs from adapters)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
                return Response(url=full, status=r.status, body=r.read())
        except urllib.error.HTTPError as e:
            body = e.read()[:500].decode("utf-8", errors="replace")
            if e.code in RETRY_STATUSES and attempt < retries:
                retry_after = e.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else delay)
                delay *= 2
                continue
            raise HttpError(e.code, f"HTTP {e.code} for {full}: {body}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise HttpError(None, f"request failed for {full}: {e}") from None
    raise AssertionError("unreachable")

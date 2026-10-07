"""Shared helpers for the OpenRouter datasets sources (`openrouter_apps`, `openrouter_session_cost`).

Not a source itself (no registry entry). Both endpoints take any OpenRouter key, allow 30 requests
a minute per key and 500 a day per account (shared with `openrouter_rankings`), and answer
`{"data": [...], "meta": {"version": "v1", "as_of": ...}}`. `meta.as_of` is when the response was
generated, not a data revision.
"""

from __future__ import annotations

import time

from cachereg.core import http
from cachereg.core.settings import get_secret

BASE = "https://openrouter.ai/api/v1/datasets/"
PAUSE = 2.1  # seconds between requests: stays under 30/min per key (tests set 0)


class Client:
    """Spaced, authenticated GETs that return (response, body) after checking the envelope."""

    def __init__(self) -> None:
        self.headers = {"Authorization": f"Bearer {get_secret('OPENROUTER_API_KEY')}"}
        self._last: float | None = None

    def get(self, endpoint: str, params: dict[str, str]) -> tuple[http.Response, dict]:
        if self._last is not None:
            wait = PAUSE - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
        try:
            resp = http.get(BASE + endpoint, params, self.headers)
        finally:
            self._last = time.monotonic()
        body = resp.json()
        meta = body.get("meta") if isinstance(body, dict) else None
        if not isinstance(meta, dict) or not isinstance(body.get("data"), list):
            raise ValueError(f"{endpoint}: unexpected response shape for {params}")
        if meta.get("version") != "v1":
            raise ValueError(f"{endpoint}: dataset version {meta.get('version')!r}, expected 'v1'")
        return resp, body

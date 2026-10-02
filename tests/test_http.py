from __future__ import annotations

import io

from cachereg.core import http


class _Resp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_recorded_url_redacts_secret_query_params(monkeypatch):
    secret = "dummy" + "-key-" + "123456"
    monkeypatch.setenv("HF_TOKEN", secret)
    monkeypatch.setattr(http.urllib.request, "urlopen", lambda req, timeout: _Resp(b"{}"))
    r = http.get("https://example.test/api", {"token": secret})
    assert secret not in r.url and "[REDACTED:HF_TOKEN]" in r.url

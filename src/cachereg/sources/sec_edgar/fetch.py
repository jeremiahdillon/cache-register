"""Fetch XBRL company facts for every company in tickers.yaml (one request each, kept as served).

SEC fair access: a declared User-Agent with a contact address (`SEC_EDGAR_USER_AGENT`, never
stored) and at most 10 requests per second.
"""

from __future__ import annotations

import gzip
import json
import time
from datetime import UTC, date, datetime, timedelta

from cachereg.core import http
from cachereg.core.settings import get_secret
from cachereg.core.store import RawFetch
from cachereg.sources.sec_edgar.companies import cik10, load_companies

SOURCE = "sec_edgar"
ADAPTER_VERSION = "1"
URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
PAUSE = 0.15  # seconds between requests (fair access: ≤ 10 per second)


def file_name(cik: str, body: bytes) -> str:
    return f"companyfacts_CIK{cik}.json" + (".gz" if body[:2] == b"\x1f\x8b" else "")


def decode(body: bytes) -> dict:
    data = json.loads(gzip.decompress(body) if body[:2] == b"\x1f\x8b" else body)
    if not isinstance(data, dict) or not isinstance(data.get("facts"), dict):
        raise ValueError("company facts: not a JSON object with 'facts'")
    return data


def iter_facts(data: dict):
    """(taxonomy, tag, unit, fact) for every fact in a companyfacts document.

    A part of the document that is not the expected shape (a concept, unit list or fact that is not
    an object or list) is yielded with ``fact=None``, so stage counts it as rejected instead of failing.
    """
    for taxonomy, tags in data["facts"].items():
        if not isinstance(tags, dict):
            yield taxonomy, None, None, None
            continue
        for tag, concept in tags.items():
            units = concept.get("units") if isinstance(concept, dict) else None
            if not isinstance(units, dict):
                yield taxonomy, tag, None, None
                continue
            for unit, facts in units.items():
                if not isinstance(facts, list):
                    yield taxonomy, tag, unit, None
                    continue
                for fact in facts:
                    yield taxonomy, tag, unit, fact if isinstance(fact, dict) else None


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    """`full` is unused: every response is the company's complete fact history."""
    today = today or datetime.now(UTC).date()
    agent = get_secret("SEC_EDGAR_USER_AGENT")
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    newest, oldest = None, None  # (filed, accn)
    for i, company in enumerate(load_companies()):
        if i:
            time.sleep(PAUSE)
        resp = http.get(URL.format(cik=company.cik), headers={"User-Agent": agent, "Accept-Encoding": "gzip"})
        data = decode(resp.body)  # validate before storing
        if cik10(data.get("cik", "")) != company.cik:
            raise ValueError(f"{company.ticker}: response is for CIK {data.get('cik')!r}, not {company.cik}")
        for _, _, _, f in iter_facts(data):
            if f is None:
                continue
            key = (str(f.get("filed") or ""), str(f.get("accn") or ""))
            if key[0]:
                newest = max(newest or key, key)
                oldest = min(oldest or key, key)
        raw.add(file_name(company.cik, resp.body), resp.body, resp.url, resp.status)
    end = (today - timedelta(days=1)).isoformat()  # facts filed later today may still arrive
    raw.vintage = {
        "kind": "edgar_filed",
        "value": newest[1] if newest else None,
        "date": newest[0] if newest else None,
        "window": [oldest[0] if oldest else end, end],
    }
    return raw

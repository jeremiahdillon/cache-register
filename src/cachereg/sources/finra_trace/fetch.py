"""Fetch FINRA TRACE end-of-day prices and yields for a fixed list of corporate bonds (CUSIPs).

The data service behind finra.org/finra-data/fixed-income (the bond pages' "Price and Yield" chart):
undocumented but public, no key. A GET to any public endpoint sets an XSRF-TOKEN cookie; data requests
are POSTs that echo it in `X-XSRF-TOKEN`. The shared HTTP client is GET-only, so this adapter makes its
own requests. One request per CUSIP for the whole window; bodies are stored as served and never
committed (FINRA's terms; SOURCE.md).
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime

from cachereg.core.store import RawFetch
from cachereg.sources.finra_trace.bonds import BONDS

SOURCE = "finra_trace"
ADAPTER_VERSION = "1"
BASE = "https://services-dynarep.ddwa.finra.org/public/reporting/v2"
COOKIE_URL = f"{BASE}/group/Firm/name/ActiveIndividual/dynamiclookup/examCode"
DATA_URL = f"{BASE}/data/group/FixedIncomeMarket/name/EndOfDayPriceYield"
FLOOR = date(2025, 1, 1)
FIELDS = ["cusip", "issueSymbolIdentifier", "tradeDate", "lastSalePrice", "lastSaleYield"]
HEADERS = {"User-Agent": "Mozilla/5.0", "Origin": "https://www.finra.org", "Referer": "https://www.finra.org/"}


def _open(opener, req, retries: int = 3):
    for attempt in range(retries + 1):
        try:
            with opener.open(req, timeout=60) as r:  # noqa: S310 (fixed https URLs)
                return r.status, r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            code = getattr(e, "code", None)
            if attempt == retries or (code is not None and code not in (429, 500, 502, 503, 504)):
                raise RuntimeError(f"finra: request to {req.full_url} failed: {e}") from None
            time.sleep(2 * 2**attempt)
    raise AssertionError("unreachable")


def _session():
    """An opener holding FINRA's session cookies, and the XSRF token data requests must echo."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    _open(opener, urllib.request.Request(COOKIE_URL, headers=HEADERS))  # noqa: S310 (fixed https URL)
    token = next((c.value for c in jar if c.name == "XSRF-TOKEN"), None)
    if not token:
        raise RuntimeError("finra: no XSRF-TOKEN cookie; the service has changed")
    return opener, token


def body_for(cusip: str, start: date, end: date) -> dict:
    return {
        "fields": FIELDS,
        "orFilters": [{"compareFilters": [{"fieldName": "cusip", "fieldValue": cusip, "compareType": "EQUAL"}]}],
        "dateRangeFilters": [
            {"startDate": f"{start} 00:00:00.000", "endDate": f"{end} 23:59:59.000", "fieldName": "tradeDate"}
        ],
        "sortFields": ["tradeDate"],
        "offset": 0,
        "limit": 5000,
    }


def records(body) -> list[dict]:
    """The rows inside a FINRA response (`returnBody.data` is a JSON string)."""
    if not isinstance(body, dict) or body.get("status") != "success":
        raise ValueError(f"finra: request failed: {str(body)[:200]}")
    rows = json.loads(body["returnBody"].get("data") or "[]")
    if not isinstance(rows, list):
        raise ValueError("finra: data is not a list")
    return rows


def check(rows: list[dict], cusip: str) -> None:
    if not rows:
        raise ValueError(f"finra {cusip}: no end-of-day rows")
    if len(rows) >= 5000:
        raise ValueError(f"finra {cusip}: hit the 5000-row page limit; paginate")
    wrong = {r.get("cusip") for r in rows} - {cusip}
    if wrong:
        raise ValueError(f"finra {cusip}: answered for {sorted(map(str, wrong))}")


def fetch(full: bool = False, today: date | None = None) -> RawFetch:
    end = today or datetime.now(UTC).date()
    opener, token = _session()
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    for cusip in BONDS:
        req = urllib.request.Request(  # noqa: S310 (fixed https URL)
            DATA_URL,
            data=json.dumps(body_for(cusip, FLOOR, end)).encode(),
            headers=HEADERS | {"Content-Type": "application/json", "Accept": "application/json", "X-XSRF-TOKEN": token},
        )
        status, payload = _open(opener, req)
        check(records(json.loads(payload)), cusip)
        raw.add(f"eod_{cusip}.json", payload, f"{DATA_URL}#cusip={cusip}", status)
    digest = hashlib.sha256(b"".join(raw.files[n] for n in sorted(raw.files)))
    raw.vintage = {"kind": "content", "value": digest.hexdigest(), "window": [FLOOR.isoformat(), end.isoformat()]}
    return raw

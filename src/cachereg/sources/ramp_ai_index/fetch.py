"""Import one Ramp AI Index view, pasted from the page's "Get the data" button (a manual source).

`cachereg fetch ramp_ai_index --from-clipboard --cut <cut>` (or `--from-file PATH`). The input is
validated in full before anything is written, then stored byte for byte as one raw file. There is no
HTTP request: the manifest records the view's page URL, `via` and the cut.
"""

from __future__ import annotations

import hashlib

from cachereg.core.manual import ManualInput
from cachereg.core.store import RawFetch, list_fetches
from cachereg.sources.ramp_ai_index import cuts

SOURCE = "ramp_ai_index"
ADAPTER_VERSION = "1"


def manual_help() -> str:
    """The cuts, in the order of the monthly routine (printed by `fetch` when --cut is missing)."""
    return cuts.listing()


def latest_imports() -> dict[str, bytes]:
    """The latest stored bytes of every cut."""
    out = {}
    for f in list_fetches(SOURCE):  # oldest first, so later imports win
        cut = (f.manifest.get("vintage") or {}).get("cut")
        if cut in cuts.BY_ID:
            out[cut] = f.read(cuts.BY_ID[cut].file_name)
    return out


def fetch(full: bool = False, today=None, manual: ManualInput | None = None) -> RawFetch:
    """`full` and `today` are unused: every paste is the view's full history."""
    if manual is None:
        raise ValueError("ramp_ai_index is imported by hand: use --from-clipboard or --from-file with --cut")
    cut = cuts.get(manual.cut)
    cells = cuts.parse(manual.body, cut)
    for other, body in latest_imports().items():
        if other != cut.id and body == manual.body:
            raise ValueError(
                f"this is the same data as the latest {other} import: the clipboard did not change "
                "(click 'Get the data' on the right view and try again)"
            )
    periods = [c.period for c in cells]
    raw = RawFetch(SOURCE, ADAPTER_VERSION)
    raw.add(cut.file_name, manual.body, cut.url, None)
    raw.requests[-1] |= {"via": manual.via, "cut": cut.id}
    raw.vintage = {
        "kind": "content",
        "value": hashlib.sha256(manual.body).hexdigest(),
        "cut": cut.id,
        "first_period": min(periods).isoformat(),
        "last_period": max(periods).isoformat(),
    }
    return raw

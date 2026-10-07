"""Which sources are due for a fetch (PLAN §4.5).

A source is due when its `cadence` (sources.yaml) has passed since its latest fetch in the raw
store, judged by the fetch folder's UTC date: `daily` once the date changes, `weekly` after 7
days, `monthly` after one calendar month (clamped to the month's last day). A source never
fetched is due. Failed fetches write nothing, so they are retried on the next run.
"""

from __future__ import annotations

import calendar
import plistlib
import sys
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

from cachereg.core.registry import CADENCES, Source
from cachereg.core.store import list_fetches


def add_months(day: date, months: int) -> date:
    y, m = divmod(day.month - 1 + months, 12)
    year, month = day.year + y, m + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def next_due(cadence: str, last: date) -> date:
    if cadence == "daily":
        return last + timedelta(days=1)
    if cadence == "weekly":
        return last + timedelta(days=7)
    if cadence == "monthly":
        return add_months(last, 1)
    raise ValueError(f"unknown cadence {cadence!r}; use one of {', '.join(CADENCES)}")


def last_fetch_date(source: str) -> date | None:
    fetches = list_fetches(source)
    return date.fromisoformat(fetches[-1].path.parent.name) if fetches else None  # raw/<source>/<YYYY-MM-DD>/


def due_date(src: Source) -> date | None:
    """The first day `src` is due, or None if it has never been fetched (due now)."""
    last = last_fetch_date(src.id)
    return next_due(src.cadence, last) if last else None


def render_plist(template: str, values: dict[str, str]) -> str:
    """Fill `@NAME@` placeholders with XML-escaped values; the result must parse as a plist."""
    for name, value in values.items():
        if f"@{name}@" not in template:
            raise ValueError(f"placeholder @{name}@ not in template")
        template = template.replace(f"@{name}@", escape(value))
    plistlib.loads(template.encode())  # raises on a malformed result
    return template


if __name__ == "__main__":  # make install-schedule: python -m cachereg.core.schedule TEMPLATE OUT NAME=VALUE…
    src, out, *pairs = sys.argv[1:]
    Path(out).write_text(render_plist(Path(src).read_text(), dict(p.split("=", 1) for p in pairs)))

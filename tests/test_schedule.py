"""`fetch --due` and the launchd template, on a synthetic raw store."""

from __future__ import annotations

import plistlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from cachereg import cli
from cachereg.core.paths import REPO_ROOT
from cachereg.core.registry import Source
from cachereg.core.schedule import add_months, due_date, next_due, render_plist
from cachereg.core.settings import MissingSecretError
from cachereg.core.store import RawFetch


def src(sid: str, cadence: str) -> Source:
    return Source(sid, "native", "none", "allowed", "allowed", "test", cadence, (), True)


def fetched(sid: str, at: datetime) -> None:
    r = RawFetch(sid, "1", fetched_at=at)
    r.add("x.json", b"{}", "https://example.test", 200)
    r.write()


def test_next_due_per_cadence():
    assert next_due("daily", date(2026, 3, 1)) == date(2026, 3, 2)
    assert next_due("weekly", date(2026, 3, 1)) == date(2026, 3, 8)
    assert next_due("monthly", date(2026, 3, 15)) == date(2026, 4, 15)
    with pytest.raises(ValueError, match="cadence"):
        next_due("hourly", date(2026, 3, 1))


def test_monthly_clamps_to_month_end():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert add_months(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)


def test_due_date_uses_latest_fetch_folder(data_env):
    s = src("weekly_src", "weekly")
    assert due_date(s) is None  # never fetched: due now
    fetched("weekly_src", datetime(2026, 3, 1, 23, 50, tzinfo=UTC))
    fetched("weekly_src", datetime(2026, 3, 4, 0, 10, tzinfo=UTC))
    fetched("weekly_src", datetime(2026, 2, 20, tzinfo=UTC))  # older fetch written later: ignored
    assert due_date(s) == date(2026, 3, 11)


TODAY = date(2026, 3, 10)  # the CLI's clock is pinned via cli._today, so no test depends on the time of day
NOON = datetime(2026, 3, 10, 12, tzinfo=UTC)


@pytest.fixture
def fake_sources(data_env, monkeypatch):
    """Sources with stub fetchers: `needs_key` raises MissingSecretError, `broken` raises RuntimeError,
    `bad_cadence` has a cadence the scheduler does not know; the rest write a raw fetch dated TODAY."""
    known = {
        "daily_today": src("daily_today", "daily"),
        "weekly_recent": src("weekly_recent", "weekly"),
        "weekly_stale": src("weekly_stale", "weekly"),
        "needs_key": src("needs_key", "daily"),
        "broken": src("broken", "daily"),
        "bad_cadence": src("bad_cadence", "hourly"),
    }
    fetched("daily_today", NOON)
    fetched("weekly_recent", NOON - timedelta(days=6))
    fetched("weekly_stale", NOON - timedelta(days=7))
    fetched("bad_cadence", NOON - timedelta(days=1))
    calls = []

    def module(self, name):
        def fetch(full=False):
            calls.append(self.id)
            if self.id == "needs_key":
                raise MissingSecretError("NEEDS_KEY is not set")
            if self.id == "broken":
                raise RuntimeError("upstream 500")
            r = RawFetch(self.id, "1", fetched_at=NOON + timedelta(seconds=len(calls)))
            r.add("x.json", b"{}", "https://example.test", 200)
            return r

        return SimpleNamespace(fetch=fetch)

    monkeypatch.setattr(cli, "load_sources", lambda: known)
    monkeypatch.setattr(cli, "_today", lambda: TODAY)
    monkeypatch.setattr(Source, "module", module)
    return calls


def run(*args):
    return CliRunner().invoke(cli.app, ["fetch", *args])


def test_fetch_due_fetches_only_due_sources_and_skips_missing_keys(fake_sources):
    r = run("--due", "daily_today", "weekly_recent", "weekly_stale", "needs_key")
    assert r.exit_code == 0, r.output  # a missing key is reported, not a failure, on scheduled runs
    assert fake_sources == ["weekly_stale", "needs_key"]  # weekly: due on day 7, not day 6
    assert "wait  daily_today" in r.output and "next due 2026-03-11" in r.output
    assert "wait  weekly_recent" in r.output and "next due 2026-03-11" in r.output
    assert "skip  needs_key" in r.output
    # weekly_stale was fetched today, so a second run waits for everything except the source without a key.
    fake_sources.clear()
    run("--due", "daily_today", "weekly_recent", "weekly_stale", "needs_key")
    assert fake_sources == ["needs_key"]


def test_fetch_due_still_fails_on_errors_other_than_a_missing_key(fake_sources):
    r = run("--due", "needs_key", "broken", "weekly_stale")
    assert r.exit_code == 1 and fake_sources == ["needs_key", "broken", "weekly_stale"]
    assert "FAIL  broken" in r.output and "skip  needs_key" in r.output


def test_fetch_due_reports_an_unknown_cadence_and_fetches_the_rest(fake_sources):
    r = run("--due", "bad_cadence", "weekly_stale")
    assert r.exit_code == 1 and fake_sources == ["weekly_stale"]
    assert "FAIL  bad_cadence" in r.output and "unknown cadence 'hourly'" in r.output


def test_fetch_due_respects_named_sources_and_plain_fetch_still_fails_on_missing_key(fake_sources):
    r = run("--due", "daily_today", "weekly_stale")
    assert r.exit_code == 0 and fake_sources == ["weekly_stale"]
    fake_sources.clear()
    r = run("needs_key")
    assert r.exit_code == 1 and fake_sources == ["needs_key"]


def test_launchd_template_renders_to_a_valid_plist_even_with_awkward_paths():
    template = (REPO_ROOT / "ops" / "launchd" / "cachereg.fetch.plist.template").read_text()
    repo = "/opt/R&D <x> | 'q'/cache-register"
    values = {
        "CACHEREG": f"{repo}/.venv/bin/cachereg",
        "REPO": repo,
        "LOG_DIR": "/opt/logs",
        "HOUR": "5",
        "MINUTE": "47",
    }
    out = render_plist(template, values)
    assert "@" not in out.split("-->", 1)[1]  # every placeholder filled
    plist = plistlib.loads(out.encode())
    assert plist["ProgramArguments"] == [f"{repo}/.venv/bin/cachereg", "fetch", "--due"]
    assert plist["WorkingDirectory"] == repo
    assert plist["StartCalendarInterval"] == {"Hour": 5, "Minute": 47}
    assert Path(plist["StandardOutPath"]).parent == Path("/opt/logs")
    with pytest.raises(ValueError, match="@NOPE@"):
        render_plist(template, {"NOPE": "x"})

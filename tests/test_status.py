"""`cachereg status` and the fetch-state record, on a synthetic raw store."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from cachereg import cli
from cachereg.core import fetch_state
from cachereg.core.registry import Source
from cachereg.core.settings import SECRETS, MissingSecretError
from tests.test_schedule import NOON, TODAY, fetched, src

SECRET = "dummy" + "-status-" + "123456"  # assembled so secret scanners do not flag the test itself


@pytest.fixture
def sources(data_env, monkeypatch):
    """`ok` fetches; `broken` fails with the secret in its message; `needs_key` has no key."""
    monkeypatch.setenv("OPENROUTER_API_KEY", SECRET)
    known = {
        "ok": src("ok", "daily"),
        "weekly_old": src("weekly_old", "weekly"),
        "broken": src("broken", "weekly"),
        "needs_key": src("needs_key", "monthly"),
        "off": Source("off", "native", "none", "allowed", "allowed", "test", "daily", (), False),
    }
    fetched("weekly_old", datetime(2026, 3, 1, 9, tzinfo=UTC))
    fetched("broken", datetime(2026, 3, 8, 9, tzinfo=UTC))
    fail = {"broken"}

    def module(self, name):
        def fetch(full=False):
            if self.id in fail:
                raise RuntimeError(f"401 for https://example.test/?key={SECRET}\nsecond line")
            if self.id == "needs_key":
                raise MissingSecretError("NEEDS_KEY is not set")
            from cachereg.core.store import RawFetch

            r = RawFetch(self.id, "1", fetched_at=NOON)
            r.add("x.json", b"{}", "https://example.test", 200)
            return r

        return SimpleNamespace(fetch=fetch)

    monkeypatch.setattr(cli, "load_sources", lambda: known)
    monkeypatch.setattr(cli, "_today", lambda: TODAY)
    monkeypatch.setattr(Source, "module", module)
    return fail


def invoke(*args):
    return CliRunner().invoke(cli.app, list(args))


def rows(output: str) -> dict[str, str]:
    return {line.split()[0]: line for line in output.splitlines() if line.strip()}


def test_fetch_records_outcomes_redacted_outside_the_raw_store(sources, data_env):
    r = invoke("fetch", "ok", "broken", "needs_key")
    assert r.exit_code == 1
    assert SECRET not in r.output and "[REDACTED:OPENROUTER_API_KEY]" in r.output
    f = fetch_state.state_file()
    assert f.parent.name == "state" and "raw" not in f.parts
    text = f.read_text()
    assert SECRET not in text
    state = json.loads(text)
    assert state["ok"]["last_error"] is None and state["ok"]["last_ok"]
    err = state["broken"]["last_error"]
    assert err["kind"] == "FAIL" and err["message"].startswith("RuntimeError: 401 for")
    assert "second line" not in err["message"] and "[REDACTED:OPENROUTER_API_KEY]" in err["message"]
    assert "last_ok" not in state["broken"]
    assert state["needs_key"]["last_error"]["kind"] == "skip"


def test_a_later_success_clears_the_error(sources):
    invoke("fetch", "broken")
    assert fetch_state.load()["broken"]["last_error"]
    sources.clear()
    assert invoke("fetch", "broken").exit_code == 0
    entry = fetch_state.load()["broken"]
    assert entry["last_error"] is None and entry["last_ok"] == entry["last_attempt"]


def test_status_shows_cadence_last_fetch_next_due_and_last_error(sources):
    invoke("fetch", "broken", "needs_key")
    r = invoke("status")
    assert r.exit_code == 0, r.output
    out = rows(r.output)
    assert out["ok"].split()[1:4] == ["daily", "never", "now"] and out["ok"].endswith("-")
    assert out["weekly_old"].split()[1:4] == ["weekly", "2026-03-01", "now"]  # due 03-08, overdue on 03-10
    b = out["broken"]
    assert b.split()[1:4] == ["weekly", "2026-03-08", "2026-03-15"]
    assert "FAIL: RuntimeError: 401" in b and SECRET not in r.output
    assert "skip: NEEDS_KEY is not set" in out["needs_key"]
    assert "off" not in out  # disabled sources are not listed
    assert "set      OPENROUTER_API_KEY" in r.output  # the secrets list is kept
    assert all(name in r.output for name in SECRETS)


def test_status_survives_an_unreadable_state_file(sources):
    f = fetch_state.state_file()
    f.parent.mkdir(parents=True)
    f.write_text("[1, 2")
    r = invoke("status")
    assert r.exit_code == 0 and "fetch state unreadable" in r.output
    assert invoke("fetch", "ok").exit_code == 0  # a fetch rewrites it
    assert fetch_state.load()["ok"]["last_error"] is None


def test_messages_are_one_short_line():
    assert fetch_state.clean("a\nb") == "a"
    assert len(fetch_state.clean("x" * 1000)) == fetch_state.MAX_MESSAGE
    assert fetch_state.clean("") == ""


def test_a_state_write_failure_never_fails_a_fetch_or_stops_the_run(sources, monkeypatch):
    def full_disk(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(fetch_state, "_save", full_disk)
    sources.clear()
    r = invoke("fetch", "ok", "broken", "needs_key")
    assert r.exit_code == 1, r.output  # from the missing key only (plain fetch), not from the state file
    assert "ok    ok" in r.output and "ok    broken" in r.output and "skip  needs_key" in r.output
    assert r.output.count("fetch state not saved (OSError)") == 3
    assert "FAIL" not in r.output


def test_status_reports_a_corrupt_raw_folder_and_keeps_going(sources, data_env):
    (data_env / "data" / "raw" / "ok" / "not-a-date" / "x").mkdir(parents=True)
    (data_env / "data" / "raw" / "ok" / "not-a-date" / "x" / "manifest.json").write_text('{"fetch_id": "z"}')
    r = invoke("status")
    assert r.exit_code == 0, r.output
    assert "raw store unreadable (ValueError)" in rows(r.output)["ok"]
    assert rows(r.output)["weekly_old"].split()[2] == "2026-03-01"
    bad = data_env / "data" / "raw" / "broken" / "2026-03-09" / "y"
    bad.mkdir(parents=True)
    (bad / "manifest.json").write_text("[1, 2]")  # valid JSON, not an object
    assert "raw store unreadable (TypeError)" in rows(invoke("status").output)["broken"]


def test_the_state_file_is_replaced_atomically_without_leftovers(data_env):
    for i in range(3):
        fetch_state.record("s", None if i % 2 else f"err {i}")
    assert [p.name for p in fetch_state.state_file().parent.iterdir()] == ["fetch.json"]

"""Manual sources (`input: manual`): the raw store, the registry and `cachereg fetch` with
--from-clipboard / --from-file, on stub sources (no clipboard, no network)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from cachereg import cli
from cachereg.core import manual
from cachereg.core.registry import Source, load_sources
from cachereg.core.store import RawFetch, list_fetches

TODAY = date(2026, 3, 10)
NOON = datetime(2026, 3, 10, 12, tzinfo=UTC)


def src(sid: str, cadence: str = "monthly", input: str = "api") -> Source:
    return Source(sid, "native", "revised", "unknown", "allowed", "test", cadence, (), True, input)


# --- store ------------------------------------------------------------------------------


def test_two_fetches_in_the_same_second_both_land_in_order(data_env):
    first, second = RawFetch("s", "1", fetched_at=NOON), RawFetch("s", "1", fetched_at=NOON)
    for r, body in ((first, b"a"), (second, b"b")):
        r.add("x.tsv", body, "https://example.test", None)
        r.write()
    stored = list_fetches("s")
    assert [f.read("x.tsv") for f in stored] == [b"a", b"b"]
    assert stored[1].fetched_at == NOON + timedelta(seconds=1)
    assert json.loads((stored[0].path / "manifest.json").read_text())["requests"][0]["status"] is None


# --- registry ---------------------------------------------------------------------------


def test_registry_input_defaults_to_api_and_rejects_unknown_values(tmp_path):
    entry = (
        "sources:\n  - {id: x, history: native, revisions: none, redistribution: allowed, derived_charts: allowed, "
        "attribution: t, cadence: daily, requires: []%s}\n"
    )
    f = tmp_path / "sources.yaml"
    f.write_text(entry % "")
    assert load_sources(f)["x"].input == "api"
    f.write_text(entry % ", input: manual")
    assert load_sources(f)["x"].input == "manual"
    f.write_text(entry % ", input: browser")
    with pytest.raises(ValueError, match="input must be one of api, manual"):
        load_sources(f)


# --- reading the input ------------------------------------------------------------------


def test_read_input_from_file_and_clipboard(tmp_path, monkeypatch):
    f = tmp_path / "paste.tsv"
    f.write_bytes(b"Date\tX\n2026-01-01\t1")
    got = manual.read_input(False, f, "c")
    assert (got.body, got.via, got.cut) == (b"Date\tX\n2026-01-01\t1", "file", "c")
    monkeypatch.setattr(manual, "read_clipboard", lambda: b"clip")
    assert manual.read_input(True, None, "c").via == "clipboard"


@pytest.mark.parametrize(
    ("clipboard", "content", "match"),
    [
        (True, b"x", "exactly one"),  # both
        (False, None, "exactly one"),  # neither
        (False, b"  \n", "empty"),
    ],
)
def test_read_input_refusals(tmp_path, clipboard, content, match):
    f = None
    if content is not None:
        f = tmp_path / "in.tsv"
        f.write_bytes(content)
    with pytest.raises(ValueError, match=match):
        manual.read_input(clipboard, f, None)


def test_read_input_refuses_oversized_input(tmp_path, monkeypatch):
    monkeypatch.setattr(manual, "MAX_BYTES", 3)
    f = tmp_path / "in.tsv"
    f.write_bytes(b"abcd")
    with pytest.raises(ValueError, match="larger than"):
        manual.read_input(False, f, None)


# --- the fetch command ------------------------------------------------------------------


@pytest.fixture
def sources(data_env, monkeypatch):
    """`api_src` has a stub fetch; `hand` is a manual source whose stub fetch stores the input."""
    known = {"api_src": src("api_src", "daily"), "hand": src("hand", "monthly", "manual")}
    calls = []

    def module(self, name):
        def fetch(full=False, manual=None):
            calls.append((self.id, manual))
            if manual is not None and manual.cut == "bad":
                raise ValueError("header does not match")
            r = RawFetch(self.id, "1", fetched_at=NOON + timedelta(seconds=len(calls)))
            r.add("x.tsv", manual.body if manual else b"{}", "https://example.test/page", None if manual else 200)
            if manual:
                r.requests[-1] |= {"via": manual.via, "cut": manual.cut}
            return r

        return SimpleNamespace(fetch=fetch, manual_help=lambda: "  cut-a  Menu : A")

    monkeypatch.setattr(cli, "load_sources", lambda: known)
    monkeypatch.setattr(cli, "_today", lambda: TODAY)
    monkeypatch.setattr(Source, "module", module)
    monkeypatch.setattr(manual, "read_clipboard", lambda: b"Date\tX\n2026-01-01\t1")
    return calls


def run(*args):
    return CliRunner().invoke(cli.app, ["fetch", *args])


def test_plain_fetch_lists_a_manual_source_and_never_fails_on_it(sources):
    r = run()
    assert r.exit_code == 0, r.output
    assert [c[0] for c in sources] == ["api_src"]
    assert "manual hand" in r.output and "due now" in r.output and "--from-clipboard" in r.output


def test_fetch_due_lists_a_due_manual_source_and_waits_for_one_that_is_not(sources):
    r = run("--due")
    assert r.exit_code == 0 and "manual hand" in r.output and [c[0] for c in sources] == ["api_src"]
    run("hand", "--from-clipboard", "--cut", "cut-a")  # imported today: next due in a month
    r = run("--due", "hand")
    assert r.exit_code == 0 and "wait  hand" in r.output and "next due 2026-04-10" in r.output


def test_manual_import_from_clipboard_writes_one_fetch(sources):
    r = run("hand", "--from-clipboard", "--cut", "cut-a")
    assert r.exit_code == 0, r.output
    assert "ok    hand" in r.output and "cut-a (clipboard)" in r.output
    (stored,) = list_fetches("hand")
    assert stored.read("x.tsv") == b"Date\tX\n2026-01-01\t1"
    assert stored.manifest["requests"][0] | {} == {
        "url": "https://example.test/page", "status": None, "file": "x.tsv", "via": "clipboard", "cut": "cut-a"
    }  # fmt: skip


def test_manual_import_from_file_keeps_the_path_out_of_the_manifest(sources, tmp_path):
    f = tmp_path / "secret-folder-name" / "paste.tsv"
    f.parent.mkdir()
    f.write_bytes(b"Date\tX\n2026-01-01\t2")
    r = run("hand", "--from-file", str(f), "--cut", "cut-a")
    assert r.exit_code == 0, r.output
    (stored,) = list_fetches("hand")
    text = (stored.path / "manifest.json").read_text()
    assert "secret-folder-name" not in text and str(tmp_path) not in text and '"via": "file"' in text


def test_missing_cut_lists_the_cuts_and_reads_nothing(sources):
    r = run("hand", "--from-clipboard")
    assert r.exit_code == 1 and "--cut is required" in r.output and "cut-a  Menu : A" in r.output
    assert sources == [] and list_fetches("hand") == []


def test_a_refused_manual_import_writes_nothing_and_exits_1(sources):
    r = run("hand", "--from-clipboard", "--cut", "bad")
    assert r.exit_code == 1 and "FAIL  hand" in r.output and "header does not match" in r.output
    assert list_fetches("hand") == []


@pytest.mark.parametrize(
    ("args", "match"),
    [
        (["hand", "api_src", "--from-clipboard", "--cut", "c"], "exactly one source"),
        (["--from-clipboard", "--cut", "c"], "exactly one source"),
        (["api_src", "--from-clipboard", "--cut", "c"], "not a manual source"),
        (["hand", "--due", "--from-clipboard", "--cut", "c"], "cannot be combined"),
        (["hand", "--full", "--from-clipboard", "--cut", "c"], "cannot be combined"),
        (["hand", "--cut", "c"], "needs --from-clipboard or --from-file"),
    ],
)
def test_manual_import_usage_errors(sources, args, match):
    r = run(*args)
    assert r.exit_code == 2 and match in r.output and sources == []

"""Guard rules. Offending strings are assembled at runtime so this file itself passes the guard."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("guard", ROOT / "scripts" / "guard.py")
guard = importlib.util.module_from_spec(spec)
sys.modules["guard"] = guard
spec.loader.exec_module(guard)

USERS = "/" + "Users" + "/"
FAKE_OR_KEY = "sk-or-" + "v1-" + "0123456789abcdef" * 4


def rules(path: str, text: str, extra: list[str] | None = None) -> set[str]:
    return {f.rule for f in guard.check_content(path, text.encode(), extra or [])}


@pytest.mark.parametrize(
    "path",
    [
        "data/raw/openrouter/x.json",
        "outputs/a/b.png",
        "x/warehouse.duckdb",
        "t.parquet",
        ".env",
        "a/.env.prod",
        ".envrc",
        ".direnv/x",
    ],
)
def test_blocked_paths(path):
    assert guard.check_path(path, 10)


@pytest.mark.parametrize("path", [".env.example", "config/curated/disclosures.csv", "src/cachereg/cli.py"])
def test_allowed_paths(path):
    assert not guard.check_path(path, 10)


def test_size_limit_outside_published():
    assert guard.check_path("docs/big.png", 2_000_000)
    assert not guard.check_path("analyses/series/x/published/2026-10-01/x.mp4", 2_000_000)


def test_home_paths():
    assert "home directory path" in rules("a.md", f"see {USERS}someone/Projects")
    assert "home directory path" in rules("a.md", "/" + "home/" + "someone/x")
    assert "home directory path" in rules("a.md", "c:" + "\\users\\" + "someone\\proj")  # any case
    assert not rules("a.md", f"e.g. {USERS}example/Projects or {USERS}you/x")
    assert not rules("a.md", "/home/runner/work is fine in CI docs")


def test_local_hostname_and_private_ip():
    assert "local hostname" in rules("a.md", "ssh " + "my-box" + ".local")
    assert "private IP address" in rules("a.md", "host " + "192.168" + ".1.20")
    assert not rules("a.md", "~/.local/share is a directory, 8.8.8.8 is public")


def test_secrets_detected_and_never_echoed(capsys):
    found = guard.check_content("cfg.py", f'OPENROUTER_API_KEY = "{FAKE_OR_KEY}"'.encode(), [])
    assert {"OpenRouter key", "hard-coded credential"} <= {f.rule for f in found}
    assert all(FAKE_OR_KEY not in str(f) for f in found)


def test_extra_patterns_are_case_insensitive_literals():
    assert "machine-specific pattern" in rules("a.md", "built on ACME-STUDIO", extra=["acme-studio"])


def test_allow_marker():
    assert not rules("a.md", f"example: {USERS}someone  <!-- guard: allow -->")


def test_binary_content_skipped():
    assert guard.check_content("x.png", b"\x89PNG\0\0" + FAKE_OR_KEY.encode(), []) == []


def test_staged_mode_blocks_commit(tmp_path):
    def run(*args):
        return subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)

    run("git", "init", "-q")
    (tmp_path / "notes.md").write_text(f"key {FAKE_OR_KEY}\n")
    run("git", "add", "notes.md")
    result = run("python3", str(ROOT / "scripts" / "guard.py"), "--staged")
    assert result.returncode == 1
    assert "OpenRouter key" in result.stderr
    assert FAKE_OR_KEY not in result.stderr + result.stdout


def test_history_mode_catches_leak_removed_later(tmp_path):
    def run(*args):
        return subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)

    run("git", "init", "-q")
    run("git", "config", "user.email", "t@example.com")
    run("git", "config", "user.name", "t")
    (tmp_path / "notes.md").write_text(f"key {FAKE_OR_KEY}\n")
    run("git", "add", "notes.md")
    run("git", "commit", "-qm", "leak", "--no-verify")
    (tmp_path / "notes.md").write_text("clean\n")
    run("git", "commit", "-qam", "remove", "--no-verify")
    script = str(ROOT / "scripts" / "guard.py")
    assert run("python3", script, "--tracked").returncode == 0
    for mode in (["--history"], ["--range", "HEAD~1..HEAD"]):
        result = run("python3", script, *mode)
        expected = 1 if mode == ["--history"] else 0
        assert result.returncode == expected, (mode, result.stderr)

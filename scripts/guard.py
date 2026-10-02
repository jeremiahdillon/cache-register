#!/usr/bin/env python3
"""Block secrets, licensed data and machine-specific details from entering git history.

Runs as the local pre-commit hook (``--staged``) and in CI (``--tracked`` and ``--range``).
CI is the enforcement of record; the local hook is a convenience that can be bypassed.

Findings report the file, line and rule name only — never the matched text — because CI
logs on a public repository are public.

Standard library only, compatible with Python 3.9+, so it runs before any environment exists.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MAX_BYTES = 1_000_000
PUBLISHED_RE = re.compile(r"^analyses/.+/published/")
ALLOW_MARKER = "guard: allow"
EXTRA_ENV = "CACHEREG_GUARD_EXTRA"
EXTRA_FILE = Path.home() / ".config" / "cachereg" / "guard-extra.txt"

BLOCKED_PATHS = [
    ("data directory", re.compile(r"^data/")),
    ("outputs directory", re.compile(r"^outputs/")),
    ("warehouse/data file", re.compile(r"\.(parquet|duckdb|duckdb\.wal|sqlite3?|db)$", re.I)),
    ("env file", re.compile(r"(^|/)\.env(\.(?!example$)[^/]+)?$")),
    ("private key file", re.compile(r"\.(pem|key|p12|pfx)$", re.I)),
]

CONTENT_RULES = [
    ("home directory path", re.compile(r"/Users/(?!(?:example|you|me|USER|username)\b)[A-Za-z0-9._-]+")),
    ("home directory path", re.compile(r"/home/(?!(?:runner|user|example|you|USER|username)\b)[a-z0-9._-]+")),
    ("home directory path", re.compile(r"[A-Za-z]:\\Users\\(?!(?:example|you|USER|username)\b)[A-Za-z0-9._-]+")),
    ("local hostname", re.compile(r"\b[A-Za-z0-9-]+\.(?:local|lan|home\.arpa)\b")),
    ("private IP address", re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b")),
    ("OpenRouter key", re.compile(r"sk-or-v1-[0-9a-f]{32,}")),
    ("Anthropic key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI-style key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{32,}")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}\b|github_pat_[A-Za-z0-9_]{40,}")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Hugging Face token", re.compile(r"\bhf_[A-Za-z0-9]{30,}\b")),
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "hard-coded credential",
        re.compile(r"(?i)(?<![a-z])(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][A-Za-z0-9_\-./+]{16,}['\"]"),
    ),
]


@dataclass(frozen=True)
class Finding:
    where: str
    rule: str

    def __str__(self) -> str:
        return f"{self.where}: {self.rule}"


def load_extra_patterns() -> list[str]:
    """Machine-specific literals (username, hostname, …) that must never be committed.

    They come from an encrypted CI secret or a local file outside the repo, so the
    patterns themselves are never published.
    """
    raw = os.environ.get(EXTRA_ENV, "")
    if EXTRA_FILE.is_file():
        raw += "\n" + EXTRA_FILE.read_text(encoding="utf-8")
    items = [p.strip() for chunk in raw.splitlines() for p in chunk.split(",")]
    return [p.lower() for p in items if len(p) >= 3 and not p.startswith("#")]


def check_path(path: str, size: int | None) -> list[Finding]:
    findings = [Finding(path, f"blocked path ({name})") for name, rx in BLOCKED_PATHS if rx.search(path)]
    if size is not None and size > MAX_BYTES and not PUBLISHED_RE.match(path):
        findings.append(Finding(path, f"file larger than {MAX_BYTES // 1_000_000} MB outside published/"))
    return findings


def check_content(path: str, data: bytes, extra: list[str]) -> list[Finding]:
    if b"\0" in data[:8192]:
        return []  # binary: covered by path and size rules
    text = data.decode("utf-8", errors="replace")
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if ALLOW_MARKER in line:
            continue
        where = f"{path}:{lineno}"
        seen = set()
        for name, rx in CONTENT_RULES:
            if name not in seen and rx.search(line):
                seen.add(name)
                findings.append(Finding(where, name))
        lowered = line.lower()
        if any(p in lowered for p in extra):
            findings.append(Finding(where, "machine-specific pattern"))
    return findings


def git(*args: str) -> bytes:
    return subprocess.run(["git", *args], check=True, capture_output=True).stdout


def git_lines(*args: str) -> list[str]:
    return [line for line in git(*args).decode().split("\0") if line]


def check_blob(path: str, data: bytes, extra: list[str]) -> list[Finding]:
    return check_path(path, len(data)) + check_content(path, data, extra)


def scan_staged(extra: list[str]) -> list[Finding]:
    findings = []
    for path in git_lines("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"):
        findings += check_blob(path, git("show", f":{path}"), extra)
    return findings


def scan_tracked(extra: list[str]) -> list[Finding]:
    findings = []
    for path in git_lines("ls-files", "-z"):
        p = Path(path)
        if p.is_file():
            findings += check_blob(path, p.read_bytes(), extra)
    return findings


def scan_commits(rev_args: list[str], extra: list[str]) -> list[Finding]:
    """Check every version of every file touched by each commit selected by ``git rev-list``."""
    findings = []
    for commit in git("rev-list", *rev_args).decode().split():
        short = commit[:10]
        changed = git_lines(
            "diff-tree", "-r", "--root", "--no-commit-id", "--name-only", "--diff-filter=ACMR", "-z", commit
        )
        for path in changed:
            data = git("show", f"{commit}:{path}")
            findings += [Finding(f"{short} {f.where}", f.rule) for f in check_blob(path, data, extra)]
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--staged", action="store_true", help="files staged for commit (pre-commit hook)")
    mode.add_argument("--tracked", action="store_true", help="all tracked files in the working tree")
    mode.add_argument("--range", metavar="A..B", help="every commit in a revision range")
    mode.add_argument("--history", action="store_true", help="every commit reachable from any ref")
    args = ap.parse_args(argv)

    extra = load_extra_patterns()
    if args.staged:
        findings = scan_staged(extra)
    elif args.tracked:
        findings = scan_tracked(extra)
    elif args.history:
        findings = scan_commits(["--all"], extra)
    else:
        findings = scan_commits([args.range], extra)

    if findings:
        print(f"guard: {len(findings)} problem(s) — matched text is not shown:", file=sys.stderr)
        for f in dict.fromkeys(findings):
            print(f"  {f}", file=sys.stderr)
        print(f"Fix the content, or mark a deliberate example line with '{ALLOW_MARKER}'.", file=sys.stderr)
        return 1
    print(f"guard: ok ({len(extra)} machine-specific pattern(s) loaded)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

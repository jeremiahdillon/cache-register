"""Shared rules of our hand-curated datasets (`curated_disclosures`, `curated_asset_values`).

Each dataset is one CSV under `config/curated/`: one row per stated figure, cited with a short
verbatim quote, append-only (a correction is a new row that `supersedes` the old one). This module
holds what the datasets share: reading the CSV, parsing a figure as stated, the quote check and the
append-only rule with its git CLI. Not a source itself (no registry entry).
"""

from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
from collections.abc import Sequence
from decimal import Decimal

from cachereg.core.paths import REPO_ROOT

MAX_QUOTE_WORDS = 25

MULTIPLIERS = {
    "thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12, "quadrillion": 10**15,
    "k": 10**3, "m": 10**6, "b": 10**9, "t": 10**12,
}  # fmt: skip
NUMBER_WORDS = {
    w: i
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen twenty".split()
    )
} | {w: 10 * i for i, w in enumerate("thirty forty fifty sixty seventy eighty ninety".split(), start=3)}
STATED = re.compile(
    r"^(?P<cur>\$)?\s*(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|[a-z]+)"
    r"\s*(?P<mult>thousand|million|billion|trillion|quadrillion|[kmbt])?\s*(?P<plus>\+)?$",
    re.I,
)


class CuratedError(ValueError):
    """A curated file breaks a rule; the message names the row."""


def parse_stated(text: str) -> tuple[Decimal, bool, bool]:
    """A figure as stated → (value in base units, has a currency sign, has a trailing +).

    Digits with optional `$`, `,` and `+`, a K/M/B/T suffix or a multiplier word; or a number word
    (`seven billion`). Decimal arithmetic throughout: 8.3 × 10¹² is not exact in binary.
    """
    m = STATED.match(text.strip())
    if not m:
        raise CuratedError(f"value_as_stated {text!r} is not a figure this parser reads")
    num = m["num"].lower()
    if num.isalpha():
        if num not in NUMBER_WORDS:
            raise CuratedError(f"value_as_stated {text!r}: unknown number word {num!r}")
        base = Decimal(NUMBER_WORDS[num])
    else:
        base = Decimal(num.replace(",", ""))
    mult = MULTIPLIERS[m["mult"].lower()] if m["mult"] else 1
    return base * mult, bool(m["cur"]), bool(m["plus"])


def norm(text: str) -> str:
    """Lower case, straight quotes and single spaces: how a quote is compared with its figure."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text.replace(" ", " ")).strip().lower()


def read_rows(body: bytes, columns: Sequence[str], filename: str) -> list[dict]:
    """Parse the CSV (UTF-8, header row) without validating it."""
    reader = csv.DictReader(io.StringIO(body.decode("utf-8-sig"), newline=""))
    if tuple(reader.fieldnames or ()) != tuple(columns):
        raise CuratedError(f"{filename}: columns must be exactly {', '.join(columns)}")
    rows = []
    for i, r in enumerate(reader, start=2):
        if None in r or any(v is None for v in r.values()):
            raise CuratedError(f"{filename} line {i}: wrong number of fields")
        rows.append(r)
    return rows


def check_append_only(old: bytes, new: bytes, columns: Sequence[str], filename: str) -> None:
    """No row of `old` may be removed or changed in `new` (rows are only appended)."""
    before = {r["id"]: r for r in read_rows(old, columns, filename)}
    after = {r["id"]: r for r in read_rows(new, columns, filename)}
    for rid, row in before.items():
        if rid not in after:
            raise CuratedError(f"{rid}: a published row was removed (add a superseding row instead)")
        changed = [c for c in columns if row[c] != after[rid][c]]
        if changed:
            raise CuratedError(f"{rid}: a published row was edited ({', '.join(changed)}); add a superseding row")


def _git_show(rev: str, repo_path: str) -> bytes | None:
    """The file at `rev`, or None when the commit or the file does not exist there."""
    try:
        return subprocess.run(  # noqa: S603 (fixed git argv)
            ["git", "show", f"{rev}:{repo_path}"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,  # noqa: S607
        ).stdout
    except subprocess.CalledProcessError:
        return None


def append_only_main(argv: list[str], *, module: str, label: str, repo_path: str, columns: Sequence[str]) -> int:
    """`--base <rev> [--head <rev>]`: check the file at `head` (default: the working file) against the
    file at `base`. Skipped when `base` is all zeros (a new branch) or lacks the file."""
    args = dict(zip(argv[::2], argv[1::2], strict=False))
    if len(argv) % 2 or "--base" not in args or set(args) - {"--base", "--head"}:
        print(f"usage: python -m {module} --base REV [--head REV]", file=sys.stderr)
        return 2
    base, head = args["--base"], args.get("--head")
    if set(base) == {"0"}:
        print(f"{label}: no base commit; append-only check skipped")
        return 0
    old = _git_show(base, repo_path)
    if old is None:
        print(f"{label}: {repo_path} not at {base[:12]}; append-only check skipped")
        return 0
    working = REPO_ROOT / repo_path
    new = _git_show(head, repo_path) if head else (working.read_bytes() if working.is_file() else None)
    if new is None:
        print(f"{label}: {repo_path} was removed (a published file is never removed)", file=sys.stderr)
        return 1
    try:
        check_append_only(old, new, columns, repo_path.rsplit("/", 1)[-1])
    except CuratedError as e:
        print(f"{label}: {e}", file=sys.stderr)
        return 1
    return 0

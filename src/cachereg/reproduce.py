"""`cachereg reproduce receipts/<topic>`: rebuild one receipt on its own and compare with the commit.

1. fetch only the receipt's sources (unless ``no_fetch``);
2. pre-flight: can every source supply a vintage for the pinned as_of? A snapshot source with no
   fetch on/before it makes exact reproduction impossible → "cannot-reproduce";
3. build only marts whose inputs are those sources;
4. render into a temporary folder (never over the committed outputs);
5. compare the canonical data hash and source vintages with the committed manifest.

``latest=True`` reproduces the *method* on today's data instead and reports how it differs.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from cachereg.build import VintageGapError, build, cutoff, load_marts
from cachereg.core.registry import load_sources
from cachereg.render import read_manifest, render
from cachereg.story import config as folder_config


@dataclass
class ReproduceResult:
    status: str  # "identical" | "differs" | "cannot-reproduce" | "fetch-failed" | "rendered-latest"
    as_of: date
    reasons: list[str] = field(default_factory=list)
    out_dir: Path | None = None


def check_mart_coverage(cfg: folder_config.FolderConfig) -> None:
    """Fail clearly if the receipt's code reads a mart table whose inputs its `sources` don't cover."""
    code = "".join((cfg.path / n).read_text() for n in ("analysis.py", "charts.py") if (cfg.path / n).is_file())
    for mart in load_marts():
        used = [t for t in mart.tables if re.search(rf"\b{t}\b", code)]
        if used and not mart.inputs <= set(cfg.sources):
            missing = ", ".join(sorted(mart.inputs - set(cfg.sources)))
            raise ValueError(
                f"{cfg.path.name} reads {', '.join(used)} (mart {mart.name}); add {missing} to its receipt.yaml sources"
            )


def _when(record: dict) -> str:
    """How a manifest source record is dated: fetch date, or source revision date for Exact sources."""
    return record.get("fetch_date") or record.get("revision_date") or "?"


@contextlib.contextmanager
def _temporary_build_dir():
    """Build staged data and the warehouse in a temp folder so the author's warehouse is untouched."""
    old = os.environ.get("CACHEREG_BUILD_DIR")
    with tempfile.TemporaryDirectory(prefix="cachereg-build-") as tmp:
        os.environ["CACHEREG_BUILD_DIR"] = tmp
        try:
            yield
        finally:
            if old is None:
                os.environ.pop("CACHEREG_BUILD_DIR", None)
            else:
                os.environ["CACHEREG_BUILD_DIR"] = old


def reproduce(folder: Path, *, latest: bool = False, no_fetch: bool = False) -> ReproduceResult:
    cfg = folder_config.load(Path(folder))
    if cfg.kind != "receipt":
        raise ValueError("reproduce works on receipts (receipts/<topic>)")
    committed = read_manifest(cfg.path / "output")
    if committed is None:
        raise FileNotFoundError(f"{cfg.path.name}: no committed output/manifest.json to compare with")
    as_of = datetime.now(UTC).date() if latest else cfg.as_of
    check_mart_coverage(cfg)

    if not no_fetch:
        sources = load_sources()
        for sid in cfg.sources:
            try:
                raw = sources[sid].module("fetch").fetch()
                if raw is not None:  # None: nothing new to store
                    raw.write()
            except Exception as e:  # noqa: BLE001 (report which source failed and why, then stop)
                return ReproduceResult("fetch-failed", as_of, [f"fetch failed for {sid}: {type(e).__name__}: {e}"])

    # Pre-flight, after fetching and before any build.
    reasons = []
    for sid in cfg.sources:
        try:
            day, after = cutoff(sid, as_of)
        except VintageGapError as e:
            return ReproduceResult(
                "cannot-reproduce",
                as_of,
                [f"cannot reproduce exactly: {e}. Run with --latest to reproduce the method on your own data."],
            )
        if after:
            reasons.append(f"{sid}: no fetch on or before {as_of}; used the earliest one ({day}) instead")

    out_dir = Path(tempfile.mkdtemp(prefix=f"cachereg-{cfg.path.name}-"))
    with _temporary_build_dir():  # only raw data is shared; staged/warehouse are throwaway
        build(as_of, list(cfg.sources))
        result = render(cfg.path, as_of, out_dir=out_dir)
    new = result.manifest

    if latest:
        reasons.insert(0, f"rendered the method on data as of {as_of} (committed outputs are as of {cfg.as_of})")
        if new["data_hash"] == committed.get("data_hash"):
            reasons.append("the data is unchanged from the committed outputs")
        return ReproduceResult("rendered-latest", as_of, reasons, out_dir)

    if new["data_hash"] == committed.get("data_hash"):
        return ReproduceResult("identical", as_of, reasons, out_dir)
    for sid, v in new["sources"].items():
        old = committed.get("sources", {}).get(sid, {})
        if v.get("content_sha256") != old.get("content_sha256"):
            reasons.append(
                f"{sid} ({v['class']}): your data ({_when(v)}) differs from the committed run's ({_when(old)})"
            )
    if not reasons:
        reasons.append("same source vintages but different results: the analysis code or a dependency changed")
    return ReproduceResult("differs", as_of, reasons, out_dir)

"""Minimal .xlsx reader on the standard library (no Excel dependency).

An .xlsx file is a zip of XML parts. `read_sheets` returns the named worksheets as rows of cell
strings (shared and inline strings resolved, numbers as written in the XML, missing cells None). It
reads only the parts the workbook's relationships name and streams each sheet (`iterparse`), so a
100 MB sheet does not become a 1 GB tree. Not a source itself (no registry entry).

Guards, since the workbook is downloaded data: the zip's total declared size is capped (zip bomb),
and a part whose prolog declares a DOCTYPE or ENTITY is refused before it is parsed, which rules out
entity expansion and external entities (the attacks `defusedxml` exists for) without a dependency.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from collections.abc import Iterable
from xml.etree import ElementTree as ET

MAX_UNCOMPRESSED = 512 * 1024 * 1024
PROLOG_BYTES = 64 * 1024
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_COL = re.compile(r"^([A-Z]{1,3})\d+$")
_ROOT = re.compile(rb"<[A-Za-z]")
_DECL = re.compile(rb"<!(DOCTYPE|ENTITY)", re.I)


def _q(tag: str) -> str:
    return f"{{{MAIN}}}{tag}"


def _column(ref: str | None) -> int | None:
    m = _COL.match(ref or "")
    if not m:
        return None
    n = 0
    for ch in m.group(1):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _open_part(zf: zipfile.ZipFile, name: str) -> io.BufferedReader:
    """A part as a stream, after checking that its prolog declares no DOCTYPE or ENTITY."""
    try:
        with zf.open(name) as f:
            head = f.read(PROLOG_BYTES)
    except KeyError:
        raise ValueError(f"workbook part {name!r} is missing") from None
    root = _ROOT.search(head)
    if root is None and len(head) == PROLOG_BYTES:
        raise ValueError(f"workbook part {name!r}: no root element in the first {PROLOG_BYTES} bytes")
    if _DECL.search(head[: root.start() if root else len(head)]):
        raise ValueError(f"workbook part {name!r} declares a DOCTYPE or ENTITY; refused")
    return zf.open(name)


def _text(el: ET.Element) -> str:
    """A string item: plain <t>, or rich-text runs <r><t>…</t></r>; phonetic runs (<rPh>) are skipped."""
    parts = []
    for child in el:
        if child.tag == _q("t"):
            parts.append(child.text or "")
        elif child.tag == _q("r"):
            parts.extend(t.text or "" for t in child.iter(_q("t")))
    return "".join(parts)


def open_workbook(body: bytes) -> zipfile.ZipFile:
    try:
        zf = zipfile.ZipFile(io.BytesIO(body))
    except zipfile.BadZipFile as e:
        raise ValueError(f"not an .xlsx (zip) file: {e}") from None
    if sum(i.file_size for i in zf.infolist()) > MAX_UNCOMPRESSED:
        raise ValueError(f"workbook expands to more than {MAX_UNCOMPRESSED // 2**20} MB; refused")
    return zf


def sheet_paths(zf: zipfile.ZipFile) -> dict[str, str]:
    """Sheet name → zip part, in workbook order."""
    wb = ET.parse(_open_part(zf, "xl/workbook.xml")).getroot()  # noqa: S314 (_open_part refuses DTDs)
    rels = ET.parse(_open_part(zf, "xl/_rels/workbook.xml.rels")).getroot()  # noqa: S314
    targets = {r.get("Id"): r.get("Target") for r in rels.iter(f"{{{PKG_REL}}}Relationship")}
    out = {}
    for s in wb.iter(_q("sheet")):
        target = targets.get(s.get(f"{{{REL}}}id"))
        if not target:
            raise ValueError(f"sheet {s.get('name')!r} has no relationship target")
        path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        out[s.get("name")] = path
    return out


def shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    out = []
    for _, el in ET.iterparse(_open_part(zf, "xl/sharedStrings.xml")):  # noqa: S314 (DTDs refused)
        if el.tag == _q("si"):
            out.append(_text(el))
            el.clear()
    return out


def _rows(zf: zipfile.ZipFile, path: str, strings: list[str]) -> list[list[str | None]]:
    rows = []
    for _, el in ET.iterparse(_open_part(zf, path)):  # noqa: S314 (DTDs refused)
        if el.tag != _q("row"):
            continue
        cells: dict[int, str | None] = {}
        nxt = 0
        for c in el.iter(_q("c")):
            col = _column(c.get("r"))
            col = nxt if col is None else col
            nxt = col + 1
            kind, v = c.get("t"), c.find(_q("v"))
            if kind == "inlineStr":
                is_ = c.find(_q("is"))
                value = _text(is_) if is_ is not None else None
            elif v is None or v.text is None:
                value = None
            elif kind == "s":
                try:
                    value = strings[int(v.text)]
                except (ValueError, IndexError):
                    raise ValueError(f"{path}: shared string index {v.text!r} out of range") from None
            else:
                value = v.text
            cells[col] = value
        rows.append([cells.get(i) for i in range(max(cells) + 1)] if cells else [])
        el.clear()
    return rows


def read_sheets(body: bytes, names: Iterable[str]) -> dict[str, list[list[str | None]]]:
    """The named sheets of a workbook as rows of cell strings. A missing sheet is an error."""
    zf = open_workbook(body)
    paths = sheet_paths(zf)
    missing = [n for n in names if n not in paths]
    if missing:
        raise ValueError(f"workbook has no sheet(s) {missing}; it has {list(paths)}")
    strings = shared_strings(zf)
    return {n: _rows(zf, paths[n], strings) for n in names}

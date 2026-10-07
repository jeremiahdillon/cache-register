"""Census BTOS: Excel reader, workbook parser, fetch, stage and marts 070–072 on synthetic workbooks.

The workbooks are written by these tests in BTOS's layout (wide cycles newest first, `%` strings,
`S`, `.`, a trailing source line, serial and text dates). Cycle codes and their calendar dates follow
BTOS's real two-week schedule; every estimate is invented.
"""

from __future__ import annotations

import io
import zipfile
from datetime import UTC, date, datetime, timedelta
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import pytest
import yaml

from cachereg.build import build
from cachereg.core import paths
from cachereg.core.http import Response
from cachereg.core.manual import ManualInput
from cachereg.core.registry import load_sources, reproducibility_class
from cachereg.core.store import list_fetches
from cachereg.core.warehouse import connect, query
from cachereg.sources import _xlsx
from cachereg.sources.census_btos import fetch as bf
from cachereg.sources.census_btos import files, workbook
from cachereg.sources.census_btos import stage as bs
from cachereg.sources.ramp_ai_index import fetch as rf

# --- synthetic workbooks --------------------------------------------------------------------------

ORIGINAL = ["202517", "202518", "202519", "202520"]
SHUTDOWN = ["202521", "202522", "202523"]
CURRENT = ["202524", "202525", "202526", "202601"]
ALL = ORIGINAL + SHUTDOWN + CURRENT
START = {c: date(2025, 8, 11) + timedelta(days=14 * i) for i, c in enumerate(ALL)}  # Mondays
# National current-use `yes`, one decimal as Census publishes.
NATIONAL_YES = {"202517": 9.0, "202518": 9.5, "202519": 9.7, "202520": 10.2,
                "202524": 17.5, "202525": 17.2, "202526": 18.0, "202601": 18.3}  # fmt: skip
BASE = {"51": 40.0, "54": 35.0, "11": 5.0, "XX": 30.0, "A": 15.0, "G": 45.0}
SUPPRESSED = {("11", "202518"), ("11", "202525")}  # sector 11's `yes` is S in these cycles
GROUPS = {
    "national": [()],
    "sector": [("51",), ("54",), ("11",), ("XX",)],
    "size": [("A",), ("G",)],
    "sector_size": [("51", "A"), ("11", "G")],
}
KEYS = {"national": (), "sector": ("Sector",), "size": ("Empsize",), "sector_size": ("Sector", "Empsize")}
AT = datetime(2026, 1, 20, 12, tzinfo=UTC)


def qtext(kind: str, wording: str) -> str:
    return f"{workbook.QUESTIONS[kind]}{workbook.WORDINGS[wording]}? (Examples of AI: invented examples.)"


def yes_value(group: tuple, cycle: str, kind: str = "ai_current") -> float:
    if not group:
        v = NATIONAL_YES[cycle]
    else:
        v = BASE[group[-1]] + 0.5 * ALL.index(cycle) + (7.0 if cycle in CURRENT else 0.0)
    return v + (4.0 if kind == "ai_expected" else 0.0)


def cell(group: tuple, kind: str, answer: str, cycle: str, wording: str, se: bool, asked=None) -> str:
    asked = asked or (ORIGINAL if wording == "original" else CURRENT)
    if cycle not in asked:
        return "."
    if answer == "Yes" and group and group[0] == "11" and (group[0], cycle) in SUPPRESSED:
        return "S"
    yes = yes_value(group, cycle, kind)
    value = {"Yes": yes, "No": 95.0 - yes, "Do not know": 5.0}[answer]
    return f"{(0.5 if not group else 1.5):.2f}%" if se else f"{value:.1f}%"


def estimate_sheet(breakdown: str, wording: str, se: bool, cycles: list[str], **override) -> list[list]:
    keys = KEYS[breakdown]
    cols = sorted(cycles, reverse=True)  # newest first, as Census writes them
    rows = [[*keys, *workbook.FIXED, *cols]]
    for g in GROUPS[breakdown]:  # a non-AI question, which is skipped
        rows.append([*g, "3", "Overall, how would you describe this business's current performance?", "1",
                     "Excellent", *["12.0%"] * len(cols)])  # fmt: skip
    for kind, qid in (("ai_current", "7"), ("ai_expected", "24")):  # same IDs in both wordings
        for g in GROUPS[breakdown]:
            for aid, answer in enumerate(workbook.ANSWERS, start=1):
                text = override["question"] if kind == "ai_current" and "question" in override else qtext(kind, wording)
                values = (cell(g, kind, answer, c, wording, se, override.get("asked")) for c in cols)
                rows.append([*g, qid, text, str(aid), answer, *values])
    rows += [[], ["Source: U.S. Census Bureau, Business Trends and Outlook Survey (BTOS), synthetic test workbook."]]
    return rows


def serial(d: date) -> int:
    return (d - workbook.EXCEL_EPOCH).days


def cycle_dates(c: str) -> tuple[date, date, date, date, date | None]:
    s = START[c]
    return (
        s,
        s + timedelta(days=13),
        s - timedelta(days=14),
        s - timedelta(days=1),
        (None if c in SHUTDOWN else s + timedelta(days=17)),
    )


def current_dates(dates: dict | None = None) -> list[list]:
    """The date sheet; `dates` replaces some cycles' (collection start, end, reference start, end, publication)."""
    rows = [["Sample Year", "Cycle", "Panel", "Smpdt", "Collection Start", "Col End", "Reference Period Start",
             "Ref End", "Publication Date", None]]  # fmt: skip
    for i, c in enumerate(ALL):
        year = {"202517": "4", "202521": "SHUTDOWN", "202601": "5"}.get(c)
        cs, ce, rs, re_, pub = (dates or {}).get(c) or cycle_dates(c)
        rows.append([year, "1", str(i % 6 + 1), c, serial(cs), serial(ce), serial(rs), serial(re_),
                     serial(pub) if pub else None])  # fmt: skip
    return rows + [[None]]


def original_dates(cycles: list[str] = ORIGINAL, dates: dict | None = None) -> list[list]:
    rows = [["Smpdt", "Col Start", "Col End", "Ref Start", "Ref End"]]
    for c in cycles:
        rows.append([c, *(d.strftime("%m/%d/%Y") for d in ((dates or {}).get(c) or cycle_dates(c))[:4])])
    return rows


class _DeterministicZip(zipfile.ZipFile):
    """Fixed member timestamps, so the same sheets always give the same bytes (fetch dedupes by hash)."""

    def writestr(self, name, data, *args, **kwargs):
        info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        super().writestr(info, data, *args, **kwargs)


def write_xlsx(sheets: dict[str, list[list]], shared: bool = True, doctype: bool = False) -> bytes:
    """A minimal .xlsx: shared strings (or inline strings), numbers for ints, sparse cells for None."""
    strings: list[str] = []
    index: dict[str, int] = {}

    def col(i: int) -> str:
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    def c(ref: str, v) -> str:
        if v is None:
            return ""
        if isinstance(v, int | float):
            return f'<c r="{ref}"><v>{v}</v></c>'
        if not shared:
            return f'<c r="{ref}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
        if v not in index:
            index[v] = len(strings)
            strings.append(v)
        return f'<c r="{ref}" t="s"><v>{index[v]}</v></c>'

    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    rel_ns = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    buf = io.BytesIO()
    with _DeterministicZip(buf, "w", zipfile.ZIP_DEFLATED) as z:
        sheet_tags, rels = [], []
        for n, (name, rows) in enumerate(sheets.items(), start=1):
            body = "".join(
                f'<row r="{r + 1}">' + "".join(c(f"{col(i)}{r + 1}", v) for i, v in enumerate(row)) + "</row>"
                for r, row in enumerate(rows)
            )
            prolog = '<!DOCTYPE x [<!ENTITY a "aaaa">]>' if doctype and n == 1 else ""
            z.writestr(f"xl/worksheets/sheet{n}.xml", f'<?xml version="1.0"?>{prolog}<worksheet {ns}><sheetData>{body}'
                       "</sheetData></worksheet>")  # fmt: skip
            sheet_tags.append(f'<sheet name="{escape(name)}" sheetId="{n}" r:id="rId{n}"/>')
            rels.append(f'<Relationship Id="rId{n}" Target="worksheets/sheet{n}.xml" Type="x"/>')
        z.writestr("xl/workbook.xml", f"<workbook {ns} {rel_ns}><sheets>{''.join(sheet_tags)}</sheets></workbook>")
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(rels) + "</Relationships>",
        )  # fmt: skip
        if strings:
            items = "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
            z.writestr("xl/sharedStrings.xml", f"<sst {ns}>{items}</sst>")
    return buf.getvalue()


def current_file(breakdown: str, dates: dict | None = None, **override) -> bytes:
    return write_xlsx({
        files.CURRENT_ESTIMATES: estimate_sheet(breakdown, "current", False, ALL, **override),
        files.CURRENT_ERRORS: estimate_sheet(breakdown, "current", True, ALL, **override),
        "Index Estimates": [["Option Text", *sorted(ALL, reverse=True)]],
        files.DATES: current_dates(dates),
        "Data Dictionary": [["Item", "Description", "Notes"]],
    })  # fmt: skip


def original_file(cycles: list[str] = ORIGINAL, dates: dict | None = None) -> bytes:
    sheets = {}
    for t in files.BY_KEY["ai_original"].tables:
        sheets[t.estimates] = estimate_sheet(t.breakdown, "original", False, cycles, asked=cycles)
        sheets[t.errors] = estimate_sheet(t.breakdown, "original", True, cycles, asked=cycles)
    sheets[files.DATES] = original_dates(cycles, dates)
    return write_xlsx(sheets, shared=False)  # inline strings: the other string form


def bodies(**changed: bytes) -> dict[str, bytes]:
    out = {k: current_file(k) for k in ("national", "sector", "size", "sector_size")} | {"ai_original": original_file()}
    return out | changed


def serve(monkeypatch, served: dict[str, bytes]) -> list[str]:
    calls = []

    def fake_get(url, params=None, headers=None, **kw):
        calls.append(url)
        key = next(f.key for f in files.FILES if f.url == url)
        return Response(url, 200, served[key])

    monkeypatch.setattr(bf.http, "get", fake_get)
    monkeypatch.setattr(bf.time, "sleep", lambda s: None)
    return calls


def fetch_at(monkeypatch, at: datetime = AT, **changed: bytes):
    serve(monkeypatch, bodies(**changed))
    raw = bf.fetch()
    raw.fetched_at = at
    raw.write()
    return raw


# --- the Excel reader -----------------------------------------------------------------------------


def test_reader_resolves_shared_and_inline_strings_numbers_and_gaps():
    for shared in (True, False):
        body = write_xlsx({"One": [["a", None, "c"], [], [1, 2.5]], "Two": [["x & y"]]}, shared=shared)
        sheets = _xlsx.read_sheets(body, ["One", "Two"])
        assert sheets["One"] == [["a", None, "c"], [], ["1", "2.5"]]
        assert sheets["Two"] == [["x & y"]]


def test_reader_refuses_bad_workbooks(monkeypatch):
    with pytest.raises(ValueError, match="not an .xlsx"):
        _xlsx.read_sheets(b"PK not really", ["One"])
    with pytest.raises(ValueError, match="DOCTYPE"):
        _xlsx.read_sheets(write_xlsx({"One": [["a"]]}, doctype=True), ["One"])
    with pytest.raises(ValueError, match="no sheet"):
        _xlsx.read_sheets(write_xlsx({"One": [["a"]]}), ["Two"])
    monkeypatch.setattr(_xlsx, "MAX_UNCOMPRESSED", 10)
    with pytest.raises(ValueError, match="expands"):
        _xlsx.read_sheets(write_xlsx({"One": [["a"]]}), ["One"])


def one_part(xml: bytes) -> zipfile.ZipFile:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("p.xml", xml)
    return zipfile.ZipFile(io.BytesIO(buf.getvalue()))


def parse_part(xml: bytes):
    return ET.parse(_xlsx._open_part(one_part(xml), "p.xml")).getroot()  # noqa: S314 (the guard under test)


@pytest.mark.parametrize(
    ("xml", "match"),
    [
        (b'<?xml version="1.0"?><!-- <a --><!DOCTYPE t [<!ENTITY x "x">]><t>&x;</t>', "DOCTYPE"),  # after a comment
        (b"<t/><!DOCTYPE t>", "DOCTYPE"),  # anywhere in the part
        (b'<?xml version="1.0"?><!ENTITY x "x"><t/>', "DOCTYPE or ENTITY"),
        ('<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE t><t/>'.encode("utf-16"), "not UTF-8"),
        (b'<?xml version="1.0" encoding="ISO-8859-1"?><t/>', "not UTF-8"),
    ],
)
def test_reader_guard_refuses_declarations_anywhere_and_non_utf8(xml, match):
    with pytest.raises(ValueError, match=match):
        parse_part(xml)


def test_reader_reports_malformed_xml_as_value_error():
    body = write_xlsx({"One": [["a"]]})
    with zipfile.ZipFile(io.BytesIO(body)) as src, _DeterministicZip(buf := io.BytesIO(), "w") as out:
        for name in src.namelist():
            data = src.read(name)
            out.writestr(name, data.replace(b"</row>", b"") if name.endswith("sheet1.xml") else data)
    with pytest.raises(ValueError, match="unreadable workbook: ParseError"):
        _xlsx.read_sheets(buf.getvalue(), ["One"])


def test_reader_guard_accepts_utf8_escaped_text_and_sees_a_split_declaration(monkeypatch):
    assert parse_part(b'\xef\xbb\xbf<?xml version="1.0" encoding="UTF-8"?><t>&lt;!DOCTYPE x&gt;</t>').text == (
        "<!DOCTYPE x>")  # fmt: skip
    monkeypatch.setattr(_xlsx, "CHUNK", 8)  # the declaration spans two reads
    with pytest.raises(ValueError, match="DOCTYPE"):
        parse_part(b'<?xml version="1.0"?>   <!DOCTYPE t><t/>')
    assert parse_part(b'<?xml version="1.0"?><t>' + b"x" * 100 + b"</t>").text == "x" * 100


# --- the workbook parser --------------------------------------------------------------------------


@pytest.mark.parametrize("key", [f.key for f in files.FILES])
def test_every_file_parses(key):
    spec = files.BY_KEY[key]
    p = workbook.parse(bodies()[key], spec)
    expected = ORIGINAL if spec.wording == "original" else CURRENT
    assert sorted({c.cycle for c in p.cells}) == expected  # `.` cells (other wording, shutdown) give no rows
    assert {c.question for c in p.cells} == {"ai_current", "ai_expected"}
    assert {c.answer for c in p.cells} == {"yes", "no", "dont_know"}
    assert p.rejected == 0  # the blank row and the source line are not data


def test_values_suppression_and_standard_errors():
    p = workbook.parse(bodies()["national"], files.BY_KEY["national"])
    yes = {c.cycle: c for c in p.cells if c.question == "ai_current" and c.answer == "yes"}
    assert yes["202524"].estimate_pct == 17.5 and yes["202524"].se_pct == 0.5 and yes["202524"].group_key == "national"
    s = workbook.parse(bodies()["sector"], files.BY_KEY["sector"])
    sup = [c for c in s.cells if c.suppressed]
    assert {(c.sector_code, c.cycle, c.answer) for c in sup} == {("11", "202525", "yes")}
    assert all(c.estimate_pct is None and c.se_pct is None for c in sup)  # never 0


def test_dates_parse_from_serials_and_text_and_carry_the_sample_year():
    cur = workbook.parse(bodies()["national"], files.BY_KEY["national"]).cycles
    orig = workbook.parse(bodies()["ai_original"], files.BY_KEY["ai_original"]).cycles
    for c in ORIGINAL:
        a, b = cur[c], orig[c]
        assert (a.collection_start, a.collection_end, a.reference_start, a.reference_end) == (
            b.collection_start, b.collection_end, b.reference_start, b.reference_end)  # fmt: skip
    assert cur["202517"].reference_end == date(2025, 8, 10) and cur["202517"].publication_date == date(2025, 8, 28)
    assert cur["202522"].publication_date is None and cur["202522"].sample_year == 4
    assert cur["202521"].note == "SHUTDOWN" and cur["202601"].sample_year == 5


@pytest.mark.parametrize(
    ("question", "match"),
    [
        (qtext("ai_current", "original"), "original wording found in a file declared current"),
        ("In the last two weeks, did this business use Artificial Intelligence (AI) at all?", "unknown AI question"),
    ],
)
def test_a_wording_other_than_the_files_stops_the_parse(question, match):
    with pytest.raises(ValueError, match=match):
        workbook.parse(current_file("national", question=question), files.BY_KEY["national"])


def test_layout_errors_are_refused():
    spec = files.BY_KEY["sector"]
    good = estimate_sheet("sector", "current", False, ALL)
    for sheet, match in [
        ([["Industry", *good[0][1:]], *good[1:]], "header starts"),
        ([[*good[0], "latest"], *good[1:]], "cycle columns"),
        ([good[0]], "no AI rows"),
    ]:
        body = write_xlsx({files.CURRENT_ESTIMATES: sheet, files.CURRENT_ERRORS: sheet, files.DATES: current_dates()})
        with pytest.raises(ValueError, match=match):
            workbook.parse(body, spec)


def test_unreadable_cells_and_unknown_codes_are_counted_not_staged():
    sheet = estimate_sheet("sector", "current", False, ALL)
    ai = next(i for i, r in enumerate(sheet) if r[2:3] and "Artificial" in r[2])
    sheet[ai] = [*sheet[ai][:5], "n/a", *sheet[ai][6:]]  # one bad value
    sheet.insert(ai, ["9Z", *sheet[ai][1:]])  # an unknown sector code
    body = write_xlsx({files.CURRENT_ESTIMATES: sheet, files.CURRENT_ERRORS: sheet, files.DATES: current_dates()})
    p = workbook.parse(body, files.BY_KEY["sector"])
    assert p.rejected == 2  # the bad estimate and the unknown code (an unreadable SE is just null)
    assert "9Z" not in {c.sector_code for c in p.cells}


def test_an_ai_question_without_the_abbreviation_still_stops_the_parse():
    question = "In the last two weeks, did this business use artificial intelligence tools?"
    with pytest.raises(ValueError, match="unknown AI question"):
        workbook.parse(current_file("national", question=question), files.BY_KEY["national"])


def test_missing_and_orphan_standard_errors_are_counted():
    est = estimate_sheet("national", "current", False, ALL)
    se = estimate_sheet("national", "current", True, ALL)
    i = next(i for i, r in enumerate(se) if r[1:2] and "Artificial" in r[1] and r[3] == "Yes")
    orphan = [*se[i][:3], "Maybe", *se[i][4:]]
    se[i] = orphan  # the Yes row's errors are missing, and an SE row has no estimate row
    body = write_xlsx({files.CURRENT_ESTIMATES: est, files.CURRENT_ERRORS: se, files.DATES: current_dates()})
    p = workbook.parse(body, files.BY_KEY["national"])
    assert p.rejected == len(CURRENT) + 1  # four published estimates without an SE, one orphan SE row
    missing = [c for c in p.cells if c.question == "ai_current" and c.answer == "yes"]
    assert len(missing) == len(CURRENT) and all(c.se_pct is None and c.estimate_pct for c in missing)


# --- fetch ----------------------------------------------------------------------------------------


def test_fetch_validates_and_stores_changed_files_only(data_env, monkeypatch):
    first = fetch_at(monkeypatch)
    assert set(first.files) == {f.file_name for f in files.FILES}
    assert first.vintage["value"] == "202601" and first.vintage["date"] == "2026-01-15"
    second = fetch_at(monkeypatch, AT + timedelta(days=7))
    assert set(second.files) == {"national.xlsx"}  # the release marker is always stored
    assert set(second.vintage["unchanged"]) == {"sector", "size", "sector_size", "ai_original"}
    changed = write_xlsx({files.CURRENT_ESTIMATES: estimate_sheet("sector", "current", False, ALL[:-1]),
                          files.CURRENT_ERRORS: estimate_sheet("sector", "current", True, ALL[:-1]),
                          files.DATES: current_dates()})  # fmt: skip
    third = fetch_at(monkeypatch, AT + timedelta(days=14), sector=changed)
    assert set(third.files) == {"national.xlsx", "sector.xlsx"}
    manifest = list_fetches("census_btos")[0].manifest
    assert {r["url"] for r in manifest["requests"]} == {f.url for f in files.FILES}
    assert all(r["url"].startswith("https://www.census.gov/hfp/btos/downloads/") for r in manifest["requests"])


def test_fetch_writes_nothing_when_a_file_is_bad(data_env, monkeypatch):
    serve(monkeypatch, bodies(size=b"<html>maintenance</html>"))
    with pytest.raises(ValueError, match="Employment Size Class.xlsx"):
        bf.fetch()
    assert list_fetches("census_btos") == []


# --- stage and marts ------------------------------------------------------------------------------


def q(sql: str):
    con = connect()
    try:
        return query(con, sql)
    finally:
        con.close()


def test_stage_keeps_every_version_and_merges_dates(data_env, synthetic_entities, monkeypatch):
    fetch_at(monkeypatch)
    fetch_at(monkeypatch, AT + timedelta(days=7))
    out = bs.stage()
    v = out["versions"]
    assert v.height == 6 and v["readable"].all()  # 5 files, then national again
    e = out["estimates"]
    assert e.filter(e["file"] == "national")["fetch_id"].n_unique() == 2
    assert set(e["status"]) == {"published", "suppressed"}
    cycles = out["cycles"]
    assert cycles.height == len(ALL) and cycles.filter(cycles["first_of_sample_year"])["cycle"].to_list() == [
        "202517", "202601"]  # fmt: skip
    sectors = dict(out["sectors"].select("code", "naics").iter_rows())
    assert sectors["31"] == "31-33" and sectors["51"] == "51" and "XX" not in sectors and len(sectors) == 19


def test_an_unreadable_stored_version_is_reported_not_fatal(data_env, synthetic_entities, monkeypatch):
    raw = fetch_at(monkeypatch)
    stored = list_fetches("census_btos")[0]
    (stored.path / "size.xlsx").write_bytes(b"truncated")  # not a zip
    good = (stored.path / "sector.xlsx").read_bytes()
    with zipfile.ZipFile(io.BytesIO(good)) as src, _DeterministicZip(buf := io.BytesIO(), "w") as out:
        for name in src.namelist():  # a valid zip with malformed sheet XML
            data = src.read(name)
            out.writestr(name, data.replace(b"</row>", b"", 1) if name.endswith("sheet1.xml") else data)
    (stored.path / "sector.xlsx").write_bytes(buf.getvalue())
    out = bs.stage()
    bad = out["versions"].filter(~out["versions"]["readable"])
    assert sorted(bad["file"].to_list()) == ["sector", "size"] and set(bad["fetch_id"]) == {raw.fetch_id}
    assert out["_rejected_rows"]["rejected"][0] == 2


def test_stage_refuses_a_cycle_in_both_wordings(data_env, synthetic_entities, monkeypatch):
    overlap = [*ORIGINAL, "202524"]  # the original wording "asked" in a current-wording cycle
    fetch_at(monkeypatch, ai_original=original_file(overlap))
    with pytest.raises(ValueError, match=r"both AI wordings: \['202524'\]"):
        bs.stage()


def test_stage_refuses_disagreeing_collection_dates(data_env, synthetic_entities, monkeypatch):
    cs, ce, rs, re_, pub = cycle_dates("202518")
    fetch_at(monkeypatch, ai_original=original_file(dates={"202518": (cs, ce, rs + timedelta(days=1), re_, pub)}))
    with pytest.raises(ValueError, match="cycle 202518 has other collection or reference dates"):
        bs.stage()


def test_ai_use_breaks_and_coverage(data_env, synthetic_entities, monkeypatch):
    fetch_at(monkeypatch)
    build(date(2026, 1, 31), ["census_btos"])
    u = q("SELECT * FROM btos_ai_use WHERE breakdown = 'national' AND question = 'ai_current' AND answer = 'yes'")
    assert dict(u.select("cycle", "estimate_pct").iter_rows()) == NATIONAL_YES
    assert set(u.filter(u["cycle"].is_in(ORIGINAL))["wording"]) == {"original"}
    row = u.filter(u["cycle"] == "202524")
    assert row["low90_pct"][0] == pytest.approx(17.5 - 1.645 * 0.5) and row["reference_start"][0] == date(2025, 11, 3)
    breaks = q("SELECT kind, last_before, first_after FROM btos_series_breaks")
    assert set(breaks.iter_rows()) == {
        ("wording_change", "202520", "202524"), ("no_collection", "202521", "202521"),
        ("no_collection", "202522", "202522"), ("no_collection", "202523", "202523"),
        ("sample_year_start", "202517", "202517"), ("sample_year_start", "202601", "202601")}  # fmt: skip
    cov = q("SELECT * FROM btos_coverage WHERE breakdown = 'sector' AND question = 'ai_current'")
    assert dict(cov.select("group_key", "mapped").unique().iter_rows())["sector:XX"] is False
    s11 = cov.filter((cov["group_key"] == "sector:11") & (cov["wording"] == "current"))
    assert s11["cycles_suppressed"][0] == 1 and s11["cycles_published"][0] == 3
    assert q("SELECT count(*) AS n FROM btos_revision_check")["n"][0] == 0  # one version: nothing to compare


def test_cycles_published_after_as_of_are_left_out(data_env, synthetic_entities, monkeypatch):
    fetch_at(monkeypatch)
    build(date(2026, 1, 14), ["census_btos"])  # 202601 is published on 2026-01-15
    assert "202601" not in set(q("SELECT DISTINCT cycle FROM btos_ai_use")["cycle"])


def test_revision_check_reports_changed_past_cells_not_new_cycles(data_env, synthetic_entities, monkeypatch):
    older = ALL[:-1]  # the first version lacks the newest cycle
    first = write_xlsx({files.CURRENT_ESTIMATES: estimate_sheet("size", "current", False, older),
                        files.CURRENT_ERRORS: estimate_sheet("size", "current", True, older),
                        files.DATES: current_dates()})  # fmt: skip
    fetch_at(monkeypatch, size=first)
    revised = estimate_sheet("size", "current", False, ALL)
    i = next(i for i, r in enumerate(revised) if r[:1] == ["A"] and "Artificial" in r[2] and r[4] == "Yes")
    col = revised[0].index("202524")
    revised[i][col] = "99.9%"
    second = write_xlsx({files.CURRENT_ESTIMATES: revised,
                         files.CURRENT_ERRORS: estimate_sheet("size", "current", True, ALL),
                         files.DATES: current_dates()})  # fmt: skip
    fetch_at(monkeypatch, AT + timedelta(days=7), size=second)
    build(date(2026, 1, 31), ["census_btos"])
    rc = q("SELECT * FROM btos_revision_check")
    assert rc.select("file", "group_key", "cycle", "change", "used_pct").rows() == [
        ("size", "size:A", "202524", "value_changed", 99.9)]  # fmt: skip
    used = q("SELECT file, fetch_id FROM btos_versions WHERE used AND file = 'size'")
    assert used.height == 1


def test_monthly_series_by_reference_days(data_env, synthetic_entities, monkeypatch):
    fetch_at(monkeypatch)
    build(date(2026, 1, 31), ["census_btos"])
    m = q("SELECT * FROM btos_ai_monthly WHERE breakdown = 'national' AND question = 'ai_current'")
    by = {r["month"]: r for r in m.iter_rows(named=True)}
    nov, dec, aug = by[date(2025, 11, 1)], by[date(2025, 12, 1)], by[date(2025, 8, 1)]
    assert nov["pct"] == pytest.approx((17.5 + 17.2) / 2) and nov["wording"] == "current"  # 14 + 14 days
    assert nov["se"] == pytest.approx((2 * (14 * 0.5) ** 2) ** 0.5 / 28) and nov["ref_days_covered"] == 28
    assert dec["pct"] == pytest.approx((18.0 + 18.3) / 2) and not dec["partial"]
    assert aug["pct"] == pytest.approx((10 * 9.0 + 14 * 9.5 + 7 * 9.7) / 31) and aug["cycles"] == "202517,202518,202519"
    assert by[date(2025, 7, 1)]["partial"] and by[date(2025, 7, 1)]["ref_days_covered"] == 4
    assert date(2025, 10, 1) not in by  # the shutdown leaves October without a reference day
    assert m.group_by("month").len()["len"].max() == 1  # wordings are never averaged together
    s11 = q("SELECT * FROM btos_ai_monthly WHERE group_key = 'sector:11' AND question = 'ai_current'")
    flagged = {r["month"] for r in s11.iter_rows(named=True) if r["has_suppression"]}
    assert flagged == {date(2025, 8, 1), date(2025, 11, 1)}  # 202518 refs Aug; 202525 refs Nov


def test_a_three_week_reference_period_is_weighted_by_its_days(data_env, synthetic_entities, monkeypatch):
    # As after a 53-week ISO year: a 21-day collection fortnight 26, then fortnight 01 refers to 3 weeks.
    long = {
        "202526": (date(2025, 12, 15), date(2026, 1, 4), date(2025, 12, 1), date(2025, 12, 14), date(2026, 1, 8)),
        "202601": (date(2026, 1, 5), date(2026, 1, 18), date(2025, 12, 15), date(2026, 1, 4), date(2026, 1, 22)),
    }
    fetch_at(monkeypatch, **{k: current_file(k, dates=long) for k in ("national", "sector", "size", "sector_size")})
    build(date(2026, 1, 31), ["census_btos"])
    m = q("SELECT * FROM btos_ai_monthly WHERE breakdown = 'national' AND question = 'ai_current'")
    by = {r["month"]: r for r in m.iter_rows(named=True)}
    dec, jan = by[date(2025, 12, 1)], by[date(2026, 1, 1)]
    assert dec["pct"] == pytest.approx((14 * 18.0 + 17 * 18.3) / 31) and dec["ref_days_covered"] == 31
    assert jan["pct"] == pytest.approx(18.3) and jan["ref_days_covered"] == 4 and jan["partial"]


# --- with Ramp (analysis (c)) ---------------------------------------------------------------------

RAMP_OVERALL = ("Date", "Series", "Adoption rate (%)", "Monthly change (pp)", "Yearly change (pp)",
                "Census question version")  # fmt: skip


def ramp_import(cut: str, rows: list[list], at: datetime) -> None:
    from cachereg.sources.ramp_ai_index import cuts

    header = list(cuts.BY_ID[cut].columns)
    body = "\n".join(["\t".join(header)] + ["\t".join("" if v is None else str(v) for v in r) for r in rows])
    raw = rf.fetch(manual=ManualInput(body.encode(), "file", cut))
    raw.fetched_at = at
    raw.write()


PRE, POST = "pre_nov_2025_wording_change", "post_nov_2025_wording_change"


def ramp_census(dec: float = 17.833333, nov_version: str = POST) -> list[list]:  # Ramp's rule on NATIONAL_YES
    census = {"2025-08-01": (9.25, PRE), "2025-09-01": (9.95, PRE), "2025-10-01": (None, None),
              "2025-11-01": (17.5, nov_version), "2025-12-01": (dec, POST)}  # fmt: skip
    rows = []
    for i, (m, (v, ver)) in enumerate(census.items()):
        rows.append([m, "Ramp Overall", 40.0 + i, 0.5, "", ""])
        rows.append([m, "Census Estimate", v, "", "", ver])
    return rows


def two_lenses(monkeypatch, dec: float = 17.833333, nov_version: str = POST):
    fetch_at(monkeypatch)
    ramp_import("adoption/overall", ramp_census(dec, nov_version), AT)
    sector_rows = [
        [m, s, 30.0, 0.5] for m in ("2025-11-01", "2025-12-01") for s in ("Technology and media", "Construction")
    ]
    ramp_import("adoption/sector", sector_rows, AT + timedelta(minutes=1))
    build(date(2026, 1, 31), ["ramp_ai_index", "census_btos"])


def test_two_lenses_by_naics_with_the_assumed_sector_and_its_sensitivity(data_env, synthetic_entities, monkeypatch):
    two_lenses(monkeypatch)
    t = q("SELECT * FROM adoption_two_lenses")
    assert set(t["lens"]) == {"ramp_paid", "btos_use_current", "btos_use_expected"}
    s = t.filter(t["scope"] == "sector")
    assert set(s.filter(s["lens"] == "ramp_paid")["naics"]) == {"51", "23"}
    btos = s.filter(s["lens"] != "ramp_paid")
    assert dict(btos.select("naics", "role").unique().iter_rows()) == {"51": "matched", "54": "sensitivity"}
    assert btos.filter(btos["naics"] == "51")["naics_assumed"].all()  # Ramp's label mapping, not BTOS's
    overall = t.filter((t["scope"] == "overall") & (t["lens"] == "btos_use_current"))
    assert overall.filter(overall["month"] == date(2025, 11, 1))["pct"][0] == pytest.approx(17.35)


def test_ramp_census_check_reproduces_ramps_rules(data_env, synthetic_entities, monkeypatch):
    two_lenses(monkeypatch)
    c = q("SELECT * FROM btos_ramp_census_check")
    assert c["month"].to_list() == [date(2025, m, 1) for m in (8, 9, 10, 11, 12)]
    known = c.filter(c["ramp_pct"].is_not_null())
    assert known["agree"].all()
    # Aug and Sep straddle a month boundary differently under the two rules; Nov has one cycle either way.
    assert dict(known.select("month", "matches").iter_rows()) == {
        date(2025, 8, 1): "collection_start", date(2025, 9, 1): "collection_start",
        date(2025, 11, 1): "both", date(2025, 12, 1): "collection_start"}  # fmt: skip
    dec = c.filter(c["month"] == date(2025, 12, 1))
    assert dec["start_rule_cycles"][0] == 3 and dec["end_rule_cycles"][0] == 2
    october = c.filter(c["month"] == date(2025, 10, 1))
    assert october["start_rule_pct"][0] is None and october["agree"][0] is None


def test_ramp_census_check_accepts_the_end_rule(data_env, synthetic_entities, monkeypatch):
    two_lenses(monkeypatch, dec=(17.2 + 18.0) / 2)  # 202525 and 202526 end in December
    c = q("SELECT month, matches, agree FROM btos_ramp_census_check WHERE month = '2025-12-01'")
    assert c.rows() == [(date(2025, 12, 1), "collection_end", True)]


def test_ramp_census_check_flags_a_mismatch(data_env, synthetic_entities, monkeypatch):
    two_lenses(monkeypatch, dec=18.5)
    c = q("SELECT month, matches FROM btos_ramp_census_check WHERE NOT agree")
    assert c.rows() == [(date(2025, 12, 1), "neither")]


def test_ramp_census_check_compares_only_the_wording_ramp_names(data_env, synthetic_entities, monkeypatch):
    two_lenses(monkeypatch, nov_version=PRE)  # Ramp labels November with the original wording
    c = q("SELECT wording, ramp_pct, matches FROM btos_ramp_census_check WHERE month = '2025-11-01'")
    assert set(c.rows()) == {("original", 17.5, "neither"), ("current", None, None)}


# --- registry and entities ------------------------------------------------------------------------


def test_registry_and_sector_aliases():
    src = load_sources()["census_btos"]
    assert reproducibility_class(src) == "Latest-only" and src.requires == () and src.redistribution == "allowed"
    data = yaml.safe_load((paths.entities_dir() / "sectors.yaml").read_text())
    codes = [c for s in data["sectors"].values() for c in (s.get("aliases") or {}).get("btos", [])]
    assert len(codes) == len(set(codes)) == 19 and "92" not in codes and "XX" not in codes

"""Pre-production walkthrough 2026-07-27 — the two client-facing export findings.

E1 (P1) — the grand total wrapped mid-number in the PDF for totals ≥ €100 000.
    "IŠ VISO su PVM:" printed "131" on one line and "126,15 €" on the next: the
    headline number of the pasiūlymas a contractor hands to their client read as
    a different, smaller amount. Two independent causes, both fixed:
      * the money formatter joined the LT thousands groups with U+202F NARROW
        NO-BREAK SPACE, which reportlab's word splitter (platypus/paragraph.py
        `_wsc`) treats as breakable whitespace — it deliberately excludes \\xa0
        but LISTS \\u202f — so "131 126,15 €" was three separate words;
      * the Suma column was a hardcoded 2.7 cm, wide enough for a 9 pt line
        amount but not for the bold 11 pt total.
    Fix: NBSP-joined money + amount columns sized from the real string widths,
    with the totals block getting its own (wider) amount column at the same outer
    width. Same wrap risk existed on the Skyriaus suma / Suma be PVM / PVM 21%
    rows — covered below.

E2 (P2) — client-visible numbering gap. The app drops placeholder rows
    ("suveskite kiekį", no quantity) from the deliverable, but each surviving row
    kept its original eil_nr, so the client read 55 → 58. Fix: renumber the
    EXPORTED rows 1..N in both the PDF and the Excel — presentation only, the
    stored project is never touched — while leaving a hierarchical KŽ scheme
    ("1.1", "2.14") alone, because the client cross-references those.

Everything here asserts on the produced artifact: pdfplumber per-line text for
the PDF, openpyxl cells/formulas for the Excel.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pdfplumber
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import main  # noqa: E402
from main import app  # noqa: E402
import auth  # noqa: E402


@pytest.fixture()
def client(monkeypatch):
    """/generate-pdf and /generate-excel only need require_user — run under the
    dev bypass so these tests exercise the WRITER path, not the auth gate
    (same idiom as test_p3_generate_excel_injection)."""
    monkeypatch.setattr(auth, "AUTH_DISABLED", True)
    return TestClient(app)


# ── helpers ──────────────────────────────────────────────────────────────────

def _lt(v: float) -> str:
    """LT money exactly as the export prints it, with ASCII spaces.

    The PDF draws U+00A0; pdfplumber normalises every space variant to 0x20 when
    it extracts text, so comparing against ASCII spaces is what the *reader*
    sees. That is the point of the assertion: the digits, the separator and the
    € must all sit on ONE extracted line.
    """
    return f"{v:,.2f}".replace(",", " ").replace(".", ",")


def _pdf_lines(content: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(content)) as d:
        out: list[str] = []
        for pg in d.pages:
            out.extend((pg.extract_text() or "").splitlines())
    return out


def _line_with(lines: list[str], needle: str) -> str:
    hits = [l for l in lines if needle in l]
    assert hits, f"no line containing {needle!r} in:\n" + "\n".join(lines[-25:])
    return hits[0]


# 60+ rows, 3 sections, LT diacritics, placeholder rows already dropped by the
# app (the frontend filters `kiekis > 0` before POSTing) so the incoming nr
# sequence has holes — including the exact 55 → 58 jump from the walkthrough.
_DROPPED_ORIGINAL_NRS = {12, 33, 56, 57}

_SECTIONS = [
    # (skyrius, n_rows, kiekis, kaina)  → subtotal
    ("SIENŲ IR LUBŲ APDAILA", 25, 100.0, 45.00),   # 112 500,00 — a ≥100k subtotal
    ("GRINDŲ DANGOS",         20,  50.0, 30.00),   #  30 000,00
    ("ELEKTROS ĮRENGINIAI",   15,   7.0, 13.00),   #   1 365,00
]
_NET = 143865.00
_PVM = 30211.65
_TOTAL = 174076.65


def _walkthrough_rows() -> list[dict]:
    rows: list[dict] = []
    original_nr = 0
    for skyrius, n, kiekis, kaina in _SECTIONS:
        emitted = 0
        while emitted < n:
            original_nr += 1
            if original_nr in _DROPPED_ORIGINAL_NRS:
                continue          # placeholder row — the app already dropped it
            emitted += 1
            rows.append({
                "nr": str(original_nr),
                "aprasymas": f"Sienų glaistymas ir dažymas (ąčęėįšųūž) Nr. {original_nr}",
                "mato_vnt": "m²",
                "kiekis": kiekis,
                "kaina": kaina,
                "suma": round(kiekis * kaina, 2),
                "skyrius": skyrius,
            })
    return rows


def _payload(**over) -> dict:
    p = {"projektas": "Walkthrough sąmata", "tipas": "kz",
         "eilutes": _walkthrough_rows()}
    p.update(over)
    return p


def _one_row_payload(kaina: float) -> dict:
    return {"projektas": "Didelė sąmata", "tipas": "kz",
            "eilutes": [{"nr": "1", "aprasymas": "Bendrastatybiniai darbai",
                         "mato_vnt": "kompl.", "kiekis": 1.0, "kaina": kaina,
                         "suma": kaina, "skyrius": "STATYBA"}]}


def test_fixture_totals_are_what_the_export_will_compute():
    """Guards the magic numbers the E1 assertions below compare against."""
    rows = _walkthrough_rows()
    assert len(rows) == 60
    assert round(sum(r["suma"] for r in rows), 2) == _NET
    assert round(_NET * 0.21, 2) == _PVM
    assert round(_NET + _PVM, 2) == _TOTAL
    assert _lt(_TOTAL) == "174 076,65"


# ══════════════════════════════════════════════════════════════════════════
# E1 — no amount may wrap mid-number
# ══════════════════════════════════════════════════════════════════════════

def test_pdf_grand_total_above_100k_renders_on_one_line(client):
    """OLD: 'IŠ VISO su PVM:' / '174' / '076,65 €' on three separate lines."""
    r = client.post("/generate-pdf", json=_payload())
    assert r.status_code == 200, r.text
    lines = _pdf_lines(r.content)

    total_line = _line_with(lines, "IŠ VISO su PVM")
    assert f"{_lt(_TOTAL)} €" in total_line, total_line
    # and the label + amount are the SAME line, not label-then-orphaned-digits
    assert total_line.strip().startswith("IŠ VISO su PVM:")
    # no line may be a bare thousands group stranded from its remainder
    assert not any(l.strip() in ("174", "076,65 €") for l in lines), lines


def test_pdf_net_and_pvm_rows_render_on_one_line(client):
    r = client.post("/generate-pdf", json=_payload())
    lines = _pdf_lines(r.content)
    assert f"{_lt(_NET)} €" in _line_with(lines, "Suma be PVM")
    assert f"{_lt(_PVM)} €" in _line_with(lines, "PVM 21%")


def test_pdf_section_subtotal_above_100k_renders_on_one_line(client):
    """Same wrap risk on the per-section rows: 112 500,00 € at 9 pt bold."""
    r = client.post("/generate-pdf", json=_payload())
    lines = _pdf_lines(r.content)
    subtotal_lines = [l for l in lines if "Skyriaus suma" in l]
    assert len(subtotal_lines) == 3, subtotal_lines
    for expected in (112500.00, 30000.00, 1365.00):
        assert any(f"{_lt(expected)} €" in l for l in subtotal_lines), (
            f"{_lt(expected)} € not whole on any subtotal line: {subtotal_lines}")


def test_pdf_large_section_subtotal_renders_on_one_line(client):
    """The 9 pt rows survive further than the bold 11 pt total, but they DO break
    at the old fixed 2.7 cm — measured pre-fix: €1 234 560,00 still fit,
    €12 345 600,00 orphaned the €, €123 456 000,00 split mid-number. The column
    is now sized from the string, so all three stay whole."""
    rows = [
        {"nr": "1", "aprasymas": "Monolitinės konstrukcijos", "mato_vnt": "m³",
         "kiekis": 1000.0, "kaina": 12345.60, "suma": 12345600.00,
         "skyrius": "KONSTRUKCIJOS"},
        {"nr": "2", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
         "kiekis": 10.0, "kaina": 5.00, "suma": 50.00, "skyrius": "APDAILA"},
    ]
    r = client.post("/generate-pdf",
                    json={"projektas": "Didelis objektas", "tipas": "kz",
                          "eilutes": rows})
    lines = _pdf_lines(r.content)
    subtotal_lines = [l for l in lines if "Skyriaus suma" in l]
    assert any(f"{_lt(12345600.00)} €" in l for l in subtotal_lines), subtotal_lines
    # the 8 pt line amount in the same column must stay whole too
    assert any(_lt(12345600.00) in l and "Monolitinės" in l for l in lines), lines


@pytest.mark.parametrize("kaina,expected_total", [
    (99173.55,   "120 000,00"),     # 6-digit total — where the wrap started
    (826446.27,  "999 999,99"),     # 7-digit
    (8264462.80, "9 999 999,99"),   # top of the range the fix must cover
])
def test_pdf_totals_are_whole_across_magnitudes(client, kaina, expected_total):
    # expectations follow the backend's own rule: PVM = round(net×0.21, 2)
    net = kaina
    pvm = round(net * 0.21, 2)
    total = round(net + pvm, 2)
    assert _lt(total) == expected_total, "fixture arithmetic drifted"

    r = client.post("/generate-pdf", json=_one_row_payload(kaina))
    assert r.status_code == 200, r.text
    lines = _pdf_lines(r.content)
    assert f"{_lt(net)} €" in _line_with(lines, "Suma be PVM")
    assert f"{_lt(pvm)} €" in _line_with(lines, "PVM 21%")
    assert f"{expected_total} €" in _line_with(lines, "IŠ VISO su PVM")


def test_pdf_total_beyond_the_spec_range_still_does_not_wrap(client):
    """The amount column is measured, not hardcoded, so it grows past €10M."""
    r = client.post("/generate-pdf", json=_one_row_payload(100_000_000.00))
    lines = _pdf_lines(r.content)
    assert f"{_lt(121_000_000.00)} €" in _line_with(lines, "IŠ VISO su PVM")


def test_pdf_reverse_vat_total_above_100k_renders_on_one_line(client):
    """Renovation exports print 'IŠ VISO (be PVM)' at the same bold 11 pt."""
    r = client.post("/generate-pdf", json=_payload(archetipas="renovacija"))
    lines = _pdf_lines(r.content)
    assert f"{_lt(_NET)} €" in _line_with(lines, "IŠ VISO (be PVM)")


@pytest.mark.parametrize("kiekis,kaina", [
    (1.0, 8264462.80),      # 7-digit unit price — broke as "8 264 462,8" / "0"
    (1234567.0, 8.0),       # 7-digit quantity
])
def test_pdf_kiekis_and_kaina_cells_do_not_break_either(client, kiekis, kaina):
    """Same defect class as E1 in the neighbouring columns; the widths are
    probed there too, so no numeric cell in the document can split."""
    rows = [{"nr": "1", "aprasymas": "Bendrastatybiniai darbai",
             "mato_vnt": "kompl.", "kiekis": kiekis, "kaina": kaina,
             "suma": round(kiekis * kaina, 2), "skyrius": "STATYBA"}]
    r = client.post("/generate-pdf",
                    json={"projektas": "T", "tipas": "kz", "eilutes": rows})
    lines = _pdf_lines(r.content)
    row_line = _line_with(lines, "Bendrastatybiniai darbai")
    for val in (kiekis, kaina, round(kiekis * kaina, 2)):
        assert _lt(val) in row_line, (val, row_line)


def test_pdf_line_amount_column_still_fits_a_7_digit_line(client):
    """Widening the totals column must not have narrowed the data rows."""
    r = client.post("/generate-pdf", json=_one_row_payload(8264462.80))
    lines = _pdf_lines(r.content)
    assert any(_lt(8264462.80) in l and "Bendrastatybiniai" in l for l in lines), (
        "the line amount is not on the same row as its description:\n"
        + "\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════
# E2 — exported rows are renumbered 1..N, presentation only
# ══════════════════════════════════════════════════════════════════════════

_PDF_ROW_NR = re.compile(r"^(\d+)\s+Sienų glaistymas ir dažymas")


def test_pdf_exported_rows_are_numbered_without_gaps(client):
    """OLD: the client read 55 → 58 where placeholder rows had been dropped."""
    r = client.post("/generate-pdf", json=_payload())
    lines = _pdf_lines(r.content)
    nrs = [int(m.group(1)) for l in lines if (m := _PDF_ROW_NR.match(l.strip()))]
    assert nrs == list(range(1, 61)), nrs


def test_excel_exported_rows_are_numbered_without_gaps(client):
    r = client.post("/generate-excel", json=_payload())
    assert r.status_code == 200, r.text
    ws = load_workbook(io.BytesIO(r.content))["Sąmata"]
    nrs = [c[0] for c in _excel_data_rows(ws)]
    assert nrs == [str(i) for i in range(1, 61)], nrs


def _excel_data_rows(ws) -> list[tuple[str, int]]:
    """(nr, sheet_row) for every priced data row — identified by its own
    =ROUND(Dn*En,2) Suma formula, which section headers and subtotals lack."""
    out = []
    for row in range(1, ws.max_row + 1):
        f = ws.cell(row=row, column=6).value
        if isinstance(f, str) and f.startswith("=ROUND(D"):
            out.append((ws.cell(row=row, column=1).value, row))
    return out


def test_excel_formulas_still_reference_their_own_row_after_renumbering(client):
    r = client.post("/generate-excel", json=_payload())
    ws = load_workbook(io.BytesIO(r.content))["Sąmata"]
    data_rows = _excel_data_rows(ws)
    assert len(data_rows) == 60
    for _nr, row in data_rows:
        assert ws.cell(row=row, column=6).value == f"=ROUND(D{row}*E{row},2)"
        # the referenced operands are the numbers written on that same row
        assert isinstance(ws.cell(row=row, column=4).value, (int, float))
        assert isinstance(ws.cell(row=row, column=5).value, (int, float))


def test_excel_subtotal_ranges_cover_exactly_their_section_rows(client):
    r = client.post("/generate-excel", json=_payload())
    ws = load_workbook(io.BytesIO(r.content))["Sąmata"]
    data_rows = {row for _nr, row in _excel_data_rows(ws)}

    ranges = []
    for row in range(1, ws.max_row + 1):
        v = ws.cell(row=row, column=6).value
        if isinstance(v, str) and v.startswith("=SUBTOTAL(9,"):
            a, b = re.match(r"=SUBTOTAL\(9,F(\d+):F(\d+)\)", v).groups()
            ranges.append((int(a), int(b), row))

    # 3 section subtotals + 1 grand "Suma be PVM"
    assert len(ranges) == 4, ranges
    for a, b, own in ranges:
        assert a <= b, f"inverted range F{a}:F{b}"
        assert own > b, "a subtotal must sit below the rows it sums"
    section_ranges = ranges[:3]
    covered = set()
    for a, b, _own in section_ranges:
        rows_in = {r for r in range(a, b + 1) if r in data_rows}
        assert rows_in, f"section range F{a}:F{b} covers no data row"
        covered |= rows_in
    assert covered == data_rows, "some data rows are in no section subtotal"
    # the grand total spans every data row (SUBTOTAL(9) skips nested SUBTOTALs)
    ga, gb, _ = ranges[3]
    assert ga <= min(data_rows) and gb >= max(data_rows)


def test_excel_lt_headers_are_unchanged(client):
    r = client.post("/generate-excel", json=_payload())
    ws = load_workbook(io.BytesIO(r.content))["Sąmata"]
    assert [ws.cell(row=3, column=c).value for c in range(1, 7)] == [
        "Nr.", "Aprašymas", "Mat. vnt.", "Kiekis", "Kaina €", "Suma €"]


def test_excel_section_sheets_share_the_combined_sheet_numbering(client):
    """A row must carry the same Nr. on its section tab and on 'Sąmata'."""
    r = client.post("/generate-excel", json=_payload())
    wb = load_workbook(io.BytesIO(r.content))
    combined = {ws_val: None for ws_val, _ in _excel_data_rows(wb["Sąmata"])}
    per_sheet: list[str] = []
    for name in wb.sheetnames:
        if name in ("Sąmata", "Prielaidos", "Patalpos", "Pastabos"):
            continue
        per_sheet += [nr for nr, _row in _excel_data_rows(wb[name])]
    assert sorted(per_sheet, key=int) == sorted(combined, key=int)


_HIERARCHICAL = {
    "projektas": "Tenderio KŽ", "tipas": "kz",
    "eilutes": [
        {"nr": "1.1", "aprasymas": "Žemės darbai", "mato_vnt": "m³",
         "kiekis": 10, "kaina": 12.0, "suma": 120.0, "skyrius": "ŽEMĖS DARBAI"},
        {"nr": "1.3", "aprasymas": "Grunto išvežimas", "mato_vnt": "m³",
         "kiekis": 10, "kaina": 8.0, "suma": 80.0, "skyrius": "ŽEMĖS DARBAI"},
        {"nr": "2.14", "aprasymas": "Betonavimas", "mato_vnt": "m³",
         "kiekis": 5, "kaina": 100.0, "suma": 500.0, "skyrius": "BETONAS"},
    ],
}


def test_hierarchical_kz_numbering_is_preserved_in_both_exports(client):
    """A tender KŽ's positions are the client's own reference — never rewritten
    (renumbering 1.1/1.3/2.14 → 1/2/3 would break the cross-reference)."""
    lines = _pdf_lines(client.post("/generate-pdf", json=_HIERARCHICAL).content)
    for nr, desc in (("1.1", "Žemės darbai"), ("1.3", "Grunto išvežimas"),
                     ("2.14", "Betonavimas")):
        assert any(l.strip().startswith(f"{nr} {desc}") for l in lines), (nr, lines)

    ws = load_workbook(io.BytesIO(
        client.post("/generate-excel", json=_HIERARCHICAL).content))["Sąmata"]
    assert [nr for nr, _row in _excel_data_rows(ws)] == ["1.1", "1.3", "2.14"]


def test_renumbering_never_touches_the_caller_rows():
    """Presentation only: the stored project keeps its own eil_nr."""
    stored = [{"nr": "55", "aprasymas": "A"}, {"nr": "58", "aprasymas": "B"}]
    exported = main._sequential_export_nr(stored)
    assert [e["nr"] for e in exported] == ["1", "2"]
    assert [e["nr"] for e in stored] == ["55", "58"]      # untouched
    exported[0]["aprasymas"] = "MUTATED"
    assert stored[0]["aprasymas"] == "A"                  # rows are copies


def test_renumbering_leaves_coded_positions_alone():
    coded = [{"nr": "A.3"}, {"nr": "A.4"}]
    assert [e["nr"] for e in main._sequential_export_nr(coded)] == ["A.3", "A.4"]
    mixed = [{"nr": "1"}, {"nr": "2.1"}]
    assert [e["nr"] for e in main._sequential_export_nr(mixed)] == ["1", "2.1"]
    assert main._sequential_export_nr([]) == []

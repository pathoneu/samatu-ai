"""extractor/schedules.py and the door schedule fed by the table reader, on synthetic sheets
(tests/synthetic_plan.py — invented drawings, no client data)."""
from __future__ import annotations

import pytest
from reportlab.lib.pagesizes import A4

from extractor import schedules as sch
from extractor import table_reader as tr
from extractor.door_schedule import scan_door_schedule
from synthetic_plan import TABLE_COL_W, TABLE_ROW_H, RuledTable, Sheet, build_plan, two_rooms

W, H = A4
TOL = 0.005


@pytest.fixture(autouse=True)
def _fresh_cache():
    tr.clear()
    yield
    tr.clear()


def _sheet(*tables, **kw) -> Sheet:
    s = two_rooms()
    s.ruled_tables = list(tables)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _read(*sheets):
    return sch.read_schedules(build_plan(list(sheets)), range(1, len(sheets) + 1))


DOORS = RuledTable(at=(330.0, 300.0), col_w=(40.0, 50.0, 50.0, 70.0), title="DURŲ ŽINIARAŠTIS",
                   rows=(("Žymuo", "Plotis, mm", "Aukštis, mm", "Tipas"),
                         ("D-1", "900", "2100", "Beapvadinės"),
                         ("D-2", "800", "2100", "Su apvadais")))
WINDOWS = RuledTable(at=(330.0, 420.0), col_w=(40.0, 60.0, 40.0), title="LANGŲ ŽINIARAŠTIS",
                     rows=(("Žymuo", "Dydis, mm", "Kiekis"), ("L-1", "1200x1500", "4"), ("L-2", "900x1500", "1")))
FINISHES = RuledTable(at=(60.0, 420.0), col_w=(30.0, 60.0, 55.0, 55.0, 55.0, 50.0), title="APDAILOS LENTELĖ",
                      rows=(("Nr.", "Patalpa", "Grindys", "Sienos", "Lubos", "Grindjuostės"),
                            ("01", "Virtuvė", "Keraminės plytelės", "Dažomos", "Dažomos", "Nėra"),
                            ("02", "Svetainė", "Laminatas", "Dažomos", "Įtempiamos", "MDF")))
TILES = RuledTable(at=(60.0, 520.0), col_w=(50.0, 60.0, 60.0), title="PLYTELIŲ SPECIFIKACIJA",
                   rows=(("Vieta", "Formatas", "Gamintojas"), ("Vonia, grindys", "600x600", "Gamykla A"),
                         ("Vonia, sienos", "300x600", "Gamykla B")))


# ── kinds and values ────────────────────────────────────────────────────────


def test_a_door_schedule_is_read_with_sizes_types_and_row_boxes():
    res = _read(_sheet(DOORS))
    d = res["ziniarasciai"]["durys"]
    assert res["status"] == "ok" and d["title"] == "DURŲ ŽINIARAŠTIS" and d["pages"] == [1]
    assert [(r["kodas"], r["plotis_mm"], r["aukstis_mm"], r["tipas"]) for r in d["rows"]] == [
        ("D-1", 900, 2100, "beapvadines"), ("D-2", 800, 2100, "su_apvadais")]
    x, top = DOORS.at
    want = [x / W, (top + 14) / H, (x + sum(DOORS.col_w)) / W, (top + 28) / H]
    assert all(abs(a - b) <= TOL for a, b in zip(d["rows"][0]["bbox_pct"], want))
    assert d["rows"][0]["page"] == 1 and d["columns"]["plotis"] == "Plotis, mm"


def test_a_window_schedule_reads_one_size_cell_and_its_count():
    w = _read(_sheet(WINDOWS))["ziniarasciai"]["langai"]
    assert [(r["kodas"], r["plotis_mm"], r["aukstis_mm"], r["kiekis"]) for r in w["rows"]] == [
        ("L-1", 1200, 1500, 4), ("L-2", 900, 1500, 1)]


def test_one_table_of_doors_and_windows_feeds_both_schedules():
    mixed = RuledTable(at=(330.0, 300.0), col_w=(40.0, 60.0, 40.0), title="ANGŲ ŽINIARAŠTIS",
                       rows=(("Žymuo", "Dydis, mm", "Kiekis"), ("D-1", "900x2100", "2"), ("L-1", "1200x1500", "3")))
    z = _read(_sheet(mixed))["ziniarasciai"]
    assert [r["kodas"] for r in z["durys"]["rows"]] == ["D-1"] and [r["kodas"] for r in z["langai"]["rows"]] == ["L-1"]


def test_sizes_in_metres_or_centimetres_are_read_as_millimetres():
    t = RuledTable(at=(330.0, 300.0), col_w=(40.0, 50.0, 50.0), title="DURŲ ŽINIARAŠTIS",
                   rows=(("Žymuo", "Plotis, m", "Aukštis, cm"), ("D-1", "0,9", "210")))
    r = _read(_sheet(t))["ziniarasciai"]["durys"]["rows"][0]
    assert (r["plotis_mm"], r["aukstis_mm"]) == (900, 2100)


def test_the_wall_thickness_column_is_not_the_door_width():
    t = RuledTable(at=(330.0, 300.0), col_w=(40.0, 60.0, 60.0, 60.0), title="DURŲ ŽINIARAŠTIS",
                   rows=(("Kodas", "Pertvaros plotis, mm", "Angos plotis, mm", "Angos aukštis, mm"),
                         ("D-1", "125", "910", "2100")))
    r = _read(_sheet(t))["ziniarasciai"]["durys"]["rows"][0]
    assert (r["plotis_mm"], r["aukstis_mm"]) == (910, 2100)


def test_a_finish_schedule_gives_each_room_its_finishes_and_floor_kind():
    a = _read(_sheet(FINISHES))["ziniarasciai"]["apdaila"]
    rows = [(r["nr"], r["pavadinimas"], r["grindys"], r["lubos"], r["grindjuostes"], r["grindu_danga"]) for r in a["rows"]]
    assert rows == [("01", "Virtuvė", "Keraminės plytelės", "Dažomos", "Nėra", "plyteles"),
                    ("02", "Svetainė", "Laminatas", "Įtempiamos", "MDF", "minksta")]


def test_a_finish_schedule_with_the_number_written_in_the_room_cell():
    t = RuledTable(at=(60.0, 420.0), col_w=(80.0, 55.0, 55.0, 55.0),
                   rows=(("Patalpa", "Grindys", "Sienos", "Lubos"), ("03 Vonia", "Plytelės", "Plytelės", "Dažomos")))
    r = _read(_sheet(t))["ziniarasciai"]["apdaila"]["rows"][0]
    assert (r["nr"], r["pavadinimas"]) == ("03", "Vonia")


def test_a_tile_specification_table():
    p = _read(_sheet(TILES))["ziniarasciai"]["plyteles"]
    assert [(r["vieta"], r["formatas_mm"], r["gamintojas"]) for r in p["rows"]] == [
        ("Vonia, grindys", [600, 600], "Gamykla A"), ("Vonia, sienos", [300, 600], "Gamykla B")]


def test_a_room_table_and_its_own_sum():
    t = RuledTable(at=(60.0, 420.0), col_w=(30.0, 80.0, 40.0), title="PATALPŲ EKSPLIKACIJA",
                   rows=(("Nr.", "Pavadinimas", "Plotas, m²"), ("01", "Koridorius", "6,20"), ("02", "Kambarys", "14,05"),
                         ("", "Iš viso", "20,25")))
    e = _read(_sheet(t))["ziniarasciai"]["eksplikacija"]
    assert [(r["nr"], r["plotas_m2"]) for r in e["rows"]] == [("01", 6.2), ("02", 14.05)]
    assert [x["value"] for x in e["totals"]] == [20.25] and e["totals"][0]["bbox_pct"]


def test_a_table_with_no_known_header_is_no_schedule():
    t = RuledTable(at=(60.0, 420.0), col_w=(60.0, 60.0), rows=(("Medžiaga", "Spalva"), ("Dažai", "Balta"), ("Lakas", "Bespalvis")))
    res = _read(_sheet(t))
    assert res["status"] == "nera" and not any(res["ziniarasciai"].values())
    assert res["lenteles"]["1"][0].get("schedule") is None


# ── continued tables ────────────────────────────────────────────────────────


def test_a_door_schedule_continued_on_the_next_sheet_is_one_schedule():
    rest = RuledTable(at=(330.0, 100.0), col_w=DOORS.col_w,
                      rows=(("D-3", "700", "2100", "Beapvadinės"), ("D-4", "700", "2100", "Stumdomos")))
    d = _read(_sheet(DOORS), _sheet(rest))["ziniarasciai"]["durys"]
    assert [r["kodas"] for r in d["rows"]] == ["D-1", "D-2", "D-3", "D-4"]
    assert d["pages"] == [1, 2] and d["tesinys"] is True and [r["page"] for r in d["rows"]] == [1, 1, 2, 2]
    assert d["rows"][3]["tipas"] == "stumdomos"


def test_a_continued_finish_schedule_whose_first_row_looks_like_a_header_keeps_that_room():
    rest = RuledTable(at=(60.0, 600.0), col_w=FINISHES.col_w,              # clear of the plan's walls
                      rows=(("03", "Vonia", "Plytelės", "Plytelės", "Dažomos", "Nėra"),
                            ("04", "Miegamasis", "Laminatas", "Dažomos", "Dažomos", "MDF")))
    a = _read(_sheet(FINISHES), _sheet(rest))["ziniarasciai"]["apdaila"]
    assert [r["nr"] for r in a["rows"]] == ["01", "02", "03", "04"] and a["pages"] == [1, 2]


def test_a_repeated_header_on_the_next_sheet_continues_without_listing_a_code_twice():
    again = RuledTable(at=(330.0, 100.0), col_w=DOORS.col_w, title="DURŲ ŽINIARAŠTIS (TĘSINYS)",
                       rows=(DOORS.rows[0], ("D-2", "800", "2100", "Su apvadais"), ("D-5", "1000", "2100", "Stiklinės")))
    d = _read(_sheet(DOORS), _sheet(again))["ziniarasciai"]["durys"]
    assert [r["kodas"] for r in d["rows"]] == ["D-1", "D-2", "D-5"] and d["pages"] == [1, 2]


def test_a_merged_two_row_header_maps_its_columns():
    t = RuledTable(at=(60.0, 420.0), col_w=(40.0, 50.0, 50.0, 40.0), title="LANGŲ ŽINIARAŠTIS",
                   rows=(("Žymuo", "Angos matmenys, mm", None, "Kiekis"), (None, "plotis", "aukštis", None),
                         ("L-1", "1200", "1500", "2")),
                   spans=((0, 1, 2, 1), (0, 0, 1, 2), (0, 3, 1, 2)))
    r = _read(_sheet(t))["ziniarasciai"]["langai"]["rows"][0]
    assert (r["kodas"], r["plotis_mm"], r["aukstis_mm"], r["kiekis"]) == ("L-1", 1200, 1500, 2)


@pytest.mark.parametrize("rotation", [90, 270])
def test_a_schedule_on_a_rotated_sheet_reads_the_same(rotation):
    d = _read(_sheet(DOORS, rotate=rotation))["ziniarasciai"]["durys"]
    assert [(r["kodas"], r["plotis_mm"]) for r in d["rows"]] == [("D-1", 900), ("D-2", 800)]


def test_candidate_pages_come_from_the_text_layer():
    pdf = build_plan([two_rooms(), _sheet(DOORS)])
    assert sch.candidate_pages(pdf) == [2]


def test_too_many_candidate_sheets_are_capped_and_said():
    res = sch.read_schedules(build_plan([_sheet(DOORS), _sheet(WINDOWS)]), [1, 2], max_pages=1)
    assert res["lapai"] == [1] and "1 lapuose iš 2" in res["detail"]


def test_a_scanned_sheet_says_the_tables_cannot_be_read():
    import io
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.line(100, 700, 300, 700)
    c.showPage()
    c.save()
    res = sch.read_schedules(buf.getvalue(), [1])
    assert res["status"] == "no_text" and "teksto" in res["detail"] and res["praleisti"]["1"]


# ── the door schedule scanner, fed by the ruled table ───────────────────────


def test_the_door_schedule_scanner_reads_a_ruled_table_with_row_boxes():
    # the notes give the sheet the text layer a real drawing has (the scanner needs 200 characters)
    s = _sheet(table_at=(330.0, 300.0), notes_at=(60.0, 450.0))
    out = scan_door_schedule(build_plan([s]))
    lent = out["lentele"]
    assert out["status"] == "lentele" and lent["saltinis"] == "lentele" and lent["page"] == 1
    assert [(r["kodas"], r["plotis_mm"], r["aukstis_mm"], r["kiekis"]) for r in lent["eilutes"]] == [
        ("D1", 900, 2100, 3), ("D2", 800, 2100, 2), ("D3", 700, 2100, 1)]
    x, top = 330.0, 300.0
    want = [x / W, (top + TABLE_ROW_H) / H, (x + sum(TABLE_COL_W)) / W, (top + 2 * TABLE_ROW_H) / H]
    assert all(abs(a - b) <= TOL for a, b in zip(lent["eilutes"][0]["bbox_pct"], want))
    assert lent["bbox_pct"] and all(r["page"] == 1 for r in lent["eilutes"])


def test_a_schedule_written_without_rules_is_read_from_words_and_still_gets_row_boxes():
    from test_door_schedule_2026_09_23 import _pdf, _schedule_page
    pdf = _pdf([_schedule_page([("D-1", 910, 2100, "Dešininės, beapvadinės"), ("D-2", 910, 2100, "Kairinės, beapvadinės")])])
    out = scan_door_schedule(pdf)
    lent = out["lentele"]
    assert lent["saltinis"] == "zodziai" and [r["kodas"] for r in lent["eilutes"]] == ["D-1", "D-2"]
    for r in lent["eilutes"]:
        x0, y0, x1, y1 = r["bbox_pct"]
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1 and x0 >= 838 / 1191 - 0.01

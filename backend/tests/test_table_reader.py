"""extractor/table_reader.py on synthetic sheets (tests/synthetic_plan.py — invented drawings, no client data).

Every box is predicted from what the sheet draws and must land in the PDFium DISPLAY frame (the frame of the
sheet zones, the room outlines and the evidence crops), at /Rotate 0, 90 and 270.
"""
from __future__ import annotations

import io

import pytest
from reportlab.lib.pagesizes import A4

from extractor import table_reader as tr
from extractor.cv_match import _rotate_pct
from extractor.sheet_zones import display_frame
from synthetic_plan import TABLE_COL_W, TABLE_ROW_H, TABLE_ROWS, RuledTable, Sheet, build_plan, two_rooms

W, H = A4
TABLE_AT = (330.0, 300.0)
TOL = 0.005


@pytest.fixture(autouse=True)
def _fresh_cache():
    tr.clear()
    yield
    tr.clear()


def _sheet(**kw) -> Sheet:
    s = two_rooms()
    s.table_at = TABLE_AT
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _pct(x0, y0, x1, y1):
    return [x0 / W, y0 / H, x1 / W, y1 / H]


def _turned(box, rotation):
    """An unrotated top-left fraction box → the display frame (cv_match._rotate_pct: mediabox → display)."""
    pts = [_rotate_pct(x, y, rotation) for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3]))]
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


def _close(got, want, tol=TOL):
    assert got is not None and all(abs(a - b) <= tol for a, b in zip(got, want)), f"{got} vs {want}"


def _only(tables):
    assert len(tables) == 1, tables
    return tables[0]


def _table_box():
    x, top = TABLE_AT
    return _pct(x, top, x + sum(TABLE_COL_W), top + len(TABLE_ROWS) * TABLE_ROW_H)


def _row_box(i):
    x, top = TABLE_AT
    return _pct(x, top + i * TABLE_ROW_H, x + sum(TABLE_COL_W), top + (i + 1) * TABLE_ROW_H)


# ── the contract ────────────────────────────────────────────────────────────


def test_a_ruled_table_is_read_with_its_header_rows_and_boxes():
    t = _only(tr.read_tables(build_plan([_sheet()]), 1))
    assert set(t) >= {"table_id", "bbox_pct", "header", "rows"}
    assert t["header"] == list(TABLE_ROWS[0]) and t["header_rows"] == 1
    assert t["title"] == "DURŲ ŽINIARAŠTIS"
    assert [r["cells"] for r in t["rows"]] == [list(r) for r in TABLE_ROWS[1:]]
    _close(t["bbox_pct"], _table_box())
    for i, row in enumerate(t["rows"], start=1):
        _close(row["bbox_pct"], _row_box(i))
        assert len(row["cell_bboxes"]) == 3
        x, top = TABLE_AT
        _close(row["cell_bboxes"][1], _pct(x + TABLE_COL_W[0], top + i * TABLE_ROW_H,
                                           x + TABLE_COL_W[0] + TABLE_COL_W[1], top + (i + 1) * TABLE_ROW_H))


def test_the_page_answer_says_ok_and_gives_the_display_size():
    res = tr.read_page_tables(build_plan([_sheet()]), 1)
    assert res["status"] == "ok" and res["detail"] is None
    assert (res["width_pt"], res["height_pt"], res["rotation"]) == pytest.approx((W, H, 0), abs=0.01)


@pytest.mark.parametrize("rotation", [90, 270])
def test_a_rotated_sheet_gives_rows_in_reading_order_and_boxes_in_the_display_frame(rotation):
    """The synthetic sheet is drawn upright under a /Rotate, so the viewer shows the table turned on its side:
    its rows are still the rows a person reads (D1, D2, D3), and every box is where the viewer shows it."""
    pdf = build_plan([_sheet(rotate=rotation)])
    W_d, H_d, rot, _ = display_frame(pdf, 1)
    assert rot == rotation and (W_d, H_d) == pytest.approx((H, W), abs=0.01)
    t = _only(tr.read_tables(pdf, 1))
    assert t["header"] == list(TABLE_ROWS[0]) and t["title"] == "DURŲ ŽINIARAŠTIS"
    assert [r["cells"] for r in t["rows"]] == [list(r) for r in TABLE_ROWS[1:]]
    assert t["text_direction"] in ("down", "up")
    _close(t["bbox_pct"], _turned(_table_box(), rotation))
    for i, row in enumerate(t["rows"], start=1):
        _close(row["bbox_pct"], _turned(_row_box(i), rotation))


def test_a_rotated_sheets_row_box_turns_back_onto_the_drawn_row_in_mediabox_points():
    """End to end: the display-frame row box, turned into the viewer's mediabox points (sheet_zones), is the row
    as drawn (the synthetic drawing coordinates ARE mediabox points)."""
    from extractor.sheet_zones import zone_to_mediabox_pt
    pdf = build_plan([_sheet(rotate=270)])
    row = _only(tr.read_tables(pdf, 1))["rows"][0]
    x, top = TABLE_AT
    want = [x, top + TABLE_ROW_H, x + sum(TABLE_COL_W), top + 2 * TABLE_ROW_H]
    assert zone_to_mediabox_pt({"bbox_pct": row["bbox_pct"]}, (W, H), 270) == pytest.approx(want, abs=1.5)


# ── tolerance ───────────────────────────────────────────────────────────────


MERGED = RuledTable(
    at=(60.0, 420.0), col_w=(40.0, 50.0, 50.0, 40.0), title="LANGŲ ŽINIARAŠTIS",
    rows=(("Žymuo", "Angos matmenys, mm", None, "Kiekis"),
          (None, "plotis", "aukštis", None),
          ("L-1", "1200", "1500", "2"),
          ("L-2", "900", "1500", "1")),
    spans=((0, 1, 2, 1), (0, 0, 1, 2), (0, 3, 1, 2)))


def test_a_merged_header_cell_gives_its_text_to_both_columns_and_a_tall_cell_is_read_once():
    t = _only(tr.read_tables(build_plan([_sheet(table_at=None, ruled_tables=[MERGED])]), 1))
    assert t["header_rows"] == 2
    assert t["header"] == ["Žymuo", "Angos matmenys, mm plotis", "Angos matmenys, mm aukštis", "Kiekis"]
    assert [r["cells"] for r in t["rows"]] == [["L-1", "1200", "1500", "2"], ["L-2", "900", "1500", "1"]]
    assert t["title"] == "LANGŲ ŽINIARAŠTIS"


def test_a_title_ruled_inside_the_table_is_its_title_not_a_header():
    tbl = RuledTable(at=(60.0, 420.0), col_w=(40.0, 60.0, 40.0),
                     rows=(("DURŲ ŽINIARAŠTIS", None, None), ("Žymuo", "Dydis", "Kiekis"), ("D1", "900x2100", "3")),
                     spans=((0, 0, 3, 1),))
    t = _only(tr.read_tables(build_plan([_sheet(table_at=None, ruled_tables=[tbl])]), 1))
    assert t["title"] == "DURŲ ŽINIARAŠTIS" and t["header"] == ["Žymuo", "Dydis", "Kiekis"]
    assert [r["cells"] for r in t["rows"]] == [["D1", "900x2100", "3"]]


def test_a_finish_schedule_keeps_its_first_room_out_of_the_header():
    """All words in every row (no number column): without a merged cell only the first row is the header."""
    tbl = RuledTable(at=(60.0, 420.0), col_w=(60.0, 50.0, 50.0, 50.0),
                     rows=(("Patalpa", "Grindys", "Sienos", "Lubos"),
                           ("Virtuvė", "Plytelės", "Dažomos", "Dažomos"),
                           ("Svetainė", "Laminatas", "Dažomos", "Dažomos")))
    t = _only(tr.read_tables(build_plan([_sheet(table_at=None, ruled_tables=[tbl])]), 1))
    assert t["header_rows"] == 1 and t["header"] == ["Patalpa", "Grindys", "Sienos", "Lubos"]
    assert [r["cells"][0] for r in t["rows"]] == ["Virtuvė", "Svetainė"]


def test_two_lines_drawn_without_a_rule_between_them_are_two_rows_with_their_own_boxes():
    tbl = RuledTable(at=(60.0, 420.0), col_w=(40.0, 60.0, 40.0), row_hs=(14.0, 22.0),
                     rows=(("Žymuo", "Dydis", "Kiekis"), ("D1\nD2", "900x2100\n800x2100", "3\n2")))
    t = _only(tr.read_tables(build_plan([_sheet(table_at=None, ruled_tables=[tbl])]), 1))
    assert [r["cells"] for r in t["rows"]] == [["D1", "900x2100", "3"], ["D2", "800x2100", "2"]]
    a, b = (r["bbox_pct"] for r in t["rows"])
    assert all(r["split"] is True for r in t["rows"])
    assert a[3] <= b[1] + 1e-6 and a[1] >= 434.0 / H - TOL and b[3] <= 456.0 / H + TOL


def test_a_wrapped_cell_is_one_row_not_two():
    tbl = RuledTable(at=(60.0, 420.0), col_w=(40.0, 90.0), row_hs=(14.0, 22.0),
                     rows=(("Kodas", "Durų tipas"), ("D-1", "Dešininės,\nbeapvadinės")))
    t = _only(tr.read_tables(build_plan([_sheet(table_at=None, ruled_tables=[tbl])]), 1))
    assert [r["cells"] for r in t["rows"]] == [["D-1", "Dešininės, beapvadinės"]] and t["rows"][0]["split"] is False


def test_a_last_row_ruled_apart_continues_the_table():
    pdf = build_plan([_sheet(table_tail_rows=(("D4", "600x2100", "1"),))])
    t = _only(tr.read_tables(pdf, 1))
    assert t["pieces"] == 2 and [r["cells"][0] for r in t["rows"]] == ["D1", "D2", "D3", "D4"]


def test_a_grid_of_dimension_numbers_is_not_a_table():
    grid = RuledTable(at=(60.0, 420.0), col_w=(40.0, 40.0, 40.0),
                      rows=(("1200", "900", "450"), ("300", "2100", "600"), ("125", "80", "15")))
    res = tr.read_page_tables(build_plan([_sheet(table_at=None, ruled_tables=[grid])]), 1)
    assert res["tables"] == [] and any("matmenys" in s["reason"] for s in res["skipped"])


def test_dimension_strings_caught_in_a_ruled_box_are_not_a_table():
    soup = RuledTable(at=(60.0, 420.0), col_w=(80.0, 80.0),
                      rows=(("1189 009 VONIA 0001", "397 500 600 136"), ("0821 0001 1384 500", "SIENA 2000 1597 12"),
                            ("700 150 200", "Spinta")))
    res = tr.read_page_tables(build_plan([_sheet(table_at=None, ruled_tables=[soup])]), 1)
    assert res["tables"] == [] and any("matmenų skaičiai" in s["reason"] for s in res["skipped"])


# ── honest answers ──────────────────────────────────────────────────────────


def _lines_only_pdf() -> bytes:
    """A sheet with a ruled grid and no text layer — a scanned table, as far as the reader can tell."""
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for i in range(5):
        c.line(100, 700 - i * 14, 300, 700 - i * 14)
    for x in (100, 160, 220, 300):
        c.line(x, 700, x, 644)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_a_sheet_without_a_text_layer_says_so_and_guesses_nothing():
    res = tr.read_page_tables(_lines_only_pdf(), 1)
    assert res["status"] == "no_text" and res["tables"] == [] and "teksto" in res["detail"]


def test_a_page_past_the_end_is_no_page():
    res = tr.read_page_tables(build_plan([_sheet()]), 3)
    assert res["status"] == "no_page" and res["tables"] == []


def test_a_sheet_drawing_too_many_objects_is_not_laid_out_and_says_so():
    res = tr.read_page_tables(build_plan([_sheet()]), 1, max_objects=1)
    assert res["status"] == "too_heavy" and res["tables"] == [] and "per daug" in res["detail"]


def test_a_second_read_of_the_same_page_is_cached(monkeypatch):
    pdf = build_plan([_sheet()])
    first = tr.read_page_tables(pdf, 1)
    import pdfplumber

    def boom(*a, **k):
        raise AssertionError("opened again")
    monkeypatch.setattr(pdfplumber, "open", boom)
    assert tr.read_page_tables(pdf, 1) == first


def test_several_pages_are_read_in_one_open():
    s2 = _sheet(table_at=(60.0, 500.0))
    res = tr.read_pages_tables(build_plan([_sheet(), s2]), [1, 2])
    assert sorted(res) == [1, 2] and all(len(r["tables"]) == 1 for r in res.values())
    assert res[2]["tables"][0]["table_id"] == "p2-t1"


def test_no_model_is_called(monkeypatch):
    import anthropic

    def boom(*a, **k):
        raise AssertionError("a model was called")
    monkeypatch.setattr(anthropic, "Anthropic", boom)
    assert tr.read_tables(build_plan([_sheet()]), 1)


def test_is_data_cell_tells_values_from_headings():
    for v in ("910", "2,10 m", "125+15*", "D-1", "L2", "VD-3", "01", "900x2100"):
        assert tr.is_data_cell(v), v
    for v in ("Kodas", "Angos plotis, mm", "m²", "", "Durų tipas"):
        assert not tr.is_data_cell(v), v

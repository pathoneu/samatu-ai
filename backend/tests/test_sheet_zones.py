"""extractor/sheet_zones.py on synthetic sheets (tests/synthetic_plan.py — invented drawings, no client data).

Every zone box is predicted from what the synthetic sheet draws and must land within 2 % of the page
(the wave-1 plan's tolerance), in the PDFium display frame.
"""
from __future__ import annotations

import threading

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth

from extractor import sheet_zones as sz
from extractor.cv_match import _rotate_pct
from synthetic_plan import (
    LEGEND_HEADING, LEGEND_ROWS, LEGEND_TEXT_DX, LT_FONT, NOTES_LINES, NOTES_STEP, ORIGIN, PT_PER_M,
    TABLE_COL_W, TABLE_ROW_H, TABLE_ROWS, TITLE_BLOCK_BOX, Sheet, build_plan, two_rooms,
)

W, H = A4
TOL = 0.02

LEGEND_AT = (330.0, 100.0)
TABLE_AT = (330.0, 300.0)
NOTES_AT = (60.0, 450.0)


@pytest.fixture(autouse=True)
def _fresh_cache():
    sz.clear()
    yield
    sz.clear()


def _full_sheet(**kw) -> Sheet:
    s = two_rooms()
    s.legend_block_at = LEGEND_AT
    s.table_at = TABLE_AT
    s.title_block = "P-01-SA.BR"
    s.notes_at = NOTES_AT
    for k, v in kw.items():
        setattr(s, k, v)
    return s


def _pct(x0, y0, x1, y1, w=W, h=H):
    return [x0 / w, y0 / h, x1 / w, y1 / h]


def _close(got, want, tol=TOL):
    assert all(abs(a - b) <= tol for a, b in zip(got, want)), f"{got} vs {want}"


def _one(zones, kind):
    hits = [z for z in zones if z["kind"] == kind]
    assert len(hits) == 1, f"{kind}: {hits} in {zones}"
    return hits[0]


def _plan_box(offset_y_m: float = 0.0):
    t = 0.2
    x0, y0 = ORIGIN[0], ORIGIN[1] + offset_y_m * PT_PER_M
    return _pct(x0, y0, x0 + (7 + 3 * t) * PT_PER_M, y0 + (3 + 2 * t) * PT_PER_M)


def _legend_box():
    x, top = LEGEND_AT
    right = max(x + stringWidth(LEGEND_HEADING, LT_FONT, 6),
                max(x + LEGEND_TEXT_DX + stringWidth(t, LT_FONT, 5) for t in LEGEND_ROWS))
    return _pct(x, top, right, top + 12 + 2 * 12 + 6)


def _table_box():
    x, top = TABLE_AT
    return _pct(x, top, x + sum(TABLE_COL_W), top + len(TABLE_ROWS) * TABLE_ROW_H)


def _notes_box():
    x, top = NOTES_AT
    right = max(x + stringWidth(t, LT_FONT, 5) for t in NOTES_LINES)
    return _pct(x, top, right, top + 6 + len(NOTES_LINES) * NOTES_STEP + 1.5)


# ── the full sheet ──────────────────────────────────────────────────────────

def test_every_zone_kind_is_found_where_it_is_drawn():
    pdf = build_plan([_full_sheet()])
    res = sz.read_zones(pdf, 1)
    assert res["status"] == "ok" and res["detail"] is None
    zones = res["zones"]
    kinds = sorted(z["kind"] for z in zones)
    assert kinds == ["antspaudas", "legenda", "lentele", "pastabos", "planas"], zones

    plan = _one(zones, "planas")
    _close(plan["bbox_pct"], _plan_box())
    assert plan["confidence"] == "read" and plan["evidence"]["source"] == "vektoriai"

    legend = _one(zones, "legenda")
    _close(legend["bbox_pct"], _legend_box())
    assert legend["label"] == LEGEND_HEADING.rstrip(":")
    assert legend["confidence"] == "read" and legend["evidence"]["source"] == "vektoriai"
    assert "3 eil." in legend["evidence"]["detail"]          # coloured square, hairline circle, black cross

    table = _one(zones, "lentele")
    _close(table["bbox_pct"], _table_box(), tol=0.005)
    assert table["label"] == "DURŲ ŽINIARAŠTIS"
    assert table["evidence"]["source"] == "lentele"

    stamp = _one(zones, "antspaudas")
    _close(stamp["bbox_pct"], _pct(*TITLE_BLOCK_BOX), tol=0.005)
    assert stamp["label"] == "SA" and stamp["confidence"] == "read"

    notes = _one(zones, "pastabos")
    _close(notes["bbox_pct"], _notes_box())
    assert notes["label"] == "PASTABOS" and notes["confidence"] == "read"


def test_zone_shape_is_the_contract():
    zones = sz.detect_zones(build_plan([_full_sheet()]), 1)
    for z in zones:
        assert set(z) == {"kind", "bbox_pct", "label", "confidence", "evidence"}
        assert z["kind"] in sz.KINDS
        assert z["confidence"] in ("read", "assumed")
        assert set(z["evidence"]) == {"source", "detail"} and z["evidence"]["source"] in sz.SOURCES
        x0, y0, x1, y1 = z["bbox_pct"]
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
        assert isinstance(z["evidence"]["detail"], str) and z["evidence"]["detail"]


def test_a_sheet_without_a_legend_has_no_legend_zone():
    zones = sz.detect_zones(build_plan([_full_sheet(legend_block_at=None)]), 1)
    assert not [z for z in zones if z["kind"] == "legenda"]
    assert {"planas", "lentele", "antspaudas"} <= {z["kind"] for z in zones}


def test_the_title_block_is_found_at_the_standard_position():
    s = two_rooms()
    s.title_block = "P-01-SA.BR"
    stamp = _one(sz.detect_zones(build_plan([s]), 1), "antspaudas")
    _close(stamp["bbox_pct"], _pct(*TITLE_BLOCK_BOX), tol=0.005)
    assert "SA" in stamp["evidence"]["detail"]


def test_a_legend_heading_with_no_glyph_rows_is_kita_not_a_legend():
    zones = sz.detect_zones(build_plan([_full_sheet(legend_glyphs=False)]), 1)
    assert not [z for z in zones if z["kind"] == "legenda"]
    other = _one(zones, "kita")
    assert other["confidence"] == "assumed"
    assert "0 eil. su ženklu" in other["evidence"]["detail"]


def test_the_room_table_is_a_table_not_a_legend():
    rows = (("Nr.", "Pavadinimas", "Plotas, m²"), ("1", "Kambarys", "12,00"), ("2", "Virtuvė", "9,00"), ("3", "Vonia", "4,50"))
    zones = sz.detect_zones(build_plan([_full_sheet(legend_block_at=None, table_title="PATALPŲ EKSPLIKACIJA",
                                                    table_rows=rows)]), 1)
    table = _one(zones, "lentele")
    assert table["label"] == "PATALPŲ EKSPLIKACIJA"
    assert not [z for z in zones if z["kind"] == "legenda"]


def test_a_table_whose_header_names_the_marks_is_a_legend():
    rows = (("Žymėjimas", "Pavadinimas", "Kiekis"), ("A", "Šviestuvas", "4"), ("B", "Rozetė", "6"), ("C", "Jungiklis", "3"))
    zones = sz.detect_zones(build_plan([_full_sheet(legend_block_at=None, table_title="ELEKTROS TAŠKAI",
                                                    table_rows=rows)]), 1)
    legend = _one(zones, "legenda")
    _close(legend["bbox_pct"], _table_box(), tol=0.005)
    assert legend["evidence"]["source"] == "lentele"
    assert not [z for z in zones if z["kind"] == "lentele"]


def test_two_plan_viewports_on_one_sheet_are_two_plan_zones():
    a = two_rooms()
    b = two_rooms()
    s = Sheet(walls=a.walls + [(x0, y0 + 6, x1, y1 + 6) for x0, y0, x1, y1 in b.walls],
              badges=a.badges, dims=a.dims,
              texts=[("1 AUKŠTO PLANAS", 2.0, 4.2, (0, 0, 0)), ("2 AUKŠTO PLANAS", 2.0, 10.2, (0, 0, 0))])
    plans = sorted((z for z in sz.detect_zones(build_plan([s]), 1) if z["kind"] == "planas"),
                   key=lambda z: z["bbox_pct"][1])
    assert len(plans) == 2, plans
    _close(plans[0]["bbox_pct"], _plan_box())
    _close(plans[1]["bbox_pct"], _plan_box(6.0))
    assert [p["label"] for p in plans] == ["1 AUKŠTO PLANAS", "2 AUKŠTO PLANAS"]


def test_a_sheet_without_text_and_walls_answers_no_zones_and_says_why():
    s = Sheet(title="")                                    # nothing drawn at all: a scan's page has no text layer
    res = sz.read_zones(build_plan([s]), 1)
    assert res["zones"] == [] and res["status"] == "no_text"
    assert res["detail"] == sz.NO_TEXT == "nėra teksto sluoksnio"
    assert sz.detect_zones(build_plan([s]), 1) == []


def test_a_page_past_the_end_is_no_page():
    res = sz.read_zones(build_plan([two_rooms()]), 3)
    assert res["status"] == "no_page" and res["zones"] == []


# ── frames ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rotation", [90, 270])
def test_a_rotated_sheet_gives_zones_in_the_display_frame(rotation):
    """/Rotate 90 or 270 (objektas_a's sheets: 270): the table pdfplumber finds and the plan PDFium reads both
    land where the viewer shows them."""
    s = _full_sheet(legend_block_at=None, notes_at=None, title_block=None, rotate=rotation)
    res = sz.read_zones(build_plan([s]), 1)
    assert (res["width_pt"], res["height_pt"]) == pytest.approx((H, W), abs=0.01) and res["rotation"] == rotation

    def turned(box):            # an unrotated top-left box → the display frame (cv_match: mediabox → display)
        pts = [_rotate_pct(x, y, rotation) for x, y in ((box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3]))]
        return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]

    _close(_one(res["zones"], "lentele")["bbox_pct"], turned(_table_box()), tol=0.005)
    _close(_one(res["zones"], "planas")["bbox_pct"], turned(_plan_box()))


def test_zone_at_prefers_the_specific_zone():
    zones = [{"kind": "planas", "bbox_pct": [0.0, 0.0, 1.0, 1.0]},
             {"kind": "legenda", "bbox_pct": [0.5, 0.5, 0.7, 0.7]}]
    assert sz.zone_at(zones, 0.6, 0.6)["kind"] == "legenda"
    assert sz.zone_at(zones, 0.2, 0.2)["kind"] == "planas"
    assert sz.zone_at(zones[1:], 0.2, 0.2) is None


# ── cost and safety ─────────────────────────────────────────────────────────

def test_a_second_read_of_the_same_page_is_cached(monkeypatch):
    pdf = build_plan([_full_sheet()])
    calls = []
    real = sz._detect
    monkeypatch.setattr(sz, "_detect", lambda b, p, cap=None: calls.append(p) or real(b, p, cap))
    first = sz.read_zones(pdf, 1)
    second = sz.read_zones(pdf, 1)
    assert calls == [1] and first == second


def test_pdfium_is_read_only_under_the_process_lock():
    from extractor.pdfium_guard import PDFIUM_LOCK
    pdf = build_plan([_full_sheet()])
    done = threading.Event()
    t = threading.Thread(target=lambda: (sz.read_zones(pdf, 1), done.set()))
    with PDFIUM_LOCK:
        t.start()
        assert not done.wait(1.0), "zones were read while another thread held PDFIUM_LOCK"
    t.join(30)
    assert done.is_set()


def test_no_model_is_called(monkeypatch):
    import anthropic

    class _Boom:
        def __init__(self, *a, **kw):
            raise AssertionError("sheet zones reached the Anthropic client")
    monkeypatch.setattr(anthropic, "Anthropic", _Boom)
    assert sz.detect_zones(build_plan([_full_sheet()]), 1)


def test_zones_for_pages_is_the_stored_shape():
    pdf = build_plan([_full_sheet(), Sheet(title="")])
    out = sz.zones_for_pages(pdf, [2, 1, 1])
    assert list(out) == ["1", "2"]
    assert out["2"] == [] and out["1"]


# ── shapes the corpus showed (2026-10-18 report, scripts/sheet_zones_report.py) ─────────────────────

def test_a_legend_whose_symbols_stand_in_a_column_right_of_the_text():
    """objektas_g's electrical legend: „El. taškas | Žymėjimas" — the text first, the symbol column after it."""
    from synthetic_plan import LEGEND_COLUMN_DX
    legend = _one(sz.detect_zones(build_plan([_full_sheet(legend_style="column")]), 1), "legenda")
    x, top = LEGEND_AT
    _close(legend["bbox_pct"], _pct(x, top, x + LEGEND_COLUMN_DX + 6, top + 42))
    assert "3 eil." in legend["evidence"]["detail"]


def test_a_legend_of_material_swatches():
    """objektas_d's ceiling legend: a grey box per finish (92 × 31 pt there), the text right of it."""
    from synthetic_plan import SWATCH, SWATCH_TEXT_DX
    legend = _one(sz.detect_zones(build_plan([_full_sheet(legend_style="swatches")]), 1), "legenda")
    x, top = LEGEND_AT
    right = max(x + stringWidth(LEGEND_HEADING, LT_FONT, 6),
                max(x + SWATCH_TEXT_DX + stringWidth(t, LT_FONT, 5) for t in LEGEND_ROWS))
    _close(legend["bbox_pct"], _pct(x, top, right, top + 12 + 2 * 12 + 3 + SWATCH[1] / 2))
    assert "3 eil." in legend["evidence"]["detail"]


def test_a_table_whose_first_row_has_no_word_is_not_a_table():
    """Walls drawn as boxes with their dimensions in them (objektas_h p1: a „table" headed by numbers)."""
    rows = (("4000", "3000", "2000"), ("150", "1200", "900"), ("300", "600", "450"), ("120", "80", "60"))
    zones = sz.detect_zones(build_plan([_full_sheet(table_rows=rows, table_title="")]), 1)
    assert not [z for z in zones if z["kind"] == "lentele"]


def test_a_reader_in_another_frame_than_the_page_is_not_used(monkeypatch):
    """objektas_e: the wall reader (and the character reader) settle their frame from where the content lies;
    on a /Rotate 270 sheet whose content does not prove it they end up turned. Zones are never placed from a
    frame that disagrees with the page's real one — the answer says so instead."""
    from extractor import pdf_vectors
    pdf = build_plan([_full_sheet()])
    real = pdf_vectors.page_geometry
    monkeypatch.setattr(pdf_vectors, "page_geometry", lambda b, p: (lambda w, h, r: (h, w, r))(*real(b, p)))
    res = sz.read_zones(pdf, 1)
    assert not [z for z in res["zones"] if z["kind"] == "planas"]
    assert "sienų brėžinio rėmas nesutampa" in res["detail"]
    assert {"legenda", "lentele", "antspaudas"} <= {z["kind"] for z in res["zones"]}    # the text still reads


def test_a_text_direction_in_another_frame_is_not_used(monkeypatch):
    from extractor import plan_area_annotations as paa
    pdf = build_plan([_full_sheet()])
    real = paa._iter_pages

    def turned(b, pages):
        for pn, W_, H_, chars, to_display in real(b, pages):
            yield pn, H_, W_, chars, to_display
    monkeypatch.setattr(paa, "_iter_pages", turned)
    res = sz.read_zones(pdf, 1)
    assert "teksto lapo rėmas nesutampa" in res["detail"]
    assert not [z for z in res["zones"] if z["kind"] in ("legenda", "pastabos", "antspaudas")]
    _close(_one(res["zones"], "planas")["bbox_pct"], _plan_box())           # the walls still read


def test_a_sheet_too_heavy_to_lay_out_skips_tables_and_says_so(monkeypatch):
    monkeypatch.setattr(sz, "TABLE_MAX_OBJECTS", 10)
    res = sz.read_zones(build_plan([_full_sheet()]), 1)
    assert not [z for z in res["zones"] if z["kind"] == "lentele"]
    assert "lentelių neieškota" in res["detail"]
    assert _one(res["zones"], "legenda")                                    # what needs no table still reads


def test_three_short_lines_without_a_heading_are_not_notes():
    s = two_rooms()
    s.texts = [("Laidas išvedamas iš lubų", 9.0, 1.0, (0, 0, 0)),
               ("Jungiklis montuojamas į baldą", 9.0, 1.3, (0, 0, 0)),
               ("Apšvietimas jungiamas su jungtuku", 9.0, 1.6, (0, 0, 0))]
    assert not [z for z in sz.detect_zones(build_plan([s]), 1) if z["kind"] == "pastabos"]


def test_zone_at_takes_a_legend_inside_the_title_band():
    zones = [{"kind": "antspaudas", "bbox_pct": [0.0, 0.7, 1.0, 1.0]},
             {"kind": "legenda", "bbox_pct": [0.6, 0.75, 0.8, 0.9]},
             {"kind": "planas", "bbox_pct": [0.5, 0.5, 0.9, 0.95]}]
    assert sz.zone_at(zones, 0.7, 0.8)["kind"] == "legenda"
    assert sz.zone_at(zones, 0.2, 0.8)["kind"] == "antspaudas"
    assert sz.zone_at(zones, 0.6, 0.6)["kind"] == "planas"


def test_a_legend_table_takes_the_row_ruled_apart_under_it():
    """objektas_h p2: „SUTARTINIAI ŽYMĖJIMAI:" over a ruled table whose last row („T Termostatas") is a
    separate ruled piece a point below — one legend, all its rows."""
    rows = (("Žymėjimas", "Pavadinimas", "Kiekis"), ("A", "Interneto lizdas", "2"), ("B", "Rozetė", "6"), ("C", "Jungiklis", "3"))
    s = _full_sheet(legend_block_at=None, table_title=LEGEND_HEADING, table_rows=rows,
                    table_tail_rows=(("T", "Termostatas", "1"),))
    legend = _one(sz.detect_zones(build_plan([s]), 1), "legenda")
    x, top = TABLE_AT
    _close(legend["bbox_pct"], _pct(x, top - 8, x + sum(TABLE_COL_W), top + 5 * TABLE_ROW_H + 4.5), tol=0.005)
    assert "5 eil." in legend["evidence"]["detail"]
    assert not [z for z in sz.detect_zones(build_plan([s]), 1) if z["kind"] == "lentele"]


# ── frames: a zone in the viewer's measurement space (E4) ───────────────────

@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_zone_to_mediabox_pt_inverts_the_viewer_turn(rotation):
    """cv_match._rotate_pct turns mediabox fractions into display fractions; zone_to_mediabox_pt is its
    inverse, in mediabox points from the top-left (cv_tools `box_pt`)."""
    Wm, Hm = 595.0, 842.0
    box_m = [100.0, 200.0, 250.0, 260.0]                  # mediabox points, top-left origin
    pts = [_rotate_pct(x / Wm, y / Hm, rotation) for x, y in
           ((box_m[0], box_m[1]), (box_m[2], box_m[1]), (box_m[0], box_m[3]), (box_m[2], box_m[3]))]
    zone = {"bbox_pct": [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]}
    assert sz.zone_to_mediabox_pt(zone, (Wm, Hm), rotation) == pytest.approx(box_m, abs=0.02)


@pytest.mark.parametrize("rotation", [90, 270])
def test_a_rotated_sheets_table_zone_lands_on_the_table_in_mediabox_points(rotation):
    """End to end on a /Rotate sheet: the table zone, turned into mediabox points, is the box the table was
    drawn at (the synthetic sheet is drawn unrotated, so its drawing coordinates ARE mediabox points)."""
    s = _full_sheet(legend_block_at=None, notes_at=None, title_block=None, rotate=rotation)
    res = sz.read_zones(build_plan([s]), 1)
    table = _one(res["zones"], "lentele")
    x, top = TABLE_AT
    want = [x, top, x + sum(TABLE_COL_W), top + len(TABLE_ROWS) * TABLE_ROW_H]
    assert sz.zone_to_mediabox_pt(table, (W, H), res["rotation"]) == pytest.approx(want, abs=3.0)

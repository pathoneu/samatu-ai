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
    monkeypatch.setattr(sz, "_detect", lambda b, p: calls.append(p) or real(b, p))
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

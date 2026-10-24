"""OCR wired into the readers (v4, flag SAMATU_OCR): a sheet with no text layer gets a scale, room badges and a room
table (docs/superpowers/research/2026-10-24-ocr-wiring.md). Every sheet is synthetic, drawn in the test; the OCR is
a stand-in that returns what the drawing's own text layer would say, so no engine is needed (the real engine has
its own test in test_text_ocr.py).
"""
from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import numpy as np
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

import text.ocr as ocr
from geometry import scale as S
from geometry.provenance import LOW, MEDIUM, PT_M, ScaleSource
from geometry.scale import ScaleContext, scale_for_page
from text.ocr import Word
from text.raster_lines import dimension_lines

W, H = A4
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMATU_OCR_CACHE_DIR", str(tmp_path / "ocr_cache"))
    ocr._cache.clear()
    yield
    ocr._cache.clear()


# ── sheets: the same drawing with and without its text ──────────────────────

from tests.test_geometry_scale import _pdf, _sheet  # noqa: E402 — six rooms in one block, strings across each room


class _NoText:
    """A canvas that draws everything but text: the sheet as it looks when its letters are outlines or pixels."""

    def __init__(self, c):
        self._c = c

    def __getattr__(self, name):
        if name in ("drawString", "drawCentredString", "drawRightString"):
            return lambda *a, **k: None
        return getattr(self._c, name)


def _twin(denom: float, *, units: str = "mm"):
    """(the sheet with walls and dimension HAIRLINES but no text, OCR's strings in mm, OCR's strings in cm)."""
    from extractor.plan_dimensions import _value_cm, read_dimension_strings
    draw = _sheet(denom, hairlines=True, units=units, walls="stroke")
    with_text = _pdf(draw)
    blank = _pdf(lambda c: draw(_NoText(c)))
    keep = ("page", "text", "bbox", "page_width", "page_height", "orientation")
    from extractor.plan_area_annotations import _iter_pages
    from extractor.plan_dimensions import _dimensions_on_page
    mm, cm = [], []
    for pn, Wd, Hd, chars, td in _iter_pages(with_text, None):
        for d in _dimensions_on_page(pn, Wd, Hd, chars, td):
            mm.append({k: d[k] for k in keep} | {"value_m": d["value_m"], "source": "ocr"})
        for d in _dimensions_on_page(pn, Wd, Hd, chars, td, units="cm"):
            cm.append({k: d[k] for k in keep} | {"value_m": d["value_m"], "source": "ocr", "units": "cm"})
    assert not [d for d in read_dimension_strings(blank)]          # the blank twin really has no text
    assert _value_cm("360") == 3.6
    return blank, mm, cm


def _fake_strings(monkeypatch, mm, cm, stated=frozenset()):
    calls = []

    def fake(pdf, page, *a, units="mm", **k):
        calls.append((page, units))
        src = cm if units == "cm" else mm
        return [dict(d) for d in src if d["page"] == page], set(stated)
    monkeypatch.setattr(ocr, "dimension_strings", fake)
    monkeypatch.setattr(ocr, "detail_scales", lambda *a, **k: set())
    return calls


# ── scale: OCR'd strings on their lines ─────────────────────────────────────

def test_ocr_strings_on_drawn_dimension_lines_give_the_measured_scale(monkeypatch):
    blank, mm, cm = _twin(50)
    monkeypatch.setenv("SAMATU_OCR", "1")
    _fake_strings(monkeypatch, mm, cm)
    sc = scale_for_page(ScaleContext(blank), 1)
    assert sc.source == ScaleSource.DIMENSION_LINES and sc.confidence == MEDIUM
    assert sc.m_per_pt / PT_M == pytest.approx(50, rel=0.01)
    assert "skaičiai perskaityti iš lapo vaizdo" in sc.source_text and sc.details["ocr"] is True
    assert sc.details["units"] == "mm" and sc.details["agree"] >= 5


def test_a_written_scale_the_strings_contradict_is_marked_and_the_measurement_wins(monkeypatch):
    """objektas_c: writes M 1:50, its strings measure ≈ 1:60 (a reduced print)."""
    blank, mm, cm = _twin(60)
    monkeypatch.setenv("SAMATU_OCR", "1")
    _fake_strings(monkeypatch, mm, cm, stated={50})
    sc = scale_for_page(ScaleContext(blank), 1)
    assert sc.source == ScaleSource.DIMENSION_LINES
    assert sc.m_per_pt / PT_M == pytest.approx(60, rel=0.01)
    assert "užrašytas mastelis neatitinka matmenų (≈ 1:60)" in sc.source_text
    assert "1:50" in sc.reason and sc.details["stated"] == [50]


def test_a_written_scale_the_strings_confirm_is_used_exactly(monkeypatch):
    blank, mm, cm = _twin(50)
    monkeypatch.setenv("SAMATU_OCR", "1")
    _fake_strings(monkeypatch, mm, cm, stated={50})
    sc = scale_for_page(ScaleContext(blank), 1)
    assert sc.m_per_pt == pytest.approx(50 * PT_M) and "sutampa su užrašytu M 1:50" in sc.source_text


def test_strings_in_centimetres_are_read_as_such_when_millimetres_give_no_plan_scale(monkeypatch):
    """objektas_j4: „173", „80" … in cm; as mm they measure 1:10 — no plan's scale — as cm 1:100."""
    blank, mm, cm = _twin(100, units="cm")
    monkeypatch.setenv("SAMATU_OCR", "1")
    _fake_strings(monkeypatch, mm, cm)
    sc = scale_for_page(ScaleContext(blank), 1)
    assert sc.source == ScaleSource.DIMENSION_LINES and sc.details["units"] == "cm"
    assert sc.m_per_pt / PT_M == pytest.approx(100, rel=0.01)
    assert "matmenys centimetrais" in sc.source_text


def test_a_sheet_writing_a_detail_scale_is_never_read_in_centimetres(monkeypatch):
    blank, mm, cm = _twin(100, units="cm")
    monkeypatch.setenv("SAMATU_OCR", "1")
    _fake_strings(monkeypatch, mm, cm)
    monkeypatch.setattr(ocr, "detail_scales", lambda *a, **k: {10})
    sc = scale_for_page(ScaleContext(blank), 1)
    assert not (sc.found and sc.source == ScaleSource.DIMENSION_LINES)


def test_few_strings_on_lines_measure_nothing(monkeypatch):
    """Four strings agreeing is chance on a busy sheet (objektas_c sheet 2 found 1:43 that way): no scale."""
    blank, mm, cm = _twin(60)
    monkeypatch.setenv("SAMATU_OCR", "1")
    _fake_strings(monkeypatch, mm[:3], [], stated={50})
    sc = scale_for_page(ScaleContext(blank), 1)
    assert sc.source == ScaleSource.STATED and sc.confidence == LOW        # the written scale, unconfirmed


def _cand(scale, support, rival, values, props=()):
    return {"scale": scale * PT_M, "support": support, "rival": rival, "values": values, "in_range": True,
            "props": list(props), "idx": [], "lines": "raster"}


def test_the_contradiction_rule_takes_the_densest_measurement_and_nothing_weaker():
    """objektas_j3 (a scan of a reduced print): writes 1:40, ten strings say ≈ 1:64, a rival five say ≈ 1:68."""
    assert S._ocr_contradicts(_cand(64, 10, 5, 7), [40])
    assert not S._ocr_contradicts(_cand(64, 4, 1, 4), [40])          # too few strings
    assert not S._ocr_contradicts(_cand(64, 6, 6, 5), [40])          # not the densest
    assert not S._ocr_contradicts(_cand(41.5, 10, 2, 7), [40])       # within 5 % of the written scale
    assert not S._ocr_contradicts(_cand(64, 10, 2, 7), [])           # nothing written to contradict
    backing = [(40 * PT_M, i) for i in range(6)]                       # six strings measure the written scale
    assert not S._ocr_contradicts(_cand(64, 10, 2, 7, backing), [40])
    assert not S._ocr_strong(_cand(64, 10, 5, 7))                     # j3 is not a strong measurement on its own


def test_flag_off_the_line_match_never_runs(monkeypatch):
    monkeypatch.delenv("SAMATU_OCR", raising=False)
    blank, mm, cm = _twin(50)
    calls = _fake_strings(monkeypatch, mm, cm)
    sc = scale_for_page(ScaleContext(blank), 1)
    assert calls == [] and not (sc.found and sc.source == ScaleSource.DIMENSION_LINES)


# ── dimension lines read off the render ─────────────────────────────────────

def _canvas(w=600, h=300):
    return np.full((h, w, 3), 255, dtype=np.uint8)


BLUE, RED, GREY = (20, 120, 200), (210, 40, 40), (190, 190, 190)


def test_a_rendered_dimension_line_is_cut_at_its_ticks_not_at_a_line_of_another_colour():
    img = _canvas()
    img[200:202, 100:401] = BLUE                     # the dimension line, 2 px
    for x in (100, 400):
        img[190:212, x:x + 2] = BLUE                 # its ticks
    img[100:300, 160:162] = RED                      # a red reference line crossing it
    s = {"bbox": [230, 185, 270, 197], "orientation": "h"}
    lines = dimension_lines(img, 1.0, [s])
    assert len(lines["h"]) == 1
    a0, a1, y, t = lines["h"][0]
    assert a0 == pytest.approx(100.5, abs=1) and a1 == pytest.approx(400.5, abs=1) and y == pytest.approx(200.5, abs=1)
    assert t == 0.0


def test_a_rendered_line_running_into_a_light_wall_fill_ends_there_and_walls_are_not_lines():
    img = _canvas()
    img[150:154, 50:500] = (0, 0, 0)                  # a wall stroke: thicker than a dimension line at 1 pt/px? no: 4 px
    img[200:201, 120:380] = (0, 0, 0)                 # a dimension line ending in…
    img[180:220, 380:420] = GREY                      # …a light grey wall fill (not ink)
    s = {"bbox": [230, 188, 270, 198], "orientation": "h"}
    (a0, a1, _y, _t), = dimension_lines(img, 1.0, [s])["h"]
    assert a0 == pytest.approx(120, abs=1) and a1 == pytest.approx(379, abs=1)
    thick = _canvas()
    thick[200:206, 120:380] = (0, 0, 0)              # 6 px = 6 pt at 1 pt/px: a wall, not a dimension line
    assert dimension_lines(thick, 1.0, [s])["h"] == []


def test_a_vertical_string_gets_its_vertical_line():
    img = _canvas(300, 600)
    img[100:401, 200:202] = BLUE
    for y in (100, 400):
        img[y:y + 2, 190:212] = BLUE
    s = {"bbox": [185, 230, 197, 270], "orientation": "v"}
    (a0, a1, x, _t), = dimension_lines(img, 1.0, [s])["v"]
    assert a0 == pytest.approx(100.5, abs=1) and a1 == pytest.approx(400.5, abs=1) and x == pytest.approx(200.5, abs=1)


# ── OCR boxes cut to their ink; the disk cache ──────────────────────────────

def test_a_padded_ocr_box_is_cut_to_its_ink_and_a_line_through_the_padding_is_not_ink():
    img = _canvas(200, 100)
    img[40:52, 50:70] = 0                            # the glyphs
    img[55, 30:120] = 0                              # a dimension line passing through the padding
    w = ocr._tighten(Word("12", 45, 35, 75, 57, 0.99, 0), img, 1.0, 1.0)
    assert (w.x0, w.y0, w.x1, w.y1) == (50, 40, 70, 52)
    blank = ocr._tighten(Word("12", 45, 35, 75, 57, 0.99, 0), _canvas(200, 100), 1.0, 1.0)
    assert (blank.x0, blank.y1) == (45, 57)          # nothing to cut to: the box as read
    tight = _canvas(200, 100)
    tight[40:52, 50:52] = 0                          # „1": a stroke as tall as the box …
    tight[40:52, 56:66] = 0                          # … then „0"
    t = ocr._tighten(Word("10", 50, 40, 66, 52, 0.99, 0), tight, 1.0, 1.0)
    assert (t.x0, t.x1) == (50, 66)                  # a digit's own stroke is not a line crossing the word


class _CountingEngine:
    name = "counting"

    def __init__(self):
        self.calls = 0

    def read(self, rgb):
        self.calls += 1
        return [ocr.Line("4280", [[10, 10], [60, 10], [60, 22], [10, 22]], 0.99)]


def _one_page_pdf() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.rect(100, 100, 300, 200)
    c.showPage()
    c.save()
    return buf.getvalue()


def test_a_sheet_is_ocrd_once_and_read_from_disk_after(monkeypatch, tmp_path):
    eng = _CountingEngine()
    monkeypatch.setattr(ocr, "_engine_tag", lambda e: "rapid-test")
    pdf = _one_page_pdf()
    first = ocr.ocr_page(pdf, 1, dpi=72, engine=eng, rotations=(0,))
    assert eng.calls == 1
    ocr._cache.clear()                                # a new process: only the disk remains
    again = ocr.ocr_page(pdf, 1, dpi=72, engine=eng, rotations=(0,))
    assert eng.calls == 1 and again == first
    files = list((tmp_path / "ocr_cache").rglob("*.json"))
    assert len(files) == 1
    ocr._cache.clear()
    ocr.ocr_page(pdf, 1, dpi=100, engine=eng, rotations=(0,))   # another DPI is another read
    assert eng.calls == 2


def test_a_test_engine_is_never_cached_on_disk(tmp_path):
    ocr.ocr_page(_one_page_pdf(), 1, dpi=72, engine=_CountingEngine(), rotations=(0,))
    assert not list((tmp_path / "ocr_cache").rglob("*.json"))


# ── the models: from the image, never downloaded in production ──────────────

def test_production_refuses_to_download_models(monkeypatch, tmp_path):
    pytest.importorskip("rapidocr")
    monkeypatch.setenv("SAMATU_OCR_MODEL_DIR", str(tmp_path / "empty"))
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(ocr.OcrUnavailable, match="fetch_ocr_models"):
        ocr.RapidEngine()


def test_the_fetch_script_and_the_engine_name_the_same_three_files(tmp_path):
    pytest.importorskip("rapidocr")
    files = ocr.model_files()
    assert set(files) == {"det", "rec", "cls"}
    assert all(f["sha256"] and f["file"].endswith(".onnx") and f["url"].startswith("https://") for f in files.values())
    spec = importlib.util.spec_from_file_location("fetch_ocr_models", REPO / "scripts" / "fetch_ocr_models.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    present = tmp_path / "x.onnx"
    present.write_bytes(b"model")
    import hashlib
    mod.fetch("https://invalid.invalid/never", present, hashlib.sha256(b"model").hexdigest())   # present: no network
    assert present.read_bytes() == b"model"


# ── badges from OCR (room_locator) ──────────────────────────────────────────

def test_room_badges_on_a_sheet_without_a_text_layer_come_from_ocr(monkeypatch):
    from extractor.room_locator import locate_rooms
    pdf = _one_page_pdf()
    rooms = [{"nr": "12"}, {"nr": "7"}]
    asked = []

    def items(pdf_bytes, page, dpi=None, engine=None):
        asked.append(page)
        return ocr.page_items([Word("12", 200, 300, 208, 306, 0.99, 0), Word("7", 400, 300, 404, 306, 0.99, 0)],
                              page, W, H)
    monkeypatch.setattr(ocr, "ocr_page_items", items)
    monkeypatch.delenv("SAMATU_OCR", raising=False)
    assert locate_rooms(pdf, rooms, [1]) == {} and asked == []          # flag off: no OCR, nothing located
    monkeypatch.setenv("SAMATU_OCR", "1")
    found = locate_rooms(pdf, rooms, [1])
    assert asked == [1]
    assert found["12"]["saltinis"] == "zenkliukas" and found["12"]["cx"] == pytest.approx(204 / W)
    assert found["7"]["page"] == 1


# ── the room table from OCR ─────────────────────────────────────────────────

def _table_words() -> list[Word]:
    """A scanned eksplikacija as OCR returns it: heading centred over the table, ink-tight boxes (capitals and
    lower case differ in top), a lone digit called vertical, a drawing number at a row's height to the left."""
    rows = [("1", "Tambūras", "3.14"), ("2", "Kambarys", "15.27"), ("3", "Virtuvė/svetainė", "35.86"),
            ("4", "San.", "3.69")]
    out = [Word("PATALPÚ", 717, 30.7, 735.7, 34.8, 0.99, 0), Word("EKSPLIKACIJA", 738.6, 30.7, 769.1, 33.8, 0.99, 0),
           Word("Pat.", 684.1, 41.0, 692.0, 48.5, 0.99, 0), Word("Patalpos", 695.9, 45.6, 713.6, 49.9, 0.99, 0),
           Word("m²", 787.8, 46.3, 793.1, 49.7, 0.99, 0)]
    y = 57.3
    for nr, name, area in rows:
        out.append(Word(nr, 686.8, y + 0.4, 689.2, y + 3.6, 0.99, 90 if nr == "3" else 0))
        out.append(Word(name, 695.4, y, 717 + 2 * len(name), y + 5.2, 0.99, 0))
        out.append(Word(area + ("," if nr == "2" else ""), 784.9, y + 0.2, 795.9, y + 3.6, 0.99, 0))
        out.append(Word("2000", 501.0, y - 1.0, 518.0, y + 6.0, 0.99, 0))        # the drawing beside the table
        y += 7.0
    out.append(Word("mazgas", 707.9, y - 7.0, 723.9, y - 3.4, 0.99, 0))
    out += [Word("Bendras", 695.6, y + 4, 712.9, y + 7.6, 0.99, 0), Word("plotas", 715.1, y + 4, 727.1, y + 8.6, 0.99, 0),
            Word("57.96", 784.9, y + 4.5, 796.2, y + 7.8, 0.99, 0)]
    return out


def test_a_scanned_room_table_is_read_from_ocr_words(monkeypatch):
    from extractor.pdfplumber_eksplikacija import _lt_ocr_word, extract_eksplikacija_pdfplumber
    assert _lt_ocr_word("PATALPÚ") == "PATALPŲ" and _lt_ocr_word("TAMBÚRAS") == "TAMBŪRAS"
    assert _lt_ocr_word("15.27,") == "15.27"
    pdf = _one_page_pdf()
    monkeypatch.setattr(ocr, "ocr_page", lambda pdf_bytes, page, *a, **k: (W, H, _table_words()))
    monkeypatch.delenv("SAMATU_OCR", raising=False)
    off = extract_eksplikacija_pdfplumber(pdf)
    assert off["patalpos"] == [] and "ocr_pages" not in off["_meta"]
    monkeypatch.setenv("SAMATU_OCR", "1")
    res = extract_eksplikacija_pdfplumber(pdf)
    got = [(r["nr"], r["pavadinimas"], r["plotas_m2"]) for r in res["patalpos"]]
    assert got == [("1", "Tambūras", 3.14), ("2", "Kambarys", 15.27), ("3", "Virtuvė/svetainė", 35.86),
                   ("4", "San. mazgas", 3.69)]
    assert all(r["_row_source"] == "ocr_table" and r["plotas_m2_raw"] for r in res["patalpos"])
    assert res["eksplikacija_source_page"] == 1 and res["_meta"]["source"] == "ocr_table"
    assert res["_meta"]["total_area_m2"] == 57.96 and res["_meta"]["total_rows_sum_m2"] == 57.96


def test_a_scanned_table_whose_rows_do_not_add_up_is_refused(monkeypatch):
    from extractor.pdfplumber_eksplikacija import extract_eksplikacija_pdfplumber
    words = [w if w.text != "57.96" else Word("67.96", w.x0, w.y0, w.x1, w.y1, w.conf, w.angle) for w in _table_words()]
    monkeypatch.setattr(ocr, "ocr_page", lambda pdf_bytes, page, *a, **k: (W, H, words))
    monkeypatch.setenv("SAMATU_OCR", "1")
    assert extract_eksplikacija_pdfplumber(_one_page_pdf())["patalpos"] == []


# ── the centimetre reading of a string ──────────────────────────────────────

def test_the_centimetre_reading():
    from extractor.plan_dimensions import _value_cm
    assert _value_cm("173") == 1.73 and _value_cm("1412") == 14.12 and _value_cm("80") == 0.8
    assert _value_cm("08") is None and _value_cm("25") is None and _value_cm("12500") is None

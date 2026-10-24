"""text/ocr.py + the scale module's OCR hook (plan 2026-10-24 §3.2, R6, §9 Phase 1 cause 7).

Every sheet is synthetic, drawn in the test. Tests that need a real OCR engine skip when none is installed
(no engine is a backend requirement yet — the manager decides); the geometry, the flag and the hook are
tested with a fake engine everywhere.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

import text.ocr as ocr
from geometry.provenance import PT_M, ScaleSource
from geometry.scale import OCR_NOTE, ScaleContext, scale_for_page
from text import layer
from text.ocr import Line, Word, ocr_words, page_items

W, H = A4
FONT = Path(__file__).resolve().parents[1] / "assets" / "fonts" / "DejaVuSans.ttf"


def _real_engine():
    for name in ("rapid", "paddle", "tesseract"):
        try:
            return ocr.get_engine(name)
        except Exception:  # noqa: BLE001 — not installed here
            continue
    return None


# ── geometry of a read (fake engine) ────────────────────────────────────────

@pytest.mark.parametrize("r", [0, 90, 180, 270])
def test_unrotate_inverts_the_turned_image(r):
    img = np.zeros((40, 70, 3), dtype=np.uint8)
    img[5, 11] = 255                                   # pixel at x = 11, y = 5
    turned = ocr._rotate_image(img, r)
    v, u = (int(a) for a in np.argwhere(turned[:, :, 0] == 255)[0])
    x, y = ocr._unrotate(u + 0.5, v + 0.5, r, 70, 40)
    assert (x, y) == pytest.approx((11.5, 5.5))


class FakeEngine:
    """Reads what it is told is on the 0° image; on the turned image it reads nothing (or the same words turned,
    when `also_turned`) — enough to check the frame arithmetic, the angle and the de-duplication."""
    name = "fake"

    def __init__(self, lines0, lines90=()):
        self.lines0, self.lines90, self.calls = list(lines0), list(lines90), 0

    def read(self, rgb):
        self.calls += 1
        return list(self.lines0) if rgb.shape[0] == 100 else list(self.lines90)


def _q(x0, y0, x1, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


def test_words_come_back_in_points_with_their_reading_angle():
    eng = FakeEngine([
        Line("4280", _q(10, 10, 50, 20), 0.99),                              # horizontal
        Line("SOFA 200x800", _q(80, 20, 90, 90), 0.98,                         # vertical, words top→bottom
             words=[("SOFA", _q(80, 20, 90, 45)), ("200x800", _q(80, 50, 90, 90))]),
        Line("1800", _q(150, 30, 160, 70), 0.97),                               # a lone vertical word
    ])
    words = ocr_words(np.zeros((100, 200, 3), dtype=np.uint8), eng, pt_per_px=0.5, rotations=(0,))
    by = {w.text: w for w in words}
    assert (by["4280"].x0, by["4280"].y0, by["4280"].x1, by["4280"].y1) == (5, 5, 25, 10)
    assert by["4280"].angle == 0
    assert by["SOFA"].angle == 270 and by["200x800"].angle == 270       # reads downward
    assert by["1800"].angle == 90                                       # a lone vertical word: upward by convention
    assert by["200x800"].y0 == pytest.approx(25)


def test_the_upright_read_on_the_turned_render_wins_over_the_sideways_one():
    # „3650" written upward at x 150..160, y 30..70 on the 100 × 200 image. On the image turned 90° clockwise
    # (200 × 100) it is upright at u = 100 − 70 … 100 − 30, v = 150 … 160.
    eng = FakeEngine([Line("3B50", _q(150, 30, 160, 70), 0.99)],
                     [Line("3650", _q(30, 150, 70, 160), 0.95)])
    words = ocr_words(np.zeros((100, 200, 3), dtype=np.uint8), eng, rotations=(0, 90))
    assert [w.text for w in words] == ["3650"]
    w = words[0]
    assert (w.x0, w.y0, w.x1, w.y1) == pytest.approx((150, 30, 160, 70)) and w.angle == 90
    assert eng.calls == 2


def test_low_confidence_reads_are_dropped():
    eng = FakeEngine([Line("7", _q(0, 0, 5, 5), 0.3)])
    assert ocr_words(np.zeros((100, 200, 3), dtype=np.uint8), eng, rotations=(0,)) == []


def test_page_items_feed_the_dimension_reader_unchanged():
    """A vertical OCR word goes through `_dimensions_on_page` as the text layer's would: orientation v, its box."""
    from extractor.plan_dimensions import _dimensions_on_page
    words = [Word("4280", 100, 200, 130, 208, 0.99, 0), Word("3650", 300, 100, 308, 130, 0.98, 90),
             Word("Virtuvė", 50, 50, 90, 58, 0.97, 0)]
    dims = []
    for pn, Wd, Hd, chars, to_display in page_items(words, 1, W, H):
        dims += _dimensions_on_page(pn, Wd, Hd, chars, to_display)
    by = {d["text"]: d for d in dims}
    assert set(by) == {"4280", "3650"}
    assert by["4280"]["orientation"] == "h" and by["4280"]["bbox"] == pytest.approx([100, 200, 130, 208], abs=0.01)
    assert by["3650"]["orientation"] == "v" and by["3650"]["bbox"] == pytest.approx([300, 100, 308, 130], abs=0.01)
    assert by["3650"]["value_m"] == 3.65


# ── a real engine on a synthetic sheet ──────────────────────────────────────

def _lt_sheet() -> bytes:
    pdfmetrics.registerFont(TTFont("DejaVuSans", str(FONT)))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setFont("DejaVuSans", 10)
    c.drawString(100, H - 150, "4280")
    c.drawString(300, H - 150, "1800")
    c.drawString(100, H - 400, "Virtuvė-svetainė")
    c.drawString(300, H - 400, "Šildymas ąčęėįšųūž")
    c.saveState()
    c.translate(450, H - 300)
    c.rotate(90)
    c.drawString(0, 0, "3650")                                   # a vertical dimension string, reading upward
    c.restoreState()
    c.rect(200, H - 600, 18, 16, stroke=1, fill=0)               # a room badge in its box
    c.drawString(203, H - 596, "12")
    c.showPage()
    c.save()
    return buf.getvalue()


SIZE = 10.0
X_MID = 0.36 * SIZE         # a digit's / letter's middle sits ~0,36 em above the baseline (DejaVu x-height / cap)


def _truth_centres() -> dict[str, tuple[float, float]]:
    """Where each string of `_lt_sheet` is, by construction (display frame, top-left origin): reportlab draws at the
    baseline, the string's middle is half its width along it and ~X_MID above it."""
    def w(t):
        return pdfmetrics.stringWidth(t, "DejaVuSans", SIZE)
    return {
        "4280": (100 + w("4280") / 2, 150 - X_MID),
        "1800": (300 + w("1800") / 2, 150 - X_MID),
        "Virtuvė-svetainė": (100 + w("Virtuvė-svetainė") / 2, 400 - X_MID),
        "3650": (450 - X_MID, 300 - w("3650") / 2),            # turned 90°: runs upward from (450, 300)
        "12": (203 + w("12") / 2, 596 - X_MID),
    }


def test_a_real_engine_reads_numbers_vertical_string_diacritics_and_badge():
    eng = _real_engine()
    if eng is None:
        pytest.skip("no OCR engine installed (rapidocr / paddleocr / tesseract)")
    pdf = _lt_sheet()
    truth = _truth_centres()
    ocr._cache.clear()
    _Wd, _Hd, words = ocr.ocr_page(pdf, 1, dpi=200, engine=eng)
    got = {w.text: w for w in words}
    for t in ("4280", "1800", "3650", "12", "Virtuvė-svetainė"):
        assert t in got, (t, sorted(got))
        tx, ty = truth[t]
        w = got[t]
        cx, cy = (w.x0 + w.x1) / 2, (w.y0 + w.y1) / 2
        assert abs(cx - tx) <= 3 and abs(cy - ty) <= 3, (t, w, truth[t])
    assert got["3650"].angle in (90, 270) and got["4280"].angle == 0
    if eng.name != "tesseract":
        assert "Šildymas" in got
        # the nine diacritics in a row: at most one wrong (į is read as j on small type — measured, the one
        # ambiguous pair the LT look-alike map cannot settle)
        row = next(w.text for w in words if len(w.text) == 9 and w.text[:2] == "ąč")
        assert sum(a != b for a, b in zip(row, "ąčęėįšųūž")) <= 1, row


# ── the flag ────────────────────────────────────────────────────────────────

def _no_text_sheet() -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.rect(100, 100, 300, 200, stroke=1, fill=0)
    c.showPage()
    c.save()
    return buf.getvalue()


class Boom:
    name = "boom"

    def read(self, rgb):  # pragma: no cover — must never run
        raise AssertionError("OCR was called with the flag off")


def test_flag_off_makes_no_ocr_call(monkeypatch):
    monkeypatch.delenv("SAMATU_OCR", raising=False)
    calls = []
    monkeypatch.setattr(ocr, "get_engine", lambda *a, **k: calls.append(1) or Boom())
    monkeypatch.setattr(ocr, "dimension_strings", lambda *a, **k: calls.append(2) or ([], set()))
    monkeypatch.setattr(ocr, "ocr_page", lambda *a, **k: calls.append(3) or (W, H, []))
    pdf = _no_text_sheet()
    sc = scale_for_page(ScaleContext(pdf), 1)
    assert not sc.found
    assert layer.page_items(pdf, [1]) == []
    assert calls == []
    from extractor.feature_flags import get_flags
    assert get_flags()["ocr"] is False


# ── the scale hook ──────────────────────────────────────────────────────────

from tests.test_geometry_scale import _pdf, _sheet  # noqa: E402 — the same synthetic block of six rooms


def _ocr_twin(denom: float):
    """(sheet with walls and NO text, the dimension strings OCR would find on it): the strings are the text
    layer of the identical sheet with text, stripped of everything the OCR could not know."""
    from extractor.plan_dimensions import read_dimension_strings
    with_text = _pdf(_sheet(denom, strings="inside"))
    keep = ("page", "text", "value_m", "bbox", "page_width", "page_height", "orientation")
    dims = [{k: d[k] for k in keep} | {"source": "ocr", "ocr_conf": 0.99} for d in read_dimension_strings(with_text)]
    return _pdf(_sheet(denom, strings=None)), dims


def test_hook_gives_a_sheet_without_a_text_layer_a_scale_from_ocr_strings(monkeypatch):
    blank_pdf, dims = _ocr_twin(50)
    assert len(dims) >= 10
    monkeypatch.setenv("SAMATU_OCR", "1")
    calls = []
    monkeypatch.setattr(ocr, "dimension_strings", lambda pdf, page, *a, **k: calls.append(page) or (
        [dict(d) for d in dims if d["page"] == page], set()))
    sc = scale_for_page(ScaleContext(blank_pdf), 1)
    assert calls == [1]
    assert sc.source == ScaleSource.DIMENSION_WALLS
    assert sc.m_per_pt / PT_M == pytest.approx(50, rel=0.01)
    assert OCR_NOTE in sc.source_text and sc.details.get("ocr") is True


def test_hook_reads_a_written_scale_by_ocr_when_nothing_else_measures(monkeypatch):
    monkeypatch.setenv("SAMATU_OCR", "1")
    monkeypatch.setattr(ocr, "dimension_strings", lambda pdf, page, *a, **k: ([], {75}))
    sc = scale_for_page(ScaleContext(_no_text_sheet()), 1)
    assert sc.source == ScaleSource.STATED and sc.m_per_pt / PT_M == pytest.approx(75)
    assert "nepatikrintas" in sc.source_text and OCR_NOTE in sc.source_text


def test_hook_leaves_a_sheet_with_a_text_layer_alone(monkeypatch):
    monkeypatch.setenv("SAMATU_OCR", "1")
    calls = []
    monkeypatch.setattr(ocr, "dimension_strings", lambda *a, **k: calls.append(1) or ([], set()))
    sc = scale_for_page(ScaleContext(_pdf(_sheet(50, strings="inside"))), 1)
    assert calls == []
    assert sc.source == ScaleSource.DIMENSION_WALLS and "OCR" not in (sc.source_text or "")
    assert OCR_NOTE not in sc.source_text
    # a sheet that WRITES its scale but has no strings is not OCR'd either (its layer has something)
    sc2 = scale_for_page(ScaleContext(_pdf(_sheet(50, strings=None, stated="PLANAS M 1:50"))), 1)
    assert calls == [] and sc2.source == ScaleSource.STATED


def test_hook_survives_a_missing_engine(monkeypatch):
    monkeypatch.setenv("SAMATU_OCR", "1")

    def missing(*a, **k):
        raise ocr.OcrUnavailable("not installed")
    monkeypatch.setattr(ocr, "dimension_strings", missing)
    sc = scale_for_page(ScaleContext(_no_text_sheet()), 1)
    assert not sc.found and sc.reason


def test_layer_ocrs_only_pages_without_a_text_layer(monkeypatch):
    monkeypatch.setenv("SAMATU_OCR", "1")
    asked = []
    monkeypatch.setattr(ocr, "ocr_page_items", lambda pdf, p, dpi=None, engine=None: asked.append(p) or [
        (p, W, H, [{"text": "7", "x0": 1, "x1": 2, "top": 1, "bottom": 2, "size": 1}], lambda b: b)])
    with_text = _pdf(_sheet(50, strings="inside"), _sheet(50, strings=None))
    items = layer.page_items(with_text, [1, 2])
    assert asked == [2]
    assert {int(it[0]) for it in items} == {1, 2}


def test_hook_replaces_a_few_layer_strings_with_the_ocr_read(monkeypatch):
    """objektas_c sheet 3: four strings of one value in the layer, the rest drawn as outlines — fewer than any source
    can use, so the sheet is OCR'd and the OCR read (which sees those four too) replaces them."""
    _blank, dims = _ocr_twin(50)
    draw_walls = _sheet(50, strings=None)

    def draw(c):
        draw_walls(c)
        c.setFont("Helvetica", 6)
        for i in range(3):
            c.drawString(100 + 40 * i, 60, "760")
    few = _pdf(draw)
    monkeypatch.setenv("SAMATU_OCR", "1")
    calls = []
    monkeypatch.setattr(ocr, "dimension_strings", lambda pdf, page, *a, **k: calls.append(page) or (
        [dict(d) for d in dims if d["page"] == page], set()))
    ctx = ScaleContext(few)
    sc = scale_for_page(ctx, 1)
    assert calls == [1]
    assert ctx.strings_on(1) and all(d.get("source") == "ocr" for d in ctx.strings_on(1))
    assert sc.source == ScaleSource.DIMENSION_WALLS and sc.m_per_pt / PT_M == pytest.approx(50, rel=0.01)


# ── R6: nothing leaves the machine ─────────────────────────────────────────

def test_no_cloud_ocr_client_in_backend():
    root = Path(__file__).resolve().parents[1]
    banned = re.compile(r"google\.cloud\s*import\s*vision|from\s+google\.cloud\.vision|textract|"
                        r"azure\.ai\.(formrecognizer|documentintelligence|vision)|ocr\.space|mathpix", re.I)
    hits = []
    for p in root.rglob("*.py"):
        if any(part in ("venv", ".venv", "node_modules", "tests") for part in p.parts):
            continue
        if banned.search(p.read_text(errors="ignore")):
            hits.append(str(p.relative_to(root)))
    assert hits == []


def test_ocr_module_imports_no_vision_or_network_client():
    src = (Path(__file__).resolve().parents[1] / "text" / "ocr.py").read_text()
    for mod in ("anthropic", "requests", "httpx", "urllib", "vision"):
        assert not re.search(rf"^\s*(import|from)\s+[\w.]*{mod}", src, re.M), mod

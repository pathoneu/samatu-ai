"""OCR'd dimension strings reach `sum_perimeters` (v4/ocr-dimension-strings, flag SAMATU_OCR).

A plan-group sheet whose text layer has few line-backed dimension strings on many hairlines (CAD exports that
wrote the dimension text as curves — objektas_a page 2) gets its dimension strings from OCR. The OCR'd strings
are attached to the sheet's vector hairlines the way text-layer strings are, so they carry
`span_source == "line"` and reach `sum_perimeters` the same way (research 2026-10-29-ocr-dimension-strings).
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import text.ocr as ocr  # noqa: E402
from extractor import geometry_lane as gl  # noqa: E402
from extractor import plan_dimensions as pd  # noqa: E402
from tests.synthetic_plan import build_plan, two_rooms  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMATU_OCR_CACHE_DIR", str(tmp_path / "ocr_cache"))
    ocr._cache.clear()
    yield
    ocr._cache.clear()


def _parsed_two_rooms():
    r1 = {"nr": "01", "pavadinimas": "A", "plotas_m2": 12.0, "plotas_saltinis": "eksplikacija", "puslapio_nr": 1,
          "perimetras_m": 13.9, "bbox_pct": {"x": 0.12, "y": 0.10, "w": 0.2, "h": 0.12},
          "polygon_pct": [[0.12, 0.10], [0.32, 0.10], [0.32, 0.22], [0.12, 0.22]],
          "polygon_source": "synthesized_from_bbox"}
    return {"puslapiai": [{"nr": 1, "tipas": "floor_plan"}, {"nr": 2, "tipas": "floor_plan"}],
            "patalpos": [r1, {"nr": "02", "pavadinimas": "B", "plotas_m2": 9.0, "plotas_saltinis": "eksplikacija",
                              "puslapio_nr": 1, "perimetras_m": 12.3}]}


class _StripSecondSheetText:
    """A reportlab Canvas wrapper that forwards everything to the real canvas except text draws on page ≥ 2."""

    def __init__(self, inner):
        self._c = inner
        self._page = 1

    def showPage(self):
        self._page += 1
        return self._c.showPage()

    def __getattr__(self, name):
        if name in ("drawString", "drawCentredString", "drawRightString") and self._page >= 2:
            return lambda *a, **k: None
        return getattr(self._c, name)


def _twin_sheets():
    """Build the two sheets twice. The 'twin' has text on both pages (the OCR fake reads from it); the 'blank'
    strips text on page 2 — walls and dimension hairlines remain, but every number is drawn as curves."""
    from reportlab.pdfgen import canvas as canvas_module
    real_canvas = canvas_module.Canvas

    def mk(sheets):
        return build_plan(sheets)

    def build():
        sheet_a = two_rooms(); sheet_a.dims = []
        sheet_b = two_rooms(); sheet_b.badges = []
        return [sheet_a, sheet_b]

    twin = mk(build())
    original = canvas_module.Canvas
    try:
        canvas_module.Canvas = lambda *a, **k: _StripSecondSheetText(real_canvas(*a, **k))
        blank = mk(build())
    finally:
        canvas_module.Canvas = original
    # the twin's page 2 must have text-layer dim strings; the blank's must not
    twin_dims = pd.read_dimension_strings(twin, pages=[2])
    blank_dims = pd.read_dimension_strings(blank, pages=[2])
    assert twin_dims, "twin page 2 must have text-layer dim strings"
    assert not blank_dims, f"blank page 2 must have no text-layer dim strings; found {len(blank_dims)}"
    keep = ("page", "text", "value_m", "bbox", "page_width", "page_height", "orientation")
    ocr_dims = [{k: d[k] for k in keep} | {"source": "ocr", "ocr_conf": 0.95} for d in twin_dims]
    return blank, ocr_dims


def test_a_sheet_with_dimension_text_as_curves_feeds_sum_perimeters_from_ocr(monkeypatch):
    """objektas_a page 2 case: the text layer gives one '1400' and nothing is on a hairline, but 349 hairlines
    sit there. With SAMATU_OCR on, OCR'd dim strings reach sum_perimeters and the rooms' perimeters read."""
    pdf, ocr_dims = _twin_sheets()
    monkeypatch.setenv("SAMATU_OCR", "1")
    calls = []

    def fake(pdf_bytes, page, *a, units="mm", **k):
        calls.append((int(page), units))
        if units != "mm":
            return [], set()
        return [dict(d) for d in ocr_dims if d["page"] == page], set()

    monkeypatch.setattr(ocr, "dimension_strings", fake)
    parsed = _parsed_two_rooms()
    gl.apply_geometry(parsed, pdf)
    r1, r2 = parsed["patalpos"]
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes"
    assert r2["perimetras_m"] == 12.0 and r2["perimetras_saltinis"] == "matmenu_eilutes"
    assert any(p == 2 for p, _ in calls), f"page 2 must have been OCR'd; calls={calls}"


def test_flag_off_leaves_perimeters_unread_from_dimensions(monkeypatch):
    """Flag OFF: the OCR engine is never asked and the sheet's dimension strings stay absent — the rooms'
    perimeters are not read from dim strings (`matmenu_eilutes` source)."""
    monkeypatch.delenv("SAMATU_OCR", raising=False)
    pdf, _ = _twin_sheets()
    calls = []
    monkeypatch.setattr(ocr, "dimension_strings", lambda *a, **k: calls.append(a[:2]) or ([], set()))
    parsed = _parsed_two_rooms()
    gl.apply_geometry(parsed, pdf)
    r1 = parsed["patalpos"][0]
    assert r1.get("perimetras_saltinis") != "matmenu_eilutes"      # no dim strings were read
    assert calls == []


def test_a_sheet_with_a_complete_text_layer_is_not_ocrd(monkeypatch):
    """A plan sheet whose text layer carries plenty of line-backed strings (two_rooms with its text intact) must
    not trigger OCR even when the flag is on."""
    from tests.test_geometry_lane import _two_sheets
    monkeypatch.setenv("SAMATU_OCR", "1")
    calls = []
    monkeypatch.setattr(ocr, "dimension_strings", lambda *a, **k: calls.append(a[:2]) or ([], set()))
    parsed = _parsed_two_rooms()
    gl.apply_geometry(parsed, _two_sheets())
    assert calls == []                                           # the sheet's text layer did the job
    r1 = parsed["patalpos"][0]
    assert r1["perimetras_m"] == 14.0 and r1["perimetras_saltinis"] == "matmenu_eilutes"


def test_ocr_augment_dimensions_returns_empty_with_the_flag_off(monkeypatch):
    """Flag OFF: the function returns [] without touching the engine (invariant: production dims unchanged)."""
    monkeypatch.delenv("SAMATU_OCR", raising=False)
    monkeypatch.setattr(ocr, "dimension_strings", lambda *a, **k: pytest.fail("must not run"))
    out = pd.ocr_augment_dimensions(b"not a pdf", [], [1, 2, 3])
    assert out == []


def test_ocr_augment_dimensions_dedupes_against_existing_text_layer_strings(monkeypatch):
    """A text-layer string of the same value at nearly the same place as an OCR'd one is the same string: keep one."""
    pdf, ocr_dims = _twin_sheets()
    monkeypatch.setenv("SAMATU_OCR", "1")
    # pretend the text layer already had the first OCR'd string
    existing = dict(ocr_dims[0]); existing["source"] = None; existing.pop("ocr_conf", None)

    def fake(pdf_bytes, page, *a, units="mm", **k):
        if units != "mm" or page != 2:
            return [], set()
        return [dict(d) for d in ocr_dims if d["page"] == page], set()
    monkeypatch.setattr(ocr, "dimension_strings", fake)
    added = pd.ocr_augment_dimensions(pdf, [existing], [2])
    added_centres = {(round((d["bbox"][0] + d["bbox"][2]) / 2, 2), round((d["bbox"][1] + d["bbox"][3]) / 2, 2), d["value_m"])
                     for d in added}
    existing_centre = (round((existing["bbox"][0] + existing["bbox"][2]) / 2, 2),
                       round((existing["bbox"][1] + existing["bbox"][3]) / 2, 2), existing["value_m"])
    assert existing_centre not in added_centres                   # the duplicate was dropped
    assert all(d.get("saltinis") == "ocr" for d in added)

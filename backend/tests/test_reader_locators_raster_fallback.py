"""Sub-reader page locators must not go blind on a rasterised PDF.

2026-08-23 flattened-scan ablation (Objektas A at 150 DPI, no text layer): the
apdailos and door-type locators search the text layer, found nothing, and the
readers silently returned `skipped` — every room fell to paskirtis defaults and
wall paint came out −31.6%. Pass-1 had classified the same pages correctly
from the images (p10 finish_schedule, p11–17 wall_elevation). The fallback
below uses that classification when — and only when — the text scan is empty.
"""
from __future__ import annotations

import pytest

from extractor import apdailos_reader as ar
from extractor import door_type_reader as dr

# Exactly what Pass-1 emitted on the raster run.
PUSLAPIAI = [{"nr": 2, "tipas": "floor_plan"}, {"nr": 3, "tipas": "floor_plan"},
             {"nr": 4, "tipas": "plumbing"}, {"nr": 6, "tipas": "ceiling_plan"},
             {"nr": 9, "tipas": "floor_plan"}, {"nr": 10, "tipas": "finish_schedule"},
             *[{"nr": n, "tipas": "wall_elevation"} for n in range(11, 18)],
             {"nr": 0, "tipas": "wall_elevation"},      # classifier can emit nr=0
             {"nr": None, "tipas": "finish_schedule"}]  # or null


@pytest.fixture
def raster(monkeypatch):
    """No text layer at all — what pdfplumber returns for a scan."""
    import extractor.pdf_page_cache as cache
    monkeypatch.setattr(cache, "page_texts", lambda b: [""] * 17)


@pytest.fixture
def with_text(monkeypatch):
    import extractor.pdf_page_cache as cache
    texts = [""] * 17
    texts[9] = "APDAILŲ PLANAS"          # page 10
    texts[11] = "SIENŲ IŠKLOTINĖS"       # page 12
    texts[1] = "D1 beapvadinės durys"    # page 2 — door tag + annotation
    monkeypatch.setattr(cache, "page_texts", lambda b: texts)


def test_apdailos_locator_falls_back_to_classification_on_a_scan(raster):
    pages = ar._find_apdailos_pages(b"%PDF", PUSLAPIAI)
    assert pages, "a scan must not leave the finish reader with no pages"
    # elevations first (they carry the per-wall finish markers), then the
    # finish schedule; bogus nr=0/None entries ignored; capped.
    assert pages[0] == 11
    assert 10 in pages and 0 not in pages
    assert len(pages) <= ar.MAX_APDAILOS_PAGES


def test_apdailos_locator_text_hits_still_win(with_text):
    pages = ar._find_apdailos_pages(b"%PDF", PUSLAPIAI)
    assert pages == [12, 10], "text-layer projects must be byte-identical to before"


def test_apdailos_locator_without_any_signal_is_empty(raster):
    assert ar._find_apdailos_pages(b"%PDF", None) == []
    assert ar._find_apdailos_pages(b"%PDF", []) == []


def test_door_locator_falls_back_to_classification_on_a_scan(raster):
    pages = dr._find_door_pages(b"%PDF", PUSLAPIAI)
    assert pages and pages[0] in (2, 3, 9), "floor plans carry the door tags"
    assert len(pages) <= dr.MAX_DOOR_PAGES


def test_door_locator_text_hits_still_win(with_text):
    assert dr._find_door_pages(b"%PDF", PUSLAPIAI) == [2]


def test_read_apdailos_reports_skipped_only_when_truly_blind(raster):
    out = ar.read_apdailos_finishes(b"%PDF", [], pages_meta=None)
    assert out["status"] == "skipped"

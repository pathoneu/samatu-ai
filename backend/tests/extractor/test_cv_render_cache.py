"""Render cache: PDF page → grayscale uint8 ndarray, cached on disk by
(pdf_hash, page_idx, dpi). Repeat calls hit cache.

2026-09-29: the drawing is a synthetic reportlab PDF (tests/synthetic_plan_pdf)
instead of a sample client drawing that carried an identifier, so these
always run."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402

from extractor.cv_render_cache import render_page, cache_key  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from synthetic_plan_pdf import plan_pdf  # noqa: E402


def _sample_pdf() -> bytes:
    return plan_pdf()


def test_render_returns_grayscale_ndarray():
    img = render_page(_sample_pdf(), page_idx=0, dpi=200)
    assert isinstance(img, np.ndarray)
    assert img.dtype == np.uint8
    assert img.ndim == 2  # grayscale, single channel


def test_cache_key_is_stable_for_same_inputs():
    pdf = _sample_pdf()
    a = cache_key(pdf, page_idx=0, dpi=200)
    b = cache_key(pdf, page_idx=0, dpi=200)
    assert a == b


def test_cache_key_differs_when_dpi_changes():
    pdf = _sample_pdf()
    assert cache_key(pdf, 0, 200) != cache_key(pdf, 0, 300)


def test_cache_key_differs_when_page_changes():
    pdf = _sample_pdf()
    assert cache_key(pdf, 0, 200) != cache_key(pdf, 1, 200)


def test_repeat_render_hits_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("extractor.cv_render_cache.CACHE_DIR", tmp_path)
    pdf = _sample_pdf()
    a = render_page(pdf, page_idx=0, dpi=200)
    b = render_page(pdf, page_idx=0, dpi=200)
    np.testing.assert_array_equal(a, b)
    # exactly one PNG in the cache dir per (pdf, page, dpi)
    assert len(list(tmp_path.glob("*.png"))) == 1

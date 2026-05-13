"""Render cache: PDF page → grayscale uint8 ndarray, cached on disk by
(pdf_hash, page_idx, dpi). Repeat calls hit cache.

2026-05-11: corpus moved to ~/Desktop/test_pdfs/ (out-of-repo). Tests
skip when the PDF can't be reached so CI stays green without the
private interior corpus."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from extractor.cv_render_cache import render_page, cache_key  # noqa: E402

_ENV_PDF = os.environ.get("SAMATU_TEST_PDF", "").strip()
_TEST_PDF_CANDIDATES = [
    Path(_ENV_PDF) if _ENV_PDF else None,
    Path.home() / "Desktop" / "test_pdfs" / "vidaus_apdaila.pdf",
    Path(__file__).resolve().parents[2] / "test_pdfs" / "vidaus_apdaila.pdf",
]
_TEST_PDF = next(
    (p for p in _TEST_PDF_CANDIDATES if p is not None and p.is_file()),
    None,
)

pytestmark = pytest.mark.skipif(
    _TEST_PDF is None,
    reason="vidaus_apdaila.pdf not found — set SAMATU_TEST_PDF or place "
           "at ~/Desktop/test_pdfs/vidaus_apdaila.pdf",
)


def _sample_pdf() -> bytes:
    return _TEST_PDF.read_bytes()


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

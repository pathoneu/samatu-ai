"""Smoke tests for the PDF page loader."""

import numpy as np
import pytest
from pathlib import Path

from detector_bench.core.pdf_loader import (
    render_page, get_page_dims_pdf,
)


# Use one of the real test PDFs as fixture (it's the production input anyway)
TEST_PDF = Path(
    "/Users/ignasgaldikas/samatu-ai/training-data/projektas_3/projektas_3_breziniai.pdf"
)


@pytest.mark.skipif(not TEST_PDF.exists(), reason="test PDF unavailable")
def test_render_page_returns_grayscale_uint8():
    img = render_page(TEST_PDF, page_nr=1, dpi=100)
    assert isinstance(img, np.ndarray)
    assert img.dtype == np.uint8
    assert img.ndim == 2  # grayscale
    assert img.shape[0] > 100 and img.shape[1] > 100


@pytest.mark.skipif(not TEST_PDF.exists(), reason="test PDF unavailable")
def test_render_page_caches_to_disk(tmp_path, monkeypatch):
    """Second call should be much faster (cache hit)."""
    import time
    monkeypatch.setenv("DETECTOR_BENCH_RENDER_CACHE", str(tmp_path))
    t0 = time.time()
    img1 = render_page(TEST_PDF, page_nr=1, dpi=100)
    cold = time.time() - t0
    t0 = time.time()
    img2 = render_page(TEST_PDF, page_nr=1, dpi=100)
    warm = time.time() - t0
    np.testing.assert_array_equal(img1, img2)
    # Warm cache should be at least 5× faster than cold
    assert warm < cold / 5.0, f"cache didn't help: cold={cold:.2f}s warm={warm:.2f}s"


@pytest.mark.skipif(not TEST_PDF.exists(), reason="test PDF unavailable")
def test_get_page_dims_pdf_returns_pdf_points():
    w_pt, h_pt = get_page_dims_pdf(TEST_PDF, page_nr=1)
    # P3 is A3 = 842 × 1191 pts (rotated 270 → 1191 × 842 effective)
    # Either way, dimensions should be in that range.
    assert 800 <= max(w_pt, h_pt) <= 1300
    assert 600 <= min(w_pt, h_pt) <= 900

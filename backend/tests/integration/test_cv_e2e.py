"""End-to-end integration: real LT PDF → CV layer returns sensible
results. Acceptance gate — a regression in cv_match /
cv_render_cache should break this test.

Marked `integration` so a regular `pytest` run skips it; CI invokes
explicitly with `pytest -m integration`.

2026-05-11: corpus moved to ~/Desktop/test_pdfs/ (out-of-repo). Tests
skip when the PDF can't be reached."""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from extractor.cv_match import find_similar_symbols  # noqa: E402
from extractor.cv_render_cache import render_page  # noqa: E402

_ENV_PDF = os.environ.get("SAMATU_TEST_PDF", "").strip()
_PDF_CANDIDATES = [
    Path(_ENV_PDF) if _ENV_PDF else None,
    Path.home() / "Desktop" / "test_pdfs" / "vidaus_apdaila.pdf",
    Path(__file__).resolve().parents[2] / "test_pdfs" / "vidaus_apdaila.pdf",
]
PDF = next(
    (p for p in _PDF_CANDIDATES if p is not None and p.is_file()),
    None,
)

pytestmark = pytest.mark.skipif(
    PDF is None,
    reason="vidaus_apdaila.pdf not found — set SAMATU_TEST_PDF or place "
           "at ~/Desktop/test_pdfs/vidaus_apdaila.pdf",
)


@pytest.mark.integration
def test_render_returns_real_page_size():
    page = render_page(PDF.read_bytes(), page_idx=0, dpi=100)
    assert page.ndim == 2
    assert page.shape[0] > 200 and page.shape[1] > 200


@pytest.mark.integration
def test_match_template_finds_self_on_real_pdf():
    """A template cropped from the page MUST match itself with very
    high confidence. Catches regressions in the matcher (e.g. wrong
    correlation method, broken NMS) without depending on what
    symbols actually exist on the page."""
    page = render_page(PDF.read_bytes(), page_idx=0, dpi=100)
    h, w = page.shape
    # 30×30 patch from somewhere safely inside the page
    template = page[h // 2:h // 2 + 30, w // 2:w // 2 + 30]
    matches = find_similar_symbols(page, template, threshold=0.95)
    assert len(matches) >= 1
    # The self-match should always be present at near-perfect confidence
    assert max(m["confidence"] for m in matches) >= 0.99

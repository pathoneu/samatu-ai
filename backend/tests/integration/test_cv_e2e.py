"""End-to-end integration: real LT PDF → CV layer returns sensible
results. Acceptance gate — a regression in cv_match / cv_wand /
cv_render_cache should break this test.

Marked `integration` so a regular `pytest` run skips it; CI invokes
explicitly with `pytest -m integration`."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from extractor.cv_match import find_similar_symbols  # noqa: E402
from extractor.cv_render_cache import render_page  # noqa: E402
from extractor.cv_wand import suggest_room_polygon  # noqa: E402

PDF = Path(__file__).resolve().parents[2].joinpath(
    "test_pdfs/vidaus_apdaila.pdf"
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


@pytest.mark.integration
def test_magic_wand_does_not_explode_on_real_pdf():
    """Wand can legitimately return None (click on a wall) but must
    NEVER produce a polygon spanning the full page (a sign that
    morphology + flood-fill leaked across the whole drawing)."""
    page = render_page(PDF.read_bytes(), page_idx=0, dpi=100)
    h, w = page.shape
    polygon = suggest_room_polygon(
        page, click_x=w // 2, click_y=h // 2, close_kernel=11,
    )
    if polygon is not None:
        import cv2
        import numpy as np
        area = cv2.contourArea(np.array(polygon, dtype=np.int32))
        assert area < (w * h * 0.9), (
            f"polygon area {area} ≥ 90% of page {w * h} — flood-fill leaked"
        )

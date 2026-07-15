"""Fix 3 — Per-page pixel/dimension cap on PDF upload (render-OOM guard).

_validate_pdf_upload bounded total size + page count but nothing bounded
per-page mediabox dimensions before Poppler rasterizes. _check_page_dimensions
rejects any page whose single dimension > 60 in, or whose area implies > ~200 MP
at 300 DPI. A0 (the largest standard sheet) must pass; giant bombs must not.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from main import _check_page_dimensions


def test_a3_passes():
    _check_page_dimensions([(842, 1191)])  # A3 in points — no raise


def test_a0_passes():
    # A0 = 841×1189 mm ≈ 2384×3370 pt ≈ 139 MP at 300 DPI — must be allowed
    _check_page_dimensions([(2384, 3370)])


def test_giant_single_dimension_rejected():
    with pytest.raises(HTTPException) as ei:
        _check_page_dimensions([(842, 1191), (50000, 50000)])
    assert ei.value.status_code == 413


def test_area_bomb_rejected():
    # Both dims < 4320 pt but area (16e6 pt²) exceeds the ~200 MP cap
    with pytest.raises(HTTPException) as ei:
        _check_page_dimensions([(4000, 4000)])
    assert ei.value.status_code == 413


def test_empty_and_none_are_noops():
    _check_page_dimensions([])
    _check_page_dimensions(None)


def test_malformed_entries_skipped():
    # A non-numeric / short tuple must not crash the pure helper
    _check_page_dimensions([("x", "y"), (None,), (842, 1191)])

"""Tests for the deterministic ceiling-height marker scanner."""
from __future__ import annotations

import io

from extractor.height_markers import (
    MAX_CEILING_M,
    MIN_CEILING_M,
    best_ceiling_candidate,
    scan_page_height_markers,
)


def _make_pdf_with_text(lines_per_page: list[list[str]]) -> bytes:
    """Build a minimal PDF whose text layer contains the supplied lines.

    Uses reportlab so the resulting PDF has a real text layer pdfplumber can
    extract. Each inner list is one page; each string is one line on that page.
    """
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    for page_lines in lines_per_page:
        y = 800
        for line in page_lines:
            c.drawString(72, y, line)
            y -= 16
        c.showPage()
    c.save()
    return buf.getvalue()


def test_finds_plus_3000_marker():
    pdf = _make_pdf_with_text([
        ["PJUVIS A-A", "+3.000  Lubu lygis", "+0.000  Grindu lygis"],
    ])
    markers = scan_page_height_markers(pdf, page_nrs=(1,))
    values = sorted(m["value_m"] for m in markers)
    # 0.000 is below MIN_CEILING_M and is filtered out
    assert values == [3.0]


def test_handles_lithuanian_comma_decimal():
    pdf = _make_pdf_with_text([
        ["+2,800 lubos"],
    ])
    markers = scan_page_height_markers(pdf, page_nrs=(1,))
    assert len(markers) == 1
    assert markers[0]["value_m"] == 2.8


def test_filters_out_implausible_heights():
    # +0.500 is below MIN, +6.000 is above MAX — both should be dropped
    pdf = _make_pdf_with_text([
        ["+0.500", "+3.200", "+6.000"],
    ])
    markers = scan_page_height_markers(pdf, page_nrs=(1,))
    values = [m["value_m"] for m in markers]
    assert values == [3.2]


def test_picks_largest_as_ceiling_candidate():
    pdf = _make_pdf_with_text([
        ["+2.400 sija", "+2.800 lubos", "+3.000 lubų plokštė"],
    ])
    markers = scan_page_height_markers(pdf, page_nrs=(1,))
    best = best_ceiling_candidate(markers)
    assert best is not None
    assert best["value_m"] == 3.0


def test_only_scans_requested_pages():
    pdf = _make_pdf_with_text([
        ["+3.000 page1"],
        ["+4.200 page2"],
    ])
    markers = scan_page_height_markers(pdf, page_nrs=(1,))
    assert all(m["page"] == 1 for m in markers)
    assert markers[0]["value_m"] == 3.0


def test_returns_empty_for_missing_pages():
    pdf = _make_pdf_with_text([["nothing here"]])
    markers = scan_page_height_markers(pdf, page_nrs=(99,))
    assert markers == []


def test_returns_empty_for_corrupted_pdf():
    markers = scan_page_height_markers(b"not a pdf", page_nrs=(1,))
    assert markers == []


def test_best_candidate_returns_none_for_empty_input():
    assert best_ceiling_candidate([]) is None


def test_min_max_constants_match_lt_residential_range():
    # Sanity check on the cutoffs in case future edits widen them
    # without re-reading the rationale in the module docstring.
    assert MIN_CEILING_M == 2.0
    assert MAX_CEILING_M == 4.5

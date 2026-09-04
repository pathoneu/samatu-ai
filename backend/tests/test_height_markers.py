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


# ── 2026-08-03: hallucinated-height class (romainiai "+37068794842") ──────
#
# The scanner used to run a SHADOWED, looser regex that matched a prefix of any
# long digit run, so a Lithuanian mobile number in a title block became a
# 3.706 m ceiling — the only "marker" in a 45-page document, and therefore the
# project-wide height. These tests pin both halves of the fix: the phone number
# is rejected, and every real marker style still reads.

def test_phone_number_is_not_a_ceiling_height():
    """+37068794842 must not parse as a ceiling height.

    This already held via the [2.0, 4.5] range check on the raw capture; the
    test pins it so a future "convert bare mm" change cannot silently reopen
    the hole.
    """
    pdf = _make_pdf_with_text([
        ["UAB Projektuotojas", "Tel. +37068794842", "el. p. info@example.lt"],
    ])
    markers = scan_page_height_markers(pdf, page_nrs=(1,))
    assert markers == []


def test_phone_number_does_not_beat_a_real_marker():
    """A real +3.000 on the same sheet must still win, unpolluted."""
    pdf = _make_pdf_with_text([
        ["Tel. +37068794842", "PJUVIS A-A", "+3.000 lubu lygis"],
    ])
    best = best_ceiling_candidate(scan_page_height_markers(pdf, page_nrs=(1,)))
    assert best is not None
    assert best["value_m"] == 3.0


def test_decimal_prefix_of_a_longer_run_is_not_a_marker():
    """The live hole: a drawing code whose first chars look like +3.706.

    Both the old strict pattern and the shadowing salvage pattern matched the
    PREFIX here and produced a 3.706 m ceiling. The token-boundary guard is
    what stops it.
    """
    pdf = _make_pdf_with_text([["Brezinio kodas +3.70612345 rev.B"]])
    assert scan_page_height_markers(pdf, page_nrs=(1,)) == []


def test_marker_immediately_followed_by_a_word_is_not_a_marker():
    pdf = _make_pdf_with_text([["kodas +3.400abc"]])
    assert scan_page_height_markers(pdf, page_nrs=(1,)) == []


def test_real_marker_followed_by_text_still_reads():
    pdf = _make_pdf_with_text([["+3.400 lubu plokste", "+2,800 lubos"]])
    values = sorted(m["value_m"]
                    for m in scan_page_height_markers(pdf, page_nrs=(1,)))
    assert values == [2.8, 3.4]


def test_mm_grid_predicate():
    from extractor.height_markers import marker_is_on_mm_grid
    assert marker_is_on_mm_grid(3.4) is True
    assert marker_is_on_mm_grid(2.82) is True     # objektas_d raw slab height
    assert marker_is_on_mm_grid(5.7) is True      # objektas_b double height
    assert marker_is_on_mm_grid(3.706) is False   # the phone number
    assert marker_is_on_mm_grid(None) is False


def test_salvage_regex_no_longer_shadows_the_scanner():
    """The salvage lane's looser pattern must live under its own name."""
    from extractor import height_markers as hm
    assert hm._HEIGHT_MARKER_RE.pattern != hm._HEIGHT_MARKER_TEXT_RE.pattern
    # …and the salvage pattern carries the same token-boundary guard.
    assert not hm._HEIGHT_MARKER_TEXT_RE.search("+37068794842")


def test_narrated_double_height_still_salvages():
    """objektas_b: 'dvigubo aukščio lubas (~5.7m)' must survive the guard."""
    from extractor.height_markers import salvage_heights_from_warnings
    rooms = [{"pavadinimas": "Svetainė/valgomasis/virtuvė"}]
    warnings = [{"level": "INFO", "message": (
        "Svetainė/valgomasis/virtuvė turi dvigubo aukščio lubas "
        "(~5.7m pagal vizualizacijas ir lubų planą)")}]
    out = salvage_heights_from_warnings(warnings, rooms)
    assert out.get("Svetainė/valgomasis/virtuvė") == 5.7


def test_narrated_bare_marker_still_salvages():
    """Objektas A-style narration '+3400 lubas' must survive the guard."""
    from extractor.height_markers import salvage_heights_from_warnings
    rooms = [{"pavadinimas": "Svetainė/virtuvė"}]
    warnings = [{"level": "INFO",
                 "message": "Svetainė/virtuvė turi +3400 lubas"}]
    out = salvage_heights_from_warnings(warnings, rooms)
    assert out.get("Svetainė/virtuvė") == 3.4


def test_narrated_phone_number_does_not_salvage():
    from extractor.height_markers import salvage_heights_from_warnings
    rooms = [{"pavadinimas": "Svetainė"}]
    warnings = [{"level": "INFO",
                 "message": "Svetainė — projektuotojo tel. +37068794842"}]
    assert salvage_heights_from_warnings(warnings, rooms) == {}


def test_min_max_constants_match_lt_residential_range():
    # Sanity check on the cutoffs in case future edits widen them
    # without re-reading the rationale in the module docstring.
    assert MIN_CEILING_M == 2.0
    assert MAX_CEILING_M == 4.5

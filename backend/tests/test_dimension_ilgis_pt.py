"""`ilgis_pt` — the drawn length of a string's dimension line, the very length its scale ratio used
(span less the stroke width: PDFium's bounds include the line caps, so the raw span runs one stroke
long). The viewer's „Patikrinti mastelį" card compares ilgis_pt × scale with the written value; on
objektas_h the raw span read 4–6 % long (+1,00 pt per string, measured 2026-10-16). Nothing in the
engine reads the key. Synthetic drawings only (reportlab lines of known width)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import dimension_sum as ds  # noqa: E402
from extractor import plan_dimensions as pdim  # noqa: E402
from extractor import sheet_alignment as sa  # noqa: E402
from tests.synthetic_plan import PT_PER_M, build_plan, two_rooms  # noqa: E402
from tests.test_dimension_sum import _room  # noqa: E402
from tests.test_slanted_dimensions import _cut_corner_room  # noqa: E402


def _line_backed(dims):
    return [d for d in dims if d.get("span_source") == "line"]


def test_every_line_backed_string_carries_the_length_its_scale_used():
    dims = pdim.read_dimension_strings(build_plan([two_rooms()]), pages=[1])
    backed = _line_backed(dims)
    assert len(backed) == 8
    for d in backed:
        assert d["ilgis_pt"] > 0
        assert abs(d["ilgis_pt"] * d["scale_m_per_pt"] / d["value_m"] - 1) < 0.005, d
        # the raw span is the line's bounds — never shorter than the drawn length
        assert d["span"][1] - d["span"][0] >= d["ilgis_pt"] - 0.01


def test_a_slanted_string_carries_its_line_length_too():
    dims = pdim.read_dimension_strings(build_plan([_cut_corner_room()]), pages=None)
    slanted = [d for d in dims if d.get("orientation") == "s"]
    assert slanted and all(d["span_source"] == "line" for d in slanted)
    for d in slanted:
        assert abs(d["ilgis_pt"] * d["scale_m_per_pt"] / d["value_m"] - 1) < 0.005, d


def test_the_length_reaches_the_walls_strings_on_the_room():
    pdf = build_plan([two_rooms()])
    dims = pdim.read_dimension_strings(pdf, pages=[1])
    rooms = [_room("01", 0.2, 0.2, 4.2, 3.2), _room("02", 4.4, 0.2, 7.4, 3.2)]
    ds.sum_perimeters(rooms, dims, sa.align_sheets(pdf, [1]), {1: 1 / PT_PER_M})
    eilutes = [e for r in rooms for s in r["_sienos"] for e in s["eilutes"]]
    assert len(eilutes) == 8
    for e in eilutes:
        assert e["ilgis_pt"] is not None
        assert abs(e["ilgis_pt"] / PT_PER_M / e["value_m"] - 1) < 0.005, e


def test_a_string_without_a_line_has_no_length():
    dims = pdim.read_dimension_strings(build_plan([two_rooms()]), pages=[1])
    assert all("ilgis_pt" not in d for d in dims if d.get("span_source") != "line")

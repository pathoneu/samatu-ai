"""A slanted wall's length is WRITTEN along it like any other — on a slanted dimension line.

objektas_h (2026-09-21): the wall-painting plan writes „2060" along the bedroom's slanted wall and
„1526" along the fireplace corner of the living room, each on its own hairline. The string reader
knew only horizontal and vertical text, so both rooms stayed „N iš M sienų be matmens (1 įstriža —
įstrižų matmenų dar neskaitau)" and their perimeters an estimate.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import dimension_sum as ds  # noqa: E402
from extractor.plan_dimensions import read_dimension_strings  # noqa: E402
from extractor.sheet_alignment import align_sheets  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan  # noqa: E402

T = 0.2


def _cut_corner_room() -> Sheet:
    """A 4 × 3 m room whose top-right corner is cut by a slanted wall from (3, 0) to (4, 1) — 1,414 m —
    every wall carrying its length inside the room, the slanted one along its own slanted line."""
    walls = [(-T, -T, 3.0, 0.0), (-T, 3.0, 4.0 + T, 3.0 + T), (-T, 0.0, 0.0, 3.0), (4.0, 1.0, 4.0 + T, 3.0)]
    o = 0.15
    k = o / math.sqrt(2)
    dims = [
        ("3000", 0.0, o, 3.0, o),                                   # top
        ("4000", 0.0, 3.0 - o, 4.0, 3.0 - o),                       # bottom
        ("3000", o, 0.0, o, 3.0),                                   # left
        ("2000", 4.0 - o, 1.0, 4.0 - o, 3.0),                       # right
        ("1414", 3.0 - k, 0.0 + k, 4.0 - k, 1.0 + k),               # the slanted wall, written along it
        ("1200", 1.0, 1.5, 2.2, 1.5), ("900", 1.0, 2.0, 1.9, 2.0),  # furniture, so the sheet has a scale to vote on
    ]
    return Sheet(walls=walls, dims=dims, badges=[("1", 1.5, 1.2)])


def _fx(m: float) -> float:
    return (60 + m * PT_PER_M) / 595.2756


def _fy(m: float) -> float:
    return (80 + m * PT_PER_M) / 841.8898


def test_a_number_written_along_a_slanted_line_is_read_with_its_line():
    dims = read_dimension_strings(build_plan([_cut_corner_room()]), pages=None)
    slanted = [d for d in dims if d.get("orientation") == "s"]
    assert [d["text"] for d in slanted] == ["1414"]
    d = slanted[0]
    assert d["value_m"] == 1.414 and d["span_source"] == "line" and d["page"] == 1
    (x0, y0), (x1, y1) = sorted(d["line"])
    k = 0.15 / math.sqrt(2)
    assert abs(x0 / 595.2756 - _fx(3.0 - k)) < 0.003 and abs(y0 / 841.8898 - _fy(0.0 + k)) < 0.003
    assert abs(x1 / 595.2756 - _fx(4.0 - k)) < 0.003 and abs(y1 / 841.8898 - _fy(1.0 + k)) < 0.003
    # the horizontal and vertical strings are what they were
    assert sorted(x["text"] for x in dims if x.get("orientation") in ("h", "v") and x.get("span_source") == "line") == \
        ["1200", "2000", "3000", "3000", "4000", "900"]


def test_a_slanted_number_without_a_line_of_its_length_is_not_a_dimension():
    sheet = _cut_corner_room()
    sheet.dims = [d for d in sheet.dims if d[0] != "1414"] + [("2900", 3.0 - 0.1, 0.1, 4.0 - 0.1, 1.1)]   # says 2,9 m over a 1,4 m line
    dims = read_dimension_strings(build_plan([sheet]), pages=None)
    assert [d for d in dims if d.get("orientation") == "s"] == []


def test_a_room_with_a_slanted_wall_is_summed_from_all_its_strings():
    pdf = build_plan([_cut_corner_room()])
    ring = [[_fx(0), _fy(0)], [_fx(3), _fy(0)], [_fx(4), _fy(1)], [_fx(4), _fy(3)], [_fx(0), _fy(3)]]
    room = {"nr": "01", "puslapio_nr": 1, "polygon_pct": ring, "polygon_source": "vektoriniai_konturai", "_konturas": {"page": 1}}
    dims = read_dimension_strings(pdf, pages=None)
    scale = {1: next(d["scale_m_per_pt"] for d in dims if d.get("scale_m_per_pt"))}
    out = ds.sum_perimeters([room], dims, align_sheets(pdf, [1]), scale)
    assert out["stated"] == ["01"], room.get("_perimetras_priezastis")
    assert room["perimetras_m"] == 13.41                            # 3 + 1,414 + 2 + 4 + 3
    slanted = next(w for w in room["_sienos"] if w["eilutes"] and w["eilutes"][0]["text"] == "1414")
    assert slanted["saltinis"] == "eilute" and slanted["ilgis_m"] == 1.414
    (ax, ay), (bx, by) = slanted["eilutes"][0]["line_pct"]
    assert 0 < min(ax, ay, bx, by) and max(ax, ay, bx, by) < 1 and ax != bx and ay != by


def test_a_slanted_wall_nobody_dimensioned_is_still_said_so():
    sheet = _cut_corner_room()
    sheet.dims = [d for d in sheet.dims if d[0] != "1414"]
    pdf = build_plan([sheet])
    ring = [[_fx(0), _fy(0)], [_fx(3), _fy(0)], [_fx(4), _fy(1)], [_fx(4), _fy(3)], [_fx(0), _fy(3)]]
    room = {"nr": "01", "puslapio_nr": 1, "polygon_pct": ring, "polygon_source": "vektoriniai_konturai", "_konturas": {"page": 1}}
    dims = read_dimension_strings(pdf, pages=None)
    scale = {1: next(d["scale_m_per_pt"] for d in dims if d.get("scale_m_per_pt"))}
    out = ds.sum_perimeters([room], dims, align_sheets(pdf, [1]), scale)
    assert out["blank"] == ["01"]
    assert room["_perimetras_priezastis"] == "1 iš 5 sienų be matmens (1 įstriža — jos ilgis plane neužrašytas)"

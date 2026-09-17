"""Plan sheets of one storey share the wall geometry; the alignment maps a
point on one sheet onto the base sheet. Synthetic only."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import sheet_alignment as sa  # noqa: E402
from tests.synthetic_plan import PT_PER_M, Sheet, build_plan, two_rooms  # noqa: E402


def test_identical_sheets_form_one_group_with_identity():
    a = two_rooms()
    b = two_rooms()
    b.dims = []                                           # a wall-painting plan: same walls, other strings
    al = sa.align_sheets(build_plan([a, b]), plan_pages=[1, 2])
    assert al["groups"] == [[1, 2]]
    t = al["transform"][2]
    assert t["base"] == 1 and abs(t["dx"]) < 1 and abs(t["dy"]) < 1 and abs(t["k"] - 1) < 0.01


def test_a_shifted_sheet_is_translated_onto_the_base():
    a = two_rooms()
    b = two_rooms()
    b.offset_m = (1.0, -0.5)                              # the same plan drawn 1 m right and 0,5 m up
    al = sa.align_sheets(build_plan([a, b]), plan_pages=[1, 2])
    assert al["groups"] == [[1, 2]]
    x, y = sa.to_base(al, 2, 300.0, 400.0)
    assert abs((x - 300.0) + 1.0 * PT_PER_M) < 1.5 and abs((y - 400.0) - 0.5 * PT_PER_M) < 1.5


def test_a_different_plan_is_its_own_group():
    a = two_rooms()
    c = Sheet(walls=[(0, 0, 3, 0.2), (0, 0, 0.2, 2), (0, 2, 3, 2.2), (2.8, 0, 3, 2.2)], badges=[("1", 1.5, 1.0)])
    al = sa.align_sheets(build_plan([a, c]), plan_pages=[1, 2])
    assert al["groups"] == [[1], [2]]
    assert al["transform"][2]["base"] == 2


def test_a_page_without_walls_is_left_alone():
    al = sa.align_sheets(build_plan([two_rooms(), Sheet()]), plan_pages=[1, 2])
    assert al["groups"] == [[1], [2]]
    assert sa.base_page(al, 2) == 2 and sa.to_base(al, 2, 10.0, 20.0) == (10.0, 20.0)


def test_a_reprint_at_another_scale_gets_a_scale_factor():
    a = two_rooms()
    b = two_rooms()
    b.scale = 0.5                                         # the same plan at 1:200
    al = sa.align_sheets(build_plan([a, b]), plan_pages=[1, 2])
    assert al["groups"] == [[1, 2]]
    assert abs(al["transform"][2]["k"] - 2.0) < 0.02

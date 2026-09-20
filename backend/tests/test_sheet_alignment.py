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


def test_another_storey_inside_the_same_outside_walls_is_not_the_same_plan():
    """Two floors of a house share the outside walls to the millimetre; their
    partitions differ. Strings of one floor must not be read for the rooms of
    the other — the walls themselves have to coincide, not only their box."""
    ground = two_rooms()
    upper = two_rooms()
    upper.walls = [w for w in upper.walls if abs(w[0] - 4.2) > 0.01]                # no partition at x = 4,2 m…
    upper.walls += [(0.2, 1.5, 7.4, 1.7), (2.0, 1.7, 2.2, 3.2), (5.0, 0.2, 5.2, 1.5)]   # …a corridor wall and two others instead
    al = sa.align_sheets(build_plan([ground, upper]), plan_pages=[1, 2])
    assert al["groups"] == [[1], [2]]


def test_a_point_goes_to_the_base_and_back():
    a = two_rooms()
    b = two_rooms()
    b.offset_m = (1.0, -0.5)
    b.scale = 0.5
    al = sa.align_sheets(build_plan([a, b]), plan_pages=[1, 2])
    x, y = sa.to_base(al, 2, 123.0, 234.0)
    back = sa.from_base(al, 2, x, y)
    assert abs(back[0] - 123.0) < 1e-6 and abs(back[1] - 234.0) < 1e-6
    assert sa.from_base(al, 1, 50.0, 60.0) == (50.0, 60.0)


# ── what objektas_g's sheets taught (2026-09-20) ─────────────────────────────
# Seven sheets draw ONE plan; two of them stayed alone: on one the plan is shifted AND a wall piece is
# missing at an edge (the wall boxes differ, so neither „as printed" nor box-onto-box fits), on the other a
# few partitions are drawn differently (overlap 0,89). Measured on four real sets: sheets of one plan
# overlap ≥ 0,89 once laid right, other plans ≤ 0,55 — nothing in between.

def test_a_shifted_sheet_whose_wall_box_differs_is_laid_corner_onto_corner():
    a = two_rooms()
    a.walls = a.walls + [(-0.8, 1.0, 0.0, 1.2)]           # a garden wall only the layout sheet draws: its box is wider
    b = two_rooms()
    b.offset_m = (0.7, -0.1)                              # the same plan, drawn elsewhere on its sheet
    al = sa.align_sheets(build_plan([a, b]), plan_pages=[1, 2])
    assert al["groups"] == [[1, 2]]
    t = al["transform"][2]
    assert abs(t["k"] - 1.0) < 1e-6
    assert abs(t["dx"] + 0.7 * PT_PER_M) < 0.5 and abs(t["dy"] - 0.1 * PT_PER_M) < 0.5


def test_a_sheet_that_draws_one_partition_more_is_still_the_same_plan():
    a = two_rooms()
    b = two_rooms()
    b.walls = b.walls + [(0.2, 1.6, 3.2, 1.8)]            # 0,6 m² of wall more: the solids overlap ≈ 0,88
    al = sa.align_sheets(build_plan([a, b]), plan_pages=[1, 2])
    assert al["groups"] == [[1, 2]]

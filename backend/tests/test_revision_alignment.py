"""extractor/revision_alignment.py — a new edition's sheet laid over the old one (synthetic plans only)."""
from __future__ import annotations

import pytest

from extractor.revision_alignment import from_old, match_revision, to_old
from tests.synthetic_plan import ORIGIN, PT_PER_M, Sheet, build_plan, pocket_and_room, two_rooms


def _moved_partition(sheet: Sheet, by_m: float) -> Sheet:
    """The same plan with the partition between the rooms moved — what a revision does."""
    walls = list(sheet.walls)
    for i in (5, 6):
        x0, y0, x1, y1 = walls[i]
        walls[i] = (x0 + by_m, y0, x1 + by_m, y1)
    return Sheet(walls=walls, badges=sheet.badges, offset_m=sheet.offset_m, scale=sheet.scale)


def _expected(offset_m, scale):
    """old = k · new + d for a sheet drawn with `offset_m` and `scale` (synthetic_plan._pt)."""
    k = 1 / scale
    dx = ORIGIN[0] - ORIGIN[0] / scale - offset_m[0] * PT_PER_M
    dy = ORIGIN[1] - ORIGIN[1] / scale - offset_m[1] * PT_PER_M
    return k, dx, dy


def test_shifted_and_scaled_revision_is_recovered_within_a_point():
    old = build_plan([two_rooms()])
    new_sheet = _moved_partition(two_rooms(), 0.5)
    new_sheet.offset_m, new_sheet.scale = (1.5, 2.0), 1.1
    new = build_plan([new_sheet])
    lapas = match_revision(old, new)[1]
    assert lapas["budas"] == "sienos" and lapas["old_page"] == 1
    assert lapas["sutapimas"] >= 0.6
    k, dx, dy = _expected((1.5, 2.0), 1.1)
    assert lapas["k"] == pytest.approx(k, abs=1e-3)
    assert lapas["dx"] == pytest.approx(dx, abs=1.0) and lapas["dy"] == pytest.approx(dy, abs=1.0)
    # the helpers are each other's inverse and land a wall corner where it is on the old sheet
    nx, ny = ORIGIN[0] + (0 + 1.5) * PT_PER_M * 1.1, ORIGIN[1] + (0 + 2.0) * PT_PER_M * 1.1
    ox, oy = to_old(lapas, nx, ny)
    assert (ox, oy) == pytest.approx(ORIGIN, abs=1.0)
    assert from_old(lapas, ox, oy) == pytest.approx((nx, ny), abs=1e-6)


def test_sheets_are_matched_by_their_walls_not_their_numbers():
    old = build_plan([two_rooms(), pocket_and_room()])
    shifted = pocket_and_room()
    shifted.offset_m = (0.8, 0.0)
    new = build_plan([shifted, two_rooms()])
    out = match_revision(old, new)
    assert (out[1]["old_page"], out[1]["budas"]) == (2, "sienos")
    assert (out[2]["old_page"], out[2]["budas"]) == (1, "sienos")
    assert out[2]["dx"] == pytest.approx(0.0, abs=1.0) and out[2]["k"] == pytest.approx(1.0)


def test_lookalike_sheet_keeps_its_own_number_and_names_the_better_one():
    # two storeys drawn alike: old 1 is the exact plan, old 2 the same with the partition 5 cm off
    old = build_plan([two_rooms(), _moved_partition(two_rooms(), 0.05)])
    new = build_plan([two_rooms(), two_rooms()])
    out = match_revision(old, new)
    assert out[1]["old_page"] == 1 and "geriausias" not in out[1]
    assert out[2]["old_page"] == 2
    assert out[2]["geriausias"]["old_page"] == 1 and out[2]["geriausias"]["sutapimas"] > out[2]["sutapimas"]


def test_unrelated_plan_and_wall_less_sheet_fall_back_to_the_sheet_edges():
    old = build_plan([two_rooms(), Sheet(title="FASADAS")])
    other = Sheet(walls=[(0, 0, 0.2, 9.0), (0, 0, 12.0, 0.2), (11.8, 0, 12.0, 9.0), (0, 8.8, 12.0, 9.0),
                         (3.0, 0.2, 3.2, 8.8), (6.0, 0.2, 6.2, 8.8), (9.0, 0.2, 9.2, 8.8)])
    new = build_plan([other, Sheet(title="FASADAS")])
    out = match_revision(old, new)
    assert out[1]["budas"] == "lapo_krastai" and out[1]["old_page"] == 1 and out[1]["sutapimas"] is None
    assert out[2] == {"old_page": 2, "k": 1.0, "dx": 0.0, "dy": 0.0, "sutapimas": None, "budas": "lapo_krastai"}


def test_more_new_sheets_than_old_ones_still_get_an_old_sheet():
    old = build_plan([two_rooms()])
    new = build_plan([two_rooms(), Sheet(title="NAUJAS LAPAS")])
    out = match_revision(old, new)
    assert out[1]["budas"] == "sienos"
    assert out[2]["old_page"] == 1 and out[2]["budas"] == "lapo_krastai"

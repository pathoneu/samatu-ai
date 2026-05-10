"""Week 2 — line_items.py unit tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from extractor.line_items import (  # noqa: E402
    opening_reveal_lm,
    opening_reveal_area_m2,
    plaster_corners_lm,
    hidroizoliacija_m2,
    hidden_door_count,
    hidden_door_frame_lm,
    silikonas_lm,
    plyteliu_45_suleidimas_lm,
    plyteliu_profiliai_lm,
)


def test_reveal_lm_three_sided_door():
    op = {"type": "door", "width_m": 0.9, "height_m": 2.05, "count": 1}
    # 2H + W = 2*2.05 + 0.9 = 5.0
    assert opening_reveal_lm([op]) == 5.0


def test_reveal_lm_three_sided_window_default_lt_mode():
    op = {"type": "window", "width_m": 1.2, "height_m": 1.5, "count": 1}
    # 2H + W = 4.2 (sill is separate line item in default LT mode)
    assert opening_reveal_lm([op]) == 4.2


def test_reveal_lm_four_sided_window_when_caller_disables_separate_sill():
    op = {"type": "window", "width_m": 1.2, "height_m": 1.5, "count": 1}
    # 2H + 2W = 5.4 when caller passes window_sides=4
    assert opening_reveal_lm([op], window_sides=4) == 5.4


def test_reveal_lm_invalid_window_sides_raises():
    with pytest.raises(ValueError):
        opening_reveal_lm([], window_sides=2)


def test_reveal_area_m2_uses_wall_thickness():
    op = {"type": "door", "width_m": 0.9, "height_m": 2.05, "count": 1}
    # 5.0 lm × 0.10 m wall thickness = 0.5 m²
    assert opening_reveal_area_m2([op], wall_thickness_m=0.10) == 0.5


def test_reveal_lm_handles_count_multiplier():
    op = {"type": "door", "width_m": 0.9, "height_m": 2.05, "count": 3}
    assert opening_reveal_lm([op]) == 15.0


def test_reveal_lm_uses_lt_defaults_when_dims_missing():
    op = {"type": "window"}
    # default 1.20 × 1.50 → 2*1.5 + 1.2 = 4.2
    assert opening_reveal_lm([op]) == 4.2


def test_plaster_corners_uses_polygon_when_available():
    room = {
        "ceiling_height_m": 2.7,
        "polygon_pct": [(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5)],  # 5 corners
    }
    assert plaster_corners_lm(room) == round(5 * 2.7, 3)


def test_plaster_corners_falls_back_to_four():
    room = {"ceiling_height_m": 2.82}
    assert plaster_corners_lm(room) == round(4 * 2.82, 3)


def test_hidroizoliacija_returns_m2_not_vnt():
    """Regression: previously this returned an integer count of wet rooms."""
    rooms = [
        {"id": "r1", "paskirtis": "vonia", "wet_room": True,
         "area_m2": 6.0, "perimeter_m": 10.0},
    ]
    total, warnings = hidroizoliacija_m2(rooms, default_wall_turnup_m=0.20)
    # floor 6 + perimeter 10 × 0.2 = 6 + 2 = 8 m²
    assert total == 8.0
    # Fallback triggers warning so UI can show provenance
    assert any("default" in w.lower() for w in warnings)


def test_hidroizoliacija_uses_explicit_zones_when_provided():
    rooms = [{
        "id": "r1", "paskirtis": "vonia", "wet_room": True,
        "area_m2": 6.0, "perimeter_m": 10.0,
        "hydro_zones": [
            {"surface": "floor", "area_m2": 6.0},
            {"surface": "wall", "area_m2": 4.4},
        ],
    }]
    total, warnings = hidroizoliacija_m2(rooms)
    assert total == 10.4
    assert warnings == []


def test_hidroizoliacija_zero_for_dry_rooms():
    rooms = [{"id": "r1", "paskirtis": "gyvenamoji", "area_m2": 20, "perimeter_m": 18}]
    total, _ = hidroizoliacija_m2(rooms)
    assert total == 0.0


def test_hidroizoliacija_picks_up_paskirtis_without_explicit_wet_room_flag():
    """`wet_room` flag is optional — paskirtis enum membership is the source of truth."""
    rooms = [{"id": "r1", "paskirtis": "wc", "area_m2": 2.0, "perimeter_m": 5.0}]
    total, _ = hidroizoliacija_m2(rooms)
    assert total == round(2.0 + 5.0 * 0.20, 3)


def test_hidden_door_count_separates_from_standard():
    openings = [
        {"type": "hidden_door", "count": 2},
        {"type": "door", "count": 3},
    ]
    assert hidden_door_count(openings) == 2


def test_hidden_door_frame_lm_three_sided():
    openings = [
        {"type": "hidden_door", "width_m": 0.9, "height_m": 2.05, "count": 2},
        {"type": "door", "count": 3},  # ignored
    ]
    # 2 × (2 * 2.05 + 0.9) = 2 × 5.0 = 10.0
    assert hidden_door_frame_lm(openings) == 10.0


def test_hidden_door_frame_zero_when_none():
    openings = [{"type": "door", "count": 5}]
    assert hidden_door_frame_lm(openings) == 0.0


def test_silikonas_inside_corners_plus_floor_perim_in_wet_rooms():
    room = {
        "id": "r1", "paskirtis": "vonia", "wet_room": True,
        "ceiling_height_m": 2.4, "perimeter_m": 10.0,
        "polygon_pct": [(0, 0), (0.4, 0), (0.4, 0.3), (0, 0.3)],  # 4 corners
        "tile_zones": [{"surface": "wall", "area_m2": 20}],
    }
    # 4 × 2.4 + 10 = 19.6
    assert silikonas_lm([room]) == 19.6


def test_silikonas_zero_when_no_tile_zones():
    room = {
        "id": "r1", "paskirtis": "vonia", "wet_room": True,
        "ceiling_height_m": 2.4, "perimeter_m": 10.0,
        "tile_zones": [],
    }
    assert silikonas_lm([room]) == 0.0


def test_45_suleidimas_only_from_explicit_zones():
    room = {
        "id": "r1", "paskirtis": "vonia",
        "tile_zones": [{"surface": "wall", "miter_45_lm": 4.8, "area_m2": 20}],
    }
    assert plyteliu_45_suleidimas_lm([room]) == 4.8


def test_45_suleidimas_zero_when_no_explicit_data():
    room = {"id": "r1", "paskirtis": "vonia", "tile_zones": []}
    assert plyteliu_45_suleidimas_lm([room]) == 0.0


def test_plyteliu_profiliai_lm_sums_explicit_edge_profiles():
    rooms = [{
        "id": "r1", "paskirtis": "vonia",
        "tile_zones": [
            {"surface": "wall", "edge_profile_lm": 3.5},
            {"surface": "wall", "edge_profile_lm": 1.2},
        ],
    }]
    assert plyteliu_profiliai_lm(rooms) == 4.7

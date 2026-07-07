"""Unit tests for extractor.geometry_solver."""

from __future__ import annotations

import math

import pytest

from extractor.geometry_solver import (
    snap_to_orthogonal,
    snap_room_walls_to_orthogonal,
    enforce_parallel_walls,
    walk_polygon,
    close_polygon,
    solve_room,
    DEFAULT_ANGLE_TOLERANCE_DEG,
)


# ── snap_to_orthogonal ────────────────────────────────────────────────────────
@pytest.mark.parametrize("input_deg,expected", [
    (0.0,    0.0),
    (1.5,    0.0),
    (-1.5,   0.0),           # wraps to 358.5 → snaps to 360→0
    (89.0,   90.0),
    (91.0,   90.0),
    (180.0,  180.0),
    (179.0,  180.0),
    (270.5,  270.0),
    (358.5,  0.0),
    (45.0,   45.0),          # not within tolerance of any orthogonal target
    (5.0,    5.0),           # outside ±2°
])
def test_snap_to_orthogonal(input_deg, expected):
    assert snap_to_orthogonal(input_deg, tolerance_deg=2.0) == pytest.approx(expected)


def test_snap_room_walls_returns_new_dict():
    angles = {"w1": 1.5, "w2": 89.5, "w3": 5.0}
    out = snap_room_walls_to_orthogonal(angles, tolerance_deg=2.0)
    assert out == {"w1": 0.0, "w2": 90.0, "w3": 5.0}
    # original untouched
    assert angles["w1"] == 1.5


# ── enforce_parallel_walls ────────────────────────────────────────────────────
def test_parallel_walls_within_tolerance_get_averaged():
    # Two horizontal walls, lengths 3100 and 3110 (diff <1%) → averaged
    lengths = {"w1": 3100.0, "w2": 4200.0, "w3": 3110.0, "w4": 4200.0}
    angles  = {"w1": 0.0,    "w2": 90.0,   "w3": 180.0,  "w4": 270.0}
    out = enforce_parallel_walls(lengths, angles, tolerance_pct=1.0)
    assert out["w1"] == pytest.approx(3105.0)
    assert out["w3"] == pytest.approx(3105.0)
    # parallel vertical walls already equal
    assert out["w2"] == 4200.0
    assert out["w4"] == 4200.0


def test_parallel_walls_outside_tolerance_left_alone():
    lengths = {"w1": 3100.0, "w3": 3200.0}    # 3.2% spread
    angles  = {"w1": 0.0,    "w3": 180.0}
    out = enforce_parallel_walls(lengths, angles, tolerance_pct=1.0)
    assert out["w1"] == 3100.0
    assert out["w3"] == 3200.0


def test_parallel_walls_group_of_three():
    # Three parallel walls all within 1% → averaged
    lengths = {"a": 1000.0, "b": 1005.0, "c": 1003.0}
    angles  = {"a": 0.0,    "b": 0.0,    "c": 180.0}
    out = enforce_parallel_walls(lengths, angles, tolerance_pct=1.0)
    avg = (1000 + 1005 + 1003) / 3
    for k in out:
        assert out[k] == pytest.approx(avg)


# ── walk + closure ────────────────────────────────────────────────────────────
def test_walk_polygon_rectangular_room_closes():
    """3000×4000 mm rectangle starting at (0,0) going E,N,W,S returns to origin."""
    poly = ["w1", "w2", "w3", "w4"]
    lengths = {"w1": 3000.0, "w2": 4000.0, "w3": 3000.0, "w4": 4000.0}
    angles  = {"w1": 0.0,    "w2": 90.0,   "w3": 180.0,  "w4": 270.0}
    pts = walk_polygon(poly, lengths, angles, (0.0, 0.0))
    assert pts[0] == (0.0, 0.0)
    assert pts[-1] == pytest.approx((0.0, 0.0), abs=1e-6)


def test_close_polygon_absorbs_small_gap():
    """Same rectangle but the south wall is 50mm short → closure should scale it."""
    poly = ["w1", "w2", "w3", "w4"]
    lengths = {"w1": 3000.0, "w2": 4000.0, "w3": 3000.0, "w4": 3950.0}
    angles  = {"w1": 0.0,    "w2": 90.0,   "w3": 180.0,  "w4": 270.0}
    out, report = close_polygon(poly, lengths, angles, (0.0, 0.0),
                                max_closure_mm=200.0, max_adjust_pct=5.0)
    assert report.gap_mm == pytest.approx(50.0)
    assert report.corrected is True
    pts2 = walk_polygon(poly, out, angles, (0.0, 0.0))
    assert math.hypot(pts2[-1][0] - pts2[0][0], pts2[-1][1] - pts2[0][1]) < 1.0


def test_close_polygon_refuses_when_gap_too_big():
    """A 500 mm gap on a 4000 mm wall is too large to silently absorb."""
    poly = ["w1", "w2", "w3", "w4"]
    lengths = {"w1": 3000.0, "w2": 4000.0, "w3": 3000.0, "w4": 3500.0}
    angles  = {"w1": 0.0,    "w2": 90.0,   "w3": 180.0,  "w4": 270.0}
    out, report = close_polygon(poly, lengths, angles, (0.0, 0.0),
                                max_closure_mm=200.0)
    # gap > max_closure_mm → no correction, original returned
    assert out == lengths
    assert report.corrected is False


def test_close_polygon_refuses_when_per_wall_pct_too_large():
    """Vertical span 4000+4000, dy gap forced to 250 → ~3.1% per wall, exceeds 2%."""
    poly = ["w1", "w2", "w3", "w4"]
    lengths = {"w1": 3000.0, "w2": 4000.0, "w3": 3000.0, "w4": 3750.0}
    angles  = {"w1": 0.0,    "w2": 90.0,   "w3": 180.0,  "w4": 270.0}
    _, report = close_polygon(poly, lengths, angles, (0.0, 0.0),
                              max_closure_mm=500.0, max_adjust_pct=2.0)
    assert report.corrected is False


# ── solve_room (composition) ──────────────────────────────────────────────────
def test_solve_room_pipeline_full():
    """A jitter-y rectangular room: angles slightly off-axis, lengths slightly
    asymmetric. solve_room should snap, average, close."""
    room = {
        "id": "r1",
        "polygon_walls": ["w1", "w2", "w3", "w4"],
        "wall_lengths_mm": {"w1": 3100.0, "w2": 4000.0, "w3": 3095.0, "w4": 4000.0},
        "wall_angles_deg": {"w1": 1.0,    "w2": 89.0,   "w3": 181.0,  "w4": 271.0},
        "start_vertex_xy_mm": (0.0, 0.0),
    }
    out = solve_room(room)
    # Angles snapped
    assert out["wall_angles_deg"] == {"w1": 0.0, "w2": 90.0, "w3": 180.0, "w4": 270.0}
    # Parallel walls equalised
    assert out["wall_lengths_mm"]["w1"] == out["wall_lengths_mm"]["w3"]
    assert out["wall_lengths_mm"]["w2"] == out["wall_lengths_mm"]["w4"]
    # Closure metadata present
    assert "_geometry_solver" in out
    # No closure correction needed after parallel-equality on this synthetic room
    pts = walk_polygon(
        out["polygon_walls"], out["wall_lengths_mm"], out["wall_angles_deg"], (0.0, 0.0)
    )
    assert math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]) < 1.0

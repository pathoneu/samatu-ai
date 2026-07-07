"""Unit tests for detect_shared_walls + attach_partition_counts."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.geometry_solver import (
    detect_shared_walls, attach_partition_counts,
    _segments_overlap_collinear,
)


def test_segments_overlap_collinear_horizontal_overlap():
    # Two horizontal segments at the same y level with x-overlap → True
    a = ((0.0, 1000.0), (3000.0, 1000.0))
    b = ((2000.0, 1010.0), (5000.0, 1010.0))   # 10mm vertical offset, well under tol
    assert _segments_overlap_collinear(a, b, tol_mm=100.0) is True


def test_segments_overlap_collinear_horizontal_no_overlap():
    a = ((0.0, 1000.0), (1000.0, 1000.0))
    b = ((2000.0, 1000.0), (3000.0, 1000.0))   # gap, no overlap
    assert _segments_overlap_collinear(a, b, tol_mm=100.0) is False


def test_segments_not_collinear():
    # Different y planes
    a = ((0.0, 0.0), (1000.0, 0.0))
    b = ((0.0, 5000.0), (1000.0, 5000.0))
    assert _segments_overlap_collinear(a, b, tol_mm=100.0) is False


def test_two_adjacent_rectangles_share_one_wall():
    """Two side-by-side rectangles share one common vertical wall."""
    # Room A: 4000x3000 rectangle at origin
    room_a = {
        "id": "A",
        "polygon_walls": ["aw1", "aw2", "aw3", "aw4"],
        "wall_lengths_mm": {"aw1": 4000, "aw2": 3000, "aw3": 4000, "aw4": 3000},
        "wall_angles_deg": {"aw1": 0, "aw2": 90, "aw3": 180, "aw4": 270},
        "start_vertex_xy_mm": (0.0, 0.0),
    }
    # Room B: 4000x3000 rectangle starting at x=4000 (shares the east wall of A)
    room_b = {
        "id": "B",
        "polygon_walls": ["bw1", "bw2", "bw3", "bw4"],
        "wall_lengths_mm": {"bw1": 4000, "bw2": 3000, "bw3": 4000, "bw4": 3000},
        "wall_angles_deg": {"bw1": 0, "bw2": 90, "bw3": 180, "bw4": 270},
        "start_vertex_xy_mm": (4000.0, 0.0),
    }
    counts = detect_shared_walls([room_a, room_b])
    assert counts["A"] == 1
    assert counts["B"] == 1


def test_three_rooms_in_a_row_middle_has_two_partitions():
    """Three rectangles side-by-side. The middle room shares walls with both
    neighbours; outer rooms share one each."""
    rooms = []
    for i, rid in enumerate(("A", "B", "C")):
        rooms.append({
            "id": rid,
            "polygon_walls": [f"{rid}w1", f"{rid}w2", f"{rid}w3", f"{rid}w4"],
            "wall_lengths_mm": {f"{rid}w1": 3000, f"{rid}w2": 3000, f"{rid}w3": 3000, f"{rid}w4": 3000},
            "wall_angles_deg": {f"{rid}w1": 0, f"{rid}w2": 90, f"{rid}w3": 180, f"{rid}w4": 270},
            "start_vertex_xy_mm": (i * 3000.0, 0.0),
        })
    counts = detect_shared_walls(rooms)
    assert counts["A"] == 1
    assert counts["B"] == 2
    assert counts["C"] == 1


def test_attach_partition_counts_populates_room_field():
    rooms = [
        {"id": "A", "polygon_walls": [], "wall_lengths_mm": {}, "wall_angles_deg": {}},
        {"id": "B", "polygon_walls": [], "wall_lengths_mm": {}, "wall_angles_deg": {}},
    ]
    attach_partition_counts(rooms, {"A": 3, "B": 2})
    assert rooms[0]["n_partition_walls"] == 3
    assert rooms[1]["n_partition_walls"] == 2


def test_no_shared_walls_when_polygons_not_translated():
    """If all rooms start at (0,0), their walls overlap artificially. Document
    the limitation: detect_shared_walls is only meaningful when each room's
    start_vertex_xy_mm is in a shared coordinate frame."""
    room_a = {
        "id": "A",
        "polygon_walls": ["aw1", "aw2", "aw3", "aw4"],
        "wall_lengths_mm": {"aw1": 3000, "aw2": 3000, "aw3": 3000, "aw4": 3000},
        "wall_angles_deg": {"aw1": 0, "aw2": 90, "aw3": 180, "aw4": 270},
        "start_vertex_xy_mm": (0.0, 0.0),
    }
    room_b = {
        "id": "B",
        "polygon_walls": ["bw1", "bw2", "bw3", "bw4"],
        "wall_lengths_mm": {"bw1": 3000, "bw2": 3000, "bw3": 3000, "bw4": 3000},
        "wall_angles_deg": {"bw1": 0, "bw2": 90, "bw3": 180, "bw4": 270},
        "start_vertex_xy_mm": (0.0, 0.0),  # SAME ORIGIN
    }
    counts = detect_shared_walls([room_a, room_b])
    # With the same origin the polygons overlap completely → all 4 walls share
    # collinear positions. This is the documented failure mode (we expect the
    # caller to translate before calling).
    assert counts["A"] >= 1
    assert counts["B"] >= 1

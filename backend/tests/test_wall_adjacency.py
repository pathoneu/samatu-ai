"""Sprint 2 wall_adjacency: deterministic shared-edge detection from polygon_pct."""
import pytest
from extractor.wall_adjacency import (
    polygon_to_segments, segments_overlap_length, shared_edges_between,
    apply_shared_edges,
)


def test_polygon_to_segments_closes_polygon():
    poly = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    segs = polygon_to_segments(poly)
    assert len(segs) == 4
    # last segment closes back to first vertex
    assert segs[-1][1] == (0.0, 0.0)


def test_segments_overlap_length_collinear_full():
    # Two segments share a full edge along x=0
    a = ((0.0, 0.0), (0.0, 1.0))
    b = ((0.0, 1.0), (0.0, 0.0))  # reversed
    assert segments_overlap_length(a, b) == pytest.approx(1.0)


def test_segments_overlap_length_partial():
    # a covers y=0..1, b covers y=0.5..1.5 → overlap is 0.5
    a = ((0.0, 0.0), (0.0, 1.0))
    b = ((0.0, 0.5), (0.0, 1.5))
    assert segments_overlap_length(a, b) == pytest.approx(0.5)


def test_segments_overlap_length_non_collinear_zero():
    # Different x-coords → not collinear
    a = ((0.0, 0.0), (0.0, 1.0))
    b = ((0.1, 0.0), (0.1, 1.0))
    assert segments_overlap_length(a, b) == 0.0


def test_segments_overlap_length_perpendicular_zero():
    a = ((0.0, 0.0), (1.0, 0.0))   # horizontal
    b = ((0.5, -0.5), (0.5, 0.5))  # vertical
    assert segments_overlap_length(a, b) == 0.0


def test_shared_edges_between_two_adjacent_rooms():
    # Room A: unit square at x=0..1, y=0..1
    # Room B: unit square at x=1..2, y=0..1 (shares right edge of A)
    a = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    b = [(1.0, 0.0), (1.0, 1.0), (2.0, 1.0), (2.0, 0.0)]
    shared = shared_edges_between(a, b)
    assert shared == pytest.approx(1.0)


def test_shared_edges_between_disjoint_rooms_zero():
    a = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    b = [(2.0, 0.0), (2.0, 1.0), (3.0, 1.0), (3.0, 0.0)]
    assert shared_edges_between(a, b) == 0.0


def test_shared_edges_partial_overlap():
    # B sticks out half a unit past A's edge
    a = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
    b = [(1.0, 0.5), (1.0, 1.5), (2.0, 1.5), (2.0, 0.5)]
    assert shared_edges_between(a, b) == pytest.approx(0.5)


def test_apply_shared_edges_subtracts_half_per_pair():
    # Two adjacent rooms each with naive perimetras = 4 (unit square scaled to 5m × 5m page).
    # Page is 10m × 10m, so 1 pct unit = 10m. Each side of unit square = 1 pct = 10m.
    # Naive perimetras_m for each room = 4 × (1 pct × 10m/pct) = 40m? No — too coarse.
    # Use a smaller example: page 1m × 1m, each room is 0.5×0.5 pct, adjacent.
    rooms = [
        {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 0.5), (0.5, 0.5), (0.5, 0.0)],
         "perimetras_m": 2.0},  # 4 sides × 0.5 page-pct × 1m/page-pct = 2m
        {"name": "B", "polygon_pct": [(0.5, 0.0), (0.5, 0.5), (1.0, 0.5), (1.0, 0.0)],
         "perimetras_m": 2.0},
    ]
    out = apply_shared_edges(rooms, page_width_m=1.0, page_height_m=1.0)
    # They share a 0.5 pct edge = 0.5m. Each room loses HALF (0.25m) per shared edge.
    # → corrected perimetras = 2.0 - 0.25 = 1.75 each.
    assert out[0]["perimetras_m"] == pytest.approx(1.75)
    assert out[1]["perimetras_m"] == pytest.approx(1.75)
    assert out[0]["perimetras_saltinis"] == "polygon_adjacency"
    assert out[0]["perimetras_orig_m"] == pytest.approx(2.0)


def test_apply_shared_edges_skips_when_polygon_missing():
    rooms = [
        {"name": "A", "polygon_pct": None, "perimetras_m": 2.0},
        {"name": "B", "polygon_pct": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
         "perimetras_m": 4.0},
    ]
    out = apply_shared_edges(rooms, page_width_m=1.0, page_height_m=1.0)
    # No corrections applied (any missing polygon → bail entirely; spec §10 fallback).
    assert out[0]["perimetras_m"] == 2.0
    assert out[1]["perimetras_m"] == 4.0
    assert out[0].get("perimetras_saltinis") != "polygon_adjacency"


def test_apply_shared_edges_anisotropic_page_dimensions():
    # Page is 2m wide × 1m tall. The horizontal edge (Δx=1.0 pct) maps to 2m,
    # vertical edge (Δy=1.0 pct) maps to 1m. Apply_shared_edges must use the
    # correct axis scale, not a single page-extent.
    rooms = [
        {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 1.0), (0.5, 1.0), (0.5, 0.0)],
         "perimetras_m": 6.0},  # 0.5*2 + 1*1 + 0.5*2 + 1*1 = 4 — but say Vision said 6
        {"name": "B", "polygon_pct": [(0.5, 0.0), (0.5, 1.0), (1.0, 1.0), (1.0, 0.0)],
         "perimetras_m": 6.0},
    ]
    out = apply_shared_edges(rooms, page_width_m=2.0, page_height_m=1.0)
    # Shared edge is vertical (axis "v") at x=0.5, length=1.0 pct → 1.0m metric.
    # Each room loses half = 0.5m.
    assert out[0]["perimetras_m"] == pytest.approx(5.5)
    assert out[1]["perimetras_m"] == pytest.approx(5.5)

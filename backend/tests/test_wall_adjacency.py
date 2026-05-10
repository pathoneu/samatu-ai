"""Sprint 2 wall_adjacency: deterministic shared-edge detection from polygon_pct.

2026-05-10 (Week 1 Task 1.4): tests that lock the LEGACY half-subtract
behavior must explicitly enable `ENABLE_LEGACY_HALF_SUBTRACT=1` and reload
the module so the runtime flag re-reads from env. Default behavior leaves
`perimetras_m` unchanged because interior finishes need both wall faces.
"""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from extractor.wall_adjacency import (
    polygon_to_segments, segments_overlap_length, shared_edges_between,
    apply_shared_edges,
)


def _reload_legacy_on():
    for modname in ("extractor.wall_adjacency", "backend.extractor.wall_adjacency"):
        if modname in sys.modules:
            importlib.reload(sys.modules[modname])


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


def test_apply_shared_edges_subtracts_half_per_pair(monkeypatch):
    """Locks the LEGACY half-subtract path. Default behavior leaves
    `perimetras_m` unchanged (Week 1 Task 1.4)."""
    monkeypatch.setenv("ENABLE_LEGACY_HALF_SUBTRACT", "1")
    _reload_legacy_on()
    from extractor.wall_adjacency import apply_shared_edges as _apply
    rooms = [
        {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 0.5), (0.5, 0.5), (0.5, 0.0)],
         "perimetras_m": 2.0},
        {"name": "B", "polygon_pct": [(0.5, 0.0), (0.5, 0.5), (1.0, 0.5), (1.0, 0.0)],
         "perimetras_m": 2.0},
    ]
    out = _apply(rooms, page_width_m=1.0, page_height_m=1.0)
    # Shared 0.5 pct edge = 0.5m. Each room loses HALF (0.25m) per shared edge.
    assert out[0]["perimetras_m"] == pytest.approx(1.75)
    assert out[1]["perimetras_m"] == pytest.approx(1.75)
    assert out[0]["perimetras_saltinis"] == "polygon_adjacency_legacy"
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


def test_apply_shared_edges_anisotropic_page_dimensions(monkeypatch):
    """Anisotropic page metric scaling — locked behind the LEGACY flag."""
    monkeypatch.setenv("ENABLE_LEGACY_HALF_SUBTRACT", "1")
    _reload_legacy_on()
    from extractor.wall_adjacency import apply_shared_edges as _apply
    rooms = [
        {"name": "A", "polygon_pct": [(0.0, 0.0), (0.0, 1.0), (0.5, 1.0), (0.5, 0.0)],
         "perimetras_m": 6.0},
        {"name": "B", "polygon_pct": [(0.5, 0.0), (0.5, 1.0), (1.0, 1.0), (1.0, 0.0)],
         "perimetras_m": 6.0},
    ]
    out = _apply(rooms, page_width_m=2.0, page_height_m=1.0)
    # Shared edge is vertical at x=0.5, length=1.0 pct → 1.0m metric.
    # Each room loses half = 0.5m.
    assert out[0]["perimetras_m"] == pytest.approx(5.5)
    assert out[1]["perimetras_m"] == pytest.approx(5.5)

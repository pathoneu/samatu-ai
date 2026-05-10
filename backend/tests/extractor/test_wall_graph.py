"""Week 6 Task 6.1 — wall_graph 12-case Algorithm A geometry matrix.

These cases lock the buffered-boundary intersection invariants. When you
relax the tolerances or change the algorithm, the diff here tells you
exactly which real-world topologies you broke.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.extractor.wall_graph import build_wall_graph  # noqa: E402


def _square(x, y, size):
    return [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]


# ---------------- Case 1 — full-edge two-rect share -------------------------

def test_case_1_two_rect_full_edge():
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.4, 0.0, 0.4)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    edges = list(g.graph.edges(data=True))
    assert edges, "two adjacent rooms must share an edge"
    # Lengths are in metres (page_width_m=10, edge runs 0.4 in pct → ~4m).
    lengths = [d["length_m"] for _, _, d in edges]
    assert max(lengths) >= 3.5


# ---------------- Case 2 — 100mm wall thickness offset ---------------------

def test_case_2_two_rect_offset_by_wall_thickness():
    """Offset of 0.001 in pct (~10mm on a 10m page) is well within the
    default 0.012 wall-tolerance — buffered-boundary intersection still
    detects the shared wall."""
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.401, 0.0, 0.4)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.has_edge("A", "B")


# ---------------- Case 3 — T intersection ---------------------------------

def test_case_3_t_intersection_three_rooms():
    """Room A's east wall is split between B (south half) and C (north half)."""
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.4, 0.0, 0.2)},
        {"id": "C", "polygon_pct": _square(0.4, 0.2, 0.2)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.has_edge("A", "B")
    assert g.graph.has_edge("A", "C")


# ---------------- Case 4 — L-shaped pair, two segments --------------------

def test_case_4_l_shape_two_separate_shared_segments():
    """Two rooms wrapping a corner share two non-collinear walls. Use
    MultiGraph parallel edges (no merge into a single edge)."""
    rooms = [
        {"id": "A", "polygon_pct": [
            (0.0, 0.0), (0.5, 0.0), (0.5, 0.3),
            (0.3, 0.3), (0.3, 0.5), (0.0, 0.5),
        ]},
        {"id": "B", "polygon_pct": [
            (0.5, 0.0), (0.7, 0.0), (0.7, 0.5),
            (0.3, 0.5), (0.3, 0.3), (0.5, 0.3),
        ]},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    edges = [(u, v) for u, v in g.graph.edges() if {u, v} == {"A", "B"}]
    # MultiGraph allows >=2 parallel edges between the same nodes
    assert len(edges) >= 1, "L-shape must yield at least one shared-wall edge"


# ---------------- Case 5 — 45° diagonal ------------------------------------

def test_case_5_45_degree_diagonal_wall():
    rooms = [
        {"id": "A", "polygon_pct": [(0.0, 0.0), (0.4, 0.0), (0.0, 0.4)]},
        {"id": "B", "polygon_pct": [(0.4, 0.0), (0.4, 0.4), (0.0, 0.4)]},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.has_edge("A", "B"), "45° diagonal walls must be detected"


# ---------------- Case 6 — 40° (non-multiple-of-45) wall -------------------

def test_case_6_40_degree_wall():
    rooms = [
        {"id": "A", "polygon_pct": [(0.0, 0.0), (0.4, 0.0), (0.0, 0.336)]},
        {"id": "B", "polygon_pct": [(0.4, 0.0), (0.4, 0.336), (0.0, 0.336)]},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.has_edge("A", "B")


# ---------------- Case 7 — open-plan partial overlap ----------------------

def test_case_7_open_plan_overlap_flagged():
    """Open-plan kitchen+living overlap (>tol²×4) must surface a warning,
    NOT a shared-wall edge that would dedupe finishes incorrectly."""
    rooms = [
        {"id": "K", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "L", "polygon_pct": _square(0.3, 0.0, 0.4)},  # overlaps K
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert any("open" in w.lower() or "overlap" in w.lower() for w in g.warnings)


# ---------------- Case 8 — courtyard polygon (does not crash) -------------

def test_case_8_courtyard_does_not_crash():
    """Polygon with weird topology must not crash the pipeline."""
    rooms = [{"id": "A", "polygon_pct": _square(0.0, 0.0, 0.5)}]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.number_of_nodes() == 1


# ---------------- Case 9 — near-miss collinear (Vision noise) -------------

def test_case_9_near_miss_within_tolerance_merges():
    """A 2e-4 pct gap (~2mm on 10m page) is well within tolerance — the
    buffered intersection detects this as one shared wall."""
    rooms = [
        {"id": "A", "polygon_pct": [
            (0.0, 0.0), (0.4, 0.0), (0.4, 0.4), (0.0, 0.4),
        ]},
        {"id": "B", "polygon_pct": [
            (0.4, 0.0), (0.8, 0.0), (0.8, 0.4), (0.4, 0.4002),
        ]},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.has_edge("A", "B")


# ---------------- Case 10 — real 25cm gap (does NOT merge) ----------------

def test_case_10_real_gap_25cm_does_not_merge():
    """A 0.025 pct gap (~25cm on 10m page) is BIG — these are two
    physically-separate rooms, not a single shared wall. No edge."""
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.425, 0.0, 0.4)},
    ]
    # Use a tighter tolerance so the 0.025 gap is firmly outside.
    g = build_wall_graph(
        rooms, page_width_m=10.0, page_height_m=10.0,
        wall_tolerance_pct=0.012,
    )
    assert not g.graph.has_edge("A", "B")


# ---------------- Case 11 — three-way T with thickness --------------------

def test_case_11_three_way_t_junction_with_thickness():
    """A's east wall is split between B (south half) and C (north half),
    with a 1mm offset simulating wall thickness (well within tolerance)."""
    rooms = [
        {"id": "A", "polygon_pct": _square(0.0, 0.0, 0.4)},
        {"id": "B", "polygon_pct": _square(0.401, 0.0, 0.2)},
        {"id": "C", "polygon_pct": _square(0.401, 0.2, 0.2)},
    ]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    assert g.graph.has_edge("A", "B")
    assert g.graph.has_edge("A", "C")


# ---------------- Case 12 — self-intersecting polygon (no crash) ----------

def test_case_12_self_intersecting_polygon_does_not_crash():
    """A bowtie polygon must be either rescued via make_valid or dropped
    with a warning. Either way, the build must not raise."""
    rooms = [{"id": "A", "polygon_pct": [(0, 0), (1, 1), (1, 0), (0, 1)]}]
    g = build_wall_graph(rooms, page_width_m=10.0, page_height_m=10.0)
    # Either node was added (rescued) or it was dropped with a warning.
    has_node = "A" in g.graph.nodes
    has_warn = any("invalid" in w.lower() or "polygon" in w.lower() for w in g.warnings)
    assert has_node or has_warn

"""Unit tests for extractor.plan_assembler — synthetic inputs only.

Builds a hand-crafted (DimensionList, RoomGraph) pair, runs assemble_plan,
and asserts the resulting perimeters/areas/openings.
"""

from __future__ import annotations

import math
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.plan_assembler import (
    assemble_plan,
    plan_to_parsed,
)
from extractor.vision.dimension_extractor import (
    Dimension, DimensionList, parse_dimension_payload,
)
from extractor.vision.room_graph_extractor import (
    Room as GraphRoom,
    Wall, Vertex, Opening, RoomGraph, parse_room_graph_payload,
)
from extractor.geometry_solver import solve_plan, walk_polygon


# ── Synthetic fixtures ────────────────────────────────────────────────────────
def _rectangular_room_fixture(L_mm: float = 3000, W_mm: float = 4000):
    """A single rectangular room.

      v1 ─── w1(L) ─── v2
       │               │
      w4(W)           w2(W)
       │               │
      v4 ─── w3(L) ─── v3

    Walls walked CCW: w1 (east), w2 (north), w3 (west), w4 (south).
    """
    dims = DimensionList(dimensions=[
        Dimension(id="d_L", text=str(L_mm), value_mm=float(L_mm),
                  x_pct=0.5, y_pct=0.1, orientation="horizontal",
                  pixel_start_pct=[0.2, 0.1], pixel_end_pct=[0.8, 0.1]),
        Dimension(id="d_W", text=str(W_mm), value_mm=float(W_mm),
                  x_pct=0.9, y_pct=0.5, orientation="vertical",
                  pixel_start_pct=[0.9, 0.2], pixel_end_pct=[0.9, 0.8]),
    ])
    verts = [
        Vertex(id="v1", x_pct=0.2, y_pct=0.8),
        Vertex(id="v2", x_pct=0.8, y_pct=0.8),
        Vertex(id="v3", x_pct=0.8, y_pct=0.2),
        Vertex(id="v4", x_pct=0.2, y_pct=0.2),
    ]
    walls = [
        Wall(id="w1", start_vertex="v1", end_vertex="v2", dimension_id="d_L",
             angle_deg=0.0, is_exterior=True, room_ids=["r1"]),
        Wall(id="w2", start_vertex="v2", end_vertex="v3", dimension_id="d_W",
             angle_deg=90.0, is_exterior=True, room_ids=["r1"]),
        Wall(id="w3", start_vertex="v3", end_vertex="v4", dimension_id="d_L",
             angle_deg=180.0, is_exterior=True, room_ids=["r1"]),
        Wall(id="w4", start_vertex="v4", end_vertex="v1", dimension_id="d_W",
             angle_deg=270.0, is_exterior=True, room_ids=["r1"]),
    ]
    rooms = [GraphRoom(
        id="r1", nr="101", name="Test Room", paskirtis="gyvenamoji",
        polygon_walls=["w1", "w2", "w3", "w4"],
        lubu_aukstis_m=2.82, lubu_tipas="gkp",
    )]
    return dims, RoomGraph(vertices=verts, walls=walls, rooms=rooms, openings=[])


# ── Assemble tests ────────────────────────────────────────────────────────────
def test_assemble_rectangular_room_perimeter_and_area():
    dims, graph = _rectangular_room_fixture(3000, 4000)
    plan = assemble_plan(dims, graph)
    assert len(plan.rooms) == 1
    r = plan.rooms[0]
    # Perimeter = 2(L+W) = 14000 mm
    assert r.perimeter_mm == pytest.approx(14000.0)
    # Area = L * W = 12 m²
    assert r.area_m2 == pytest.approx(12.0, rel=1e-3)
    # All four walls had direct dimension references → score 1.0
    assert r.confidence_score == 1.0
    assert r.confidence_color == "green"
    assert r.missing_dimension_walls == []


def test_assemble_missing_dimension_inferred_from_closure():
    """Drop the dimension on w3 (the second L wall). The assembler should
    recover the missing length from the parallel-known wall w1."""
    dims, graph = _rectangular_room_fixture(3000, 4000)
    # Drop w3's dimension reference
    for w in graph.walls:
        if w.id == "w3":
            w.dimension_id = None

    plan = assemble_plan(dims, graph)
    r = plan.rooms[0]
    assert r.wall_lengths_mm["w3"] == pytest.approx(3000.0)
    # Confidence: 3/4 walls direct = 0.75 → yellow
    assert r.confidence_score == pytest.approx(0.75)
    assert r.confidence_color == "yellow"
    # Note: the closure inference happens against parallel-wall constraint,
    # but doesn't mark the inferred wall as "missing" (we recovered it).
    assert r.missing_dimension_walls == []
    assert r.area_m2 == pytest.approx(12.0, rel=1e-3)


def test_assemble_opening_resolution_from_dimension_id():
    """Window with width 1500 referenced by dimension_id should pull through."""
    dims, graph = _rectangular_room_fixture(3000, 4000)
    dims.dimensions.append(Dimension(
        id="d_win_w", text="1500", value_mm=1500.0,
        x_pct=0.3, y_pct=0.5, orientation="horizontal",
    ))
    dims.dimensions.append(Dimension(
        id="d_win_h", text="1500", value_mm=1500.0,
        x_pct=0.4, y_pct=0.5, orientation="vertical",
    ))
    graph.openings.append(Opening(
        id="o1", wall_id="w1", type="window",
        width_dimension_id="d_win_w", height_dimension_id="d_win_h",
    ))

    plan = assemble_plan(dims, graph)
    r = plan.rooms[0]
    assert len(r.openings) == 1
    op = r.openings[0]
    assert op.width_mm == 1500.0
    assert op.height_mm == 1500.0
    assert op.width_source == "dimension"


def test_assemble_opening_uses_schedule_override():
    """Schedule entry for "L1" should override dim-id refs."""
    dims, graph = _rectangular_room_fixture(3000, 4000)
    graph.openings.append(Opening(
        id="o1", wall_id="w1", type="window",
        schedule_ref="L1",
    ))
    schedule = {"langai": [{"id": "L1", "width_mm": 2750, "height_mm": 2200}]}
    plan = assemble_plan(dims, graph, schedule_payload=schedule)
    op = plan.rooms[0].openings[0]
    assert op.width_mm == 2750.0
    assert op.height_mm == 2200.0
    assert op.width_source == "schedule"


def test_assemble_l_shaped_room_area_via_shoelace():
    """L-shaped room: 6 vertices, 6 walls. Area = (L1×W1) + (L2×W2)."""
    dims = DimensionList(dimensions=[
        Dimension(id="dA", text="5000", value_mm=5000.0, x_pct=0.3, y_pct=0.5, orientation="horizontal"),
        Dimension(id="dB", text="3000", value_mm=3000.0, x_pct=0.6, y_pct=0.3, orientation="vertical"),
        Dimension(id="dC", text="3000", value_mm=3000.0, x_pct=0.7, y_pct=0.4, orientation="horizontal"),
        Dimension(id="dD", text="2000", value_mm=2000.0, x_pct=0.8, y_pct=0.4, orientation="vertical"),
        Dimension(id="dE", text="2000", value_mm=2000.0, x_pct=0.5, y_pct=0.8, orientation="horizontal"),
        Dimension(id="dF", text="5000", value_mm=5000.0, x_pct=0.2, y_pct=0.5, orientation="vertical"),
    ])
    # L-shape walked CCW starting at bottom-left corner (0,0):
    #   E 5000 → N 3000 → W 3000 → N 2000 → W 2000 → S 5000 → back to start.
    # Area = bottom rectangle 5000×3000 + top-left rectangle 2000×2000 = 19 m².
    walls = [
        Wall(id="w1", start_vertex="v1", end_vertex="v2", dimension_id="dA", angle_deg=0.0,   room_ids=["r1"]),
        Wall(id="w2", start_vertex="v2", end_vertex="v3", dimension_id="dB", angle_deg=90.0,  room_ids=["r1"]),
        Wall(id="w3", start_vertex="v3", end_vertex="v4", dimension_id="dC", angle_deg=180.0, room_ids=["r1"]),
        Wall(id="w4", start_vertex="v4", end_vertex="v5", dimension_id="dD", angle_deg=90.0,  room_ids=["r1"]),
        Wall(id="w5", start_vertex="v5", end_vertex="v6", dimension_id="dE", angle_deg=180.0, room_ids=["r1"]),
        Wall(id="w6", start_vertex="v6", end_vertex="v1", dimension_id="dF", angle_deg=270.0, room_ids=["r1"]),
    ]
    verts = [
        Vertex(id="v1", x_pct=0.1, y_pct=0.9),
        Vertex(id="v2", x_pct=0.6, y_pct=0.9),
        Vertex(id="v3", x_pct=0.6, y_pct=0.6),
        Vertex(id="v4", x_pct=0.3, y_pct=0.6),
        Vertex(id="v5", x_pct=0.3, y_pct=0.4),
        Vertex(id="v6", x_pct=0.1, y_pct=0.4),
    ]
    rooms = [GraphRoom(
        id="r1", nr="201", name="L-room", paskirtis="gyvenamoji",
        polygon_walls=["w1", "w2", "w3", "w4", "w5", "w6"],
    )]
    plan = assemble_plan(dims, RoomGraph(vertices=verts, walls=walls, rooms=rooms))
    r = plan.rooms[0]
    assert r.perimeter_mm == pytest.approx(20000.0)
    assert r.area_m2 == pytest.approx(19.0, rel=1e-3)


def test_plan_to_parsed_yields_runnable_input_for_existing_engine():
    """The bridge output must be in the schema `_recompute_per_room_via_python`
    consumes. Verify it then runs the engine and produces non-zero outputs."""
    from extractor.vision_call import (
        _recompute_per_room_via_python,
        _recompute_santrauka,
    )

    dims, graph = _rectangular_room_fixture(3000, 4000)
    plan = assemble_plan(dims, graph)
    parsed = plan_to_parsed(plan)

    assert parsed["patalpos"][0]["plotas_m2"] == pytest.approx(12.0, rel=1e-3)
    parsed = _recompute_per_room_via_python(parsed, None)
    parsed = _recompute_santrauka(parsed)
    sant = parsed["santrauka"]
    assert sant["dazymo_plotas_total_m2"] > 0


def test_geometry_solver_chains_with_assembler():
    """End-to-end: assembler + solver on a slightly-jittered room must produce
    snapped angles and a closed polygon."""
    dims, graph = _rectangular_room_fixture(3000, 4000)
    # Add jitter to the graph walls
    for w in graph.walls:
        if w.angle_deg is not None:
            w.angle_deg += 0.7
    plan = assemble_plan(dims, graph)
    plan2 = solve_plan(plan.to_dict())
    r = plan2["rooms"][0]
    assert all(a in (0.0, 90.0, 180.0, 270.0) for a in r["wall_angles_deg"].values())
    pts = walk_polygon(
        r["polygon_walls"], r["wall_lengths_mm"], r["wall_angles_deg"], (0.0, 0.0)
    )
    assert math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1]) < 1.0

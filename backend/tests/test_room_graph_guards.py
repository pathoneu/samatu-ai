"""Tests for the room-graph guards added in 1.2: wall_type/curved fields,
degenerate-triangle filter, defensive parser."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.room_graph_extractor import (
    parse_room_graph_payload, _filter_degenerate_rooms,
    RoomGraph, Vertex, Wall, Room,
)


def _rect_room(rid: str, wall_angles=(0, 90, 180, 270)) -> dict:
    """Build a minimal rectangular-room payload."""
    return {
        "vertices": [
            {"id": f"{rid}_v1", "x_pct": 0.1, "y_pct": 0.9},
            {"id": f"{rid}_v2", "x_pct": 0.5, "y_pct": 0.9},
            {"id": f"{rid}_v3", "x_pct": 0.5, "y_pct": 0.5},
            {"id": f"{rid}_v4", "x_pct": 0.1, "y_pct": 0.5},
        ],
        "walls": [
            {"id": f"{rid}_w{i+1}",
             "start_vertex": f"{rid}_v{i+1}",
             "end_vertex":   f"{rid}_v{((i+1) % 4) + 1}",
             "angle_deg": float(wall_angles[i]),
             "room_ids": [rid]}
            for i in range(4)
        ],
        "rooms": [{
            "id": rid, "nr": rid, "name": "rect", "paskirtis": "gyvenamoji",
            "polygon_walls": [f"{rid}_w{i+1}" for i in range(4)],
        }],
        "openings": [],
    }


def test_wall_type_default_is_partition():
    payload = _rect_room("r1")
    rg = parse_room_graph_payload(payload)
    assert all(w.wall_type == "partition" for w in rg.walls)
    assert all(w.curved is False for w in rg.walls)


def test_wall_type_round_trips_known_values():
    payload = _rect_room("r1")
    payload["walls"][0]["wall_type"] = "load_bearing"
    payload["walls"][1]["wall_type"] = "exterior_envelope"
    payload["walls"][2]["wall_type"] = "PARTITION"  # case insensitive
    payload["walls"][3]["curved"] = True
    rg = parse_room_graph_payload(payload)
    types = [w.wall_type for w in rg.walls]
    assert types == ["load_bearing", "exterior_envelope", "partition", "partition"]
    assert rg.walls[3].curved is True


def test_unknown_wall_type_falls_back_to_partition():
    payload = _rect_room("r1")
    payload["walls"][0]["wall_type"] = "magnetic_levitation"
    rg = parse_room_graph_payload(payload)
    assert rg.walls[0].wall_type == "partition"


def test_degenerate_triangle_dropped():
    """3-wall polygon with one near-straight interior angle gets filtered."""
    rg = RoomGraph(
        vertices=[
            Vertex(id="v1", x_pct=0.1, y_pct=0.5),
            Vertex(id="v2", x_pct=0.9, y_pct=0.5),
            Vertex(id="v3", x_pct=0.5, y_pct=0.51),    # almost on the v1-v2 line
        ],
        walls=[
            # v1 → v2 east; v2 → v3 going back west-ish; v3 → v1 going west.
            # Interior at v2 will be ~180° (the polygon doubles back).
            Wall(id="w1", start_vertex="v1", end_vertex="v2", angle_deg=0.0),
            Wall(id="w2", start_vertex="v2", end_vertex="v3", angle_deg=181.0),
            Wall(id="w3", start_vertex="v3", end_vertex="v1", angle_deg=179.0),
        ],
        rooms=[Room(id="r1", nr="r1", name="x", paskirtis="x",
                    polygon_walls=["w1", "w2", "w3"])],
    )
    dropped = _filter_degenerate_rooms(rg)
    assert len(rg.rooms) == 0
    assert any("degenerate" in d or "walls" in d for d in dropped)


def test_polygon_with_fewer_than_3_walls_dropped():
    rg = RoomGraph(
        vertices=[Vertex(id="v1", x_pct=0, y_pct=0), Vertex(id="v2", x_pct=1, y_pct=0)],
        walls=[Wall(id="w1", start_vertex="v1", end_vertex="v2", angle_deg=0)],
        rooms=[Room(id="r1", nr="r1", name="x", paskirtis="x",
                    polygon_walls=["w1"])],
    )
    dropped = _filter_degenerate_rooms(rg)
    assert rg.rooms == []
    assert any("only 1 walls" in d for d in dropped)


def test_rectangle_with_clean_angles_kept():
    """A real axis-aligned rectangle survives the filter."""
    rg = parse_room_graph_payload(_rect_room("r1"))
    assert len(rg.rooms) == 1


def test_polygon_with_missing_angle_data_kept():
    """When angle_deg is None for any wall, we can't validate — leave the
    room for the assembler to handle. (Better to keep slightly-noisy rooms
    than to drop legitimate ones.)"""
    payload = _rect_room("r1")
    payload["walls"][0]["angle_deg"] = None
    rg = parse_room_graph_payload(payload)
    assert len(rg.rooms) == 1

"""Unit tests for adjacency_extractor parser + applier (no Vision calls)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.adjacency_extractor import (
    parse_adjacency_payload, apply_adjacency_to_rooms,
    AdjacencyPayload, RoomAdjacency, Adjacency,
)


def test_parse_minimal_payload():
    raw = {
        "rooms": [
            {
                "room_name": "Miegamasis", "room_nr": "101",
                "adjacent_rooms": [
                    {"to_room": "Koridorius", "to_room_nr": "105",
                     "shared_wall_count": 1, "wall_types": ["interior_partition"]},
                ],
                "exterior_wall_count": 2,
                "confidence": "high", "evidence": "north + east face outside",
            },
        ],
    }
    out = parse_adjacency_payload(raw)
    assert len(out.rooms) == 1
    r = out.rooms[0]
    assert r.room_nr == "101"
    assert r.n_partition_walls == 1
    assert r.exterior_wall_count == 2
    assert len(r.adjacent_rooms) == 1
    assert r.adjacent_rooms[0].to_room_nr == "105"


def test_parse_handles_missing_optional_fields():
    raw = {"rooms": [{"room_name": "X"}]}
    out = parse_adjacency_payload(raw)
    assert len(out.rooms) == 1
    r = out.rooms[0]
    assert r.room_nr is None
    assert r.adjacent_rooms == []
    assert r.exterior_wall_count == 0


def test_n_partition_walls_sums_correctly():
    r = RoomAdjacency(
        room_name="A", room_nr="1",
        adjacent_rooms=[
            Adjacency("B", "2", 1, ["interior_partition"]),
            Adjacency("C", "3", 2, ["interior_partition"]),  # L-shaped shared wall
            Adjacency("D", "4", 1, ["interior_partition"]),
        ],
        exterior_wall_count=1,
    )
    assert r.n_partition_walls == 4


def test_apply_adjacency_sets_partition_count_by_room_nr():
    rooms = [{"nr": "101", "pavadinimas": "Miegamasis", "elementai": []}]
    adj = AdjacencyPayload(rooms=[
        RoomAdjacency(room_name="Miegamasis", room_nr="101",
                      adjacent_rooms=[Adjacency("Koridorius", "105", 1, [])],
                      exterior_wall_count=2),
    ])
    summary = apply_adjacency_to_rooms(rooms, adj)
    assert rooms[0]["n_partition_walls"] == 1
    assert rooms[0]["_exterior_wall_count"] == 2
    assert summary["n_rooms_matched"] == 1
    assert summary["n_partition_walls_total"] == 1


def test_apply_adjacency_matches_by_name_when_nr_missing():
    rooms = [{"nr": None, "pavadinimas": "Miegamasis", "elementai": []}]
    adj = AdjacencyPayload(rooms=[
        RoomAdjacency(room_name="miegamasis", room_nr=None,
                      adjacent_rooms=[], exterior_wall_count=1),
    ])
    summary = apply_adjacency_to_rooms(rooms, adj)
    assert summary["n_rooms_matched"] == 1


def test_apply_adjacency_flags_windows_exterior_in_rooms_with_exterior_walls():
    rooms = [{
        "nr": "101", "pavadinimas": "Miegamasis",
        "elementai": [
            {"tipas": "langas", "kiekis": 2, "plotis_mm": 1200, "aukstis_mm": 1500},
            {"tipas": "duris",  "kiekis": 1, "plotis_mm": 900,  "aukstis_mm": 2100},
        ],
    }]
    adj = AdjacencyPayload(rooms=[
        RoomAdjacency(room_name="Miegamasis", room_nr="101",
                      adjacent_rooms=[], exterior_wall_count=2),
    ])
    summary = apply_adjacency_to_rooms(rooms, adj)
    window = rooms[0]["elementai"][0]
    door = rooms[0]["elementai"][1]
    assert window["_exterior"] is True
    assert "_exterior" not in door  # doors not touched by adjacency
    assert summary["n_windows_flagged_exterior"] == 2  # kiekis=2 counts


def test_apply_adjacency_marks_interior_window_when_no_exterior_walls():
    """Room with exterior_wall_count=0 → window must be interior (transom)."""
    rooms = [{
        "nr": "9", "pavadinimas": "Interior bath",
        "elementai": [{"tipas": "langas", "kiekis": 1,
                       "plotis_mm": 600, "aukstis_mm": 600}],
    }]
    adj = AdjacencyPayload(rooms=[
        RoomAdjacency(room_name="Interior bath", room_nr="9",
                      adjacent_rooms=[Adjacency("Hallway", "10", 1, [])],
                      exterior_wall_count=0),
    ])
    apply_adjacency_to_rooms(rooms, adj)
    assert rooms[0]["elementai"][0]["_exterior"] is False


def test_apply_adjacency_preserves_explicit_exterior_flag():
    """If a window already has _exterior=False (e.g. from doors_reader-like
    source), the adjacency pass must NOT overwrite it."""
    rooms = [{
        "nr": "1", "pavadinimas": "X",
        "elementai": [{"tipas": "langas", "kiekis": 1,
                       "plotis_mm": 1200, "aukstis_mm": 1500,
                       "_exterior": False}],
    }]
    adj = AdjacencyPayload(rooms=[
        RoomAdjacency(room_name="X", room_nr="1",
                      adjacent_rooms=[], exterior_wall_count=3),
    ])
    apply_adjacency_to_rooms(rooms, adj)
    # Explicit False preserved despite room having exterior walls
    assert rooms[0]["elementai"][0]["_exterior"] is False


def test_apply_adjacency_reports_unmatched():
    rooms = [{"nr": "999", "pavadinimas": "Ghost", "elementai": []}]
    adj = AdjacencyPayload(rooms=[
        RoomAdjacency(room_name="Other", room_nr="1",
                      adjacent_rooms=[], exterior_wall_count=0),
    ])
    summary = apply_adjacency_to_rooms(rooms, adj)
    assert summary["n_unmatched_rooms"] == 1
    assert summary["n_rooms_matched"] == 0


def test_parse_rejects_non_dict():
    with pytest.raises(ValueError):
        parse_adjacency_payload([])  # type: ignore[arg-type]

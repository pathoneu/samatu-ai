"""Evidence we already compute, pay for, and used to throw away (Patikra P0 T3).

Four readings were reduced to a scalar at their call site and the reasoning
behind them discarded — the adjacency payload (the pusiniai-kampai term's own
explanation), the sanitary point-list (`{tipas, vieta}` per fixture, from a pass
that exists BECAUSE counting from a glance under-reads), the height marker's
coordinates (the whole point of that lane is WHERE the number is printed), and
the per-room opening counts every deduction rides on.

Each is one dict deep and already paid for. These tests pin that they survive.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extractor.height_markers import (  # noqa: E402
    _marker_points, assign_markers_to_rooms,
)
from extractor.vision.adjacency_extractor import (  # noqa: E402
    Adjacency, AdjacencyPayload, RoomAdjacency, apply_adjacency_to_rooms,
)
from extractor.vision_call import _recompute_per_room_via_python  # noqa: E402


# ── adjacency ───────────────────────────────────────────────────────────────

def test_the_adjacency_payload_survives_the_call_site():
    rooms = [{"nr": "101", "pavadinimas": "Svetainė", "elementai": []}]
    payload = AdjacencyPayload(rooms=[RoomAdjacency(
        room_name="Svetainė", room_nr="101",
        adjacent_rooms=[
            Adjacency(to_room="Virtuvė", to_room_nr="102", shared_wall_count=1,
                      wall_types=["pertvara"]),
            Adjacency(to_room="Koridorius", to_room_nr="103", shared_wall_count=2,
                      wall_types=["pertvara", "laikanti"]),
        ],
        exterior_wall_count=2, confidence="high",
        evidence="Svetainė ribojasi su virtuve ir koridoriumi")])

    apply_adjacency_to_rooms(rooms, payload)
    adj = rooms[0]["_adjacency"]
    # The scalar everything downstream already used stays exactly as it was…
    assert rooms[0]["n_partition_walls"] == 3
    # …and now it can say why.
    assert [n["room_nr"] for n in adj["neighbours"]] == ["102", "103"]
    assert [n["shared_walls"] for n in adj["neighbours"]] == [1, 2]
    assert adj["wall_types"] == ["laikanti", "pertvara"]
    assert adj["exterior_walls"] == 2
    assert adj["confidence"] == "high"
    assert "virtuve" in adj["evidence"].lower()


def test_an_unmatched_room_gets_no_adjacency_at_all():
    """A room the pass could not match must not carry someone else's walls."""
    rooms = [{"nr": "999", "pavadinimas": "Nežinoma", "elementai": []}]
    apply_adjacency_to_rooms(rooms, AdjacencyPayload(rooms=[]))
    assert "_adjacency" not in rooms[0]


# ── height markers ──────────────────────────────────────────────────────────

def test_marker_points_keep_the_position_and_drop_the_unplaceable():
    pts = _marker_points([
        {"raw": "+3.400", "value_m": 3.4, "page": 6, "x_pct": 0.512345,
         "y_pct": 0.4},
        {"raw": "+2.800", "value_m": 2.8, "page": 6},          # no position
    ])
    assert len(pts) == 1
    assert pts[0] == {"raw": "+3.400", "value_m": 3.4, "page": 6,
                      "x_pct": 0.5123, "y_pct": 0.4}


def test_assigned_markers_carry_their_coordinates():
    # Three rooms because the lane refuses to assign anything until at least
    # three room numbers land inside their own outlines (the frame gate).
    def _box(nr: str, x0: float) -> dict:
        return {"nr": nr, "pavadinimas": f"Patalpa {nr}",
                "polygon_pct": [[x0, 0.0], [x0 + 0.3, 0.0],
                                [x0 + 0.3, 0.4], [x0, 0.4]]}

    rooms = [_box("101", 0.0), _box("102", 0.3), _box("103", 0.6)]
    labels = [{"page": 6, "nr": "101", "x_pct": 0.15, "y_pct": 0.2},
              {"page": 6, "nr": "102", "x_pct": 0.45, "y_pct": 0.2},
              {"page": 6, "nr": "103", "x_pct": 0.75, "y_pct": 0.2}]
    markers = [{"page": 6, "raw": "+3.400", "value_m": 3.4,
                "x_pct": 0.2, "y_pct": 0.2}]
    out = assign_markers_to_rooms(markers, labels, rooms)
    assert out["ok"], out.get("reason")
    ev = out["evidence"]["101"]
    assert ev["chosen_m"] == 3.4
    assert ev["page"] == 6
    # The whole point of this lane is WHERE the number is printed.
    assert ev["points"] == [{"raw": "+3.400", "value_m": 3.4, "page": 6,
                             "x_pct": 0.2, "y_pct": 0.2}]


# ── per-room opening counts ─────────────────────────────────────────────────

def test_opening_counts_are_persisted_without_touching_the_calculator():
    parsed = {"patalpos": [{
        "nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
        "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
        "elementai": [
            {"tipas": "duris", "kiekis": 3, "plotis_mm": 900, "aukstis_mm": 2100},
            {"tipas": "langas", "kiekis": 2, "plotis_mm": 1200, "aukstis_mm": 1500},
        ],
    }]}
    room = _recompute_per_room_via_python(parsed, {})["patalpos"][0]
    assert room["_n_doors"] == 3
    assert room["_n_windows"] == 2
    # Deliberately NOT the bare keys: `calc_room_quantities` reads those off the
    # room it is handed, and `main.py`'s /recompute-interior hands it the raw
    # room — a bare key would silently change that endpoint's geometry.
    assert "n_doors" not in room
    assert "n_windows" not in room

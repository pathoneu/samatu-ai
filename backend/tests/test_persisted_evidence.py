"""Evidence we already compute, pay for, and used to throw away (Patikra P0 T3).

Four readings were reduced to a scalar at their call site and the reasoning
behind them discarded — the adjacency payload (the pusiniai-kampai term's own
explanation), the sanitary point-list (`{tipas, vieta}` per fixture, from a pass
that exists BECAUSE counting from a glance under-reads), the height marker's
coordinates (the whole point of that lane is WHERE the number is printed), and
the per-room opening counts every deduction rides on.

Each is one dict deep and already paid for. These tests pin that they survive.

2026-09-04 adds the three PAGES the room check sheet needs to crop a fact from
the right sheet: the eksplikacija row's own page, the apdailų-lentelė page per
room, and the durų-žiniaraštis page per anchored opening. Every one of them
existed somewhere project-level and could not be attributed to a room.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from extractor.height_markers import (  # noqa: E402
    _marker_points, assign_markers_to_rooms,
)
from extractor.apdailos_reader import merge_apdailos_into_rooms  # noqa: E402
from extractor.vision_call import (  # noqa: E402
    _apply_schedule_match, _recompute_per_room_via_python,
    _stamp_eksplikacija_evidence,
)


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


# ── the three pages the check sheet crops from (2026-09-04) ─────────────────

def test_the_eksplikacija_row_carries_its_own_page_not_the_models_guess():
    """The trap this closes, measured on a corpus project: the top-level
    `eksplikacija_source_page` is Vision's separate guess (1) while the
    deterministic reader that produced the bbox read page 2. A crop keyed on
    the top-level number would frame the wrong sheet with a rectangle that
    still looked plausible."""
    room = {"nr": "01", "pavadinimas": "Tambūras"}
    _stamp_eksplikacija_evidence(
        room,
        {"row_idx": 200, "page": 2,
         "eksplikacija_row_bbox": [954.6, 651.68, 1091.28, 660.44],
         "eksplikacija_page_width_pdf": 1191.0,
         "eksplikacija_page_height_pdf": 842.0},
        {"eksplikacija_source_page": 2},
    )
    assert room["eksplikacija_source_page"] == 2
    assert room["eksplikacija_row_bbox"] == [954.6, 651.68, 1091.28, 660.44]
    assert room["eksplikacija_page_width_pdf"] == 1191.0
    assert room["eksplikacija_row_idx"] == 200


def test_a_row_without_its_own_page_falls_back_to_the_readers():
    """Not to the top-level field — that one is a different producer."""
    room = {"nr": "01"}
    _stamp_eksplikacija_evidence(room, {"row_idx": 3},
                                 {"eksplikacija_source_page": 5})
    assert room["eksplikacija_source_page"] == 5


def test_a_vision_lane_row_stamps_no_geometry_it_does_not_have():
    """The Vision eksplikacija reader computes no bbox. Absent must stay
    absent — a zero or a None would look like a measurement."""
    room = {"nr": "01"}
    _stamp_eksplikacija_evidence(room, {"row_idx": 3, "page": 2}, {})
    assert "eksplikacija_row_bbox" not in room
    assert "eksplikacija_page_width_pdf" not in room
    assert room["eksplikacija_source_page"] == 2


def test_an_anchored_opening_records_the_schedule_page():
    """„matmenys — iš žiniaraščio, psl. 9" needs the page ON the element: the
    id alone forces a lookup into `schedule_tables`, which a saved blob may no
    longer be able to answer."""
    elem = {"tipas": "duris", "kiekis": 2, "plotis_mm": 890, "aukstis_mm": 2090}
    _apply_schedule_match(elem, {"plotis_mm": 900, "aukstis_mm": 2100,
                                 "id": "D1", "page": 9})
    assert elem["_schedule_anchored"] is True
    assert elem["_schedule_id"] == "D1"
    assert elem["_schedule_page"] == 9
    # …and the schedule's millimetres win, which is the point of anchoring.
    assert (elem["plotis_mm"], elem["aukstis_mm"]) == (900, 2100)


def test_a_schedule_row_without_a_page_leaves_the_key_off():
    elem = {"tipas": "langas", "kiekis": 1}
    _apply_schedule_match(elem, {"plotis_mm": 1200, "aukstis_mm": 1500,
                                 "id": "L1"})
    assert "_schedule_page" not in elem
    assert elem["_schedule_anchored"] is True


def test_the_finish_read_records_which_sheet_it_came_from():
    """Until now the only record was project-level `_meta.apdailos_page`, so a
    multi-sheet read could not tell a room which drawing answered it."""
    rooms = [{"nr": "101", "pavadinimas": "Svetainė"},
             {"nr": "999", "pavadinimas": "Nedalyvavo"}]
    n = merge_apdailos_into_rooms(rooms, {
        "status": "ok", "page": 10, "pages": [10, 11],
        "patalpos": [{"nr": "101", "sienu_apdaila": {"dazymas_share": 1.0}}],
    })
    assert n == 1
    assert rooms[0]["_apdailos_page"] == 10
    assert rooms[0]["_apdailos_pages"] == [10, 11]
    # A room the reader never returned must not inherit someone else's sheet.
    assert "_apdailos_page" not in rooms[1]


def test_a_failed_finish_read_stamps_nothing():
    rooms = [{"nr": "101"}]
    assert merge_apdailos_into_rooms(
        rooms, {"status": "error", "page": 10, "patalpos": []}) == 0
    assert "_apdailos_page" not in rooms[0]


def test_the_evidence_keys_survive_the_deterministic_recompute():
    """`_recompute_per_room_via_python` merges computed fields ONTO the room.
    Every evidence key here is a primitive it must not overwrite — otherwise
    the crop rectangles vanish on the first Prielaidos edit."""
    parsed = {"patalpos": [{
        "nr": "101", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
        "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.7,
        "puslapio_nr": 2, "elementai": [],
        "eksplikacija_row_idx": 0,
        "eksplikacija_row_bbox": [1.0, 2.0, 3.0, 4.0],
        "eksplikacija_page_width_pdf": 1191.0,
        "eksplikacija_page_height_pdf": 842.0,
        "eksplikacija_source_page": 2,
        "_apdailos_page": 10,
        "_height_marker_evidence": {"chosen_m": 2.7, "page": 6, "points": []},
    }]}
    room = _recompute_per_room_via_python(parsed, {})["patalpos"][0]
    assert room["eksplikacija_row_bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert room["eksplikacija_source_page"] == 2
    assert room["eksplikacija_page_width_pdf"] == 1191.0
    assert room["_apdailos_page"] == 10
    assert room["_height_marker_evidence"]["page"] == 6

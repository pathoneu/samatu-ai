"""doors_reader reconstruction tests (rebuilt from the lost module's .pyc).

merge_doors_into_rooms is authoritative: it strips pass-1 door attributions and
re-attributes each door to the FIRST room in `between`, so
sum(per_room_doors) == total_count (no double-counting of shared doors).
"""
from extractor.doors_reader import merge_doors_into_rooms, build_user_text, _find_floor_plan_page


def _rooms():
    return [
        {"nr": "101", "paskirtis": "tamburas", "elementai": [{"tipas": "duris", "kiekis": 1}]},
        {"nr": "103", "paskirtis": "koridorius", "elementai": []},
        {"nr": "108", "paskirtis": "gyvenamoji", "elementai": [{"tipas": "duris", "kiekis": 1},
                                                               {"tipas": "langas", "kiekis": 1}]},
    ]


def test_merge_strips_pass1_and_reattributes_to_owner():
    rooms = _rooms()
    result = {"status": "ok", "total_count": 3, "doors": [
        {"tipas": "standart", "between": ["exterior", "101"], "plotis_mm": 1000, "aukstis_mm": 2100},
        {"tipas": "standart", "between": ["103", "108"], "plotis_mm": 900, "aukstis_mm": 2100},
        {"tipas": "pasleptos", "between": ["103", "108"], "plotis_mm": 900, "aukstis_mm": 2400},
    ]}
    merge_doors_into_rooms(rooms, result)
    doors_per_room = {r["nr"]: sum(1 for e in r["elementai"]
                                   if (e.get("tipas") or "").startswith(("duris", "pasleptos")))
                      for r in rooms}
    # exterior door owner = first non-exterior nr in between = 101
    assert doors_per_room["101"] == 1
    # both 103<->108 doors owned by FIRST in between = 103 (not double-counted in 108)
    assert doors_per_room["103"] == 2
    assert doors_per_room["108"] == 0
    # total preserved, langas untouched
    assert sum(doors_per_room.values()) == 3
    assert any(e.get("tipas") == "langas" for e in rooms[2]["elementai"])
    # hidden door preserved as pasleptos_duris, exterior flagged
    assert any(e.get("tipas") == "pasleptos_duris" for e in rooms[1]["elementai"])
    assert any(e.get("_exterior") for e in rooms[0]["elementai"])


def test_merge_noop_when_not_ok():
    rooms = _rooms()
    assert merge_doors_into_rooms(rooms, {"status": "error"}) == 0
    assert len(rooms[0]["elementai"]) == 1  # pass-1 door untouched


def test_find_floor_plan_page_prefers_classification():
    assert _find_floor_plan_page(b"", [{"tipas": "floor_plan", "nr": 2}]) == 2


def test_build_user_text_has_schema_and_procedure():
    txt = build_user_text([{"nr": "101", "pavadinimas": "Tambūras", "plotas_m2": 5.0}])
    assert "total_count" in txt and "PROCEDŪRA" in txt and "Tambūras" in txt

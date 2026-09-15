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



# ── the merge must never erase what it cannot place (2026-09-10) ─────────────
def _rooms_01():
    return [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
         "elementai": [{"tipas": "duris", "kiekis": 2, "plotis_mm": 900, "aukstis_mm": 2100}, {"tipas": "langas", "kiekis": 1}]},
        {"nr": "02", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji",
         "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100}]},
        {"nr": "08", "pavadinimas": "Koridorius", "paskirtis": "koridorius", "elementai": []},
    ]


def _doors(*between):
    return {"status": "ok", "total_count": len(between),
            "doors": [{"between": list(b), "tipas": "standart", "plotis_mm": 900, "aukstis_mm": 2100} for b in between]}


def _n_doors(room):
    return sum(int(e.get("kiekis") or 1) for e in room.get("elementai") or []
               if (e.get("tipas") or "").lower() in ("duris", "pasleptos_duris"))


def test_between_numbers_without_leading_zeros_still_place_the_doors():
    from extractor.doors_reader import merge_doors_into_rooms
    rooms = _rooms_01()
    res = _doors(("8", "1"), ("8", "2"), (8, "exterior"))
    assert merge_doors_into_rooms(rooms, res) == 1
    assert [_n_doors(r) for r in rooms] == [0, 0, 3], "the corridor owns all three"
    assert res["_unattributed"] == 0


def test_between_room_names_place_the_doors_when_unique():
    from extractor.doors_reader import merge_doors_into_rooms
    rooms = _rooms_01()
    res = _doors(("Koridorius", "Svetainė"), ("Miegamasis", "Koridorius"))
    assert merge_doors_into_rooms(rooms, res) == 2
    assert [_n_doors(r) for r in rooms] == [0, 1, 1]


def test_an_unplaceable_enumeration_leaves_the_first_reads_doors_alone():
    from extractor.doors_reader import merge_doors_into_rooms
    rooms = _rooms_01()
    res = _doors(("101", "103"), ("103", "108"), ("Holas", "exterior"))
    assert merge_doors_into_rooms(rooms, res) == 0
    assert [_n_doors(r) for r in rooms] == [2, 1, 0], "pass-1 doors survive"
    assert res["_unattributed"] == 3 and res.get("_kept_pass1_doors") is True


def test_a_mostly_placeable_enumeration_replaces_and_reports_the_rest():
    from extractor.doors_reader import merge_doors_into_rooms
    rooms = _rooms_01()
    res = _doors(("08", "01"), ("08", "02"), ("99", "77"))
    assert merge_doors_into_rooms(rooms, res) == 1
    assert [_n_doors(r) for r in rooms] == [0, 0, 2]
    assert res["_unattributed"] == 1 and not res.get("_kept_pass1_doors")


def test_a_room_number_binds_only_when_it_leads_the_reference():
    """„01 Svetainė" and „P-07" are room numbers; „Miegamasis 2" is a room
    NAME with a digit in it and must not become room 02 (2026-09-15 review)."""
    from extractor.doors_reader import _room_resolver
    rooms = [{"nr": "01", "pavadinimas": "Svetainė"}, {"nr": "02", "pavadinimas": "Vonia"},
             {"nr": "07", "pavadinimas": "Miegamasis"}]
    resolve = _room_resolver(rooms)
    assert resolve("01 Svetainė") is rooms[0]
    assert resolve("7") is rooms[2] and resolve("P-07") is rooms[2] and resolve("07 (miegamasis)") is rooms[2]
    assert resolve("Vonia") is rooms[1]
    assert resolve("Miegamasis 2") is None
    assert resolve("Miegamasis 02") is None
    assert resolve("exterior") is None

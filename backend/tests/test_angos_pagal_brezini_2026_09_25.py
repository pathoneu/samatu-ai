"""2026-09-25 — what the drawing SHOWS in a wall opening decides what stands there. The geometry lane labels
each opening `nupiesta` („langas" — glazing lines inside the wall band; „durys" — a swing arc hinged at its
end) and the walls pass uses the label: a window takes a glazed opening first; a listed window whose only
opening is a drawn door becomes that (exterior) door; a free glazed opening to the outside becomes a window;
a free opening with a swing becomes a door — a listed door no opening backed takes it first. objektas_h: the
kitchen's third and fourth windows, the bedroom's second, the boiler room's two doors, the terrace door drawn
where the wall is not cut."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402


def _room(nr, elementai, angos=None, **more):
    room = {"nr": nr, "pavadinimas": f"P{nr}", "paskirtis": more.pop("paskirtis", "gyvenamoji"), "plotas_m2": 14.0,
            "perimetras_m": 15.0, "lubu_aukstis_m": 2.7, "elementai": elementai, **more}
    if angos is not None:
        room["_angos_sienose"] = {"page": 1, "angos": []}
        for k, a in enumerate(angos):
            i, w = a[0], a[1]
            rec = {"i": i, "plotis_m": w, "storis_m": 0.3, "line_pct": [[0.1 * k, 0.1], [0.1 * k + 0.05, 0.1]]}
            if len(a) > 2 and a[2]:
                rec["nupiesta"] = a[2]
            if len(a) > 3 and a[3]:
                rec["be_tarpo"] = True
            room["_angos_sienose"]["angos"].append(rec)
    return room


def _openings(room, tipas):
    return [e for e in room["elementai"] if e.get("tipas") == tipas]


def test_a_free_glazed_opening_to_the_outside_becomes_a_window_with_the_rooms_window_height():
    kitchen = _room("04", [{"tipas": "langas", "kiekis": 2, "plotis_mm": 1350, "aukstis_mm": 1400}],
                    angos=[("03", 2.13), ("laukas", 1.37, "langas"), ("laukas", 1.36, "langas"),
                           ("laukas", 0.89, "langas"), ("laukas", 1.35, "langas")], paskirtis="virtuve")
    out = ur.reconcile_openings_with_walls([kitchen])
    windows = _openings(kitchen, "langas")
    assert sum(int(w["kiekis"]) for w in windows) == 4
    added = [w for w in windows if w.get(ur.ADDED_FROM_WALLS_KEY)]
    assert sorted(w["plotis_mm"] for w in added) == [890, 1370]
    assert all(w["aukstis_mm"] == 1400 and w[ur.DRAWN_KEY] == "langas" and w["_is_sienu_angos"] == "laukas" for w in added)
    assert out["added_windows"] == 2
    # idempotent: the added windows stand in their openings again, nothing more is added
    ur.reconcile_openings_with_walls([kitchen])
    assert sum(int(w["kiekis"]) for w in _openings(kitchen, "langas")) == 4


def test_a_listed_window_whose_only_opening_is_a_drawn_door_becomes_that_exterior_door():
    boiler = _room("02", [{"tipas": "langas", "kiekis": 1, "plotis_mm": 1000}],
                   angos=[("laukas", 1.0, "durys"), ("vidus", 0.64, "durys")], paskirtis="katiline")
    out = ur.reconcile_openings_with_walls([boiler])
    assert _openings(boiler, "langas") == []
    doors = _openings(boiler, "duris")
    ext = [d for d in doors if d.get(ur.EXTERIOR_KEY)]
    assert len(ext) == 1 and ext[0]["plotis_mm"] == 1000 and ext[0]["aukstis_mm"] == 2100
    assert ext[0][ur.KIND_BY_DRAWING_KEY] == "durys" and ext[0]["_tipas_vision"] == "langas"
    assert out["converted"] == 1
    # the drawn door into the unnumbered space beside it is added too — a room lists no door it has none of
    inner = [d for d in doors if d.get(ur.OPENING_SIDE_KEY) == "vidus"]
    assert len(inner) == 1 and inner[0]["plotis_mm"] == 640 and inner[0].get(ur.ADDED_FROM_WALLS_KEY) is True
    # a second run keeps the door a door and adds nothing
    ur.reconcile_openings_with_walls([boiler])
    assert len(_openings(boiler, "duris")) == 2 and _openings(boiler, "langas") == []


def test_a_window_prefers_the_glazed_opening_over_a_drawn_door_of_the_same_width():
    room = _room("06", [{"tipas": "langas", "kiekis": 1, "plotis_mm": 1000, "aukstis_mm": 1500}],
                 angos=[("laukas", 1.0, "durys"), ("laukas", 1.0, "langas")])
    ur.reconcile_openings_with_walls([room])
    win = _openings(room, "langas")[0]
    assert win[ur.OPENING_INDEX_KEY] == [1] and win[ur.DRAWN_KEY] == "langas"
    # the drawn door left free becomes an exterior door
    door = _openings(room, "duris")
    assert len(door) == 1 and door[0].get(ur.EXTERIOR_KEY) is True and door[0][ur.DRAWN_KEY] == "durys"


def test_a_listed_door_no_opening_backed_takes_the_drawn_door_before_one_is_added():
    # the listed door's guessed width (1,10 m) is too far from the 0,70 m opening for the plain width match
    corridor = _room("03", [{"tipas": "duris", "kiekis": 1, "plotis_mm": 1100, "aukstis_mm": 2100}],
                     angos=[("07", 0.7, "durys")], paskirtis="koridorius")
    bath = _room("07", [], angos=[("03", 0.7, "durys")], paskirtis="vonia")
    out = ur.reconcile_openings_with_walls([corridor, bath])
    doors = _openings(corridor, "duris")
    assert len(doors) == 1 and doors[0].get(ur.UNBACKED_KEY) is None
    assert doors[0][ur.OPENING_SIDE_KEY] == "07" and doors[0]["plotis_mm"] == 700 and doors[0][ur.DRAWN_KEY] == "durys"
    assert out["stood_unbacked"] == 1 and out["unbacked"] == 0
    assert bath["elementai"] == []                              # the corridor's door stands in that opening


def test_a_door_drawn_where_the_wall_is_not_cut_is_added_once_as_an_exterior_door():
    kitchen = _room("04", [{"tipas": "langas", "kiekis": 1, "plotis_mm": 1350, "aukstis_mm": 1500}],
                    angos=[("laukas", 1.35, "langas"), ("laukas", 0.95, "durys", True)], paskirtis="virtuve")
    out = ur.reconcile_openings_with_walls([kitchen])
    doors = _openings(kitchen, "duris")
    assert len(doors) == 1 and doors[0].get(ur.EXTERIOR_KEY) is True and doors[0]["plotis_mm"] == 950
    assert doors[0].get(ur.ADDED_FROM_WALLS_KEY) is True and doors[0][ur.DRAWN_KEY] == "durys"
    assert out["added"] == 1
    ur.reconcile_openings_with_walls([kitchen])
    assert len(_openings(kitchen, "duris")) == 1


def test_a_drawn_door_between_two_rooms_is_added_on_one_side_only():
    laundry = _room("106", [], angos=[("105", 0.86), ("103", 0.9, "durys", True)], paskirtis="skalbykla")
    corridor = _room("103", [{"tipas": "duris", "kiekis": 1, "plotis_mm": 860, "aukstis_mm": 2100}],
                     angos=[("108", 0.86), ("106", 0.9, "durys", True)], paskirtis="koridorius")
    ur.reconcile_openings_with_walls([corridor, laundry])
    between = [(r["nr"], e) for r in (corridor, laundry) for e in r["elementai"]
               if e.get("tipas") == "duris" and str(e.get(ur.OPENING_SIDE_KEY)) in ("106", "103")
               and str(e.get(ur.OPENING_SIDE_KEY)) != r["nr"]]
    assert len(between) == 1, between
    # the laundry, with no door listed, also got one from its opening to 105 (the older rule) — but not a second 103 door
    assert sum(1 for e in laundry["elementai"] if e.get(ur.OPENING_SIDE_KEY) == "103") + \
        sum(1 for e in corridor["elementai"] if e.get(ur.OPENING_SIDE_KEY) == "106") == 1


def test_reveals_follow_the_drawing_added_window_and_exterior_door():
    room = _room("09", [{"tipas": "langas", "kiekis": 1, "plotis_mm": 1570, "aukstis_mm": 1500}],
                 angos=[("03", 0.87), ("laukas", 0.97, "langas"), ("laukas", 1.57, "langas")], paskirtis="miegamasis")
    ur.reconcile_openings_with_walls([room])
    q = ur.calc_room_quantities(room)
    assert abs(q["angokrasciu_gkp_m"] - ((0.97 + 3.0) + (1.57 + 3.0))) < 0.05

"""2026-09-23 — what the six contractor sąmatas showed about openings (docs/superpowers/research/
2026-09-23-eiluciu-paklaidos.md): a door two rooms list counted twice; reveals had been fitted to one
project; the frameless-door row counted only the doors the drawing tags; a cornice was billed everywhere."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402
from extractor.line_items import hidden_door_count, hidden_door_frame_lm  # noqa: E402


def _room(nr, elementai, **more):
    return {"nr": nr, "pavadinimas": f"P{nr}", "paskirtis": "gyvenamoji", "plotas_m2": 12.0, "perimetras_m": 14.0,
            "lubu_aukstis_m": 2.7, "elementai": elementai, **more}


def door(w=800, h=2100, **more):
    return {"tipas": "duris", "kiekis": 1, "plotis_mm": w, "aukstis_mm": h, **more}


# ── doors two rooms list ────────────────────────────────────────────────────────

def test_a_door_added_from_the_wall_opening_toward_a_room_that_lists_it_is_counted_once():
    corridor = _room("03", [door(800), door(900)])
    bedroom = _room("09", [door(800, _is_sienu_angos="03")])           # the check sheet's „+ Durys" from 09's wall to 03
    assert ur.mark_shared_doors([corridor, bedroom]) == 1
    assert bedroom["elementai"][0][ur.SHARED_DOOR_KEY] == "03" and bedroom["elementai"][0][ur.SHARED_DOOR_N_KEY] == 1
    assert ur.SHARED_DOOR_KEY not in corridor["elementai"][0] and ur.SHARED_DOOR_KEY not in corridor["elementai"][1]
    assert ur.door_units_counted(bedroom["elementai"][0]) == 0 and ur.door_units_counted(corridor["elementai"][0]) == 1
    # idempotent: a second pass finds the same one pair, nothing accumulates
    assert ur.mark_shared_doors([corridor, bedroom]) == 1 and bedroom["elementai"][0][ur.SHARED_DOOR_N_KEY] == 1


def test_visions_own_lists_pair_through_the_wall_openings_the_lane_read():
    # 03 lists two doors, 09 lists its own; the wall between 03 and 09 has one 0,87 m opening
    corridor = _room("03", [door(800), door(900)],
                     _angos_sienose={"page": 1, "angos": [{"i": "09", "plotis_m": 0.87, "line_pct": [[0.6, 0.3], [0.6, 0.32]]},
                                                          {"i": "laukas", "plotis_m": 1.0, "line_pct": [[0.1, 0.1], [0.1, 0.12]]}]})
    bedroom = _room("09", [door(900)])
    assert ur.mark_shared_doors([corridor, bedroom]) == 1
    assert bedroom["elementai"][0][ur.SHARED_DOOR_KEY] == "03"     # counted in the lower-numbered room
    # a width that matches nothing on the other side is left alone
    other = _room("10", [door(1400)])
    corridor2 = _room("03", [door(800)], _angos_sienose={"page": 1, "angos": [{"i": "10", "plotis_m": 0.8, "line_pct": [[0.6, 0.3], [0.6, 0.32]]}]})
    assert ur.mark_shared_doors([corridor2, other]) == 0


def test_each_unit_pairs_once_and_exterior_doors_never_do():
    a = _room("01", [door(900, kiekis=2), door(1000, _exterior=True)])
    b = _room("02", [door(900, _is_sienu_angos="01"), door(900, _is_sienu_angos="01"), door(900, _is_sienu_angos="01")])
    assert ur.mark_shared_doors([a, b]) == 2                      # two units in 01 — the third door in 02 stays its own
    assert sum(ur.door_units_counted(el) for el in b["elementai"]) == 1
    assert ur.door_units_counted(a["elementai"][1]) == 1


# ── what the rows are made of ───────────────────────────────────────────────────

def test_reveals_are_the_windows_and_the_exterior_doors_and_a_framed_interior_door_is_nothing():
    room = _room("05", [{"tipas": "langas", "kiekis": 2, "plotis_mm": 1500, "aukstis_mm": 1800, "_exterior": True},
                        door(1800, 2200, _exterior=True), door(800)])
    out = ur.calc_room_quantities(room)
    assert out["angokrasciu_gkp_m"] == round(2 * (1.5 + 3.6) + (1.8 + 4.4), 2)     # 16,4: windows + the terrace door
    assert out["pasleptu_duru_staktu_m"] == 0 and out["pasleptu_duru_kompl"] == 0  # a framed door: architraves cover it
    assert out["_pasleptu_duru_pagal"] == "zymejimas"


def test_a_tagged_hidden_door_is_prepared_and_the_project_assumption_makes_the_untagged_ones_frameless_too():
    tagged = _room("03", [{"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2400}, door(800)])
    plain = _room("09", [door(800)])
    rooms = [tagged, plain]
    settled = ur.settle_frameless_default(rooms)
    assert (settled["value"], settled["source"]) == (True, "brezinys") and all(r[ur.FRAMELESS_DEFAULT_KEY] for r in rooms)
    assert "patvirtinkite" in settled["sakinys"]                 # symbols alone are not a confirmed frame type
    out = ur.calc_room_quantities(tagged)
    assert out["pasleptu_duru_staktu_m"] == round((4.8 + 0.9) + (4.2 + 0.8), 2) and out["pasleptu_duru_kompl"] == 2
    assert out["_pasleptu_duru_pagal"] == "prielaida"
    # nothing frameless anywhere in the drawing: untagged doors stay framed
    alone = [_room("09", [door(800)])]
    alone_settled = ur.settle_frameless_default(alone)
    assert (alone_settled["value"], alone_settled["source"]) == (False, "nera_pozymiu")
    assert ur.calc_room_quantities(alone[0])["pasleptu_duru_staktu_m"] == 0
    # his choice wins either way
    assert ur.settle_frameless_default(alone, overrides={"vidaus_durys_beapvadines": True})["source"] == "jusu"
    assert alone[0][ur.FRAMELESS_DEFAULT_KEY] is True
    assert ur.settle_frameless_default(rooms, overrides={"vidaus_durys_beapvadines": False})["value"] is False


def test_a_door_counted_in_the_neighbour_leaves_this_rooms_per_opening_rows_but_not_its_wall():
    corridor = _room("03", [door(800)])
    bedroom = _room("09", [door(800, _is_sienu_angos="03")])
    ur.prepare_rooms_for_calc([corridor, bedroom], overrides={"vidaus_durys_beapvadines": True})
    b = ur.calc_room_quantities(bedroom)
    c = ur.calc_room_quantities(corridor)
    assert b["pasleptu_duru_staktu_m"] == 0 and c["pasleptu_duru_staktu_m"] == round(4.2 + 0.8, 2)
    # the opening still comes off BOTH rooms' painted wall (each side has the hole)
    assert b["walls_paintable_m2"] < 14.0 * 2.7 and c["walls_paintable_m2"] < 14.0 * 2.7
    assert abs(b["walls_paintable_m2"] - c["walls_paintable_m2"]) < 0.01


def test_line_items_agree_with_the_calculator_on_shared_and_assumed_doors():
    ops = [door(800, _bendra_su="03", _bendra_su_n=1), door(900), {"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2400}]
    assert hidden_door_count(ops) == 1 and hidden_door_frame_lm(ops) == 5.7
    assert hidden_door_count(ops, frameless_default=True) == 2 and hidden_door_frame_lm(ops, frameless_default=True) == round(5.7 + 5.1, 3)


# ── the cornice needs the drawing to name one ──────────────────────────────────

def test_a_cornice_is_billed_only_when_the_drawing_mentions_one():
    from extractor.vision_call import _calc_lubu_karnizas_m
    assert _calc_lubu_karnizas_m(20.0, "gyvenamoji", evidence=False) == 0.0
    assert _calc_lubu_karnizas_m(20.0, "gyvenamoji", evidence=True) == 21.0
    assert _calc_lubu_karnizas_m(20.0, "gyvenamoji") == 21.0                     # a caller that knows nothing: as before
    rooms = [_room("05", [])]
    ur.prepare_rooms_for_calc(rooms, legend={"text_layer_ok": True, "karnizas": {"defined": False, "pages": []}})
    assert rooms[0][ur.KARNIZAS_KEY] is False
    ur.prepare_rooms_for_calc(rooms, legend={"text_layer_ok": True, "karnizas": {"defined": True, "pages": [4]}})
    assert rooms[0][ur.KARNIZAS_KEY] is True


def test_the_legend_scan_reports_a_cornice_named_in_the_text():
    from extractor.symbol_legend import _KARNIZAS_RE
    assert _KARNIZAS_RE.search("LUBŲ KARNIZAS LK-1, dažomas") and _KARNIZAS_RE.search("karnizo profilis")
    assert not _KARNIZAS_RE.search("sienų dažymas")


def test_one_wall_opening_backs_one_pair_and_a_hidden_door_pairs_with_a_hidden_one():
    """objektas_h tambūras: two interior doors listed (0,8 and 0,9 m), ONE opening to the corridor (1,0 m) —
    only one of them can be the corridor's door; and a framed door does not claim the corridor's hidden one."""
    tamburas = _room("01", [door(800), door(900)],
                     _angos_sienose={"page": 1, "angos": [{"i": "03", "plotis_m": 1.0, "line_pct": [[0.4, 0.4], [0.4, 0.43]]}]})
    corridor = _room("03", [{"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2400}, door(900), door(800)],
                     _angos_sienose={"page": 1, "angos": [{"i": "01", "plotis_m": 1.0, "line_pct": [[0.4, 0.4], [0.4, 0.43]]}]})
    assert ur.mark_shared_doors([tamburas, corridor]) == 1
    marked = [(el.get("tipas"), el.get("plotis_mm")) for el in corridor["elementai"] if el.get(ur.SHARED_DOOR_KEY)]
    assert marked == [("duris", 900)]                          # the framed 0,9 m door, not the hidden one, and only once

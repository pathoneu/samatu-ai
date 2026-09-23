"""2026-09-23 — the wall openings the geometry lane read are the PRIMARY list of holes in a room's walls;
the doors and windows Vision counted are stood in them (universal_rules.reconcile_openings_with_walls):
widths from the walls, exterior doors from „laukas", passages between living spaces, doors no opening backs
named for a look. The founder: „durys 1,40 pločio nebus tikrai"; H's terrace and garage doors were billed as
frameless interior ones."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402
from extractor.line_items import hidden_door_count  # noqa: E402
from extractor.project_questions import build_questions  # noqa: E402
from extractor.room_facts import build_room_facts  # noqa: E402


def _room(nr, elementai, angos=None, **more):
    room = {"nr": nr, "pavadinimas": f"P{nr}", "paskirtis": "gyvenamoji", "plotas_m2": 12.0, "perimetras_m": 14.0,
            "lubu_aukstis_m": 2.7, "elementai": elementai, **more}
    if angos is not None:
        room["_angos_sienose"] = {"page": 1, "angos": [
            {"i": i, "plotis_m": w, "line_pct": [[0.1 * k, 0.1], [0.1 * k + 0.05, 0.1]]} for k, (i, w) in enumerate(angos)]}
    return room


def door(w=None, **more):
    el = {"tipas": "duris", "kiekis": 1, "aukstis_mm": 2100, **more}
    if w:
        el["plotis_mm"] = w
    return el


def window(w=None, **more):
    el = {"tipas": "langas", "kiekis": 1, "aukstis_mm": 1500, **more}
    if w:
        el["plotis_mm"] = w
    return el


def test_the_kitchen_of_h_terrace_door_windows_and_the_passage_to_the_corridor():
    """H 04: Vision listed two windows (1200) and one „hidden door" 2000 wide; the walls show the passage to
    the corridor (2,13), three windows and one door-width opening to the outside."""
    corridor = _room("03", [], paskirtis="koridorius")
    kitchen = _room("04", [window(1200), window(1200), {"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 2000, "aukstis_mm": 2100}],
                    angos=[("03", 2.13), ("laukas", 1.37), ("laukas", 1.36), ("laukas", 0.89), ("laukas", 1.35)], paskirtis="virtuve")
    out = ur.reconcile_openings_with_walls([corridor, kitchen])
    assert out == {"rooms": 1, "matched": 3, "widths": 3, "exterior": 0, "passages": 1, "unbacked": 0, "added": 0}
    els = kitchen["elementai"]
    # each 1200 window takes the closest opening still free: 1,35 then 1,36 — the 1,37 stays open
    assert els[0]["plotis_mm"] == 1350 and els[1]["plotis_mm"] == 1360 and els[0][ur.WIDTH_SOURCE_KEY] == "sienos"
    assert els[2].get(ur.PASSAGE_KEY) is True and els[2]["plotis_mm"] == 2130 and els[2][ur.OPENING_SIDE_KEY] == "03"
    ur.settle_frameless_default([kitchen], overrides={"vidaus_durys_beapvadines": True})
    q = ur.calc_room_quantities(kitchen)
    assert q["pasleptu_duru_kompl"] == 0                        # a passage is no frameless door frame
    # the two openings nobody stands in are offered — the 0,89 one to the outside as a window he can retype
    facts = build_room_facts({"patalpos": [corridor, kitchen]}, "04")
    f = next(x for x in facts["facts"] if x["key"] == "angos")
    assert f["status"] == "assumed" and "Praėjimai be durų: į patalpą 03 (2,13 m)" in f["sentence"]
    assert sorted(s["plotis_m"] for s in f["suggestions"]) == [0.89, 1.37]
    assert "angose niekas nestovi" in f["sentence"]


def test_a_door_with_no_opening_to_a_room_takes_a_door_wide_opening_to_the_outside():
    boiler = _room("02", [door()], angos=[("laukas", 1.0), ("vidus", 0.64)], paskirtis="katiline")
    out = ur.reconcile_openings_with_walls([boiler])
    # the 0,64 opening to a space without an outline is a door-width opening to a room — it wins
    assert out["exterior"] == 0 and boiler["elementai"][0][ur.OPENING_SIDE_KEY] == "vidus" and boiler["elementai"][0]["plotis_mm"] == 640
    hall = _room("01", [door(1000, _exterior=True), door(800), door(900)], angos=[("laukas", 1.6), ("vidus", 0.74)], paskirtis="tamburas")
    out = ur.reconcile_openings_with_walls([hall])
    els = hall["elementai"]
    assert els[0][ur.OPENING_SIDE_KEY] == "laukas" and els[0]["plotis_mm"] == 1600     # Vision's exterior door — the entrance
    assert els[1][ur.OPENING_SIDE_KEY] == "vidus" and els[1]["plotis_mm"] == 740
    assert els[2].get(ur.UNBACKED_KEY) is True and out["unbacked"] == 1
    ur.settle_frameless_default([hall], overrides={"vidaus_durys_beapvadines": True})
    assert ur.calc_room_quantities(hall)["pasleptu_duru_kompl"] == 1                  # only the door an opening backs
    assert hidden_door_count(els, frameless_default=True) == 1
    facts = build_room_facts({"patalpos": [hall]}, "01")
    f = next(x for x in facts["facts"] if x["key"] == "angos")
    assert "1 durys sąraše, kurioms angos sienose nematau" in f["sentence"] and f["status"] == "assumed"


def test_a_door_added_from_an_opening_stands_in_it_and_a_unit_split_keeps_one_kind_per_element():
    living = _room("05", [door(kiekis=2), door(_is_sienu_angos="laukas")],
                   angos=[("03", 1.56), ("laukas", 1.36), ("laukas", 5.07)], paskirtis="gyvenamoji")
    corridor = _room("03", [], paskirtis="koridorius")
    out = ur.reconcile_openings_with_walls([corridor, living])
    els = living["elementai"]
    # the tagged door took an opening to the outside (the closest to its size — none: the first), the two
    # untagged units: one the passage to the corridor, the other nothing — split into two elements
    kinds = sorted((e.get("kiekis"), bool(e.get(ur.PASSAGE_KEY)), bool(e.get(ur.UNBACKED_KEY)), bool(e.get(ur.EXTERIOR_KEY))) for e in els)
    assert kinds == [(1, False, False, True), (1, False, True, False), (1, True, False, False)]
    assert out["passages"] == 1 and out["unbacked"] == 1 and out["exterior"] == 1


def test_a_wide_opening_into_a_bedroom_or_a_bathroom_is_still_a_door():
    bedroom = _room("09", [door(800), door(1200)], angos=[("08", 1.4), ("10", 1.18), ("03", 0.87)], paskirtis="miegamoji")
    bath = _room("08", [], paskirtis="vonia")
    wardrobe = _room("10", [], paskirtis="drabuzine")
    corridor = _room("03", [door(900)], angos=[("09", 0.87)], paskirtis="koridorius")
    ur.reconcile_openings_with_walls([bedroom, bath, wardrobe, corridor])
    els = bedroom["elementai"]
    assert not any(e.get(ur.PASSAGE_KEY) for e in els)
    assert {e[ur.OPENING_SIDE_KEY] for e in els} == {"03", "10"}      # 800 → the 0,87 to the corridor, 1200 → the 1,18 wardrobe
    # and the corridor's 900 stands in its 0,87 opening to the bedroom — the pair is exact now
    assert corridor["elementai"][0][ur.OPENING_SIDE_KEY] == "09" and corridor["elementai"][0]["plotis_mm"] == 870
    assert ur.mark_shared_doors([bedroom, bath, wardrobe, corridor]) == 1


def test_a_size_he_typed_stays_and_the_pass_is_idempotent_and_leaves_rooms_without_walls_alone():
    room = _room("06", [door(800, _dydis_user=True), window(1200)], angos=[("03", 0.77), ("laukas", 1.37)])
    plain = _room("07", [door(800)])
    first = ur.prepare_rooms_for_calc([room, plain])
    assert first["angos"]["matched"] == 2 and room["elementai"][0]["plotis_mm"] == 800 and room["elementai"][1]["plotis_mm"] == 1370
    assert plain["elementai"][0].get(ur.UNBACKED_KEY) is None and plain.get("_angos_sienose_suderinta") is False
    again = ur.prepare_rooms_for_calc([room, plain])
    assert {k: v for k, v in again["angos"].items() if k != "widths"} == {k: v for k, v in first["angos"].items() if k != "widths"}
    assert again["angos"]["widths"] == 0 and len(room["elementai"]) == 2   # nothing left to change


def test_the_question_names_the_room_whose_door_the_walls_do_not_back():
    hall = _room("01", [door(1000, _exterior=True), door(900)], angos=[("laukas", 1.6)], paskirtis="tamburas",
                 plotas_saltinis="inline_label", lubu_aukstis_saltinis="per_room", _tile_read_source="apdailos",
                 grindu_danga="minksta", grindu_danga_saltinis="user_override")
    ur.prepare_rooms_for_calc([hall], overrides={"vidaus_durys_beapvadines": False})
    out = build_questions({"patalpos": [hall], "_overrides": {"vidaus_durys_beapvadines": False}})
    q = next(x for x in out["questions"] if x["kind"] == "angos")
    assert q["items"] == [] and q["manual"][0]["room_nr"] == "01"
    assert "angos sienose nematau" in q["manual"][0]["sentence"]


def test_a_room_with_no_door_counted_gets_one_from_its_walls_and_a_wide_door_into_a_bathroom_counts():
    """H: Vision listed no door for two bathrooms and the wardrobe; the walls show their openings from the
    bedroom (1,40 and 1,18). A floor plan has no room without a door."""
    bedroom = _room("09", [door(800)], angos=[("03", 0.87), ("08", 1.4), ("10", 1.18)], paskirtis="miegamoji")
    bath = _room("08", [], angos=[("09", 1.4)], paskirtis="vonia")
    wardrobe = _room("10", [], angos=[("09", 1.18)], paskirtis="drabuzine")
    corridor = _room("03", [door(900)], angos=[("09", 0.87)], paskirtis="koridorius")
    prep = ur.prepare_rooms_for_calc([bedroom, bath, wardrobe, corridor], overrides={"vidaus_durys_beapvadines": True})
    assert prep["angos"]["added"] == 2
    b = bath["elementai"][0]
    assert (b["tipas"], b["plotis_mm"], b["aukstis_mm"], b["_is_sienu_angos"], b[ur.ADDED_FROM_WALLS_KEY]) == ("duris", 1400, 2100, "09", True)
    assert wardrobe["elementai"][0]["plotis_mm"] == 1180
    # the 1,40 door into the bathroom is a door (the passage rule already decided) — a frameless one here
    assert ur.calc_room_quantities(bath)["pasleptu_duru_kompl"] == 1 and hidden_door_count(bath["elementai"], frameless_default=True) == 1
    # a second run stands the added doors in the same openings — nothing is added twice
    again = ur.prepare_rooms_for_calc([bedroom, bath, wardrobe, corridor], overrides={"vidaus_durys_beapvadines": True})
    assert again["angos"]["added"] == 0 and len(bath["elementai"]) == 1 and len(wardrobe["elementai"]) == 1
    # a room whose door the neighbour lists (standing in the opening toward it) gets nothing
    assert len(corridor["elementai"]) == 1 and ur.mark_shared_doors([bedroom, bath, wardrobe, corridor]) == 1


def test_a_door_stood_toward_one_room_never_pairs_with_a_door_of_another_and_a_garage_door_is_exterior():
    """objektas_a: the corridor's door to the bedroom was paired with the hall's door to the corridor (same
    width), and the laundry's door from the garage was billed as a frameless interior one."""
    hall = _room("101", [door(1150)], angos=[("103", 1.15), ("laukas", 1.34)], paskirtis="tamburas")
    corridor = _room("103", [{"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 1150, "aukstis_mm": 2100}, door(1150)],
                     angos=[("101", 1.15), ("110", 1.15)], paskirtis="koridorius")
    bedroom = _room("110", [], angos=[("103", 1.15)], paskirtis="miegamoji")
    laundry = _room("106", [], angos=[("105", 0.86)], paskirtis="skalbykla")
    garage = _room("105", [door(1910, _exterior=True)], angos=[("laukas", 1.91), ("106", 0.86)], paskirtis="garazas")
    prep = ur.prepare_rooms_for_calc([hall, corridor, bedroom, laundry, garage], overrides={"vidaus_durys_beapvadines": True})
    # the hall's door pairs with the corridor's door stood toward the hall (a hidden one — the tag wins over the kind)
    assert prep["shared_doors"] == 1
    assert corridor["elementai"][0].get(ur.SHARED_DOOR_KEY) == "101" and corridor["elementai"][1].get(ur.SHARED_DOOR_KEY) is None
    # the laundry got its door from the walls, and it is a door to the outside (the garage): reveals, no frame
    l = laundry["elementai"][0]
    assert l[ur.ADDED_FROM_WALLS_KEY] and l.get(ur.EXTERIOR_KEY) is True
    q = ur.calc_room_quantities(laundry)
    assert q["pasleptu_duru_kompl"] == 0 and q["angokrasciu_gkp_m"] == round(0.86 + 4.2, 2)


def test_a_neighbours_door_stood_toward_this_room_claims_the_opening_whatever_width_he_typed_on_it():
    """H demo: the bathroom's door (typed 800) stands in the bedroom's 1,40 opening to it; the bedroom must
    not be offered that opening again."""
    bedroom = _room("09", [door(870)], angos=[("03", 0.87), ("08", 1.4)], paskirtis="miegamoji",
                    plotas_saltinis="inline_label", lubu_aukstis_saltinis="per_room")
    bath = _room("08", [door(800, _dydis_user=True, _is_sienu_angos="09")], angos=[("09", 1.4)], paskirtis="vonia")
    corridor = _room("03", [door(870)], angos=[("09", 0.87)], paskirtis="koridorius")
    ur.prepare_rooms_for_calc([bedroom, bath, corridor])
    assert bath["elementai"][0]["plotis_mm"] == 800 and bath["elementai"][0][ur.OPENING_SIDE_KEY] == "09"
    f = next(x for x in build_room_facts({"patalpos": [bedroom, bath, corridor]}, "09")["facts"] if x["key"] == "angos")
    assert f["suggestions"] == [] and "į patalpą 08 (1,40 m) įrašytos prie tos patalpos" in f["sentence"]


def test_a_visions_exterior_door_keeps_its_flag_and_its_wall_width_through_a_second_run():
    """H demo, the Prielaidos toggle: the second recompute of the same request cleared the entrance door's
    exterior flag (set by Vision, re-marked by the pass) and the door — now 1,6 m wide from the walls —
    matched no opening and became „be angos"."""
    hall = _room("01", [door(1000, _exterior=True), door(800), door(900)], angos=[("03", 1.0), ("laukas", 1.6), ("vidus", 0.74)],
                 paskirtis="tamburas")
    for _ in range(3):
        ur.prepare_rooms_for_calc([hall])
        e = hall["elementai"][0]
        assert e.get(ur.EXTERIOR_KEY) is True and e["plotis_mm"] == 1600 and not e.get(ur.UNBACKED_KEY)
        assert e.get(ur.EXTERIOR_MARKED_KEY) is None                  # Vision's flag, not the pass's
    # a door the pass itself called exterior (no Vision flag) is re-derived the same way each run
    kitchen = _room("04", [window(1350), window(1360), door()], angos=[("laukas", 1.37), ("laukas", 1.36), ("laukas", 0.89)], paskirtis="virtuve")
    for _ in range(3):
        ur.prepare_rooms_for_calc([kitchen])
        d = kitchen["elementai"][2]
        assert d.get(ur.EXTERIOR_KEY) is True and d["plotis_mm"] == 890 and d.get(ur.EXTERIOR_MARKED_KEY) is True

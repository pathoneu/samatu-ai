"""2026-10-07 — the units left of a listed window that stood in part take the openings to the outside still free
(universal_rules.reconcile_openings_with_walls, step 4g).

objektas_a 102, production run of 2026-10-07: all three reads listed „langas 2110 ×3"; the walls show an opening
to room 101 (1,15 m) and four to the outside — 2,11, 1,73 (the terrace door 1730 stands there), 3,90 and 0,96 m.
Step 2 stood one unit in the 2,11 m opening and found none within the tolerance for the other two, and step 5
cut them: the room kept ONE window, the 3,90 and 0,96 m openings stayed empty and the project's reveals fell from
82,93 to 52,99 m (true 89,39). The units left now take the openings to the outside still free once the doors,
the drawn doors and the drawn glazing took theirs — the closest width first — and the wall's width. A unit no
free opening is left for is still cut (objektas_h 05); an element none of whose units stood is still kept whole
(moving it too was measured worse); his rooms and a size he typed stay step 4f's.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402
from extractor.project_questions import build_questions  # noqa: E402
from extractor.room_facts import build_room_facts  # noqa: E402

OUTLINE = [[0.2, 0.2], [0.4, 0.2], [0.4, 0.35], [0.2, 0.35]]


def _room(nr, elementai, angos, **more):
    return {"nr": nr, "pavadinimas": f"P{nr}", "paskirtis": more.pop("paskirtis", "gyvenamoji"), "puslapio_nr": 2,
            "plotas_m2": 30.0, "perimetras_m": 24.0, "lubu_aukstis_m": 2.7, "polygon_pct": OUTLINE,
            "polygon_source": "vektoriniai_konturai", "_konturas": {"page": 1}, "elementai": elementai,
            "plotas_saltinis": "inline_label", "lubu_aukstis_saltinis": "per_room",
            "_angos_sienose": {"page": 1, "angos": [
                {"i": i, "plotis_m": w, "storis_m": 0.3, "line_pct": [[0.2 + 0.03 * k, 0.1], [0.22 + 0.03 * k, 0.1]],
                 **({"nupiesta": n} if n else {})}
                for k, (i, w, n) in enumerate(angos)]},
            **more}


def _el(tipas, plotis_mm, kiekis=1, aukstis_mm=None, **more):
    return {"tipas": tipas, "kiekis": kiekis, "plotis_mm": plotis_mm,
            "aukstis_mm": aukstis_mm or (2400 if tipas == "langas" else 2100), **more}


def _pieces(room, tipas):
    """(units, width, openings stood in) per element of that kind, sorted."""
    return sorted((ur._el_units(e), e.get("plotis_mm"), tuple(e.get(ur.OPENING_INDEX_KEY) or ()))
                  for e in room["elementai"] if (e.get("tipas") or "") == tipas)


def _angos(rooms, nr):
    return next(f for f in build_room_facts({"patalpos": rooms}, nr)["facts"] if f["key"] == "angos")


# 102's walls: k=0 to the hall, k=1..4 to the outside
WALLS_102 = [("101", 1.15, None), ("laukas", 2.11, None), ("laukas", 1.73, None), ("laukas", 3.9, None),
             ("laukas", 0.96, None)]


def _room_102(*windows):
    return _room("102", [*windows, _el("duris", 1730), _el("duris", 1150)], WALLS_102, paskirtis="valgomasis")


def test_objektas_a_102_three_listed_windows_stand_in_the_three_openings_to_the_outside():
    room = _room_102(_el("langas", 2110, kiekis=3))
    for run in range(2):                                           # the second run changes nothing
        out = ur.reconcile_openings_with_walls([room])
        # one unit in the 2,11 m opening (step 2), the two left in the 0,96 and 3,90 m ones — with the walls' widths
        assert _pieces(room, "langas") == [(1, 960, (4,)), (1, 2110, (1,)), (1, 3900, (3,))]
        assert all(e.get(ur.WIDTH_SOURCE_KEY) == "sienos" for e in room["elementai"] if e["tipas"] == "langas")
        assert _pieces(room, "duris") == [(1, 1150, (0,)), (1, 1730, (2,))]
        terrace = next(e for e in room["elementai"] if e["tipas"] == "duris" and e["plotis_mm"] == 1730)
        assert terrace.get(ur.EXTERIOR_KEY) is True and terrace[ur.OPENING_SIDE_KEY] == "laukas"
        assert not any(e.get(ur.UNBACKED_KEY) for e in room["elementai"])
        assert out["stood_left"] == (2 if run == 0 else 0)
    # the reveals count all three windows (W + 2H each) and the terrace door again — two windows were missing
    q = ur.calc_room_quantities(room)
    assert abs(q["angokrasciu_gkp_m"] - ((2.11 + 4.8) + (3.9 + 4.8) + (0.96 + 4.8) + (1.73 + 4.2))) < 0.05


def test_the_room_sheet_and_the_questions_no_longer_offer_the_openings_the_windows_stand_in():
    """Cut, the two units left the 3,90 and 0,96 m openings to be offered as NEW windows; standing in them, there
    is nothing left to offer or to name (room_facts._stood_in_walls, project_questions._ask_angos)."""
    room = _room_102(_el("langas", 2110, kiekis=3))
    ur.prepare_rooms_for_calc([room])
    f = _angos([room], "102")
    assert f["status"] == "read" and f["value"] == 5                # 3 windows and 2 doors
    assert f["suggestions"] == [] and f["withheld"] == [] and f["langai_be_angos"] == 0
    assert "neįstatyt" not in f["sentence"] and "Sienose tiek pat angų" in f["sentence"]
    assert not any(q["kind"] == "angos" for q in build_questions({"patalpos": [room]})["questions"])


def test_a_unit_no_free_opening_to_the_outside_is_left_for_is_still_cut():
    """objektas_h 05's shape: „langas 1500 ×2", one glazed opening; the openings to the outside left are the
    listed door's (step 4 stands it there as exterior) and a drawn door's (step 4e adds it) — both taken before
    the window's units left look. An opening to another room is no window's, nor is a gap narrower than a window."""
    room = _room("05", [_el("langas", 1500, kiekis=2, aukstis_mm=1800), _el("duris", 1800)],
                 [("laukas", 1.36, "langas"), ("laukas", 1.8, None), ("laukas", 0.9, "durys"), ("03", 0.8, None),
                  ("laukas", 0.3, None)])
    for _ in range(2):
        out = ur.reconcile_openings_with_walls([room])
        assert _pieces(room, "langas") == [(1, 1360, (0,))]
        assert _pieces(room, "duris") == [(1, 900, (2,)), (1, 1800, (1,))]
        assert all(e.get(ur.EXTERIOR_KEY) for e in room["elementai"] if e["tipas"] == "duris")
        assert out["stood_left"] == 0


def test_an_element_none_of_whose_units_stood_is_kept_whole_and_named_beside_the_openings_left():
    """The run of 2026-10-06 listed „langas 3000 ×2" and „langas 2110": the 3000 element stood nowhere and stays
    whole, its two windows named beside the 3,90 and 0,96 m openings for a look (097a17b) — standing such an
    element in the openings left too took objektas_a's reveals from +0,79 to −2,21 % (eval --replay-geometry)."""
    room = _room_102(_el("langas", 3000, kiekis=2), _el("langas", 2110))
    for _ in range(2):
        out = ur.reconcile_openings_with_walls([room])
        assert _pieces(room, "langas") == [(1, 2110, (1,)), (2, 3000, ())]
        assert out["stood_left"] == 0
    f = _angos([room], "102")
    assert f["suggestions"] == [] and [w["tipas"] for w in f["withheld"]] == ["langas"]
    assert ("Sąraše langai 3,00 m (2 vnt.) neįstatyti į angas, o sienose liko angos 3,90 ir 0,96 m — tikriausiai tai "
            "tie patys langai, tik kito pločio.") in f["sentence"]


def test_his_room_and_a_size_he_typed_stay_step_4f():
    """A room whose doors and windows he corrected keeps the units no opening of their width took as a window
    standing in no opening, and a size he typed is never stood in an opening of another width."""
    his = _room_102(_el("langas", 2110, kiekis=3))
    his[ur.USER_OPENINGS_KEY] = "2026-10-07T09:00:00Z"
    ur.reconcile_openings_with_walls([his])
    assert _pieces(his, "langas") == [(1, 2110, (1,)), (2, 2110, ())]
    typed = _room_102(_el("langas", 3900, kiekis=2, _dydis_user=True))
    ur.reconcile_openings_with_walls([typed])
    assert _pieces(typed, "langas") == [(1, 3900, ()), (1, 3900, (3,))]

"""2026-09-24 — door-less passages: their reveals are finished like a window's (no frame ever covers them),
and a FREE opening wider than a door between two living spaces that nobody stands in IS such a passage
(objektas_h: the 1,56 m opening from the corridor to the living room). The founder: „H angokraščius
grąžink kaip buvo" — measured instead: the old rule's 70 m came from three doors Vision invented."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402


def _room(nr, elementai, angos=None, **more):
    room = {"nr": nr, "pavadinimas": f"P{nr}", "paskirtis": "gyvenamoji", "plotas_m2": 14.0, "perimetras_m": 15.0,
            "lubu_aukstis_m": 2.7, "elementai": elementai, **more}
    if angos is not None:
        room["_angos_sienose"] = {"page": 1, "angos": [
            {"i": i, "plotis_m": w, "line_pct": [[0.1 * k, 0.1], [0.1 * k + 0.05, 0.1]]} for k, (i, w) in enumerate(angos)]}
    return room


def test_a_passage_the_walls_show_gets_reveals_like_a_window_and_no_frame():
    corridor = _room("03", [], paskirtis="koridorius")
    kitchen = _room("04", [{"tipas": "pasleptos_duris", "kiekis": 1, "plotis_mm": 2000, "aukstis_mm": 2400}],
                    angos=[("03", 2.13)], paskirtis="virtuve")
    ur.reconcile_openings_with_walls([corridor, kitchen])
    el = kitchen["elementai"][0]
    assert el.get(ur.PASSAGE_KEY) is True and el["plotis_mm"] == 2130
    ur.settle_frameless_default([kitchen], overrides={"vidaus_durys_beapvadines": True})
    q = ur.calc_room_quantities(kitchen)
    assert q["pasleptu_duru_kompl"] == 0
    assert abs(q["angokrasciu_gkp_m"] - (2.13 + 2 * 2.4)) < 0.01


def test_a_free_wide_opening_between_two_living_spaces_becomes_a_passage_once():
    corridor = _room("03", [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100}],
                     angos=[("05", 1.56), ("06", 0.8)], paskirtis="koridorius")
    living = _room("05", [], angos=[("03", 1.56), ("laukas", 1.36)], paskirtis="gyvenamoji")
    bedroom = _room("06", [], angos=[("03", 0.8)], paskirtis="miegamasis")
    out = ur.reconcile_openings_with_walls([corridor, living, bedroom])
    passages = [(r["nr"], e) for r in (corridor, living, bedroom) for e in r["elementai"] if e.get(ur.PASSAGE_KEY)]
    assert len(passages) == 1, passages
    nr, el = passages[0]
    assert el.get(ur.ADDED_FROM_WALLS_KEY) is True and el["plotis_mm"] == 1560 and el["_is_sienu_angos"] in ("05", "03")
    assert out["passages"] == 1
    # the bedroom lists no door, but the corridor's door already stands in the opening between them — nothing
    # is added on the bedroom's side, and a door-width opening is never a passage
    assert bedroom["elementai"] == []
    assert corridor["elementai"][0][ur.OPENING_SIDE_KEY] == "06"
    # idempotent: a second run stands the added passage in its opening and adds nothing
    before = sum(len(r["elementai"]) for r in (corridor, living, bedroom))
    ur.reconcile_openings_with_walls([corridor, living, bedroom])
    assert sum(len(r["elementai"]) for r in (corridor, living, bedroom)) == before
    q = ur.calc_room_quantities(living if nr == "05" else corridor)
    assert q["angokrasciu_gkp_m"] >= 1.56 + 2 * ur.STANDARD_DOOR_H_M - 0.01


def test_a_free_wide_opening_into_a_bathroom_is_not_a_passage():
    corridor = _room("03", [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100}],
                     angos=[("07", 1.4), ("06", 0.8)], paskirtis="koridorius")
    bath = _room("07", [{"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2100}], angos=[("03", 1.4)], paskirtis="vonia")
    ur.reconcile_openings_with_walls([corridor, bath])
    assert not [e for r in (corridor, bath) for e in r["elementai"] if e.get(ur.PASSAGE_KEY)]

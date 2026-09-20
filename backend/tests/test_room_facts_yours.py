"""A fact that is HIS says so — `yours: true` — so the sheet can badge it.

Founder, after the first real Patikra run (2026-09-17): „sunku suprasti, ar
kažką pataisiau". A corrected fact differed from a read one only by a sentence
(„įrašėte patys"); looking down a room nothing marked what was his.
"""
from __future__ import annotations

from extractor.room_facts import build_room_facts


def _facts(room: dict, project: dict | None = None) -> dict:
    blob = {"patalpos": [{"nr": "3", "puslapio_nr": 1, "paskirtis": "miegamoji", "plotas_m2": 12.0,
                          "perimetras_m": 14.0, "lubu_aukstis_m": 2.7, "lubu_aukstis_saltinis": "section_pjuvis",
                          "walls_paintable_m2": 30.0, "ceiling_paintable_m2": 12.0, "pvc_grindys_m2": 12.0,
                          "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}],
                          **room}],
            **(project or {})}
    return {f["key"]: f for f in build_room_facts(blob, "3")["facts"]}


def test_a_room_nobody_touched_has_nothing_of_his():
    facts = _facts({"plotas_saltinis": "eksplikacija", "perimetras_saltinis": "matmenu_eilutes"})
    assert {k: f["yours"] for k, f in facts.items()} == {
        "plotas": False, "perimetras": False, "aukstis": False, "apdaila": False, "angos": False, "grindys": False}


def test_an_area_he_typed_or_drew():
    assert _facts({"plotas_saltinis": "user_override"})["plotas"]["yours"] is True
    assert _facts({"plotas_source": "manual_polygon"})["plotas"]["yours"] is True
    assert _facts({"plotas_saltinis": "eksplikacija"})["plotas"]["yours"] is False


def test_a_perimeter_he_typed_or_an_estimate_he_accepted():
    assert _facts({"perimetras_saltinis": "user_override"})["perimetras"]["yours"] is True
    assert _facts({"perimetras_saltinis": "konturo_ivertis"})["perimetras"]["yours"] is False


def test_a_height_he_entered_on_the_room_or_in_the_assumptions():
    assert _facts({"lubu_aukstis_saltinis": "user_override"})["aukstis"]["yours"] is True
    assert _facts({}, {"_overrides": {"lubu_auksciai": {"3": 3.1}}})["aukstis"]["yours"] is True
    assert _facts({}, {"_overrides": {"lubu_auksciai": {"4": 3.1}}})["aukstis"]["yours"] is False


def test_walls_he_switched_on_or_off():
    assert _facts({}, {"_overrides": {"walls_paint_override": {"3": 0}}})["apdaila"]["yours"] is True
    assert _facts({"_walls_paint_override": 1})["apdaila"]["yours"] is True
    assert _facts({}, {"_overrides": {"walls_paint_override": {}}})["apdaila"]["yours"] is False


def test_openings_he_counted_or_sized():
    assert _facts({"_angos_user_at": "2026-09-20T10:00:00Z"})["angos"]["yours"] is True
    sized = [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2000, "_dydis_user": True}]
    assert _facts({"elementai": sized})["angos"]["yours"] is True


def test_a_floor_covering_he_chose_but_not_one_the_floor_plan_gave():
    assert _facts({"grindu_danga": "plyteles", "grindu_danga_saltinis": "user_override"})["grindys"]["yours"] is True
    assert _facts({"grindu_danga": "plyteles", "grindu_danga_saltinis": "grindu_planas",
                   "_grindu_danga": {"page": 7, "irodymas": "uzrasas", "tekstas": "plytelės", "rect_pct": [0.1, 0.1, 0.2, 0.2]}
                   })["grindys"]["yours"] is False

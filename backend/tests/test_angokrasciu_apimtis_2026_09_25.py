"""2026-09-25 — which openings' reveals (angokraščiai) the finisher bills is SCOPE, his choice in Prielaidos
(`angokrasciai_apimtis`), never a reading: the drawing shows the openings, the default counts windows, exterior
doors and door-less passages (W + 2H each) and not interior doors. objektas_h: everything drawn is 77,5 m, his
row 63,23 m — without the glass wall and the terrace door 62,9 m, without the passages 64,8 m."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from extractor import universal_rules as ur  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def _room():
    return {"nr": "04", "pavadinimas": "Virtuvė", "paskirtis": "virtuve", "plotas_m2": 26.0, "perimetras_m": 18.0,
            "lubu_aukstis_m": 2.7, "elementai": [
                {"tipas": "langas", "kiekis": 2, "plotis_mm": 1350, "aukstis_mm": 1500},
                {"tipas": "duris", "kiekis": 1, "plotis_mm": 950, "aukstis_mm": 2100, ur.EXTERIOR_KEY: True},
                {"tipas": "duris", "kiekis": 1, "plotis_mm": 2130, "aukstis_mm": 2400, ur.PASSAGE_KEY: True, ur.OPENING_SIDE_KEY: "03"},
                {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100, ur.OPENING_SIDE_KEY: "07"},
            ]}


WINDOWS = 2 * (1.35 + 3.0)
EXTERIOR = 0.95 + 4.2
PASSAGE = 2.13 + 4.8
INTERIOR = 0.8 + 4.2


def _reveals(room):
    return ur.calc_room_quantities(room)["angokrasciu_gkp_m"]


def test_default_scope_is_windows_exterior_doors_and_passages():
    room = _room()
    out = ur.settle_reveals_scope([room], overrides={})
    assert out["value"] == ur.REVEALS_SCOPE_DEFAULT and out["source"] == "numatyta"
    assert "vidaus durų — ne" in out["sakinys"]
    assert abs(_reveals(room) - (WINDOWS + EXTERIOR + PASSAGE)) < 0.01
    # a room the pass never settled uses the same default
    assert abs(_reveals(_room()) - (WINDOWS + EXTERIOR + PASSAGE)) < 0.01


def test_his_choice_switches_kinds_on_and_off():
    room = _room()
    out = ur.settle_reveals_scope([room], overrides={"angokrasciai_apimtis": {"praejimai": False, "vidaus_durys": True}})
    assert out["source"] == "jusu" and out["value"] == {"langai": True, "lauko_durys": True, "praejimai": False, "vidaus_durys": True}
    assert "Jūsų pasirinkimas" in out["sakinys"] and "praėjimų be durų — ne" in out["sakinys"]
    assert abs(_reveals(room) - (WINDOWS + EXTERIOR + INTERIOR)) < 0.01
    ur.settle_reveals_scope([room], overrides={"angokrasciai_apimtis": {"langai": False, "lauko_durys": False}})
    assert abs(_reveals(room) - PASSAGE) < 0.01
    # the frameless-door row does not move with the reveals scope
    ur.settle_frameless_default([room], overrides={"vidaus_durys_beapvadines": True})
    ur.settle_reveals_scope([room], overrides={"angokrasciai_apimtis": {"vidaus_durys": True}})
    q = ur.calc_room_quantities(room)
    assert abs(q["pasleptu_duru_staktu_m"] - INTERIOR) < 0.01 and q["pasleptu_duru_kompl"] == 1
    assert abs(q["angokrasciu_gkp_m"] - (WINDOWS + EXTERIOR + PASSAGE + INTERIOR)) < 0.01


def test_prepare_rooms_settles_the_scope_and_reports_it():
    room = _room()
    out = ur.prepare_rooms_for_calc([room], overrides={"angokrasciai_apimtis": {"praejimai": False}})
    assert out["angokrasciai"]["source"] == "jusu" and room[ur.REVEALS_SCOPE_KEY]["praejimai"] is False


def test_recompute_api_applies_the_scope_to_every_room_with_openings():
    window_room = {"nr": "09", "pavadinimas": "Miegamasis", "paskirtis": "miegamasis", "plotas_m2": 16.0,
                   "perimetras_m": 16.0, "lubu_aukstis_m": 2.7,
                   "elementai": [{"tipas": "langas", "kiekis": 1, "plotis_mm": 1570, "aukstis_mm": 1500}]}
    payload = {"rooms": [_room(), window_room],
               "edits": [{"field": "angokrasciai_apimtis", "new_value": {"langai": False, "praejimai": False}}],
               "current_assumptions": {}}
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    by = {str(x.get("nr")): x for x in body["rooms"]}
    assert abs(float(by["04"]["angokrasciu_gkp_m"]) - EXTERIOR) < 0.01            # windows and the passage are out
    assert abs(float(by["09"]["angokrasciu_gkp_m"])) < 0.01                        # a windows-only room follows too
    assert body["_paruosimas"]["angokrasciai"]["source"] == "jusu"
    # unknown kinds are ignored, known ones coerced to bool
    payload["edits"] = [{"field": "angokrasciai_apimtis", "new_value": {"langai": 1, "kazkas": True}}]
    r = client.post("/api/recompute-quantities", json=payload)
    assert r.status_code == 200 and r.json()["_paruosimas"]["angokrasciai"]["value"]["langai"] is True

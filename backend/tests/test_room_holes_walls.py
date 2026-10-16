"""„Atimti" holes with walls (2026-10-16, togal-v2 W5 follow-up (b)).

A hole cut out of a room's drawn outline is recorded per hole in `_konturas.skyles[i]` with its perimeter,
its convex corners and his answer to „Kas atimama?" (`sienos`). A column / shaft (`sienos: true`) adds its
faces to the walls — 2(a+b) on the wall length behind paint, putty, plaster and skirting — and its four
outer corners × height to kampai, as the fifth ledger term `kampai_skyliu_m`, in both kampai modes. A floor
opening (`sienos: false`) changes nothing. The route side (the record itself, measured on a synthetic plan's
sheet) is in test_room_outline_api.py.
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

import main
from extractor.universal_rules import calc_room_quantities, translate_user_prefs_to_room_rules

H = 2.7
A, B = 0.5, 0.4          # the hole: a 0,5 × 0,4 m column


def _room(sienos=None):
    r = {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 12.0,
         "plotas_saltinis": "eksplikacija", "perimetras_m": 14.0, "perimetras_saltinis": "matmenu_eilutes",
         "lubu_aukstis_m": H, "n_doors": 1, "n_windows": 1}
    if sienos is not None:
        r["_konturas"] = {"page": 1, "saltinis": "nubrezta", "perimetras_m": 14.0, "skyliu_perimetras_m": 2 * (A + B),
                          "skyles": [{"perimetras_m": 2 * (A + B), "plotas_m2": A * B, "kampai": 4, "sienos": sienos}]}
    return r


TERMS = ("kampai_inner_m", "kampai_opening_reveals_m", "kampai_pusiniai_m", "kampai_perimetras_m", "kampai_skyliu_m")


@pytest.mark.parametrize("mode", ["su_vidiniais", "tik_isoriniai"])
def test_a_column_adds_its_faces_to_the_walls_and_its_four_corners_to_kampai(mode):
    rules = translate_user_prefs_to_room_rules({"apimtis": {"kampai": mode}})
    plain = calc_room_quantities(_room(), rules=rules)
    col = calc_room_quantities(_room(True), rules=rules)
    assert col["_walls_perimetras_m"] - plain["_walls_perimetras_m"] == pytest.approx(2 * (A + B), abs=0.01)
    assert col["walls_gross_m2"] - plain["walls_gross_m2"] == pytest.approx(2 * (A + B) * H, abs=0.02)
    assert col["walls_paintable_m2"] - plain["walls_paintable_m2"] == pytest.approx(2 * (A + B) * H, abs=0.02)
    assert col["_grindjuosciu_baze_m"] - plain["_grindjuosciu_baze_m"] == pytest.approx(2 * (A + B), abs=0.02)
    assert col["kampu_metrai"] - plain["kampu_metrai"] == pytest.approx(4 * H, abs=0.01)
    assert col["kampai_skyliu_m"] == pytest.approx(4 * H, abs=0.01)
    assert col["kampai_perimetras_m"] == plain["kampai_perimetras_m"]       # never into the legacy `+ perim` term
    assert sum(col[t] for t in TERMS) == pytest.approx(col["kampu_metrai"], abs=0.02)   # the five-term identity
    assert col["perimetras_m"] == plain["perimetras_m"] == 14.0            # the room's own figure: no double add
    assert col["_skyliu_sienos_m"] == pytest.approx(2 * (A + B), abs=0.01)


def test_a_floor_opening_changes_nothing_and_a_room_without_holes_carries_zero_terms():
    plain = calc_room_quantities(_room())
    assert calc_room_quantities(_room(False)) == plain
    assert plain["kampai_skyliu_m"] == 0.0 and plain["_skyliu_sienos_m"] == 0.0
    assert sum(plain[t] for t in TERMS) == pytest.approx(plain["kampu_metrai"], abs=0.02)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _rows(client, rooms):
    r = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(rooms)})
    assert r.status_code == 200, r.text
    return r.json()


def test_the_rows_move_by_the_column_and_a_rebuild_does_not_add_it_twice(client):
    q = lambda out: {r["aprasymas"]: float(r.get("kiekis") or 0) for r in out["darbu_sarasas"]}  # noqa: E731
    plain, col = _rows(client, [_room()]), _rows(client, [_room(True)])
    assert q(col)["Sienų glaistymas/dažymas"] - q(plain)["Sienų glaistymas/dažymas"] == pytest.approx(2 * (A + B) * H, abs=0.02)
    assert q(col)["Dažymo kampų montavimas"] - q(plain)["Dažymo kampų montavimas"] == pytest.approx(4 * H, abs=0.02)
    assert q(_rows(client, [_room(False)])) == q(plain)
    again = _rows(client, col["patalpos"])
    assert q(again) == q(col)
    kampai = next(r for r in col["darbu_sarasas"] if r["aprasymas"] == "Dažymo kampų montavimas")
    terms = kampai["contributions"][0]["terms"]
    assert terms["kolonų / šachtų kampai"] == pytest.approx(4 * H, abs=0.01)
    assert sum(terms.values()) == pytest.approx(kampai["contributions"][0]["value"], abs=0.02)
    plain_terms = next(r for r in plain["darbu_sarasas"] if r["aprasymas"] == "Dažymo kampų montavimas")["contributions"][0]["terms"]
    assert "kolonų / šachtų kampai" not in plain_terms


# ── follow-up (2): the splash zone and the cornice see a column's faces too ──

def _derived(room):
    from extractor.vision_call import _elementai_to_counts, derive_room_extras
    out = {**room, **calc_room_quantities(room)}
    derive_room_extras(out, _elementai_to_counts(out.get("elementai") or []), None)
    return out


def test_a_column_in_a_wet_room_adds_its_faces_to_the_splash_zone():
    def bath(sienos):
        return {**_room(sienos), "nr": "02", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0}
    plain, col, floor_hole = _derived(bath(None)), _derived(bath(True)), _derived(bath(False))
    assert col["hidroizoliacija_m2"] - plain["hidroizoliacija_m2"] == pytest.approx(2 * (A + B) * 0.30, abs=0.01)
    assert floor_hole["hidroizoliacija_m2"] == plain["hidroizoliacija_m2"]


def test_a_column_adds_its_faces_to_the_cornice_when_the_drawing_has_one():
    from extractor.universal_rules import KARNIZAS_KEY
    def living(sienos):
        return {**_room(sienos), KARNIZAS_KEY: True}
    plain, col = _derived(living(None)), _derived(living(True))
    assert plain["lubu_karnizo_m"] > 0
    assert col["lubu_karnizo_m"] - plain["lubu_karnizo_m"] == pytest.approx(2 * (A + B) * 1.05, abs=0.01)   # + 5 % waste
    assert _derived({**_room(True), KARNIZAS_KEY: False})["lubu_karnizo_m"] == 0.0                          # no evidence, none


def test_a_room_without_holes_derives_exactly_what_it_did():
    plain = _derived(_room())
    assert plain["hidroizoliacija_m2"] == 0.0 and plain["_skyliu_sienos_m"] == 0.0
    assert plain["calculation_trace"].startswith("perim(14.00)")

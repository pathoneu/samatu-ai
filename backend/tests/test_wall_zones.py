"""v3 W5-E E1 — furniture and panel zones (input) and the §1.1 deduction behind SAMATU_FURNITURE_ZONES (off)."""
import json

import pytest

from extractor import wall_zones as wz
from extractor.universal_rules import calc_room_quantities


def _room(**kw):
    r = {"nr": "5", "pavadinimas": "Miegamasis", "paskirtis": "miegamasis", "plotas_m2": 14.0, "perimetras_m": 15.0,
         "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 1}
    r.update(kw)
    return r


WARDROBE = {"elementai": [{"tipas": "spinta_built_in", "kiekis": 1, "plotis_mm": 2000, "aukstis_mm": 2500}]}


def test_reader_furniture_from_the_plan_and_typed():
    r = _room(**WARDROBE, _baldu_zonos=[{"plotis_m": "1,2", "aukstis_m": 2.0, "page": 3, "rect_pct": [0.1, 0.1, 0.2, 0.2]}])
    t = wz.zone_totals(r)
    assert t["_baldu_zonos_m2"] == 5.0 + 2.4
    assert [z["saltinis"] for z in t["baldu_zonos"]] == ["brezinys", "ivesta"]
    assert t["baldu_zonos"][1]["page"] == 3 and t["baldu_zonos"][1]["rect_pct"] == [0.1, 0.1, 0.2, 0.2]


def test_wardrobe_without_height_is_not_a_zone():
    r = _room(elementai=[{"tipas": "spinta_built_in", "kiekis": 1, "plotis_mm": 2000}])
    assert wz.zone_totals(r)["_baldu_zonos_m2"] == 0.0


def test_reader_panels_from_the_finish_share():
    r = _room(sienu_apdailos_breakdown={"dazymas_share": 0.8, "plokste_share": 0.2}, walls_gross_m2=40.0,
              doors_deducted_m2=2.0, _plokstes_zonos=[{"plotis_m": 1, "aukstis_m": 1}])
    t = wz.zone_totals(r)
    assert t["_plokstes_zonos_m2"] == round(0.2 * 38.0 + 1.0, 2)
    assert t["plokstes_zonos"][0]["saltinis"] == "apdailos_lentele"


def test_nonsense_typed_zones_are_ignored():
    r = _room(_baldu_zonos=[{"plotis_m": 0, "aukstis_m": 2}, {"plotis_m": 99, "aukstis_m": 2}, "x"])
    assert wz.zone_totals(r)["_baldu_zonos_m2"] == 0.0


def test_flag_off_changes_nothing(monkeypatch):
    monkeypatch.delenv(wz.FLAG_ENV, raising=False)
    a = calc_room_quantities(_room(**WARDROBE))
    monkeypatch.setenv(wz.FLAG_ENV, "0")
    b = calc_room_quantities(_room(**WARDROBE))
    c = calc_room_quantities(_room())
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)
    assert a["walls_paintable_m2"] == c["walls_paintable_m2"]
    assert "_zonos_atimta_m2" not in a


def test_flag_on_deducts(monkeypatch):
    monkeypatch.setenv(wz.FLAG_ENV, "1")
    base = calc_room_quantities(_room())
    on = calc_room_quantities(_room(**WARDROBE))
    assert on["walls_paintable_m2"] == pytest.approx(base["walls_paintable_m2"] - 5.0, abs=0.01)
    assert on["_zonos_atimta_m2"] == 5.0
    # never below zero
    huge = calc_room_quantities(_room(_baldu_zonos=[{"plotis_m": 30, "aukstis_m": 10}] * 3))
    assert huge["walls_paintable_m2"] == 0.0


# ── the check sheet (Patikra) ──────────────────────────────────────────────────────────────────────────

from extractor import niche_depth as nd  # noqa: E402
from extractor import user_text  # noqa: E402
from extractor.room_facts import build_room_facts  # noqa: E402


def _project(room):
    room = {**room, "puslapio_nr": 1}
    room.update(calc_room_quantities(room))
    return {"patalpos": [room], "darbu_sarasas": []}


def _facts(project):
    return {f["key"]: f for f in build_room_facts(project, "5")["facts"]}


def test_sheet_shows_zones_only_when_there_are_some(monkeypatch):
    monkeypatch.delenv(wz.FLAG_ENV, raising=False)
    assert "baldu_zonos" not in _facts(_project(_room()))
    assert "baldu_zonos" not in _facts(_project(_room(**WARDROBE)))       # flag off, nothing typed: sheet unchanged
    f = _facts(_project(_room(**WARDROBE, **{wz.TYPED_FURNITURE_M2: 1.0})))["baldu_zonos"]
    assert f["value"] == 6.0 and f["unit"] == "m²" and f["editable"]["field"] == wz.TYPED_FURNITURE_M2
    assert "2,00 × 2,50 m = 5,00 m² (plane)" in f["sentence"] and "įskaičiuotas" in f["sentence"]
    assert not user_text.is_banned(f["sentence"])
    monkeypatch.setenv(wz.FLAG_ENV, "1")
    f = _facts(_project(_room(**WARDROBE)))["baldu_zonos"]
    assert f["value"] == 5.0 and "atimtas" in f["sentence"]


def test_typed_zone_total_is_his(monkeypatch):
    monkeypatch.delenv(wz.FLAG_ENV, raising=False)
    f = _facts(_project(_room(**{wz.TYPED_PANEL_M2: 3.5})))["plokstes_zonos"]
    assert f["value"] == 3.5 and f["yours"] is True and "įrašėte patys" in f["sentence"]


def test_niche_depth_fact(monkeypatch):
    monkeypatch.delenv(nd.FLAG_ENV, raising=False)
    niche = {"elementai": [{"tipas": "nisa_LED", "ilgis_m": 4.0}], "nisu_metrai": 4.0}
    assert "nisos_gylis" not in _facts(_project(_room(**niche)))          # flag off, nothing typed: no question
    f = _facts(_project(_room(**niche, nisos_gylis_m=0.15)))["nisos_gylis"]
    assert f["value"] == 0.15 and f["yours"] is True and "metrais" in f["sentence"]
    monkeypatch.setenv(nd.FLAG_ENV, "1")
    f = _facts(_project(_room(**niche)))["nisos_gylis"]
    assert f["status"] == "missing" and f["value"] is None and not user_text.is_banned(f["sentence"])


def test_wardrobe_length_without_height_asks(monkeypatch):
    room = _room(elementai=[{"tipas": "spinta_built_in", "kiekis": 1, "ilgis_m": 2.5}])
    assert wz.wardrobes_without_height(room) == [2.5]
    monkeypatch.delenv(wz.FLAG_ENV, raising=False)
    assert "baldu_zonos" not in _facts(_project(room))
    monkeypatch.setenv(wz.FLAG_ENV, "1")
    f = _facts(_project(room))["baldu_zonos"]
    assert f["status"] == "missing" and f["value"] is None and "2,50 m ilgio" in f["sentence"]
    assert not user_text.is_banned(f["sentence"])


def test_panels_are_never_deducted(monkeypatch):
    monkeypatch.setenv(wz.FLAG_ENV, "1")
    plain = calc_room_quantities(_room())
    panels = calc_room_quantities(_room(sienu_apdailos_breakdown={"dazymas_share": 0.8, "plokste_share": 0.2},
                                        **{wz.TYPED_PANEL_M2: 3.0}))
    assert "_zonos_atimta_m2" not in panels
    f = _facts(_project(_room(sienu_apdailos_breakdown={"dazymas_share": 0.8, "plokste_share": 0.2})))["plokstes_zonos"]
    assert "lieka dažomame sienų plote" in f["sentence"] and not user_text.is_banned(f["sentence"])
    typed = calc_room_quantities(_room(**{wz.TYPED_FURNITURE_M2: 2.0}))
    assert typed["_zonos_atimta_m2"] == 2.0
    assert typed["walls_paintable_m2"] == round(plain["walls_paintable_m2"] - 2.0, 2)

"""A room-sheet recompute must give the SAME per-room numbers as a fresh
extraction of the same primitives.

Found 2026-09-07 while checking the demo project like a contractor: the first
click on any „ką skaičiuoti" choice changed the wall area of every room and the
kampuotė metres by −10 / −5 / +4,2 m, and the numbers never came back — the
`/recompute-interior` handler passed the raw room to the calculator, which
therefore counted its default 1 door + 1 window instead of the drawing's
openings (the Prielaidos path had the fix since 2026-07-29, this one did not).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import main
from extractor.vision_call import _recompute_per_room_via_python

FIXTURE = Path(__file__).resolve().parents[2] / "ground_truth" / "objektas_g" / "ai_extract.json"
COMPARED = ("walls_paintable_m2", "ceiling_paintable_m2", "kampai_m", "kampu_metrai",
            "kampai_opening_reveals_m", "grindjuosciu_m", "plyteles_sienos_m2",
            "plyteles_grindys_m2", "angokrasciu_gkp_m", "dazymo_plotas_m2",
            # steps 4–6: the materials and the rest the calculator does not return
            "hidroizoliacija_m2", "glaistas_kg", "dazai_l", "gruntas_l",
            "lubu_karnizo_m", "nisu_metrai")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _rooms_with_openings():
    """Synthetic rooms in the fixture's shape: a living room with 3 doors +
    1 window, a bathroom with 1 door and NO window, a room with no elementai."""
    return [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 37.86,
         "perimetras_m": 27.5, "lubu_aukstis_m": 2.82,
         "elementai": [{"tipas": "langas", "plotis_mm": 2850, "aukstis_mm": 2200, "kiekis": 1},
                       {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2400, "kiekis": 2},
                       {"tipas": "pasleptos_duris", "plotis_mm": 900, "aukstis_mm": 2400, "kiekis": 1}]},
        {"nr": "06", "pavadinimas": "Vonios kambarys", "paskirtis": "vonia", "plotas_m2": 7.25,
         "perimetras_m": 11.2, "lubu_aukstis_m": 2.82, "plyteles_sienos_aukstis_m": 2.4,
         "elementai": [{"tipas": "duris", "plotis_mm": 800, "aukstis_mm": 2100, "kiekis": 1}]},
        {"nr": "09", "pavadinimas": "Techninė patalpa", "paskirtis": "katiline", "plotas_m2": 6.78,
         "perimetras_m": 10.6, "lubu_aukstis_m": 2.82, "elementai": []},
    ]


def _by_nr(rooms):
    return {r["nr"]: r for r in rooms}


def _assert_parity(fresh, sheet):
    for nr, f in fresh.items():
        s = sheet[nr]
        for k in COMPARED:
            if f.get(k) is None and s.get(k) is None:
                continue
            assert s.get(k) == pytest.approx(f.get(k), abs=0.011), \
                f"room {nr} {k}: fresh extraction {f.get(k)} vs room-sheet recompute {s.get(k)}"


def test_room_sheet_recompute_counts_the_drawings_openings_like_a_fresh_run(client):
    rooms = _rooms_with_openings()
    fresh = _by_nr(_recompute_per_room_via_python({"patalpos": copy.deepcopy(rooms)}, None)["patalpos"])
    r = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(rooms)})
    assert r.status_code == 200, r.text
    sheet = _by_nr(r.json()["patalpos"])
    _assert_parity(fresh, sheet)
    # and the bathroom really has no phantom window: one door's reveal only
    assert sheet["06"]["kampai_opening_reveals_m"] == pytest.approx(fresh["06"]["kampai_opening_reveals_m"])
    assert sheet["06"]["kampai_opening_reveals_m"] < 5.5


def test_a_second_recompute_of_the_same_rooms_is_a_fixed_point(client):
    rooms = _rooms_with_openings()
    first = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(rooms)}).json()["patalpos"]
    second = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(first)}).json()["patalpos"]
    _assert_parity(_by_nr(first), _by_nr(second))


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture not on this machine")
def test_parity_holds_on_a_real_out_of_sample_fixture(client):
    fx = json.loads(FIXTURE.read_text())
    fresh = _by_nr(_recompute_per_room_via_python(copy.deepcopy(fx), None)["patalpos"])
    body = {"patalpos": copy.deepcopy(fx["patalpos"]), "archetipas": fx.get("archetipas"),
            "_ceiling_anchor": fx.get("_ceiling_anchor"), "context": {}}
    r = client.post("/recompute-interior", json=body)
    assert r.status_code == 200, r.text
    _assert_parity(fresh, _by_nr(r.json()["patalpos"]))


def _row_total(rows, *prefixes):
    return sum(float(r.get("kiekis") or 0) for r in rows
               if any((r.get("aprasymas") or "").startswith(p) for p in prefixes))


def test_the_material_litres_follow_the_recomputed_areas(client):
    """Walls measured through the openings are larger, so the paint, putty and
    primer for them must be larger too — not a frozen first-run total re-split."""
    rooms = _rooms_with_openings()
    a = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(rooms),
                    "rules_override": {"apimtis": {"sienos_angos": "atimti"}}}).json()
    b = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(rooms),
                    "rules_override": {"apimtis": {"sienos_angos": "neatimti"}}}).json()
    walls_a = _row_total(a["darbu_sarasas"], "Sienų glaistymas/dažymas")
    walls_b = _row_total(b["darbu_sarasas"], "Sienų glaistymas/dažymas")
    assert walls_b > walls_a
    for prefixes in (("Dažai sienoms", "Dažai luboms"), ("Glaistas sienoms", "Glaistas luboms"),
                     ("Gruntas sienoms", "Gruntas luboms")):
        ta, tb = _row_total(a["darbu_sarasas"], *prefixes), _row_total(b["darbu_sarasas"], *prefixes)
        assert tb > ta, f"{prefixes}: {ta} → {tb} while the walls grew {walls_a} → {walls_b}"
    # and the trace on the room describes the recomputed geometry, not the old one
    r01 = next(r for r in b["patalpos"] if r["nr"] == "01")
    assert "3 dur." in r01["calculation_trace"] and "1 lang." in r01["calculation_trace"]

"""The putty (glaistymo) Q-level travels under two key names.

The Prielaidos panel stores `glaistimo_lygis`; the project wizard and older
blobs store `glaistas_q_lygis`, and the row builder plus `derive_room_extras`
read only the second one. Only `/api/recompute-quantities` bridged the names,
so the next room edit (`/recompute-interior`, fed the persisted `_overrides`)
fell back to Q2: putty kilograms dropped ~4,8× and the Q4 sanding rows vanished
while the panel still showed Q4 (audit calc-engine-1, 2026-09-29).
"""
from __future__ import annotations

import copy

import pytest
from fastapi.testclient import TestClient

import main
from extractor.vision_call import _calc_glaistas_kg, _recompute_per_room_via_python


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _stored_rooms():
    """Rooms as a stored project carries them: primitives + computed fields."""
    rooms = [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
         "perimetras_m": 22.0, "lubu_aukstis_m": 2.8,
         "elementai": [{"tipas": "langas", "plotis_mm": 1500, "aukstis_mm": 1500, "kiekis": 1},
                       {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": 1}]},
        {"nr": "02", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji", "plotas_m2": 14.0,
         "perimetras_m": 15.2, "lubu_aukstis_m": 2.8,
         "elementai": [{"tipas": "langas", "plotis_mm": 1200, "aukstis_mm": 1500, "kiekis": 1},
                       {"tipas": "duris", "plotis_mm": 800, "aukstis_mm": 2100, "kiekis": 1}]},
    ]
    return _recompute_per_room_via_python({"patalpos": rooms}, None)["patalpos"]


def _putty_rows(rows):
    return {p["aprasymas"]: p["kiekis"] for p in rows
            if (p.get("aprasymas") or "").startswith("Glaistas ")}


def _q4_sanding(rows):
    return {p["aprasymas"]: p["kiekis"] for p in rows
            if "šlifavimas Q4" in (p.get("aprasymas") or "")}


def _interior(client, rooms, overrides):
    r = client.post("/recompute-interior",
                    json={"patalpos": copy.deepcopy(rooms), "rules_override": overrides})
    assert r.status_code == 200, r.text
    return r.json()


def test_normaliser_reads_either_name_and_prefers_the_prielaidos_key():
    from extractor.vision_call import putty_q_level
    assert putty_q_level(None) == "Q2"
    assert putty_q_level({}) == "Q2"
    assert putty_q_level({}, default=None) is None
    assert putty_q_level({"glaistas_q_lygis": "Q3"}) == "Q3"
    assert putty_q_level({"glaistimo_lygis": "Q4"}) == "Q4"
    # the panel shows glaistimo_lygis, and it is the later edit
    assert putty_q_level({"glaistas_q_lygis": "Q3", "glaistimo_lygis": "Q4"}) == "Q4"


def test_q4_chosen_in_prielaidos_survives_the_next_room_edit(client):
    rooms = _stored_rooms()
    # 1. Prielaidos: Q4
    r = client.post("/api/recompute-quantities", json={
        "rooms": copy.deepcopy(rooms),
        "edits": [{"field": "glaistimo_lygis", "new_value": "Q4"}],
        "current_assumptions": {},
        "context": {"detected_symbols_summary": {}},
    })
    assert r.status_code == 200, r.text
    body = r.json()
    prielaidos_putty = _putty_rows(body["pozicijos"])
    prielaidos_sanding = _q4_sanding(body["pozicijos"])
    assert prielaidos_putty and prielaidos_sanding, [p.get("aprasymas") for p in body["pozicijos"]]

    # 2. The frontend persists `_overrides = {..._overrides, ...assumptions}`
    #    and the next room edit sends it as rules_override.
    persisted = {**body["assumptions"]}
    assert persisted.get("glaistimo_lygis") == "Q4"
    sheet = _interior(client, body["rooms"], persisted)
    rows = sheet["pozicijos"]

    assert _q4_sanding(rows) == pytest.approx(prielaidos_sanding, abs=0.011)
    assert _putty_rows(rows) == pytest.approx(prielaidos_putty, abs=0.011)
    for room in sheet["patalpos"]:
        assert room["glaistas_kg"] == pytest.approx(
            _calc_glaistas_kg(float(room["dazymo_plotas_m2"]), "Q4"), abs=0.011)


def test_either_key_name_gives_the_same_room_edit_result(client):
    rooms = _stored_rooms()
    a = _interior(client, rooms, {"glaistimo_lygis": "Q4"})
    b = _interior(client, rooms, {"glaistas_q_lygis": "Q4"})
    assert _q4_sanding(a["pozicijos"])
    assert [(p["aprasymas"], p["kiekis"]) for p in a["pozicijos"]] == \
           [(p["aprasymas"], p["kiekis"]) for p in b["pozicijos"]]
    assert [r["glaistas_kg"] for r in a["patalpos"]] == [r["glaistas_kg"] for r in b["patalpos"]]


def test_no_putty_key_is_the_q2_default_unchanged(client):
    rooms = _stored_rooms()
    none_set = _interior(client, rooms, {})
    explicit_q2 = _interior(client, rooms, {"glaistas_q_lygis": "Q2"})
    assert not _q4_sanding(none_set["pozicijos"])
    assert [(p["aprasymas"], p["kiekis"]) for p in none_set["pozicijos"]] == \
           [(p["aprasymas"], p["kiekis"]) for p in explicit_q2["pozicijos"]]
    for room in none_set["patalpos"]:
        assert room["glaistas_kg"] == pytest.approx(
            _calc_glaistas_kg(float(room["dazymo_plotas_m2"]), "Q2"), abs=0.011)


def test_prielaidos_path_reads_the_wizard_key_too(client):
    """A project whose Q-level came from the wizard (`glaistas_q_lygis`) gets
    the same putty kilograms from a Prielaidos edit as one set in the panel."""
    rooms = _stored_rooms()

    def _prielaidos(assumptions):
        r = client.post("/api/recompute-quantities", json={
            "rooms": copy.deepcopy(rooms),
            "edits": [{"field": "lubu_auksciai", "new_value": {"01": 3.0}}],
            "current_assumptions": assumptions,
            "context": {"detected_symbols_summary": {}},
        })
        assert r.status_code == 200, r.text
        return r.json()

    wizard = _prielaidos({"glaistas_q_lygis": "Q4"})
    panel = _prielaidos({"glaistimo_lygis": "Q4"})
    assert [r.get("glaistas_kg") for r in wizard["rooms"]] == \
           [r.get("glaistas_kg") for r in panel["rooms"]]
    assert _putty_rows(wizard["pozicijos"]) == _putty_rows(panel["pozicijos"])
    assert _q4_sanding(wizard["pozicijos"])

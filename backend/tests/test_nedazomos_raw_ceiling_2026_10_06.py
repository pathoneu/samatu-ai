"""2026-10-06 — „Nedažomos" on a raw garage must not paint its ceiling.

A room whose room type has no interior finish (garažas, tambūras) and whose drawing shows none comes out of
the extraction with bare walls AND a bare ceiling — the unfinished-ceiling gate in
universal_rules.calc_room_quantities. The Patikra walls question proposes „Nedažomos" for exactly that room;
confirming it, or picking it in Nustatymai, sends `walls_paint_override = 0`, which reaches the calculator as
`walls_paint_factor_override = 0.0` — and the gate only fired while that override was ABSENT. Measured on a
44 m² garage: ceiling 0 → 44 m² on both live recompute paths, the putty, primer and paint with it.

Now an explicit „Nedažomos" gives the room a fresh extraction gives, on /api/recompute-quantities and on
/recompute-interior alike, down to the sąmata rows; only „Dažomos" (an override above 0) treats the room as
finished. A finished room type keeps its ceiling whatever he says about its walls.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
from extractor.vision_call import (  # noqa: E402
    _build_pozicijos_from_rooms, _emit_v8_compat_fields, _recompute_per_room_via_python,
    _recompute_santrauka,
)

ROOM_KEYS = ("walls_paintable_m2", "ceiling_paintable_m2", "dazymo_plotas_m2", "gkp_lubu_standart_m2",
             "gkp_lubu_virs_3m_m2", "glaistas_kg", "gruntas_l", "kampu_metrai")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _raw(nr="15", paskirtis="garazas", name="Garažas", plotas=44.0, perim=27.0):
    """A room the standard leaves unfinished — no finishes read, the ceiling type from the room type."""
    return {"nr": nr, "pavadinimas": name, "paskirtis": paskirtis, "plotas_m2": plotas,
            "perimetras_m": perim, "lubu_aukstis_m": 2.82,
            "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}]}


def _living(**kw):
    room = {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
            "perimetras_m": 22.0, "lubu_aukstis_m": 2.8,
            "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}]}
    room.update(kw)
    return room


def _extracted(rooms):
    """The extraction path's tail on these primitives: per-room engine, totals, rows."""
    parsed = _recompute_per_room_via_python({"patalpos": copy.deepcopy(rooms), "bendras_plotas_m2": 30.0}, None)
    parsed = _recompute_santrauka(parsed)
    parsed = _build_pozicijos_from_rooms(parsed)
    return _emit_v8_compat_fields(parsed)


def _prielaidos(client, parsed, choice):
    res = client.post("/api/recompute-quantities", json={
        "rooms": copy.deepcopy(parsed["patalpos"]), "pozicijos": copy.deepcopy(parsed["pozicijos"]),
        "darbu_sarasas": copy.deepcopy(parsed["darbu_sarasas"]),
        "edits": [{"field": "walls_paint_override", "new_value": choice}],
        "current_assumptions": {}, "context": {"bendras_plotas_m2": 30.0}})
    assert res.status_code == 200, res.text
    body = res.json()
    return body["rooms"], body


def _room_sheet(client, parsed, choice):
    res = client.post("/recompute-interior", json={
        "patalpos": copy.deepcopy(parsed["patalpos"]), "bendras_plotas_m2": 30.0,
        "rules_override": {"walls_paint_override": choice}})
    assert res.status_code == 200, res.text
    body = res.json()
    return body["patalpos"], body


PATHS = {"prielaidos": _prielaidos, "room_sheet": _room_sheet}


def _by_nr(rooms):
    return {str(r["nr"]): r for r in rooms}


def _paint_litres(room):
    # the Prielaidos path splits the one canonical figure into walls + ceiling
    return float(room.get("dazai_l") or 0) + float(room.get("dazai_luboms_l") or 0)


def _rows(body):
    return {(r.get("skyrius"), r.get("aprasymas")): round(float(r.get("kiekis") or 0), 2)
            for r in body["darbu_sarasas"]}


@pytest.mark.parametrize("path", sorted(PATHS))
@pytest.mark.parametrize("raw", [_raw(), _raw("02", "tamburas", "Tambūras", 7.36, 11.4)],
                         ids=["garazas", "tamburas"])
def test_nedazomos_on_a_raw_room_is_the_room_the_extraction_gives(client, path, raw):
    parsed = _extracted([raw, _living()])
    fresh = _by_nr(parsed["patalpos"])[raw["nr"]]
    assert fresh["walls_paintable_m2"] == 0 and fresh["ceiling_paintable_m2"] == 0   # the drawing's default

    rooms, body = PATHS[path](client, parsed, {raw["nr"]: 0})
    out = _by_nr(rooms)[raw["nr"]]
    for k in ROOM_KEYS:
        assert out.get(k) == pytest.approx(fresh.get(k), abs=0.011), \
            f"{path} {k}: extraction {fresh.get(k)} vs after „Nedažomos“ {out.get(k)}"
    assert _paint_litres(out) == pytest.approx(_paint_litres(fresh), abs=0.02)
    assert out["_ceiling_paint_source"] == "unfinished_room_standard"
    assert out["_walls_unpainted_reason"] == "override"
    assert any("pažymėjote kaip nedažomas" in n for n in out["_ceiling_finish_assumptions"])
    # and the sąmata he sees is the extraction's, row for row
    fresh_rows, rows = _rows(parsed), _rows(body)
    assert rows == fresh_rows, {k: (fresh_rows.get(k), rows.get(k))
                                for k in set(rows) | set(fresh_rows) if rows.get(k) != fresh_rows.get(k)}


def test_dazomos_finishes_the_garage_and_both_paths_agree(client):
    parsed = _extracted([_raw(), _living()])
    (pri, pri_body), (sheet, sheet_body) = (PATHS[p](client, parsed, {"15": 1}) for p in sorted(PATHS))
    a, b = _by_nr(pri)["15"], _by_nr(sheet)["15"]
    assert a["walls_paintable_m2"] > 0 and a["ceiling_paintable_m2"] == pytest.approx(44.0)
    assert a["_ceiling_paint_source"] == "standard" and not a["_ceiling_finish_assumptions"]
    for k in ROOM_KEYS:
        assert a.get(k) == pytest.approx(b.get(k), abs=0.011), f"{k}: Prielaidos {a.get(k)} vs room sheet {b.get(k)}"
    assert _rows(pri_body) == _rows(sheet_body)


@pytest.mark.parametrize("path", sorted(PATHS))
def test_nedazomos_leaves_a_finished_rooms_concrete_ceiling_painted(client, path):
    """A living room under a READ concrete slab (`lubu_tipas` „betonas“ is a value the reader writes): its
    room type is finished, so „Nedažomos“ for its walls must not take the ceiling with them."""
    parsed = _extracted([_raw(), _living(lubu_tipas="betonas")])
    rooms, _ = PATHS[path](client, parsed, {"01": 0})
    out = _by_nr(rooms)["01"]
    assert out["walls_paintable_m2"] == 0
    assert out["ceiling_paintable_m2"] == pytest.approx(30.0)
    assert out["_ceiling_paint_source"] == "standard"


@pytest.mark.parametrize("path", sorted(PATHS))
def test_nedazomos_over_a_finishes_read_leaves_the_garage_wholly_unfinished(client, path):
    """A garage the finishes table calls painted comes out finished — walls and ceiling. His „Nedažomos“
    overrules the only evidence it had, so the room falls back to its standard: no wall and no ceiling paint
    (0 m² of wall beside 20 m² of painted raw slab is the split the gate exists to prevent)."""
    garage = {**_raw(plotas=20.0, perim=18.0), "sienu_apdailos_breakdown": {"dazai_share": 1.0}}
    parsed = _extracted([garage, _living()])
    fresh = _by_nr(parsed["patalpos"])["15"]
    assert fresh["walls_paintable_m2"] > 0 and fresh["ceiling_paintable_m2"] == pytest.approx(20.0)
    rooms, _ = PATHS[path](client, parsed, {"15": 0})
    out = _by_nr(rooms)["15"]
    assert out["walls_paintable_m2"] == 0 and out["ceiling_paintable_m2"] == 0
    assert out["dazymo_plotas_m2"] == 0 and out["glaistas_kg"] == 0

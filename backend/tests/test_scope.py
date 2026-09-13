"""Apimtis — what the contractor does and does not do (item 4, 2026-09-06).

Server-side enforcement: an excluded room stays on the sheet but leaves every
row, total and the ceiling anchor; a family that is off drops its rows and
their materials; „lubos ne mūsų" empties the ceiling rows; „sienos be angų"
stops the openings deduction. Synthetic rooms only.
"""
from __future__ import annotations

import copy
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SAMATU_AUTH_DISABLED", "1")

from extractor.ledger import replay  # noqa: E402
from extractor.scope import (  # noqa: E402
    EXCLUDED_BECAUSE, EXCLUDED_QUANTITIES_KEY, apply_ceiling_choice, excluded_quantity,
    filter_rows_by_families, mark_rooms, normalize_apimtis, section_family,
)
from main import app  # noqa: E402

client = TestClient(app)


def _door(n=1):
    return {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": n}


def _window(n=1):
    return {"tipas": "langas", "plotis_mm": 1200, "aukstis_mm": 1500, "kiekis": n}


def _rooms():
    # `elementai` is the primitive every recompute path derives the opening
    # counts from (api.recompute_quantities._calc_input); bare n_doors /
    # n_windows on a room are never read in production.
    return [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
         "perimetras_m": 22.0, "lubu_aukstis_m": 2.7, "puslapio_nr": 1,
         "elementai": [_door(1), _window(2)]},
        {"nr": "02", "pavadinimas": "Miegamasis", "paskirtis": "miegamasis", "plotas_m2": 14.0,
         "perimetras_m": 15.0, "lubu_aukstis_m": 2.7, "puslapio_nr": 1,
         "elementai": [_door(1), _window(1)]},
        {"nr": "03", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0,
         "perimetras_m": 10.0, "lubu_aukstis_m": 2.7, "puslapio_nr": 1,
         "hidroizoliacija_m2": 9.5, "elementai": [_door(1)]},
    ]


def _recompute(apimtis=None, anchor=True, walls_anchor=None, floor_anchors=None):
    body = {"patalpos": _rooms(), "rules_override": {}}
    if apimtis is not None:
        body["rules_override"]["apimtis"] = apimtis
    if anchor:
        body["_ceiling_anchor"] = {"total_area_m2": 50.0, "label": "Iš viso", "page": 1}
    if walls_anchor is not None:
        body["_walls_anchor"] = walls_anchor
    if floor_anchors is not None:
        body["_floor_anchors"] = floor_anchors
    res = client.post("/recompute-interior", json=body)
    assert res.status_code == 200, res.text
    out = res.json()
    assert out.get("status") == "ok", out
    return out


def _rows(out, prefix):
    rows = out.get("darbu_sarasas") or out.get("pozicijos") or []
    return [r for r in rows if str(r.get("aprasymas") or "").startswith(prefix)]


def _row(out, prefix):
    hits = _rows(out, prefix)
    return hits[0] if hits else None


def _qty(out, prefix):
    """The family's quantity — iki + virš 3 m tiers summed when a room is tall."""
    return round(sum(float(r.get("kiekis") or 0) for r in _rows(out, prefix)), 2)


# ── the pure helpers ─────────────────────────────────────────────────────────

def test_normalize_keeps_only_real_choices():
    assert normalize_apimtis(None) is None
    assert normalize_apimtis({}) is None
    assert normalize_apimtis({"lubos": "dazomos", "sienos_angos": "atimti", "patalpos_ne": [], "darbai_ne": []}) is None
    a = normalize_apimtis({"patalpos_ne": [7, " 07", "07"], "darbai_ne": ["plyteles", "nesamone"],
                           "lubos": "ne_musu", "sienos_angos": "kazkas",
                           "patalpu_sritys_ne": {"03": ["grindys", "elektra", "x"], " ": ["apdaila"], "05": []},
                           "rotband": "dalis", "rotband_dalis": "45"})
    assert a == {"patalpos_ne": ["07", "7"], "darbai_ne": ["plyteles"],
                 "patalpu_sritys_ne": {"03": ["grindys"]},
                 "lubos": "ne_musu", "sienos_angos": None, "rotband": "dalis", "rotband_dalis": 45.0,
                 "kampai": None}
    assert normalize_apimtis({"rotband": "nera"})["rotband"] == "nera"


def test_section_family_mirrors_the_upload_screen():
    assert section_family("Sienų glaistymas dažymas") == "apdaila"
    assert section_family("Plytelių klijavimas") == "plyteles"
    assert section_family("Grindys") == "grindys"
    assert section_family("Santechnikos darbai") == "santechnika"
    assert section_family("Elektros instaliacijos darbai") == "elektra"
    assert section_family("Ventiliacijos darbai") is None
    assert section_family("Pridėtiniai elementai") is None


def test_mark_rooms_zeroes_and_clears():
    rooms = _rooms()
    rooms[1]["walls_paintable_m2"] = 33.0
    assert mark_rooms(rooms, normalize_apimtis({"patalpos_ne": ["02"]})) == ["02"]
    assert rooms[1]["_neskaiciuoti"] is True and rooms[1]["walls_paintable_m2"] == 0.0
    assert "_neskaiciuoti" not in rooms[0]
    mark_rooms(rooms, None)
    assert "_neskaiciuoti" not in rooms[1], "switching the room back on clears the mark"


def test_family_filter_drops_rows_and_their_materials_but_never_unknown_sections():
    rows = [
        {"aprasymas": "Vonios sienų plytelių klijavimas", "skyrius": "Plytelių klijavimas", "kiekis": 20},
        {"aprasymas": "Sienų glaistymas/dažymas", "skyrius": "Sienų glaistymas dažymas", "kiekis": 200},
        {"aprasymas": "Plytelių klijai", "skyrius": "Medžiagos", "susijes_darbas": "Vonios sienų plytelių klijavimas"},
        {"aprasymas": "Dažai sienoms", "skyrius": "Medžiagos", "susijes_darbas": "Sienų glaistymas/dažymas"},
        {"aprasymas": "Ortakių montavimas", "skyrius": "Ventiliacijos darbai", "kiekis": 40},
    ]
    kept = filter_rows_by_families(rows, normalize_apimtis({"darbai_ne": ["plyteles"]}))
    assert [r["aprasymas"] for r in kept] == ["Sienų glaistymas/dažymas", "Dažai sienoms", "Ortakių montavimas"]
    assert filter_rows_by_families(rows, None) == rows


def test_ceiling_choice_respects_a_rooms_own_flag():
    rooms = _rooms()
    for r in rooms:
        r["ceiling_paintable_m2"] = r["plotas_m2"]
    rooms[0]["ceiling_paint_override"] = True
    n = apply_ceiling_choice(rooms, normalize_apimtis({"lubos": "ne_musu"}))
    assert n == 2
    assert rooms[0]["ceiling_paintable_m2"] == 30.0, "the room's own flag (painted) wins over the project default"
    assert rooms[1]["ceiling_paintable_m2"] == 0.0 and rooms[1]["_ceiling_paint_source"] == "pasirinkimas"


# ── through the endpoint ─────────────────────────────────────────────────────

def test_an_excluded_room_leaves_every_row_but_stays_on_the_sheet():
    base = _recompute()
    out = _recompute({"patalpos_ne": ["02"]})
    rooms = {r["nr"]: r for r in out["patalpos"]}
    assert set(rooms) == {"01", "02", "03"}, "the room is kept, never deleted"
    assert rooms["02"].get("_neskaiciuoti") is True and float(rooms["02"].get("walls_paintable_m2") or 0) == 0
    assert _qty(out, "Sienų glaistymas/dažymas") < _qty(base, "Sienų glaistymas/dažymas")
    assert _qty(out, "Sienų glaistymas/dažymas") == pytest.approx(
        _qty(base, "Sienų glaistymas/dažymas") - float(
            next(r for r in base["patalpos"] if r["nr"] == "02")["walls_paintable_m2"]), abs=0.02)
    assert out["bendras_plotas_m2"] == pytest.approx(36.0)
    assert out.get("_apimtis") == {"patalpos_ne": ["02"], "darbai_ne": [], "patalpu_sritys_ne": {},
                                   "lubos": None, "sienos_angos": None, "rotband": None, "rotband_dalis": None,
                                   "kampai": None}
    walls = _row(out, "Sienų glaistymas/dažymas")
    assert any(e.get("room_nr") == "02" and e.get("excluded_because") == EXCLUDED_BECAUSE
               for e in walls.get("excluded") or []), "the ledger says why the room is out"
    assert all(c.get("room_nr") != "02" for c in walls.get("contributions") or [])


def test_mark_rooms_remembers_what_it_zeroed():
    """An anchored line bills a STATED total (the eksplikacija's ceiling, the
    drawing's painted walls, the floor plan's skirting) and takes the excluded
    rooms' own share off it — a share `mark_rooms` zeroes before the builder
    runs. So the zeroed values stay beside the marks, survive a second marking
    pass over a room nobody recomputed, and go when the room comes back."""
    rooms = _rooms()
    rooms[1]["walls_paintable_m2"] = 33.0
    rooms[1]["grindjuosciu_m"] = 12.5
    mark_rooms(rooms, normalize_apimtis({"patalpos_ne": ["02"]}))
    assert rooms[1]["walls_paintable_m2"] == 0.0 and rooms[1]["grindjuosciu_m"] == 0.0
    assert rooms[1][EXCLUDED_QUANTITIES_KEY] == {"walls_paintable_m2": 33.0, "grindjuosciu_m": 12.5}
    assert excluded_quantity(rooms[1], "walls_paintable_m2") == 33.0
    assert excluded_quantity(rooms[0], "walls_paintable_m2") == 0.0, "nothing held, nothing to remember"
    assert EXCLUDED_QUANTITIES_KEY not in rooms[0]
    mark_rooms(rooms, normalize_apimtis({"patalpos_ne": ["02"]}))   # a second pass: fields already 0
    assert rooms[1][EXCLUDED_QUANTITIES_KEY]["walls_paintable_m2"] == 33.0
    # a family off in one room remembers that family's share only
    rooms = _rooms()
    rooms[0]["walls_paintable_m2"] = 40.0
    rooms[0]["grindjuosciu_m"] = 20.0
    mark_rooms(rooms, normalize_apimtis({"patalpu_sritys_ne": {"01": ["grindys"]}}))
    assert rooms[0]["walls_paintable_m2"] == 40.0 and rooms[0]["grindjuosciu_m"] == 0.0
    assert rooms[0][EXCLUDED_QUANTITIES_KEY] == {"grindjuosciu_m": 20.0}
    assert excluded_quantity(rooms[0], "walls_paintable_m2") == 40.0, "a live value is the share"
    mark_rooms(rooms, None)
    assert EXCLUDED_QUANTITIES_KEY not in rooms[0], "switching the room back on clears the memory"


def test_the_walls_anchor_loses_the_excluded_rooms_share():
    """The sienų apdailos plano legend counts every room; a room he does not do
    comes off it by what THAT room's walls held before the choice zeroed them.
    (2026-09-13: the share read 0,00 — `mark_rooms` runs after the per-room
    math — so an anchored Sienų line never dropped when a room was switched off.)"""
    base = _recompute(anchor=False)
    rooms = {r["nr"]: r for r in base["patalpos"]}
    walls_sum = round(sum(float(r.get("walls_paintable_m2") or 0) for r in rooms.values()), 2)
    share_02 = round(float(rooms["02"]["walls_paintable_m2"]), 2)
    assert walls_sum > 0 and share_02 > 0
    legend = round(walls_sum * 0.9, 2)
    wa = {"total_area_m2": legend, "label": "sienų apdailos plano legenda", "page": 1,
          "parts": [{"value": legend, "label": "Glaistoma dažoma"}]}
    anchored = _recompute(anchor=False, walls_anchor=wa)
    assert _qty(anchored, "Sienų glaistymas/dažymas") == pytest.approx(legend, abs=0.02)
    out = _recompute({"patalpos_ne": ["02"]}, anchor=False, walls_anchor=wa)
    assert _qty(out, "Sienų glaistymas/dažymas") == pytest.approx(legend - share_02, abs=0.02)
    walls = _row(out, "Sienų glaistymas/dažymas")
    assert walls["roll_up"][0]["op"] == "anchor"
    chain = " ".join(f"{s.get('label') or ''} {s.get('note') or ''}" for s in walls["roll_up"])
    assert "neįtrauktos patalpos" in chain
    assert f"Atimta {share_02:.2f}".replace(".", ",") in chain
    assert abs(replay(walls["contributions"], walls["roll_up"]) - float(walls["kiekis"])) <= 0.01
    # the room that is out is named, and its share is remembered on the room itself
    assert any(e.get("room_nr") == "02" for e in walls.get("excluded") or [])
    r02 = next(r for r in out["patalpos"] if r["nr"] == "02")
    assert r02.get(EXCLUDED_QUANTITIES_KEY, {}).get("walls_paintable_m2") == pytest.approx(share_02, abs=0.01)


def _tile_base(r: dict) -> float:
    n_d = sum(int(el.get("kiekis") or 1) for el in (r.get("elementai") or [])
              if (el.get("tipas") or "").lower() in ("duris", "pasleptos_duris"))
    return round(max(0.0, float(r.get("perimetras_m") or 0) - n_d * 0.85) * 1.10, 2)


def test_the_floor_anchors_lose_the_excluded_rooms_share():
    """The grindų plano legend states the skirting metres and the covering m²
    for the whole flat; a room he does not do comes off each by its own share,
    and a room whose tiles he does not do leaves the tile-skirting line."""
    base = _recompute(anchor=False)
    rooms = {r["nr"]: r for r in base["patalpos"]}
    gj = round(sum(float(r.get("grindjuosciu_m") or 0) for r in rooms.values()), 2)
    lam = round(sum(float(r.get("pvc_grindys_m2") or 0) for r in rooms.values()), 2)
    tile_rooms = [r for r in rooms.values() if float(r.get("plyteles_grindys_m2") or 0) > 0]
    tile = round(sum(_tile_base(r) for r in tile_rooms), 2)
    assert gj > 0 and lam > 0 and tile > 0 and [r["nr"] for r in tile_rooms] == ["03"]
    fa = {"grindjuostes": {"total": round(gj * 0.8, 2), "unit": "m", "label": "grindų plano legenda", "page": 1,
                           "parts": [{"value": round(gj * 0.8, 2), "label": "Grindjuostės"}]},
          "laminatas": {"total": round(lam * 0.95, 2), "unit": "m2", "label": "grindų plano legenda", "page": 1,
                        "parts": [{"value": round(lam * 0.95, 2), "label": "laminuota grindų danga"}]},
          "plyteliu_grindjuostes": {"total": round(tile * 0.7, 2), "unit": "m", "label": "grindų plano legenda", "page": 1,
                                    "parts": [{"value": round(tile * 0.7, 2), "label": "Grindjuostės (iš plytelių)"}]}}
    anchored = _recompute(anchor=False, floor_anchors=fa)
    assert _qty(anchored, "Grindjuosčių sumontavimas") == pytest.approx(gj * 0.8, abs=0.02)
    assert _qty(anchored, "Parketo / laminato klojimas") == pytest.approx(lam * 0.95, abs=0.02)
    assert _qty(anchored, "Plytelių grindjuosčių") == pytest.approx(tile * 0.7, abs=0.02)
    assert _qty(anchored, "Grindų dangos pamušalas") == pytest.approx(lam * 0.95, abs=0.02), "the underlay follows the billed covering"
    for prefix in ("Grindjuosčių sumontavimas", "Grindjuosčių dažymas", "Parketo / laminato klojimas", "Plytelių grindjuosčių"):
        row = _row(anchored, prefix)
        assert row["roll_up"][0]["op"] == "anchor" and row["contributions"], prefix
        assert row["contributions_sum_to_total"] is False, prefix
        assert abs(replay(row["contributions"], row["roll_up"]) - float(row["kiekis"])) <= 0.01, prefix
    assert any(c.get("room_nr") == "03" for c in _row(anchored, "Plytelių grindjuosčių")["contributions"]), \
        "the wet room is behind the tile-skirting line — its walls are painted above a tiled base"

    out = _recompute({"patalpos_ne": ["02"]}, anchor=False, floor_anchors=fa)
    share_gj = float(rooms["02"]["grindjuosciu_m"])
    share_lam = float(rooms["02"]["pvc_grindys_m2"])
    assert share_gj > 0 and share_lam > 0
    assert _qty(out, "Grindjuosčių sumontavimas") == pytest.approx(gj * 0.8 - share_gj, abs=0.02)
    assert _qty(out, "Parketo / laminato klojimas") == pytest.approx(lam * 0.95 - share_lam, abs=0.02)
    assert _qty(out, "Plytelių grindjuosčių") == pytest.approx(tile * 0.7, abs=0.02), "02 has no tile floor"
    chain = " ".join(f"{s.get('label') or ''} {s.get('note') or ''}" for s in _row(out, "Grindjuosčių sumontavimas")["roll_up"])
    assert "neįtrauktos patalpos" in chain and f"Atimta {share_gj:.2f}".replace(".", ",") in chain
    assert any(e.get("room_nr") == "02" and e.get("excluded_because") == EXCLUDED_BECAUSE
               for e in _row(out, "Grindjuosčių sumontavimas").get("excluded") or [])

    tiles_off = _recompute({"patalpu_sritys_ne": {"03": ["plyteles"]}}, anchor=False, floor_anchors=fa)
    assert _row(tiles_off, "Plytelių grindjuosčių") is None, "no tile room left in scope — no line, anchored or not"
    assert _qty(tiles_off, "Grindjuosčių sumontavimas") == pytest.approx(gj * 0.8, abs=0.02)


def test_a_typed_perimeter_keeps_its_marker_through_the_recompute():
    """The sheet marks a typed perimeter `user_override` (lib/roomSheet.js
    userEditPatch); the recompute must hand it back so the facts say „įrašėte
    patys" and a re-read of the drawing keeps the number."""
    rooms = _rooms()
    rooms[0]["perimetras_m"] = 23.5
    rooms[0]["perimetras_saltinis"] = "user_override"
    rooms[0]["plotas_saltinis"] = "user_override"
    rooms[0]["_angos_user_at"] = "2026-09-13T12:00:00Z"
    res = client.post("/recompute-interior", json={"patalpos": rooms, "rules_override": {}})
    assert res.status_code == 200, res.text
    r01 = next(r for r in res.json()["patalpos"] if r["nr"] == "01")
    assert r01["perimetras_m"] == 23.5 and r01["perimetras_saltinis"] == "user_override"
    assert r01["plotas_saltinis"] == "user_override" and r01["_angos_user_at"] == "2026-09-13T12:00:00Z"


def test_a_legend_that_describes_another_flat_is_ignored_with_a_warning():
    base = _recompute(anchor=False)
    gj = round(sum(float(r.get("grindjuosciu_m") or 0) for r in base["patalpos"]), 2)
    fa = {"grindjuostes": {"total": round(gj * 3.0, 2), "unit": "m", "label": "grindų plano legenda", "page": 1,
                           "parts": [{"value": round(gj * 3.0, 2), "label": "Grindjuostės"}]}}
    out = _recompute(anchor=False, floor_anchors=fa)
    assert _qty(out, "Grindjuosčių sumontavimas") == pytest.approx(gj, abs=0.02)
    assert _row(out, "Grindjuosčių sumontavimas")["roll_up"][0]["op"] == "sum"
    warns = [w for w in out.get("warnings") or [] if w.get("code") == "grindu_plano_legenda_ignored"]
    assert len(warns) == 1 and warns[0].get("kind") == "grindjuostes"
    assert "Patikrinkite" in warns[0]["message"]


def test_the_ceiling_anchor_loses_the_excluded_rooms_area():
    base = _recompute()
    out = _recompute({"patalpos_ne": ["02"]})
    assert _qty(base, "Lubų glaistymas/dažymas") == pytest.approx(50.0, abs=0.02), "anchored on the table total"
    assert _qty(out, "Lubų glaistymas/dažymas") == pytest.approx(36.0, abs=0.02)
    lubos = _row(out, "Lubų glaistymas/dažymas")
    assert any(s.get("op") == "anchor" for s in lubos.get("roll_up") or [])
    chain = " ".join(f"{s.get('label') or ''} {s.get('note') or ''}" for s in lubos["roll_up"])
    assert "neįtrauktos patalpos" in chain and "Atimta 14,00 m²" in chain


def test_every_scoped_ledger_still_replays_to_its_kiekis():
    out = _recompute({"patalpos_ne": ["02"], "darbai_ne": ["plyteles"]})
    checked = 0
    for r in out["darbu_sarasas"]:
        if r.get("roll_up"):
            assert replay(r.get("contributions"), r["roll_up"]) == pytest.approx(float(r["kiekis"]), abs=0.01), r["aprasymas"]
            checked += 1
    assert checked >= 3


def test_a_family_that_is_off_has_no_rows_and_no_materials():
    out = _recompute({"darbai_ne": ["plyteles"]})
    rows = out["darbu_sarasas"]
    assert not any(str(r.get("skyrius") or "").startswith("Plytelių") for r in rows)
    tile_names = {str(r.get("aprasymas") or "").lower() for r in _recompute()["darbu_sarasas"]
                  if str(r.get("skyrius") or "").startswith("Plytelių")}
    assert not any(str(r.get("susijes_darbas") or "").lower() in tile_names for r in rows)
    assert any(str(r.get("skyrius") or "").startswith("Santechnik") for r in rows), "other families untouched"


def test_ceilings_not_ours_empties_the_ceiling_rows_only():
    base = _recompute()
    out = _recompute({"lubos": "ne_musu"})
    assert _qty(out, "Lubų glaistymas/dažymas") == 0.0
    assert _qty(out, "Sienų glaistymas/dažymas") == pytest.approx(_qty(base, "Sienų glaistymas/dažymas"), abs=0.02)
    lubos = _row(base, "Lubų glaistymas/dažymas")
    assert lubos is not None


def test_stretch_ceilings_for_the_whole_project_unless_a_room_says_otherwise():
    body = {"patalpos": _rooms(), "rules_override": {"apimtis": {"lubos": "itempiamos"},
                                                     "stretch_ceiling_override": {"03": 0}},
            "_ceiling_anchor": {"total_area_m2": 50.0, "label": "Iš viso", "page": 1}}
    res = client.post("/recompute-interior", json=body)
    assert res.status_code == 200
    out = res.json()
    assert _qty(out, "Lubų glaistymas/dažymas") == pytest.approx(6.0, abs=0.02), \
        "only the bathroom (its own flag: not stretch) keeps a painted ceiling"


def test_walls_without_openings_are_larger_by_the_openings():
    base = _recompute()
    out = _recompute({"sienos_angos": "neatimti"})
    assert _qty(out, "Sienų glaistymas/dažymas") > _qty(base, "Sienų glaistymas/dažymas")
    r01_base = next(r for r in base["patalpos"] if r["nr"] == "01")
    r01 = next(r for r in out["patalpos"] if r["nr"] == "01")
    assert r01["walls_paintable_m2"] > r01_base["walls_paintable_m2"]
    assert r01["walls_paintable_m2"] == pytest.approx(22.0 * 2.7, abs=0.5), "perimeter × height, nothing deducted"


def test_no_scope_is_byte_identical_to_before():
    a = _recompute()
    b = _recompute({"lubos": "dazomos", "sienos_angos": "atimti"})
    assert [(r["aprasymas"], r.get("kiekis")) for r in a["darbu_sarasas"]] == \
           [(r["aprasymas"], r.get("kiekis")) for r in b["darbu_sarasas"]]
    assert "_apimtis" not in b


def test_a_prielaidos_edit_keeps_the_scope():
    """The assumptions panel recomputes through /api/recompute-quantities with
    the scope folded into `current_assumptions` — the excluded room must stay
    out of the rebuilt rows there too, or one height edit would silently put
    it back."""
    first = _recompute({"patalpos_ne": ["02"]})
    body = {
        "rooms": first["patalpos"],
        "pozicijos": first.get("pozicijos") or [],
        "darbu_sarasas": first.get("darbu_sarasas") or [],
        "edits": [{"field": "lubu_auksciai", "new_value": {"01": 3.0}}],
        "current_assumptions": {"apimtis": {"patalpos_ne": ["02"]}},
        "context": {"_ceiling_anchor": {"total_area_m2": 50.0, "label": "Iš viso", "page": 1},
                    "_overrides": {}},
    }
    res = client.post("/api/recompute-quantities", json=body)
    assert res.status_code == 200, res.text
    out = res.json()
    rooms = {str(r.get("nr")): r for r in (out.get("rooms") or out.get("patalpos") or [])}
    assert rooms["02"].get("_neskaiciuoti") is True
    walls_rows = _rows(out, "Sienų glaistymas/dažymas")
    assert walls_rows
    for w in walls_rows:
        assert all(c.get("room_nr") != "02" for c in w.get("contributions") or [])
    assert _qty(out, "Sienų glaistymas/dažymas") > _qty(first, "Sienų glaistymas/dažymas"), \
        "room 01 grew taller — still without room 02"


def test_walls_without_openings_also_on_the_wall_finish_branch():
    """Rooms read from the išklotinės go through the apdailos branch, which
    deducts a standardised door area of its own — the choice has to reach it
    too, or a project with finish sheets would ignore „be angų"."""
    from extractor.universal_rules import ROOM_TYPE_RULES, calc_room_quantities
    room = {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 30.0,
            "perimetras_m": 22.0, "lubu_aukstis_m": 2.7, "n_doors": 2, "n_windows": 1,
            "sienu_apdailos_breakdown": {"dazai_share": 1.0}}
    with_deduction = calc_room_quantities(dict(room))
    rules = {k: dict(v) for k, v in ROOM_TYPE_RULES.items()}
    for rt in rules:
        rules[rt]["deduct_openings"] = False
    without = calc_room_quantities(dict(room), rules=rules)
    assert without["walls_paintable_m2"] > with_deduction["walls_paintable_m2"]
    assert without["walls_paintable_m2"] == pytest.approx(22.0 * 2.7, abs=0.5)


def test_a_room_switched_back_on_comes_back():
    """The mark rides on the stored room dicts; a later recompute WITHOUT a
    scope (the choice was undone → nothing to send) must clear it."""
    off = _recompute({"patalpos_ne": ["02"]})
    body = {"patalpos": off["patalpos"], "rules_override": {},
            "_ceiling_anchor": {"total_area_m2": 50.0, "label": "Iš viso", "page": 1}}
    res = client.post("/recompute-interior", json=body)
    assert res.status_code == 200
    back = res.json()
    r02 = next(r for r in back["patalpos"] if r["nr"] == "02")
    assert not r02.get("_neskaiciuoti") and float(r02["walls_paintable_m2"]) > 0
    assert _qty(back, "Sienų glaistymas/dažymas") == pytest.approx(_qty(_recompute(), "Sienų glaistymas/dažymas"), abs=0.02)
    assert _qty(back, "Lubų glaistymas/dažymas") == pytest.approx(50.0, abs=0.02)


# ── one room, one family off ─────────────────────────────────────────────────

def test_a_family_switched_off_in_one_room_leaves_that_rooms_share_only():
    base = _recompute()
    out = _recompute({"patalpu_sritys_ne": {"01": ["grindys"]}})
    r01b = next(r for r in base["patalpos"] if r["nr"] == "01")
    r01 = next(r for r in out["patalpos"] if r["nr"] == "01")
    assert r01.get("_neskaiciuoti_sritys") == ["grindys"] and not r01.get("_neskaiciuoti")
    assert float(r01["walls_paintable_m2"]) == pytest.approx(float(r01b["walls_paintable_m2"]), abs=0.01), "walls untouched"
    assert float(r01.get("pvc_grindys_m2") or 0) == 0 and float(r01.get("grindjuosciu_m") or 0) == 0
    assert _qty(out, "Parketo / laminato klojimas") == pytest.approx(
        _qty(base, "Parketo / laminato klojimas") - float(r01b.get("pvc_grindys_m2") or 0), abs=0.02)
    assert _qty(out, "Grindjuosčių sumontavimas") < _qty(base, "Grindjuosčių sumontavimas")
    assert _qty(out, "Sienų glaistymas/dažymas") == pytest.approx(_qty(base, "Sienų glaistymas/dažymas"), abs=0.02)


def test_apdaila_off_in_one_room_names_the_choice_in_the_ledger():
    out = _recompute({"patalpu_sritys_ne": {"02": ["apdaila"]}})
    walls = _row(out, "Sienų glaistymas/dažymas")
    assert any(e.get("room_nr") == "02" and e.get("excluded_because") == EXCLUDED_BECAUSE
               for e in walls.get("excluded") or []), walls.get("excluded")
    assert all(c.get("room_nr") != "02" for c in walls.get("contributions") or [])
    lubos = _row(out, "Lubų glaistymas/dažymas")
    assert _qty(out, "Lubų glaistymas/dažymas") == pytest.approx(36.0, abs=0.02), "anchor minus the room's ceiling"


def test_tiles_off_in_the_bathroom_drops_its_tile_rows_and_piece_counts():
    base = _recompute()
    out = _recompute({"patalpu_sritys_ne": {"03": ["plyteles"]}})
    assert _qty(base, "Vonios sienų plytelių klijavimas") > 0
    assert _qty(out, "Vonios sienų plytelių klijavimas") == 0
    assert _qty(out, "Nuolydžio formavimas dušo zonoje") < _qty(base, "Nuolydžio formavimas dušo zonoje") or \
        _qty(base, "Nuolydžio formavimas dušo zonoje") == 0
    assert _qty(out, "Sienų glaistymas/dažymas") > 0


# ── Rotband: a share he chooses, never a number from anyone's sąmata ─────────

def test_rotband_is_a_stated_assumption_until_he_chooses():
    base = _recompute()
    row = _row(base, "Sienų lyginimas Knauf Rotband")
    assert row is not None and "Prielaida" in str(row.get("_assumption") or "")
    assert float(row["kiekis"]) == pytest.approx(0.30 * _qty(base, "Sienų glaistymas/dažymas"), abs=0.05)
    none = _recompute({"rotband": "nera"})
    assert _row(none, "Sienų lyginimas Knauf Rotband") is None
    all_walls = _recompute({"rotband": "visos"})
    assert float(_row(all_walls, "Sienų lyginimas Knauf Rotband")["kiekis"]) == pytest.approx(
        _qty(base, "Sienų glaistymas/dažymas"), abs=0.05)
    half = _recompute({"rotband": "dalis", "rotband_dalis": 50})
    r = _row(half, "Sienų lyginimas Knauf Rotband")
    assert float(r["kiekis"]) == pytest.approx(0.5 * _qty(base, "Sienų glaistymas/dažymas"), abs=0.05)
    assert "pasirinkimas" in str(r.get("_assumption") or "").lower()


def test_waterproofing_stays_one_line_and_carries_its_square_metres():
    """The LT pro convention is ONE hidroizoliacija line per job (billed per wet
    zone); a contractor who bills it in m² is checked against the line's own m²
    detail by the row scorecard, not by a second row he might price twice."""
    out = _recompute()
    rows = [r for r in out["darbu_sarasas"] if str(r.get("aprasymas") or "").startswith("Hidroizoliacijos įrengimas")]
    assert len(rows) == 1
    assert str(rows[0].get("mato_vnt") or "").lower() in ("vnt", "kompl")
    # the m² live on the builder's own row (`pozicijos`); the compat emit keeps the sąmata row lean
    poz = [r for r in out.get("pozicijos") or [] if str(r.get("aprasymas") or "").startswith("Hidroizoliacijos įrengimas")]
    assert len(poz) == 1
    assert float(poz[0].get("_detail_m2") or 0) > 6.0, "the bathroom floor alone is 6 m²; the splash zone adds to it"


def test_corner_bead_on_the_rooms_own_corners_is_his_choice():
    base = _recompute()
    outer = _recompute({"kampai": "tik_isoriniai"})
    r01b = next(r for r in base["patalpos"] if r["nr"] == "01")
    r01 = next(r for r in outer["patalpos"] if r["nr"] == "01")
    assert float(r01b["kampai_inner_m"]) == pytest.approx(4 * 2.7, abs=0.01), "today: four vertical room corners"
    assert float(r01["kampai_inner_m"]) == 0.0
    assert float(r01["kampu_metrai"]) == pytest.approx(float(r01b["kampu_metrai"]) - 4 * 2.7, abs=0.01)
    assert _qty(outer, "Dažymo kampų montavimas") < _qty(base, "Dažymo kampų montavimas")
    same = _recompute({"kampai": "su_vidiniais"})
    assert _qty(same, "Dažymo kampų montavimas") == pytest.approx(_qty(base, "Dažymo kampų montavimas"), abs=0.02)
    # the Setup Wizard checkbox now reaches the calculator too (the scope choice wins when set)
    body = {"patalpos": _rooms(), "rules_override": {"count_inner_corners": False}}
    res = client.post("/recompute-interior", json=body)
    assert res.status_code == 200
    assert _qty(res.json(), "Dažymo kampų montavimas") == pytest.approx(_qty(outer, "Dažymo kampų montavimas"), abs=0.02)

"""2026-09-29 — the contractor's explicit corrections win, on BOTH live recompute paths
(POST /api/recompute-quantities — Prielaidos; POST /recompute-interior — the room sheet).

  · calc-engine-4: an opening he steps down to 0 counts as 0 (a MISSING count is still one unit), and the
    walls pass does not stand a new window or door in the opening he emptied;
  · calc-engine-3: „Nedažomos" empties the room's painted walls in every wall branch — a finishes read and
    the bathroom paint-above-tile default included — and the putty, primer and paint follow;
  · calc-engine-2: a per-room height edit through Prielaidos gives the same room and the same rows as the
    same edit through the room sheet (the plasterboard ceiling tier, putty and primer included).

With no correction present nothing moves — the corpus eval pins that separately.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402
from extractor import universal_rules as ur  # noqa: E402
from extractor.vision_call import _elementai_to_counts  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "dev"})
    return TestClient(main.app)


def _by_nr(rooms):
    return {str(r["nr"]): r for r in rooms}


def _prielaidos(client, rooms, edits, assumptions=None, context=None):
    res = client.post("/api/recompute-quantities", json={
        "rooms": copy.deepcopy(rooms), "pozicijos": [], "darbu_sarasas": [],
        "edits": edits, "current_assumptions": assumptions or {},
        "context": context or {"bendras_plotas_m2": sum(float(r.get("plotas_m2") or 0) for r in rooms)},
    })
    assert res.status_code == 200, res.text
    return res.json()


def _room_sheet(client, rooms, rules_override=None):
    res = client.post("/recompute-interior", json={"patalpos": copy.deepcopy(rooms),
                                                   "rules_override": rules_override or {}})
    assert res.status_code == 200, res.text
    return res.json()


# ── calc-engine-4: an opening at 0 is 0 ─────────────────────────────────────

WINDOW = {"tipas": "langas", "plotis_mm": 1200, "aukstis_mm": 1500}


def _bedroom(elementai):
    return {"nr": "02", "pavadinimas": "Miegamasis", "paskirtis": "miegamoji", "plotas_m2": 14.0,
            "perimetras_m": 15.0, "lubu_aukstis_m": 2.7, "elementai": elementai}


def test_a_missing_count_is_one_unit_and_an_explicit_zero_is_none():
    counts = _elementai_to_counts([{**WINDOW, "kiekis": 0}, {**WINDOW}, {"tipas": "duris", "kiekis": 0}])
    assert counts["n_windows"] == 1 and counts["n_doors"] == 0
    assert ur._el_units({"kiekis": 0}) == 0 and ur._el_units({}) == 1 and ur._el_units({"kiekis": None}) == 1


def test_a_window_stepped_to_zero_is_the_same_room_as_no_window():
    door = {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}
    zero = ur.calc_room_quantities({**_bedroom([door, {**WINDOW, "kiekis": 0}]),
                                    **_elementai_to_counts([door, {**WINDOW, "kiekis": 0}])})
    gone = ur.calc_room_quantities({**_bedroom([door]), **_elementai_to_counts([door])})
    for k in ("walls_paintable_m2", "kampu_metrai", "kampai_opening_reveals_m", "angokrasciu_gkp_m", "grindjuosciu_m"):
        assert zero[k] == pytest.approx(gone[k]), k


@pytest.mark.parametrize("path", ["room_sheet", "prielaidos"])
def test_both_paths_count_the_zeroed_window_as_none(client, path):
    door = {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}
    zero, gone = _bedroom([door, {**WINDOW, "kiekis": 0}]), _bedroom([door])
    if path == "room_sheet":
        a, b = _room_sheet(client, [zero])["patalpos"][0], _room_sheet(client, [gone])["patalpos"][0]
    else:
        edit = [{"field": "lubu_auksciai", "new_value": {"02": 2.9}}]
        a, b = _prielaidos(client, [zero], edit)["rooms"][0], _prielaidos(client, [gone], edit)["rooms"][0]
    for k in ("walls_paintable_m2", "kampu_metrai", "angokrasciu_gkp_m", "dazymo_plotas_m2"):
        assert a[k] == pytest.approx(b[k]), k
    assert "0 lang." in a["calculation_trace"]


def _kitchen(kiekis=2):
    room = {"nr": "04", "pavadinimas": "Virtuvė", "paskirtis": "virtuve", "plotas_m2": 14.0,
            "perimetras_m": 15.0, "lubu_aukstis_m": 2.7,
            "elementai": [{"tipas": "langas", "kiekis": kiekis, "plotis_mm": 1350, "aukstis_mm": 1400}],
            "_angos_sienose": {"page": 1, "angos": [
                {"i": "laukas", "plotis_m": 1.36, "storis_m": 0.3, "nupiesta": "langas",
                 "line_pct": [[0.1, 0.1], [0.15, 0.1]]},
                {"i": "laukas", "plotis_m": 1.35, "storis_m": 0.3, "nupiesta": "langas",
                 "line_pct": [[0.2, 0.1], [0.25, 0.1]]}]}}
    return room


def _windows(room):
    return sum(ur._el_units(e) for e in room["elementai"] if e.get("tipas") == "langas")


def _stepped(room, delta):
    """What the room sheet saves after one press of the stepper (lib/roomSheet.js adjustOpeningCount +
    openingsPatch): the element kept, its count moved, the room marked as his."""
    room = copy.deepcopy(room)
    el = next(e for e in room["elementai"] if e.get("tipas") == "langas")
    el["kiekis"] = max(0, int(el["kiekis"]) + delta)
    room["_angos_user_at"] = "2026-09-29T10:00:00Z"
    return room


def test_the_walls_do_not_put_back_a_window_he_removed():
    room = _kitchen()
    ur.reconcile_openings_with_walls([room])
    assert _windows(room) == 2
    room = _stepped(room, -1)
    room = _stepped(room, -1)                                   # both units gone
    for _ in range(3):                                          # and it stays gone, run after run
        ur.reconcile_openings_with_walls([room])
        assert _windows(room) == 0
    assert not any(e.get(ur.ADDED_FROM_WALLS_KEY) for e in room["elementai"])


def test_one_window_of_two_removed_stays_one_and_stepping_back_up_restores_it():
    room = _kitchen()
    ur.reconcile_openings_with_walls([room])
    room = _stepped(room, -1)
    for _ in range(2):
        ur.reconcile_openings_with_walls([room])
        assert _windows(room) == 1
    room = _stepped(room, +1)
    ur.reconcile_openings_with_walls([room])
    assert _windows(room) == 2
    assert not any(e.get(ur.REMOVED_OPENINGS_KEY) for e in room["elementai"])


def test_without_his_mark_a_lower_count_is_the_walls_business_as_before():
    """No `_angos_user_at` → no correction → the pass behaves exactly as it always did."""
    room = _kitchen()
    ur.reconcile_openings_with_walls([room])
    room["elementai"][0]["kiekis"] = 1
    ur.reconcile_openings_with_walls([room])
    assert _windows(room) == 2


def test_the_room_sheet_recompute_keeps_his_removal_and_says_so(client):
    room = _kitchen()
    first = _room_sheet(client, [room])["patalpos"][0]
    assert first["_n_windows"] == 2
    removed = _stepped(_stepped(first, -1), -1)
    second = _room_sheet(client, [removed])["patalpos"][0]
    third = _room_sheet(client, [second])["patalpos"][0]
    assert second["_n_windows"] == 0 and third["_n_windows"] == 0
    from extractor.room_facts import _fact_angos
    fact = _fact_angos({"patalpos": [third]}, third, None)
    assert fact["value"] == 0
    assert "pašalinote" in fact["sentence"] and not fact.get("suggestions")


# ── calc-engine-3: „Nedažomos" wins in every branch ─────────────────────────

def _garage_with_finishes_read():
    return {"nr": "01", "pavadinimas": "Garažas", "paskirtis": "garazas", "plotas_m2": 20.0,
            "perimetras_m": 18.0, "lubu_aukstis_m": 2.8, "sienu_apdailos_breakdown": {"dazai_share": 1.0},
            "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}]}


def _bathroom_paint_above_tile():
    return {"nr": "03", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0,
            "perimetras_m": 10.0, "lubu_aukstis_m": 2.8, "_bathroom_paint_above_tile_m": 2.0,
            "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100}]}


def _living_legacy():
    return {"nr": "05", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 20.0,
            "perimetras_m": 18.0, "lubu_aukstis_m": 2.8,
            "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100}]}


def _assert_unpainted(room):
    assert room["walls_paintable_m2"] == 0
    assert room["_walls_unpainted_reason"] == "override"
    assert room["dazymo_plotas_m2"] == pytest.approx(room["ceiling_paintable_m2"], abs=0.01)
    assert room["gruntas_l"] == pytest.approx(round(room["dazymo_plotas_m2"] / 7.0, 2), abs=0.01)


@pytest.mark.parametrize("make", [_garage_with_finishes_read, _bathroom_paint_above_tile, _living_legacy])
def test_nedazomos_on_the_room_sheet_path(client, make):
    room = make()
    painted = _room_sheet(client, [room])["patalpos"][0]
    assert painted["walls_paintable_m2"] > 0
    out = _room_sheet(client, [room], {"walls_paint_override": {room["nr"]: 0}})["patalpos"][0]
    _assert_unpainted(out)
    assert out["glaistas_kg"] < painted["glaistas_kg"] and out["dazai_l"] < painted["dazai_l"]
    assert out["kampu_metrai"] < painted["kampu_metrai"]


@pytest.mark.parametrize("make", [_garage_with_finishes_read, _bathroom_paint_above_tile, _living_legacy])
def test_nedazomos_on_the_prielaidos_path(client, make):
    room = make()
    painted = _room_sheet(client, [room])["patalpos"][0]
    body = _prielaidos(client, [painted], [{"field": "walls_paint_override", "new_value": {room["nr"]: 0}}])
    out = body["rooms"][0]
    _assert_unpainted(out)
    assert out["glaistas_kg"] < painted["glaistas_kg"]
    assert out["kampu_metrai"] < painted["kampu_metrai"]
    # and the two paths agree on the room
    sheet = _room_sheet(client, [painted], {"walls_paint_override": {room["nr"]: 0}})["patalpos"][0]
    for k in ("walls_paintable_m2", "dazymo_plotas_m2", "kampu_metrai", "glaistas_kg", "gruntas_l"):
        assert out[k] == pytest.approx(sheet[k], abs=0.011), k


# ── calc-engine-2: a height edit is the same room on both paths ─────────────

PARITY_KEYS = ("walls_gross_m2", "walls_paintable_m2", "ceiling_paintable_m2", "dazymo_plotas_m2",
               "kampai_m", "kampu_metrai", "lubu_karnizo_m", "gkp_lubu_standart_m2", "gkp_lubu_virs_3m_m2",
               "glaistas_kg", "gruntas_l", "hidroizoliacija_m2", "plyteles_sienos_m2", "grindjuosciu_m")


def _flat():
    return [
        {"nr": "01", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji", "plotas_m2": 35.5,
         "perimetras_m": 25.0, "lubu_aukstis_m": 2.82,
         "elementai": [{"tipas": "langas", "plotis_mm": 1800, "aukstis_mm": 1500, "kiekis": 2},
                       {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": 1}]},
        {"nr": "02", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0,
         "perimetras_m": 10.0, "lubu_aukstis_m": 2.82, "plyteles_sienos_aukstis_m": 2.0,
         "elementai": [{"tipas": "duris", "plotis_mm": 800, "aukstis_mm": 2100, "kiekis": 1}]},
    ]


def _rows(body):
    return {(r.get("skyrius"), r.get("aprasymas")): round(float(r.get("kiekis") or 0), 2)
            for r in body["darbu_sarasas"]}


def test_a_height_edit_gives_the_same_room_and_rows_on_both_paths(client):
    start = _room_sheet(client, _flat())
    rooms = start["patalpos"]
    prielaidos = _prielaidos(client, rooms, [{"field": "lubu_auksciai", "new_value": {"01": 3.2}}],
                             context={"bendras_plotas_m2": start.get("bendras_plotas_m2") or 41.5})
    edited = copy.deepcopy(rooms)
    _by_nr(edited)["01"].update({"lubu_aukstis_m": 3.2, "lubu_aukstis_saltinis": "user_override"})
    sheet = _room_sheet(client, edited, {"lubu_auksciai": {"01": 3.2}})
    a, b = _by_nr(prielaidos["rooms"])["01"], _by_nr(sheet["patalpos"])["01"]
    for k in PARITY_KEYS:
        assert a.get(k) == pytest.approx(b.get(k), abs=0.011), f"{k}: Prielaidos {a.get(k)} vs room sheet {b.get(k)}"
    # the ceiling moved to the tier above 3 m, on both
    assert a["gkp_lubu_virs_3m_m2"] > 0 and a["gkp_lubu_standart_m2"] == 0
    # the paint litres: the same total, however the Prielaidos path splits it
    assert a["dazai_l"] + (a.get("dazai_luboms_l") or 0) == pytest.approx(b["dazai_l"], abs=0.02)
    ra, rb = _rows(prielaidos), _rows(sheet)
    assert ra == rb, {k: (ra.get(k), rb.get(k)) for k in set(ra) | set(rb) if ra.get(k) != rb.get(k)}


def test_a_prielaidos_edit_keeps_the_rooms_own_fields(client):
    """The calculator echoes `paskirtis` normalised; a height or paint edit in Prielaidos must not
    rewrite what the room is called or what kind of room it is (the room-sheet path never did)."""
    rooms = _room_sheet(client, _flat())["patalpos"]
    room = _by_nr(rooms)["01"]
    room["paskirtis"] = "svetaine"
    before = {k: copy.deepcopy(room.get(k)) for k in ("nr", "pavadinimas", "paskirtis", "elementai", "lubu_tipas")}
    out = _prielaidos(client, rooms, [{"field": "lubu_auksciai", "new_value": {"01": 3.2}}])
    after = _by_nr(out["rooms"])["01"]
    for k, v in before.items():
        assert after.get(k) == v, f"{k}: {v!r} became {after.get(k)!r}"
    assert after["lubu_aukstis_m"] == 3.2


def test_both_paths_hold_back_one_and_the_same_list_of_the_rooms_own_fields(client, monkeypatch):
    """The fields a room keeps when the calculator's answer is merged into it are ONE list, read by both paths
    (api.recompute_quantities._KEPT_ON_RECALC; main.recompute_interior builds `preserved` from it) — a field
    added to it is held back on both at once. Before, the two lists were kept equal by a comment."""
    from api import recompute_quantities as rq
    assert "calculation_trace" in rq._KEPT_ON_RECALC     # redone by derive_room_extras on both paths anyway
    monkeypatch.setattr(rq, "_KEPT_ON_RECALC", rq._KEPT_ON_RECALC + ("_walls_perimetras_saltinis",))
    rooms = _room_sheet(client, _flat())["patalpos"]
    for r in rooms:
        r["_walls_perimetras_saltinis"] = "bandymas"     # a field the calculator does write
    sheet = _room_sheet(client, copy.deepcopy(rooms), {"lubu_auksciai": {"01": 3.2}})
    prielaidos = _prielaidos(client, rooms, [{"field": "lubu_auksciai", "new_value": {"01": 3.2}}])
    assert _by_nr(prielaidos["rooms"])["01"]["_walls_perimetras_saltinis"] == "bandymas"
    assert _by_nr(sheet["patalpos"])["01"]["_walls_perimetras_saltinis"] == "bandymas"

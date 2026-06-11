"""Finish-semantics lane (2026-06-11 experiments follow-up).

Measured root cause on bacveviciaus: 160 m² of molio tinkas (clay-plaster decor)
was counted as PAINT because the apdailos vocabulary had no such category →
combined paint +62.8%. These tests pin the fix: molio share splits OUT of
walls_paintable into molio_tinko_m2 and emits its own pozicija.
"""
from extractor.universal_rules import calc_room_quantities
from extractor.vision_call import _build_pozicijos_from_rooms


def _room(**kw):
    r = {"nr": "1", "pavadinimas": "Svetainė", "paskirtis": "gyvenamoji",
         "plotas_m2": 30.0, "perimetras_m": 22.0, "lubu_aukstis_m": 2.8,
         "elementai": []}
    r.update(kw)
    return r


# ── Task 1: molio tinkas split ───────────────────────────────────────────
def test_molio_share_reduces_paint_and_sets_field():
    base = calc_room_quantities(_room(
        sienu_apdailos_breakdown={"dazymas_share": 1.0, "plyteles_share": 0.0}))
    molio = calc_room_quantities(_room(
        sienu_apdailos_breakdown={"dazymas_share": 0.69, "plyteles_share": 0.0,
                                  "molio_tinkas_share": 0.31}))
    assert molio["molio_tinko_m2"] > 0
    # paint + molio together ≈ the fully-painted baseline (area is split, not lost)
    assert abs((molio["walls_paintable_m2"] + molio["molio_tinko_m2"])
               - base["walls_paintable_m2"]) < 0.05
    assert molio["walls_paintable_m2"] < base["walls_paintable_m2"]


def test_no_molio_share_unchanged():
    q = calc_room_quantities(_room(
        sienu_apdailos_breakdown={"dazymas_share": 1.0, "plyteles_share": 0.0}))
    assert q.get("molio_tinko_m2", 0) == 0


def test_molio_pozicija_emitted():
    rooms = [_room(sienu_apdailos_breakdown={
        "dazymas_share": 0.5, "plyteles_share": 0.0, "molio_tinkas_share": 0.5})]
    rooms[0].update(calc_room_quantities(rooms[0]))
    out = _build_pozicijos_from_rooms({"patalpos": rooms, "santrauka": {}})
    molio = [p for p in out["pozicijos"] if "molio tinku" in p["aprasymas"].lower()]
    assert len(molio) == 1, [p["aprasymas"] for p in out["pozicijos"]]
    assert molio[0]["vnt"] == "m2"
    assert abs(molio[0]["kiekis"] - rooms[0]["molio_tinko_m2"]) < 0.01


def test_no_molio_no_pozicija():
    rooms = [_room()]
    rooms[0].update(calc_room_quantities(rooms[0]))
    out = _build_pozicijos_from_rooms({"patalpos": rooms, "santrauka": {}})
    assert not [p for p in out["pozicijos"] if "molio" in p["aprasymas"].lower()]


# ── Task 2: self-reported low-confidence propagation ─────────────────────
def test_apdailos_low_confidence_propagates():
    from extractor.apdailos_reader import merge_apdailos_into_rooms
    rooms = [{"nr": "1", "pavadinimas": "Garažas"},
             {"nr": "2", "pavadinimas": "Vonia"}]
    merge_apdailos_into_rooms(rooms, {"status": "ok", "patalpos": [
        {"nr": "1", "sienu_apdaila": {"dazymas_share": 1.0},
         "pastabos": "low confidence; spėjimas pagal paskirtį"},
        {"nr": "2", "sienu_apdaila": {"plyteles_share": 0.9},
         "pastabos": "Plytelės aiškiai pažymėtos plane"},
    ]})
    assert rooms[0].get("_apdailos_confidence") == "low"
    assert "_apdailos_confidence" not in rooms[1]

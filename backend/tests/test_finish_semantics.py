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


# ── low-confidence apdailos must not override structural no-paint default ──
def test_low_conf_apdailos_does_not_paint_garage():
    base = {"nr": "1", "pavadinimas": "Garažas", "paskirtis": "garazas",
            "plotas_m2": 44.0, "perimetras_m": 27.0, "lubu_aukstis_m": 2.82,
            "elementai": [], "sienu_apdailos_breakdown": {"dazymas_share": 1.0}}
    # low-confidence guess → garage stays unpainted (structural default 0)
    low = calc_room_quantities({**base, "_apdailos_confidence": "low"})
    assert float(low.get("walls_paintable_m2") or 0) == 0.0
    # confident read → a genuinely-painted garage IS painted
    high = calc_room_quantities(dict(base))  # no _apdailos_confidence == confident
    assert float(high.get("walls_paintable_m2") or 0) > 20.0


# ── silikonavimas covers all tiled rooms, not only paskirtis-wet ──────────
def test_silikonavimas_includes_tiled_non_wet_rooms():
    from extractor.vision_call import _build_pozicijos_from_rooms
    # A skalbykla (not in WET set) marked substantially tiled by apdailos.
    rooms = [
        {"nr": "1", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 6.0,
         "perimetras_m": 10.0, "lubu_aukstis_m": 2.7, "elementai": []},
        {"nr": "2", "pavadinimas": "Skalbykla", "paskirtis": "skalbykla", "plotas_m2": 9.0,
         "perimetras_m": 12.0, "lubu_aukstis_m": 2.7, "elementai": [],
         "sienu_apdailos_breakdown": {"plyteles_share": 0.7, "dazymas_share": 0.3}},
    ]
    for r in rooms:
        r.update(calc_room_quantities(r))
    out = _build_pozicijos_from_rooms({"patalpos": rooms, "santrauka": {}})
    sil = round(sum(p["kiekis"] for p in out["pozicijos"]
                    if "silikonavimas" in p["aprasymas"].lower()), 2)
    # both rooms' perimeters seal: (10+12) × 1.4 = 30.8, not just the wet 10 × 1.4
    assert sil > 28.0, sil

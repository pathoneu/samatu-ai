"""Garage floor-tile default (2026-07-04).

Evidence: both contractor-validated fixtures tile the garage floor —
Beržų bills 10.10 m² (notes p105 grindys; the GT file previously needed
tile_floor_override=True to hit truth) and Objektas B bills garage
tiling explicitly (pasiūlymas items 40-43). The old default (tile_floor
False) made every vision run report 0 m² garage floor tile, which was
the single biggest slice of the -20.0% plytelės-grindys error that both
benchmark models reproduced identically.

The garage floor TYPE stays "concrete": no screed, no baseboards, no
soft covering — only the tile area changes.
"""
from __future__ import annotations

from extractor.universal_rules import calc_room_quantities


def _garazas(**extra) -> dict:
    room = {
        "nr": "105", "pavadinimas": "Garažas", "paskirtis": "garazas",
        "plotas_m2": 10.67, "perimetras_m": 13.5, "lubu_aukstis_m": 3.0,
        "lubu_tipas": "betonas", "plyteles_sienos_aukstis_m": 0,
    }
    room.update(extra)
    return room


def test_garage_floor_tiled_by_default():
    out = calc_room_quantities(_garazas())
    assert out["plyteles_grindys_m2"] == 10.67


def test_garage_tile_floor_override_false_still_wins():
    out = calc_room_quantities(_garazas(tile_floor_override=False))
    assert out["plyteles_grindys_m2"] == 0


def test_garage_exact_area_override_still_wins():
    # Beržų truth: 10.10 m² of the 10.67 m² slab is tiled.
    out = calc_room_quantities(_garazas(plyteles_grindys_m2_override=10.1))
    assert out["plyteles_grindys_m2"] == 10.1


def test_garage_floor_type_stays_concrete():
    out = calc_room_quantities(_garazas())
    # No screed under the garage slab, no baseboards, no soft covering.
    assert out["isliginamasis_m2"] == 0
    assert out["grindjuostes_m"] == 0
    assert out["pvc_grindys_m2"] == 0

"""2026-09-23: the tiled band loses its openings, and a kitchen's backsplash runs along the counter."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from extractor import universal_rules as ur  # noqa: E402


def _bath(**more):
    return {"nr": "07", "pavadinimas": "Vonia", "paskirtis": "vonia", "plotas_m2": 5.64, "perimetras_m": 9.63,
            "lubu_aukstis_m": 2.82, "plyteles_sienos_aukstis_m": 2.4,
            "elementai": [{"tipas": "duris", "kiekis": 1, "plotis_mm": 700, "aukstis_mm": 2100}], **more}


def test_the_door_in_a_tiled_bathroom_wall_is_not_tiled():
    out = ur.calc_room_quantities(_bath())
    gross = 9.63 * 2.4
    assert abs(out["plyteles_sienos_m2"] - (gross - 0.7 * 2.1)) < 0.02        # objektas_g: +13 % over him for exactly the doors
    no_door = ur.calc_room_quantities(_bath(elementai=[]))
    assert abs(no_door["plyteles_sienos_m2"] - gross) < 0.02


def test_a_window_loses_only_its_part_inside_the_band_and_a_full_tile_room_is_untouched():
    room = _bath(elementai=[{"tipas": "langas", "kiekis": 1, "plotis_mm": 600, "aukstis_mm": 2100}])
    out = ur.calc_room_quantities(room)
    inside = 0.6 * (2.4 - 0.9)                                                  # sill at 0,9 m, band to 2,4 m
    assert abs(out["plyteles_sienos_m2"] - (9.63 * 2.4 - inside)) < 0.02
    assert ur._openings_in_tile_band_m2({"elementai": [{"tipas": "duris", "kiekis": 2}]}, 2.4, 1.0) == round(2 * 0.9 * 2.1, 4)
    assert ur._openings_in_tile_band_m2({"elementai": [{"tipas": "duris", "kiekis": 1}]}, 0, 1.0) == 0.0


def test_a_kitchens_backsplash_runs_along_the_counter_not_round_the_room():
    kitchen = {"nr": "04", "pavadinimas": "Virtuvė/valgomasis", "paskirtis": "virtuve", "plotas_m2": 26.31,
               "perimetras_m": 21.0, "lubu_aukstis_m": 2.82, "elementai": []}
    out = ur.calc_room_quantities(kitchen)
    assert abs(out["plyteles_sienos_m2"] - 0.6 * 3.0) < 0.02                     # was 0,6 × 21 = 12,6 m² of tile nobody lays
    rules = ur.translate_user_prefs_to_room_rules({"kitchen_counter_length_m": 4.5})
    assert abs(ur.calc_room_quantities(kitchen, rules=rules)["plyteles_sienos_m2"] - 0.6 * 4.5) < 0.02
    read = ur.resolve_wall_tile_read(kitchen, ur.ROOM_TYPE_RULES["virtuve"], 2.82, 0.0, perimeter_m=21.0)
    assert read["missing"] and "stalviršio" in read["assumption"] and abs(read["share"] - 3.0 / 21.0) < 1e-6
    assert ur.default_paint_prefs()["kitchen_counter_length_m"] == 3.0

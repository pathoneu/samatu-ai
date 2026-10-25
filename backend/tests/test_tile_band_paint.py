"""A wall is either tiled or painted — never both on the same square metre.

2026-09-05. The first blind out-of-sample runs (Objektas G and H) showed the
largest single wall-paint error to be a rule: a room tiled to 2,4–2,5 m of its
2,82 m height kept its FULL painted wall area, so the band was billed as tile
AND as paint. Only the išklotinių branch deducted it. These tests pin the
corrected behaviour in the other two branches and the provenance it leaves.

Every room here is synthetic.
"""
from __future__ import annotations

import pytest

# These tests check how a door / window is deducted under the older 1,0 m² LT rule (the `lt_rangovas`
# default is 3,0 m² since 2026-10-25 — rangovo taisyklė; see conftest.lt_aperture_1m2).
pytestmark = pytest.mark.usefixtures("lt_aperture_1m2")

from extractor.universal_rules import (
    TILE_BAND_DOOR_H_M, _tile_zone_in_paint_base, calc_room_quantities,
)

# One standard 0,9 × 2,1 door NET of its painted jambs at the default 0,10 m wall
# thickness — the deduction every branch uses since 2026-09-15 (was a flat 1,85
# gross on the legacy path and 1,125 on the apdailos path).
DOOR = round(0.9 * 2.1 - (0.9 + 2 * 2.1) * 0.10, 3)   # 1,38


def test_helper_adds_back_the_part_of_the_openings_inside_the_band():
    # band above door height, whole perimeter tiled → the whole door is in the band
    assert _tile_zone_in_paint_base(24.0, 2.4, 1.0, DOOR) == pytest.approx(24.0 - DOOR)
    # band at half the door → half of the door is in the band
    assert _tile_zone_in_paint_base(10.0, TILE_BAND_DOOR_H_M / 2, 1.0, 2.0) == pytest.approx(9.0)
    # a 10 % splashback almost never carries the door
    assert _tile_zone_in_paint_base(2.0, 0.6, 0.1, 2.0) == pytest.approx(2.0 - 2.0 * 0.1 * 0.6 / 2.1)
    # nothing tiled → nothing deducted; never negative
    assert _tile_zone_in_paint_base(0.0, 2.4, 1.0, DOOR) == 0.0
    assert _tile_zone_in_paint_base(1.0, 2.4, 1.0, 50.0) == 0.0


def test_vision_read_band_paints_only_the_strip_above_it():
    room = {"paskirtis": "vonia", "plotas_m2": 6.0, "perimetras_m": 10.0,
            "lubu_aukstis_m": 2.8, "n_doors": 1, "n_windows": 0,
            "plyteles_sienos_aukstis_m": 2.4}          # read off the drawing
    out = calc_room_quantities(room)
    assert out["plyteles_sienos_m2"] == pytest.approx(24.0)
    # 10 m × 0,4 m strip — the door is inside the band, not above it
    assert out["walls_paintable_m2"] == pytest.approx(10.0 * 0.4, abs=0.02)
    assert out["_tile_zone_deducted_m2"] == pytest.approx(24.0 - DOOR, abs=0.02)
    assert not out["_walls_full_tile"]
    # a band READ off the drawing is not an assumption — no note; the ledger's
    # per-room line („Dažoma sienų dalis virš plytelių juostos") explains it
    assert not any("Plytelių juosta" in n for n in out["_wall_finish_assumptions"])


def test_full_tile_room_is_unchanged_zero_paint():
    room = {"paskirtis": "vonia", "plotas_m2": 6.0, "perimetras_m": 10.0,
            "lubu_aukstis_m": 2.8, "n_doors": 1, "n_windows": 0,
            "plyteles_sienos_aukstis_m": 2.8}
    out = calc_room_quantities(room)
    assert out["_walls_full_tile"]
    assert out["walls_paintable_m2"] == 0.0
    assert out["_tile_zone_deducted_m2"] == 0.0     # no strip to speak of


def test_untiled_room_is_unchanged():
    room = {"paskirtis": "miegamasis", "plotas_m2": 14.0, "perimetras_m": 15.0,
            "lubu_aukstis_m": 2.8, "n_doors": 1, "n_windows": 1}
    out = calc_room_quantities(room)
    assert out["plyteles_sienos_m2"] == 0.0
    assert out["_tile_zone_deducted_m2"] == 0.0
    assert out["walls_paintable_m2"] == pytest.approx(15.0 * 2.8 - DOOR - 1.8, abs=0.02)


def test_kitchen_splashback_leaves_the_paint_base_too():
    room = {"paskirtis": "virtuve", "plotas_m2": 12.0, "perimetras_m": 12.0,
            "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 1}
    out = calc_room_quantities(room)
    band = out["plyteles_sienos_m2"]                # paskirtis default splashback
    assert band > 0
    openings = DOOR + 1.8
    # 2026-09-23: the kitchen band runs along the counter (3,0 m of a 12 m perimeter — its share of the walls)
    share = 3.0 / 12.0
    assert band == pytest.approx(share * 12.0 * 0.6, abs=0.02)
    in_band = openings * share * (0.6 / TILE_BAND_DOOR_H_M)
    assert out["walls_paintable_m2"] == pytest.approx(
        12.0 * 2.7 - openings - (band - in_band), abs=0.05)


def test_apdailos_branch_deducts_the_band_like_the_others():
    room = {"paskirtis": "vonia", "plotas_m2": 7.0, "perimetras_m": 9.63,
            "lubu_aukstis_m": 2.82, "n_doors": 1, "n_windows": 0,
            "plyteles_sienos_aukstis_m": 2.4,
            "sienu_apdailos_breakdown": {"plyteles_share": 0.75, "dazomos_share": 0.25}}
    out = calc_room_quantities(room)
    zone = 0.75 * 9.63 * 2.4
    assert out["plyteles_sienos_m2"] == pytest.approx(zone, abs=0.02)
    gross = 9.63 * 2.82
    # apdailos branch: doors at the net deduction, no window deduction
    door_net = gross - out["walls_paintable_m2"] - out["_tile_zone_deducted_m2"]
    assert door_net == pytest.approx(DOOR, abs=0.02)
    assert out["_tile_zone_deducted_m2"] == pytest.approx(zone - DOOR * 0.75, abs=0.02)
    # untiled quarter of the walls at full height + the strip above the band
    assert out["walls_paintable_m2"] == pytest.approx(
        gross - DOOR - (zone - DOOR * 0.75), abs=0.02)


def test_default_band_is_disclosed_and_not_billed_twice():
    """No tile evidence at all: the wet-room default band is an ASSUMPTION the
    contractor must see — and even an assumed band is billed once."""
    room = {"paskirtis": "san", "plotas_m2": 4.0, "perimetras_m": 8.0,
            "lubu_aukstis_m": 2.7, "n_doors": 1, "n_windows": 0}
    out = calc_room_quantities(room)
    assert out["_tile_read_source"] == "paskirtis_default"
    assert out["_tile_read_missing"] is True
    assert out["plyteles_sienos_m2"] > 0
    assert out["plyteles_sienos_m2"] + out["walls_paintable_m2"] <= out["walls_gross_m2"] + 0.01
    assert any("juost" in n for n in out["_wall_finish_assumptions"])

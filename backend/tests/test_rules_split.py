"""Phase 2 commit 1 — the mechanical split of universal_rules into backend/rules/.

Zero behaviour change is the contract: every name a caller imports from
`extractor.universal_rules` is the SAME object as the one in `rules.*`, so a
test or a Prielaidos path that mutates `UNIVERSAL_RULES` in place still reaches
the engine, and every moved convention carries its source (R5)."""
from __future__ import annotations

import math

import pytest

from extractor import universal_rules as ur
from rules import conventions, rounding, rows


def test_conventions_are_reexported_as_the_same_objects():
    for name in conventions.CONVENTIONS:
        assert getattr(ur, name) is getattr(conventions, name), name


def test_row_helpers_are_reexported_as_the_same_functions():
    for name in ("calc_paint_liters", "is_high_ceiling", "calc_gkp_sheets", "gkp_sheet_count",
                 "gkp_ceiling_areas_m2", "slope_factor", "stairwell_wall_area_m2", "calc_totals",
                 "paint_coverage_for_class"):
        assert getattr(ur, name) is getattr(rows, name), name


def test_every_moved_constant_names_its_source():
    for name, conv in conventions.CONVENTIONS.items():
        assert conv.source.strip(), name
        assert conv.value is getattr(conventions, name)
        assert isinstance(conv.fitted_on, tuple)


def test_values_unchanged_by_the_split():
    # the numbers the old module carried — a split that changed one would move every quantity
    assert ur.UNIVERSAL_RULES["openings_threshold_m2"] == 1.0
    assert ur.UNIVERSAL_RULES["default_window_area_m2"] == 1.80
    assert ur.SKIRTING_WASTE == 1.10 and ur.GKP_SHEET_WASTE == 1.10
    assert ur.STANDARD_DOOR_W_M == 0.9 and ur.STANDARD_DOOR_H_M == 2.1
    assert ur.REVEALS_SCOPE_DEFAULT == {"langai": True, "lauko_durys": True, "praejimai": True,
                                        "vidaus_durys": False}
    assert ur.WET_ROOM_PASKIRTYS == ("vonia", "wc", "san")
    assert ur.ROOM_TYPE_RULES["vonia"]["tile_walls_to_m"] == 2.0


def test_in_place_mutation_reaches_the_engine(monkeypatch):
    monkeypatch.setitem(ur.UNIVERSAL_RULES, "drywall_sheet_area_m2", 6.0)
    assert rows.gkp_sheet_count(6.0) == math.ceil(1 * ur.GKP_SHEET_WASTE)


# ── rounding (R4) ──────────────────────────────────────────────────────────
@pytest.mark.parametrize("value, expected", [
    (2.675, 2.68),          # Python's round() gives 2.67 (binary 2.67499…)
    (1.005, 1.01),
    (0.125, 0.13),
    (-2.675, -2.68),
    (10.0, 10.0),
    (419.9249999, 419.92),
])
def test_round_2_is_half_up_on_the_decimal_reading(value, expected):
    assert rounding.round_2(value) == expected


def test_round_count_and_pack():
    assert rounding.round_count(2.5) == 3
    assert rounding.round_count(2.49) == 2
    assert rounding.round_pack(3.0000000001) == 3
    assert rounding.round_pack(3.01) == 4
    assert rounding.round_pack(10, 25) == 1
    assert rounding.round_pack(0) == 0


def test_round_qty_by_unit():
    assert rounding.round_qty(2.675, "m2") == 2.68
    assert rounding.round_qty(2.675, "m") == 2.68
    assert rounding.round_qty(2.5, "vnt") == 3
    assert isinstance(rounding.round_qty(2.0, "vnt"), int)
    assert rounding.round_qty(None, "m2") is None
    assert rounding.round_qty(1.234, "kažkas") == 1.23

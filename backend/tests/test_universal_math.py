"""Universal math regression suite — locks calc_room_quantities + helpers
against CLAUDE.md §1 SPEC values, NOT against current code output.

W1 2026-05-11 (per docs/superpowers/research/council-transcript-2026-05-11-
execution.md). Each test cites the CLAUDE.md §1.X line number it enforces.
Known bugs are marked `@pytest.mark.xfail` with a reason — DON'T green
them by adjusting expected values; fix the code or document the gap.

Why this file exists: prior tests (test_extractor_unit.py) verify the
code reproduces itself. They lock in whatever happens to be implemented.
This file asserts CLAUDE.md §1 spec values regardless of what code does.
A diff between expected and actual surfaces bugs deterministically.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from extractor.universal_rules import (  # noqa: E402
    calc_room_quantities,
    UNIVERSAL_RULES,
    slope_factor,
)


# ─────────────────────────────────────────────────────────────────────
# §1.1 Dažomas plotas (paintable wall area)
# ─────────────────────────────────────────────────────────────────────


def test_dazomas_plotas_basic_walls_gross_formula():
    """CLAUDE.md §1.1: S_walls_gross = perimeter × ceiling_height.
    With LT default deductions (1 door + 1 window applied when n is zero/missing
    due to `or 1` fallback), result is walls_gross − defaults + ceiling.
    Asserts formula at the level we control: paintable >= walls_gross − 4 m² of
    default openings + ceiling area.
    """
    room = {
        "paskirtis": "gyvenamoji",
        "plotas_m2": 20.0,
        "perimetras_m": 18.0,
        "lubu_aukstis_m": 2.7,
        "n_doors": 1,    # explicit; setting 0 hits the `or 1` fallback
        "n_windows": 1,
    }
    out = calc_room_quantities(room)
    walls_gross = 18.0 * 2.7         # 48.6
    door_area = UNIVERSAL_RULES["default_door_area_m2"]    # 1.85
    window_area = UNIVERSAL_RULES["default_window_area_m2"]  # 1.62 (older default)
    # Walls_net = gross − doors − windows; ceiling = floor area
    expected_total = (walls_gross - door_area - window_area) + 20.0
    # Within 1 m² tolerance (window default values shifted over time)
    assert abs(out["dazymo_plotas_m2"] - expected_total) < 1.5, (
        f"Expected ~{expected_total:.2f}, got {out['dazymo_plotas_m2']}"
    )


def test_nrm2_threshold_constant_per_claude():
    """CLAUDE.md §1.1: 'Openings < 0.5 m² are NOT deducted (RICS NRM2 rule).'
    Threshold constant must be exactly 0.5 m² to honor the spec.
    """
    assert UNIVERSAL_RULES["nrm2_no_deduct_threshold_m2"] == 0.5, (
        f"NRM2 threshold should be 0.5 m² per CLAUDE.md §1.1, got "
        f"{UNIVERSAL_RULES['nrm2_no_deduct_threshold_m2']}"
    )


def test_lt_and_nrm2_diverge_on_0_6m2_opening():
    """CLAUDE.md §1.1 (LT vs NRM2 distinction): a 0.6 m² window should be
    DEDUCTED under NRM2 (>= 0.5) but NOT under LT (< 1.0 m² LT threshold).
    Differing behaviour proves both standards are honored independently.
    """
    room = {
        "paskirtis": "gyvenamoji",
        "plotas_m2": 20.0,
        "perimetras_m": 18.0,
        "lubu_aukstis_m": 2.7,
        "n_windows": 1,
        "window_area_m2": 0.6,    # between LT (1.0) and NRM2 (0.5) thresholds
        "n_doors": 1,
        "door_area_m2": 1.85,
    }
    out_nrm2 = calc_room_quantities(
        room, rules={"_paint_deduction_standard": "NRM2"}
    )
    out_lt = calc_room_quantities(
        room, rules={"_paint_deduction_standard": "LT"}
    )
    # NRM2 deducts the 0.6 m² window; LT doesn't. NRM2 should have ~0.6 m²
    # LESS paintable than LT.
    diff = out_lt["dazymo_plotas_m2"] - out_nrm2["dazymo_plotas_m2"]
    assert 0.4 <= diff <= 0.8, (
        f"NRM2 should deduct 0.6 m² window while LT doesn't (diff ~0.6 m²); "
        f"got LT={out_lt['dazymo_plotas_m2']} NRM2={out_nrm2['dazymo_plotas_m2']} diff={diff:.2f}"
    )


# ─────────────────────────────────────────────────────────────────────
# §1.4 Grindjuostės + kornizai (baseboard + cornice)
# ─────────────────────────────────────────────────────────────────────


def test_grindjuostes_perim_minus_doors_plus_10pct():
    """CLAUDE.md §1.4: 'baseboard = room_perimeter − Σ(door_widths) + 10% waste'.
    Implementation at universal_rules.py:553 uses 0.85m default door width.
    """
    room = {
        "paskirtis": "gyvenamoji",
        "plotas_m2": 20.0,
        "perimetras_m": 18.0,
        "n_doors": 1,
        "n_windows": 0,
    }
    out = calc_room_quantities(room)
    # perim 18.0 − 0.85 door = 17.15; × 1.10 = 18.865
    expected = (18.0 - 0.85) * 1.10
    actual = out.get("grindjuostes_m") or out.get("grindjuosciu_m") or 0
    assert abs(actual - expected) < 0.05, (
        f"Expected grindjuostės ≈ {expected:.2f} per CLAUDE.md §1.4, got {actual}"
    )


def test_grindjuostes_zero_when_tile_floor():
    """CLAUDE.md §1.4 spirit: don't bill baseboard where there's no finished
    paint surface (tile floors don't need wooden baseboards). Code checks
    `tile_floor` rule per paskirtis.
    """
    room = {
        "paskirtis": "vonia",  # tile_floor = True
        "plotas_m2": 6.0,
        "perimetras_m": 10.0,
        "n_doors": 1,
        "n_windows": 0,
    }
    out = calc_room_quantities(room)
    actual = out.get("grindjuostes_m") or out.get("grindjuosciu_m") or 0
    assert actual == 0, (
        f"Tile-floor room should have 0 grindjuostės; got {actual}"
    )


# ─────────────────────────────────────────────────────────────────────
# §3 Waste factors — verify our recently-corrected herringbone values
# ─────────────────────────────────────────────────────────────────────


def test_waste_factor_paint_in_claude_range():
    """CLAUDE.md §3: Paint 5-8%."""
    val = UNIVERSAL_RULES["waste_factors"]["paint"]
    assert 0.05 <= val <= 0.08, f"paint waste {val} outside §3 range 5-8%"


def test_waste_factor_drywall_in_claude_range():
    """CLAUDE.md §3: Drywall 10-15%."""
    val = UNIVERSAL_RULES["waste_factors"]["drywall"]
    assert 0.10 <= val <= 0.15, f"drywall waste {val} outside §3 range 10-15%"


def test_waste_factor_tiles_straight_in_claude_range():
    """CLAUDE.md §3: Tiles straight 5-10%."""
    val = UNIVERSAL_RULES["waste_factors"]["tiles_straight"]
    assert 0.05 <= val <= 0.10, f"tiles_straight {val} outside §3 range 5-10%"


def test_waste_factor_tiles_herringbone_in_claude_range():
    """CLAUDE.md §3: Tiles herringbone 10-15%. Was 0.18 pre-W1-audit
    (out-of-range); fixed to 0.13 per §1.7 +12% and §3 max 15%.
    """
    val = UNIVERSAL_RULES["waste_factors"]["tiles_herringbone"]
    assert 0.10 <= val <= 0.15, f"tiles_herringbone {val} outside §3 range 10-15%"


def test_waste_factor_parquet_herringbone_in_claude_range():
    """CLAUDE.md §1.6: parquet/laminate herringbone +12-16% range
    (§3 lists laminate 5-10% straight; herringbone-specific lives in §1.6).
    Was 0.20 pre-W1-audit; fixed to 0.16 (upper bound of §1.6).
    """
    val = UNIVERSAL_RULES["waste_factors"]["parquet_herringbone"]
    assert 0.12 <= val <= 0.16, f"parquet_herringbone {val} outside §1.6 range"


# ─────────────────────────────────────────────────────────────────────
# §3 Slope factor (roof / sloped ceiling)
# ─────────────────────────────────────────────────────────────────────


def test_slope_factor_flat_returns_one():
    """CLAUDE.md §3 (Type 3, slope_factor table): Flat (1-3°) → 1.00.
    `slope_factor(0)` and small angles should be 1.0 within 0.005.
    """
    assert abs(slope_factor(0) - 1.00) < 0.005
    assert abs(slope_factor(1) - 1.00) < 0.005


def test_slope_factor_45deg_returns_1_414():
    """CLAUDE.md §3 (slope_factor table): 45° → 1.414 (sqrt(2))."""
    assert abs(slope_factor(45) - 1.414) < 0.005


# ─────────────────────────────────────────────────────────────────────
# §1.10 Paint quantity — 2 coats use 1.8× multiplier, NOT 2.0×
# ─────────────────────────────────────────────────────────────────────


def test_paint_liters_2coats_uses_1_8x_multiplier():
    """CLAUDE.md §1.10: 'for 2 coats multiply by 1.8× (not 2.0×) — first
    coat absorbs more'. Standalone helper landed W2 alongside this test.
    50 m² × 1.8 / 9 m²/L = 10.0 L (not 50 × 2/9 = 11.11 L).
    """
    from extractor.universal_rules import calc_paint_liters
    liters = calc_paint_liters(area_m2=50.0, coats=2, coverage_m2_per_liter=9.0)
    assert abs(liters - 10.0) < 0.01, (
        f"Expected 10.0 L per CLAUDE.md §1.10 (50 × 1.8 / 9), got {liters}"
    )


def test_paint_liters_3coats_adds_full_coat_each():
    """3 coats = 1.8 (first two) + 1.0 (third) = 2.8× effective.
    50 m² × 2.8 / 9 = 15.56 L.
    """
    from extractor.universal_rules import calc_paint_liters
    liters = calc_paint_liters(area_m2=50.0, coats=3, coverage_m2_per_liter=9.0)
    assert abs(liters - 50.0 * 2.8 / 9.0) < 0.01


# ─────────────────────────────────────────────────────────────────────
# §1.11 Glaistymas Q4 — 1.5 kg/m²/mm at 3-5mm thickness
# ─────────────────────────────────────────────────────────────────────


def test_glaistas_q4_consumption_rate_per_claude():
    """CLAUDE.md §1.11 table: Q4 = 1.5 kg/m²/mm. Constant lives in
    UNIVERSAL_RULES.skim_consumption (gloss-prep absorbs more material).
    """
    q4_rate = UNIVERSAL_RULES.get("skim_consumption", {}).get("Q4")
    assert q4_rate is not None, "Q4 skim_consumption missing from UNIVERSAL_RULES"
    assert q4_rate == 1.5, f"CLAUDE.md §1.11 says Q4=1.5 kg/m²/mm, got {q4_rate}"


def test_glaistas_q_levels_monotonic_per_claude():
    """CLAUDE.md §1.11 table: Q1 < Q2 < Q3 < Q4 — finer finish needs
    more material. Sanity test, catches reordered/swapped constants.
    """
    s = UNIVERSAL_RULES["skim_consumption"]
    assert s["Q1"] < s["Q2"] < s["Q3"] < s["Q4"], (
        f"Q-levels not monotonic: {s}"
    )


# ─────────────────────────────────────────────────────────────────────
# §1.4 Cornice — perim + 5% waste, no door deduct, only gyvenamosios
# ─────────────────────────────────────────────────────────────────────


def test_cornice_only_in_living_spaces():
    """CLAUDE.md §1.4: cornice (lubų karnizas) on living spaces only,
    not vonia/wc/garažas. Implemented at vision_call.py:582-601.
    Vonia should return 0 cornice.
    """
    from extractor.vision_call import _calc_lubu_karnizas_m
    assert _calc_lubu_karnizas_m(10.0, "vonia") == 0
    assert _calc_lubu_karnizas_m(10.0, "wc") == 0
    assert _calc_lubu_karnizas_m(10.0, "garazas") == 0


def test_cornice_perim_plus_5pct_in_living():
    """CLAUDE.md §1.4: cornice = perim + 5% (no door deduct)."""
    from extractor.vision_call import _calc_lubu_karnizas_m
    # 10m perim × 1.05 = 10.5
    assert _calc_lubu_karnizas_m(10.0, "miegamoji") == 10.5
    assert _calc_lubu_karnizas_m(10.0, "koridorius") == 10.5


# ─────────────────────────────────────────────────────────────────────
# §1.8 GKP sheets — CEILING(wall_area / 3.0) × 1.10
# ─────────────────────────────────────────────────────────────────────


def test_gkp_sheets_ceil_div_3_x_1_1():
    """CLAUDE.md §1.8: GK sheets = ceil(wall_area / 3.0) × 1.10.
    50 m² → ceil(50/3.0) = 17 → 17 × 1.10 = 18.7 → ceil(18.7) = 19 sheets.
    Standalone helper landed W2 alongside this test.
    """
    from extractor.universal_rules import calc_gkp_sheets
    assert calc_gkp_sheets(50.0) == 19, (
        f"50 m² should need 19 sheets per CLAUDE.md §1.8, got "
        f"{calc_gkp_sheets(50.0)}"
    )


def test_gkp_sheets_small_area_min_one():
    """Even 2 m² should round up to 1 sheet (+10% waste → still 1)."""
    from extractor.universal_rules import calc_gkp_sheets
    assert calc_gkp_sheets(2.0) == 2  # ceil(2/3)=1 × 1.10 → ceil(1.1)=2


def test_gkp_sheets_zero_area_zero_sheets():
    """Edge case: no wall area → no sheets."""
    from extractor.universal_rules import calc_gkp_sheets
    assert calc_gkp_sheets(0.0) == 0
    assert calc_gkp_sheets(-5.0) == 0


# ─────────────────────────────────────────────────────────────────────
# Perimeter floor for SYNTHETIC (non-eksplikacija) geometry — 2026-06-05
#
# Root cause (diagnosed across berzas/bacveviciaus/ciurliu/lazunu): on plans
# with no eksplikacija table Vision emits a minimum-SQUARE perimeter
# (perim ≈ 4·√area), under-reading wall paint. The floor lifts ONLY the
# wall-path perimeter, gated on plotas_saltinis so trusted-table rooms are
# never inflated (this gate is the zero-regression guarantee).
# ─────────────────────────────────────────────────────────────────────


def test_perimeter_floor_skips_eksplikacija_rooms():
    """GATE: a room whose area came from an eksplikacija table is NEVER inflated.
    This is what keeps the read-from-table projects at zero regression."""
    room = {
        "paskirtis": "gyvenamoji",
        "plotas_m2": 16.0,
        "perimetras_m": 16.0,          # 4·√16 — square, but TRUSTED source
        "plotas_saltinis": "eksplikacija",
        "lubu_aukstis_m": 2.8,
    }
    out = calc_room_quantities(room)
    assert out["_perimetras_floor_applied"] is False
    assert out["_walls_perimetras_m"] == pytest.approx(16.0, abs=0.01)
    assert out["walls_gross_m2"] == pytest.approx(16.0 * 2.8, abs=0.01)


def test_perimeter_floor_lifts_synthetic_square_room():
    """A synthetic square perimeter (no eksplikacija) is floored toward an
    elongated rectangle for the WALL path; measured perimetras_m is untouched."""
    room = {
        "paskirtis": "gyvenamoji",
        "plotas_m2": 16.0,
        "perimetras_m": 16.0,          # 4·√16 — square synthesis
        "plotas_saltinis": "wall_dim_calc",
        "lubu_aukstis_m": 2.8,
    }
    out = calc_room_quantities(room)
    expected = 4.69 * 4.0              # 4.69·√16 = 18.76
    assert out["_perimetras_floor_applied"] is True
    assert out["_walls_perimetras_m"] == pytest.approx(expected, abs=0.01)
    assert out["walls_gross_m2"] == pytest.approx(expected * 2.8, abs=0.01)
    assert out["perimetras_m"] == pytest.approx(16.0, abs=0.01)  # measured stays


def test_perimeter_floor_keeps_already_elongated_perimeter():
    """If the synthetic perimeter already exceeds the floor, don't lower it."""
    room = {
        "paskirtis": "gyvenamoji",
        "plotas_m2": 16.0,
        "perimetras_m": 22.0,          # already > 4.69·√16 = 18.76
        "plotas_saltinis": "default_fallback",
        "lubu_aukstis_m": 2.8,
    }
    out = calc_room_quantities(room)
    assert out["_perimetras_floor_applied"] is False
    assert out["walls_gross_m2"] == pytest.approx(22.0 * 2.8, abs=0.01)


def test_perimeter_floor_does_not_touch_silikonavimas():
    """SCOPING: the floor is wall-path only. Wet-room corner sealant stays on the
    MEASURED perimeter so the calibrated ×2.3 multiplier is preserved."""
    room = {
        "paskirtis": "vonia",
        "plotas_m2": 4.0,
        "perimetras_m": 8.0,           # synthetic square
        "plotas_saltinis": "wall_dim_calc",
        "lubu_aukstis_m": 2.8,
    }
    out = calc_room_quantities(room)
    assert out["_perimetras_floor_applied"] is True
    assert out["silikonavimas_m"] == pytest.approx(8.0 * 2.3, abs=0.01)  # measured perim

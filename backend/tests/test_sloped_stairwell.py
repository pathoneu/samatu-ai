"""Sloped ceiling + stairwell module tests (Sprint §2A.3).

Verifies:
  - slope_factor: 1/cos(angle), edge cases (0°, 30°, 45°, clamped at 60°).
  - calc_room_quantities: sloped/vaulted/coffered ceiling area uplifts.
  - stairwell_wall_area_m2: perim × max_height − Σ(triangles).
  - calc_room_quantities for paskirtis="laiptine": uses stairwell formula.
"""
import math
import pytest

from extractor.universal_rules import (
    slope_factor,
    stairwell_wall_area_m2,
    calc_room_quantities,
    normalize_paskirtis,
)


# ── slope_factor ─────────────────────────────────────────────────────────

class TestSlopeFactor:
    def test_zero_angle_no_uplift(self):
        assert slope_factor(0) == 1.0

    def test_negative_angle_clamped_to_1(self):
        assert slope_factor(-5) == 1.0

    def test_30_degrees_matches_table(self):
        # 1 / cos(30°) ≈ 1.1547
        assert slope_factor(30) == pytest.approx(1.1547, abs=0.001)

    def test_45_degrees_matches_table(self):
        # 1 / cos(45°) = sqrt(2) ≈ 1.4142
        assert slope_factor(45) == pytest.approx(math.sqrt(2), abs=0.001)

    def test_clamped_at_60_degrees(self):
        # 70° would give 1/cos(70°) ≈ 2.92, but clamped to 60° = 2.0
        assert slope_factor(70) == pytest.approx(2.0, abs=0.001)


# ── Sloped ceilings via calc_room_quantities ─────────────────────────────

class TestSlopedCeiling:
    @pytest.fixture
    def base_room(self):
        return {
            "nr": 1, "pavadinimas": "Mansarda", "paskirtis": "miegamoji",
            "plotas_m2": 20.0, "perimetras_m": 18.0, "lubu_aukstis_m": 2.5,
            "n_doors": 1, "n_windows": 1,
        }

    def test_flat_ceiling_default(self, base_room):
        out = calc_room_quantities(base_room)
        # Flat: ceiling_paintable == floor_area
        assert out["ceiling_paintable_m2"] == pytest.approx(20.0, abs=0.01)

    def test_sloped_30deg_adds_15pct(self, base_room):
        room = {**base_room, "ceiling_geometry": "sloped", "slope_angle_deg": 30}
        out = calc_room_quantities(room)
        # 20 × 1.1547 ≈ 23.09
        assert out["ceiling_paintable_m2"] == pytest.approx(23.09, abs=0.05)

    def test_sloped_45deg_adds_41pct(self, base_room):
        room = {**base_room, "ceiling_geometry": "sloped", "slope_angle_deg": 45}
        out = calc_room_quantities(room)
        # 20 × sqrt(2) ≈ 28.28
        assert out["ceiling_paintable_m2"] == pytest.approx(28.28, abs=0.05)

    def test_vaulted_same_factor_as_sloped(self, base_room):
        sloped = {**base_room, "ceiling_geometry": "sloped", "slope_angle_deg": 30}
        vaulted = {**base_room, "ceiling_geometry": "vaulted", "slope_angle_deg": 30}
        out_s = calc_room_quantities(sloped)
        out_v = calc_room_quantities(vaulted)
        assert out_s["ceiling_paintable_m2"] == out_v["ceiling_paintable_m2"]

    def test_coffered_default_20pct_uplift(self, base_room):
        room = {**base_room, "ceiling_geometry": "coffered"}
        out = calc_room_quantities(room)
        # 20 × 1.20 = 24.00
        assert out["ceiling_paintable_m2"] == pytest.approx(24.0, abs=0.01)

    def test_coffered_custom_factor(self, base_room):
        room = {**base_room, "ceiling_geometry": "coffered", "coffered_factor": 1.30}
        out = calc_room_quantities(room)
        assert out["ceiling_paintable_m2"] == pytest.approx(26.0, abs=0.01)

    def test_unknown_geometry_falls_back_to_flat(self, base_room):
        room = {**base_room, "ceiling_geometry": "alien"}
        out = calc_room_quantities(room)
        assert out["ceiling_paintable_m2"] == pytest.approx(20.0, abs=0.01)

    def test_sloped_with_zero_angle_falls_back_to_flat(self, base_room):
        room = {**base_room, "ceiling_geometry": "sloped", "slope_angle_deg": 0}
        out = calc_room_quantities(room)
        assert out["ceiling_paintable_m2"] == pytest.approx(20.0, abs=0.01)


# ── Stairwell wall area helper ───────────────────────────────────────────

class TestStairwellWallArea:
    def test_no_steps_falls_back_to_perim_times_height(self):
        # 16m perimeter × 5m max height = 80 m²
        assert stairwell_wall_area_m2(16, 5) == 80.0

    def test_with_steps_subtracts_triangles(self):
        # 16m × 5m = 80 m²; 14 steps × 0.5 × 0.30 × 0.18 = 0.378 m²
        result = stairwell_wall_area_m2(16, 5, num_steps=14,
                                         stair_run_m=0.30, stair_rise_m=0.18)
        assert result == pytest.approx(80.0 - 0.378, abs=0.01)

    def test_partial_data_falls_back_safe(self):
        # Steps but no run/rise: fallback to gross
        assert stairwell_wall_area_m2(16, 5, num_steps=14) == 80.0

    def test_negative_inputs_clamped(self):
        # Negative perimeter → 0 gross
        assert stairwell_wall_area_m2(-5, 5) == 0.0


# ── Stairwell paskirtis end-to-end ───────────────────────────────────────

class TestStairwellRoom:
    def test_normalize_paskirtis_recognizes_laiptine(self):
        assert normalize_paskirtis("Laiptinė") == "laiptine"
        assert normalize_paskirtis("laiptine") == "laiptine"

    def test_calc_uses_stairwell_formula(self):
        room = {
            "nr": 1, "pavadinimas": "Laiptinė", "paskirtis": "laiptine",
            "plotas_m2": 8.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.82,
            "max_height_m": 6.0,
            "num_steps": 14, "stair_run_m": 0.30, "stair_rise_m": 0.18,
            "n_doors": 1, "n_windows": 1,
        }
        out = calc_room_quantities(room)
        # walls_gross = 12 × 6 − (14 × 0.5 × 0.30 × 0.18) = 72 − 0.378 ≈ 71.62
        assert out["walls_gross_m2"] == pytest.approx(71.62, abs=0.05)

    def test_calc_falls_back_to_2H_when_no_max_height(self):
        room = {
            "nr": 1, "pavadinimas": "Laiptinė", "paskirtis": "laiptine",
            "plotas_m2": 8.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.82,
            "n_doors": 1, "n_windows": 1,
        }
        out = calc_room_quantities(room)
        # Default max_height_m = H × 2 = 5.64; walls_gross = 12 × 5.64 = 67.68
        assert out["walls_gross_m2"] == pytest.approx(67.68, abs=0.05)

    def test_stairwell_room_type_explicit(self):
        # Even with non-laiptine paskirtis, room_type="stairwell" triggers formula
        room = {
            "nr": 1, "pavadinimas": "Hall", "paskirtis": "holas",
            "room_type": "stairwell",
            "plotas_m2": 8.0, "perimetras_m": 12.0, "lubu_aukstis_m": 2.82,
            "max_height_m": 6.0,
            "n_doors": 1, "n_windows": 1,
        }
        out = calc_room_quantities(room)
        # 12 × 6 = 72 (no steps so no subtraction)
        assert out["walls_gross_m2"] == pytest.approx(72.0, abs=0.05)

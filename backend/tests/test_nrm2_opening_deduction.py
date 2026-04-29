"""NRM2 / VOB / LT opening-deduction standard tests (Sprint §2A.1).

Verifies tiered opening logic:
  LT  (default) — every opening ≥ 1.0 m² deducted; reveals added for ALL openings.
  NRM2          — ≤ 0.5 m² no deduction, no reveal.
                  0.5–3.0 m² deduct, no reveal.
                  > 3.0 m² deduct + reveal.
  VOB           — same as NRM2 but reveal threshold = 2.5 m².
"""
import pytest

from extractor.universal_rules import (
    _opening_should_deduct,
    _opening_adds_reveal,
    _resolve_deduction_standard,
    calc_room_quantities,
    translate_user_prefs_to_room_rules,
)


# ── Pure helper tests ────────────────────────────────────────────────────

class TestOpeningShouldDeduct:
    def test_lt_default_threshold_1_m2(self):
        assert _opening_should_deduct(0.4, "LT") is False
        assert _opening_should_deduct(1.0, "LT") is True
        assert _opening_should_deduct(1.85, "LT") is True

    def test_nrm2_threshold_0_5_m2(self):
        assert _opening_should_deduct(0.3, "NRM2") is False
        assert _opening_should_deduct(0.5, "NRM2") is True
        assert _opening_should_deduct(1.85, "NRM2") is True
        assert _opening_should_deduct(5.0, "NRM2") is True

    def test_vob_threshold_0_5_m2(self):
        assert _opening_should_deduct(0.3, "VOB") is False
        assert _opening_should_deduct(0.5, "VOB") is True


class TestOpeningAddsReveal:
    def test_lt_always_adds(self):
        assert _opening_adds_reveal(0.5, "LT") is True
        assert _opening_adds_reveal(1.85, "LT") is True
        assert _opening_adds_reveal(5.0, "LT") is True

    def test_nrm2_only_above_3m2(self):
        assert _opening_adds_reveal(0.5, "NRM2") is False
        assert _opening_adds_reveal(1.85, "NRM2") is False
        assert _opening_adds_reveal(2.99, "NRM2") is False
        assert _opening_adds_reveal(3.01, "NRM2") is True
        assert _opening_adds_reveal(5.0, "NRM2") is True

    def test_vob_only_above_2_5m2(self):
        assert _opening_adds_reveal(2.4, "VOB") is False
        assert _opening_adds_reveal(2.6, "VOB") is True


class TestResolveDeductionStandard:
    def test_default_lt_when_no_rules(self):
        assert _resolve_deduction_standard(None) == "LT"
        assert _resolve_deduction_standard({}) == "LT"

    def test_reads_meta_key(self):
        assert _resolve_deduction_standard({"_paint_deduction_standard": "NRM2"}) == "NRM2"
        assert _resolve_deduction_standard({"_paint_deduction_standard": "VOB"}) == "VOB"
        assert _resolve_deduction_standard({"_paint_deduction_standard": "lt"}) == "LT"

    def test_reads_user_pref_key(self):
        assert _resolve_deduction_standard({"paint_deduction_standard": "NRM2"}) == "NRM2"

    def test_unknown_value_falls_back_to_lt(self):
        assert _resolve_deduction_standard({"_paint_deduction_standard": "UNKNOWN"}) == "LT"


# ── End-to-end calc_room_quantities tests ───────────────────────────────

class TestCalcRoomQuantitiesNRM2:
    @pytest.fixture
    def base_room(self):
        # 5×4m room, perimeter 18m, ceiling 2.82m.
        # walls_gross = 18 × 2.82 = 50.76 m²
        return {
            "nr": 1,
            "pavadinimas": "Svetainė",
            "paskirtis": "gyvenamoji",
            "plotas_m2": 20.0,
            "perimetras_m": 18.0,
            "lubu_aukstis_m": 2.82,
            "n_doors": 1,
            "n_windows": 1,
            "door_area_m2": 1.85,    # standard 0.9×2.05m → 1.85 m² (in 0.5-3.0 range)
            "window_area_m2": 1.80,  # standard 1.2×1.5m → 1.80 m² (in 0.5-3.0 range)
        }

    def test_lt_default_deducts_both(self, base_room):
        out = calc_room_quantities(base_room)
        # LT: doors+windows >= 1.0 → both deducted
        assert out["doors_deducted_m2"] == pytest.approx(1.85, abs=0.01)
        assert out["windows_deducted_m2"] == pytest.approx(1.80, abs=0.01)
        # walls_paintable = 50.76 - 1.85 - 1.80 = 47.11
        assert out["walls_paintable_m2"] == pytest.approx(47.11, abs=0.05)

    def test_nrm2_deducts_same_as_lt_for_standard_openings(self, base_room):
        rules = translate_user_prefs_to_room_rules({"paint_deduction_standard": "NRM2"})
        out = calc_room_quantities(base_room, rules=rules)
        # Both 1.85 and 1.80 m² are in NRM2's 0.5-3.0 deduct range
        assert out["doors_deducted_m2"] == pytest.approx(1.85, abs=0.01)
        assert out["windows_deducted_m2"] == pytest.approx(1.80, abs=0.01)
        assert out["walls_paintable_m2"] == pytest.approx(47.11, abs=0.05)

    def test_nrm2_skips_tiny_openings_below_0_5(self, base_room):
        # Tiny vent door 0.6×0.5 = 0.30 m² (vent / pet flap)
        room = {**base_room, "door_area_m2": 0.30}
        rules = translate_user_prefs_to_room_rules({"paint_deduction_standard": "NRM2"})
        out = calc_room_quantities(room, rules=rules)
        # NRM2: 0.30 < 0.5 threshold → no deduction
        assert out["doors_deducted_m2"] == 0
        # window still deducted normally
        assert out["windows_deducted_m2"] == pytest.approx(1.80, abs=0.01)

    def test_lt_keeps_old_1m2_threshold(self, base_room):
        # 0.6×0.5 = 0.30 m² door — LT default still > nothing? Threshold is 1.0
        # so 0.30 m² door < 1.0 → no deduction (also LT)
        room = {**base_room, "door_area_m2": 0.30}
        out = calc_room_quantities(room)  # LT default
        assert out["doors_deducted_m2"] == 0

    def test_nrm2_deducts_0_8m2_door_lt_skips(self, base_room):
        # WC narrow door 0.6×1.4 ≈ 0.84 m². LT threshold 1.0 → skipped.
        # NRM2 threshold 0.5 → deducted.
        room = {**base_room, "door_area_m2": 0.84}
        out_lt = calc_room_quantities(room)  # LT
        rules_nrm2 = translate_user_prefs_to_room_rules({"paint_deduction_standard": "NRM2"})
        out_nrm2 = calc_room_quantities(room, rules=rules_nrm2)
        assert out_lt["doors_deducted_m2"] == 0  # LT skips < 1.0
        assert out_nrm2["doors_deducted_m2"] == pytest.approx(0.84, abs=0.01)


class TestTranslateUserPrefsCarriesStandard:
    def test_meta_key_propagated(self):
        rules = translate_user_prefs_to_room_rules({"paint_deduction_standard": "NRM2"})
        assert rules["_paint_deduction_standard"] == "NRM2"

    def test_meta_key_uppercased(self):
        rules = translate_user_prefs_to_room_rules({"paint_deduction_standard": "vob"})
        assert rules["_paint_deduction_standard"] == "VOB"

    def test_meta_key_absent_when_unset(self):
        rules = translate_user_prefs_to_room_rules({"bathroom_tile_height_m": 2.4})
        assert "_paint_deduction_standard" not in rules

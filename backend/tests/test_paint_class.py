"""Paint class (1/2/3) coats × coverage tests (Sprint §2A.5).

Verifies:
  Class 1: 10 m²/L × 1 coat × 1.0 absorption (top opaque, prepared substrate).
  Class 2: 9 m²/L × 2 coats × 1.8 absorption (LT residential default).
  Class 3: 7.5 m²/L × 3 coats × 2.5 absorption (rough / fresh plaster).
"""
import pytest

from extractor.vision_call import (
    _calc_dazai_liters,
    _resolve_paint_class,
    _PAINT_CLASS_PROFILES,
    _PAINT_CLASS_DEFAULT,
)
from extractor.universal_rules import translate_user_prefs_to_room_rules


# ── Helper: paint class resolution ───────────────────────────────────────

class TestResolvePaintClass:
    def test_default_class_2_when_no_input(self):
        assert _resolve_paint_class(None) == 2
        assert _resolve_paint_class({}) == 2

    def test_reads_pref_key(self):
        assert _resolve_paint_class({"paint_class": 1}) == 1
        assert _resolve_paint_class({"paint_class": 3}) == 3

    def test_reads_meta_key(self):
        assert _resolve_paint_class({"_paint_class": 1}) == 1

    def test_string_value_coerced(self):
        assert _resolve_paint_class({"paint_class": "3"}) == 3

    def test_invalid_falls_back_to_default(self):
        assert _resolve_paint_class({"paint_class": 7}) == 2
        assert _resolve_paint_class({"paint_class": "abc"}) == 2
        assert _resolve_paint_class({"paint_class": None}) == 2


# ── Coverage rate semantics ──────────────────────────────────────────────

class TestPaintClassProfiles:
    def test_profile_1_top_opaque(self):
        p = _PAINT_CLASS_PROFILES[1]
        assert p["coats"] == 1
        assert p["coverage_m2_per_l"] == 10.0
        assert p["absorption_factor"] == 1.0

    def test_profile_2_lt_default(self):
        p = _PAINT_CLASS_PROFILES[2]
        assert p["coats"] == 2
        assert p["coverage_m2_per_l"] == 9.0
        assert p["absorption_factor"] == 1.8

    def test_profile_3_economy(self):
        p = _PAINT_CLASS_PROFILES[3]
        assert p["coats"] == 3
        assert p["coverage_m2_per_l"] == 7.5
        assert p["absorption_factor"] == 2.5

    def test_default_is_class_2(self):
        assert _PAINT_CLASS_DEFAULT == 2


# ── Liters calculation ───────────────────────────────────────────────────

class TestCalcDazaiLiters:
    """Reference: 100 m² wall, paint class drives output liters.

      Class 1: 100 × 1.0 / 10.0 = 10.00 L
      Class 2: 100 × 1.8 / 9.0  = 20.00 L  (matches legacy 2-coat behavior)
      Class 3: 100 × 2.5 / 7.5  = 33.33 L
    """

    def test_class_1_low_consumption(self):
        # 1 coat top opaque
        assert _calc_dazai_liters(100, paint_class=1) == 10.0

    def test_class_2_default_residential(self):
        # 2 coats, LT default
        assert _calc_dazai_liters(100, paint_class=2) == 20.0

    def test_class_3_high_absorption(self):
        # 3 coats, rough/fresh substrate
        assert _calc_dazai_liters(100, paint_class=3) == pytest.approx(33.33, abs=0.01)

    def test_class_2_matches_legacy_two_coats(self):
        # Class 2 should produce same number as the old `coats=2` path
        # (this guarantees no regression for default-mode projects).
        legacy = _calc_dazai_liters(100, coats=2)
        cls2 = _calc_dazai_liters(100, paint_class=2)
        assert legacy == cls2

    def test_unknown_class_falls_back_to_default(self):
        # paint_class=99 → falls back to default profile (class 2 = 20L)
        assert _calc_dazai_liters(100, paint_class=99) == 20.0

    def test_paint_class_takes_priority_over_coats(self):
        # When both passed, paint_class wins
        result = _calc_dazai_liters(100, coats=1, paint_class=3)
        assert result == pytest.approx(33.33, abs=0.01)

    def test_zero_area_zero_liters(self):
        assert _calc_dazai_liters(0, paint_class=2) == 0.0


# ── Translate user prefs ─────────────────────────────────────────────────

class TestTranslateUserPrefsCarriesPaintClass:
    def test_meta_key_propagated(self):
        rules = translate_user_prefs_to_room_rules({"paint_class": 3})
        assert rules["_paint_class"] == 3

    def test_string_class_coerced(self):
        rules = translate_user_prefs_to_room_rules({"paint_class": "1"})
        assert rules["_paint_class"] == 1

    def test_invalid_class_dropped(self):
        rules = translate_user_prefs_to_room_rules({"paint_class": 9})
        assert "_paint_class" not in rules

    def test_meta_key_absent_when_unset(self):
        rules = translate_user_prefs_to_room_rules({"bathroom_tile_height_m": 2.4})
        assert "_paint_class" not in rules

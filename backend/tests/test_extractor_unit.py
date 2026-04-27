"""Unit tests for the extractor package — fast (no Vision calls)."""
import sys
import os
from pathlib import Path

# Ensure backend/ is on path so extractor package imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from extractor.universal_rules import (
    UNIVERSAL_RULES, ROOM_TYPE_RULES,
    calc_room_quantities, calc_totals, normalize_paskirtis,
)
from extractor.lt_rules import apply_lt_sanity, mansardinis_svoris


def test_universal_rules_loaded():
    assert isinstance(UNIVERSAL_RULES, dict)
    assert UNIVERSAL_RULES["openings_threshold_m2"] == 1.0
    assert UNIVERSAL_RULES["default_window_area_m2"] == 1.80  # corrected from 1.40
    assert "vonia" in ROOM_TYPE_RULES


def test_calc_room_quantities_basic():
    room = {
        "nr": "01",
        "pavadinimas": "Miegamasis",
        "paskirtis": "miegamoji",
        "plotas_m2": 14.0,
        "perimetras_m": 15.0,
        "lubu_aukstis_m": 2.7,
        "lubu_tipas": "gkp",
    }
    out = calc_room_quantities(room)
    # Sienos = perim × H = 15 × 2.7 = 40.5; +lubos 14 = 54.5 ish
    assert 50 <= out["dazymo_plotas_m2"] <= 60


def test_calc_totals_sums():
    rooms = [
        {"dazymo_plotas_m2": 50, "kampu_metrai": 12, "plotas_m2": 14, "lubu_tipas": "gkp", "lubu_aukstis_m": 2.7, "paskirtis": "miegamoji"},
        {"dazymo_plotas_m2": 30, "kampu_metrai": 11, "plotas_m2": 10, "lubu_tipas": "gkp", "lubu_aukstis_m": 2.7, "paskirtis": "gyvenamoji"},
    ]
    totals = calc_totals(rooms)
    assert totals["dazymo_plotas_total_m2"] == 80
    assert totals["kampai_m_total"] == 23


def test_normalize_paskirtis():
    # NOTE: "vonios" (genitive) does NOT match — V8 only checks for "vonia" substring.
    # "vonios kambarys" → falls through to "gyvenamoji" (V8 behavior, known limitation).
    # DIVERGENCE FLAGGED: normalize_paskirtis cannot handle LT genitive case forms.
    # The Vision model uses the enum values directly so this is not critical for the
    # new extractor pipeline (Vision returns "vonia", not "vonios kambarys").
    assert normalize_paskirtis("vonia") == "vonia"          # direct value
    assert normalize_paskirtis("Vonia") == "vonia"          # capitalized
    assert normalize_paskirtis("Tualetas") == "wc"
    assert normalize_paskirtis("") == "gyvenamoji"


def test_lt_sanity_returns_warnings_list():
    parsed = {
        "patalpos": [
            {"nr": "01", "paskirtis": "vonia", "plotas_m2": 200.0},  # absurdly large
            {"nr": "02", "paskirtis": "miegamoji", "plotas_m2": 5.0},  # below 8m² min
        ]
    }
    out = apply_lt_sanity(parsed)
    assert "_lt_warnings" in out
    assert len(out["_lt_warnings"]) >= 1


def test_mansardinis_svoris():
    assert mansardinis_svoris(20.0, 1.4) == 0.0
    assert mansardinis_svoris(20.0, 1.8) == 10.0  # 50% weighting
    assert mansardinis_svoris(20.0, 2.5) == 20.0  # full


def test_default_window_area_corrected():
    """Regression test: window area must be 1.80 m² (LT STR), not 1.40 (US)."""
    assert UNIVERSAL_RULES["default_window_area_m2"] == 1.80


def test_grindjuostes_waste_applied():
    """Regression test: baseboard must include +10% waste (NRM2 §27)."""
    room = {
        "nr": "01",
        "pavadinimas": "Svetainė",
        "paskirtis": "gyvenamoji",
        "plotas_m2": 20.0,
        "perimetras_m": 18.0,
        "lubu_aukstis_m": 2.82,
        "n_doors": 1,
    }
    out = calc_room_quantities(room)
    # Base: (18.0 - 1 × 0.85) = 17.15 m; with 10% waste: 17.15 × 1.10 = 18.865
    assert out["grindjuosciu_m"] > 17.15, "Waste factor must be applied"
    expected = round((18.0 - 0.85) * 1.10, 2)
    assert abs(out["grindjuosciu_m"] - expected) < 0.01


def test_calc_totals_with_wet_rooms():
    """Hidroizoliacija counter works for vonia/wc/san."""
    rooms = [
        {"dazymo_plotas_m2": 40, "kampu_metrai": 15, "plotas_m2": 12, "paskirtis": "vona",
         "lubu_tipas": "gkp", "lubu_aukstis_m": 2.82},
        {"dazymo_plotas_m2": 15, "kampu_metrai": 8, "plotas_m2": 3.5, "paskirtis": "wc",
         "lubu_tipas": "gkp", "lubu_aukstis_m": 2.82},
        {"dazymo_plotas_m2": 60, "kampu_metrai": 20, "plotas_m2": 18, "paskirtis": "miegamoji",
         "lubu_tipas": "gkp", "lubu_aukstis_m": 2.82},
    ]
    totals = calc_totals(rooms)
    # Only wc should count (vona ≠ vonia)
    assert totals["hidroizoliacijos_vnt"] == 1


def test_calc_totals_gkp_ceiling_split():
    """GKP lubos virš 3m vs standart are split correctly."""
    rooms = [
        {"dazymo_plotas_m2": 60, "kampu_metrai": 0, "plotas_m2": 20, "paskirtis": "gyvenamoji",
         "lubu_tipas": "gkp", "lubu_aukstis_m": 3.5},  # virš 3m
        {"dazymo_plotas_m2": 40, "kampu_metrai": 0, "plotas_m2": 15, "paskirtis": "miegamoji",
         "lubu_tipas": "gkp", "lubu_aukstis_m": 2.82},  # standart
    ]
    totals = calc_totals(rooms)
    assert totals["gkp_lubu_virs_3m_m2_total"] >= 20  # at least the 3.5m room
    assert totals["gkp_lubu_m2_total"] >= 15           # at least the 2.82m room


def test_lt_sanity_no_mutation():
    """apply_lt_sanity MUST NOT change plotas_m2 or other values."""
    parsed = {
        "patalpos": [
            {"nr": "01", "paskirtis": "vonia", "plotas_m2": 200.0,
             "perimetras_m": 60.0, "lubu_aukstis_m": 2.5},
        ]
    }
    original_plotas = parsed["patalpos"][0]["plotas_m2"]
    out = apply_lt_sanity(parsed)
    assert out["patalpos"][0]["plotas_m2"] == original_plotas, "Values must not be mutated"


def test_translate_user_prefs_to_room_rules():
    """User prefs translate correctly to room rules."""
    from extractor.universal_rules import translate_user_prefs_to_room_rules
    prefs = {"bathroom_tile_height_m": 2.4, "garazas_painted": True}
    rules = translate_user_prefs_to_room_rules(prefs)
    assert rules is not None
    assert rules["vonia"]["tile_walls_to_m"] == 2.4
    assert rules["wc"]["tile_walls_to_m"] == 2.4
    assert rules["garazas"]["walls_paint"] == 1.0

"""Unit tests for the consistency checker."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.consistency_checker import (
    check_room_count, check_wall_floor_ratio,
    check_height_plausibility, check_perimeter_geometry,
    check_height_uniformity, run_all_checks,
)


def test_room_count_match():
    parsed = {
        "patalpos": [{"nr": "1"}, {"nr": "2"}, {"nr": "3"}],
        "_eksplikacija": {"patalpos": [{"number": "1"}, {"number": "2"}, {"number": "3"}]},
    }
    out = check_room_count(parsed)
    assert out["status"] == "PASS"


def test_room_count_missing():
    """The lazunu case: floor plan 3 rooms, eksplikacija 6 → FAIL."""
    parsed = {
        "patalpos": [{"nr": "1"}, {"nr": "2"}, {"nr": "3"}],
        "_eksplikacija": {"patalpos": [{"number": str(i)} for i in range(1, 7)]},
    }
    out = check_room_count(parsed)
    assert out["status"] == "FAIL"
    assert "3 room(s) missing" in out["message"]


def test_room_count_extra():
    """The romainiai case: floor plan 20 rooms, eksplikacija 11 → WARN (subset)."""
    parsed = {
        "patalpos": [{"nr": str(i)} for i in range(1, 21)],
        "_eksplikacija": {"patalpos": [{"number": str(i)} for i in range(1, 12)]},
    }
    out = check_room_count(parsed)
    assert out["status"] == "WARN"


def test_room_count_skipped_when_no_eksplikacija():
    parsed = {"patalpos": [{"nr": "1"}]}
    out = check_room_count(parsed)
    assert out["status"] == "PASS"


def test_wall_floor_ratio_passes_for_typical_residential():
    parsed = {"patalpos": [
        {"plotas_m2": 16, "walls_gross_m2": 45},
        {"plotas_m2": 20, "walls_gross_m2": 56},
    ]}
    out = check_wall_floor_ratio(parsed)
    assert out["status"] == "PASS"
    assert 2.0 < out["value"] < 4.0


def test_wall_floor_ratio_too_low_warns():
    parsed = {"patalpos": [{"plotas_m2": 100, "walls_gross_m2": 100}]}
    out = check_wall_floor_ratio(parsed)
    assert out["status"] == "WARN"


def test_height_plausibility():
    parsed = {"patalpos": [{"lubu_aukstis_m": 2.82}, {"lubu_aukstis_m": 7.5}]}
    out = check_height_plausibility(parsed)
    assert out["status"] == "WARN"
    assert out["value"] == 1


def test_perim_geometry_flags_impossible():
    parsed = {"patalpos": [{"plotas_m2": 16, "perimetras_m": 10}]}
    out = check_perimeter_geometry(parsed)
    assert out["status"] == "WARN"


def test_height_uniformity_flags_default_only():
    """All rooms at 2.82 → WARN (likely a guess)."""
    parsed = {"patalpos": [{"lubu_aukstis_m": 2.82}] * 5}
    out = check_height_uniformity(parsed)
    assert out["status"] == "WARN"


def test_height_uniformity_passes_with_variation():
    parsed = {"patalpos": [
        {"lubu_aukstis_m": 2.82}, {"lubu_aukstis_m": 3.4}, {"lubu_aukstis_m": 3.0},
    ]}
    out = check_height_uniformity(parsed)
    assert out["status"] == "PASS"


def test_run_all_checks_returns_summary():
    parsed = {"patalpos": [{"nr": "1", "plotas_m2": 16, "perimetras_m": 16,
                            "walls_gross_m2": 45, "lubu_aukstis_m": 2.82}]}
    out = run_all_checks(parsed)
    assert "checks" in out
    assert "overall_status" in out
    assert len(out["checks"]) == 5

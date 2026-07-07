"""Unit tests for the geometric perimeter validator."""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.perimeter_validator import (
    validate_room_perimeter, validate_extract,
    PERIM_LOWER_BOUND_K, PERIM_UPPER_BOUND_K,
)


def test_square_room_passes():
    """16 m² room with perim 16m = perfect square. Should pass."""
    r = {"nr": "1", "pavadinimas": "Kambarys", "plotas_m2": 16.0, "perimetras_m": 16.0}
    out = validate_room_perimeter(r)
    assert out.status == "PASS"
    assert out.lower_bound_m == 4 * PERIM_LOWER_BOUND_K  # 15.2
    assert out.upper_bound_m == 4 * PERIM_UPPER_BOUND_K  # 26.0


def test_perim_too_small_flagged():
    """16 m² room with perim 10m is geometrically impossible — flag it."""
    r = {"nr": "2", "plotas_m2": 16.0, "perimetras_m": 10.0}
    out = validate_room_perimeter(r)
    assert out.status == "NEEDS_REEXTRACTION"
    assert out.discrepancy_pct < 0
    assert "lower bound" in out.reason


def test_perim_too_large_flagged():
    """16 m² room with perim 50m — unlikely winding shape."""
    r = {"nr": "3", "plotas_m2": 16.0, "perimetras_m": 50.0}
    out = validate_room_perimeter(r)
    assert out.status == "NEEDS_REEXTRACTION"
    assert out.discrepancy_pct > 0
    assert "upper bound" in out.reason


def test_l_shape_at_upper_bound_passes():
    """L-shaped 16 m² room with perim 24m is plausible."""
    r = {"nr": "4", "plotas_m2": 16.0, "perimetras_m": 24.0}
    out = validate_room_perimeter(r)
    assert out.status == "PASS"


def test_missing_area_returns_no_data():
    r = {"nr": "5", "plotas_m2": 0, "perimetras_m": 12.0}
    out = validate_room_perimeter(r)
    assert out.status == "NO_DATA"


def test_missing_perim_returns_no_data():
    r = {"nr": "6", "plotas_m2": 14.0, "perimetras_m": 0}
    out = validate_room_perimeter(r)
    assert out.status == "NO_DATA"


def test_validate_extract_aggregates_correctly():
    parsed = {
        "patalpos": [
            {"nr": "1", "plotas_m2": 16.0, "perimetras_m": 16.0},     # PASS
            {"nr": "2", "plotas_m2": 16.0, "perimetras_m": 10.0},     # NEEDS_REEXTRACTION
            {"nr": "3", "plotas_m2": 16.0, "perimetras_m": 0.0},      # NO_DATA
            {"nr": "4", "plotas_m2": 25.0, "perimetras_m": 20.0},     # PASS
        ],
    }
    report = validate_extract(parsed)
    assert report["n_total"] == 4
    assert report["n_pass"] == 2
    assert report["n_needs_reextraction"] == 1
    assert report["n_no_data"] == 1
    assert len(report["flagged_rooms"]) == 1
    assert report["flagged_rooms"][0]["room_nr"] == "2"


def test_geometric_bounds_consistent_with_isoperimetric_inequality():
    """For ANY area A, perimeter must satisfy P >= 2*sqrt(pi*A).
    Our lower bound 3.8 should be strictly greater than 2*sqrt(pi) ≈ 3.545."""
    assert PERIM_LOWER_BOUND_K > 2 * math.sqrt(math.pi)


def test_circle_perimeter_would_fail_lower_bound():
    """If a perfect circle (P/√A = 2√π ≈ 3.545) were a room, our 3.8
    bound would flag it. That's intentional — rooms aren't circular."""
    area = 100.0
    perim = 2 * math.sqrt(math.pi * area)  # ≈ 35.45
    r = {"nr": "c", "plotas_m2": area, "perimetras_m": perim}
    out = validate_room_perimeter(r)
    assert out.status == "NEEDS_REEXTRACTION"

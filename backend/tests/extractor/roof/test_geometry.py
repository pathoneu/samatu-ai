"""Unit tests for backend.extractor.roof.geometry."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from extractor.roof import geometry  # noqa: E402


def test_module_loads():
    """Sentinel — confirms module is importable."""
    assert geometry.__doc__ is not None


import math
import pytest


@pytest.mark.parametrize("angle_deg,expected", [
    (0,  1.000),
    (15, 1.035),
    (22, 1.079),
    (25, 1.103),
    (30, 1.155),
    (35, 1.221),
    (45, 1.414),
])
def test_slope_factor(angle_deg, expected):
    """slope_factor = 1/cos(angle) — sloped area / plan area."""
    assert geometry.slope_factor(angle_deg) == pytest.approx(expected, abs=0.001)


def test_slope_factor_zero_angle():
    assert geometry.slope_factor(0) == 1.0


def test_slope_factor_invalid():
    with pytest.raises(ValueError, match="must be in"):
        geometry.slope_factor(90)


@pytest.mark.parametrize("angle_deg,expected", [
    (15, 1.439),
    (22, 1.469),
    (25, 1.489),
    (30, 1.528),
    (35, 1.578),
    (45, 1.732),
])
def test_hip_valley_factor(angle_deg, expected):
    """hvf = √(sec²α + 1) — sloped hip/valley length / plan-projected length."""
    assert geometry.hip_valley_factor(angle_deg) == pytest.approx(expected, abs=0.002)


def test_keturslaitis_a_laida_perdanga():
    """A LAIDA perdanga = outer-wall footprint = 8.95 × 13.12 = 117.4 m²."""
    result = geometry.keturslaitis_quantities(
        footprint_outer_w=8.95,
        footprint_outer_l=13.12,
        eaves_overhang_m=0.925,        # from outer wall face, NOT axis
        slope_long_deg=25,
        slope_short_deg=22,
        wall_thickness_m=0.25,
    )
    assert result.perdanga_m2 == pytest.approx(117.4, abs=2.0)


def test_keturslaitis_a_laida_stogas():
    """A LAIDA stogas: 2 long faces (i=25°) + 2 short hips (i=22°) + 5% waste ≈ 185 m²."""
    result = geometry.keturslaitis_quantities(
        footprint_outer_w=8.95, footprint_outer_l=13.12,
        eaves_overhang_m=0.925,        # from outer wall face, NOT axis
        slope_long_deg=25, slope_short_deg=22,
        wall_thickness_m=0.25,
    )
    assert result.stogas_m2 == pytest.approx(185, abs=5)


def test_keturslaitis_a_laida_latakai():
    """A LAIDA latakai = full eaves perimeter = 2×(10.80+14.97) ≈ 51.5 m."""
    result = geometry.keturslaitis_quantities(
        footprint_outer_w=8.95, footprint_outer_l=13.12,
        eaves_overhang_m=0.925,        # from outer wall face, NOT axis
        slope_long_deg=25, slope_short_deg=22,
        wall_thickness_m=0.25,
    )
    assert result.latakai_m == pytest.approx(52, abs=2)


def test_keturslaitis_a_laida_kraigai():
    """A LAIDA kraigai = top ridge + 4 hip surface lengths ≈ 37 m."""
    result = geometry.keturslaitis_quantities(
        footprint_outer_w=8.95, footprint_outer_l=13.12,
        eaves_overhang_m=0.925,        # from outer wall face, NOT axis
        slope_long_deg=25, slope_short_deg=22,
        wall_thickness_m=0.25,
    )
    assert result.kraigai_m == pytest.approx(37, abs=3)

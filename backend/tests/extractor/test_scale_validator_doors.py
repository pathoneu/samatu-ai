"""Week 2 Task 2.4 — door-as-ruler scale validator."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.extractor.scale_validator import (  # noqa: E402
    validate_scale_by_doors,
    ScaleValidationResult,
)


def test_4x_scale_error_returns_red():
    """Door rendered at 360 px, claim is 100 px/m → implied width 3.6 m → 4× off."""
    result = validate_scale_by_doors(
        door_pixel_widths=[360, 358, 362],
        claimed_px_per_m=100.0,
        expected_door_width_m=0.9,
    )
    assert result.valid is False
    assert result.severity == "red"
    assert result.factor is not None and 3.5 < result.factor < 4.5


def test_correct_scale_returns_green():
    result = validate_scale_by_doors(
        door_pixel_widths=[90, 91, 89],
        claimed_px_per_m=100.0,
        expected_door_width_m=0.9,
    )
    assert result.valid is True
    assert result.severity == "green"


def test_borderline_factor_returns_yellow():
    """1.5× off → yellow (suspicious but not catastrophic)."""
    result = validate_scale_by_doors(
        door_pixel_widths=[135, 135, 135],
        claimed_px_per_m=100.0,
        expected_door_width_m=0.9,
    )
    assert result.valid is False
    assert result.severity == "yellow"


def test_no_doors_returns_yellow():
    result = validate_scale_by_doors(
        door_pixel_widths=[],
        claimed_px_per_m=100.0,
    )
    assert result.severity == "yellow"
    assert result.factor is None
    assert "no door" in result.message.lower() or "ruler" in result.message.lower()


def test_zero_or_negative_px_per_m_returns_yellow():
    result = validate_scale_by_doors(
        door_pixel_widths=[90, 91, 89],
        claimed_px_per_m=0,
    )
    assert result.severity == "yellow"


def test_median_dodges_single_spike():
    """One mis-detected door at 5× shouldn't poison the result."""
    result = validate_scale_by_doors(
        door_pixel_widths=[90, 91, 450, 89, 90],  # 450 is the spike
        claimed_px_per_m=100.0,
    )
    assert result.severity == "green"

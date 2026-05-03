"""Sprint 0 Fix 3: scale verification tests."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from extractor.scale_validator import (
    parse_scale_string, validate_scale, ScaleMismatch,
)


def test_parse_scale_string_extracts_factor():
    assert parse_scale_string("M 1:50") == 50.0
    assert parse_scale_string("Mastelis 1:100") == 100.0
    assert parse_scale_string("1:200") == 200.0
    assert parse_scale_string("M 1 : 75") == 75.0


def test_parse_scale_string_returns_none_when_absent():
    assert parse_scale_string("Vilniaus g. 12") is None
    assert parse_scale_string("") is None
    assert parse_scale_string(None) is None


def test_validate_scale_passes_when_consistent():
    # Room is 3×4m at scale 1:50, page rendered at 200dpi
    # Expected diagonal ~ 5m → 5000mm / 50 = 100mm = 100 * 200/25.4 = 787.4 px
    warnings = validate_scale(
        scale_factor=50.0,
        rendered_dpi=200,
        rooms=[{"width_m": 3.0, "height_m": 4.0, "diagonal_px": 787}],
    )
    assert warnings == []


def test_validate_scale_warns_on_5pct_mismatch():
    # Page actually rendered at 1:100 but title says 1:50 → 2× error
    warnings = validate_scale(
        scale_factor=50.0,
        rendered_dpi=200,
        rooms=[{"width_m": 3.0, "height_m": 4.0, "diagonal_px": 394}],
    )
    assert len(warnings) == 1
    assert "scale" in warnings[0].lower() or "mastelis" in warnings[0].lower()


def test_validate_scale_no_rooms_yields_no_warnings():
    assert validate_scale(scale_factor=50.0, rendered_dpi=200, rooms=[]) == []

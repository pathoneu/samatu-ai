"""Unit tests for the semantic-routing authority map."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest  # noqa: E402

from extractor.page_classifier import PageType  # noqa: E402
from extractor.roof.page_authority import (  # noqa: E402
    PAGE_AUTHORITY,
    RoofInputField,
    can_write,
)


def test_floor_plan_owns_global_axes():
    assert can_write(PageType.FLOOR_PLAN, RoofInputField.AXIS_LENGTH)
    assert can_write(PageType.FLOOR_PLAN, RoofInputField.AXIS_WIDTH)


def test_section_owns_slope_and_heights():
    assert can_write(PageType.SECTION, RoofInputField.SLOPE)
    assert can_write(PageType.SECTION, RoofInputField.WALL_THICKNESS)
    assert can_write(PageType.SECTION, RoofInputField.EAVES_TO_GROUND)
    assert can_write(PageType.SECTION, RoofInputField.SOFLITAS_DEPTH)


def test_stogo_planas_owns_topology_and_eaves():
    assert can_write(PageType.STOGO_PLANAS, RoofInputField.ROOF_TYPE)
    assert can_write(PageType.STOGO_PLANAS, RoofInputField.EAVES_OVERHANG)
    assert can_write(PageType.STOGO_PLANAS, RoofInputField.CHIMNEY_COUNT)


def test_section_cannot_write_global_axes():
    """The 0039 bug: SECTION/detail pages must NOT supply building width."""
    assert not can_write(PageType.SECTION, RoofInputField.AXIS_LENGTH)
    assert not can_write(PageType.SECTION, RoofInputField.AXIS_WIDTH)


def test_stogo_planas_cannot_overwrite_global_axes_when_partial():
    """Structural gegnių planas (often classified stogo_planas) shows only
    partial half-rafter detail; it must not be authoritative for the FULL
    building footprint. Floor plan is the only authority for global axes."""
    assert not can_write(PageType.STOGO_PLANAS, RoofInputField.AXIS_LENGTH)
    assert not can_write(PageType.STOGO_PLANAS, RoofInputField.AXIS_WIDTH)


def test_unknown_page_writes_nothing():
    for field in RoofInputField:
        assert not can_write(PageType.UNKNOWN, field)


@pytest.mark.parametrize("field", list(RoofInputField))
def test_every_field_has_at_least_one_authority(field):
    """No field is orphan — every field has at least one PageType that owns it."""
    assert any(field in PAGE_AUTHORITY[pt] for pt in PageType), \
        f"{field} has no authority page-class"

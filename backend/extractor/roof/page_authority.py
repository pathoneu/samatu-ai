"""Semantic Routing Hierarchy for the roof input merger.

Each PageType is granted EXCLUSIVE write-access to a specific set of
`RoofInput` fields. When the Vision extractor returns a value for a
field from a page whose PageType is not in the authority list for that
field, the merger MUST drop the value (not average it, not flag it).
This is the architectural fix for the 0039 bug where Opus correctly
read axis_width=4.61m from a SECTION/detail page — accurate to the page,
wrong as a building footprint.

Source: 2026-05-14 consultcouncil — Gemini's Semantic Routing Hierarchy
proposal, accepted unanimously in R3.
"""
from __future__ import annotations

from enum import Enum

from extractor.page_classifier import PageType


class RoofInputField(str, Enum):
    """All fields that the typed merger can populate on `RoofInput`."""
    ROOF_TYPE = "roof_type"
    AXIS_LENGTH = "axis_to_axis_length_m"
    AXIS_WIDTH = "axis_to_axis_width_m"
    EAVES_OVERHANG = "eaves_overhang_from_axis_m"
    WALL_THICKNESS = "wall_thickness_m"
    SLOPE = "slope_angle_deg"
    CHIMNEY_COUNT = "chimney_count"
    ROOFLIGHT_COUNT = "rooflight_count"
    WINDOWS_COUNT = "windows_count"


# Write-access map: PageType -> set of RoofInputField the page is
# authoritative for. ANY value extracted from a page whose PageType is
# not in this map for a given field MUST be dropped by the merger.
PAGE_AUTHORITY: dict[PageType, set[RoofInputField]] = {
    PageType.FLOOR_PLAN: {
        RoofInputField.AXIS_LENGTH,
        RoofInputField.AXIS_WIDTH,
    },
    PageType.SECTION: {
        RoofInputField.SLOPE,
        RoofInputField.WALL_THICKNESS,
    },
    PageType.STOGO_PLANAS: {
        RoofInputField.ROOF_TYPE,
        RoofInputField.EAVES_OVERHANG,
        RoofInputField.CHIMNEY_COUNT,
        RoofInputField.ROOFLIGHT_COUNT,
        RoofInputField.WINDOWS_COUNT,
    },
    PageType.WALL_ELEVATION: set(),
    PageType.CEILING_PLAN: set(),
    PageType.ELECTRICAL: set(),
    PageType.PLUMBING: set(),
    PageType.EKSPLIKACIJA: set(),
    PageType.LEGEND: set(),
    PageType.UNKNOWN: set(),
}


def can_write(page_type: PageType, field: RoofInputField) -> bool:
    """Return True if a page of this type may populate this RoofInput field."""
    return field in PAGE_AUTHORITY.get(page_type, set())

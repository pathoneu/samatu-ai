"""End-to-end test of the typed merger using saved Vision JSON."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest  # noqa: E402

from extractor.page_classifier import PageType  # noqa: E402
from extractor.roof.page_authority import RoofInputField  # noqa: E402
from extractor.roof.vision_extractor import build_roof_input  # noqa: E402


A_LAIDA_STOGO_P10 = {
    "_page_num": 10, "_page_class": PageType.STOGO_PLANAS,
    "roof_type": "keturslaitis",
    "axis_to_axis_length_m": 12.88, "axis_to_axis_width_m": 8.70,
    "eaves_overhang_from_axis_m": 1.05, "wall_thickness_m": None,
    "visible_slope_angles_deg": [25, 22],
    "chimney_count": 0, "rooflight_count": 0, "windows_count": 0,
    "confidence": 0.78,
}
A_LAIDA_PJUVIS_P9 = {
    "_page_num": 9, "_page_class": PageType.SECTION,
    "slope_angles_deg": [25],
    "ridge_height_m": 5.8, "eaves_height_m": 3.2, "wall_thickness_m": None,
    "confidence": 0.9,
}

_0039_GEGNIU_P48 = {
    "_page_num": 48, "_page_class": PageType.STOGO_PLANAS,
    "roof_type": "dvislaitis",
    "axis_to_axis_length_m": 25.34, "axis_to_axis_width_m": 4.61,
    "eaves_overhang_from_axis_m": None, "wall_thickness_m": None,
    "visible_slope_angles_deg": [35],
    "chimney_count": 1, "rooflight_count": 0, "windows_count": 0,
    "confidence": 0.5,
}
_0039_PJUVIS_P49 = {
    "_page_num": 49, "_page_class": PageType.SECTION,
    "slope_angles_deg": [30.0],
    "ridge_height_m": 8.45, "eaves_height_m": None, "wall_thickness_m": None,
    "confidence": 0.85,
}
_0039_FLOOR_P46 = {
    "_page_num": 46, "_page_class": PageType.FLOOR_PLAN,
    "axis_to_axis_length_m": 25.59, "axis_to_axis_width_m": 7.12,
    "confidence": 0.85,
}


def test_a_laida_typed_merger_uses_stogo_fallback_with_flag():
    """A LAIDA: no FLOOR_PLAN — stogo_planas axes become fallback with HITL flag."""
    inp, evidence, flags = build_roof_input(
        pages=[A_LAIDA_STOGO_P10, A_LAIDA_PJUVIS_P9],
    )
    assert inp.roof_type == "keturslaitis"
    assert inp.slopes_deg == [25, 22] or inp.slopes_deg == [25]
    # Either slopes from stogo_planas labels (if section provides only 1)
    # or section's [25]; both acceptable. The merger should at minimum
    # produce keturslaitis-compatible slope info.
    fallback_flags = [f for f in flags if f.field == RoofInputField.AXIS_WIDTH]
    assert len(fallback_flags) >= 1


def test_0039_typed_merger_uses_floor_plan_for_width():
    """0039: gegnių planas shows partial width 4.61m; floor_plan p46 shows 7.12m.
    Typed merger MUST pick 7.12m (FLOOR_PLAN authoritative for AXIS_WIDTH)."""
    inp, evidence, flags = build_roof_input(
        pages=[_0039_GEGNIU_P48, _0039_PJUVIS_P49, _0039_FLOOR_P46],
    )
    assert inp.roof_type == "dvislaitis"
    expected_outer_width = 7.12 + 0.25  # default wall thickness
    assert inp.building_width_m == pytest.approx(expected_outer_width, abs=0.01)
    assert inp.slopes_deg == [30.0]


def test_0039_drops_unauthorized_axis_width_from_stogo_planas():
    """The 4.61m from STOGO_PLANAS p48 stays in evidence (non-authoritative)
    but is NOT what RoofInput.building_width_m uses."""
    _, evidence, _ = build_roof_input(
        pages=[_0039_GEGNIU_P48, _0039_PJUVIS_P49, _0039_FLOOR_P46],
    )
    unauth = [
        e for e in evidence
        if e.field == RoofInputField.AXIS_WIDTH and not e.is_authoritative()
    ]
    assert len(unauth) >= 1


def test_slope_conflict_pjuvis_wins_with_warning_flag():
    """Stogo planas labels 35°; pjūvis reads 30°. Pjūvis wins, flag raised."""
    _, _, flags = build_roof_input(
        pages=[_0039_GEGNIU_P48, _0039_PJUVIS_P49, _0039_FLOOR_P46],
    )
    slope_flags = [f for f in flags if f.field == RoofInputField.SLOPE]
    assert len(slope_flags) >= 1


def test_falls_back_to_default_wall_thickness_with_flag():
    """No page reports wall_thickness → default 0.25m + flag."""
    _, _, flags = build_roof_input(
        pages=[A_LAIDA_STOGO_P10, A_LAIDA_PJUVIS_P9],
    )
    wt_flags = [f for f in flags if f.field == RoofInputField.WALL_THICKNESS]
    assert len(wt_flags) >= 1

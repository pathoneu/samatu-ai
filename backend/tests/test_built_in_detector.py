"""Unit tests for built_in_detector parser + exclusion applier."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.built_in_detector import (
    BuiltIn, BuiltInPayload, parse_built_in_payload,
    apply_built_in_exclusions, CANONICAL_TYPES,
)


def test_parse_minimal_payload():
    raw = {
        "page_role": "furniture_layout",
        "built_ins": [
            {"id": "f1", "type": "wardrobe", "room_nr": "110",
             "wall_label": "west", "width_mm": 2200, "height_mm": 2400,
             "confidence": "high", "evidence": "Full-height wardrobe symbol"},
            {"id": "f2", "type": "kitchen_cabinet_run", "room_nr": "102",
             "wall_label": "north", "width_mm": 3300, "height_mm": 2400},
        ],
    }
    out = parse_built_in_payload(raw)
    assert len(out.built_ins) == 2
    assert out.built_ins[0].type == "wardrobe"
    assert out.built_ins[0].excluded_area_m2 == pytest.approx(2.2 * 2.4)


def test_parse_unknown_type_falls_back_to_other():
    raw = {"built_ins": [{"id": "x", "type": "lava_lamp",
                          "width_mm": 1000, "height_mm": 1000}]}
    out = parse_built_in_payload(raw)
    assert out.built_ins[0].type == "other"


def test_per_room_aggregation_sums_correctly():
    out = BuiltInPayload(built_ins=[
        BuiltIn(id="a", type="wardrobe",  room_nr="110", wall_label=None, width_mm=2200, height_mm=2400),
        BuiltIn(id="b", type="wardrobe",  room_nr="110", wall_label=None, width_mm=1200, height_mm=2400),
        BuiltIn(id="c", type="kitchen_cabinet_run", room_nr="102", wall_label=None, width_mm=3300, height_mm=2400),
    ])
    per_room = out.per_room_excluded_m2()
    assert per_room["110"] == pytest.approx(2.2*2.4 + 1.2*2.4)
    assert per_room["102"] == pytest.approx(3.3*2.4)


def test_apply_exclusions_creates_negative_extra_walls():
    """Applying the exclusion adds a NEGATIVE extra_walls_m2 so that
    the calculator's existing `walls_paintable += extra_walls_m2` reduces
    the room's walls by the excluded amount."""
    parsed = {
        "patalpos": [
            {"nr": "110", "extra_walls_m2": 0.0},
            {"nr": "111", "extra_walls_m2": 6.24},   # pre-existing positive extra
        ],
    }
    built_ins = BuiltInPayload(built_ins=[
        BuiltIn(id="x", type="wardrobe", room_nr="110", wall_label=None,
                width_mm=2200, height_mm=2400),
        BuiltIn(id="y", type="bathtub_apron", room_nr="111", wall_label=None,
                width_mm=2000, height_mm=600),
    ])
    apply_built_in_exclusions(parsed, built_ins)
    r110 = parsed["patalpos"][0]
    r111 = parsed["patalpos"][1]
    assert r110["extra_walls_m2"] == pytest.approx(-(2.2*2.4))
    assert r111["extra_walls_m2"] == pytest.approx(6.24 - (2.0*0.6))
    # Audit trail
    assert r110["_built_in_exclusions_m2"] == pytest.approx(2.2*2.4)
    assert r111["_built_in_exclusions_m2"] == pytest.approx(2.0*0.6)


def test_apply_exclusions_skips_unknown_rooms():
    parsed = {"patalpos": [{"nr": "101", "extra_walls_m2": 0.0}]}
    built_ins = BuiltInPayload(built_ins=[
        BuiltIn(id="x", type="wardrobe", room_nr="999", wall_label=None,
                width_mm=2200, height_mm=2400),
    ])
    apply_built_in_exclusions(parsed, built_ins)
    # 101 unchanged (no built-in for it); 999 doesn't exist
    assert parsed["patalpos"][0]["extra_walls_m2"] == 0.0


def test_canonical_types_cover_lt_construction_practice():
    """Sanity: the 7 canonical tags map to LT contractor practice."""
    expected = {"wardrobe", "kitchen_cabinet_run", "shower_cubicle",
                "bathtub_apron", "bathroom_vanity", "fixed_shelving"}
    assert expected.issubset(CANONICAL_TYPES)


def test_parse_rejects_non_dict():
    with pytest.raises(ValueError):
        parse_built_in_payload([])  # type: ignore[arg-type]

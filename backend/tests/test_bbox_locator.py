"""Unit tests for bbox_locator parser + patalpa merger."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.bbox_locator import (
    parse_bbox_payload, merge_into_patalpos, RoomBBoxList, RoomBBox,
)


def test_parse_well_formed_payload():
    raw = {"rooms": [
        {"nr": "101", "name": "Tambūras",
         "bbox_pct": {"x_min": 0.1, "y_min": 0.5, "x_max": 0.3, "y_max": 0.75},
         "confidence": "high"},
        {"nr": "102", "name": "Svetainė",
         "bbox_pct": {"x_min": 0.3, "y_min": 0.1, "x_max": 0.7, "y_max": 0.5}},
    ]}
    out = parse_bbox_payload(raw)
    assert len(out.rooms) == 2
    assert out.rooms[0].nr == "101"
    crop = out.rooms[0].to_crop_bbox()
    assert crop["x"] == pytest.approx(0.1)
    assert crop["w"] == pytest.approx(0.2)


def test_parse_drops_inverted_bbox():
    """xmin >= xmax (or ymin >= ymax) is invalid → drop the entry."""
    raw = {"rooms": [
        {"nr": "1", "bbox_pct": {"x_min": 0.5, "y_min": 0.1, "x_max": 0.4, "y_max": 0.5}},
        {"nr": "2", "bbox_pct": {"x_min": 0.1, "y_min": 0.1, "x_max": 0.4, "y_max": 0.5}},
    ]}
    out = parse_bbox_payload(raw)
    assert len(out.rooms) == 1
    assert out.rooms[0].nr == "2"


def test_parse_drops_out_of_unit_range():
    raw = {"rooms": [
        {"nr": "1", "bbox_pct": {"x_min": -0.1, "y_min": 0.1, "x_max": 0.5, "y_max": 0.5}},
        {"nr": "2", "bbox_pct": {"x_min": 0.1, "y_min": 0.5, "x_max": 0.5, "y_max": 1.5}},
    ]}
    out = parse_bbox_payload(raw)
    assert out.rooms == []


def test_parse_missing_keys_drops_entry():
    raw = {"rooms": [
        {"nr": "1"},
        {"nr": "2", "bbox_pct": {"x_min": 0.1, "y_min": 0.1, "x_max": 0.5, "y_max": 0.5}},
    ]}
    out = parse_bbox_payload(raw)
    assert [r.nr for r in out.rooms] == ["2"]


def test_merge_populates_only_rooms_with_missing_bbox():
    parsed = {"patalpos": [
        {"nr": "101", "bbox_pct": None},
        {"nr": "102", "bbox_pct": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}},
        {"nr": "103"},  # also missing
    ]}
    bboxes = RoomBBoxList(rooms=[
        RoomBBox(nr="101", name="A", bbox_pct={"x_min": 0.1, "y_min": 0.1, "x_max": 0.2, "y_max": 0.2}),
        RoomBBox(nr="102", name="B", bbox_pct={"x_min": 0.5, "y_min": 0.5, "x_max": 0.7, "y_max": 0.7}),
        RoomBBox(nr="103", name="C", bbox_pct={"x_min": 0.3, "y_min": 0.3, "x_max": 0.4, "y_max": 0.4}),
    ])
    n = merge_into_patalpos(parsed, bboxes)
    assert n == 2  # 101 + 103 were populated; 102 was preserved
    # 102's existing bbox was NOT overwritten
    assert parsed["patalpos"][1]["bbox_pct"] == {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}


def test_parse_rejects_non_dict():
    with pytest.raises(ValueError):
        parse_bbox_payload([])  # type: ignore[arg-type]

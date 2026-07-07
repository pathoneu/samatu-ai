"""Unit tests for per_room_zoom_pipeline.

Tests the wrapper logic + result envelope. The actual Vision calls are
exercised live in compare_pipelines.py / run_pilot — those need an API key
and burn credits, so we don't run them here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.per_room_zoom_pipeline import (
    ZoomResult, run_zoom_on_room, _polygon_walk_closes,
)


def test_zoom_result_serialises_to_dict():
    r = ZoomResult(nr="101", name="Test", bbox_pct={"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5})
    d = r.to_dict()
    assert d["nr"] == "101"
    assert d["bbox_pct"]["w"] == 0.5
    assert d["polygon_closed"] is False
    assert d["error"] is None


def test_skip_room_without_bbox():
    """When a room has no bbox_pct, run_zoom_on_room must return immediately
    with an explanatory error and never call Vision."""
    room = {"nr": "101", "pavadinimas": "Tambūras", "bbox_pct": None}
    res = run_zoom_on_room(
        pdf_bytes=b"PDF-1.0\n",  # not a real PDF — but we won't reach the crop
        page_number=1,
        room_primitive=room,
    )
    assert res.error == "no_bbox_pct"
    assert res.n_dimensions == 0
    assert res.n_walls == 0


def test_polygon_walk_close_detection():
    # Closed unit square (in mm)
    closed = {
        "polygon_walls": ["w1", "w2", "w3", "w4"],
        "wall_lengths_mm": {"w1": 3000, "w2": 4000, "w3": 3000, "w4": 4000},
        "wall_angles_deg": {"w1": 0, "w2": 90, "w3": 180, "w4": 270},
    }
    assert _polygon_walk_closes(closed) is True

    # 100mm short on the south wall — within 5cm tolerance? Yes (50mm < 50mm? No.).
    almost_closed = dict(closed)
    almost_closed["wall_lengths_mm"] = {**closed["wall_lengths_mm"], "w4": 3960}
    # 40mm gap → within 50mm tolerance → True
    assert _polygon_walk_closes(almost_closed) is True

    open_poly = dict(closed)
    open_poly["wall_lengths_mm"] = {**closed["wall_lengths_mm"], "w4": 3500}
    assert _polygon_walk_closes(open_poly) is False

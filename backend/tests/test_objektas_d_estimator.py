"""Tests for the lazunu_estimator."""

from __future__ import annotations

import math
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.lazunu_estimator import (
    estimate_rooms_from_wall_list,
    apply_lazunu_estimate_to_extract,
    LT_COMPACTNESS_RATIO,
)


def test_empty_inputs_returns_empty_list():
    assert estimate_rooms_from_wall_list([], None, None) == []


def test_wall_list_only_infers_room_count():
    walls = [5000, 5000, 5000, 5000, 6000, 6000, 6000, 6000]  # 8 walls
    rooms = estimate_rooms_from_wall_list(walls, None, None)
    # Total = 44000mm; 44/15 = 2.93 → 2 rooms (int)
    assert len(rooms) >= 1
    assert all(r["plotas_m2"] > 0 for r in rooms)
    assert all(r["_source"] == "estimated_lazunu" for r in rooms)


def test_area_only_estimates_rooms():
    rooms = estimate_rooms_from_wall_list([], 90.0, room_count=6)
    assert len(rooms) == 6
    total = sum(r["plotas_m2"] for r in rooms)
    assert abs(total - 90.0) < 1.0


def test_rooms_compactness_within_lt_norm():
    rooms = estimate_rooms_from_wall_list([], 60.0, room_count=4)
    for r in rooms:
        ratio = r["perimetras_m"] / math.sqrt(r["plotas_m2"])
        assert abs(ratio - LT_COMPACTNESS_RATIO) < 0.5


def test_apply_to_extract_replaces_rooms_and_emits_warning():
    ai = {"patalpos": [{"lubu_aukstis_m": 2.82}], "warnings": []}
    out = apply_lazunu_estimate_to_extract(
        ai, wall_lengths_mm=None, total_floor_area_m2=70.0, room_count=6,
    )
    assert len(out["patalpos"]) == 6
    assert any("ESTIMATED" in (w.get("message", "") or "") for w in out["warnings"])
    assert all(r["lubu_aukstis_m"] == 2.82 for r in out["patalpos"])


def test_total_area_scaling_matches_target():
    rooms = estimate_rooms_from_wall_list(
        [5000, 5000, 5000, 5000], total_floor_area_m2=50.0, room_count=4,
    )
    total = sum(r["plotas_m2"] for r in rooms)
    assert abs(total - 50.0) < 0.5

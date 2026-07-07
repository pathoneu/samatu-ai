"""Tests for the multi-signal ceiling-height fusion."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.height_fusion import (
    HeightSignal, HeightFusion, fuse,
    signal_from_door_heights, signal_from_explicit_reading,
    apply_fused_height_to_rooms,
    DEFAULT_FALLBACK_H,
)


def test_door_signal_with_standard_2100mm_doors_returns_none():
    """Standard LT doors recover only the default; signal is information-less."""
    rooms = [{"nr": "1", "elementai": [
        {"tipas": "duris", "aukstis_mm": 2100},
        {"tipas": "duris", "aukstis_mm": 2100},
    ]}]
    sig = signal_from_door_heights(rooms)
    assert sig.value_m is None
    assert sig.confidence == "low"


def test_door_signal_with_2400mm_doors_is_high_confidence():
    rooms = [{"nr": "1", "elementai": [
        {"tipas": "duris", "aukstis_mm": 2400},
        {"tipas": "duris", "aukstis_mm": 2400},
        {"tipas": "duris", "aukstis_mm": 2400},
    ]}]
    sig = signal_from_door_heights(rooms)
    assert sig.value_m == 3.00
    assert sig.confidence == "high"


def test_door_signal_no_doors_returns_none():
    rooms = [{"nr": "1", "elementai": []}]
    sig = signal_from_door_heights(rooms)
    assert sig.value_m is None


def test_explicit_reading_preferred_over_door_lintel():
    signals = [
        HeightSignal("door_lintel", 3.00, "high"),
        HeightSignal("explicit", 2.82, "high", evidence="A=2820"),
    ]
    out = fuse(signals)
    assert out.primary_m == 2.82
    assert out.chosen_source == "explicit"


def test_door_lintel_used_when_no_explicit():
    signals = [
        HeightSignal("explicit", None, "low"),
        HeightSignal("door_lintel", 3.00, "high"),
    ]
    out = fuse(signals)
    assert out.primary_m == 3.00
    assert out.chosen_source == "door_lintel"


def test_no_signal_returns_none_so_caller_keeps_existing():
    """When neither explicit-high nor door-non-standard fires, fusion
    returns primary_m=None so the caller MUST preserve existing height."""
    signals = [
        HeightSignal("explicit", None, "low"),
        HeightSignal("door_lintel", None, "low"),
    ]
    out = fuse(signals)
    assert out.primary_m is None
    assert out.chosen_source == "none"


def test_implausible_height_rejected_and_no_signal_returned():
    """A 5.0m 'ceiling height' would be a Vision misread — fusion must reject."""
    signals = [
        HeightSignal("explicit", 5.0, "high"),
        HeightSignal("door_lintel", None, "low"),
    ]
    out = fuse(signals)
    assert out.primary_m is None
    assert out.chosen_source == "none"


def test_medium_confidence_explicit_no_longer_applied():
    """Medium-confidence explicits (often from wall_elevation pages reading
    fixture heights) used to overwrite the existing height. They mustn't."""
    signals = [
        HeightSignal("explicit", 2.45, "medium", evidence="from wall elevation"),
    ]
    out = fuse(signals)
    assert out.primary_m is None


def test_apply_skips_rooms_with_explicit_source():
    rooms = [
        {"nr": "1", "lubu_aukstis_m": 2.82, "_lubu_aukstis_source": "height_extractor"},
        {"nr": "2", "lubu_aukstis_m": 2.70},
    ]
    fusion = HeightFusion(primary_m=3.00, chosen_source="door_lintel", confidence="high")
    summary = apply_fused_height_to_rooms(rooms, fusion)
    assert rooms[0]["lubu_aukstis_m"] == 2.82  # preserved
    assert rooms[1]["lubu_aukstis_m"] == 3.00  # updated
    assert summary["n_updated"] == 1


def test_apply_preserves_non_default_per_room_heights():
    """A room with H=3.4 means Vision deliberately extracted a high
    ceiling for that room — must not be clobbered by a project-wide
    fused value."""
    rooms = [
        {"nr": "high_room", "lubu_aukstis_m": 3.4},
        {"nr": "garage", "lubu_aukstis_m": 3.0},
        {"nr": "default_room", "lubu_aukstis_m": 2.82},
    ]
    fusion = HeightFusion(primary_m=2.70, chosen_source="explicit", confidence="high")
    summary = apply_fused_height_to_rooms(rooms, fusion)
    assert rooms[0]["lubu_aukstis_m"] == 3.4  # preserved (not in default set)
    assert rooms[1]["lubu_aukstis_m"] == 3.0  # preserved (not in default set)
    assert rooms[2]["lubu_aukstis_m"] == 2.70  # updated (was a default)
    assert summary["n_updated"] == 1
    assert len(summary["preserved"]) == 2

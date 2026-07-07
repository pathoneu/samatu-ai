"""Unit tests for schedule_extractor parser + apply_schedule_to_elementai."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.schedule_extractor import (
    Schedule, ScheduleEntry,
    parse_schedule_payload, apply_schedule_to_elementai,
)


def test_parse_minimal_payload():
    payload = {
        "durys": [
            {"id": "D1", "width_mm": 900, "height_mm": 2100, "count": 12, "is_exterior": False},
            {"id": "D2", "width_mm": 2700, "height_mm": 2100, "count": 1, "is_exterior": True,
             "notes": "Stikliniai lauko"},
        ],
        "langai": [
            {"id": "L1", "width_mm": 2750, "height_mm": 2200, "count": 2, "is_exterior": True},
        ],
    }
    s = parse_schedule_payload(payload)
    assert len(s.durys) == 2
    assert len(s.langai) == 1
    assert s.durys[1].is_exterior is True
    assert s.durys[1].notes.startswith("Stikliniai")


def test_apply_schedule_overrides_elementai_dimensions_and_flag():
    rooms = [
        {"nr": "102", "pavadinimas": "Svetainė",
         "elementai": [
             {"tipas": "duris", "kiekis": 1, "plotis_mm": 900, "aukstis_mm": 2100,
              "schedule_ref": "D2"},
             {"tipas": "langas", "kiekis": 1, "plotis_mm": 1200, "aukstis_mm": 1500,
              "schedule_ref": "L1"},
             # No schedule_ref → leave untouched
             {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100},
         ]},
    ]
    sched = Schedule(
        durys=[ScheduleEntry(id="D2", width_mm=2700, height_mm=2100, is_exterior=True, count=1)],
        langai=[ScheduleEntry(id="L1", width_mm=2750, height_mm=2200, is_exterior=True, count=2)],
    )
    apply_schedule_to_elementai(rooms, sched)
    elementai = rooms[0]["elementai"]
    # Schedule overrode the first opening
    assert elementai[0]["plotis_mm"] == 2700
    assert elementai[0]["aukstis_mm"] == 2100
    assert elementai[0]["_exterior"] is True
    # And the window
    assert elementai[1]["plotis_mm"] == 2750
    assert elementai[1]["_exterior"] is True
    # Third element had no schedule_ref → untouched
    assert elementai[2]["plotis_mm"] == 800
    assert "_exterior" not in elementai[2]


def test_apply_schedule_ignores_unknown_refs():
    rooms = [{"nr": "1", "elementai": [
        {"tipas": "duris", "kiekis": 1, "plotis_mm": 800, "aukstis_mm": 2100,
         "schedule_ref": "NONEXISTENT"},
    ]}]
    sched = Schedule(durys=[ScheduleEntry(id="D1", width_mm=900, height_mm=2100)])
    apply_schedule_to_elementai(rooms, sched)
    # Unchanged
    assert rooms[0]["elementai"][0]["plotis_mm"] == 800
    assert "_exterior" not in rooms[0]["elementai"][0]


def test_parse_handles_empty_schedule():
    s = parse_schedule_payload({"durys": [], "langai": []})
    assert s.durys == []
    assert s.langai == []


def test_parse_rejects_non_dict_payload():
    with pytest.raises(ValueError):
        parse_schedule_payload([])  # type: ignore[arg-type]

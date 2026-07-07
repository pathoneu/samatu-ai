"""Unit tests for niche_locator parser + fold_niches_into_rooms."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.niche_locator import (
    NicheList, NicheRecord,
    parse_niche_payload, fold_niches_into_rooms,
)


def test_parse_minimal_payload():
    payload = {
        "niches": [
            {"room_nr": "102", "room_name": "Svetainė", "type": "ceiling_led",
             "length_mm": 18000, "count": 1, "confidence": "high",
             "evidence": "LD-1 red dashed"},
            {"room_nr": "111", "room_name": "Tėvų vonia", "type": "wall_led",
             "length_mm": 1200, "count": 2, "confidence": "medium"},
        ],
    }
    nl = parse_niche_payload(payload)
    assert len(nl.niches) == 2
    assert nl.niches[0].length_m == 18.0
    assert nl.niches[1].count == 2


def test_parse_empty_payload():
    nl = parse_niche_payload({"niches": []})
    assert nl.niches == []


def test_parse_rejects_non_dict():
    with pytest.raises(ValueError):
        parse_niche_payload([])  # type: ignore[arg-type]


def test_per_room_grouping():
    nl = NicheList(niches=[
        NicheRecord(room_nr="102", room_name="a", type="ceiling_led", length_mm=1000),
        NicheRecord(room_nr="102", room_name="a", type="ceiling_led", length_mm=2000),
        NicheRecord(room_nr="103", room_name="b", type="wall_led", length_mm=500),
    ])
    by_room = nl.per_room()
    assert len(by_room["102"]) == 2
    assert len(by_room["103"]) == 1


def test_fold_replaces_existing_led_entries():
    """fold_niches_into_rooms is REPLACE for rooms the niche pass touched.

    The fold function deletes old nisa_LED entries on the room and substitutes
    the niche-pass records. This is intentional: when the targeted pass runs,
    it's treated as authoritative for that room. (The additive-only policy
    lives in the calling code that decides WHICH rooms to fold, not in the
    fold helper itself.)
    """
    rooms = [
        {"nr": "102", "elementai": [
            {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "kiekis": 1},
            {"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 18.0},
        ]},
        {"nr": "999", "elementai": [
            {"tipas": "nisa_LED", "kiekis": 1, "ilgis_m": 5.0},
        ]},
    ]
    nl = NicheList(niches=[
        NicheRecord(room_nr="102", room_name="x", type="ceiling_led",
                    length_mm=15000, count=1),
    ])
    fold_niches_into_rooms(rooms, nl)
    # Room 102: old nisa_LED gone, new one in (15.0m). Door preserved.
    el_102 = rooms[0]["elementai"]
    assert any(e["tipas"] == "duris" for e in el_102)
    nisa_in_102 = [e for e in el_102 if e["tipas"] == "nisa_LED"]
    assert len(nisa_in_102) == 1
    assert nisa_in_102[0]["ilgis_m"] == 15.0
    assert nisa_in_102[0]["_source"] == "niche_locator"
    # Room 999: not mentioned in niche pass → unchanged
    assert rooms[1]["elementai"][0]["ilgis_m"] == 5.0


def test_fold_skips_rooms_not_in_niche_pass():
    rooms = [{"nr": "1", "elementai": [{"tipas": "nisa_LED", "ilgis_m": 7.0, "kiekis": 1}]}]
    nl = NicheList(niches=[])  # empty
    fold_niches_into_rooms(rooms, nl)
    # No-op
    assert rooms[0]["elementai"][0]["ilgis_m"] == 7.0

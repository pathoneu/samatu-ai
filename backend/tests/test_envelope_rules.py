"""Tests for the envelope-room exterior heuristic (Task 1.3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "backend"))

from infer_exterior_openings import is_envelope_room, infer_room_exteriors


def test_envelope_via_adjacency_count():
    """4-wall room with 2 partition walls → 2 exterior walls → on envelope."""
    room = {"n_walls_estimate": 4, "elementai": []}
    assert is_envelope_room(room, partition_count=2) is True
    assert is_envelope_room(room, partition_count=4) is False


def test_envelope_fallback_via_explicit_exterior_flag():
    """Even without adjacency data, if Vision flagged any opening _exterior,
    the room must be on the envelope."""
    room = {"elementai": [{"tipas": "duris", "_exterior": True}]}
    assert is_envelope_room(room) is True


def test_envelope_fallback_via_paskirtis():
    """Tambūras / garažas / similar are on the envelope by category."""
    for paskirtis in ("tamburas", "tambūras", "garazas", "garažas"):
        assert is_envelope_room({"paskirtis": paskirtis}) is True


def test_envelope_fallback_returns_false_for_interior_room():
    room = {"paskirtis": "vonia", "elementai": [{"tipas": "duris", "plotis_mm": 700}]}
    assert is_envelope_room(room) is False


def test_900x2100_door_in_envelope_room_flagged():
    """The standard LT exterior door (900×2100) — the one this turn's task
    explicitly calls out — gets flagged when the room is on the envelope."""
    room = {
        "nr": "101",
        "pavadinimas": "Tambūras",
        "paskirtis": "tamburas",
        "elementai": [
            {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100},
        ],
    }
    n, _ = infer_room_exteriors(room)
    assert n == 1
    assert room["elementai"][0]["_exterior"] is True


def test_900x2100_door_in_interior_room_NOT_flagged():
    """Same door in a non-envelope room (no signals) stays interior."""
    room = {
        "nr": "104",
        "pavadinimas": "Vonia",
        "paskirtis": "vonia",
        "elementai": [
            {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100},
        ],
    }
    n, _ = infer_room_exteriors(room)
    assert n == 0
    assert "_exterior" not in room["elementai"][0]


def test_existing_exterior_flag_preserved():
    room = {
        "paskirtis": "gyvenamoji",
        "elementai": [{"tipas": "duris", "plotis_mm": 900, "_exterior": True}],
    }
    n, _ = infer_room_exteriors(room)
    # already True → 0 changes
    assert n == 0
    assert room["elementai"][0]["_exterior"] is True


def test_adjacency_count_can_override_fallback():
    """Even if paskirtis is 'gyvenamoji' (no fallback trigger), a partition
    count of 0 forces envelope=True."""
    room = {
        "paskirtis": "gyvenamoji",
        "n_walls_estimate": 4,
        "elementai": [{"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100}],
    }
    n, _ = infer_room_exteriors(room, partition_count=0)
    assert n == 1


def test_envelope_rule_does_not_override_existing_exterior_door():
    """Beržų Tambūras has 1 exterior + 2 interior doors all at 900×2100.
    The envelope rule MUST NOT over-flag the 2 interior ones — that would
    shrink angokraščiai by hiding interior reveals (eval fitting). The
    safeguard: rule only fires when room has NO already-flagged exterior
    door of the same kind."""
    room = {
        "nr": "101",
        "pavadinimas": "Tambūras",
        "paskirtis": "tamburas",
        "elementai": [
            {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100, "_exterior": True},
            {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100},   # interior #1
            {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100},   # interior #2
        ],
    }
    n, _ = infer_room_exteriors(room)
    # 0 new flags — the existing exterior door blocks the envelope rule.
    assert n == 0
    flagged = [e for e in room["elementai"] if e.get("_exterior")]
    assert len(flagged) == 1


def test_envelope_rule_fires_for_sole_entrance_door():
    """The case the rule WAS designed for — a studio entrance / mažas
    tambūras with ONE 900×2100 door, none yet flagged."""
    room = {
        "paskirtis": "tamburas",
        "elementai": [
            {"tipas": "duris", "plotis_mm": 900, "aukstis_mm": 2100},
        ],
    }
    n, _ = infer_room_exteriors(room)
    assert n == 1
    assert room["elementai"][0]["_exterior"] is True

"""Regression: room_aukstas_from_nr was naive ("first digit = floor"),
which broke for LT projects that number rooms sequentially on the first
floor and use "X.Y" compound notation for upper floors.

Surfaced via Playwright testing 2026-05-10: a real 2-storey project
("01"–"11" on aukštas 1; "1.2"–"9.2" on aukštas 2) was being grouped into
9 phantom floors by the cross-page validator.

Convention map after fix:
- Bare number ("5", "11", "01")        → floor 1 (single-floor or
                                                  sequential numbering)
- "X.Y" compound  ("1.2", "9.2")       → floor Y (LT samatininkų syntax)
- "1F-01", "2F05", "0F-01"             → first digit (explicit floor prefix)
- "1-01", "2-12"                       → first digit (legacy hyphen prefix)
- Roman: "I-01", "II-12", "III-08"     → 1 / 2 / 3
- "P-01", "C-01"                       → 0 (cellar / parter)
- Empty / None                          → 1 (safe default)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from extractor.universal_rules import room_aukstas_from_nr  # noqa: E402


# ── LT compound notation: room.floor ────────────────────────────────────────

def test_compound_x_dot_y_returns_floor_after_dot():
    assert room_aukstas_from_nr("1.2") == 2
    assert room_aukstas_from_nr("9.2") == 2
    assert room_aukstas_from_nr("1.3") == 3
    assert room_aukstas_from_nr("5.2") == 2
    assert room_aukstas_from_nr("11.2") == 2  # double-digit room


def test_compound_with_dot_zero_means_basement_or_parter():
    assert room_aukstas_from_nr("1.0") == 0


# ── Bare numbers: must NOT be parsed as their own digit value ───────────────

def test_bare_number_is_floor_1():
    """Per LT residential convention: a sequential room number with no
    floor prefix means single-floor or default to first floor."""
    assert room_aukstas_from_nr("1") == 1
    assert room_aukstas_from_nr("2") == 1
    assert room_aukstas_from_nr("5") == 1
    assert room_aukstas_from_nr("9") == 1
    assert room_aukstas_from_nr("11") == 1
    assert room_aukstas_from_nr("99") == 1
    # Zero-padded variants:
    assert room_aukstas_from_nr("01") == 1
    assert room_aukstas_from_nr("05") == 1


# ── Explicit floor prefix: "XF-NN" or "XF NN" ───────────────────────────────

def test_x_f_prefix_returns_first_digit():
    assert room_aukstas_from_nr("1F-01") == 1
    assert room_aukstas_from_nr("2F-05") == 2
    assert room_aukstas_from_nr("3F-08") == 3
    assert room_aukstas_from_nr("0F-01") == 0
    assert room_aukstas_from_nr("1F05") == 1
    assert room_aukstas_from_nr("2F12") == 2


def test_x_dash_prefix_returns_first_digit():
    """Legacy "1-01" / "2-05" hyphen-separated numbering still respected."""
    assert room_aukstas_from_nr("1-01") == 1
    assert room_aukstas_from_nr("2-05") == 2
    assert room_aukstas_from_nr("3-08") == 3


# ── Roman numerals ──────────────────────────────────────────────────────────

def test_roman_prefix_returns_correct_floor():
    assert room_aukstas_from_nr("I-01") == 1
    assert room_aukstas_from_nr("II-12") == 2
    assert room_aukstas_from_nr("III-08") == 3


# ── Cellar / parter ─────────────────────────────────────────────────────────

def test_cellar_prefix_returns_zero():
    assert room_aukstas_from_nr("P-01") == 0
    assert room_aukstas_from_nr("C-01") == 0


# ── Defensive fallbacks ─────────────────────────────────────────────────────

def test_empty_returns_default_floor_1():
    assert room_aukstas_from_nr("") == 1
    assert room_aukstas_from_nr(None) == 1


def test_unknown_format_returns_default_floor_1():
    assert room_aukstas_from_nr("???") == 1
    assert room_aukstas_from_nr("ABC") == 1


# ── End-to-end: real project from Playwright trace ──────────────────────────

def test_real_2_storey_project_grouping():
    """The 2026-05-07 project numbered rooms "1"-"11" on floor 1 and
    "1.2"-"9.2" on floor 2. Pre-fix the validator saw 9 phantom floors;
    post-fix it must see exactly 2."""
    first_floor = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
    second_floor = ["1.2", "2.2", "3.2", "4.2", "5.2", "6.2", "7.2", "8.2", "9.2"]
    distinct_floors = {room_aukstas_from_nr(nr) for nr in first_floor + second_floor}
    assert distinct_floors == {1, 2}

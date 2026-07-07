"""Unit tests for symbol_detector parse + envelope (no live Vision)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.symbol_detector import (
    Symbol, SymbolPayload,
    parse_symbol_payload, CANONICAL_TYPES,
)


def test_parse_known_types_pass_through():
    raw = {
        "page_role": "electrical",
        "symbols": [
            {"id": "s1", "type": "socket", "subtype": "double",
             "room_nr": "102", "x_pct": 0.5, "y_pct": 0.3, "confidence": "high"},
            {"id": "s2", "type": "switch", "subtype": None,
             "room_nr": "101", "x_pct": 0.6, "y_pct": 0.2, "confidence": "medium"},
        ],
    }
    out = parse_symbol_payload(raw)
    assert out.page_role == "electrical"
    assert len(out.symbols) == 2
    assert out.symbols[0].type == "socket"
    assert out.symbols[0].subtype == "double"
    assert out.symbols[1].subtype is None


def test_unknown_type_falls_back_to_other():
    raw = {"symbols": [{"id": "s1", "type": "lava_lamp",
                        "x_pct": 0.1, "y_pct": 0.1}]}
    out = parse_symbol_payload(raw)
    assert out.symbols[0].type == "other"


def test_counts_by_type():
    out = SymbolPayload(symbols=[
        Symbol(id="s1", type="socket",       subtype=None, room_nr="102", x_pct=0, y_pct=0),
        Symbol(id="s2", type="socket",       subtype=None, room_nr="102", x_pct=0, y_pct=0),
        Symbol(id="s3", type="switch",       subtype=None, room_nr="101", x_pct=0, y_pct=0),
        Symbol(id="s4", type="light_ceiling", subtype=None, room_nr="103", x_pct=0, y_pct=0),
    ])
    counts = out.counts_by_type()
    assert counts["socket"] == 2
    assert counts["switch"] == 1
    assert counts["light_ceiling"] == 1


def test_counts_by_room_buckets_unassigned():
    out = SymbolPayload(symbols=[
        Symbol(id="s1", type="socket", subtype=None, room_nr="102", x_pct=0, y_pct=0),
        Symbol(id="s2", type="socket", subtype=None, room_nr=None,  x_pct=0, y_pct=0),
    ])
    counts = out.counts_by_room()
    assert counts["102"]["socket"] == 1
    assert counts["_unassigned"]["socket"] == 1


def test_canonical_types_cover_lt_construction_taxonomy():
    """Sanity check: the 14 canonical tags map to the contractor sub-counts
    Beržų's gap-analysis tracks (sockets/switches/lights/data/thermo/vent/
    water/drain). If we ever drop one, this test fails so the prompt and
    taxonomy stay in lockstep."""
    required = {"socket", "switch", "light_ceiling", "light_track", "vent_supply",
                "thermostat", "water_cold", "drain"}
    assert required.issubset(CANONICAL_TYPES)


def test_parse_rejects_non_dict():
    with pytest.raises(ValueError):
        parse_symbol_payload([])  # type: ignore[arg-type]

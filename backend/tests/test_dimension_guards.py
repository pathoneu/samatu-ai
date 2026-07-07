"""Unit tests for the dimension_extractor parse/filter guards.

Covers the post-filter rules (room number rejection, level markers, OOR
coords, duplicate ids) and the resilient JSON decoder (markdown fences,
leading prose, brace-balance fallback).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.vision.dimension_extractor import (
    parse_dimension_payload, _decode_response_json,
)


# ── Filter rules ──────────────────────────────────────────────────────────────
def test_room_number_with_zero_value_is_filtered():
    """Room labels like '102' often arrive as orientation=horizontal with
    value_mm=102 — far below the 50mm minimum and almost certainly a label.
    Use 0 here to test the value_mm<=0 branch directly."""
    payload = {"dimensions": [
        {"id": "d1", "text": "102", "value_mm": 0, "orientation": "horizontal",
         "x_pct": 0.5, "y_pct": 0.5},
        {"id": "d2", "text": "3150", "value_mm": 3150, "orientation": "horizontal",
         "x_pct": 0.3, "y_pct": 0.4},
    ]}
    out = parse_dimension_payload(payload)
    assert len(out.dimensions) == 1
    assert out.dimensions[0].id == "d2"
    assert "filtered" in out._meta
    assert out._meta["filtered"][0]["reason"] == "non_positive_value_mm"


def test_value_mm_out_of_range_filtered():
    """Sub-50mm (e.g. text was area "1m²" misread) and >100m values get
    filtered. (102 is intentionally NOT in this test — it's a plausible
    wall thickness; only position can disambiguate a 102 room number from a
    102mm thickness annotation, and that's the prompt's job, not the
    filter's.)"""
    payload = {"dimensions": [
        {"id": "d1", "text": "1", "value_mm": 1, "orientation": "horizontal",
         "x_pct": 0.5, "y_pct": 0.5},
        {"id": "d2", "text": "200000", "value_mm": 200000, "orientation": "horizontal",
         "x_pct": 0.3, "y_pct": 0.4},
        {"id": "d3", "text": "3150", "value_mm": 3150, "orientation": "horizontal",
         "x_pct": 0.5, "y_pct": 0.5},
    ]}
    out = parse_dimension_payload(payload)
    ids = {d.id for d in out.dimensions}
    assert ids == {"d3"}
    reasons = {f["reason"] for f in out._meta.get("filtered", [])}
    assert any("out_of_range" in r for r in reasons)


def test_level_marker_kept_when_orientation_is_level():
    """Elevation markers ('+0.000') have orientation='level' and may legitimately
    have value_mm=None or 0. They pass through the filter (the calculator
    can decide what to do with them)."""
    payload = {"dimensions": [
        {"id": "d1", "text": "+0,000", "value_mm": None, "orientation": "level",
         "x_pct": 0.5, "y_pct": 0.5},
    ]}
    out = parse_dimension_payload(payload)
    assert len(out.dimensions) == 1


def test_coords_out_of_range_filtered():
    payload = {"dimensions": [
        {"id": "d1", "text": "3150", "value_mm": 3150, "orientation": "horizontal",
         "x_pct": 1.5, "y_pct": 0.5},
        {"id": "d2", "text": "3150", "value_mm": 3150, "orientation": "horizontal",
         "x_pct": 0.5, "y_pct": -0.2},
        {"id": "d3", "text": "3150", "value_mm": 3150, "orientation": "horizontal",
         "x_pct": 0.5, "y_pct": 0.5},
    ]}
    out = parse_dimension_payload(payload)
    assert {d.id for d in out.dimensions} == {"d3"}


def test_duplicate_ids_first_wins():
    payload = {"dimensions": [
        {"id": "d1", "text": "3150", "value_mm": 3150, "orientation": "horizontal",
         "x_pct": 0.5, "y_pct": 0.5},
        {"id": "d1", "text": "9999", "value_mm": 9999, "orientation": "horizontal",
         "x_pct": 0.5, "y_pct": 0.5},
    ]}
    out = parse_dimension_payload(payload)
    assert len(out.dimensions) == 1
    assert out.dimensions[0].value_mm == 3150


# ── JSON decoder resilience ───────────────────────────────────────────────────
def test_decode_plain_json():
    assert _decode_response_json('{"dimensions": []}') == {"dimensions": []}


def test_decode_strips_markdown_code_fence():
    raw = "```json\n{\"dimensions\": [{\"id\": \"d1\"}]}\n```"
    out = _decode_response_json(raw)
    assert out["dimensions"][0]["id"] == "d1"


def test_decode_strips_trailing_fence():
    raw = "{\"x\": 1}\n```"
    # Plain JSON parse handles this if we strip fences. The brace fallback
    # also handles it. Either way we get the object.
    out = _decode_response_json(raw)
    assert out == {"x": 1}


def test_decode_brace_balance_fallback_on_leading_prose():
    """Model occasionally prefaces with prose; the brace-balance fallback
    recovers the first complete JSON object."""
    raw = 'Here is the dimension list:\n{"dimensions": [{"id": "d1"}]}'
    out = _decode_response_json(raw)
    assert out["dimensions"][0]["id"] == "d1"


def test_decode_brace_balance_skips_strings_with_braces():
    """A '{' inside a JSON string must not confuse the brace counter."""
    raw = '{"label": "value with {braces} inside", "ok": true}'
    out = _decode_response_json(raw)
    assert out["ok"] is True
    assert out["label"] == "value with {braces} inside"


def test_decode_empty_raises():
    with pytest.raises(ValueError):
        _decode_response_json("")


def test_decode_no_json_raises():
    with pytest.raises(ValueError):
        _decode_response_json("just prose, no json at all")

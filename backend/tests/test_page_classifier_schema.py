"""Tests for PageClassification schema extensions (Phase 1 T2).

Verifies `dalis` and `roof_type_hint` fields are exposed in the
dataclass, JSON schema, and parser. Wiring of `_extract_antspaudas_text`
into `classify_page` lives in T3 (separate test file).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from extractor.page_classifier import (  # noqa: E402
    Dalis,
    PageClassification,
    PageType,
    RoofTypeHint,
    _SCHEMA,
    parse_classification,
)


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------

def test_dalis_enum_has_seven_lt_codes_plus_unknown():
    """LT building-section codes per stogai V1 plan."""
    values = {d.value for d in Dalis}
    assert values == {"BD", "SP", "SA", "SK", "VVN", "ŠVOK", "E", "unknown"}


def test_roof_type_hint_enum_covers_phase_2_strategies():
    """Roof types Phase 2 strategies dispatch on (incl. unknown sentinel)."""
    values = {r.value for r in RoofTypeHint}
    assert values == {
        "dvislaitis",
        "keturslaitis",
        "vienslaitis",
        "mansardinis",
        "plokscias",
        "unknown",
    }


# ---------------------------------------------------------------------------
# Dataclass shape
# ---------------------------------------------------------------------------

def test_classification_accepts_optional_dalis_and_roof_hint():
    c = PageClassification(
        page_type=PageType.FLOOR_PLAN,
        confidence=0.92,
        dalis=Dalis.SA,
        roof_type_hint=RoofTypeHint.DVISLAITIS,
    )
    assert c.dalis is Dalis.SA
    assert c.roof_type_hint is RoofTypeHint.DVISLAITIS


def test_classification_defaults_new_fields_to_none():
    """Existing callers (image-only) must still construct without new args."""
    c = PageClassification(page_type=PageType.FLOOR_PLAN, confidence=0.9)
    assert c.dalis is None
    assert c.roof_type_hint is None
    assert c.top_2 is None


# ---------------------------------------------------------------------------
# JSON schema (sent to Haiku)
# ---------------------------------------------------------------------------

def test_json_schema_declares_dalis_field():
    """All 7 LT dalies + UNKNOWN sentinel. Anthropic structured-output
    rejects `["string","null"]` type arrays, so `"unknown"` is the
    in-band null."""
    assert "dalis" in _SCHEMA["properties"]
    enum_vals = _SCHEMA["properties"]["dalis"]["enum"]
    for code in ("BD", "SP", "SA", "SK", "VVN", "ŠVOK", "E", "unknown"):
        assert code in enum_vals
    assert _SCHEMA["properties"]["dalis"]["type"] == "string"


def test_json_schema_declares_roof_type_hint_field():
    assert "roof_type_hint" in _SCHEMA["properties"]
    enum_vals = _SCHEMA["properties"]["roof_type_hint"]["enum"]
    for rt in (
        "dvislaitis",
        "keturslaitis",
        "vienslaitis",
        "mansardinis",
        "plokscias",
        "unknown",
    ):
        assert rt in enum_vals
    assert _SCHEMA["properties"]["roof_type_hint"]["type"] == "string"


def test_new_fields_not_required():
    """Haiku must be allowed to return classifications without them."""
    required = _SCHEMA.get("required", [])
    assert "dalis" not in required
    assert "roof_type_hint" not in required


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def test_parser_handles_payload_with_new_fields():
    payload = {
        "page_type": "section",
        "confidence": 0.88,
        "top_2": None,
        "dalis": "SA",
        "roof_type_hint": "keturslaitis",
    }
    c = parse_classification(payload)
    assert c.page_type is PageType.SECTION
    assert c.dalis is Dalis.SA
    assert c.roof_type_hint is RoofTypeHint.KETURSLAITIS


def test_parser_handles_payload_missing_new_fields():
    """Legacy Haiku response (pre-T2) must still parse."""
    payload = {"page_type": "floor_plan", "confidence": 0.9}
    c = parse_classification(payload)
    assert c.dalis is None
    assert c.roof_type_hint is None


def test_parser_handles_explicit_nulls():
    payload = {
        "page_type": "floor_plan",
        "confidence": 0.9,
        "dalis": None,
        "roof_type_hint": None,
    }
    c = parse_classification(payload)
    assert c.dalis is None
    assert c.roof_type_hint is None


def test_parser_handles_unknown_sentinel_strings():
    """Haiku returning literal `"unknown"` maps to the enum's UNKNOWN, not None."""
    payload = {
        "page_type": "unknown",
        "confidence": 0.4,
        "dalis": "unknown",
        "roof_type_hint": "unknown",
    }
    c = parse_classification(payload)
    assert c.dalis is Dalis.UNKNOWN
    assert c.roof_type_hint is RoofTypeHint.UNKNOWN


def test_parser_rejects_invalid_dalis():
    payload = {"page_type": "section", "confidence": 0.9, "dalis": "XYZ"}
    with pytest.raises(ValueError):
        parse_classification(payload)

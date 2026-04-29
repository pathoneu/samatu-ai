"""Tests for plyteliu_specifikacija pdfplumber-based tile spec reader."""
from __future__ import annotations

import pytest
from extractor.plyteliu_specifikacija import (
    TILE_SIZE_PATTERN,
    _classify_where,
    _detect_format,
    _detect_brand,
    _is_plausible,
    _has_tile_anchor,
)


def test_tile_size_pattern_matches_unicode_x():
    """Pattern must match standard `1200×1200×6` form (Unicode multiplication
    sign). Most LT CAD-export PDFs use this character."""
    m = TILE_SIZE_PATTERN.search("Plytelės 1200×1200×6 mm")
    assert m is not None
    assert m.group(1) == "1200"
    assert m.group(2) == "1200"
    assert m.group(3) == "6"


def test_tile_size_pattern_matches_ascii_x():
    """ASCII `x` form also accepted (some PDFs use it)."""
    m = TILE_SIZE_PATTERN.search("Plytelės 600x300 mm")
    assert m is not None
    assert m.group(1) == "600"
    assert m.group(2) == "300"
    assert m.group(3) is None


def test_tile_size_pattern_handles_whitespace():
    m = TILE_SIZE_PATTERN.search("PLYTELĖ 1200 × 600")
    assert m is not None
    assert (m.group(1), m.group(2)) == ("1200", "600")


def test_plausibility_filter_rejects_door_size():
    """Door dimensions (e.g., 2000×800) shouldn't pass — height >1500."""
    # Width 800, height 2000 — 2000 is out of plausible H range
    assert not _is_plausible(800, 2000, None)
    # Width 50, height 50 — too small (mosaic floor)
    assert _is_plausible(50, 50, None)
    # Width 1200, thickness 30 — over 20mm rejected
    assert not _is_plausible(1200, 1200, 30)


def test_classify_where_picks_vonia_over_others():
    assert _classify_where("VONIOS PLYTELĖS: 1200×1200") == "vonia"
    assert _classify_where("Vonios kambario sienos") == "vonia"


def test_classify_where_falls_back_to_kita():
    """No room keyword → 'kita' (other) fallback."""
    assert _classify_where("Visa apdaila") == "kita"


def test_detect_format_recognizes_didziaformate():
    assert _detect_format("DIDŽIAFORMATĖS PLYTELĖS 1200×1200") == "Didžiaformatė"
    assert _detect_format("plain 600×600 tiles") is None


def test_detect_brand_finds_known_brand():
    assert _detect_brand("Atlas Concorde Boost Pro Steel 1200×1200") == "Atlas Concorde"
    assert _detect_brand("Cersanit Maraska") == "Cersanit"
    assert _detect_brand("unknown brand mention") is None


def test_has_tile_anchor_detects_keywords():
    assert _has_tile_anchor("PLYTELĖS specifikacija")
    assert _has_tile_anchor("Plyt. zonos")
    assert _has_tile_anchor("Keramines plyteles")
    # No tile keyword → returns False (avoids matching door/window dims)
    assert not _has_tile_anchor("Durų matmenys 800×2000")


def test_extract_returns_empty_on_garbage_pdf():
    """Soft-fail: invalid PDF bytes → empty result with _error in _meta, no
    crash."""
    from extractor.plyteliu_specifikacija import extract_plyteliu_specifikacija
    result = extract_plyteliu_specifikacija(b"not a pdf")
    assert result["tile_specs"] == []
    assert "_meta" in result
    # error logged but not raised
    assert "error" in result["_meta"] or result["_meta"]["pages_scanned"] == 0

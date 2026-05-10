"""Week 4 Task 4.2 — Q-level bundling tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from extractor.bundling import (  # noqa: E402
    collapse_to_bundled,
    expand_to_q_level,
    BUNDLE_GLAISTYMAS_DAZYMAS,
)


def test_default_collapses_glaistymas_dazymas_into_one_line():
    raw = {"lines": [
        {"code": "glaistymas_q3_m2", "quantity": 200, "unit_price_eur_be_pvm": 9},
        {"code": "dazymas_sienos_m2", "quantity": 200, "unit_price_eur_be_pvm": 5},
        {"code": "dazymas_lubos_m2", "quantity": 80, "unit_price_eur_be_pvm": 4},
        {"code": "gruntavimas_m2", "quantity": 280, "unit_price_eur_be_pvm": 1},
    ]}
    out = collapse_to_bundled(raw, mode="default_bundled")
    bundle = next(l for l in out["lines"] if l["code"] == BUNDLE_GLAISTYMAS_DAZYMAS)
    # Bundle quantity sums all four member lines.
    assert bundle["quantity"] == 760
    assert bundle["unit_price_eur_be_pvm"] == 14
    # Member lines no longer present.
    survivor_codes = {l["code"] for l in out["lines"]}
    assert "glaistymas_q3_m2" not in survivor_codes


def test_advanced_mode_keeps_q_level_split():
    raw = {"lines": [
        {"code": "glaistymas_q3_m2", "quantity": 200, "unit_price_eur_be_pvm": 9},
        {"code": "dazymas_sienos_m2", "quantity": 200, "unit_price_eur_be_pvm": 5},
    ]}
    out = collapse_to_bundled(raw, mode="advanced_split")
    codes = {l["code"] for l in out["lines"]}
    assert "glaistymas_q3_m2" in codes
    assert "dazymas_sienos_m2" in codes
    assert BUNDLE_GLAISTYMAS_DAZYMAS not in codes


def test_invalid_mode_raises():
    with pytest.raises(ValueError):
        collapse_to_bundled({"lines": []}, mode="bogus")


def test_collapse_preserves_non_member_lines():
    raw = {"lines": [
        {"code": "glaistymas_q2_m2", "quantity": 100, "unit_price_eur_be_pvm": 9},
        {"code": "grindjuostes_m", "quantity": 60, "unit_price_eur_be_pvm": 5},
        {"code": "hidroizoliacija_m2", "quantity": 8, "unit_price_eur_be_pvm": 10},
    ]}
    out = collapse_to_bundled(raw, mode="default_bundled")
    codes = {l["code"] for l in out["lines"]}
    assert "grindjuostes_m" in codes
    assert "hidroizoliacija_m2" in codes
    assert BUNDLE_GLAISTYMAS_DAZYMAS in codes


def test_q4_advanced_adds_sanding_premium():
    out = expand_to_q_level(bundled_qty_m2=200, q_level="Q4")
    codes = {l["code"] for l in out}
    assert "glaistas_kg" in codes
    assert "slifavimas_m2" in codes


def test_q1_does_not_add_sanding():
    out = expand_to_q_level(bundled_qty_m2=200, q_level="Q1")
    codes = {l["code"] for l in out}
    assert "glaistas_kg" in codes
    assert "slifavimas_m2" not in codes


def test_unknown_q_level_returns_empty():
    assert expand_to_q_level(100, "Q5") == []


def test_collapse_idempotent():
    """Running collapse twice should produce the same output as once."""
    raw = {"lines": [
        {"code": "glaistymas_q3_m2", "quantity": 200, "unit_price_eur_be_pvm": 9},
        {"code": "grindjuostes_m", "quantity": 60, "unit_price_eur_be_pvm": 5},
    ]}
    once = collapse_to_bundled(raw, mode="default_bundled")
    twice = collapse_to_bundled(once, mode="default_bundled")
    # Bundle quantity stable across re-collapsing (no member lines left in
    # `once` to add into the bundle on the second pass).
    once_bundle = next(l for l in once["lines"] if l["code"] == BUNDLE_GLAISTYMAS_DAZYMAS)
    twice_bundle = next(l for l in twice["lines"] if l["code"] == BUNDLE_GLAISTYMAS_DAZYMAS)
    assert once_bundle["quantity"] == twice_bundle["quantity"]

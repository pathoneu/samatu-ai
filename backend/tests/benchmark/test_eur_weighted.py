"""Week 4 Task 4.4 — EUR-weighted error metric."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from extractor.benchmark.eur_weighted import (  # noqa: E402
    eur_weighted_error,
    per_line_eur_impact,
    load_prices,
)


@pytest.fixture
def cfg():
    return load_prices()


def test_perfect_match_zero_error(cfg):
    pred = {"glaistymas_dazymas_bundle": 200}
    gt = {"glaistymas_dazymas_bundle": 200}
    assert eur_weighted_error(pred, gt, cfg) == 0.0


def test_10_percent_underestimate_on_bundled_line(cfg):
    pred = {"glaistymas_dazymas_bundle": 180}
    gt = {"glaistymas_dazymas_bundle": 200}
    err = eur_weighted_error(pred, gt, cfg)
    # Single-line case: error = 20 × 14 / (200 × 14) = 0.10
    assert 0.099 <= err <= 0.101


def test_top_5_lines_dominate_other(cfg):
    """Glaistymas error swamps silikonas error per R4 weights."""
    pred = {"glaistymas_dazymas_bundle": 220, "silikonas_lm": 100}
    gt = {"glaistymas_dazymas_bundle": 200, "silikonas_lm": 50}
    err = eur_weighted_error(pred, gt, cfg)
    # Reasonable error band given R4 weights (0.30 vs 0.20).
    assert 0.05 < err < 0.20


def test_per_line_impact_sorts_by_eur_magnitude(cfg):
    pred = {
        "glaistymas_dazymas_bundle": 250,   # +50 m² × 14 € = 700 €
        "silikonas_lm": 100,                 # +50 m × 2.5 € = 125 €
        "grindjuostes_m": 60,                # 0 delta
    }
    gt = {"glaistymas_dazymas_bundle": 200, "silikonas_lm": 50, "grindjuostes_m": 60}
    rows = per_line_eur_impact(pred, gt, cfg)
    # Sorted by abs_eur_impact descending.
    assert rows[0]["code"] == "glaistymas_dazymas_bundle"
    assert rows[0]["abs_eur_impact"] == 700.0
    assert rows[1]["code"] == "silikonas_lm"
    assert rows[1]["abs_eur_impact"] == 125.0


def test_unknown_codes_use_other_weight(cfg):
    """A line code not listed in `weights` falls back to `_other` weight."""
    pred = {"some_obscure_line": 10}
    gt = {"some_obscure_line": 20}
    rows = per_line_eur_impact(pred, gt, cfg)
    obscure = next(r for r in rows if r["code"] == "some_obscure_line")
    # Fallback weight is `_other` from cfg
    assert obscure["weight"] == cfg["weights"]["_other"]


def test_zero_gt_returns_zero_error_not_division_by_zero(cfg):
    """When GT is empty, metric is undefined — return 0 not NaN/exception."""
    err = eur_weighted_error({"x": 5}, {}, cfg)
    assert err == 0.0


def test_real_lt_prices_loaded(cfg):
    assert cfg["currency"] == "EUR"
    assert cfg["vat_mode"] == "be_pvm"
    assert cfg["weights"]["glaistymas_dazymas_bundle"] == 0.30
    assert cfg["unit_prices"]["glaistymas_dazymas_bundle"] == 14.0

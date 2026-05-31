"""Unit tests for eval_harness.py.

These tests don't touch Vision: they exercise the GT-inputs path and the metric
math against the Beržų truth file checked into the repo.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_harness():
    """Load eval_harness.py as a module without installing it."""
    spec = importlib.util.spec_from_file_location(
        "eval_harness", REPO_ROOT / "eval_harness.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def harness():
    return _load_harness()


@pytest.fixture(scope="module")
def berzas_truth(harness):
    return harness._load_truth("berzas")


def test_truth_file_has_required_keys(berzas_truth):
    assert "gt_dimensions" in berzas_truth
    assert "gt_totals" in berzas_truth
    assert "gt_per_room" in berzas_truth
    assert len(berzas_truth["gt_dimensions"]) >= 10, "expect ≥10 rooms for Beržų"


def test_truth_contractor_invariants(berzas_truth):
    """Cross-checks from contractor-notes-verbatim.md.

    iki_3m + virš_3m == combined (584.81); walls_paint + ceiling_paint == combined
    (within ~0.5 rounding because contractor items 16+17 only contain non-garage
    finished rooms while walls_paint_total includes the garage 31.45 m²)."""
    g = berzas_truth["gt_totals"]
    iki = g["dazymo_iki_3m_m2"]["value"]
    virs = g["dazymo_virs_3m_m2"]["value"]
    combined = g["dazymo_walls_plus_ceilings_combined_m2"]["value"]
    assert abs((iki + virs) - combined) < 0.05, f"{iki}+{virs} != {combined}"


def test_use_gt_inputs_runs_and_emits_santrauka(harness, berzas_truth):
    parsed = harness.run_pipeline_use_gt_inputs(berzas_truth)
    assert parsed.get("patalpos"), "patalpos must be populated"
    sant = parsed.get("santrauka") or {}
    assert "dazymo_plotas_total_m2" in sant
    assert sant["dazymo_plotas_total_m2"] > 0, "paint total should be > 0"


def test_metric_evaluation_returns_status_per_truth_key(harness, berzas_truth):
    parsed = harness.run_pipeline_use_gt_inputs(berzas_truth)
    results = harness.evaluate(parsed, berzas_truth)
    keys = {r.truth_key for r in results}
    # Headline tier must be evaluated against truth
    assert "dazymo_walls_plus_ceilings_combined_m2" in keys
    assert "led_nisos_m" in keys
    assert "floor_total_m2" in keys


def test_floor_area_matches_truth_within_one_percent(harness, berzas_truth):
    """Floor area is the easiest invariant: sum of plotas_m2 should match contractor
    bendras_plotas 165.61 m² within 1%."""
    parsed = harness.run_pipeline_use_gt_inputs(berzas_truth)
    results = harness.evaluate(parsed, berzas_truth)
    floor = [r for r in results if r.truth_key == "floor_total_m2"][0]
    assert floor.pct_error is not None
    assert abs(floor.pct_error) < 1.0, f"floor area drift {floor.pct_error}%"


def test_summary_shape(harness, berzas_truth):
    parsed = harness.run_pipeline_use_gt_inputs(berzas_truth)
    results = harness.evaluate(parsed, berzas_truth)
    s = harness._summarize(results)
    for k in (
        "headline_mae_pct", "headline_max_pct",
        "headline_ok", "headline_total", "category_mae_pct",
    ):
        assert k in s
    assert s["headline_total"] >= 4

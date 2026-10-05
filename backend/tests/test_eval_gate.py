"""eval_harness.py --gate / --accept-baseline (audit 2026-09-29, testing-eval-4).

The old exit code was 1 whenever any project's worst metric was over 2 %, which
is always, so it meant nothing. The gate compares against an accepted baseline
instead. These tests pin the comparison with small made-up numbers.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def harness():
    spec = importlib.util.spec_from_file_location("eval_harness_gate", REPO_ROOT / "eval_harness.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


_BASE = {"objektas_a": {"MAE": 3.0, "Sienų dažomas plotas": 11.0},
         "objektas_b": {"MAE": 16.0}}


def _cmp(harness, current, **kw):
    kw.setdefault("tolerance", 0.25)
    return harness.compare_to_baseline(_BASE, current, **kw)


def test_equal_passes(harness):
    regressions, improvements = _cmp(harness, json.loads(json.dumps(_BASE)))
    assert regressions == [] and improvements == []


def test_worse_within_tolerance_passes(harness):
    cur = {"objektas_a": {"MAE": 3.25, "Sienų dažomas plotas": 11.1},
           "objektas_b": {"MAE": 16.0}}
    regressions, _ = _cmp(harness, cur)
    assert regressions == []


def test_worse_beyond_tolerance_fails_and_names_the_metric(harness):
    cur = {"objektas_a": {"MAE": 3.0, "Sienų dažomas plotas": 11.4},
           "objektas_b": {"MAE": 16.0}}
    regressions, _ = _cmp(harness, cur)
    assert len(regressions) == 1
    line = regressions[0]
    assert "objektas_a" in line and "Sienų dažomas plotas" in line
    assert "11.000" in line and "11.400" in line


def test_missing_project_fails(harness):
    regressions, _ = _cmp(harness, {"objektas_a": dict(_BASE["objektas_a"])})
    assert len(regressions) == 1 and "objektas_b" in regressions[0]


def test_missing_metric_fails(harness):
    cur = {"objektas_a": {"MAE": 3.0}, "objektas_b": {"MAE": 16.0}}
    regressions, _ = _cmp(harness, cur)
    assert len(regressions) == 1 and "Sienų dažomas plotas" in regressions[0]


def test_improvement_passes_and_is_reported(harness):
    cur = {"objektas_a": {"MAE": 2.0, "Sienų dažomas plotas": 11.0},
           "objektas_b": {"MAE": 16.0}, "objektas_z": {"MAE": 50.0}}   # new project: not a failure
    regressions, improvements = _cmp(harness, cur)
    assert regressions == []
    assert len(improvements) == 1 and "objektas_a" in improvements[0] and "MAE" in improvements[0]


def test_rows_share_higher_is_better(harness):
    base = {"objektas_a": {"within_10_share": 30.0}}
    worse = harness.compare_to_baseline(base, {"objektas_a": {"within_10_share": 28.9}},
                                        tolerance=1.0, higher_is_better=True)
    within = harness.compare_to_baseline(base, {"objektas_a": {"within_10_share": 29.0}},
                                         tolerance=1.0, higher_is_better=True)
    better = harness.compare_to_baseline(base, {"objektas_a": {"within_10_share": 35.0}},
                                         tolerance=1.0, higher_is_better=True)
    assert len(worse[0]) == 1 and within[0] == [] and better[0] == [] and len(better[1]) == 1


def test_accept_writes_codenames_only_sorted_and_keeps_other_section(harness, tmp_path):
    path = tmp_path / "eval_baseline.json"
    path.write_text(json.dumps({"rows": {"objektas_a": {"within_10_share": 30.0}}}))
    harness.accept_baseline("totals", {"objektas_b": {"MAE": 16.0}, "objektas_a": {"MAE": 3.0}},
                            path=path)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    assert data["rows"] == {"objektas_a": {"within_10_share": 30.0}}
    assert list(data["totals"]) == ["objektas_a", "objektas_b"]
    assert text == json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_accept_refuses_an_empty_run(harness, tmp_path):
    path = tmp_path / "eval_baseline.json"
    assert harness.accept_baseline("totals", {}, path=path) == 1
    assert not path.exists()


def test_gate_numbers_keep_codenames_only(harness):
    summary = [
        {"slug": "objektas_a", "status": "ok", "mae_pct": 3.06,
         "metrics": [{"label": "Sienų dažomas plotas", "pct_error": -11.2281}]},
        {"slug": "tikras_pavadinimas", "status": "ok", "mae_pct": 1.0, "metrics": []},
        {"slug": "objektas_x", "status": "no_ai_side", "metrics": []},
    ]
    assert harness.gate_numbers_totals(summary) == {
        "objektas_a": {"legacy MAE": 3.06, "Sienų dažomas plotas": 11.228}}


def test_gate_numbers_lead_with_the_billed_lines(harness):
    """2026-10-05 (testing-eval-2): the headline is his billed lines. A copied
    family is in no average but is still gated — a copy that stops matching is
    a regression; a family whose units cannot be summed has no number."""
    summary = [{
        "slug": "objektas_a", "status": "ok", "mae_pct": 3.06, "billed_mae_pct": 6.208,
        "billed_families": [
            {"family": "Dažymas (sienos+lubos)", "status": "measured", "pct_error": -1.7478},
            {"family": "GKP lubos", "status": "copied", "pct_error": 0.0},
            {"family": "Dažymo kampai", "status": "not_produced", "pct_error": -100.0},
            {"family": "Plytelės", "status": "unit_mismatch", "pct_error": None}],
        "metrics": [{"label": "Lubų dažomas plotas", "pct_error": 0.0}]}]
    assert harness.gate_numbers_totals(summary) == {"objektas_a": {
        "billed MAE": 6.208,
        "billed · Dažymas (sienos+lubos)": 1.748,
        "billed · GKP lubos": 0.0,
        "billed · Dažymo kampai": 100.0,
        "legacy MAE": 3.06,
        "Lubų dažomas plotas": 0.0}}


def test_gate_exit_codes(harness, tmp_path, capsys):
    path = tmp_path / "eval_baseline.json"
    assert harness.run_gate("totals", _BASE, path=path) == 1          # no baseline yet
    harness.accept_baseline("totals", _BASE, path=path)
    assert harness.run_gate("totals", _BASE, path=path) == 0
    worse = {"objektas_a": {"MAE": 4.0, "Sienų dažomas plotas": 11.0}, "objektas_b": {"MAE": 16.0}}
    assert harness.run_gate("totals", worse, path=path) == 1
    out = capsys.readouterr().out
    assert "objektas_a" in out and "MAE" in out

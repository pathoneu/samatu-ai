"""Unit tests for calibration_learner — promotion gating + outlier detection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.calibration_learner import analyze, render_report, PROMOTION_RULES


def _write(root: Path, project_id: str, factors: dict[str, dict]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    record = {
        "project_id": project_id,
        "factors": {k: {"applied": True, "label": k, "unit": "m²", **v}
                    for k, v in factors.items()},
        "perimeter_correction_factor": None,
        "updated_at": 0,
        "schema_version": 2,
    }
    (root / f"{project_id}.json").write_text(json.dumps(record), encoding="utf-8")


def test_no_calibrations(tmp_path):
    out = analyze(root=tmp_path)
    assert out["n_projects"] == 0
    assert out["metrics"] == []
    assert out["candidates"] == []


def test_single_project_is_not_a_promotion_candidate(tmp_path):
    _write(tmp_path, "p1", {
        "dazymo_plotas_m2": {"factor": 1.10, "ai_value": 100, "user_value": 110},
    })
    out = analyze(root=tmp_path)
    assert out["n_projects"] == 1
    [m] = out["metrics"]
    assert m["n_projects"] == 1
    assert m["promotion_candidate"] is False
    assert "only 1 project" in m["promotion_reason"]


def test_three_consistent_projects_become_promotion_candidate(tmp_path):
    for pid, f in [("p1", 1.011), ("p2", 1.009), ("p3", 1.012)]:
        _write(tmp_path, pid, {
            "dazymo_plotas_m2": {"factor": f, "ai_value": 100, "user_value": f*100},
        })
    out = analyze(root=tmp_path)
    [m] = out["metrics"]
    assert m["n_projects"] == 3
    assert m["promotion_candidate"] is True
    assert m["direction_consistency"] == 1.0
    assert m["iqr"] <= PROMOTION_RULES["max_iqr"]
    assert 1.009 <= m["median"] <= 1.012


def test_three_inconsistent_directions_blocks_promotion(tmp_path):
    for pid, f in [("p1", 1.05), ("p2", 0.97), ("p3", 1.02)]:
        _write(tmp_path, pid, {
            "led_nisos_m": {"factor": f, "ai_value": 40, "user_value": f*40},
        })
    out = analyze(root=tmp_path)
    [m] = out["metrics"]
    assert m["promotion_candidate"] is False
    assert "direction inconsistency" in m["promotion_reason"]


def test_wide_iqr_blocks_promotion(tmp_path):
    for pid, f in [("p1", 1.01), ("p2", 1.10), ("p3", 1.20), ("p4", 1.30)]:
        _write(tmp_path, pid, {
            "kampu_metrai_m": {"factor": f, "ai_value": 50, "user_value": f*50},
        })
    out = analyze(root=tmp_path)
    [m] = out["metrics"]
    assert m["n_projects"] == 4
    assert m["direction_consistency"] == 1.0   # all same direction
    assert m["iqr"] > PROMOTION_RULES["max_iqr"]
    assert m["promotion_candidate"] is False
    assert "IQR" in m["promotion_reason"]


def test_median_near_one_blocks_promotion(tmp_path):
    """Even with 5 consistent projects, if the median shift is <0.5% there
    is no meaningful systematic bias to promote."""
    for pid, f in [("p1", 1.001), ("p2", 1.002), ("p3", 1.003),
                   ("p4", 1.001), ("p5", 1.002)]:
        _write(tmp_path, pid, {
            "dazymo_plotas_m2": {"factor": f, "ai_value": 100, "user_value": f*100},
        })
    out = analyze(root=tmp_path)
    [m] = out["metrics"]
    assert m["promotion_candidate"] is False
    assert "within ±0.5% of 1.0" in m["promotion_reason"]


def test_outlier_detected(tmp_path):
    for pid, f in [("p1", 1.01), ("p2", 1.02), ("p3", 1.01), ("p4", 1.50)]:
        _write(tmp_path, pid, {
            "dazymo_plotas_m2": {"factor": f, "ai_value": 100, "user_value": f*100},
        })
    out = analyze(root=tmp_path)
    [m] = out["metrics"]
    assert any(o["project_id"] == "p4" for o in m["outliers"])


def test_render_report_runs_without_exception(tmp_path):
    _write(tmp_path, "p1", {
        "dazymo_plotas_m2": {"factor": 1.01, "ai_value": 100, "user_value": 101},
    })
    out = analyze(root=tmp_path)
    txt = render_report(out)
    assert "Calibration Learner" in txt
    assert "dazymo_plotas_m2" in txt or "Dažymo" in txt or "promotion" in txt


def test_unapplied_factors_excluded(tmp_path):
    record = {
        "project_id": "p1",
        "factors": {
            "metric_a": {"applied": True,  "label": "a", "unit": "m²", "factor": 1.01,
                         "ai_value": 100, "user_value": 101},
            "metric_b": {"applied": False, "label": "b", "unit": "m²", "factor": None,
                         "ai_value": 0,   "user_value": 0, "reason": "ai_value_zero"},
        },
        "perimeter_correction_factor": None,
        "updated_at": 0,
        "schema_version": 2,
    }
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "p1.json").write_text(json.dumps(record), encoding="utf-8")
    out = analyze(root=tmp_path)
    metric_keys = {m["metric"] for m in out["metrics"]}
    assert metric_keys == {"metric_a"}

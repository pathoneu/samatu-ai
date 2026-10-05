"""eval_harness --track-drift: the drift row records the headlines that exist
(2026-10-05).

`_append_drift_row` read `summary["mae_pct"]`, a key `_summarize` never writes,
so every row of eval_runs/drift.jsonl logged `"mae_pct": null` — the one number
a drift log is for. It now records the legacy headline `_summarize` computes
and his billed lines when the project has a sąmata. The log is written to a
temporary directory here; the repository's eval_runs/ is never touched.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def eh():
    spec = importlib.util.spec_from_file_location("eval_harness_drift", REPO_ROOT / "eval_harness.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness_drift"] = mod
    spec.loader.exec_module(mod)
    return mod


def _metric(eh, label, actual, truth, tier="headline"):
    pct = round((actual - truth) / truth * 100, 3)
    return eh.MetricResult(truth_key=label, label=label, unit="m²", tier=tier, truth_value=truth,
                           truth_confidence="ok", actual_value=actual, abs_error=round(actual - truth, 3),
                           pct_error=pct, status="warn")


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_the_row_carries_the_legacy_and_billed_headlines(eh, tmp_path, monkeypatch):
    monkeypatch.setattr(eh, "EVAL_RUNS_ROOT", tmp_path)
    results = [_metric(eh, "Walls", 110.0, 100.0), _metric(eh, "Ceilings", 95.0, 100.0),
               _metric(eh, "Corners", 130.0, 100.0, tier="category")]
    summary = eh._summarize(results)
    with contextlib.redirect_stdout(io.StringIO()):
        eh._append_drift_row("objektas_x", "replay", summary, results,
                             billed={"billed_mae_pct": 12.5, "billed_scored": 4, "billed_families": []})
        eh._append_drift_row("objektas_x", "replay", summary, results)          # no sąmata to score
    first, second = _rows(tmp_path / "drift.jsonl")
    assert "mae_pct" not in first, "the key _summarize never wrote is gone"
    assert first["legacy_mae_pct"] == pytest.approx(7.5) == summary["headline_mae_pct"]
    assert first["legacy_max_pct"] == pytest.approx(10.0)
    assert first["category_mae_pct"] == pytest.approx(30.0)
    assert (first["billed_mae_pct"], first["billed_scored"]) == (12.5, 4)
    assert first["metrics"] == {"Walls": 10.0, "Ceilings": -5.0}
    assert first["project_id"] == "objektas_x" and first["mode"] == "replay" and first["git_sha"]
    assert second["legacy_mae_pct"] == pytest.approx(7.5)
    assert (second["billed_mae_pct"], second["billed_scored"]) == (None, None)


def test_run_one_logs_numbers_not_nulls(eh, tmp_path, monkeypatch):
    """The real single-project path on tracked files only: objektas_a's cached
    extract (`--replay --track-drift`) logs both headlines as numbers — the
    legacy one exactly as the run saves it. Fed the hand-entered rooms
    (`--use-gt-inputs`) the engine builds no rows, so there are no billed lines
    to score: that row logs the legacy headline and a null billed one."""
    monkeypatch.setattr(eh, "EVAL_RUNS_ROOT", tmp_path)
    with contextlib.redirect_stdout(io.StringIO()):
        eh.run_one("objektas_a", "replay", track_drift=True)
        eh.run_one("objektas_a", "use_gt_inputs", track_drift=True)
    replay, gt_inputs = _rows(tmp_path / "drift.jsonl")
    (results_json,) = tmp_path.glob("*_objektas_a_replay/results.json")
    saved = json.loads(results_json.read_text(encoding="utf-8"))["summary"]
    assert isinstance(replay["legacy_mae_pct"], float) and replay["legacy_mae_pct"] == saved["headline_mae_pct"]
    assert isinstance(replay["billed_mae_pct"], float) and replay["billed_scored"] >= 1
    assert replay["metrics"]
    assert isinstance(gt_inputs["legacy_mae_pct"], float)
    assert (gt_inputs["billed_mae_pct"], gt_inputs["billed_scored"]) == (None, None)

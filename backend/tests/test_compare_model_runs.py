"""W1.2: compare_model_runs.py — stable markdown from synthetic result JSONs,
plus the eval_harness --model guard rails (fresh-vision-only + MODEL_OVERRIDE).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cmr():
    return _load_script("compare_model_runs",
                        REPO_ROOT / "scripts" / "compare_model_runs.py")


def _metric(key, label, truth, actual, pct, unit="m²", status="ok"):
    return {"truth_key": key, "label": label, "unit": unit, "tier": "headline",
            "truth_value": truth, "truth_confidence": "high",
            "actual_value": actual,
            "abs_error": (None if actual is None or truth is None
                          else round(abs(actual - truth), 2)),
            "pct_error": pct, "status": status}


def _run(project, model, actual_paint, pct_paint, tokens_in, cost_eur,
         wall_s, readers=None):
    raw_meta = {"model": model, "input_tokens": tokens_in,
                "output_tokens": 8000, "cache_read_tokens": 100_000,
                "cache_write_tokens": 20_000}
    raw_meta.update(readers or {})
    return {
        "project": project, "mode": "vision", "model": model,
        "summary": {"n_ok": 1},
        "meta_rollup": {"model": model, "input_tokens": tokens_in,
                        "output_tokens": 8000, "cache_read_tokens": 100_000,
                        "cache_write_tokens": 20_000,
                        "cost_usd": round(cost_eur / 0.93, 4),
                        "cost_eur": cost_eur, "pricing_note": None,
                        "wall_time_s": wall_s, "raw_meta": raw_meta},
        "metrics": [
            _metric("walls_paint_total_m2", "Sienų dažomas plotas",
                    419.92, actual_paint, pct_paint),
            _metric("led_nisos_m", "LED nišų ilgis", 42.3, 40.0,
                    -5.44, unit="m", status="warn"),
        ],
        "per_room": [],
    }


@pytest.fixture()
def synthetic_files(tmp_path):
    a1 = _run("berzas", "claude-opus-4-8", 431.5, 2.76, 250_000, 1.85, 310.0,
              readers={"doors_elapsed_s": 21.0, "apdailos_elapsed_s": 33.5})
    a2 = _run("ciurliu", "claude-opus-4-8", 300.0, -3.10, 180_000, 1.40, 250.0)
    b1 = _run("berzas", "claude-fable-5", 424.0, 0.97, 260_000, 3.90, 780.0,
              readers={"doors_elapsed_s": 55.0, "apdailos_elapsed_s": 71.2})
    b2 = _run("ciurliu", "claude-fable-5", 305.5, -1.32, 190_000, 3.05, 640.0)
    paths = {}
    for name, data in (("a1", a1), ("a2", a2), ("b1", b1), ("b2", b2)):
        p = tmp_path / f"{name}_results.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        paths[name] = p
    return paths


def test_report_contains_per_project_metric_rows(cmr, synthetic_files):
    report = cmr.build_report(
        [json.loads(synthetic_files["a1"].read_text()),
         json.loads(synthetic_files["a2"].read_text())],
        [json.loads(synthetic_files["b1"].read_text()),
         json.loads(synthetic_files["b2"].read_text())],
    )
    assert "# Model comparison — claude-opus-4-8 vs claude-fable-5" in report
    assert "## berzas" in report and "## ciurliu" in report
    # truth, A, B, pct A, pct B on one row
    assert ("| Sienų dažomas plotas | m² | 419.92 | 431.50 | 424.00 "
            "| +2.76% | +0.97% |") in report


def test_report_mae_and_totals(cmr, synthetic_files):
    report = cmr.build_report(
        [json.loads(synthetic_files["a1"].read_text()),
         json.loads(synthetic_files["a2"].read_text())],
        [json.loads(synthetic_files["b1"].read_text()),
         json.loads(synthetic_files["b2"].read_text())],
    )
    # per-project MAE: berzas A = mean(2.76, 5.44) = 4.10; B = mean(0.97, 5.44) = 3.21
    # (the synthetic LED metric carries pct -5.44 on BOTH sides)
    assert "| berzas | 4.10 | 3.21 |" in report
    # totals: tokens summed across projects
    assert "| input_tokens | 430,000 | 450,000 |" in report
    # € cost summed: 1.85+1.40 vs 3.90+3.05
    assert "| cost_eur | €3.2500 | €6.9500 |" in report
    assert "| wall time (min) | 9.3 | 23.7 |" in report


def test_report_per_reader_breakdown(cmr, synthetic_files):
    report = cmr.build_report(
        [json.loads(synthetic_files["a1"].read_text())],
        [json.loads(synthetic_files["b1"].read_text())],
    )
    assert "## Per-reader elapsed" in report
    assert "| doors | 21.0 | 55.0 |" in report
    assert "| apdailos | 33.5 | 71.2 |" in report


def test_report_is_stable(cmr, synthetic_files):
    """Same inputs → byte-identical output (no timestamps/randomness)."""
    args = ([json.loads(synthetic_files["a1"].read_text())],
            [json.loads(synthetic_files["b1"].read_text())])
    assert cmr.build_report(*args) == cmr.build_report(*args)


def test_cli_two_file_shorthand_writes_out(cmr, synthetic_files, tmp_path, capsys):
    out = tmp_path / "report.md"
    rc = cmr.main([str(synthetic_files["a1"]), str(synthetic_files["b1"]),
                   "-o", str(out)])
    assert rc == 0
    assert out.exists()
    assert "# Model comparison" in out.read_text(encoding="utf-8")


def test_cli_rejects_wrong_arity(cmr, synthetic_files):
    with pytest.raises(SystemExit):
        cmr.main([str(synthetic_files["a1"])])


def test_script_has_no_api_imports():
    """Pure post-processing — must never import anthropic or the backend."""
    src = (REPO_ROOT / "scripts" / "compare_model_runs.py").read_text()
    assert "anthropic" not in src
    assert "vision_call" not in src


# ── eval_harness --model guard rails ─────────────────────────────────────────

@pytest.fixture(scope="module")
def harness():
    return _load_script("eval_harness_w12", REPO_ROOT / "eval_harness.py")


def test_harness_model_flag_requires_vision(harness, monkeypatch):
    """--model with a cache-reading mode must fail loudly — a cached Opus
    extract scored under a fable label would corrupt the benchmark."""
    for argv in (
        ["--model", "claude-fable-5", "--replay"],
        ["--model", "claude-fable-5", "--use-gt-inputs"],
        ["--model", "claude-fable-5", "--totals-only"],
        ["--model", "claude-fable-5"],  # implicit default = use_gt_inputs
    ):
        monkeypatch.setattr(sys, "argv", ["eval_harness.py"] + argv)
        monkeypatch.delenv("MODEL_OVERRIDE", raising=False)
        with pytest.raises(SystemExit) as exc:
            harness.main()
        assert "--vision" in str(exc.value), argv
        # env must NOT be polluted by the failed invocation
        import os
        assert os.getenv("MODEL_OVERRIDE") is None


def test_harness_model_flag_sets_override_before_pipeline(harness, monkeypatch):
    """--model --vision sets MODEL_OVERRIDE, namespaces the run dir by model,
    and forces a FRESH pipeline call (our stub is the only extract source)."""
    import os
    calls = {}

    def fake_vision(pdf_path):
        calls["override_at_pipeline_time"] = os.getenv("MODEL_OVERRIDE")
        return {"patalpos": [], "bendras_plotas_m2": 0,
                "_meta": {"model": os.getenv("MODEL_OVERRIDE"),
                          "input_tokens": 10, "output_tokens": 5,
                          "cache_read_tokens": 0, "cache_write_tokens": 0}}

    monkeypatch.setattr(harness, "run_pipeline_vision", fake_vision)
    monkeypatch.setattr(harness, "EVAL_RUNS_ROOT",
                        Path(harness.EVAL_RUNS_ROOT).parent / "eval_runs_test_tmp")
    monkeypatch.delenv("MODEL_OVERRIDE", raising=False)
    monkeypatch.setattr(sys, "argv", [
        "eval_harness.py", "--project", "berzas", "--vision",
        "--model", "claude-fable-5"])
    import shutil
    try:
        harness.main()
        assert calls["override_at_pipeline_time"] == "claude-fable-5"
        model_dir = harness.EVAL_RUNS_ROOT / "claude-fable-5"
        assert model_dir.exists()
        results = sorted(model_dir.rglob("results.json"))
        assert results, "results.json not written under eval_runs/<model>/"
        payload = json.loads(results[-1].read_text())
        assert payload["model"] == "claude-fable-5"
        assert payload["meta_rollup"]["model"] == "claude-fable-5"
        assert payload["meta_rollup"]["wall_time_s"] >= 0
    finally:
        shutil.rmtree(harness.EVAL_RUNS_ROOT, ignore_errors=True)
        os.environ.pop("MODEL_OVERRIDE", None)

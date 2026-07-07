"""--experiment support in eval_harness.py (2026-07-04 accuracy A/Bs).

Offline only: exercises the spec→env translation, the run-dir tag, and the
fresh-vision guard. No Vision, no API.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

_EXPERIMENT_ENVS = ("SAMATU_PDF_NATIVE", "SAMATU_ZOOM_AGENTIC",
                    "SAMATU_VOTING_MODELS")


def _load_harness():
    spec = importlib.util.spec_from_file_location(
        "eval_harness_expmod", REPO_ROOT / "eval_harness.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_harness_expmod"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def harness():
    return _load_harness()


@pytest.fixture(autouse=True)
def _clean_experiment_env(monkeypatch):
    for env in _EXPERIMENT_ENVS:
        monkeypatch.delenv(env, raising=False)


def test_native_pdf_spec_sets_env_and_tag(harness):
    import os
    tag = harness._apply_experiment_env("native-pdf")
    assert tag == "native-pdf"
    assert os.environ["SAMATU_PDF_NATIVE"] == "1"
    assert "SAMATU_ZOOM_AGENTIC" not in os.environ


def test_agentic_zoom_spec_sets_env_and_tag(harness):
    import os
    tag = harness._apply_experiment_env("agentic-zoom")
    assert tag == "agentic-zoom"
    assert os.environ["SAMATU_ZOOM_AGENTIC"] == "1"


def test_mixed_vote_spec_sets_model_list(harness):
    import os
    tag = harness._apply_experiment_env(
        "mixed-vote:claude-fable-5,claude-fable-5,claude-opus-4-8")
    assert os.environ["SAMATU_VOTING_MODELS"] == \
        "claude-fable-5,claude-fable-5,claude-opus-4-8"
    # filesystem-safe tag (no commas/colons)
    assert tag == "mixed-vote_claude-fable-5+claude-fable-5+claude-opus-4-8"
    assert "," not in tag and ":" not in tag


def test_mixed_vote_empty_list_rejected(harness):
    with pytest.raises(SystemExit):
        harness._apply_experiment_env("mixed-vote:")
    with pytest.raises(SystemExit):
        harness._apply_experiment_env("mixed-vote: , ")


def test_unknown_spec_rejected(harness):
    with pytest.raises(SystemExit):
        harness._apply_experiment_env("warp-drive")


def test_experiment_without_vision_is_refused(harness, monkeypatch):
    """Same guard as --model: experiments must be fresh Vision reads."""
    import os
    monkeypatch.setattr(sys, "argv",
                        ["eval_harness.py", "--experiment", "native-pdf"])
    with pytest.raises(SystemExit) as exc:
        harness.main()
    assert "--vision" in str(exc.value)
    # guard fired BEFORE the env was set
    assert "SAMATU_PDF_NATIVE" not in os.environ


def test_experiment_run_dir_tagging(harness, monkeypatch, tmp_path):
    """run_one namespaces experiment output as <model-or-config>__<tag>/."""
    monkeypatch.setattr(harness, "EVAL_RUNS_ROOT", tmp_path)
    # stub the pipeline: reuse the GT-inputs driver so no Vision is called
    truth = harness._load_truth("berzas")
    monkeypatch.setattr(harness, "run_pipeline_vision",
                        lambda pdf_path: harness.run_pipeline_use_gt_inputs(truth))
    harness.run_one("berzas", "vision", experiment="native-pdf",
                    model="claude-opus-4-8")
    tagged = list(tmp_path.glob("claude-opus-4-8__native-pdf/*_berzas_vision"))
    assert len(tagged) == 1
    assert (tagged[0] / "results.json").exists()

    harness.run_one("berzas", "vision", experiment="agentic-zoom", model=None)
    assert list(tmp_path.glob("default-config__agentic-zoom/*_berzas_vision"))

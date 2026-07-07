"""models_config.model_for resolution-chain tests (W1.1, 2026-07-03).

Chain: SAMATU_MODEL_<ROLE> → MODEL_OVERRIDE → legacy (VISION_MODEL /
EXTRACTION_MODEL) → per-role default. Resolution must happen at CALL time
so eval_harness --model (which sets MODEL_OVERRIDE) steers every reader.
"""
import pytest

import models_config
from models_config import ROLES, model_for, resolved_models

_ENV_VARS = [
    "MODEL_OVERRIDE", "VISION_MODEL", "EXTRACTION_MODEL",
] + [f"SAMATU_MODEL_{r.upper()}" for r in ROLES]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_default_is_opus_48_for_every_role():
    for role in ROLES:
        assert model_for(role) == "claude-opus-4-8"


def test_unknown_role_raises_keyerror():
    with pytest.raises(KeyError):
        model_for("nonexistent_role")


def test_model_override_applies_globally(monkeypatch):
    monkeypatch.setenv("MODEL_OVERRIDE", "claude-fable-5")
    for role in ROLES:
        assert model_for(role) == "claude-fable-5"


def test_per_role_env_beats_model_override(monkeypatch):
    monkeypatch.setenv("MODEL_OVERRIDE", "claude-fable-5")
    monkeypatch.setenv("SAMATU_MODEL_DOORS", "claude-opus-4-8")
    assert model_for("doors") == "claude-opus-4-8"
    assert model_for("apdailos") == "claude-fable-5"  # override still global


def test_model_override_beats_legacy_envs(monkeypatch):
    monkeypatch.setenv("MODEL_OVERRIDE", "claude-fable-5")
    monkeypatch.setenv("VISION_MODEL", "claude-opus-4-8")
    monkeypatch.setenv("EXTRACTION_MODEL", "claude-opus-4-8")
    assert model_for("vision_pass1") == "claude-fable-5"
    assert model_for("extraction") == "claude-fable-5"


def test_legacy_vision_model_applies_to_vision_roles_only(monkeypatch):
    monkeypatch.setenv("VISION_MODEL", "claude-fable-5")
    assert model_for("vision_pass1") == "claude-fable-5"
    assert model_for("vision_pass2") == "claude-fable-5"
    assert model_for("doors") == "claude-fable-5"
    assert model_for("symbols") == "claude-fable-5"
    # extraction + chat are NOT vision roles
    assert model_for("extraction") == "claude-opus-4-8"
    assert model_for("chat") == "claude-opus-4-8"


def test_legacy_extraction_model_applies_to_extraction_only(monkeypatch):
    monkeypatch.setenv("EXTRACTION_MODEL", "claude-fable-5")
    assert model_for("extraction") == "claude-fable-5"
    assert model_for("vision_pass1") == "claude-opus-4-8"
    assert model_for("chat") == "claude-opus-4-8"


def test_resolution_is_call_time_not_import_time(monkeypatch):
    """Env changes AFTER import must apply — this is what lets the eval
    harness set MODEL_OVERRIDE and steer already-imported readers."""
    assert model_for("vision_pass1") == "claude-opus-4-8"
    monkeypatch.setenv("MODEL_OVERRIDE", "claude-fable-5")
    assert model_for("vision_pass1") == "claude-fable-5"
    monkeypatch.delenv("MODEL_OVERRIDE")
    assert model_for("vision_pass1") == "claude-opus-4-8"


def test_resolved_models_returns_live_full_map(monkeypatch):
    monkeypatch.setenv("MODEL_OVERRIDE", "claude-fable-5")
    live = resolved_models()
    assert set(live) == set(ROLES)
    assert all(v == "claude-fable-5" for v in live.values())


def test_role_set_matches_plan():
    assert set(ROLES) == {
        "vision_pass1", "vision_pass2", "doors", "apdailos", "sanitary",
        "legend", "page_classifier", "symbols", "extraction", "chat",
    }


def test_no_temperature_rule_documented():
    """The no-temperature rule must stay in the module docstring — it is the
    guard against someone re-adding a param that 400s on Opus 4.8/Fable 5."""
    doc = models_config.__doc__ or ""
    assert "temperature" in doc and "top_p" in doc and "top_k" in doc

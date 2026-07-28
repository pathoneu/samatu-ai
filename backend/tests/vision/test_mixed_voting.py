"""EXPERIMENT Mode 3 — mixed-model voting (SAMATU_VOTING_MODELS).

All tests run offline ($0): _run_pass1_once is stubbed, adjacency disabled.
Covers: env parsing, cache-friendly same-model grouping, per-round model
resolution through the voting loop, per-round token/cost split in
_meta.voting_models, calc_meta_cost_usd aggregation (per-round rates), and
default-OFF behaviour (no env → per-round telemetry still recorded since the
2026-07-28 T4 fix, but no `experiment` block and an unchanged billed amount).
"""
from __future__ import annotations

import pytest

import extractor.vision_call as vc
import extractor.vision.adjacency_extractor as adj_mod
from pricing import RATES, calc_claude_cost_usd, calc_meta_cost_usd


# ── env parsing + grouping ─────────────────────────────────────────────────────
def test_mixed_voting_models_env_parsing(monkeypatch):
    monkeypatch.delenv("SAMATU_VOTING_MODELS", raising=False)
    assert vc._mixed_voting_models() is None
    monkeypatch.setenv("SAMATU_VOTING_MODELS", "")
    assert vc._mixed_voting_models() is None
    monkeypatch.setenv("SAMATU_VOTING_MODELS", " , ,")
    assert vc._mixed_voting_models() is None
    monkeypatch.setenv("SAMATU_VOTING_MODELS",
                       " claude-fable-5 , claude-fable-5, claude-opus-4-8 ")
    assert vc._mixed_voting_models() == [
        "claude-fable-5", "claude-fable-5", "claude-opus-4-8"]


def test_group_rounds_by_model_keeps_same_model_consecutive():
    # Prompt cache is per-model — same-model rounds must run back-to-back.
    assert vc._group_rounds_by_model(["a", "b", "a"]) == ["a", "a", "b"]
    assert vc._group_rounds_by_model(["x"]) == ["x"]
    assert vc._group_rounds_by_model(["a", "a", "a"]) == ["a", "a", "a"]
    # first-appearance order of distinct models preserved
    assert vc._group_rounds_by_model(["b", "a", "b", "a"]) == ["b", "b", "a", "a"]


# ── voting loop resolution ─────────────────────────────────────────────────────
def _fake_run(model: str) -> dict:
    return {
        "patalpos": [{"nr": 1, "pavadinimas": "X", "plotas_m2": 10.0,
                      "perimetras_m": 12.0}],
        "detected_symbols_summary": {},
        "_meta": {"attempt": 1, "model": model,
                  "input_tokens": 1000, "output_tokens": 500,
                  "cache_read_tokens": 200, "cache_write_tokens": 100},
    }


@pytest.fixture
def no_adjacency(monkeypatch):
    monkeypatch.setattr(adj_mod, "extract_adjacency",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("offline")))


def test_voted_mixed_resolves_model_per_round(monkeypatch, no_adjacency):
    monkeypatch.setenv("SAMATU_VOTING_MODELS",
                       "claude-fable-5,claude-opus-4-8,claude-fable-5")
    seen_models: list[str | None] = []

    def _stub(client, system, pages, *, native_pdf=None, model=None):
        seen_models.append(model)
        return _fake_run(model)

    monkeypatch.setattr(vc, "_run_pass1_once", _stub)
    out = vc._run_pass1_voted(client=None, system=None,
                              pages=[{"image_b64": "x"}], n=99,  # env overrides n
                              _emit=lambda e: None)

    # grouped: both fable rounds consecutive, then opus; env length wins over n
    assert seen_models == ["claude-fable-5", "claude-fable-5", "claude-opus-4-8"]

    meta = out["_meta"]
    assert meta["voting_runs"] == 3
    rounds = meta["voting_models"]
    assert [r["model"] for r in rounds] == seen_models
    assert [r["round"] for r in rounds] == [1, 2, 3]
    # per-round cost priced at THAT round's model rates
    fable = calc_claude_cost_usd(input_tokens=1000, output_tokens=500,
                                 cache_read_tokens=200, cache_write_tokens=100,
                                 model="claude-fable-5")
    opus = calc_claude_cost_usd(input_tokens=1000, output_tokens=500,
                                cache_read_tokens=200, cache_write_tokens=100,
                                model="claude-opus-4-8")
    assert rounds[0]["cost_usd"] == pytest.approx(round(fable, 4))
    assert rounds[2]["cost_usd"] == pytest.approx(round(opus, 4))
    assert meta["voting_cost_usd"] == pytest.approx(
        round(round(fable, 4) * 2 + round(opus, 4), 4))
    # provenance
    exp = meta["experiment"]["mixed_vote"]
    assert exp["models_requested"] == [
        "claude-fable-5", "claude-opus-4-8", "claude-fable-5"]
    assert exp["models_run_order"] == seen_models
    # aggregation logic untouched: token sums still span all rounds
    assert meta["input_tokens"] == 3000
    assert meta["output_tokens"] == 1500


def test_voted_mixed_records_failed_round(monkeypatch, no_adjacency):
    monkeypatch.setenv("SAMATU_VOTING_MODELS", "claude-fable-5,claude-opus-4-8")
    calls = iter([
        {"status": "error", "_error": "vision_call_failed: boom"},
        _fake_run("claude-opus-4-8"),
    ])
    monkeypatch.setattr(vc, "_run_pass1_once",
                        lambda *a, **k: next(calls))
    out = vc._run_pass1_voted(client=None, system=None,
                              pages=[{"image_b64": "x"}], n=2,
                              _emit=lambda e: None)
    # degraded single-run path still carries the mixed-vote provenance
    assert out["_voting"]["degraded"] is True
    rounds = out["_meta"]["voting_models"]
    assert rounds[0]["error"] == "vision_call_failed: boom"
    assert rounds[1]["model"] == "claude-opus-4-8"
    assert out["_meta"]["experiment"]["mixed_vote"]


def test_voted_mixed_unknown_model_cost_is_none_not_crash(monkeypatch, no_adjacency):
    monkeypatch.setenv("SAMATU_VOTING_MODELS", "no-such-model,no-such-model")
    monkeypatch.setattr(vc, "_run_pass1_once",
                        lambda *a, **k: _fake_run(k.get("model")))
    out = vc._run_pass1_voted(client=None, system=None,
                              pages=[{"image_b64": "x"}], n=2,
                              _emit=lambda e: None)
    rounds = out["_meta"]["voting_models"]
    assert all(r["cost_usd"] is None for r in rounds)
    assert out["_meta"]["voting_cost_usd"] is None


def test_voted_default_off_still_records_per_round_telemetry(monkeypatch, no_adjacency):
    """T4 (2026-07-28 telemetry audit) — CONTRACT CHANGE, deliberate.

    This test previously asserted `"voting_models" not in meta` when the env
    var is unset. That was the bug: production never sets SAMATU_VOTING_MODELS,
    so the per-round cache-hit/miss split — the only way to tell a prompt-cache
    regression from a genuine token increase — was unreachable in prod.

    What must NOT change: the experiment-only provenance block stays gated, and
    the billed amount is identical (asserted below)."""
    monkeypatch.delenv("SAMATU_VOTING_MODELS", raising=False)
    monkeypatch.setattr(vc, "_run_pass1_once",
                        lambda *a, **k: _fake_run("claude-opus-4-8"))
    out = vc._run_pass1_voted(client=None, system=None,
                              pages=[{"image_b64": "x"}], n=3,
                              _emit=lambda e: None)
    meta = out["_meta"]
    assert meta["voting_runs"] == 3

    rounds = meta["voting_models"]
    assert len(rounds) == 3
    assert [r["round"] for r in rounds] == [1, 2, 3]
    assert all(r["model"] == "claude-opus-4-8" for r in rounds)
    assert all(r["cache_read_tokens"] == 200 for r in rounds)
    assert all(r["cache_write_tokens"] == 100 for r in rounds)

    # Experiment-only provenance stays experiment-only.
    assert "mixed_vote" not in (meta.get("experiment") or {})

    # And the money is unchanged: with one model, pricing the per-round split
    # equals pricing the summed tokens (calc_claude_cost_usd is linear).
    assert calc_meta_cost_usd(meta) == pytest.approx(calc_claude_cost_usd(
        input_tokens=3 * 1000, output_tokens=3 * 500,
        cache_read_tokens=3 * 200, cache_write_tokens=3 * 100,
        model="claude-opus-4-8"))


# ── cost aggregation (calc_meta_cost_usd) ─────────────────────────────────────
def test_calc_meta_cost_usd_splits_per_round_rates():
    meta = {
        "model": "claude-fable-5",           # first round's model — must NOT
        "input_tokens": 2_000_000,           # be used to price the whole sum
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "voting_models": [
            {"round": 1, "model": "claude-fable-5", "input_tokens": 1_000_000,
             "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0},
            {"round": 2, "model": "claude-opus-4-8", "input_tokens": 1_000_000,
             "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0},
        ],
    }
    # 1M in @ $10 (fable) + 1M in @ $5 (opus) = $15 — NOT 2M @ $10 = $20
    assert calc_meta_cost_usd(meta) == pytest.approx(
        RATES["claude-fable-5"]["in"] + RATES["claude-opus-4-8"]["in"])


def test_calc_meta_cost_usd_single_model_matches_legacy():
    meta = {"model": "claude-opus-4-8", "input_tokens": 741,
            "output_tokens": 20438, "cache_read_tokens": 152518,
            "cache_write_tokens": 76259}
    legacy = calc_claude_cost_usd(
        input_tokens=741, output_tokens=20438, cache_read_tokens=152518,
        cache_write_tokens=76259, model="claude-opus-4-8")
    assert calc_meta_cost_usd(meta) == pytest.approx(legacy)


def test_calc_meta_cost_usd_skips_errored_rounds():
    meta = {
        "model": "claude-opus-4-8",
        "voting_models": [
            {"round": 1, "model": "claude-opus-4-8", "error": "boom"},
            {"round": 2, "model": "claude-opus-4-8", "input_tokens": 1_000_000,
             "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0},
        ],
    }
    assert calc_meta_cost_usd(meta) == pytest.approx(RATES["claude-opus-4-8"]["in"])


def test_calc_meta_cost_usd_unknown_round_model_raises():
    meta = {"voting_models": [
        {"round": 1, "model": "no-such-model", "input_tokens": 10}]}
    with pytest.raises(ValueError):
        calc_meta_cost_usd(meta)

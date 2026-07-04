"""Sub-call cost roll-up — complete per-extraction metering (2026-07-04).

The extraction pipeline makes MANY Anthropic calls beyond Pass-1 (eksplikacija
Vision fallback, apdailos, doors, door_type ×N voted rounds, zoom fixed-crop,
agentic zoom, sanitary fixtures). Their tokens used to be dropped — only Pass-1
was priced — so per-user/per-project cost (and the hard spend cap) undercounted
true spend by 34-76%.

Design mirrors the existing `voting_models` mechanism: ONE usage_event per
extraction, but its cost is complete. `calc_meta_cost_usd` now also prices an
optional `meta["extra_calls"]` list — each entry at ITS OWN model's rate — and
sums it on top of the main/voting cost. Sub-readers may use DIFFERENT models
than Pass-1 (each resolves its own model_for(...)), so a naive single-model
token sum would misprice.
"""
import pytest

import db
from pricing import calc_claude_cost_usd, calc_meta_cost_usd

MTOK = 1_000_000


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "rollup.db")
    db.init_schema()


# ── extra_calls: additive, per-model-correct ──────────────────────────────────

def test_extra_calls_absent_is_unchanged():
    """Regression guard: a meta WITHOUT extra_calls prices exactly as before."""
    meta = {"input_tokens": 50_000, "output_tokens": 8_000,
            "cache_read_tokens": 200_000, "cache_write_tokens": 30_000,
            "model": "claude-opus-4-8"}
    got = calc_meta_cost_usd(meta)
    expected = calc_claude_cost_usd(50_000, 8_000, 200_000, 30_000,
                                    model="claude-opus-4-8")
    assert got == pytest.approx(expected)


def test_extra_calls_empty_list_is_unchanged():
    meta = {"input_tokens": 50_000, "output_tokens": 8_000,
            "model": "claude-opus-4-8", "extra_calls": []}
    got = calc_meta_cost_usd(meta)
    expected = calc_claude_cost_usd(50_000, 8_000, model="claude-opus-4-8")
    assert got == pytest.approx(expected)


def test_extra_calls_added_on_top_of_single_model_main():
    """Pass-1 Opus + one Apdailos Opus sub-call = sum of both, priced per-call."""
    meta = {
        "input_tokens": 40_000, "output_tokens": 6_000,
        "cache_read_tokens": 100_000, "cache_write_tokens": 20_000,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 12_000,
             "output_tokens": 900, "cache_read_tokens": 5_000,
             "cache_write_tokens": 0},
        ],
    }
    main_cost = calc_claude_cost_usd(40_000, 6_000, 100_000, 20_000,
                                     model="claude-opus-4-8")
    extra_cost = calc_claude_cost_usd(12_000, 900, 5_000, 0,
                                      model="claude-opus-4-8")
    assert calc_meta_cost_usd(meta) == pytest.approx(main_cost + extra_cost)


def test_extra_calls_mixed_models_each_at_own_rate():
    """Pass-1 Opus + an Apdailos Opus call + a Fable door-type round.
    Each extra_call is priced at ITS OWN model's rate, not the main model's."""
    meta = {
        "input_tokens": 40_000, "output_tokens": 6_000,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 10_000,
             "output_tokens": 500},
            {"model": "claude-fable-5", "input_tokens": 8_000,
             "output_tokens": 400, "cache_read_tokens": 2_000},
        ],
    }
    main_cost = calc_claude_cost_usd(40_000, 6_000, model="claude-opus-4-8")
    apdailos = calc_claude_cost_usd(10_000, 500, model="claude-opus-4-8")
    door_fable = calc_claude_cost_usd(8_000, 400, cache_read_tokens=2_000,
                                      model="claude-fable-5")
    assert calc_meta_cost_usd(meta) == pytest.approx(
        main_cost + apdailos + door_fable)


def test_extra_calls_added_on_top_of_voting_main():
    """extra_calls stack on top of a mixed-model VOTING main cost, not instead."""
    meta = {
        "model": "claude-opus-4-8",
        "voting_models": [
            {"model": "claude-opus-4-8", "input_tokens": 30_000,
             "output_tokens": 4_000},
            {"model": "claude-fable-5", "input_tokens": 28_000,
             "output_tokens": 3_800},
        ],
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 9_000,
             "output_tokens": 600},
        ],
    }
    vote = (calc_claude_cost_usd(30_000, 4_000, model="claude-opus-4-8")
            + calc_claude_cost_usd(28_000, 3_800, model="claude-fable-5"))
    extra = calc_claude_cost_usd(9_000, 600, model="claude-opus-4-8")
    assert calc_meta_cost_usd(meta) == pytest.approx(vote + extra)


def test_extra_call_unknown_model_raises():
    """An unknown model in an extra_call must RAISE — never silently mis-price,
    consistent with calc_claude_cost_usd / the voting path."""
    meta = {
        "input_tokens": 10_000, "output_tokens": 500,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-haiku-4-5", "input_tokens": 5_000,
             "output_tokens": 200},
        ],
    }
    with pytest.raises(ValueError, match="no pricing rate"):
        calc_meta_cost_usd(meta)


def test_extra_call_missing_tokens_default_to_zero():
    """Partial token fields default to 0 (best-effort capture); a bare {model}
    extra_call adds nothing."""
    meta = {"input_tokens": 10_000, "output_tokens": 500,
            "model": "claude-opus-4-8",
            "extra_calls": [{"model": "claude-opus-4-8"}]}
    expected = calc_claude_cost_usd(10_000, 500, model="claude-opus-4-8")
    assert calc_meta_cost_usd(meta) == pytest.approx(expected)


def test_extra_call_without_model_key_raises():
    """An extra_call MUST name its model — a missing model key is a capture bug,
    not a free call. Raise rather than silently pricing at the default."""
    meta = {"input_tokens": 10_000, "output_tokens": 500,
            "model": "claude-opus-4-8",
            "extra_calls": [{"input_tokens": 5_000, "output_tokens": 200}]}
    with pytest.raises(ValueError):
        calc_meta_cost_usd(meta)


# ── record_usage stores the FULL summed cost, not just Pass-1 ──────────────────

def test_record_usage_includes_extra_calls_cost(tmp_path, monkeypatch):
    """record_usage on a response whose _meta.extra_calls is populated must
    ledger the FULL summed cost (×0.93 EUR), not just the Pass-1 tokens."""
    _isolate(tmp_path, monkeypatch)
    meta = {
        "input_tokens": 40_000, "output_tokens": 6_000,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 20_000,
             "output_tokens": 1_500},
            {"model": "claude-fable-5", "input_tokens": 8_000,
             "output_tokens": 400},
        ],
    }
    cost = db.record_usage("u1", {"_meta": meta}, "extract-interior")
    expected_usd = calc_meta_cost_usd(meta)
    assert cost == pytest.approx(expected_usd * 0.93)
    total, n = db.user_usage_since("u1", hours=24)
    assert n == 1
    assert total == pytest.approx(round(expected_usd * 0.93, 4))


def test_record_usage_extra_calls_strictly_greater_than_pass1_only(tmp_path, monkeypatch):
    """The whole point of the fix: a response with sub-calls must ledger MORE
    than the same response with Pass-1 tokens alone (the old undercount)."""
    _isolate(tmp_path, monkeypatch)
    base_meta = {"input_tokens": 40_000, "output_tokens": 6_000,
                 "model": "claude-opus-4-8"}
    full_meta = {**base_meta, "extra_calls": [
        {"model": "claude-opus-4-8", "input_tokens": 25_000, "output_tokens": 2_000},
        {"model": "claude-opus-4-8", "input_tokens": 25_000, "output_tokens": 2_000},
    ]}
    pass1_only = db.record_usage("u1", {"_meta": dict(base_meta)}, "extract-interior")
    with_subs = db.record_usage("u2", {"_meta": full_meta}, "extract-interior")
    assert with_subs > pass1_only > 0

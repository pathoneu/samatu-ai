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


def _mk_metric(harness, label, actual, truth):
    abs_err = round(actual - truth, 3)
    pct = round((abs_err / truth) * 100, 3) if truth else None
    return harness.MetricResult(
        truth_key=label, label=label, unit="m²", tier="headline",
        truth_value=truth, truth_confidence="ok", actual_value=actual,
        abs_error=abs_err, pct_error=pct, status="fail")


def test_honest_filter_fresh_collapse_is_scored_and_flagged(harness):
    """A FRESH ai_extract emitting 0.0 vs a real >0 truth must NOT be silently
    dropped: it scores as the genuine -100% collapse AND is flagged in
    `collapsed`. Regression guard for the 2026-06-09 benchmark-honesty fix —
    the original silent-drop hid collapsed metrics on non-berzas projects."""
    results = [_mk_metric(harness, "CombinedPaint", 0.0, 388.0),  # collapse
               _mk_metric(harness, "LED", 22.45, 16.84)]          # normal
    scored, not_emitted, collapsed = harness._partition_headline_metrics(
        results, "ai_extract")
    assert [r.label for r in scored] == ["CombinedPaint", "LED"]
    assert collapsed == ["CombinedPaint"]
    assert not_emitted == []
    cp = next(r for r in scored if r.label == "CombinedPaint")
    assert cp.pct_error == -100.0


def test_honest_filter_replay_zero_is_excluded(harness):
    """Legacy `replay` keeps the old behaviour: a 0.0 vs >0 truth means the
    cached santrauka schema never tracked the field → excluded, not_emitted."""
    results = [_mk_metric(harness, "CombinedPaint", 0.0, 388.0),
               _mk_metric(harness, "LED", 22.45, 16.84)]
    scored, not_emitted, collapsed = harness._partition_headline_metrics(
        results, "replay")
    assert [r.label for r in scored] == ["LED"]
    assert not_emitted == ["CombinedPaint"]
    assert collapsed == []


def test_incomplete_truth_is_excluded_from_mae_but_still_reported(harness):
    """A truth marked incomplete/partial cannot measure the extractor, so it
    must not enter any MAE — and must not vanish either.

    Regression guard for the 2026-07-29 romainiai audit: _summarize selected
    on `pct_error is not None`, silently re-admitting the rows _classify had
    already demoted to no_truth. print_report skips no_truth rows, so the
    metric that supplied 79% of romainiai's 112.947% headline MAE was
    invisible in the table above the number."""
    good = _mk_metric(harness, "LED", 51.02, 34.54)          # +47.713%
    bad = _mk_metric(harness, "CombinedPaint", 1168.58, 420.08)  # +178.18%
    bad.truth_confidence = "incomplete"
    bad.status = "no_truth"                                  # what _classify does

    s = harness._summarize([good, bad])
    assert round(s["headline_mae_pct"], 3) == 47.713, "incomplete truth leaked into MAE"
    assert round(s["headline_max_pct"], 3) == 47.713
    assert s["headline_total"] == 1
    # ...but it is still surfaced, with its numbers, so nothing hides.
    excluded = s["excluded_incomplete_truth"]
    assert [e["label"] for e in excluded] == ["CombinedPaint"]
    assert excluded[0]["pct_error"] == 178.18
    assert excluded[0]["truth_confidence"] == "incomplete"

    # The aggregate path applies the same rule.
    scored, _, _ = harness._partition_headline_metrics([good, bad], "ai_extract")
    assert [r.label for r in scored] == ["LED"]


def test_hidden_door_metric_reads_pozicija_not_the_dead_santrauka_key(harness):
    """`pasleptu_duru_staktu_m_total` is a dead santrauka key (0.0 on all five
    benchmark projects — nothing writes the per-room field it sums). The real
    quantity ships as the pozicija 'Durų angų paruošimas beapvadinėms durims',
    so scoring the santrauka key guaranteed a fake -100% collapse."""
    accessor = harness.METRICS["pasleptu_duru_staktos_m"]["accessor"]
    parsed = {
        "santrauka": {"pasleptu_duru_staktu_m_total": 0.0},
        "pozicijos": [
            {"aprasymas": "Durų angų paruošimas beapvadinėms durims",
             "kiekis": 5.1, "vnt": "m"},
            {"aprasymas": "Angokraščių glaistymas-dažymas", "kiekis": 64.0},
        ],
    }
    assert accessor(parsed) == 5.1
    # A populated santrauka key still wins, and a genuine absence stays None
    # (scores "missing") rather than becoming a phantom 0.0.
    assert accessor({**parsed, "santrauka": {"pasleptu_duru_staktu_m_total": 7.0}}) == 7.0
    assert accessor({"santrauka": {}, "pozicijos": []}) is None


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


# ── _meta_rollup: reported cost must include _meta.extra_calls sub-Vision calls ──
# (2026-07-04 sub-call metering fix). Before the fix the harness priced Pass-1
# only; a measured run's headline €/project would undercount by 34-76%.

def test_meta_rollup_includes_extra_calls_cost(harness):
    """The reported cost_eur must price the WHOLE _meta (Pass-1 + extra_calls),
    matching backend db.record_usage — not Pass-1 alone."""
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from pricing import calc_meta_cost_usd
    meta = {
        "input_tokens": 40_000, "output_tokens": 6_000,
        "cache_read_tokens": 100_000, "cache_write_tokens": 20_000,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 12_000,
             "output_tokens": 900, "reader": "apdailos"},
            {"model": "claude-opus-4-8", "input_tokens": 9_000,
             "output_tokens": 700, "reader": "doors"},
        ],
    }
    mr = harness._meta_rollup({"_meta": meta}, 12.3, "claude-opus-4-8")
    expected_usd = round(calc_meta_cost_usd(meta), 4)
    assert mr["cost_usd"] == pytest.approx(expected_usd)
    assert mr["cost_eur"] == pytest.approx(round(expected_usd * 0.93, 4))
    # Pass-1-only cost is retained for the true/Pass-1 multiplier and is STRICTLY
    # smaller than the true cost when sub-calls fired.
    assert mr["cost_eur_pass1"] < mr["cost_eur"]
    assert mr["extra_calls_cost_eur"] == pytest.approx(
        round(mr["cost_eur"] - mr["cost_eur_pass1"], 4))
    # raw_meta retains extra_calls for offline auditing.
    assert "extra_calls" in mr["raw_meta"]
    assert len(mr["raw_meta"]["extra_calls"]) == 2


def test_meta_rollup_no_extra_calls_matches_pass1(harness):
    """Regression guard: without extra_calls, true cost == Pass-1 cost (the
    pre-fix number), so historical single-call runs price identically."""
    meta = {"input_tokens": 40_000, "output_tokens": 6_000,
            "model": "claude-opus-4-8"}
    mr = harness._meta_rollup({"_meta": meta}, 5.0, "claude-opus-4-8")
    assert mr["cost_eur"] == pytest.approx(mr["cost_eur_pass1"])
    assert mr["extra_calls_cost_eur"] == pytest.approx(0.0)
    assert mr["extra_calls_breakdown"] == {}


def test_meta_rollup_breakdown_attributes_cost_per_reader(harness):
    """extra_calls_breakdown groups sub-call cost by reader tag and its per-reader
    costs sum to the total extra_calls cost."""
    meta = {
        "input_tokens": 30_000, "output_tokens": 4_000,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 12_000,
             "output_tokens": 900, "reader": "apdailos"},
            {"model": "claude-opus-4-8", "input_tokens": 6_000,
             "output_tokens": 300, "reader": "door_type"},
            {"model": "claude-opus-4-8", "input_tokens": 6_100,
             "output_tokens": 310, "reader": "door_type"},
        ],
    }
    mr = harness._meta_rollup({"_meta": meta}, 8.0, "claude-opus-4-8")
    bd = mr["extra_calls_breakdown"]
    assert set(bd) == {"apdailos", "door_type"}
    assert bd["door_type"]["n_calls"] == 2
    assert bd["apdailos"]["n_calls"] == 1
    total_eur = round(sum(v["cost_eur"] for v in bd.values()), 4)
    assert total_eur == pytest.approx(mr["extra_calls_cost_eur"], abs=1e-3)

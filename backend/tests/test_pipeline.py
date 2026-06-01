"""Unit tests for the extraction Pipeline framework."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from extractor.pipeline import Pipeline, PipelineResult, StepResult


def test_steps_run_in_added_order():
    pipeline = Pipeline()
    log: list[str] = []
    pipeline.add_step("a", lambda ctx: log.append("a") or None)
    pipeline.add_step("b", lambda ctx: log.append("b") or None)
    pipeline.add_step("c", lambda ctx: log.append("c") or None)
    result = pipeline.run({})
    assert log == ["a", "b", "c"]
    assert result.n_ok == 3
    assert result.n_failed == 0


def test_step_can_mutate_context():
    pipeline = Pipeline()
    pipeline.add_step("set", lambda ctx: ctx.update({"x": 1}) or None)
    pipeline.add_step("inc", lambda ctx: ctx.update({"x": ctx["x"] + 1}) or None)
    result = pipeline.run({})
    assert result.context["x"] == 2


def test_step_can_return_dict_to_merge():
    pipeline = Pipeline()
    pipeline.add_step("step1", lambda ctx: {"a": 1, "b": 2})
    pipeline.add_step("step2", lambda ctx: {"c": ctx["a"] + ctx["b"]})
    result = pipeline.run({})
    assert result.context["a"] == 1
    assert result.context["b"] == 2
    assert result.context["c"] == 3


def test_failure_in_one_step_does_not_kill_pipeline():
    def boom(ctx):
        raise RuntimeError("step 2 exploded")

    pipeline = Pipeline()
    pipeline.add_step("a", lambda ctx: {"a": 1})
    pipeline.add_step("b", boom)
    pipeline.add_step("c", lambda ctx: {"c": 3})
    result = pipeline.run({})
    assert result.n_ok == 2
    assert result.n_failed == 1
    failed = next(s for s in result.steps if s.name == "b")
    assert failed.status == "error"
    assert "step 2 exploded" in failed.error
    # 'c' still ran because it has no declared dependency on 'b'
    assert result.context["c"] == 3


def test_dependency_failure_skips_dependent_step():
    def boom(ctx):
        raise ValueError("nope")
    ran = []
    pipeline = Pipeline()
    pipeline.add_step("a", boom)
    pipeline.add_step("b", lambda ctx: ran.append("b"), depends=["a"])
    pipeline.add_step("c", lambda ctx: ran.append("c"))  # no dep — should run
    result = pipeline.run({})
    assert ran == ["c"]
    skipped = next(s for s in result.steps if s.name == "b")
    assert skipped.status == "skipped_dependency_failed"
    assert "a" in skipped.notes["unmet_dependencies"]


def test_step_can_report_cost_via_context_sentinel():
    def vision_step(ctx):
        ctx["_step_vision_cost_usd"] = 0.42
        ctx["payload"] = "ok"
    pipeline = Pipeline().add_step("vision", vision_step)
    result = pipeline.run({})
    step = result.steps[0]
    assert step.cost_usd == 0.42
    assert result.total_cost_usd == 0.42
    # Sentinel is consumed (popped) from context
    assert "_step_vision_cost_usd" not in result.context


def test_step_can_report_notes_via_context_sentinel():
    def step(ctx):
        ctx["_step_x_notes"] = {"input_tokens": 1500, "output_tokens": 300}
    pipeline = Pipeline().add_step("x", step)
    result = pipeline.run({})
    step = result.steps[0]
    assert step.notes["input_tokens"] == 1500


def test_on_step_callback_fires_per_step():
    received: list[str] = []
    pipeline = (Pipeline()
                .add_step("a", lambda ctx: None)
                .add_step("b", lambda ctx: None))
    pipeline.run({}, on_step=lambda s: received.append(s.name))
    assert received == ["a", "b"]


def test_durations_are_recorded():
    import time as _t
    def slow(ctx):
        _t.sleep(0.01)
    pipeline = Pipeline().add_step("slow", slow)
    result = pipeline.run({})
    assert result.steps[0].duration_ms >= 10
    assert result.total_duration_ms >= 10


def test_pipeline_result_summary():
    pipeline = (Pipeline()
                .add_step("a", lambda ctx: None)
                .add_step("b", lambda ctx: (_ for _ in ()).throw(RuntimeError("x"))))
    result = pipeline.run({})
    d = result.to_dict()
    assert d["n_ok"] == 1
    assert d["n_failed"] == 1
    assert len(d["steps"]) == 2

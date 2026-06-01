"""Extraction pipeline framework — dependency-ordered, per-step error
handling, graceful degradation.

The existing ``extract_interior()`` in vision_call.py grew organically
into ~30 inline steps. This module provides the abstraction the future
code should adopt:

    pipeline = Pipeline()
    pipeline.add_step("render", render_pdf)
    pipeline.add_step("eksplikacija", read_eksplikacija, depends=["render"])
    pipeline.add_step("vision_pass1", run_vision, depends=["eksplikacija"])
    ...
    result = pipeline.run(context)

Each step:
  • Receives the shared ``context`` dict
  • Mutates context in-place OR returns a dict that's merged in
  • Is wrapped in try/except: a step crash sets the step's ``error`` field
    but the pipeline CONTINUES with the remaining steps that don't depend
    on it (graceful degradation, NOT crash-the-project)
  • Records start_ts, end_ts, duration_ms, status, error (if any),
    cost_usd (if reported)

Step dependencies are DAG-style: a step runs only after all its
dependencies have completed (status="ok"). If a dependency failed,
the dependent step is marked ``skipped_dependency_failed``.

The pipeline records a structured log on ``result.steps`` for
observability + the eval/audit harness.

This framework is currently shipped as INFRASTRUCTURE — production
``extract_interior()`` keeps its inline sequence for the moment, with
the migration tracked as follow-up work (see backend/extractor/__init__.py
docstring).
"""

from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field, asdict
from typing import Any, Callable

StepFn = Callable[[dict[str, Any]], dict[str, Any] | None]


@dataclass
class StepResult:
    name: str
    status: str               # "ok" | "error" | "skipped_dependency_failed"
    duration_ms: float = 0.0
    error: str | None = None
    cost_usd: float = 0.0
    notes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PipelineResult:
    steps: list[StepResult] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    total_duration_ms: float = 0.0
    total_cost_usd: float = 0.0
    n_ok: int = 0
    n_failed: int = 0
    n_skipped: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [s.to_dict() for s in self.steps],
            "total_duration_ms": self.total_duration_ms,
            "total_cost_usd": self.total_cost_usd,
            "n_ok": self.n_ok,
            "n_failed": self.n_failed,
            "n_skipped": self.n_skipped,
        }


class Pipeline:
    """A dependency-ordered sequence of named steps with per-step error
    handling and structured timing/cost logging."""

    def __init__(self, name: str = "extract") -> None:
        self.name = name
        self._steps: list[tuple[str, StepFn, list[str]]] = []

    def add_step(
        self,
        name: str,
        fn: StepFn,
        depends: list[str] | None = None,
    ) -> "Pipeline":
        self._steps.append((name, fn, depends or []))
        return self

    def run(
        self,
        context: dict[str, Any] | None = None,
        on_step: Callable[[StepResult], None] | None = None,
    ) -> PipelineResult:
        ctx = context if context is not None else {}
        result = PipelineResult(context=ctx)
        completed_ok: set[str] = set()
        t_pipeline_start = time.perf_counter()

        for name, fn, depends in self._steps:
            # Skip if any dependency failed/skipped
            unmet = [d for d in depends if d not in completed_ok]
            if unmet:
                step_res = StepResult(
                    name=name, status="skipped_dependency_failed",
                    notes={"unmet_dependencies": unmet},
                )
                result.steps.append(step_res)
                result.n_skipped += 1
                if on_step:
                    on_step(step_res)
                continue

            t0 = time.perf_counter()
            try:
                ret = fn(ctx)
                # If the step returned a dict, merge it into context
                if isinstance(ret, dict):
                    ctx.update(ret)
                step_res = StepResult(
                    name=name, status="ok",
                    duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                )
                # Pull cost / notes from context if the step reported them
                step_cost_key = f"_step_{name}_cost_usd"
                step_notes_key = f"_step_{name}_notes"
                if step_cost_key in ctx:
                    step_res.cost_usd = float(ctx.pop(step_cost_key))
                if step_notes_key in ctx:
                    step_res.notes = dict(ctx.pop(step_notes_key))
                completed_ok.add(name)
                result.n_ok += 1
                result.total_cost_usd += step_res.cost_usd
            except Exception as exc:
                step_res = StepResult(
                    name=name, status="error",
                    duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                    error=f"{type(exc).__name__}: {exc}",
                    notes={"traceback": traceback.format_exc().splitlines()[-3:]},
                )
                result.n_failed += 1

            result.steps.append(step_res)
            if on_step:
                on_step(step_res)

        result.total_duration_ms = round(
            (time.perf_counter() - t_pipeline_start) * 1000, 2
        )
        return result

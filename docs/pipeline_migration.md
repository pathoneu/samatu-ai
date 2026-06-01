# Extraction pipeline migration plan

`backend/extractor/pipeline.py` ships the `Pipeline` framework the
2026-06-01 cleanup brief specified: per-step error handling,
dependency-ordered execution, structured timing/cost logging,
graceful degradation.

This document tracks the migration of `extract_interior()` in
`backend/extractor/vision_call.py` from its inline ~30-step sequence
to Pipeline-based steps.

## Current state (post-2026-06-01)

The Pipeline framework is built and tested (10 unit tests cover
ordering, dependency handling, exception isolation, cost reporting,
notes propagation, and the on-step callback).

`extract_interior()` itself is NOT yet migrated. The function still
runs its 30+ steps inline via try/except. The migration is deferred
because:

  1. The function is ~1000 lines spanning 20+ commits worth of
     organic growth — a single big-bang refactor is high risk
  2. The existing inline try/except already provides per-step error
     isolation for ~80% of steps (the post-processing chain)
  3. Step ordering inside the function is documented but not
     formalized as dependencies; some reordering would be needed
     during migration

## Migration order (when scheduled)

The post-processing chain is the lowest-risk target because each
step already has try/except and no inter-step data passing beyond
the shared `parsed` dict.

### Phase A — post-processing chain (low risk)

Wrap Steps 3 through 4.7 in a Pipeline. Order of wrapping:

  1. `recompute_santrauka` (Step 3)
  2. `apply_lt_sanity` (Step 4)
  3. `cross_page_validator` (Step 4.05)
  4. `scale_validator` (Step 4.06)
  5. `sanity_checks.run_all_checks` (Step 4.065)
  6. `consistency_checker.run_all_checks` (Step 4.067)
  7. `perimeter_validator.validate_extract` (Step 4.066)
  8. `plyteliu_specifikacija` (Step 4.07)
  9. `wall_elevation` (Step 4.08) — opt-in via WALL_ELEVATION_EXTRACT
  10. emit `lt_sanity` mirror (Step 4.1)
  11. `_determinism_warning` (Step 4.5)
  12. `_emit_v8_compat_fields` (Step 5)

### Phase B — Vision-pass orchestration (medium risk)

Wrap the eksplikacija pre-pass, Vision pass 1, zoom pass, apdailos
reader, doors reader. Each is a single Vision call with retry logic
that should become a Pipeline step.

### Phase C — Setup + final return (low risk)

PDF rendering, vendor filter, paint class resolution, final result
shape.

## Adoption pattern

Each step is a callable `(context: dict) -> dict | None`:

```python
def santrauka_step(ctx):
    parsed = ctx["parsed"]
    ctx["parsed"] = _recompute_santrauka(parsed)

pipeline = (Pipeline("extract_interior")
            .add_step("santrauka", santrauka_step)
            .add_step("lt_sanity", lt_sanity_step, depends=["santrauka"])
            ...)
result = pipeline.run({"parsed": parsed, "pdf_bytes": pdf_bytes})
```

The pipeline's `result.steps` populates `parsed["_pipeline_log"]` for
the structured logging required by Task 3.

## Why this is enough for now

The framework is the contract; the migration is a behaviour-preserving
refactor. Once the framework is committed and tested, future work can
move 2-3 steps at a time per PR, each PR small enough to review
carefully and back out cheaply. That beats a single 1000-line
diff that nobody can review with confidence.

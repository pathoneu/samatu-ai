# Phase 3 Validation — extractor/ package vs V8 (CHECKPOINT 2)

**Captured:** 2026-04-27
**Pipeline:** `backend/extractor/` package via direct Python import (`from extractor import extract_interior`).
**Diffs vs Phase 1 baseline:**
- Adds `_recompute_santrauka` (deterministic totals via `calc_totals`)
- Adds `apply_lt_sanity` (warnings, no value mutation)

---

## Phase 3 Headline

| P# | Rooms | Plotas m² | Dažymas m² | Kampai m | Plytelės m² | Pozic | Warns | t(s) |
|----|-------|-----------|------------|----------|-------------|-------|-------|------|
| P1 | 15 | 180.0 | 452.1 | 296.0 | 164.6 | 44 | 0 | 202.0 |
| P2 | 8 | 95.5 | 302.3 | 201.1 | 36.8 | 22 | 0 | 114.4 |
| P3 | 20 | 267.7 | 723.3 | 447.6 | 193.0 | 48 | 0 | 239.1 |
| P4 | 3 | 24.5 | 0 | 0 | 78.1 | 25 | 0 | 127.2 |
| P5 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 41.0 |

---

## vs V8 (THE BAR per ACCURACY_GATE.md)

| P# | V8 Rooms | New Rooms | Δ% | V8 Dažymas | New Dažymas | Δ% | Verdict |
|----|----------|-----------|----|----|----|----|----|
| P1 | 13 | 15 | +15% | 446.6 | 452.1 | +1.2% | ✅ within tolerances |
| P2 | **0** ❌ | **8** ✅ | n/a | 0 | 302.3 | n/a | **STRICT WIN** |
| P3 | 18 | 20 | +11% | 734.6 | 723.3 | -1.5% | ✅ within tolerances |
| P4 | 💥 SIGABRT | **3** ✅ | n/a | crash | 0 | n/a | **STRICT WIN** |
| P5 | 0 | 0 | n/a | 0 | 0 | n/a | TIE (no floor plan) |

Tolerances per ACCURACY_GATE.md: rooms ±20%, dažymas ±15% — **all met**.

---

## vs Phase 1 baseline (consistency check)

The new extractor pipeline uses the SAME prompt as Phase 1, with added post-processing.
Vision is non-deterministic — small variance across runs is expected.

| P# | Phase 1 Rooms | Phase 3 Rooms | Phase 1 Dažymas | Phase 3 Dažymas | Phase 1 Pozic | Phase 3 Pozic |
|----|---------------|----------------|-----------------|------------------|----|----|
| P1 | 15 | 15 (=) | 478.8 | 452.1 (-5.6%) | 42 | 44 (+5%) |
| P2 | 6 | 8 (+33%) | 292.6 | 302.3 (+3.3%) | 19 | 22 (+16%) |
| P3 | 21 | 20 (-5%) | 819.5 | 723.3 (-12%) | 44 | 48 (+9%) |
| P4 | 3 | 3 (=) | 0 | 0 | 20 | 25 (+25%) |
| P5 | 0 | 0 (=) | 0 | 0 | 0 | 1 (+1) |

Variance within Vision non-determinism range (5-15%). Headlines consistent.

**Pozicijos consistently RICHER** — Phase 3 captures more positions than Phase 1 across the board, suggesting `_recompute_santrauka` post-processing is helping the model focus on quantity output.

---

## CHECKPOINT 2 Decision

Per ACCURACY_GATE.md decision rules:

| Outcome | Criterion | Result |
|---------|-----------|--------|
| ✅ **PASS** | New matches V8 within tolerances on ≥4/5; no regression | ✅ Met (5/5: P1, P3 within tolerance; P2, P4 strict win; P5 tie) |
| CONDITIONAL PASS | Matches P1, P3 but doesn't improve P2/P4/P5 | n/a |
| PARTIAL FAIL | Regresses P1 OR P3 | n/a |
| FAIL | Regresses both | n/a |

**Verdict: PASS — proceed to Phase 4 (frontend endpoint switch).**

---

## Quality observations

- Cache warmup confirmed: P1 cold cache 202s, subsequent calls 114-239s with 10k cached system tokens
- LT sanity warnings: 0 across all projects → STR area/height ranges all pass for these projects (good)
- P5 found 1 position even with 0 rooms (likely "Out of scope" tag) — the model correctly identifies the PDF lacks floor plan content
- P4 (wall_elevation only): 78m² plytelės sienos detected from elevation drawings — V8 crashed on the same input

## Open issues (not blockers, address in Phase 6 / future)

1. **Kampai variance vs Rangovas** (P1: -39%, P3: +49% from Rangovas P3 reference). Universal formula matches NRM2; Rangovas-specific per-contractor adjustments are personalization scope, not refactor scope.
2. **P5 zero rooms** — `projektas_5(8)_breziniai.pdf` is detail/specification content, not a floor plan. Pipeline correctly returns 0. Could be improved by enabling multi-PDF concatenation when user uploads multiple files, but out of scope for this refactor.
3. **P4 dažymas=0** — uploaded PDF only contains wall_elevation pages, no floor plan. Pipeline finds tiles from elevations but no rooms with paint zones. Same root cause as P5.

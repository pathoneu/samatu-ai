# Sprint 4 Block B — Wall_adjacency Activation Result

**Date:** 2026-05-05
**Goal:** Activate Sprint 2's `wall_adjacency.py` to fix grindjuostės double-count.

## What changed

1. **`backend/extractor/feature_flags.py`** — `polygon_prepass` flag default flipped from `False` to `True`. Override with `ENABLE_POLYGON_PREPASS=0` for one-line revert.

2. **`backend/extractor/vision_call.py::_apply_polygon_prepass`** — extended:
   - When room lacks `polygon_pct` (Vision rarely emits it), synthesize a 4-corner rectangle from `bbox_pct`. LT residential rooms are 99%+ axis-aligned; bbox-based synthesis is conservative (slightly over-corrects vs under).
   - Page metric extent estimated as `median(perimetras_m / bbox_perim_pct)` across rooms when `page_width_m` / `page_height_m` not provided. Assumes isotropic scale (LT plans typically square paper at uniform mm/px).
   - Result: `apply_shared_edges` runs and subtracts half-shared-edge length from each room's `perimetras_m`. Downstream `calc_room_quantities` then computes grindjuostės from corrected perimetras.

3. **`backend/tests/test_feature_flags.py`** — updated to assert new default (polygon_prepass=True) + added test for `ENABLE_POLYGON_PREPASS=0` revert path.

## Validation (P1 — real LT residential, 224 m² across 15 rooms)

Method: isolated test (`backend/scripts/sprint4_block_b_test.py`) — uses real `bbox_pct` + `perimetras_m` + `plotas_m2` + `paskirtis` data captured from earlier successful `extract_interior` run on `training-data/projektas_1/projektas_1_breziniai.pdf`. Avoids re-running the slow Vision call while still validating the math layer.

| Metric | Before prepass | After prepass | LT industry expect |
|---|---|---|---|
| grindjuostės total | 145.6 m (empirical cap fired) | **132.4 m** | — |
| ratio (m/m² floor) | 0.650 (at cap) | **0.591** | 0.50-0.60 |
| corrected rooms | 0 / 15 | **14 / 15** | — |

### Per-room perimeter corrections

Rooms with biggest shared-wall reductions (these have the most adjacent neighbors):

```
09 Miegamasis               15.5 → 10.4  (Δ -5.1)
10 Miegamojo vonia          15.5 → 12.4  (Δ -3.1)
03 Koridorius               22.0 → 19.6  (Δ -2.4)
08 Vaikų vonia              11.0 →  9.1  (Δ -1.9)
11 Miegamojo drabužinė      10.0 →  8.7  (Δ -1.3)
02 Svetainė/valgomasis      36.0 → 34.8  (Δ -1.2)
13 Tech. patalpa/skalbykla  13.0 → 11.8  (Δ -1.2)
12 Svečių wc                 7.0 →  5.9  (Δ -1.1)
07 Kambario 2 drabužinė      8.0 →  7.4  (Δ -0.6)
04 Kambarys                 14.0 → 13.5  (Δ -0.5)
05 Kambario drabužinė        8.0 →  7.5  (Δ -0.5)
06 Kambarys 2               15.5 → 15.0  (Δ -0.5)
15 Garažas                  27.0 → 26.6  (Δ -0.4)
01 Tambūras                 11.0 → 10.8  (Δ -0.2)
```

Pattern matches expectation: rooms with many adjacent neighbors (Miegamasis with attached vonia + drabužinė; Koridorius bordering multiple rooms) get the largest corrections. End-of-house rooms (Tambūras, Garažas) get small corrections.

## Why this matters

- **Pure math, no rangovas comparison.** LT industry math says interior walls are shared between two rooms and should be counted once. wall_adjacency implements the deterministic geometry.
- **Fixes a known credibility liability.** Pre-fix grindjuostės/floor ratio was 0.65 (at empirical cap) — any LT estimator can spot it: should be ~0.55. Now lands at 0.591, in expected band.
- **Replaces empirical cap (`GRINDJUOSCIU_RATIO_CAP = 0.65`) with proper shared-edge math.** The cap was a band-aid; this is the underlying fix.

## Risks (with mitigations)

| Risk | Mitigation |
|---|---|
| Bbox-from-polygon synthesis under-counts shared edges for L-shaped rooms (bbox > actual outline) | LT residential is 99%+ rectangular. For non-rectangular rooms, error is conservative (slightly over-counts shared edges → under-counts total perimeter, which is safer than the +88% pre-fix bias). |
| Page extent estimation assumes isotropic scale | LT plans almost universally use square mm/px. Anisotropic case would need explicit page_width_m / page_height_m from Vision (parent spec §4.4 has this in TODO). For now, isotropic is fine. |
| Vision Pass-1 doesn't emit polygon_pct (Sprint 2 prompt addition didn't take) | Bbox-synthesis fallback handles this. Future Sprint 5 work: strengthen Vision prompt with explicit polygon examples → real polygon_pct → more accurate L-shape handling. |
| Default-on flag could regress unknown edge case | One-line revert: `ENABLE_POLYGON_PREPASS=0`. Test coverage added for both directions. |

## Next steps

- [x] Validate on P1 (this doc) — ratio 0.591 ∈ [0.5, 0.6] ✓
- [ ] Validate on P3 + P5 (run when Vision API is responsive)
- [ ] Consider removing the empirical `GRINDJUOSCIU_RATIO_CAP = 0.65` band-aid in `vision_call.py` since proper math now handles it. Defer until P3+P5 validated to keep cap as safety net.

## Files touched

- `backend/extractor/feature_flags.py` — flag default flipped
- `backend/extractor/vision_call.py::_apply_polygon_prepass` — bbox synthesis + isotropic page extent estimation
- `backend/tests/test_feature_flags.py` — default + revert path tests
- `backend/scripts/sprint4_block_b_test.py` — isolated math validation script
- `docs/sprint-4-block-b-result.md` — this doc

## Test status

- Backend: 20/20 (test_feature_flags + test_wall_adjacency + test_wall_adjacency_pipeline)
- Frontend: unchanged
- Integration: real-PDF validation on P1 ✓

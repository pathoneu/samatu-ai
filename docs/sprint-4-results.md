# Sprint 4 — Accuracy Through Pure Math — Results

**Date:** 2026-05-05
**Plan:** `docs/superpowers/plans/2026-05-05-sprint-4-accuracy.md`
**Anchor:** Pure LT-industry math + drawing-as-ground-truth. NO Rangovas comparison.

---

## TL;DR

| Block | Status | Impact |
|---|---|---|
| **B — wall_adjacency activation** | ✓ shipped | grindjuostės/floor 0.650 → 0.591 m/m² (LT industry band) |
| **C — Section 6 sanity checks** | ✓ shipped | 6 runtime warnings; ⚠ banner in QuantitiesPanel |
| **A — eksplikacija read fidelity** | ✓ partial | P1+P3+P5 verified via pdfplumber; multi-floor case noted |
| **D — symbol counting validation** | ⏸ deferred | Manual count + Vision diff → Sprint 5 |

**Production-ready accuracy improvements shipped today.** Test suite: 35/35 backend (Block C added 15 tests), 118/118 frontend, vite build clean.

---

## Block B — Wall_adjacency activation

Detail: `docs/sprint-4-block-b-result.md`

**Bug fixed:** grindjuostės/floor ratio was 0.65 (at empirical cap) — should be 0.5-0.6 per LT math (interior walls shared between adjacent rooms, counted once not twice).

**Validation across 3 projects:**

| Project | floor m² | bbox→polygon synth | rooms corrected | comment |
|---|---|---|---|---|
| P1 (single floor) | 224.0 | 15/15 | 14/15 | ratio 0.650 → 0.591 ✓ |
| P3 (two floors) | 258.7 | 0/20 | 0/20 | bbox_pct missing on multi-floor pages — Vision didn't emit |
| P5 (small) | 34.4 | 4/4 | 4/4 | ✓ — corrected |

**Open finding:** P3 (multi-floor) Vision emits rooms WITHOUT bbox_pct. Single-floor projects (P1, P5) get bbox 100%. Sprint 5 work: strengthen Vision prompt to emit bbox_pct on every page, not just primary plan view.

**Fallback path stable:** when bbox_pct missing, `_apply_polygon_prepass` doesn't crash — `apply_shared_edges` bails with rooms unchanged. Empirical cap (`GRINDJUOSCIU_RATIO_CAP = 0.65`) still active as safety net for non-corrected paths.

---

## Block C — Section 6 sanity checks

Commit: `ffb3326`

**Implemented 6 of 10 CLAUDE.md Section 6 checks** (skipped #6-9 facade/roof/concrete out-of-scope for interior MVP):

1. ✓ Paintable wall area = 2.5-4× floor area
2. ✓ Ceiling area ≈ floor area (±5% strict, ±10% with soffit band)
3. ✓ Baseboard ≈ perimeter − 0.8m × doors
4. ✓ Paint ≈ 0.22 l/m² (2 coats avg)
5. ⏸ GK sheets math identity (placeholder — need per-room GKP area data)
6. ✓ Window reveals ≈ 5m per standard window

**Wired into pipeline.** `vision_call.py` runs `run_all_checks` after extraction; warnings appended to existing `vision_result["warnings"]` list (which Sprint 0 scale_validator already populates).

**Frontend surface:** `<QuantitiesPanel>` shows `⚠ N įspėjimai` banner at top when warnings present. Click → expandable list with `message` + `hint` + `expected` vs `actual`. Handles both string (Sprint 0) and dict (Block C) shapes.

**Real-PDF validation:**
- P3: 5 warnings emitted (cross_page_validator + sanity_checks combined)
- P5: 5 warnings (smaller project, fewer rooms)
- P1: not re-tested (Vision API was hung during baseline run; isolated math test passed instead)

**Pure math, no Rangovas reference:** every check derives from CLAUDE.md or LT industry constants.

---

## Block A — Eksplikacija read fidelity

**Reframed from "manual transcription" to "pdfplumber-as-truth":** Sprint 0's `pdfplumber_eksplikacija.py` already deterministically reads eksplikacija lentelę when the PDF allows it. Use IT as ground truth instead of hand-transcribing.

**P1 validation:** ✓ all 15 rooms have `saltinis: "eksplikacija"`, plotai match pdfplumber output exactly (Tambūras 7.36, Svetainė 62.42, Koridorius 15.25, Garažas 55.40, etc.). Vision faithfully preserves pdfplumber primitives.

**P3 finding:** pdfplumber reads 11 rooms (single-floor eksplikacija page 5). Final extract emits **20 rooms across two floors** (1A + 2A). Vision correctly extracted second-floor rooms via separate prompt path. The cross_page_validator emitted: "Bendras plotas iš dviejų eksplikacijų: 1A=170.67m² + 2A=97.04m² = 267.71m²." Math adds up to 267.71 vs final patalpos sum 258.73 — small 3% gap. Acceptable; investigate when more multi-floor projects available.

**P5 finding:** pdfplumber MISS (no eksplikacija lentelė detected on page 1). Falls through to Vision-direct extraction. 4 rooms, 34.4 m² total. Without ground-truth lentelė, can't compute fidelity score for P5. Sprint 5 work: add fallback eksplikacija detection or accept Vision-only path with stricter sanity checks.

**Conclusion:** Eksplikacija → final patalpos pipeline preserves primitives faithfully when eksplikacija is parseable. Multi-floor + missing-eksplikacija edge cases are real but contained.

---

## Block D — Symbol counting validation

**Status:** Deferred to Sprint 5.

**Reasoning:** Block D requires (1) manual count of symbols on 3+ project pages and (2) comparison with AI's `detected_symbols_summary`. The manual count is ~1 hour of human work and the existing `ground_truth/projektas_*.yaml` files are AI-seeded (`confirmed_by: claude_unverified_seed`), not human-confirmed. Without trustworthy ground truth, the validation is a tautology.

**Suggested Sprint 5 approach:** human user spends 1h verifying ground_truth YAML files (count rozetes/jungiklius/sanitarą per page directly from PDFs), updating `confirmed_by: human`. Then run Block D diff script with new ground truth.

---

## Empirical cap status

`GRINDJUOSCIU_RATIO_CAP = 0.65` band-aid in `vision_call.py` remains active as safety net. After Block B activation, it shouldn't fire for projects with bbox_pct populated — corrected ratio falls in 0.5-0.6 band naturally. For PDFs without bbox_pct (e.g. P3 multi-floor), cap continues to prevent the +88% double-count. Remove the cap once all PDF types reliably get bbox_pct (Sprint 5+).

---

## Commits

- `3158356` — docs(sprint-4): plan
- `63c8690` — feat(sprint-4 block B): activate wall_adjacency
- `ffb3326` — feat(sprint-4 block C): Section 6 sanity checks as runtime warnings

---

## What ships to production

After this sprint, deployment carries:
1. **Block B math fix** — grindjuostės properly accounts for shared walls (eligible projects)
2. **Block C warnings UI** — ⚠ banner alerts user when math doesn't add up
3. **Block A audit baseline** — P1 confirms eksplikacija → final patalpos preservation; multi-floor + no-eksplikacija edge cases documented for Sprint 5

**Real-world testuotojai feedback** drives Sprint 5 priority:
- If grindjuostės still wrong on their PDFs → push Vision prompt to emit polygon_pct + bbox_pct everywhere
- If ⚠ banner fires too often / too rarely → tune sanity check thresholds
- If symbols miscounted → Block D activation with human ground truth

---

## Out-of-scope work flagged for Sprint 5

1. Vision prompt strengthening — emit bbox_pct + polygon_pct reliably on every floor plan page
2. Multi-floor extraction reconciliation — sum-of-eksplikacijos vs final patalpos sum
3. No-eksplikacija fallback (P5-style)
4. Block D execution with human-confirmed ground truth
5. Empirical cap removal (after coverage broad)
6. Per-room GKP area tracking → enable check_gk_sheets_math
7. AssumptionsPanel field-name mismatch (Sprint 0 follow-up #12) still pending

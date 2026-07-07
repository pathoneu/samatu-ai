# Finish-Semantics Lane + Confidence Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Checkbox steps.

**Goal:** Fix the two empirically-measured top error sources (2026-06-11 experiments): finish-assignment semantics (objektas_b paint +62.8% — molio tinkas counted as paint, self-reported low confidence ignored) and the unsellable confidence system (false-green 50–60%).

**Contractor-anchored success criteria:**
- Objektas B: "Sienų dekoravimas molio tinku" emitted (~160 m² target when apdailos re-read live); combined paint error shrinks from +62.8% toward ±15%.
- False-green rate (exp1b, confidence-aware): 50%/60% → **<25%** on both projects, with error recall by flags ≥70%.
- Zero regression on berzas paint (−6.6%) and the 772+ test suite.

**Architecture:** (1) apdailos vocabulary gains molio_tinkas/kita_danga categories; universal_rules apdailos branch splits molio area OUT of walls_paintable into a new per-room `molio_tinko_m2`; pozicijos emit the decor line. (2) `merge_apdailos_into_rooms` propagates self-reported "low confidence" → `_apdailos_confidence`. (3) New `extractor/confidence.py` post-pass stamps every pozicija with `confidence` + `_confidence_reason`: per-class calibration table (classes with measured systematic bias → geltona), apdailos low-conf rooms → finish-derived lines geltona, voting flags → geometry-derived lines geltona. (4) apdailos page-finder excludes VIZUALIZACIJA pages, collects all candidates. (5) Verify: offline re-score both saved voted extracts; live cheap re-read of the objektas_b apdailos page only (merge → recompute → re-score).

### Task 1: molio tinkas vocabulary + calc split (TDD)
- Modify `apdailos_reader.py`: SYSTEM_PROMPT + schema gain `molio_tinkas_share` + `kita_danga_share` ("molio/kalkinio tinko dekoras, mikrocementas — NE dažymas, NE plytelės").
- Modify `universal_rules.py` apdailos branch: `molio_m2 = molio_share × walls_paintable_gross`; `walls_paintable −= molio_m2`; set `room["molio_tinko_m2"]`.
- Modify `vision_call.py` pozicijos: emit `Sienų dekoravimas molio tinku` (SK_GD, m², Σ molio_tinko_m2) when > 0.
- Tests: share=0.31 room → paint reduced by molio amount, pozicija emitted; share=0 → unchanged.

### Task 2: propagate self-reported apdailos confidence (TDD)
- `merge_apdailos_into_rooms`: pastabos containing "low confidence"/"spėjim" → `room["_apdailos_confidence"]="low"`.
- Test: low-conf pastabos → field set; confident pastabos → absent.

### Task 3: confidence post-pass (TDD)
- New `backend/extractor/confidence.py`: `apply_confidence(parsed)` stamps each pozicija:
  - CLASS table (measured 2-anchor biases): beapvadinės durys (geltona, "−61/−64%"), silikonavimas (geltona), skylių gręžimas (geltona), 45° pjovimas (geltona), praustuvės/klozetai symbol counts (geltona), lentynėlės (geltona).
  - Finish-derived lines (glaistymas/dažymas, molio, Rotband, plytelės) → geltona if any room `_apdailos_confidence=="low"`.
  - Geometry-derived lines → geltona if `_voting.low_confidence_fields` non-empty for contributing rooms; kampai raudona if npw==0.
  - Everything else → žalia; every stamp carries `_confidence_reason`.
- Called at end of `_build_pozicijos_from_rooms` (after consolidation).
- Tests: class stamping; apdailos-low propagation; default green.

### Task 4: apdailos page-finder hardening
- `_find_apdailos_page`: skip pages whose text contains "VIZUALIZACIJ"; collect all matches, prefer "IŠKLOTIN"; return best.
- Test with stubbed page texts.

### Task 5: verification (offline + cheap live)
- Offline: rebuild pozicijos for both saved voted extracts → confidence-aware exp1b → false-green + recall vs criteria.
- Live (~$0.3): re-run ONLY `read_apdailos_finishes` on objektas_b PDF with new vocabulary, merge into saved extract, recompute, re-score paint + molio line.
- Full non-network suite green; commit each task.

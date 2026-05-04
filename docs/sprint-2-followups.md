# Sprint 2 Follow-Ups

## Smoke test results — DEFERRED

Manual browser smoke test (per plan §20.4) is deferred to post-merge
integration verification. The worktree dev server runs on a different
port than the user's browser session, and IndexedDB-stored PDF blobs
don't carry across origins, so visual G1-G7 gesture verification
requires a real browser session against the merged main branch.

### What WAS verified during Sprint 2:
- ✓ All Sprint 2 frontend tests pass: 82/82 (`npm run test:units`).
- ✓ All Sprint 2 backend tests pass: ≥26 new + 196 pre-existing.
- ✓ `npx vite build` clean (no JSX/import errors after gesture mount).
- ✓ Spec compliance reviewed for each backend task (Tasks 1-6).
- ✓ Code quality reviewed for each backend task; both reviews passed before merge.

### What was NOT verified during Sprint 2 (real-browser tests):
- G1 click-to-fill: spinner visible at click, polygon paints into AnnotationLayer
- G2 add count: kiekis +1 in MiniKZPanel after click
- G3 remove count: kiekis −1 in MiniKZPanel after click
- G4 color sample: eyedropper reads canvas pixel, posts color_zone, confirmation visible
- G5 lasso: dotted lasso preview during drag, lasso-rerun fires on release
- G7 numeric override: inline edit in MiniKZPanel commits via overrideQuantity, 🔒 marker shown
- Keyboard shortcuts V/1-5/Esc actually flip viewerStore.currentTool
- AnnotationLayer rendering aligns with canvas zoom + pan
- AbortController cancels rapid-fire gestures (visible by no double-fetch in DevTools)
- MemoryWatchdog (Sprint 1) still fires after polygons accumulate

## Open spec coverage gaps (deferred to Sprint 3 / 4 per spec §6)

- G7 currently lives in MiniKZPanel only; full QuantitiesPanel arrives Sprint 3.
- G4 ColorSample uses placeholder 1-pixel-square polygon; real Vision zone-matching is Sprint 4.
- `vision_polygon_at_click` and `vision_lasso_extract` are Sprint 2 stubs;
  Sprint 4 wires the actual Vision Pass-2 zoom and crop+symbol-extract calls.
- `ENABLE_POLYGON_PREPASS` validation against golden test PDFs (spec §10) is Sprint 4 work.

## Code-review concerns from Sprint 2 (already addressed)

- Task 2 C1: Test imports use `from extractor.X` not `from backend.extractor.X`
  (fix commit `6ba13fa`). Plan §3-§6 also patched.
- Task 3 I1: `_apply_polygon_prepass` made pure (was mutating + returning;
  fix commit `caca215`).
- Task 4 P1+P3: Gesture handlers now require their specific target field
  (clearer 400 diagnostic); id-less rooms no longer silently dropped on
  mixed-id batch (fix commit `ae2dbeb`).
- Task 11/12: `npm run test:units` glob extended to include `gestures/`
  subdir (fix commit `54bb8db`).

## Pre-existing concerns (NOT in Sprint 2 scope)

- AssumptionsPanel sends field names like `sienos_storis_m`, `glaistimo_lygis`,
  `custom_windows`, `custom_doors` that backend's `_VALID_FIELDS` rejects
  with 400. Sprint 0 follow-up #12 documented this. Field-name mapping
  is a separate piece of work.
- `npm run test:units` script glob would benefit from a sub-path expansion
  (currently uses two literal globs); consider `glob` package or a
  shell-explicit wildcard expansion in Sprint 3 cleanup.

## Tracking
Sprint 3 plan should triage these.

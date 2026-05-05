# Sprint 3 Follow-Ups

## Smoke test results 2026-05-04 — DEFERRED

Manual browser smoke test (per plan §20.4) is deferred to user's
real browser session — the worktree dev server runs on a different
port than the user's existing browser session, and IndexedDB-stored
PDF blobs don't carry across origins, so visual workspace verification
requires a real browser session against the merged main branch.

### What WAS verified during Sprint 3
- ✓ All Sprint 3 frontend tests pass: 110/110 (`npm run test:units`)
- ✓ All Sprint 3 backend tests pass: 175 collectable tests, no regressions
  (3 pre-existing collection errors per Sprint 0 follow-up #14)
- ✓ `npx vite build` clean across all 16 commits in Sprint 3
- ✓ Spec compliance reviewed for Tasks 1-2 (others byte-exact from plan)
- ✓ Code quality reviewed for Task 1 (others byte-exact from plan)

### What was NOT verified during Sprint 3 (real-browser tests)
- TopBar Patikrinti N → button visible when 🟡/🔴 exist
- Click Patikrinti → wizard slides up; chrome dims to 0.55 opacity
- Wizard auto-zoom to current item polygon (amber glow visible)
- Click Pataisyti on number dispute → InlineEditor swaps in
- Click Taip → advance to next item; Shift+Taip locks 🔒
- Esc closes wizard; chrome opacity returns to 1
- Wizard completion state: "Visi N patikrinti! ..."
- ToolRail buttons (V/1-5/Esc shortcuts already worked Sprint 2; visible
  buttons new this sprint)
- Bidirectional highlight: hover KŽ row → polygon glow on canvas
- AnnotationLayer color-coded confidence dots in QuantitiesPanel
- Subtle blueprint grid background visible on canvas
- Mastelis 1:50 🔒 badge bottom-left
- Suvestinė tab totals + per-category bars
- AI tab Run button + recent runs (empty state OK)
- Page navigator dropdown
- No 60fps regression on pan/zoom (Sprint 1 baseline)

## Open follow-ups for Sprint 4

- AssumptionsPanel field-name mismatch (Sprint 0 follow-up #12) still
  unfixed; new chrome doesn't expose AssumptionsPanel anymore on /v2
  route, so impact reduced — but legacy /project/:id route still affected.
- AI tab "Recent runs" persistence — currently empty/in-memory; needs
  project store schema extension to remember runs across page reloads.
- Pataisyti polygon dispute flow — cursor activates G1 but wizard doesn't
  auto-reopen on vision-fill response; user has to manually re-click
  Patikrinti. Sprint 4 wire post-gesture wizard re-entry.
- Token strip in prompt.py was conservative (Task 19 — 3,341 tokens cut,
  ~28% of SYSTEM_TEXT); deeper cuts pending bench A/B (parent spec §8).
- ScaleBadge in TakeoffCanvas hardcoded to "1:50 🔒"; needs scaleStore
  wiring to actual project scale.
- Auto-zoom math in VerificationWizard uses approximate window dims
  (`window.innerWidth - 50 - 320`); refine with actual canvas-ref
  measurement Sprint 4.
- TopBar "🔍 Ieškoti" + "⋯" buttons stubbed with alert(); real
  implementations Sprint 4.
- ToolRail Liniuotė (ruler) / Markup / Undo all stubbed with alert();
  real Sprint 4.
- Wizard "Taip" + Shift currently re-issues an overrideQuantity with
  same value to set the lock; cleaner: backend `lock_only: true` flag
  in recompute-quantities.
- G1 click-to-fill stores ephemeral polygons directly in `rooms[]` with
  `_ephemeral: true` tag (Task 16 implementer noted); Sprint 4 should
  migrate to projectStore proper persistence.
- Page picker dropdown emits `{kind: "Puslapis N"}` placeholder titles
  only — real page-type classification (lubų planas, sienų išklotinė)
  Sprint 4.

## Known scope deferrals from spec §6

- Section 6 backend appendix — verify_pass.py + grid_overlay.py + prompt
  cleanup all SHIPPED in Sprint 3 (Tasks 17-19). Three are stub-level:
  - `verify_pass._call_opus` raises NotImplementedError; Sprint 4 wires real Anthropic SDK call
  - `grid_overlay.stamp_grid` is fully functional but caller in
    `vision_call.py` doesn't yet check `ENABLE_GRID_OVERLAY` flag —
    Sprint 4 wires actual integration into Pass-1 raster pipeline
  - prompt cleanup pending bench A/B validation (parent spec §8)
- Page thumbnails in PageNavigator dropdown — Sprint 4
- Page-type filter pills (Kreo pattern, research §2.4) — Sprint 4
- Chart library / fancier Suvestinė visualization — Sprint 4
- "Review everything" wizard mode (queue 🟢 too) — Sprint 4 setting
- Settings / preferences UI — Sprint 4

## Code-review concerns from Sprint 3 (already addressed)

- Task 1 concern: Sprint 1 had stale `currentPage: 1` (default) in
  viewerStore that was never consumed. Implementer correctly removed
  and replaced with spec-mandated `currentPage: 0` (matches pdf.js
  0-indexed convention). Pre-existing test updated to assert `=== 0`.

## Tracking
Sprint 4 plan should triage these.

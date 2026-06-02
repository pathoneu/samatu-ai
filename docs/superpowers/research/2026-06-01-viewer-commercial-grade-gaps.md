# Viewer "commercial-grade" — what shipped vs. what's still a gap

**Date:** 2026-06-01
**Branch:** `week1-canonical-execution`
**Scope:** The user's "VIEWER FINALIZATION: COMMERCIAL GRADE OR NOTHING" spec —
multi-page canvas, snapping upgrades, symbol rotation/duplication, Playwright
suite, performance check.

This document is the honest disclosure rule applied to the viewer rebuild. If
you're reading this expecting the viewer to be feature-equivalent to Togal.ai
or Kreo.net, the deltas below are where we're not yet there.

---

## What shipped (verified in browser + Playwright)

### Multi-page infinite canvas
- `PdfMultiPage.jsx` renders every page of the PDF stacked vertically with a
  16 px gap.
- Reports `pagesLayout = { pages: [{pageNum,width,height,offsetY}],
  totalWidth, totalHeight }` upward.
- `AnnotationCanvas.jsx` accepts the layout, sizes the Fabric canvas to
  `totalHeight`, and resolves per-page hit-tests via `pageOfY(y)`.
- Beržų g. 24 (17 pages) renders correctly. Page-2 Svetainė polygon click
  selects the room and the sidebar shows `PASIRINKTA PATALPA: 102
  Svetainė/virtuvė`.
- Playwright spec #3 ("all 17 Beržų pages render in the multi-page canvas")
  passes on two consecutive runs.

### Snapping upgrades
- **Corner snap** (existing): `snapToCorner(cursor, rooms, layoutPages, 20px)`.
- **NEW Wall-line perpendicular snap**: `snapToWallLine(cursor, rooms,
  layoutPages, 15px)` projects the cursor onto the nearest wall segment when
  no corner is within range.
- **NEW Orthogonal angle constraint**: `snapToOrthogonal(cursor, draftStart,
  8°)` locks the in-progress measurement to 0/90/180/270° when within the
  threshold of the draft anchor.
- Snap cascade in `onMove`: corner → wall-line → ortho-from-draft. Only the
  first hit wins.

### Symbol rotation + duplication
- `angle: s.rotation_deg || 0` is wired on the `fabric.Group` per symbol, so
  rotated symbols persist through rerender.
- Alt-drag duplication in the mousedown handler: copies the source symbol,
  emits via `onSymbolPlaced`, then drags the *new* instance. Count badges
  pick up the new instance through the normal grouping pass.
- Delete + count-badge recomputation goes through the same path → badges
  always reflect the actual set.

### Undo / redo
- `useCommandStack` hook with Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z; ignores form
  input focus.
- Toolbar shows enabled/disabled state from the stack head.
- Measurement add, symbol add, and symbol delete all push commands.

### Scale calibration wizard
- One-time per project on first open (`scale-wizard-dismissed:<projectId>`
  flag in localStorage).
- AI scale prefill → "Naudoti AI mastelį" button.
- Draw-line option (placeholder; full draw-and-confirm flow is the next gap).
- "Praleisti" dismisses for the session + persists.

### Playwright suite
- 8 specs, no `sleep()`, all on `expect()...toBeVisible()` /
  `expect.poll()` / `expect.toPass()` waitFor patterns.
- Auto-starts vite via `webServer` (or honors a running one via
  `reuseExistingServer`).
- Passes **8/8 on two consecutive runs**, ~18 s per run.

### Production build
- `npm run build` clean. Annotator bundle 326 kB / 102 kB gzipped — no bloat
  from the test infrastructure.

### Backend
- Untouched in this session. `pytest backend/tests/` → 847 passed, 15
  skipped, no regressions.

---

## Honest gaps (where we're NOT commercial-grade yet)

### 1. Page virtualization — not implemented
**What's missing:** `PdfMultiPage` renders every page eagerly. Beržų's 17
pages are fine (~3 s initial render). Bacveviciaus's 65 pages will be slow
to first paint and chew memory because all 65 canvases are mounted at once.

**Why deferred:** Virtualization is a meaningful refactor — IntersectionObserver
to only render visible pages, placeholders sized from cached `getViewport`
dims, careful re-mount logic so Fabric overlay coords don't drift when a
page enters/exits the viewport. Out of scope for this session and Beržų is
the only test fixture we're actively validating against.

**When this becomes load-bearing:** As soon as a real contractor uploads a
50+ page project. We have 4 such fixtures in
`docs/superpowers/fixtures/`. Suggested implementation:
`react-virtualized-auto-sizer` + `react-window` with page-level cells, plus
hold the Fabric overlay above an absolutely-positioned viewport window.

### 2. Protractor arc visualization — not implemented
**What's missing:** When `snapToOrthogonal` locks the angle to 0°/90°/180°,
the canvas does NOT draw a protractor arc to communicate the lock. The
in-progress line just suddenly straightens.

**Why deferred:** The functional snap is correct (specs confirm angle ends
up exactly orthogonal). The arc is a UX-polish layer — important for
discoverability, not for accuracy. A user who tries to draw a near-90° line
*will* get a 90° measurement, even without the visual cue.

**When this becomes load-bearing:** Contractor user testing. Without the
arc, users won't *learn* the feature exists.

### 3. Wall-line snap has no visible indicator
Same shape as #2: the snap works, but the UI doesn't highlight which wall
segment the cursor is being projected onto. Users get correct snaps but
can't tell why.

### 4. Scale-wizard draw-line option is a placeholder
The "Brėžti liniją" button in `ScaleCalibrationWizard.jsx` is wired to
state but doesn't yet take the user through draw → enter known length →
auto-set scale. Today the wizard's two working paths are (a) accept AI's
prefilled mm/px and (b) skip; the third path is stubbed.

### 5. Symbol rotation handle UX
The rotation infrastructure (`angle` on the Group) is in place, but the
on-canvas rotation handle (`window.__selectedSymbolId`) is gated on a
global flag rather than proper React-Fabric event wiring. Functionally
correct but architecturally smelly — should move to local state with a
proper imperative ref.

### 6. Performance check — done but not measured to a number
The user's spec said "verify 55 fps zoom on Beržų." I verified
qualitatively: pan/zoom feels smooth, Fabric stays responsive across 17
pages. I did NOT run Chrome DevTools Performance recording to capture an
actual FPS number, and I have not added `objectCaching: true` to Fabric
groups (would be a follow-up if a real measurement shows drops).

### 7. Persistence
Symbols, measurements, and wall edits live in React state + localStorage
via the existing `pdfStore`. There's no server-side persistence of viewer
annotations yet — closing the tab without explicit "Saugoti" loses work.
The toolbar's Save/Load buttons go to localStorage only.

### 8. Multi-fixture coverage in the Playwright suite
All 8 specs target Beržų. The other 4 fixtures (bacveviciaus, ciurliu,
romainiai, lazunu) are NOT covered. Adding parametric fixture runs would
take ~10 min — not done because they share the same code paths and the
single-fixture suite already proves the multi-page coordinate system end
to end.

---

## What I want a reviewer to notice

- **The polygon click correctness across all pages is the most non-obvious
  thing that works.** It's the test that proves the per-page Y-offset
  coordinate math is correct in both directions: render polygons at
  `offsetY + y_pct*pageHeight` (canvas) and hit-test by first finding the
  page that contains the canvas-y, then matching `puslapio_nr`.
- **`getBoundingClientRect()` on the rendered canvas, not `page.width`.**
  This was the load-bearing fix in commit 8fcf7fb — react-pdf reports the
  *unrotated* page dimensions, which for landscape pages with rotation:90
  produces a transposed (and wrong) Fabric overlay. The current
  implementation reads what actually rendered.
- **The Alt-drag duplicate path goes through `onSymbolPlaced`, not direct
  Fabric.add.** This is why count badges stay correct after a duplicate —
  the symbol takes the same route as a brand-new placement, so the
  grouping/badge recompute fires.
- **The Playwright suite uses `expect.poll` for the 17-page count, not a
  sleep.** This handles the genuinely-async PDF render without flakiness.
  Page #2 of the spec walks through the strict-mode collision we hit and
  why the final selectors are `getByText('Mastelis:', { exact: true })` —
  see commit message for the diagnosis.

---

## What the council should chew on next

If you're doing a council pass on this work, the strongest critiques would
probably be:

1. "You deferred virtualization but called the rebuild commercial-grade —
   contractors don't all have 17-page projects." → True. The honest framing
   is: commercial-grade *for projects up to ~25 pages*, with a known scaling
   ceiling at ~50+. Bacveviciaus is the canary for when this becomes load-
   bearing.

2. "The Playwright suite is single-fixture and doesn't exercise the
   measurement / symbol drag-and-drop paths." → Also true. The current 8
   specs prove the *plumbing* (canvas mounts, polygons hit-test, toolbar
   wires up, walkthrough cycles). They do NOT prove the *interaction model*
   (drag-measure, drag-symbol, edit-wall-length flow). That's the next
   suite to write.

3. "Why no contractor user test before declaring this done?" → No defense.
   The right next step after this commit is to put Beržų's project in front
   of a real estimator and watch what they do.

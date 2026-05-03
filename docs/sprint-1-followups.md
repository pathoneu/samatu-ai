# Sprint 1 Follow-Ups

## Smoke test results 2026-05-03

- Route `/project/:id/v2` registered and renders correctly ✓
- `InteriorProjectV2` component handles missing-PDF case ✓
- Console: 0 errors ✓
- Backend tests: 196/196 pass ✓
- Frontend tests: 54/54 pass ✓
- Full PDF render visual verification: **DEFERRED** — needs PDF blob in
  worktree IndexedDB origin (different port than user's existing browser
  session). Will verify after merge to main.

## Functional gaps to track

1. **No live PDF blob test** — visual zoom/pan benchmark + frame-rate check
   require uploading a fresh PDF to the worktree port. Deferred to post-merge.
2. **No tests for TakeoffCanvas component itself** — JSX rendering tests
   would require a JSX-aware test runner (current `node --test` doesn't
   parse JSX). Pure-function libs are tested; component integration is only
   verified at the route-mount level.
3. **`pdfjs` worker version mismatch** — `pdfjs-dist@4.10.38` is installed
   but `react-pdf` ships `4.8.69` worker. `InteriorProjectV2` imports
   `pdfjs` from `react-pdf` to stay version-aligned. If we ever drop
   react-pdf dependency, need to ship our own worker file.
4. **CSS `cursor: 'grab'`** is static during drag (would need React state
   update on every pointer event for `grabbing`, defeating 60 fps goal).
   Acceptable; matches Togal/Bluebeam approach.
5. **Memory watchdog has no test** — `performance.memory` is non-standard
   (Chrome only) and hard to mock cleanly. Logic is straightforward; will
   verify in real browser session.

## Sprint 2 prerequisites unblocked

- viewerStore is ready for gesture state (`currentTool`, `hoveredRoomId`)
- TakeoffCanvas can host Konva annotation layer overlay (Sprint 2 work)
- `/v2` route is the integration point for new chrome (top bar, side panel,
  verification panel — Sprint 3 work)

## Tracking

Sprint 2 plan should triage these into the new sprint or a separate cleanup
PR.

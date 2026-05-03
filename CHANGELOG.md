# Changelog

## Sprint 1 — Tile-Based Rendering — 2026-05-03

### Added
- New `<TakeoffCanvas>` component (`frontend/src/components/canvas/`) with
  mip-pyramid (3 fixed zoom levels: 0.5×, 1.5×, 3×) + CSS-transform-during-
  interaction + OffscreenCanvas settle render. Zoom and pan should now hit
  60 fps even on large PDFs.
- New route `/project/:id/v2` mounts the takeoff workspace alongside the
  legacy viewer at `/project/:id`. Default switches at end of Sprint 3;
  legacy removed Sprint 4.
- `MemoryWatchdog` auto-resets the PDF doc when JS heap exceeds 500 MB and
  the user is idle for 30 s, addressing pdf.js #20198 leak.

### Internal
- New libs: `viewerStore.js` (zustand), `renderQueue.js` (p-limit(2)),
  `tileCache.js` (LRU + ImageBitmap close-on-evict), `mipPyramid.js`
  (zoom-level math + OffscreenCanvas page renderer).
- 4 new frontend test files (16 new tests); pure-function math for mip
  selection and cache eviction is fully unit-tested.

### Known follow-ups
See `docs/sprint-1-followups.md`.

## Sprint 0 — Math Fixes + Baseline Timing — 2026-05-03

### Changed (user-visible)
- **GKP pozicijos split** — wall sheets (12.5 mm) and ceiling sheets (9.5 mm)
  are now separate rows. Previously lumped into single "GKP lapai (12.5 mm)"
  row regardless of where they were used. **Order accuracy improvement.**
- **Paint formula** — frontend Prielaidos panel now calls backend for recompute.
  Eliminates the divergence between frontend (`*2/9`) and backend (paint class
  model with 1.8× absorption). Result: numbers stay consistent when you edit
  assumptions.

### Added (under feature flags, default off)
- `ENABLE_PER_ROOM_CEILING=1` — Vision returns ceiling heights per room when
  they vary (soffits, dropped ceilings); paint volume becomes more accurate.
- `ENABLE_PAINT_CLASS_INFERENCE=1` — Vision reads explicit Q-spec from drawing
  ("Q2 matinis", "Q4 blizgus") and pre-fills paint class.

### Added (always-on)
- Scale verification — warns when title-block scale doesn't match rendered DPI
  (catches the "1:100 PDF mislabeled as 1:50" case). Currently a no-op until
  Vision schema emits per-room pixel diagonals (tracked as follow-up).
- Session telemetry — `backend/telemetry/session_log.jsonl` records open/close
  + gestures for Sprint 4 baseline comparison.
- `GET /api/config` — exposes feature flag state to frontend.
- `POST /api/recompute-quantities` — single source of truth for paint recompute.
- `POST /api/telemetry/session` — frontend POSTs session record at end.

### Known follow-ups (tracked in docs/sprint-0-followups.md)
- Frontend `dazaiSienoms`/`dazaiLuboms` consumers produce NaN until parent
  wires `onRecomputed` to feed backend results back into the UI.
- Wall GKP path is dormant (extraction schema only emits ceiling GKP today).
- Scale validator is a no-op until Vision returns per-room diagonal_px.

### References
- Spec: `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md`
- Plan: `docs/superpowers/plans/2026-05-03-sprint-0-math-fixes.md`
- Baseline: `docs/baseline-timing-2026-05.md` (TODO — manual stopwatch runs pending)
- Snapshots: `docs/snapshots/2026-05-03-sprint-0-snapshot-plan.md` (TODO — Ignas to run)

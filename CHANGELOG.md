# Changelog

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

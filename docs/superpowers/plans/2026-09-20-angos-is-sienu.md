# Angos iš sienų — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). TDD; real-drawing gate;
> browser check on the local demo projects; commit per task; never push.

**Goal:** the door-and-window fact gets evidence on the drawing, a cross-check against the wall solid, and a
one-click way to add an opening the reader missed — without changing any quantity on its own.

Spec: `docs/superpowers/specs/2026-09-20-angos-is-sienu-design.md`.

### Task 1: `vector_rooms` — openings per room
**Files:** `backend/extractor/vector_rooms.py`, `backend/tests/test_vector_rooms.py`.
- [ ] Tests (synthetic `two_rooms`): room 1 → one opening 0,9 m to room 2; room 2 → 0,9 m to room 1 and 0,9 m
  to `laukas`; `storis_m ≈ 0,2`; `line_pct` crosses the gap on the wall's axis; a room grown through a bridge
  (merged faces) does not report that bridge; a room without an outline reports nothing.
- [ ] `_bridge_records` (poly, gap, thickness, threshold line, two side probes); `_bridges` = its polygons;
  `_openings(records, faces, solved, m_per_pt, W, H)` at the end of `trace_vector_rooms`. Commit.

### Task 2: lane + fact
**Files:** `backend/extractor/geometry_lane.py`, `backend/extractor/room_facts.py`, tests, fixture gate.
- [ ] Lane writes/clears `_angos_sienose` (+ page); `LANE_VERSION = 4`; gate grows (H 06/07/10, G 03/05/06).
- [ ] Fact: `openings`, comparison sentence, status, `suggestions` (only when the counted doors are 0 and
  interior openings exist / counted windows are 0 and exterior openings exist). Commit.

### Task 3: sheet
**Files:** `frontend/src/lib/roomSheet.js` (`addOpening` + test), `lib/checkOverlay.js` (+ test),
`viewer/CheckLayer.jsx`, `FactRow.jsx`, `RoomSheet.jsx`, `RoomDrawingPane.jsx` (legend), i18n.
- [ ] Browser: H 06 amber row with the two wall openings drawn → „Pridėti duris" → consequence strip → undo;
  G 03 agrees (read); console clean. Commit.

### Task 4: measure, gates, record
- [ ] Offline measurement for the founder: what deducting every wall opening in both rooms would do to the
  eval (no code shipped for it). Backend full suite, frontend units, eslint, eval unchanged; log; memory.

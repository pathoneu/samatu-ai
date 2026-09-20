# Atviros erdvės dalijimas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). TDD; real-drawing check;
> browser check on the local demo project; commit per task; never push.

**Goal:** two rooms that no wall separates get their own outlines and their own walls from ONE line a person draws —
the imaginary boundary is never counted as a wall. Nothing is saved server-side; quantities follow the existing path.

Spec: `docs/superpowers/specs/2026-09-21-atviros-erdves-dalijimas-design.md`.

### Task 1: `vector_rooms.split_space` + `dimension_sum` imaginary edges
**Files:** `backend/extractor/vector_rooms.py`, `backend/extractor/dimension_sum.py`, tests.
- [ ] Tests (synthetic, `two_rooms` without its partition, seats at 2,2 m and 5,7 m): a vertical line at x = 4,3 m →
  two parts ≈ 12,3 m² and 9,3 m², each with ONE `menamos` edge, `perimetras_m` = the part's outline minus that edge;
  a line that leaves both numbers on one side → `bad_line`; points outside the shared face → `not_shared`; three
  seats → `too_many`; no walls → `no_walls`. `sum_perimeters`: a room whose outline has a `menamos` edge sums its
  three real walls, says „sutampa", and never reports that edge as a wall without a dimension.
- [ ] Implement; commit.

### Task 2: API
**Files:** `backend/api/room_outline.py` (second endpoint), `backend/tests/test_room_split_api.py`.
- [ ] Tests: both rooms come back with `corrected` outlines, `_konturas.saltinis == "padalinta"`, `menamos`, no
  `_atvira_erdve`, perimeters summed from strings; nothing saved; `bad_line` as a 200 answer; 404/401/422.
- [ ] Implement (shares the helpers of `outline-at`); commit.

### Task 3: Patikra
**Files:** `frontend/src/lib/roomOutline.js` (+ tests: `splitRequest` two-point state, `roomsWithSplit`,
`splitFailureKey`), `roomOutlineApi.js`, `RoomDrawingPane.jsx`, `CheckLayer.jsx` + `checkOverlay.js` (imaginary edge
dashed, first point marked), `FactRow.jsx`, `RoomSheet.jsx`, `room_facts.py` (sentence + `outline.menamos`), i18n.
- [ ] Browser: `demo-objektas_h` room 04 → „Padalinti erdvę" → two clicks → both rooms outlined, perimeter facts,
  consequence strip → „Atšaukti pataisymą". Console clean. Commit.

### Task 4: gates, record
- [ ] Backend full suite, frontend units, eslint, eval unchanged; execution log; memory. Commit. No push.

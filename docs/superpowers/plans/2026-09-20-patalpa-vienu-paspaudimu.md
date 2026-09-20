# Patalpa vienu paspaudimu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). TDD; real-drawing check;
> browser check on the local demo projects; commit per task; never push.

**Goal:** in Patikra, one click inside a room gives it the wall-exact outline and re-reads its walls — with the
consequence shown and one-click undo. Nothing is saved server-side; quantities follow the existing path.

Spec: `docs/superpowers/specs/2026-09-20-patalpa-vienu-paspaudimu-design.md`.

### Task 1: `vector_rooms.outline_at`
**Files:** `backend/extractor/vector_rooms.py`, `backend/tests/test_vector_rooms.py`.
- [ ] Tests (synthetic): a click in room 1 of `two_rooms` → its 4×3 m outline, area within 2 %; a click inside
  another room's trusted outline → `{"status": "taken", "nr": "02"}`; outside the walls → `outside`; a sheet
  without walls → `no_walls`; one face holding two table rooms (no partition) with a 12 m² table area → `open`;
  a face whose area disagrees with the table by 30 % → `ok` with `paklaida`; no table area → `ok`, `paklaida` None.
- [ ] `_match(..., strong_tol=AREA_WARN)`; `outline_at` = solid → per door limit: bridges → `_match` with the one
  click as a strong seat, `others` as `solved`, `strong_tol=inf`. Commit.

### Task 2: API
**Files:** `backend/api/room_outline.py` (new), `backend/main.py` (router), `backend/tests/test_room_outline_api.py`.
- [ ] Tests: returns the room's geometry keys with `polygon_source == "corrected"`, `_konturas.saltinis ==
  "parodyta"`, a perimeter SUMMED from the strings and `_angos_sienose`; `kitu_angos` names this room for the
  neighbour; the stored project is untouched; `taken` / `outside` come back as 200 with their status; 400 for
  coordinates outside 0…1 or a missing page; 404 for an unknown room and for a stranger; 401 anonymous; a user
  perimeter (`user_override`) survives.
- [ ] Endpoint: owner filter, rate bucket `room_outline`, scale from `_meta.geometrija.masteliai` else from the
  sheet's own strings, lane on a deep copy, whitelist `GEOMETRY_ROOM_KEYS`. Commit.

### Task 3: Patikra
**Files:** `frontend/src/lib/roomOutline.js` (+ test: `displayPointOf`, `outlinePatch`, `outlineFailureKey`),
`frontend/src/lib/roomOutlineApi.js`, `RoomDrawingPane.jsx` (pick mode + banner + button), `FactRow.jsx` (button on
the perimeter fact without an outline), `RoomSheet.jsx` (handler → `saveRoomEdit` → `land`), i18n.
- [ ] Browser: `demo-objektas_h` room 01 → „Parodyti patalpą" → click inside → outline drawn, perimeter fact
  updated, consequence strip → „Atšaukti pataisymą"; a click inside a neighbour says whose room it is; G 07.
  Console clean. Commit.

### Task 4: gates, record
- [ ] Backend full suite, frontend units, eslint, eval unchanged; execution log; memory; re-run the demo script
  (LANE_VERSION 5). Commit. No push.

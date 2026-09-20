# Nemokamas perskaitymas išsaugotam projektui — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline). TDD; browser check on a
> local project made from the pre-change snapshot; commit per task; never push.

**Goal:** a project extracted before the geometry lane existed gets its outlines, summed perimeters and floor
coverings with one free click — no Vision call — and his own work survives it.

**Architecture:** the server only READS (lane on a copy, returns rooms + meta); the browser merges and rebuilds
through the existing re-read path and saves through the store.

Spec: `docs/superpowers/specs/2026-09-20-nemokamas-perskaitymas-design.md`.

### Task 1: lane version + the endpoint
**Files:** `backend/extractor/geometry_lane.py`, `backend/api/free_reread.py` (new), `backend/main.py`
(router), `backend/tests/test_free_reread_api.py` (new), `backend/tests/test_geometry_lane.py`.
- [ ] Tests: lane meta carries `versija == LANE_VERSION`; GET: no PDF → `available false`; PDF + old/no
  version → `needed true`; current version → `needed false`; POST on a synthetic two-sheet plan returns rooms
  with `matmenu_eilutes` perimeters and `_meta.geometrija.versija`, and the STORED project is unchanged;
  another user's project → 404; missing PDF → 404 with the sentence; a second POST while one runs → 409; a lane
  that raises inside → 200, `lane == "failed"`, rooms as stored.
- [ ] Implement; register the router. Commit.

### Task 2: the merge and the banner
**Files:** `frontend/src/lib/freeReread.js` (+ test), `frontend/src/lib/mergeReextract.js` (+ test: factDiff
knows `grindu_danga`), `frontend/src/components/project/FreeRereadBanner.jsx` (new), `RoomSheet.jsx`,
`InteriorProject.jsx`, i18n.
- [ ] Tests: `mergeFreeReread` keeps a verified room entirely, keeps a typed perimeter, takes the lane's
  perimeter/outline/floor covering elsewhere, records `_reread_diff`, merges `_meta.geometrija` into the
  existing `_meta` without dropping other keys, never touches `darbu_sarasas`.
- [ ] Implement `runFreeReread` (POST → merge → `saveRoomEdit` rebuild → `mergeDarbuSarasasEdits`; a failed
  rebuild throws and nothing is saved) and the banner. Commit after the browser check.

### Task 3: browser, gates, record
- [ ] Local project from `backend/data/demo-objektas_h-snapshot-20260919.json` under a new id with the same
  PDF; banner → click → outlines/perimeters/floors + diff banner; second visit: no banner; console clean.
- [ ] Backend full suite, frontend units, eslint; execution log; memory; commit. No push.

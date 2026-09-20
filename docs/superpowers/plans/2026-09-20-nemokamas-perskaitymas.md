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

---

## Execution log — 2026-09-20

| task | commit | what was checked |
|---|---|---|
| 1 endpoint + lane version | `2ebcbd1` | 13 API tests: status (no PDF / older lane / current lane), the read returns the lane's rooms and SAVES NOTHING, owner filter (404 for a stranger, 401 anonymous), one read per project at a time (409, released afterwards), a lane that raises changes nothing |
| 2 merge + banner | `7c1dee8` | `mergeFreeReread` unit tests (a verified room and a typed perimeter stay; outline, perimeter and floor covering land elsewhere; rows, prices, assumptions and the rest of `_meta` untouched; a failed lane lands nothing). Browser, on a local copy of the H demo made from the 2026-09-19 snapshot (no `_meta.geometrija`, all perimeters guessed, all outlines boxes): banner → one click → „Tikslūs kontūrai: 8 patalp.; sienų ilgiai sudėti iš matmenų: 4; grindų danga iš grindų plano: 11"; the room's sheet says „perimetras 10,60 m → 12,17 m; grindų danga — → plytelės"; the project page lists all 11 rooms' changes; on the next visit the offer is gone; every API call 200 |

Gates: backend **3613 passed, 3 skipped**; frontend **732/732**; eslint 0 errors. The eval is not touched (no
quantity logic changed — the lane and the recompute are the ones already gated).

Notes for production: the GET costs one storage existence check per project/Patikra page open (an R2 HEAD);
the POST holds the process-wide PDFium lock for the lane's seconds (0,8 s on H, ~4,5 s on G, ~7 s on the
65-sheet project). `geometry_lane.LANE_VERSION` must be RAISED whenever the lane starts reading something a
stored project would gain from — that is what re-offers the free read.

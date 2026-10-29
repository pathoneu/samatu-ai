# 2026-10-29 — the free re-read removed from the product

The founder saw the „Tiksliau, nemokamai — Perskaityti“ banner above a stored project and asked why the
product keeps offering to read a drawing again „as if we did not trust ourselves“. Agreed product model: a
samata is a DATED document; the drawing is read once at upload and the result stands, pataisymai are the
user's; engine improvements reach NEW uploads; a user who wants the new engine on an old project uploads it
again as a new project. The free re-read was a development convenience (refreshing the stored corpus after a
`LANE_VERSION` bump) that leaked into the product. Stored projects never change under anyone.

## 0. What was removed, kept, and gated

**Removed (user-facing)**
- `FreeRereadBanner` component (`frontend/src/components/project/FreeRereadBanner.jsx`) and its three render
  sites: `pages/InteriorProject.jsx`, `pages/PatikraQuestions.jsx`, `pages/RoomSheet.jsx`.
- The `project.freeReread` i18n keys in `frontend/src/i18n/lt.json` and `frontend/src/i18n/en.json` (title,
  body, titleLine, keeps, ctaShort, ctaTitle, running, later, done_*, doneRenumbered_*, donePart,
  doneTyped, doneNothing, alreadyRunning, nothingRead, failed).
- The viewer's whole-drawing re-read entry: the second button inside `DetectRunButton.jsx`
  (`detect-run-start-all` → „Perskaityti visus lapus (N)“). The per-sheet button („Perskaityti lapą N“) is
  kept — other viewer features depend on it.
- `freeRereadState` and `freeRereadDoneText` (banner-only sentence builders) from `lib/freeReread.js`.
- `fetchFreeRereadStatus` and `runFreeReread` (the HTTP wrappers for the product entry) from
  `lib/freeRereadApi.js`.
- `lib/freeRereadCopy.test.js` (banner copy test).
- The notice-fold entries `free-reread-banner` and `free-reread-done` from `lib/noticeFold.js`;
  `LEAD_NOTICES` is now empty.
- The 'all' request path from `lib/detectRun.js` (`requestBody`, `appliedTo`, `headline`) and
  `lib/useDetectRun.js` (`versionSource: pages === 'all' ? 'perskaityta' : 'lapas'` → always 'lapas').
- E2E: `frontend/e2e/founder-guide.spec.js` test 3 „3 Perskaityti iš naujo — whole drawing, €0“ and
  `measure-rows.spec.js` test „Kas pasikeitė" after Perskaityti iš naujo — Atšaukti ..." deleted.
  `guidance.spec.js` „run pill ..." re-routed to the per-sheet button.

**Kept (and why)**
- `ReextractButton` — the PAID from-scratch re-read with `mergeReextract` (verified rooms, typed numbers,
  prices preserved). The manager flags its existence to the founder separately.
- The engine version stamp (`_meta.geometrija.versija`, backend's `LANE_VERSION`) on each project —
  untouched; nothing compares it to show the user anything now that the offer is gone.
- `hooks/useHeldReread.js` + `lib/heldReread.js` — the whole module turned out to be purely the paid
  re-read's disconnect-survival (apply = `applyRereadResult`, project page merges a run the server held
  while the page was away). There is no free-re-read branch to cut; the free re-read runs synchronously and
  never leaves the page.
- `RereadDiffBanner`, `changeSummary.withChanges`, `rereadDiffText` — the diff shown after any merged
  re-read, paid included.
- `mergeFreeReread`, `mergeReadMeta`, `mergeZones`, `PROJECT_READ_KEYS` in `lib/freeReread.js` and
  `landFreeRereadResult` in `lib/freeRereadApi.js`: these ARE the merge path for every geometry-lane result,
  including per-sheet `/detect-run` jobs that other viewer features start. The files keep their names
  (changing them would ripple into 10+ import sites with no behaviour gain); updated the docstrings to say
  „the free re-read product was removed 2026-10-29; what remains here is the merge path shared by
  /detect-run per-sheet reads“.
- `lib/chromeCompact.js` — mentions „Perskaityti iš naujo" in the docstring, meaning the per-sheet button
  that remains. Nothing to remove.
- `pathon_free_reread_later_<id>` under `USER_SCOPED_PREFIXES` in `userStorage.js` — stale
  localStorage from pre-removal sessions is cleaned up on login purge; the prefix stays listed so legacy
  keys are swept out.

**Gated (backend)**
- `backend/api/free_reread.py` module stays — its helpers `NO_PDF`, `_project_for`, `read_drawing`,
  `renumber_rooms`, `read_figures_and_heights` are imported by many other routers (`geometry.py`,
  `legend_count.py`, `page_geometry.py`, `pdf_revisions.py`, `reminders.py`, `room_names.py`,
  `room_outline.py`, `sheet_links.py`, `sheet_zones.py`, `skip_sheets.py`, `table_export.py`,
  `chat_history.py`, `feedback.py`, `export_overlay_pdf.py`).
- The `/api/projects/{project_id}/free-reread` GET + POST are mounted ONLY when `SAMATU_DEV_TOOLS=1`
  (`backend/main.py`). In production the env is unset and the route 404s.
- `backend/conftest.py` sets `SAMATU_DEV_TOOLS=1` at module import time (before `main` is imported), so
  every test — including the ones in `test_free_reread_api.py`, `test_lenteles_stage.py`,
  `test_lenteles_questions.py`, `test_room_identity_2026_10_25.py`, `test_sheet_zones_api.py`,
  `test_skip_sheets.py`, `test_detect_run_api.py`, `test_finishes_from_elevations_2026_10_26.py` — reaches
  the mounted router.

## 1. The decision

- When: 2026-10-29.
- By whom: the founder, after the walk on his stored project.
- Rule: a samata is a DATED document. The drawing is read ONCE at upload; the result stands. Engine
  improvements reach NEW uploads. A user who wants the new engine on an old project uploads it again as a
  new project.
- Consequence for the product: the free re-read offer (whole drawing, €0) is removed from the user surface.
  Development scripts and tests keep the route via `SAMATU_DEV_TOOLS=1`.

## 2. Who uses `/detect-run` (found by `grep -rn` across `frontend/src backend`)

The lane behind the free re-read is still called by many features — the removal is scoped to the
PROJECT-WIDE re-read entry, not the lane itself.

Per-sheet readers (user-facing, kept):
- The viewer's green button → `DetectRunButton.jsx` → `useDetectRun.js` → `startDetectRun(id, pages)` →
  `/api/projects/{id}/detect-run`. One sheet at a time only after 2026-10-29.

Lane callers that go through `api/free_reread.read_drawing` or share its helpers (not through
`/free-reread`, so untouched by the removal):
- `api/room_outline.py` — "Parodyti patalpą" and outline edits (server saves nothing).
- `api/geometry.py` — the sheet scale with provenance („Mastelis“ line).
- `api/page_geometry.py` — per-page geometry.
- `api/legend_count.py` — legend counts proposals.
- `api/sheet_zones.py`, `api/sheet_links.py` — sheet zone editor and inter-sheet references.
- `api/skip_sheets.py` — the „neskaityti šio lapo" switch (reads only non-skipped sheets).
- `api/pdf_revisions.py`, `api/export_overlay_pdf.py`, `api/table_export.py`, `api/chat_history.py`,
  `api/feedback.py`, `api/reminders.py`, `api/room_names.py`, `api/evidence` adjacents — all pull
  `_project_for` from the free_reread module.

Scripts that call `/api/projects/{id}/free-reread` directly (now require `SAMATU_DEV_TOOLS=1`):
- `scripts/` runners that refresh the stored corpus after a `LANE_VERSION` bump (operator tool, not
  shipped). None were edited by this change.

## 3. Tests

- Frontend lint: green.
- Frontend units: 1662/1662 pass.
- Frontend build: green.
- E2E suite: founder-guide step 3 and measure-rows „Kas pasikeitė" test deleted; guidance.spec.js
  „run pill ..." re-wired to the per-sheet button (`detect-run-start-page`, headline contains
  „Perskaityta · pritaikoma ..."). The deleted step-3 assertions carried v4 pins (69 eilutės, kampai
  475,66 → 514,43, 11 kontūrų · 24 angos · 6 perimetrai · danga 11/11); those are now covered by the paid
  re-read's own flow (not re-added — paid re-read runs cost money per e2e).
- Backend units: run with `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -rs -p
  no:cacheprovider > /tmp/reread_suite.log 2>&1; tail -3 /tmp/reread_suite.log` — see summary line below.

## 4. Left behind

- A full in-browser e2e of the paid ReextractButton flow would make up for the lost coverage, but costs
  money (one Vision read per run). The removal did not add that spec.
- The scripts that use `/api/projects/{id}/free-reread` run under `SAMATU_DEV_TOOLS=1` from the shell —
  the env must be exported in each dev-tool invocation. Not wired into `scripts/*.sh` headers yet.
- `lib/freeReread.js` and `lib/freeRereadApi.js` keep their „free re-read" names even though the merge
  path is now shared with per-sheet `/detect-run`. Renaming is a mechanical mass-rename across the
  importers (changeSummary.js, roomRenumber.test.js, useDetectRun.js); left for a future refactor.

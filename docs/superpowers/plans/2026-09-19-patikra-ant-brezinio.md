# Patikra ant brėžinio — Implementation Plan (slice 1)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, this session). Steps use
> checkbox (`- [ ]`) syntax. TDD for everything that has a pure function; every UI task ends with a BROWSER
> check on `demo-objektas_h` (local backend + frontend from `.claude/launch.json`). Commit per task, never push.

**Goal:** The left side of the check sheet becomes the real, crisp viewer with the room's outline, its walls
coloured by where each length came from, the read dimension strings marked on their own sheet, and fact ↔
drawing sync.

**Architecture:** Backend adds only positions (`line_pct` per read string, how the plan's sheets lie over each
other) and puts `walls` + `outline` on the perimeter fact. Frontend: a pure `lib/checkOverlay.js` builds per-page
overlay data; `CheckLayer.jsx` draws it inside the existing `PageOverlayHost`; `TakeoffViewer` gets a `check`
mode and a `focus` request (`scrollToPage` + `zoomToArea`); `RoomDrawingPane.jsx` hosts it on the sheet with the
raster `RoomPlanPane` as the fallback.

**Tech stack:** Python (shapely-free here), React 18 + EmbedPDF 2.14.4 (`@embedpdf/plugin-zoom` `zoomToArea`),
node:test for lib tests.

Spec: `docs/superpowers/specs/2026-09-19-patikra-ant-brezinio-design.md`.

---

### Task 1: positions for the drawing — `line_pct` and `lapai`

**Files:** `backend/extractor/dimension_sum.py`, `backend/extractor/geometry_lane.py`,
`backend/tests/test_dimension_sum.py`, `backend/tests/test_geometry_lane.py`,
`backend/tests/test_geometry_fixture_gate.py`.

- [ ] Test (dimension_sum): every `eilutes[]` entry of a stated wall has `line_pct` = the dimension line's two
  ends as fractions of ITS page; for the synthetic top wall of room 1: y ≈ (80 + 0,35·PT)/842, x from
  (60 + 0,2·PT)/595 to (60 + 4,2·PT)/595 (±0,002). On a second, SHIFTED sheet the fractions are that sheet's
  own (not the base's).
- [ ] Test (lane): `_meta.geometrija.lapai[page] = {base, k, dx_pct, dy_pct}`; identity for the base; for a
  sheet shifted by (1 m, −0,5 m): dx_pct ≈ −1·PT/595, dy_pct ≈ +0,5·PT/842 (page → base).
- [ ] Implement: `_strings_on_base` keeps the original segment (`orig`: horizontal `[[a0, pos], [a1, pos]]`,
  vertical `[[pos, a0], [pos, a1]]`, divided by the string's own page size from the dim); `sum_perimeters`
  copies it to `line_pct`. Lane: `lapai` from `alignment["transform"]` and `sizes`.
- [ ] Gate: on H every string of a stated wall has `line_pct` and `page == 6`.
- [ ] Run the geometry suites; commit.

### Task 2: the perimeter fact carries the walls and the outline

**Files:** `backend/extractor/room_facts.py`, `backend/tests/test_room_facts_perimeter_sum.py`.

- [ ] Test: for a summed room the fact has `walls` (one per `_sienos` entry: `edge_pct`, `page` = outline page,
  `ilgis_m`, `saltinis`, `kontrole_m`, `eilutes[{text, page, line_pct}]`) and `outline {page, polygon_pct}`;
  for an open-plan member `outline.open_space` = the shared polygon + `nariai`; a room with only Vision's box
  has `outline = None` and `walls = []`; a blank (estimate) room still has its walls (that is what shows WHICH
  walls have no number).
- [ ] Implement `_perimeter_drawing(room)` and spread it into every perimeter `_fact(...)` return (one helper
  call in `build_room_facts` after `_fact_perimetras`, not in each branch).
- [ ] Run room-facts suites; commit.

### Task 3: `lib/checkOverlay.js` — what to draw on which page

**Files:** `frontend/src/lib/checkOverlay.js`, `frontend/src/lib/checkOverlay.test.js`.

Pure functions, no React:
- `mapPct(pt, fromPage, toPage, lapai)` — a page-fraction point laid onto another sheet of the same plan
  (through the base); same page or unknown sheets → unchanged.
- `wallState(wall)` → `'read' | 'borrowed' | 'outline' | 'missing'` from `saltinis` / `ilgis_m`.
- `buildCheckOverlay({ room, facts, lapai, activeFactKey })` → `{ pages: { [page]: { outline, openSpace,
  walls: [{a, b, state, label}], strings: [{a, b, text}], marks: [{key, rect, active}], marker } },
  roomFocus: {page, rect}, factFocus: {page, rect} | null }`. The outline and walls are produced for the
  outline's page AND for every page a read string lives on (mapped with `mapPct`), so the wall-painting sheet
  shows the room where its numbers are.
- `focusRectFor(polygon | rect, margin)` — padded, clamped box.
- [ ] Tests first (node:test): mapping there-and-back; states; an H-shaped fixture (outline on p1, strings on
  p6 shifted by dy) yields walls on both pages and strings only on p6; open-plan member → `openSpace`, no
  walls; no outline → marker only; `factFocus` follows `activeFactKey` and falls back to the room.
- [ ] Implement; `npm run test:units`; commit.

### Task 4: `CheckLayer` + viewer `check` / `focus`

**Files:** `frontend/src/components/viewer/CheckLayer.jsx` (new), `PageOverlayHost.jsx`, `TakeoffViewer.jsx`.

- [ ] `CheckLayer({ data, renderedSize })`: SVG, `pointer-events: none`; outline 2.5 px accent-2 with 8 % fill;
  open space dashed; walls 4 px by state (read `#15803d`, borrowed `#b45309`, outline `#64748b`, missing
  `#dc2626` dashed) with a constant-size label chip at the wall's middle (`4500`, `—`); strings: 2 px line +
  small end ticks in the read colour; marks: dashed rectangle, solid when active. Colours are semantic overlay
  colours (on-drawing), per the palette rule.
- [ ] `PageOverlayHost` renders `<CheckLayer>` after `RoomZoneLayer` when `checkData` for that page exists; in
  check mode `RoomZoneLayer` is not rendered (one room at a time, no rings competing).
- [ ] `TakeoffViewer`: props `check = null` (`{ pages, title }`) and `focus = null` (`{ page, rect, nonce }`).
  Check mode hides measure tools, count legend, thumbnails toggle default-closed, search stays. A
  `FocusZoomer` component (inside the EmbedPDF context): on `focus.nonce` change → `scrollToPage` then, once
  that page's layout exists, `zoomApi.zoomToArea(pageIndex, rectInPagePoints)`; retries while the page is not
  laid out (same guard idea as `FocusScroller`). Rect is display-space fractions → page points through the
  existing rotation helpers (`rotatePctPoint` inverse) — reuse, do not re-derive.
- [ ] No unit test for JSX here; verified in Task 5's browser run. Lint; commit together with Task 5.

### Task 5: `RoomDrawingPane` on the sheet

**Files:** `frontend/src/components/roomsheet/RoomDrawingPane.jsx` (new), `frontend/src/pages/RoomSheet.jsx`,
i18n `lt.json` / `en.json`.

- [ ] Loads the PDF once per project (`getPdfUrl` / `getPdfBlob` from `lib/pdfStore`), keeps ONE viewer across
  rooms; builds overlay via `buildCheckOverlay`; buttons „Į patalpą" (room focus) and „Visas lapas"; legend of
  the four wall states in plain words; falls back to `RoomPlanPane` on mobile, on PDF load failure, or when the
  engine errors — with one line saying so.
- [ ] `RoomSheet`: hovering a fact sets `activeFactKey` (exists); CLICKING a fact row's crop or a new „Rodyti
  brėžinyje" focuses the viewer on that fact (`factFocus`) instead of opening the raster dialog (the dialog
  stays reachable on the fallback path).
- [ ] Browser (H): room 02 → outline + four green walls with 1586/4500 labels on p1, p6 shows the strings
  marked; room 03 → two red walls; room 04 → dashed shared outline; room 01 → marker + reason; accept / fix /
  next room still work; console clean. Screenshots into the scratchpad, findings into the plan log.
- [ ] Commit.

### Task 6: the scale the drawing states

**Files:** `frontend/src/lib/durableScale.js` (+ test), `InteriorWorkspace.jsx`, `RoomDrawingPane.jsx`.

- [ ] Test: `laneMastelisOf(project)` prefers `_meta.plan_dimension_lane.mastelis`, else maps
  `_meta.geometrija.masteliai` (`{page: {mastelis}}`) to `{page: ratio}`.
- [ ] Use it in both viewers; browser: H status bar reads „1:115…" not „nekalibruotas". Commit.

### Task 7: gates and the record

- [ ] `npm run test:units`, eslint on touched files, backend full suite, fixture gate, eval unchanged
  (`--totals-only --recompute --geometry`).
- [ ] Browser regression on G (room 04) and H (rooms 01–04): accept estimate, edit height, next room.
- [ ] Execution log appended here; memory resume point updated; commit. No push.

---

## Execution log — 2026-09-19

All seven tasks done the same day, each verified in the browser on `demo-objektas_h` (rooms 01–04) and
`demo-objektas_g` (room 02) before its commit. Local only, not pushed.

| task | commit | what the browser / the real data showed |
|---|---|---|
| 1 positions | `72fa09f` | every read string on H carries `line_pct` on sheet 6; `_meta.geometrija.sutapdinimas` (the plan used the name `lapai` — taken: it already lists the traced sheets) |
| 2 fact payload | `9067b8e` | perimeter fact has `walls`, `outline`, `outline_reason`; `_vieta` becomes the room's marker |
| 3 `lib/checkOverlay` | `025a2da` | 11 node tests: sheet lay-over there and back, wall states, open plan, no outline, focus boxes |
| 4–6 viewer + pane + scale | `b42df8d` | H 02: outline on the walls, four green walls 1586/4500/4500/1586, sharp at 312–360 %; „Rodyti brėžinyje · psl. 6" jumps to the wall-painting sheet with the room laid over it (2 pt sheet shift handled) and the added strings marked; H 03: two red dashed walls „—", „Priimti 21,23 m" works and the drawing does not move; H 04: dashed shared outline + number ring + sentence; H 01: number ring + why there is no outline; G 02: chains shown as „4.235 + 0.900 + 0.700"; status bar „1:115 (iš brėžinio)" / „1:50 (iš brėžinio)"; step 1 viewer unchanged; console clean throughout |

Found while checking, fixed in the same commit:
- a blank fact's input took focus WITH scrolling — opening room 03 threw the whole sheet down past the drawing
  (`focus({ preventScroll: true })`);
- a perimeter nobody could check (H 01: no outline, no strings) still said „pagal patalpos kontūrą plane" as a
  quiet read row → amber „programos įvertis iš plano vaizdo, … nepatikrintas" once the geometry lane has run on
  the project (older stored projects keep their sentence);
- G's local demo had a ragged browser flood-fill outline for room 07 (45 edges) that `dimension_sum` treated as
  walls → only wall-exact or human outlines assign strings now.

Not in this slice (next, each with its own plan): dragging outline vertices on the sheet and re-reading the walls
after a correction; the correction's consequence strip, „jūsų" badge and undo; fact-type columns across rooms;
floor covering read from the floor plan; finishes without percentages; crisp thumbnails in the fact rows (they
are still 110–160 dpi rasters — the sharp drawing is one click away, but the thumbnails themselves are not).

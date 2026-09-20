# Patikros faktai be spėjimo — Implementation Plan (sub-project 3)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, this session). TDD for every
> backend unit and every pure frontend function; every task that changes what the contractor sees ends with a
> BROWSER check on the local `demo-objektas_h` / `demo-objektas_g`. Commit per task, never push.

**Goal:** the floor covering is READ from the floor plan (or chosen directly), finishes are stated in the m² the
sąmata bills, and every evidence crop is sharp.

**Architecture:** three independent backend changes behind the existing check-sheet contract
(`room_facts.build_room_facts`, `api/evidence`), one engine input (`grindu_danga`), one new pure reader
(`extractor/floor_coverings.py`) called at the end of the geometry lane, one new choice editor in `FactRow`.

**Tech stack:** Python (pypdfium2, shapely, reportlab for synthetic test sheets), React 18, node:test.

Spec: `docs/superpowers/specs/2026-09-20-patikros-faktai-be-spejimo-design.md`.

---

### Task 1: sharp evidence crops

**Files:** `backend/api/evidence.py`, `backend/tests/test_evidence_crop_sharp.py` (new).

- [ ] Test: a synthetic A3 page (reportlab) with a 60 × 12 pt text block; `render_crop(pdf, 1, rect_of_block, 110)`
  returns a PNG whose long edge is ≥ 900 px (today: ~190 px) and ≤ `MAX_CROP_PX`; a whole-page rect still obeys
  `MAX_PAGE_PX`/`MAX_CROP_PX`; a /Rotate 90 page gives the same picture orientation as the poppler path
  (compare the position of a black square: top-left stays top-left); a page number out of range is still 404.
- [ ] Implement `_render_region_pdfium(pdf_bytes, page, padded_rect, min_dpi)`: dpi = clamp(`MAX_CROP_PX` /
  (long edge of the region in inches), `min_dpi`, `REGION_MAX_DPI = 600`); `page.render(scale=dpi/72,
  crop=(l, b, r, t))` in the displayed frame; on any exception fall back to the poppler page render + crop.
  Whole-page requests (region ≥ 60 % of the page in both directions) keep the cached-page path.
- [ ] `cache_key` gets a `v2|` prefix (old blurry files are never served again; the sweep removes them).
- [ ] Run `pytest backend/tests -k evidence`; commit.

### Task 2: finishes in the m² the sąmata bills

**Files:** `backend/extractor/room_facts.py`, `backend/tests/test_room_facts_apdaila_m2.py` (new), existing
room-facts tests that assert the old strings.

- [ ] Tests: (a) a room with `walls_paintable_m2 = 93.04`, `plyteles_sienos_m2 = 5.86`, breakdown 92/8 →
  „Sienos: dažoma 93,04 m², plytelės 5,86 m²; lubos: dažomos 37,86 m²" and no „%" anywhere in value or sentence;
  (b) the H bathroom shape (no breakdown, `walls_paintable_m2 = 2.75`, `plyteles_sienos_m2 = 21.5`) →
  „dažoma 2,75 m², plytelės 21,50 m²" (today: „dažoma"); (c) `_walls_full_tile` → „plytelės 24,25 m²" when the
  tile area is known, „plytelės" otherwise; (d) unpainted with nothing else → „nedažomos"; (e) a room kept out
  by choice keeps showing the READING (areas from `scope.EXCLUDED_QUANTITIES_KEY` when present, else names
  without numbers) plus the kept-out sentence; (f) another finish in the breakdown (tapetai 0.3) with no m² of
  its own → named without a number („tapetai"); (g) stretch ceiling → „įtempiamos 37,86 m²"; unpainted ceiling
  → „nedažomos".
- [ ] Implement; update the old assertions; run the room-facts suites + the jargon/trust guards; commit.

### Task 3: the engine takes a floor covering

**Files:** `backend/extractor/universal_rules.py`, `backend/extractor/vision_call.py` (`_floor_rule_is_tile`),
`backend/api/room_recalc.py` (primitive allow-list), `backend/tests/test_floor_covering_calc.py` (new).

- [ ] Tests on `calc_room_quantities`: a `miegamoji` 12 m² / 14 m perimeter with
  `grindu_danga="plyteles"` → tiles 12, soft 0, skirting 0 (`_grindjuosciu_praleista == "plyteles"`);
  a `vonia` with `"minksta"` → tiles 0, soft = area, skirting > 0; any room with `"be_dangos"` → tiles 0, soft 0,
  skirting 0, levelling 0; an unknown value or no field → byte-identical result to today (compare the whole
  dict for three purposes incl. `garazas`); `plyteles_grindys_m2_override` still wins for the tile AREA;
  `tile_floor_override` is ignored when `grindu_danga` is set.
- [ ] Implement `FLOOR_COVERINGS = {"plyteles": ("tile", True), "minksta": ("parquet", False),
  "be_dangos": ("concrete", False)}` and one local `floor_type` used by tiles, soft floor, skirting, levelling.
- [ ] `_floor_rule_is_tile` and `room_facts._floor_by_rule` honour `grindu_danga`; `room_recalc` allow-list
  gets `grindu_danga`, `grindu_danga_saltinis`.
- [ ] Parity suites (`test_recompute_interior_parity.py`, universal-rules suites); commit.

### Task 4: `floor_coverings` — what the floor plan draws in each room

**Files:** `backend/extractor/floor_coverings.py` (new), `backend/tests/synthetic_floor_plan.py` (new helper),
`backend/tests/test_floor_coverings.py` (new).

API:
```python
find_floor_sheets(pdf_bytes, pages) -> list[int]            # title says GRINDŲ (DANGŲ) PLANAS
read_floor_coverings(pdf_bytes, page, rooms) -> dict
#   rooms: [{nr, polygon: [[x, y] pt …] | None, point: (x, y) pt | None}] in THAT page's display frame
#   → {"rooms": {nr: {danga, irodymas: "uzrasas" | "rastas", tekstas, plotas_m2, rect_pct, page}},
#      "legenda": [{tekstas, klase, spalva}], "page": page}
classify_line(text) -> "plyteles" | "minksta" | None
```
- [ ] Tests (synthetic sheets drawn with reportlab): label inside a room → `uzrasas` with the m² beside it;
  a label in the neighbour room does not leak; coloured legend + same-colour hatch → `rastas` for a polygon
  room and for a point-only room; black legend text → nothing; a skirting legend line („Grindjuostės (iš
  plytelių)") in green with green lines along the walls → nothing; tile hatch + soft hatch both ≥ 25 % in one
  room → nothing for that room; two tile colours in one bathroom → `plyteles`; „Šildomos grindys" → not a
  covering; `classify_line` table (plytelė / akmens masės / laminuota grindų danga / SPC vinilinės / Grindys –
  …, eglutės raštas / grindjuostės / klojimo pradžios taškas).
- [ ] Implement: coloured text lines via PDFium chars + `FPDFText_GetFillColor` (rotation-0 frame conversion
  shared with `pdf_vectors._to_display`); strokes from `pdf_vectors.page_paths(strokes=True)` grouped by colour;
  share of a room covered by a colour = area of the morphological closing (buffer ±`CLOSE_M = 0.65` m when the
  scale is known, else 3 % of the page width) of that colour's segments ∩ room, over the room's area;
  `MIN_SHARE = 0.35`, `MIXED_SHARE = 0.25`; point-only rooms use a disc of `POINT_R_M = 0.8` m.
- [ ] Run; commit.

### Task 5: the lane writes it, the fact says it

**Files:** `backend/extractor/geometry_lane.py`, `backend/extractor/room_facts.py`,
`backend/tests/test_geometry_lane.py`, `backend/tests/test_room_facts_grindys.py` (new),
`backend/tests/test_geometry_fixture_gate.py` + `fixtures_geometry_gate.json`.

- [ ] Lane: after the perimeters, `find_floor_sheets` over the classified plan pages; each located room is laid
  onto the floor sheet (`alignment.from_base` — the same lay-over the outlines use); writes `grindu_danga`,
  `grindu_danga_saltinis="grindu_planas"`, `_grindu_danga`; never over `user_override`; clears a stale
  `grindu_planas` value when the re-run reads nothing; meta `grindu_dangos {lapas, perskaityta: {nr: danga},
  legenda}`. Idempotent.
- [ ] Fact: read → status `read`, kind `grindu_planas`, page + rect of the evidence, sentence quoting the
  drawing; user → `read`, „Dangą pasirinkote jūs."; none → `assumed` with what the floor plan lists in general;
  `editable = {"field": "grindu_danga", "kind": "choice"}`; `suggestion` absent.
- [ ] Gate on the real drawings (fixture JSON grows): H all 11 rooms read, 01 → `minksta`, 04 → `plyteles`,
  07/08 → `plyteles`; G 03/05/06/07/09 → `plyteles`, 01 → `minksta`, 02/04/08 unread.
- [ ] Run geometry + room-facts suites; commit.

### Task 6: the direct choice on the sheet

**Files:** `frontend/src/components/roomsheet/FactRow.jsx`, `frontend/src/lib/roomSheet.js` (+ test),
`frontend/src/lib/mergeReextract.js` (+ test), `frontend/src/pages/RoomSheet.jsx`, i18n `lt.json` / `en.json`.

- [ ] Tests: `userEditPatch('grindu_danga', 'plyteles')` → `{grindu_danga, grindu_danga_saltinis:
  'user_override'}`; `roomTouched` is true for it; `carryUserFacts` keeps it against a fresh read and reports
  the difference.
- [ ] `FactRow`: `field === 'grindu_danga'` → three buttons + consequence sentence; the `paskirtis` select stays
  for blobs whose fact still says `paskirtis`. `RoomSheet.saveChoice` routes `grindu_danga` through
  `saveRoomEdit` + `userEditPatch`.
- [ ] Browser (H 01, G 09, G 02): green fact with the quote; „Rodyti brėžinyje" jumps to the floor plan; choosing
  another covering moves the sąmata rows (ripple) and the fact turns to „pasirinkote jūs"; console clean.
- [ ] `npm run test:units`, eslint; commit.

### Task 7: gates and the record

- [ ] Re-run the lane on both local demo projects (`scripts/apply_geometry_to_local_project.py`), full backend
  suite, frontend units, eval (`--totals-only --recompute --geometry`) against the 2026-09-19 numbers
  (9,83 % / 7,06 % / rows 15,0 / 29,2 / 24,3 %).
- [ ] Browser regression: H rooms 01–04, G rooms 02 and 09 — crops sharp, finishes in m², floor fact, accept,
  next room.
- [ ] Execution log appended here; memory updated; commit. No push.

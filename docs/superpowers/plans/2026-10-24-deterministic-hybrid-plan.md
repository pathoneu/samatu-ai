# Pathon v4 — deterministic hybrid takeoff: execution plan

**Date:** 2026-10-24 · **Author:** manager (Fable 5.1) · **Status:** DRAFT for the founder's approval, nothing started
**Branch:** work continues on `togal-v2`; `main` untouched; nothing pushed without the founder's OK.

> **Phase 0 (c) result, 2026-10-24 (merge 8430bb0c):** gate G0 **FAILS on raster** — SAM 2.1 (b and l, local, MPS) from an honest click lands within 2 % of the table on 0/11 rooms (median error 94 %; whole-sheet masks, label glyphs, leaks through doors), with wall negatives 0/11, with a box 1/11; the **vector clause PASSES** (vector lane 3,8 % median on objektas_h and g, SAM ≥ 13 % at best). SAM 2 is therefore **not** the room source in §3.1; the raster path is decided by the founder after the deterministic raster spike (wall mask + door-gap bridging) — see `docs/superpowers/research/2026-10-24-sam2-room-mask-spike.md`. The objektas_a vector outlines run 7–23 % under the table (scale or table convention — under investigation in Phase 0 (a)).

## 0. Verdict in one paragraph

For six months contractors have rejected the output. The founder's diagnosis: numbers were
extrapolated by a multimodal language model from pictures, and the engine's conventions were
guessed instead of learned from the contractor's own sąmatos. From now on **no quantity may
come from a language model looking at pixels**. Geometry comes from the PDF's vector paths
where they exist, from SAM 2 + OpenCV masks where they do not, or from the user's own polygon.
Text comes from the PDF text layer, then OCR, and a language model is allowed only to turn
already-extracted text into a schema. The rules engine becomes a named-parameter conventions
profile, **fitted against every contractor sąmata we have (eight projects) and validated
leave-one-out**. The honest inventory below shows roughly half of this already exists in the
geometry lane built in September–October; the other half (SAM source, Vision disengagement,
conventions fitting, the four compliance rules, the calibration-line gesture) is the work.

## 1. Non-negotiable rules, as code contracts

| # | Rule | Enforced by |
|---|------|-------------|
| R1 | A room/zone polygon has `source ∈ {vector, sam2, manual}`. `vision` and `estimate` are not legal sources; such values are deleted, not flagged. | `backend/geometry/provenance.py` + a guard test that fails on any other source in a stored blob |
| R2 | Area, perimeter, counts, lengths are computed by OpenCV / shapely from polygons and vector paths. Never read off an image by a model. | guard test over `extractor/` imports: no `vision*` import inside `geometry/` or `rules/` |
| R3 | A language model may only (a) classify a page from its **text**, (b) transform extracted **text** (tables, schedules, legends) into schema JSON. It never emits a number that was not literally in the text. | `backend/text/` returns the source string next to every value; a test asserts every numeric field has a `source_text` |
| R4 | Every row quantity is rounded once, at the row boundary: m² and m to 0.01 (`Decimal`, `ROUND_HALF_UP`), counts to integers, material packs `ceil`. No rounding inside intermediate math (rounding early is how estimates drift). | `backend/rules/rounding.py`, used by every row generator |
| R5 | Every convention is a named parameter in one profile with its source written beside it. Profile defaults are **fitted** to the contractor sąmatos and validated on a held-out project. | `backend/rules/conventions.py`, `backend/rules/fit.py`, fit report in `docs/superpowers/research/` |
| R6 | Inference is local. SAM 2 through Ultralytics on this machine; PaddleOCR local. No drawing leaves the machine for geometry or OCR. | no cloud geometry/OCR client anywhere in `backend/`; grep guard |
| R7 | Where no legal source exists, the field is blank with a reason sentence. Never a default dressed as a reading. | existing blank-with-reason pattern (`_only_while`, reasons) |

### The four compliance rules the founder set (go into the profile, fitted, not hard-coded)

1. **Precision 0.01 m²** — R4 above.
2. **Angų užskaitos taisyklė.** Opening ≤ `aperture_no_deduct_max_m2` (**3.0**, founder's default) → not deducted from the wall face. Opening > 3.0 m² → deducted, and its perimeter goes to a row **„Angokraščių apdaila (m)"**. Today the code applies the NRM2 0.5 m² threshold with a 0.5–3.0 one-face tier (`universal_rules.py` `UNIVERSAL_RULES["nrm2_no_deduct_threshold_m2"]`, `_opening_should_deduct`, `_opening_adds_reveal`). The fit will show which threshold reproduces his rows; the founder's 3.0 becomes the default of the `lt_rangovas` profile unless the fit contradicts it on most projects, in which case the manager reports both numbers and the founder decides.
3. **Grindjuostės.** Deduct exactly `skirting_door_deduct_m` (**0.90**) per door intersecting the room outline. Today the code deducts the drawn door width (default 0.9 only when the drawing has no width). Fit decides fixed vs drawn.
4. **Moisture zones.** Room name matching `wet_room_markers` („Vonia", „WC", „San. mazgas", plus „Dušas", „Tualetas", „Skalbykla" as candidates — fit decides) → two rows: **„Grindų hidroizoliacija" (m² = net floor area)** and **„Hidroizoliacinė juosta kampams" (m = gross perimeter)**. Today one row.

Honesty note on the citations: STR 1.14.01:1999 is the rule for building areas and volumes and STR 3.01.01:2002 covers resource norms; I could not verify that either states the 3.0 m² aperture rule or the 0.90 m skirting deduction. They are written into the profile as **contractor conventions** with the founder as source. If the founder has the clause, it goes into the source column.

## 2. Honest inventory — what exists today (`togal-v2` @ 2f66baf0)

**Deterministic geometry that stays and becomes the first source**
- `backend/extractor/geometry_lane.py`, `vector_rooms.py`, `wall_outline.py`, `pdf_vectors.py` — room outlines from the PDF's own paths (wall-exact on vector sheets).
- `plan_dimensions.py`, `dimension_sum.py` — sheet scale from dimension strings and stated scales; perimeters from summed dimension strings.
- `drawn_openings.py` — doors (swing arcs) and windows (glazing) as drawn, per wall face.
- `vector_symbols.py`, `legend_rows.py`, `api/legend_count.py` — symbol counting from vector paths (the legend tool).
- `sheet_zones.py`, `room_locator.py`, `wall_graph.py`, `wall_adjacency.py` — sheet layout, room label → sheet, shared walls.
- Routes: `rooms/{nr}/outline-at` (one click → outline), `outline-set`, `outline-merge`, `split-space`, `split-proposal`, `hole-at`, `pages/{page}/geometry`, `pages/{page}/zones`, `calibrate` (`api/room_outline.py`, `api/sheet_refs.py`, `api/calibrate.py`).
- Frontend: `TakeoffViewer.jsx` overlay already captures clicks in PDF points and draws polygons back (`PageOverlayHost.jsx`, `OutlineToolLayer.jsx`, `OutlineEditLayer.jsx`, `useRoomTool.js`, `useOutlineTool.js`, `lib/roomOutlineApi.js`, `lib/pageGeometryApi.js`); scale UI exists (`CalibrateDialog.jsx`, `ScaleChip.jsx`, `ScaleCheckCard.jsx`, `lib/scaleSuggestion.js`, `lib/durableScale.js`).

**Pixel CV that gets replaced by SAM 2**
- `extractor/cv_polygon.py`, `cv_wand.py` (flood fill), `cv_match.py` (template match), `main.py` `POST /api/click-to-fill` and `POST /api/projects/{id}/detect-room-polygons`, `api/cv_tools.py`.

**Model-looks-at-pixels code that must be disengaged from geometry (the kill list, §6)**
- `extractor/vision_call.py` (7 855 lines, orchestrator `extract_interior`, `vision_polygon_at_click`, `perimeter_warning` / square-perimeter synthesis).
- `extractor/vision/`: `bbox_locator.py`, `dimension_extractor.py`, `elevation_extractor.py`, `height_extractor.py`, `niche_locator.py`, `room_graph_extractor.py`, `adjacency_extractor.py`, `symbol_detector.py`, `built_in_detector.py`, `schedule_extractor.py`.
- `extractor/niche_inference.py`, `objektas_d_estimator.py`, `wall_elevation.py` (tile zones from išklotinė images), `agentic_crop.py`, `verify_pass.py`, `vision_call_v2.py`, `interior_v9/symbol_detector.py`.
- API: `api/vision_fill.py`, `api/vision_readers.py`, `api/symbols.py`, `legend/vision-read`.

**Text readers that stay but move behind the text-layer-first rule**
- `pdfplumber_eksplikacija.py`, `eksplikacija_reader.py`, `table_reader.py`, `schedules.py`, `door_schedule.py`, `plyteliu_specifikacija.py`, `material_specs.py`, `apdailos_reader.py`, `doors_reader.py`, `door_type_reader.py`, `sanitary_fixture_reader.py`, `page_classifier.py`, `height_markers.py`, `floor_coverings.py`, `plan_area_annotations.py`.

**Rules engine**
- `extractor/universal_rules.py` (3 604 lines; `UNIVERSAL_RULES` dict already holds thresholds, waste factors, door defaults, `SKIRTING_WASTE`), `lt_rules.py`, `tile_calculator.py`, `line_items.py`, `ledger.py`, `samata_template.py`, `row_scorecard.py`, `api/recompute_quantities.py` (1 409 lines, the live recompute), `main.py` `/recompute-interior`.

**Truth we can learn from (gitignored, local only)**
- `ground_truth/<project>/contractor_samata_priced.json` for **eight** projects (objektas_a, b, c, d, g, h and two more), plus `truth.json`, `reading_truth.json`, `adjacency.json`. The eval harness already computes the **share of his rows within ±10 %** per project (`eval_harness.py`), today ≈ 26 % corpus mean.
- Corpus fact measured today: every project fixture is a **vector PDF with a text layer**; the one pure-raster file is the ablation `objektas_a_flat150.pdf` (0 text pages, 0 vector pages). The contractor's cold uploads can be either, so both paths must work.

**DB** (`backend/db.py`, SQLite): `projects` (blob), `project_versions`, `corrections`, `extractions`, `extraction_jobs`, `price_lists`, `samata_templates`, `assemblies`, `user_settings`, plus auth/billing tables. PDFs in R2 / local disk (`storage.py`).

## 3. Target architecture

```
PDF ──PDFium──► page raster 300 DPI (page_raster_cache)      text layer ──► backend/text/
          └────► vector paths ──► geometry/vector_source      (OCR: PaddleOCR when no text layer)
click (x,y PDF pts) + scale ──► geometry/sam_source (SAM 2.1, local) ──► mask
mask / paths ──► geometry/polygonize (cv2.findContours, approxPolyDP, snap to vector walls) ──► GeoJSON
GeoJSON + scale ──► geometry/measure (area m², perimeter m, openings on faces, corners)
measure + text schema ──► rules/ (conventions profile, row generators, rounding) ──► sąmata rows
                                                        ▲
                       rules/fit.py ◄── ground_truth/*/contractor_samata_priced.json (8 projects)
```

### 3.1 `backend/geometry/` (new package, deterministic only; no `vision*` import allowed)
- `render.py` — PDFium page → 300 DPI PNG, cached (reuse `page_raster_cache.py`); pixel ↔ PDF-point matrix.
- `scale.py` — one function `scale_for_page(project, page) -> Scale{m_per_pt, source}` with sources in order: user calibration line → dimension strings in the text layer (`plan_dimensions.py`) → stated scale → OCR'd dimension string (raster) → blank. Adds the **calibration-line gesture**: the user drags a line over a dimension string such as „4280"; the backend reads the string under the line from the text layer (or OCR) and sets `m_per_pt` from the line length in points. (`api/calibrate.py` today stores user totals, not a scale line; the new route is separate.)
- `vector_source.py` — wraps `wall_outline.py` / `vector_rooms.py`; returns a polygon with `source="vector"` when the page has wall paths around the click.
- `sam_source.py` — SAM 2.1 via Ultralytics (`sam2.1_b` default, `sam2.1_s` fallback; MPS on Apple silicon, CPU elsewhere), point prompt(s) + optional negative points + optional box; returns a binary mask; model loaded once per process; weights cached under `backend/data/models/` (gitignored).
- `polygonize.py` — `cv2.findContours` (RETR_CCOMP for holes), `approxPolyDP` with ε tied to scale (≈ 2 cm), snap vertices to nearby vector wall faces when the page has them, remove slivers, GeoJSON out.
- `measure.py` — shapely area/perimeter in metres from GeoJSON + scale; openings intersecting faces (reuse `drawn_openings.py`); outer-corner count (reuse `ring_corner_counts`).
- `provenance.py` — `source ∈ {vector, sam2, manual}`, `scale_source`, model version, prompt points; stored next to the polygon.

### 3.2 `backend/text/` (text-first readers; model only for schema)
- `layer.py` — PDFium/pdfplumber text with positions (exists in pieces).
- `ocr.py` — PaddleOCR (lang `lt`/latin) for pages with no text layer; returns words with boxes, same shape as `layer.py`.
- `tables.py` — eksplikacija, door/window schedules, finish schedules, legends: deterministic column parsing first (existing readers); when the table is an image, OCR then the same parser.
- `schema_llm.py` — the only model call left: text in → JSON schema out, with `source_text` per value; refused if a value is not a substring of the input.
- `page_kind.py` — sheet classification from title-block text (existing `page_classifier.py` reduced to text).

### 3.3 `backend/rules/` (split out of `universal_rules.py`, no behaviour change in the split commit)
- `conventions.py` — the `lt_rangovas` profile: every constant named, typed, with `source` and `fitted_on` fields. Includes the four founder rules (§1), waste factors (laminate 1.08, tiles 1.10, …), wet-room markers, door deduction, tile band height, reveals scope.
- `rows.py` — row generators per family (dažymas sienos/lubos, glaistymas Q2–Q4, gruntas, plytelės sienų/grindų, grindjuostės, hidroizoliacija ×2, angokraščių apdaila, GKP, tapetai, taškai…). Each row carries its formula string and inputs for Patikra.
- `rounding.py` — R4.
- `fit.py` — for each profile parameter, grid-search the value that maximises his rows within ±10 % across the eight sąmatos; **leave-one-out**: fit on seven, score the eighth, report both. Output: `docs/superpowers/research/2026-10-XX-conventions-fit.md` + `conventions_fitted.json`. Also lists rows he writes that we never emit, and rows we emit that he never writes.

### 3.4 Routes
- `POST /api/geometry/segment` — stateless. Body: `project_id, page, points[], negative_points[], box?`. Returns GeoJSON polygon, `area_m2`, `perimeter_m`, `source`, `scale`. Nothing saved.
- `POST /api/geometry/scale-line` — body: `page, p1, p2`; reads the dimension string under the line; returns `m_per_pt`, `source_text`; saved per page.
- Existing `rooms/{nr}/outline-set` stays the single persistence path (polygon + provenance), `recompute-quantities` stays the single recalculation path, but every number inside it must trace to geometry or text (§6 removes the rest).
- Removed: `/api/click-to-fill`, `detect-room-polygons`, `vision_fill`, `vision_readers`, `symbols` (vision), `legend/vision-read`.

### 3.5 Data model
- Project blob, per room: `geometry: {polygon_pdf_pts, page, source, scale_source, model, area_m2, perimeter_m, openings[], corners}` replaces the scattered `polygon`, `polygon_source`, `_sutapdinimas` keys (migration reads old keys once, writes the new one; old `vision`/`estimate` polygons become `null` + reason).
- New table `room_geometry` (project_id, room_nr, page, source, polygon_json, scale_m_per_pt, prompt_json, user_id, created_at) — append-only provenance; also the future training set for a floor-plan-specific segmentation model.
- New table `page_scales` (project_id, page, m_per_pt, source, source_text, user_id, created_at).
- `corrections` stays as is (feeds `scripts/build_ground_truth.py`).

### 3.6 Frontend (`TakeoffViewer`)
- Tool „Patalpa": click → `/api/geometry/segment` → dashed proposal → „Tinka" saves via `outline-set`; second click inside adds a positive point, click on a wall with Alt adds a negative point; vertices editable with the existing `OutlineEditLayer`.
- Tool „Mastelis": drag a line over a dimension string → `/api/geometry/scale-line` → chip shows „1 : 50 iš „4280"".
- Zones on išklotinės (tile bands, furniture blocks): same segment call with a box prompt on the išklotinė sheet; the room's wall face gets `tile_zone_m2` from the polygon, not from a model.
- Viewer library: EmbedPDF/PDFium stays. The overlay already does what the Konva proposal asks for (exact PDF-point clicks, live polygons). Replacing it is 3–4 weeks of UI work with no accuracy effect; it is listed as a Phase 5 option, decided after the backend gates pass. The sąmata table may move to TanStack Table in the same phase.

## 4. Execution phases, gates, owners

Manager: Fable 5.1 (directs, reviews, merges). Workers: Opus 5.5 in worktrees, one per track, ≤ 4 at once. Every merge: denylist grep, `--no-ff`, units/lint/build, touched backend tests, merge-log row. The old eval gate (MAE %) stays as a regression tracker only; **the new gate is his rows within ±10 % per project, reported in-sample and leave-one-out.**

| Phase | Days | Work | Gate to pass before the next phase |
|------|------|------|-----------------------------------|
| **0 Baseline + SAM viability** | 1–3 | (a) Freeze today's numbers: rows ±10 % per project, per-room area error of the vector lane vs the designer's table. (b) Pull the contractor's two new projects from the prod DB backup + R2 (read-only), run the geometry lane on them cold, list failures. (c) SAM 2 spike: click → mask → m² on `objektas_a_flat150.pdf` (raster), objektas_h, objektas_g; vs table areas and vs vector outlines; prompt variants; timing. | **G0:** on raster, SAM area within 2 % of the table on ≥ 80 % of rooms and no leak through doors on ≥ 90 %; on vector sheets, vector lane remains ≥ SAM. If G0 fails: fallback is vector + manual polygons now, and a floor-plan-trained segmenter (fine-tune on CubiCasa5k-style data + our `room_geometry` rows) as its own track. |
| **1 Geometry package** | 4–8 | `backend/geometry/` (3.1), `/api/geometry/segment`, `/api/geometry/scale-line`, provenance, `room_geometry` + `page_scales` tables, migration of old polygon keys, wire „Parodyti patalpą" to vector → SAM → manual. Delete `cv_wand`, `cv_polygon`, `click-to-fill`, `detect-room-polygons`, `vision_polygon_at_click`. | **G1:** per-room area vs table ≤ 1 % median on all eight projects where a table exists; perimeter vs summed dimension strings ≤ 2 %; guard tests for R1/R2/R6 green. |
| **2 Rules + fit** | 6–12 | Split `universal_rules.py` into `rules/` with zero behaviour change (commit 1), then `conventions.py` profile, `rounding.py`, the four founder rules, hidro two rows, `fit.py` + fit report with leave-one-out. | **G2:** rows ±10 % share rises from ≈ 26 % to ≥ 50 % in-sample **and** ≥ 40 % leave-one-out; the fit report names every parameter that moved and the projects that disagree. |
| **3 Disengage Vision from geometry** | 10–16 | Kill list §6: each module deleted or reduced to text input; `backend/text/` with PaddleOCR; `schema_llm.py` with the substring guard; blank-with-reason everywhere a number loses its source. | **G3:** no stored quantity has provenance `vision`/`estimate` (guard test over the eight replayed projects); rows ±10 % not below G2; Vision spend per project drops to the text-schema calls only. |
| **4 Frontend tools** | 14–20 | „Patalpa" click/negative/box, „Mastelis" line over a string, zone boxes on išklotinės, provenance shown in Patikra evidence (polygon + source + scale). WebKit + Chromium e2e. | **G4:** manager's own walk on 5173 in both engines; founder guide updated. |
| **5 Cold test + options** | 20–24 | Run the two new contractor projects end to end with the new pipeline; founder walk; hand to the contractor. Decide Konva/TanStack and the floor-plan segmenter track. | **G5:** the contractor's verdict on his two projects. |

Days are working days from approval. Weekly usage limits can stretch them; the manager reports slippage, never silently.

## 5. What to refactor first (the order inside Phase 1–2)

1. `backend/geometry/scale.py` first — every m² depends on it; today scale logic is spread over `plan_dimensions.py`, `scale_validator.py`, `room_seeds.calibrate_page_scale`, `wall_outline._scales`, `api/calibrate.py`, `api/room_graph._extract_scale_factor`, and `lib/durableScale.js`. One source of truth, one provenance.
2. `backend/geometry/polygonize.py` + `measure.py` on top of the existing vector outlines — gives G1 numbers on vector sheets before SAM lands.
3. `sam_source.py` behind `source="sam2"`; „Parodyti patalpą" chooses vector → sam2 → manual.
4. `universal_rules.py` split (mechanical, zero behaviour) so `conventions.py` can be fitted without touching 3 600 lines each time.
5. `api/recompute_quantities.py`: strip imports from `vision_call` (today it imports calc helpers from there); the helpers move to `rules/`.
6. Then the kill list.

## 6. Kill list (delete, or reduce to text-only input)

| Module / route | Today | Action |
|---|---|---|
| `vision_call.vision_polygon_at_click` | model draws a polygon at a click | delete → `geometry/segment` |
| `vision_call.perimeter_warning` + square-perimeter synthesis, `_perimeter_floor_enabled` | perimeter guessed from area | delete → blank with reason until a polygon exists |
| `vision/bbox_locator.py`, `room_graph_extractor.py`, `adjacency_extractor.py` | room positions/adjacency by model | delete → `room_locator.py`, `wall_adjacency.py` from geometry |
| `vision/dimension_extractor.py` | dimension strings read by model from image | delete → text layer, OCR fallback |
| `vision/height_extractor.py`, `height_fusion.py` | heights from section images | reduce to text: `height_markers.py` (text layer/OCR); model only maps text to rooms |
| `vision/elevation_extractor.py`, `wall_elevation.py` | tile zones from išklotinė images | delete → SAM/OpenCV zone polygons on išklotinės + text labels |
| `vision/niche_locator.py`, `niche_inference.py` | niche lengths inferred | delete → vector/segment polygons on ceiling plan or blank |
| `vision/symbol_detector.py`, `built_in_detector.py`, `interior_v9/symbol_detector.py`, `api/symbols.py`, `legend/vision-read` | counts/furniture by model | delete → `vector_symbols.py`; raster: template match on the legend glyph with a user-confirmed count, or manual count tool |
| `vision/schedule_extractor.py`, `apdailos_reader.py`, `doors_reader.py`, `door_type_reader.py`, `sanitary_fixture_reader.py`, `eksplikacija_reader.py`, `material_specs.py` | model reads tables from images | reduce: text layer/OCR → deterministic parser → `schema_llm.py` only for structuring, substring-guarded |
| `page_classifier.py` | model classifies page images | reduce to title-block text + layout features |
| `objektas_d_estimator.py`, `agentic_crop.py`, `verify_pass.py`, `vision_call_v2.py`, `calibration_learner.py` | estimators / second-look passes | delete |
| `cv_wand.py`, `cv_polygon.py`, `cv_match.py`, `api/cv_tools.py`, `/api/click-to-fill`, `detect-room-polygons` | pixel flood fill / template | delete → `geometry/` |
| `api/vision_fill.py`, `api/vision_readers.py` | model fills blanks | delete |
| `api/calibrate.py` (user totals calibration) | scales rows to the user's totals | keep but rename to „Jūsų sumos" and keep out of the eval; it is not geometry calibration |

`extract_interior` in `vision_call.py` shrinks to: text lane → geometry lane → rules. The 7 855-line file is retired when its last caller moves.

## 7. Risks, stated plainly

- **SAM 2 on line drawings.** SAM is trained on photographs. On thin-line plans with hatching it may leak through door openings or split a room on a furniture outline. That is exactly what G0 measures before anything is built on it. The fallback (fine-tuned floor-plan segmenter on our own `room_geometry` rows) is a real track, not a footnote.
- **Scale on raster sheets.** Everything in m² depends on `m_per_pt`. OCR of „4280" with Lithuanian fonts and rotated strings is the weak link; the calibration-line gesture puts the user in control, and the chip always shows the source.
- **Over-fitting his conventions.** Eight sąmatos is a small set; a threshold that fits all eight may still be his habit on one job type. Leave-one-out is mandatory, and the fit report shows disagreements.
- **The contractor's two new projects** may differ in drawing style (another architect). They are the honest test; nothing from them enters the fit.
- **Weekly usage limits** stop Opus workers mid-task; resume points are written into each brief.
- **Cost.** Phase 0–2 need no Vision calls. Phase 3 text-schema calls are cents per project.

## 8. Decisions the founder makes before we start

1. **Approve the phase order** (geometry → rules fit → disengage Vision → frontend), or reorder.
2. **Aperture threshold:** 3.0 m² as the profile default even if the fit prefers another value, or let the fit decide and report.
3. **Kill vs flag:** delete the Vision geometry modules outright (clean, irreversible on this branch, history keeps them) or keep them behind a flag defaulting OFF for one release. Recommendation: delete; flags are how the old path survives.
4. **Prod data pull:** OK to read the newest DB backup and the two new project PDFs from R2 to a local, gitignored folder for the cold test (read-only, nothing leaves the machine).
5. **Viewer:** EmbedPDF overlay stays for now; Konva/TanStack decided at Phase 5.

Nothing in this plan has been started. Two spike workers were launched and stopped before they wrote anything.

## 9. Amendments after Phase 0 (2026-10-24, measured — see the three research docs of this date)

**Gates.**
- **G0:** SAM 2 FAILED on raster, PASSED the vector clause → SAM 2 is not a geometry source. Raster path: founder decides between the deterministic wall-mask spike and a floor-plan-trained segmenter. **Founder decision 2026-10-24 („ok, 5%"): the raster clause is restated — ≤ 5 % of the vector outline, IoU ≥ 0,9, no leak, on ≥ 80 % of rooms; the raster outline is a proposal the user confirms; frozen constants tested on an unseen raster sheet before wiring (`backend/geometry/raster_source.py`, flag `SAMATU_RASTER_ROOMS`, default OFF). No segmenter track.** **2026-10-24, later: the frozen-constant test failed out of sample (d 0/4, b 1/15, i 6/17) — raster track PARKED by the founder; scanned sheets get a manual polygon plus OCR for labels, strings and scale; revisit with a real raster corpus.**
- **G1 restated:** the primary measure is the outline against the **dimension strings** (median edge-vs-string error ≤ 1 % on every project that has strings; perimeter vs summed strings ≤ 2 %), with the designer's table area as a **secondary, convention-dependent** check (≤ 5 % median). Reason: on objektas_a the walls match the strings to +2,3 % while every outline is 7–23 % under the table; the table counts area by its own convention (non-uniform offset per room), not by a scale error.
- **Phase 1 scope widened — the lane is blind more often than not.** Vector outlines exist on 3 of 7 corpus projects and on 0 of 7 of the contractor's production projects. Causes to remove, each with a principled rule and a synthetic-PDF test: (1) badge height cap 6,5 pt (his badges 6,6 pt, another 11 pt); (2) wall solid from one fill colour (outer walls in a second grey drop out); (3) duplicate room numbers across two units on one sheet and in stacked tables; (4) dashed door-swing arcs not classified; (5) no scale when no dimension string sits on a hairline (c, r1, j1) → match strings to wall faces, parse the stated „M 1:xx", borrow a scale from a sibling sheet of the same set when the sheets overlay at identity (d: rooms on sheet 2, scale on sheet 1), and the calibration-line gesture as the user's fallback; (6) rooms placed only by the model's boxes (b has no room badges) → badge-less placement from the table row + the closed wall ring that contains the room's own m² label, else blank; (7) no text layer (j3 raster scan, j4 text-as-outlines) → OCR on the render (PaddleOCR, local) for labels, strings and tables; j4 needs no segmenter.

**Conventions (Phase 2) — what his eight sąmatos say.**
- **Waterproofing:** he writes **one** row, `vnt` = number of vonia / WC / san. mazgas rooms (6 of 7 projects; laundry never counted). Our engine already reproduces it on a, b, c, d. The founder's two-row form (floor m² + corner tape m) is **contradicted by his data**: it becomes a profile option, not the default, unless the founder overrules with a reason. **Founder decision 2026-10-24: overruled — the two-row form IS the default; the one-row `vnt` form is the profile option. The eval reports the waterproofing family separately so the cost of the override on a, b, c, d stays visible.**
- **Waste on labour rows:** he bills **net** area (d 0,99, g 1,00, a per-room median 0,99). No 1,08 / 1,10 on labour rows; waste stays in the „Medžiagos" rows only (already so).
- **Opening threshold:** today's engine default is the LT standard, which deducts openings ≥ **1,0 m²** (not NRM2 0,5 as §1 assumed). 3,0 m² vs 1,0 m² moves wall paint by 1–5 % and the ±10 % share by ≤ 4 pp; the data cannot identify the threshold. 3,0 stays available in the profile; the founder's call whether it is the default.
- **Skirting:** fixed 0,90 m vs drawn widths differ by 1–5 %; the real lever (20–60 %) is **which rooms** he skirts. Undetermined.
- **The real Phase 2 lever is scope and granularity, not thresholds:** which rooms get which work (he excludes floors/tiles/plumbing/electrical on some jobs); one combined walls+ceilings paint row (all projects but g); one combined wall+floor tile row; real gaps we never emit (tile-clad reveals/niches, large-format tiles and mosaic, extra skim coat, glass-fibre/wallpaper, demolition); rows we emit that he never writes (all material quantities, „Grindjuosčių dažymas"). Phase 2 therefore starts with a **scope + granularity profile** (per-room work scope choices and row merging as he writes them) and only then thresholds. Leave-one-out runs over six usable projects (a, b, c, d, g, h); r1 is a paint-only quote and r2 has no floor plan.

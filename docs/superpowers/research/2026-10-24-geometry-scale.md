# One source of truth for the sheet scale — `backend/geometry/scale.py`

**Date:** 2026-10-24 · **Worker:** Opus 5.5 (manager: Fable 5.1) · **Branch:** `v4/geometry-scale` (from `togal-v2` @ 4c1baeb5)
**Plan:** `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md` §3.1 `scale.py`, §3.4 scale-line route, §5 item 1, §9 Phase 1 cause 5.
**Cost:** €0. No model call anywhere (eval passes ran with a dead key). Codenames only; every test drawing is synthetic.

> **Resume point:** DONE — all code, measurements and tests below are final on branch `v4/geometry-scale`.

## 0. What changed

| piece | what |
|---|---|
| `backend/geometry/provenance.py` | `Scale` dataclass (`m_per_pt, source, source_text, confidence, page_from, reason, details`), `ScaleSource` enum (`user_line, dimension_lines, dimension_walls, stated, sibling, blank`), `blank(reason)`. |
| `backend/geometry/scale.py` | `scale_for_page(ctx, page)`, `scales_for_pages`, `ScaleContext(pdf_bytes, dims, user_scales, alignment)`, `scale_from_line` / `string_under_line` (the „Mastelis" gesture), `line_scales`, `lane_fill`, `lane_record`, `user_scales_for_project`. |
| `backend/db.py` | table `page_scales` (project_id, page, m_per_pt, source, source_text, details, user_id, created_at; FK → projects ON DELETE CASCADE; created in `_migrate_schema`, idempotent), `add_page_scale`, `get_page_scales` (newest row per page in force, history kept). |
| `backend/api/geometry.py` (+2 lines in `main.py`) | `POST /api/projects/{id}/geometry/scale-line` `{page, p1, p2, frame?}` and `GET /api/projects/{id}/geometry/scale?page=`. Owner-scoped (`free_reread._project_for`), rate bucket `geometry_scale`. |
| `backend/extractor/geometry_lane.py` | three hooks, each marked `v4 scale hook n/3` (see §2). `LANE_VERSION` 13 → **14**. |
| `backend/extractor/wall_outline.py` | `_scales` reads through `scale.line_scales` (one line, marked). |
| untouched | `plan_dimensions.py` (source 2 keeps its behaviour exactly), `api/calibrate.py` (the user's TOTALS calibration), the other worker's files (`room_locator`, `vector_rooms`, `drawn_openings`, `pdfplumber_eksplikacija`, `table_reader`), every frontend file (the new `masteliai[page]` keys are additive; `durableScale.js` reads only `m_per_pt` / `mastelis`). |

## 1. The cascade (`scale_for_page`)

1. **USER_LINE** — the newest `page_scales` row for the sheet. Always wins, HIGH.
2. **DIMENSION_LINES** — `plan_dimensions` unchanged: the `scale_m_per_pt` it put on the strings (its stated-scale snap and refusals included). HIGH with ≥ 10 line-backed strings, else MEDIUM; a sheet read at another scale than it writes keeps the note (`reason`).
3. **DIMENSION_WALLS** — strings with no hairline matched to the wall faces they measure. Faces = the boundary of the union of EVERY non-black wall-shaped fill (not one dominant colour). Each horizontal string is paired with the nearest vertical face left and right of it — on its own line across (a string inside a room) and among faces within 120 pt across (a chain outside the walls) — only when the string sits within 15 % of the span from its middle; each pair proposes `value / distance`. Accepted when ≥ 5 strings with ≥ 4 different values agree within 1 %, with twice the support of any proposal ≥ 4 % away, inside 1:20…1:500; a scale no drawing is made at (a reduced print) needs twice that. Strings in centimetres are read as such only when the ×10 reading lands within 1,5 % of a drawing scale. When a sheet alone is not enough, sheets of the SAME plan at the same print scale (frame size + wall fills coinciding at k ≈ 1) pool their strings. Snapped to the written scale (HIGH) when within 2 % of it, else the measurement stands with a note.
4. **STATED** — „M 1:50" on the sheet (`plan_dimensions.stated_scales_on_page`). CONFIRMED (HIGH) when the line reader refused the strings at the stated scale in other units (objektas_j1), or when a sibling measures the same scale (then `page_from` = that sheet). When a sibling measures ANOTHER scale, the sibling wins (a set printed reduced: objektas_j2 writes 1:40, measures 1:45). Nothing confirming it: LOW. Two written scales and nothing to choose by: blank.
5. **SIBLING** — a sheet with a measured scale (1–3), same frame size, that overlays this one: the lane's own alignment when given; else wall fills (`sheet_alignment._best_fit`, ≥ 0,85 overlap; the scale follows k); else, for sheets drawn without wall fills, the stroked drawing after one translation at k = 1 (≥ 80 % of the smaller sheet's stroke vertices within 1,5 pt). MEDIUM, `page_from`.
6. **BLANK** — LT reason that says what to check („Nubrėžkite liniją ant žinomo matmens…"). Never a default.

**Validation of source 3 against source 2** (the only ground truth for a scale we have): on the 48 sheets of a, b, d, g, h, i, j2 whose strings sit on hairlines, the hairlines were hidden and the wall matcher asked: **7 right (|Δ| ≤ 0,93 %), 0 wrong, 41 silent.** Three looser variants were tried and rejected on this set: pairing a string with the far face of a wall too (echo peaks one wall thickness off), counting a rival only by strings of its own, and a 30 % centre tolerance — together they gave 2–6 wrong scales (half the scale on electrical sheets where „500" is an outlet's offset from a wall; +5 % on elevations).

## 2. How the lane uses it (`geometry_lane.apply_geometry`)

- Hook 1/3: `scale = line_scales(dims)`; a person's lines (`user_scales=` kwarg, else `page_scales` of `parsed["id"]` when the web app already has `db` imported — the eval and scripts never open a DB) are applied BEFORE the wall alignment, so sheets laid over that sheet borrow the person's scale. The „align every sheet" decision is keyed on the sheets' OWN lines (`line_scaled`), exactly as before — a scale from source 3–5 never shrinks which sheets lend their strings.
- Hook 2/3: after the lane's own alignment borrowing, `lane_fill` gives the remaining plan/anchor sheets sources 3–5; `masteliai_tusti` = the reason for each asked sheet left blank. A sheet the lane already scaled keeps its value (only provenance is added).
- Hook 3/3: `masteliai[page]` gains `saltinis`, `tekstas`, `is_lapo`, `patikimumas`, `pastaba`.
- The lane fills only the sheets it works on (plan sheets, rooms' sheets, dimensioned sheets). Any other sheet's scale is one `GET …/geometry/scale?page=` away; filling every sheet inside the lane would add seconds to every room click (`room_outline` re-runs the lane per click).
- Cost: the lane takes +0,2…3,5 s per project (a 4,2 → 6,7 s, b 12,3 → 14,9 s, r1 1,7 → 5,2 s; others ≤ +1 s).

## 3. Scale per plan sheet, before (togal-v2) → after

Before = what togal-v2 gives the sheet (its hairline scale, or the lane's wall-alignment borrow on sheets the lane asked). After = `scale_for_page`. Corpus fixtures and the contractor's uploads (cold, `scripts/cold_run/run_cold.py` inputs). Plan-type sheets only (floor / ceiling / electrical / plumbing; a's raster cover and i's text sheet left out).

| project | sheet | before | after | source | from sheet | confidence | note / reason |
|---|---|---|---|---|---|---|---|
| a | 2 | 1:82 | 1:82,5 | sibling | 4 | medium | |
| a | 3 | 1:82 | 1:82,5 | sibling | 4 | medium | |
| a | 4 | 1:82 | 1:82,5 | dimension lines | | high | |
| a | 5 | — | 1:82,5 | sibling | 4 | medium | |
| a | 6 | — | — | blank | | | 17 strings, all „2800/3000/3400" ceiling heights; walls drawn differently (no overlay); no written scale |
| a | 7 | — | 1:82,5 | sibling | 4 | medium | |
| a | 8 | 1:83 | 1:82,8 | dimension lines | | high | |
| a | 9 | 1:83 | 1:82,6 | dimension lines | | high | |
| b | 1, 3, 4, 5, 9, 10 | 1:100 | 1:100 | dimension lines | | high | |
| b | 2, 7, 8, 11 | — | 1:100 | stated, confirmed | 3 | high | |
| b | 6 | — | — | blank | | | no written scale, no strings |
| c | 1, 2 | — | — | blank | | | no written scale, no strings in the text layer |
| c | 3 | — | — | blank | | | 4 strings (one value), no written scale |
| d | 1 | 1:40 | 1:40 | dimension lines | | high | |
| **d** | **2 (rooms)** | — | **1:40** | **stated „M 1:40", confirmed by sheet 1** | **1** | **high** | walls are black strokes; overlay after a (−32; +59,5) pt shift, 98,8 % of vertices |
| d | 3, 4 | 1:30 | 1:30 | dimension lines | | high | |
| g | 1, 3 | 1:50 | 1:50 | stated, confirmed | 2 | high | (before: the lane's borrow) |
| g | 2, 4–7 | 1:50 | 1:50 | dimension lines | | high | |
| h | 1–6, 8 | 1:115 | 1:115 | dimension lines | | high (p4 medium) | |
| h | 7 | 1:115 | 1:115 | sibling | 1 | medium | |
| r1 | 5 | — | 1:100,2 | dimension walls (cm) | | medium | 10 strings agree |
| r1 | 8, 23, 33 | — | 1:100,2 | dimension walls (cm), pooled 5/8/23/33 | | medium | 14 strings agree |
| r1 | 6, 9, 24, 34, 35, 36 | — | — | blank | | | strings neither on hairlines nor clearing the wall-match test, alone or pooled (refused rather than guessed: the person's line is the way) |
| i (both uploads) | 4, 5, 7 (B: 4–7) | 1:75 / 1:71 | same | dimension lines | | high | |
| i (A) | 6 | — | 1:75 | stated, confirmed | 4 | high | |
| i (both) | 8, 9, 10 | — | 1:75 | stated, confirmed | 5 | high | |
| j1 | 1 | — | **1:100** | stated, confirmed by strings in cm | | high | the line reader measured 1:10 and refused (cm read as mm) |
| **j2** | **1** | — | **1:44,9 (0,01584 m/pt)** | **dimension walls** | | medium | 24 strings with 6+ values; the sheet writes 1:40 (noted, not used). The raster-rooms spike measured 0,01576 m/pt from three strings by hand: +0,5 %. At the written 1:40 outlines come out 18–31 % under the table — the written scale is never trusted alone; when nothing confirms it, it is recorded as „užrašytas, nepatikrintas", LOW |
| j2 | 2, 3 | — | 1:44,9 | dimension walls, pooled 1/2/3 | | medium | |
| j2 | 4 | — | 1:50 | stated, confirmed | 1 | high | the same plan at 1:50 (k = 1,111) |
| j2 | 5 | 1:50 | 1:50 | dimension lines | | high | |
| j2 | 6 | 1:45 | 1:45 | dimension lines | | high | writes 1:40 (noted) |
| j2 | 7 | — | 1:44,9 | sibling | 1 | medium | writes 1:40 (noted) |
| j4 | 1 | — | — | blank | | | no text layer (text as outlines) — needs OCR; a line gesture has no string to read either |

**Totals (74 plan sheets):** a scale on **38 before → 62 after**; every one with its source. Target check: a ✓ except the ceiling plan (6); **c ✗** (the text layer holds no scale information at all — OCR or the person's line on a string the PDF does not have as text: not reachable by this task); d ✓, rooms sheet 2 gets 1:40 with `page_from = 1`; g ✓; h ✓; i ✓ on every plan sheet of both uploads; j1 ✓; j2 ✓; b ✓ except sheet 6 (empty); r1 4 of 10.

**What a scale now buys in the lane (cold run, seeded with production's room list):** objektas_j1 goes from **0 to 15 of 18 rooms outlined**; 13 of the 15 within 0,4 % of the table area (201: 2,65 vs 3,14; 208: 5,21 vs 5,57; 204 −1,6 %). Twin rooms 102 / 202 now both get 10,03 / 10,04 m (production's model gave 9,40 / 12,04). Perimeters there are outline estimates (the strings have no hairline, so `sum_perimeters` adds none — unchanged rule). objektas_i and j2 still outline nothing: their rooms are not located (badge size, duplicate numbers — the other worker's track), not a scale problem any more. In the corpus lane run: r1 gains 1 outline; d, b gain scales on sheets where nothing is traced (d draws walls as black strokes, which `wall_fills` ignores; b's rooms are not badge-located).

## 4. Four eval passes

`venv/bin/python eval_harness.py --totals-only --recompute --gate` and `--rows --recompute --gate`, plain and `--replay-geometry`, on the branch head (dead API key).

| pass | baseline (togal-v2, re-run here) | v4/geometry-scale |
|---|---|---|
| totals plain — billed lines MAE | 22,60 % · GATE OK | 22,60 % · GATE OK |
| rows plain — ±10 % / €±10 | 26,1 % / 34,7 % · GATE OK | 26,1 % / 34,7 % · GATE OK |
| totals replay — billed lines MAE | 22,88 % · (false FAIL, 6 artefact lines) | 22,88 % · same 6 artefact lines |
| rows replay — ±10 % / €±10 | 27,9 % / 39,6 % · GATE OK | 27,9 % / 39,6 % · GATE OK |

## 5. Results of the passes on the branch head

| pass | v4/geometry-scale |
|---|---|
| totals plain | **22,60 %**, GATE OK — byte-identical to baseline apart from the run folder |
| rows plain | **26,1 % / 34,7 %**, GATE OK — identical |
| totals replay | **22,88 %**; the same six artefact WORSE/BETTER lines as the baseline (the known false FAIL) — identical otherwise |
| rows replay | **27,9 % / 39,6 %**, GATE OK — one change: romainiai (r1, scope mismatch, outside the mean) room 4 is now outlined from the vector walls at the new 1:100 (cm) scale, perimeter 8,40 → 8,17 m as an outline estimate; its ±10 % share stays 6,7 % |

Per project: nothing moved on a, b, c, d, g, h. Why: the new scales land on sheets where the lane traces nothing today (d's walls are black strokes, b's rooms are not badge-located, c has no scale anywhere), or on sheets that already had the same scale through the lane's own borrow (a, g, h). Nothing got worse. (Passes were run on 2f7a8928; the two later commits only add a try/except around `lane_fill` and change a LOW-confidence label — no number can move.)

## 6. Tests

- New: `tests/test_geometry_scale.py` (23) — every source on a synthetic PDF built in the test: hairline-backed strings; strings matched to walls (mm, cm, snapped to the written scale, contradicting the written 1:40 → the strings win); written scale alone (LOW, „užrašytas, nepatikrintas"), confirmed by strings refused in cm (j1 case), two written scales → blank; sibling by wall fills, by strokes after a shift (d case), reprinted at another size (k), another plan lends nothing, sibling beats a contradicted written scale (j2 case), sibling confirms a written one; blank with reason; the person's line wins; string-under-line; lane_fill; a failing lane_fill never sinks the lane; **the vision-import guard**.
- New: `tests/test_geometry_scale_api.py` (10) — the `page_scales` migration on a DB without the table (idempotent), newest row in force + history + cascade on project delete, POST over a string (stored, then in force on GET), GET provenance (walls on sheet 1, sibling on sheet 2), a line over nothing / on a sheet without text → reason and nothing stored, the pdf frame, 400/404/422, another user's project → 404, the lane taking a person's line (and its sibling borrowing it).
- Adjusted: `test_geometry_lane.py` (two no-scale tests also blank the written scale), `test_free_reread_api.py` and `test_sheet_zones_api.py` (LANE_VERSION ≥ 13).
- Touched suites (lane, free re-read, dimension source, detect run, fixture gate, plan dimensions, dimension sum, merge corners, eval replay, ilgis_pt, sheet zones, both new files): green.
- **Full backend suite on the branch: 5473 passed, 57 skipped, 1 failed → the one failure was `test_sheet_zones_api` pinning `LANE_VERSION == 13`; fixed and re-run green.**

## 7. Not done, and why

- **room_seeds.calibrate_page_scale** is an m²-per-area-fraction prior for `detect-room-polygons` (kill list §6), not a sheet scale — left. **api/room_graph._extract_scale_factor** reads `_meta.page_scale_mm_per_pct`, which nothing writes any more (the Annotator page shows nothing) — left; it is not a sheet scale either. **scale_validator.parse_scale_string** stays for `vision_call`'s title-block check; the geometry package uses the stricter `plan_dimensions.stated_scales_on_page` (standard scales only, the same rule the line reader uses).
- **OCR** of a dimension string under the person's line on a sheet without a text layer (j3, j4, c): the route answers with a reason; a later task.
- **Frontend** „Mastelis" tool: the routes exist, no UI yet (Phase 4).
- **a sheet 6** (ceiling plan): its walls are drawn in other colours than sheet 4's, so the fill overlay fails; the stroke overlay runs only for sheets WITHOUT fills. Trying strokes when fills disagree would widen the overlay test beyond what was measured.
- **Merge note:** `LANE_VERSION` 13 → 14 here; if the other worker's branch also raises it, the merge takes the higher number + 1.

## 8. Reproduce

Scratch scripts (outside the repo): `diag.py` (per-sheet strings / hairlines / written scales), `scales.py` (`scale_for_page` on every page), `validate_walls.py` (source 3 vs source 2 with hairlines hidden), `corpus_lane.py` (the lane's `masteliai` on the corpus, run once from a `git archive togal-v2` tree and once from the branch), `cmp_cold.py` (run_cold.py before/after), `passes.sh` (the four eval passes).

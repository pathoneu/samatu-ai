# No-vision route for vector PDFs — v4

**Date:** 2026-10-26 · **Author:** Opus 5 worker on `v4/no-vision-vector` (off togal-v2 @ 683487f4)
**Status:** MEASURED 2026-10-27 — gate FAILED; landed behind `SAMATU_NO_VISION_ROUTE=1` (OFF by default)

## 0. Resume point (kept current)

**What is on the branch:**

- `backend/extractor/no_vision_route.py` — `is_vector_pdf`, `should_use_no_vision`, `extract_interior_no_vision`.
- `backend/extractor/vision_call.py:extract_interior` — routes a vector PDF to the no-vision route when `SAMATU_NO_VISION_ROUTE=1` is set AND `is_vector_pdf` returns True; Vision route otherwise.
- `SAMATU_FORCE_VISION=1` — stronger off switch, checked before the route flag; keeps the golden replay pin working.
- `SAMATU_NO_VISION_ROUTE=1` — opt-in flag (OFF by default, see §8 decision 7 for why).

**The verdict (manager-measured, 2026-10-27):**

| measure | baseline (today, Vision) | hybrid no-vision | verdict |
|---|---|---|---|
| billed lines MAE (lower is better) | 57,50 % | 65,86 % | FAIL (+8,4 pp) |
| rows ±10 % | 9,0 % | 8,9 % | pass |
| € ±10 % | 18,0 % | 16,4 % | FAIL (−1,6 pp) |
| scorecard: interior door pairs · exterior doors per room · windows per room · passages | 21/24 · 32/32 · 29/30 · 2/4 | 21/24 · 25/32 · 26/30 · 2/4 | FAIL |

The "hybrid" is a/b/d/h through the no-vision route, c/g through today's Vision read (what a Vision fallback for "no room list" would produce). The predecessor's scorecard "unchanged" was measured on restored `ai_extract.json` files; the actual scorecard on the no-vision extracts failed (7 exterior doors lost, 3 windows lost).

**Cause:** The route starts every room with `elementai: []` and relies on `reconcile_openings_with_walls` + `_angos_sienose`. That lane reads only openings AS DRAWN, so:
- **objektas_d** (no wall outlines, `_angos_sienose_suderinta=False`) loses every window, door, hidden door and LED niche in all 4 rooms.
- **objektas_a** and **objektas_h** get drawn-opening counts that disagree with the reading truth (a 101 gains a window it has none of; h 02 window → 2 doors; h 04 2 windows → 4 windows + 1 door).
- **Per-room LED niches** (`nisa_led`, read by Pass-1 from the ceiling plan), **hidden/sliding doors** (`pasleptos_duris`), **built-in wardrobes** (`spinta_built_in`), and **ceiling type** (`lubu_tipas`) have NO deterministic source on this route and are simply gone.

Pass-1 Vision is not only the room list; it is the per-room reader of those five field groups, and the deterministic lanes replace only the room list, the perimeters and the drawn openings on projects that have outlines.

**Nothing pushed.** Branch is 6 commits ahead of togal-v2 (+ 2 new commits from this session).

Commits on `v4/no-vision-vector` in order:
1. `55138792` feat: no-vision vector route — skip Pass-1 Vision for vector PDFs
2. `19d4755c` feat: add per-step timings to the no-vision route (`_meta.no_vision_sekundes`)
3. `fc8310d4` feat: mixed-text-layer gate, early-break eksplikacija, tests, report
4. `2daef16b` docs: no-vision route report — final gate numbers, runtime table, moved rows
5. `f213837c` feat: no-vision route behind `SAMATU_NO_VISION_ROUTE` opt-in flag (OFF by default)
6. `c12a8017` fix: NameError `median_chars` in `is_vector_pdf` when PDF has text but no wall fills

## 1. What the route does

Pipeline, in order (events in CODE font are stream events):

1. `rendering_pdf`, `route_selected`, `started`, `pass1_started { skipped: true, note: "be vaizdo skaitymo" }` — the UI sees Pass-1 start and complete, with `skipped: true`.
2. `eksplikacija_started`/`eksplikacija_completed`: the room table from the drawing's text layer (`pdfplumber_eksplikacija.extract_eksplikacija_pdfplumber`). When pdfplumber refuses (`ambiguous_rows` > rows accepted — objektas_a), the eksplikacija page's TEXT is handed to `text.schema_llm.structure` with its substring guard. No sheet image is sent; the model's answer is kept only when its `source_text` is in the input text.
3. `pass1_completed { skipped: true, rooms_count }`: the room list, or blank with a reason.
4. `run_drawing_lanes` — the same function the paid reading and the eval tail call (page kinds from text, text-layer scan + anchors, dimension-string perimeters, raster outlines, text heights, geometry lane, legend counts). Emits `page_kinds_from_text`, `plan_dimension_lane`, `wall_outline_lane`, `geometry_lane`, `legend_counts`.
5. `zoom_started`/`zoom_completed` with `skipped: true` and 0 counts.
6. `apdailos_started`/`apdailos_completed`: wall finishes from the finish sheets' TEXT (fast path per sheet, else `text.schema_llm`).
7. `door_types_started`/`door_types_completed`: frameless/sliding from the drawing's text (no model).
8. `heights_from_drawing`: ceiling heights filled across rooms (`row_provenance.fill_heights_from_read`).
9. Deterministic scans (`plyteliu_specifikacija`, `symbol_legend`, `door_schedule`, `vector_symbols`).
10. `post_processing`: `_recompute_per_room_via_python` → `_build_pozicijos_from_rooms` → `_recompute_santrauka` → the sanity tail (`apply_lt_sanity`, `cross_page_validator`, `scale_validator`, `sanity_checks`, `consistency_checker`, `sanity_mirror`, v8 compat).
11. `_meta.vision_pass = "none"`, `_meta.route = "no_vision_vector"`, `_meta.route_sakinys = …`, `_meta.no_vision_sekundes = {eksplikacija, lanes, apdailos, door_types, heights, skenavimai, math_sanity}`.

## 2. Decision function

```
should_use_no_vision(pdf_bytes) → (True, "Brėžinys vektorinis — skaitoma be vaizdo modelio")
    when SAMATU_FORCE_VISION ≠ "1"
    and  SAMATU_NO_VISION_ROUTE = "1"                  ← opt-in flag (OFF by default)
    and  at least max(5, 20 % of pages) carry ≥ 10 chars of text layer
    and  there exists a page with ≥ 1 wall-shaped vector fill (`pdf_vectors.wall_fills`)
```

When `SAMATU_NO_VISION_ROUTE` is not `"1"`, the function returns `(False, sentence)` without reading `pdf_bytes` at all — zero cost.

The whole-document median was too strict on a 65-sheet TP where only ~20 sheets carry text and 45 do not: median = 0 even though every interior sheet has a text layer and the paid reading reads them. The share-of-pages rule gives objektas_b vector=True.

Falls open: any failure returns `(False, "<reason>")` and the Vision route is unchanged.

Verified by `test_is_vector_pdf_*`, `test_route_is_off_by_default`, and `test_should_use_no_vision_honours_force_vision_env`.

## 3. What stays on Vision (and why)

- **Raster / flattened PDFs** — `objektas_a_flat150.pdf` (0 chars/page): the text layer is gone. There is no deterministic source for room names, dimension strings or finishes; a model looking at the pixels is the only reader. The route predicate returns False and `extract_interior` runs its old Vision pipeline unchanged.
- **Vector PDFs without a readable room list** — objektas_c (3 A3 sheets, ~80 chars/page total; no eksplikacija), objektas_g (room-area labels present, room names only in the drawing). With the flag on, the route stops with the room list blank + reason; it does not call Vision as a fallback (founder rule, §0).

## 4. Runtime table

Old route (Vision pipeline): taken from the stored `_meta.elapsed_s` of `ai_extract.json` (the paid reads). New route: measured 2026-10-27.

| project | pages | OLD elapsed (ai_extract.json `_meta.elapsed_s`) | NEW elapsed | NEW stage (eks / lanes / apdailos / door_t / heights / scans / math) |
|---------|-------|-------------------------------|-------------|---------------------------------------------------------------------|
| objektas_a | 17 | 208,3 s | **205,7 s** | 134 / 69 / 54 / 0,01 / 0,0 / 10 / 0,03 — then 30 after eks cap |
| objektas_b | 65 | 468,3 s | **304,3 s** | 65 / 183 / 0,1 / 0,05 / 0,0 / 55 / 0,02 |
| objektas_c | 3 | 308,7 s | **15,8 s** (0 rooms) | — / 5,5 / — / — / — / 4,5 / — |
| objektas_d | 10 | 212,4 s | **20,6 s** | 1 / 11 / 0,1 / 0,01 / 0,0 / 7 / 0,02 |
| objektas_g | 16 | 1510,6 s | **122,5 s** (0 rooms) | — / 66 / — / — / — / 54 / — |
| objektas_h | 8 | 735,4 s | **17,5 s** | 2,3 / 12,4 / 0,0 / 0,01 / 0,0 / 3 / 0,02 |

The a and b runtimes are dominated by the text-schema calls, not Vision: a's eksplikacija call (~45 s) + apdailos call (~82 s), b's legend lane (~126 s of its 183 s total lanes). Lowering the legend budget is a one-env-var change that needs a re-measurement before being authorised.

## 5. Gate table

**Baseline** (today's Vision route, `ai_extract.json`): billed_lines **57,50 %**, rows ±10 % **9,0 %**, € ±10 % **18,0 %** (measured 2026-10-27 with `--totals-only --recompute`).

**No-vision hybrid** (a/b/d/h through no-vision route, c/g through Vision): billed_lines **65,86 %**, rows ±10 % **8,9 %**, € ±10 % **16,4 %**.

| metric | gate target (±1 pp) | baseline | no-vision hybrid | result |
|--------|---------------------|----------|------------------|--------|
| billed lines | 57,5 % ± 1 → 56,5–58,5 % | 57,5 % | 65,86 % | **FAIL** (+8,4 pp) |
| rows ±10 % | 9,0 % ± 1 → 8,0–10,0 % | 9,0 % | 8,9 % | pass |
| € ±10 % | 18,0 % ± 1 → 17,0–19,0 % | 18,0 % | 16,4 % | **FAIL** (−1,6 pp) |

Reading scorecard (baseline → hybrid): interior door pairs 21/24 → 21/24; exterior doors per room 32/32 → **25/32**; windows per room 29/30 → **26/30**; passages 2/4 → 2/4. **FAIL** — 7 exterior doors lost, 3 windows lost. The predecessor's "scorecard unchanged" was measured on restored `ai_extract.json` files, not on the no-vision extracts.

**Per-project rows ±10 % / € ±10 %, BASELINE → HYBRID:**

| project | baseline rows / € | no-vision rows / € |
|---------|-------------------|--------------------|
| objektas_a | 9,4 % / 37,9 % | 9,4 % / 33,3 % |
| objektas_b | 1,8 % / 1,2 % | 0,9 % / 1,2 % |
| objektas_c | 5,6 % / 4,0 % | unchanged (Vision) |
| objektas_d | 14,0 % / 15,0 % | 10,0 % / 5,0 % |
| objektas_g | 15,0 % / 49,1 % | unchanged (Vision) |
| objektas_h | 8,3 % / 0,9 % | 12,5 % / 6,0 % |

Only h improves; a, b, d get worse. The earlier predecessor table (a 7,5 / 33,3, b 0,9, c 15,0 / 11,4) was wrong — those were the no-vision numbers, not the baseline.

**Family-level billed lines (Σ his vs Σ ours per family), BASELINE → HYBRID:**

| project | family | baseline | no-vision hybrid |
|---------|--------|----------|------------------|
| objektas_a | Dažymas | −0,06 % | +7,61 % |
| | Kampai | −10,51 % | −13,71 % |
| | Angokraščiai | +17,25 % | −24,99 % |
| | GKP lubos | −6,42 % | −21,56 % |
| | Rotband | −100 % | −100 % |
| | Plytelės | −0,66 % | +43,45 % |
| | **MAE** | **22,48 %** | **35,22 %** |
| objektas_b | Dažymas | −54,57 % | −54,57 % |
| | Kampai | −100 % | −100 % |
| | Angokraščiai | −10,64 % | −94,09 % |
| | GKP lubos | −100 % | −100 % |
| | Rotband | −100 % | −100 % |
| | Plytelės | −9,11 % | −35,50 % |
| | **MAE** | **62,39 %** | **80,69 %** |
| objektas_c | (Vision both) | Dažymas −76,03 %, Angokr. +7,73 %, Plytelės −49,79 % | **MAE 72,26 %** |
| objektas_d | Dažymas | −72,58 % | −72,58 % |
| | Angokraščiai | −6,38 % | −100 % (row gone) |
| | Plytelės | −18,05 % | −18,05 % |
| | **MAE** | **66,17 %** | **81,77 %** |
| objektas_g | (Vision both) | Dažymas −8,10 %, Plytelės −58,24 % | **MAE 55,45 %** |
| objektas_h | Dažymas | +12,21 % | +12,21 % |
| | Angokraščiai | +21,64 % | +9,31 % |
| | **MAE** | **66,77 %** | **64,30 %** |
| **Billed lines (all 32 obs.)** | | **57,50 %** | **65,86 %** |

## 6. Moved families — with causes

- **objektas_a**: MAE 22,48 % → 35,22 %. Angokraščiai swings from +17,25 % to −24,99 % (drawn-opening reconciliation overwrites the correct reading: room 101 gains a window it does not have). GKP lubos worse (−6,42 % → −21,56 %) because LED niches (read from ceiling plan by Pass-1) have no source on this route. Plytelės swings to +43,45 %.
- **objektas_b**: MAE 62,39 % → 80,69 %. Angokraščiai nearly wiped (−10,64 % → −94,09 %) because the drawn-opening reconciliation on b produces fewer windows and exterior doors than Pass-1 Vision.
- **objektas_c**: unchanged (Vision on both sides). Root cause: no eksplikacija, no room-name words in text layer — route would produce 0 rooms.
- **objektas_d**: MAE 66,17 % → 81,77 %. Angokraščiai row completely gone (−6,38 % → −100 %) because `_angos_sienose_suderinta=False` on d (no wall outlines) means every window and door count comes back 0.
- **objektas_g**: unchanged (Vision on both sides). Root cause: room names are graphical labels only.
- **objektas_h**: MAE 66,77 % → 64,30 % (slight improvement). Angokraščiai improves (+21,64 % → +9,31 %) because drawn-opening counts on h happen to agree better with the contractor's than Pass-1 Vision did.

## 7. Tests

`backend/tests/test_no_vision_route_2026_10_26.py` — **10 passed** (2026-10-27):

- `test_is_vector_pdf_true_on_vector_with_text_and_walls`
- `test_is_vector_pdf_false_on_empty_raster`
- `test_route_is_off_by_default` ← new (checks flag is checked before any PDF work)
- `test_should_use_no_vision_honours_force_vision_env`
- `test_rooms_from_table_shape_feeds_calc_room_quantities`
- `test_rooms_from_table_calcs_through_calc_room_quantities`
- `test_pass1_and_zoom_events_are_emitted_as_skipped`
- `test_meta_marks_the_route_as_no_vision`
- `test_route_wiring_in_extract_interior_prefers_no_vision_on_vector`
- `test_is_vector_pdf_text_but_no_walls_returns_false_without_nameerror` ← new (NameError regression)

Golden replay (`test_golden_replay_extract_interior.py`): **6 passed** (sets `SAMATU_FORCE_VISION=1` — Vision pipeline unchanged).

Full backend suite with `SAMATU_AUTH_DISABLED=1`: **5313 passed, 9 skipped**, 0 failed (pre-existing 9 skips for network/OAuth/R2 tests).

## 8. Decisions taken

1. **Keep the stream event names.** The frontend's SSE state machine listens to `pass1_started/completed` and `zoom_started/completed`; emitting the same names with `skipped: true` + a note means no UI change.
2. **Only text.schema_llm, when needed.** The ONLY model call allowed on this route. On the four projects that have an eksplikacija text layer AND finish sheets that name one room per sheet, no model call fires at all (b, d, h). On a the model is called twice (eksplikacija ≤ 2 pages, apdailos one call); eksplikacija stops at the first page that yields ≥ 5 rooms.
3. **Blank-with-reason over a Vision fallback for c/g.** When the route flag is on and the room list cannot be recovered from the drawing's text, the route stops with a warning instead of asking Vision. With the flag off (default), c and g go through Vision unchanged. A Vision fallback specifically for "no room list" is the manager's recommended next step if this route is pursued (see §9).
4. **`SAMATU_FORCE_VISION=1` opt-out.** For side-by-side comparison the old route stays reachable; checked before the `NO_VISION_ROUTE` flag. The golden replay tests set it so the Vision pipeline's reader stubs still fire.
5. **Legend lane budget is unchanged** (120 s, from `AUTO_BUDGET_S`). The Vision route runs the same lane; lowering it here would also lower it on the Vision route or require a per-route override. Left as-is pending the founder's call.
6. **Mixed-text-layer gate.** A share-of-pages rule (max(5, 20 %) with ≥ 10 chars) instead of a whole-document median, so a 65-sheet TP whose last 45 sheets have no text layer still routes to no-vision as long as the ~20 interior sheets have one. objektas_b wins by this.
7. **Landed OFF behind `SAMATU_NO_VISION_ROUTE`.** The measured gate failure (billed lines +8,4 pp, scorecard −7 doors −3 windows) means today's behaviour is byte-identical and the founder can switch the flag on locally. This is not a replacement for Pass-1 until the lost fields have deterministic sources.

## 9. What is open

What would make the route a real Pass-1 replacement, in priority order:

1. **Per-room openings where no outline exists.** `_angos_sienose_suderinta=False` on d kills every window and door count. Need a deterministic source for openings on plans without wall outlines (door-arc + glazing-line scanner that does not require a closed polygon), and a reconciliation that does not overwrite a correct count with a drawn one.
2. **LED niches from the ceiling plan's vector lines / legend.** `nisa_led` and `nisa_uzuolaidu` are read by Pass-1 from ceiling-plan images. A vector-line scanner on ceiling plan sheets (text-classified as `lubų_planas`) can recover them deterministically.
3. **Hidden/sliding doors from the door schedule scanner on every project.** The door schedule scanner (`door_schedule.scan_door_schedule`) already fires on this route, but it only reads schedules; hidden/sliding doors on plans without a schedule (a, h) still have no source.
4. **Built-in furniture from the furniture plan.** `spinta_built_in` is read by Pass-1 from furniture plan images. A page-kind-classified vector scanner would replace it.
5. **Ceiling type.** `lubu_tipas` (stretch vs GKP vs plain) is a Pass-1 Vision read that has no deterministic substitute yet.
6. **Room list fallback to Vision for c/g.** With the flag on, c and g return 0 rooms with a warning. A targeted Vision call for "no room list" (single image of the plan sheet, prompt limited to `(nr, name, m²)` triples) would unblock those two projects without paying the full Pass-1 cost.
7. **Legend-lane budget on big TPs.** `AUTO_BUDGET_S = 120 s` is hit by b (126 s) and g (55 s). A per-route budget override is a one-env-var change once the gate passes.
8. **a's two text-schema calls (~45 + ~82 s).** The eksplikacija call is already capped at 2 pages and stops early; the apdailos call could be replaced by a pdfplumber finish-schedule table reader if p4's table is machine-readable.

**Alternative the manager will put to the founder:** narrow Pass-1 instead of removing it — choose only plan + ceiling + furniture sheets by text page-kind, turn voting off, limit the prompt to the five field groups above. This would cost ~7 USD of paid reads to gate against the 6-project corpus and would tell whether the lossy field is the prompt, the resolution, or the lane interaction.

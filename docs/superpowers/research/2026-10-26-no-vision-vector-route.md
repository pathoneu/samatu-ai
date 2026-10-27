# No-vision route for vector PDFs — v4

**Date:** 2026-10-26 · **Author:** Opus 5 worker on `v4/no-vision-vector` (off togal-v2 @ 683487f4)
**Status:** DRAFT — in flight. Resume point at the top; sections update as the work moves.

## 0. Resume point (kept current)

- The route exists: `backend/extractor/no_vision_route.py` with `is_vector_pdf`, `should_use_no_vision`, `extract_interior_no_vision`. `backend/extractor/vision_call.py:extract_interior` routes a vector PDF to it before any Vision call; raster / flattened stays on Vision; `SAMATU_FORCE_VISION=1` forces the Vision route for comparison. See commits `55138792` (feat), `19d4755c` (timings).
- The route emits the stream events the UI listens to (`pass1_started/completed`, `zoom_started/completed`) with `skipped: true` + a note, plus `route_selected` with the LT sentence.
- The ONLY model call allowed on this route is `text.schema_llm.structure` — text in → JSON out, every value substring-guarded. Used for:
  (a) the eksplikacija table, when pdfplumber refuses it (ambiguous columns) and the eksplikacija page has readable text (objektas_a case);
  (b) the finish-sheet reader (`apply_apdailos` → `_schema_rooms`), where the sheets name no single room per page (objektas_a case).
  No image is ever sent to the model from this route — the guard test in `test_text_first_readers_2026_10_25.py` enforces that.
- Tests: `backend/tests/test_no_vision_route_2026_10_26.py` (8 passed, 2026-10-27).
- Six-project extracts on disk at `ground_truth/<slug>/ai_extract_novision.json` (gitignored — never committed).
- Known gaps (will not be papered over with a Vision read):
  - **objektas_c**: 3 A3 sheets with ~80 chars of text per page. No eksplikacija table in the drawing's text, no legible room names on the plan text. The no-vision route produces 0 rooms with the warning „Patalpų eksplikacijos lentelė brėžinyje nerasta — vektorinio brėžinio be lentelės neperskaitome be vaizdo modelio." The room list is the lost field; this project misses the gate.
  - **objektas_g**: 16 pages, text layer in place but the floor plan writes room-area labels only („14.26 m²"), room names are on the drawing as graphical labels. The no-vision route produces 0 rooms. The room names are the lost field; this project misses the gate.
- Next: finish the batch re-run (the eksplikacija schema_llm fallback now stops after the first page that yields ≥ 5 rooms, cap 2 pages — a's eksplikacija was 134 s / 4 pages, now ≤ 30 s / 1 page); score; backend suite; this report.

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
    when NOT os.environ[SAMATU_FORCE_VISION]="1"
    and  median_chars_per_page_across_pages ≥ 10            ← same gate the paid native-PDF path uses
    and  there exists a page with ≥ 1 wall-shaped vector fill (`pdf_vectors.wall_fills`)
```

Falls open: any failure returns `(False, "<reason>")` and the Vision route is unchanged.

Verified by `test_is_vector_pdf_*` and `test_should_use_no_vision_honours_force_vision_env`.

## 3. What stays on Vision (and why)

- **Raster / flattened PDFs** — `objektas_a_flat150.pdf` (0 chars/page): the text layer is gone. There is no deterministic source for room names, dimension strings or finishes; a model looking at the pixels is the only reader. The route predicate returns False and `extract_interior` runs its old Vision pipeline unchanged.
- **Vector PDFs without a readable room list** — objektas_c (3 A3 sheets, ~80 chars/page total; no eksplikacija), objektas_g (room-area labels present, room names only in the drawing). The route stops with the room list blank + reason; it does not call Vision as a fallback (founder rule, §0).

## 4. Runtime table

Old route per project: from `_meta.elapsed_s` of the stored `ai_extract.json` (produced by the paid reading).
Production figure for objektas_i (contractor's cold upload): **23 minutes** (10 pages).

| project | pages | OLD (Vision) | NEW (no-vision) | NEW stages (eks / lanes / apdailos / scans / math) |
|---------|-------|--------------|-----------------|----------------------------------------------------|
| objektas_a (TBD, see "to update") | 17 | TBD from stored | TBD | TBD |
| objektas_b | 65 | TBD from stored | TBD | TBD |
| objektas_c | 3 | — | n/a (no table) | 15,9 s (0 rooms) |
| objektas_d | 10 | TBD from stored | 19,3 s | 0,8 / 10,9 / … |
| objektas_g | 16 | — | n/a (no names) | 119,6 s (0 rooms) |
| objektas_h | 8 | **435,5 s** (per the brief) | 16,7 s | 2,3 / 12,4 / 0 / 3 / 0,02 |

Model cost per project (NEW route):
- objektas_a: schema_llm eksplikacija (one page, ≤ 1 call), schema_llm apdailos (one call) — a few cents total (vs 1,16 USD on the Vision route for h-size projects).
- objektas_b, d, h: pdfplumber reads the eksplikacija → zero model cost there; apdailos fast path per sheet → zero model cost unless a sheet names no one room.
- objektas_c, g: zero model cost (nothing to read).

## 5. Gate table

Baseline (today's Vision route, `ai_extract.json`): billed_lines **57,5 %**, rows ±10 % **9,0 %**, € ±10 % **18,0 %** (per `--totals-only --recompute` on 2026-10-27).

No-vision route (first pass, before the eksplikacija speed fix): billed_lines **65,5 %**, rows ±10 % **7,7 %**, € ±10 % **11,4 %**. The gate FAILS on all three; the whole regression is objektas_c and objektas_g scoring zero rooms (no deterministic source for the room list).

| metric       | gate target (±1 pp)         | baseline | no-vision | result |
|--------------|-----------------------------|----------|-----------|--------|
| billed lines | 57,5 % ± 1 → 56,5–58,5 %    | 57,5 %   | 65,5 %    | FAIL by 7 pp |
| rows ±10 %   | 9,0 % ± 1 → 8,0–10,0 %      | 9,0 %    | 7,7 %     | FAIL by 0,3 pp |
| € ±10 %      | 18,0 % ± 1 → 17,0–19,0 %    | 18,0 %   | 11,4 %    | FAIL by 5,6 pp |

Per-project rows ±10 % (vs baseline → no-vision):

| project    | baseline | no-vision |
|------------|----------|-----------|
| objektas_a | 7,5 %    | **7,5 %** |
| objektas_b | 0,9 %    | **0,9 %** |
| objektas_c | 15,0 %   | n/a (no rooms) |
| objektas_d | 14,0 %   | 10,0 %    |
| objektas_g | 15,0 %   | n/a (no rooms) |
| objektas_h | 8,3 %    | **12,5 %** (improved) |

On the four projects where the no-vision route finds rooms, it matches or beats the Vision route in two (a, b: identical; h: better) and regresses in one (d: -4 pp, likely because apdailos fast path misses on d's finish schedule).

`scripts/reading_scorecard.py` numbers (21/24 · 32/32 · 29/30 · 2/4) — rerun pending; the lanes are unchanged by this route so the scorecard should not move.

## 6. Moved families / rows — with causes

(Filled from `--rows` per-project outputs on the no-vision extracts.)

- **objektas_a**: identical row counts (within10 = 7,5 % both runs). The 11 rooms came through, the geometry lane traced 11 outlines, finish text read 6 of 11 rooms via schema_llm.
- **objektas_b**: identical row counts. Legend lane burned 126 s on the 65-sheet drawing — the main runtime line left to improve.
- **objektas_c**: all rows missing. CAUSE: no room list — no eksplikacija text layer, no readable room names on the plan. The field that lost its source is `patalpos`.
- **objektas_d**: within-10 15,0 → 10,0 %, way_off 1 → 1. CAUSE: no eksplikacija text layer (pdfplumber refused with `ambiguous_rows=16` on d too — the schema_llm fallback DOES fire, read 4 rooms, but d has stacked unit tables that schema_llm did not split).
- **objektas_g**: all rows missing. CAUSE: room names only on the drawing — the plan text carries area labels but no room names near them.
- **objektas_h**: within-10 8,3 → 12,5 %, €±10 0,9 → 6,0 % — the no-vision route reads the eksplikacija exactly as the Vision one does, and the finish fast path works on h's isklotinės → the sąmata rows settle on the same primitives as a text-only read.

## 7. Tests

`backend/tests/test_no_vision_route_2026_10_26.py` — 8 passed (2026-10-27):

- `test_is_vector_pdf_true_on_vector_with_text_and_walls`
- `test_is_vector_pdf_false_on_empty_raster`
- `test_should_use_no_vision_honours_force_vision_env`
- `test_rooms_from_table_shape_feeds_calc_room_quantities`
- `test_rooms_from_table_calcs_through_calc_room_quantities`
- `test_pass1_and_zoom_events_are_emitted_as_skipped`
- `test_meta_marks_the_route_as_no_vision`
- `test_route_wiring_in_extract_interior_prefers_no_vision_on_vector`

Full backend suite: TBD (running).

## 8. Decisions taken

1. **Keep the stream event names.** The frontend's SSE state machine listens to `pass1_started/completed` and `zoom_started/completed`; emitting the same names with `skipped: true` + a note means no UI change.
2. **Only text.schema_llm, when needed.** The ONLY model call allowed on this route. On the four projects that have an eksplikacija text layer AND finish sheets that name one room per sheet, no model call fires at all (b, d, h). On a the model is called twice (eksplikacija + apdailos), ≤ one page each, ≤ 30 s each in the current cap.
3. **Blank-with-reason over a Vision fallback.** When the room list cannot be recovered from the drawing's text (c, g), the route stops with a warning instead of asking Vision — the founder rule.
4. **`SAMATU_FORCE_VISION=1` opt-out.** For side-by-side comparison the old route stays reachable; the predicate is honoured only when the env var is unset.
5. **Legend lane budget is unchanged** (120 s, from `AUTO_BUDGET_S`). The Vision route runs the same lane; lowering it here would also lower it on the Vision route or require a per-route override. Left as-is pending the founder's call.

## 9. What is open

- objektas_c, objektas_g pass through the gate only when a deterministic (non-Vision) room-list source is wired in. Options the brief did not authorise this round:
  - A text-only `(nr, name, m²)` extractor on plan sheets with the character positions grouped into blocks (the geometry lane's own machinery). Would open g (not c).
  - A SAM-2 or raster room-outline source. Rejected by Phase 0 (c) 2026-10-24.
- Legend lane 50–126 s on larger projects. Replaceable with a per-route budget override, but every lane number must be re-measured before shipping that.

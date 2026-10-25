# Kill model rows (v4 Phase 3b) — 2026-10-25

Branch `v4/kill-model-rows` from `togal-v2` @ bc6005fe (room identity merged). Worker: Opus 5.5. Not merged. No paid
call anywhere (dead key; the cold runner and the golden replay refuse to build a client). Inventory of where every
row comes from: `2026-10-25-row-provenance-inventory.md`.

## Resume point

- DONE: inventory (commit 1), row kills in four commits, Vision geometry modules deleted with their tests and
  frontend callers, cold-runner sąmata stage + guard test, LANE_VERSION 18, one plain rows pass, golden replay on h,
  touched backend tests, frontend units / lint / build. Merge of togal-v2 at the end (see the hand-back).
- NOT done by me (pacing rule): the full backend suite and the three other eval passes — the manager runs them.

## 1. The rule as code — `backend/extractor/row_provenance.py`

Every row the builder emits carries `_kilme`: `drawing` (text layer, geometry lane, vector symbol counter, a legend,
his entry), `derived` (a formula over drawing facts with a named convention), `model-3c` (a reader of a table or text
image that Phase 3c moves onto the text layer — the plumbing reader's counts, the door-type reader's frameless count,
the sanitary tub count), or `blank` (kiekis None, „—" on screen, `_assumption` = `_tuscia_priezastis` = a plain LT
sentence saying what to check). `model` and `default` never stay on a row with a number; `illegal_rows()` is the guard.
`_kilme` and `_tuscia_priezastis` ride onto `darbu_sarasas` (`_emit_v8_compat_fields`).

Room inputs: `perimeter_class` (legal: dimension strings, table, outline he drew or the lane traced incl. its
outline-length estimate, his entry; Pass-1 and zoom = model; the √A square = default) and `height_class` (legal: an
altitude printed in the room, the plan's statement, a section marker the project height came from, his entry; „kaip
kitose" = the height read in the other rooms; Pass-1 per-room / section / zoom heights = model; 2,82 m with no read
project height = default). `gate_room_inputs` blanks every per-room row (walls, Rotband, corners, skirting, cornice,
wall tiles, silicone, 45° cuts, tile skirting, scaffolding) while a room behind it has an illegal input, naming the
rooms; a row billed at the drawing's own total (wall-finish legend, floor-plan legend, room-table total) is `drawing`
whatever the rooms are.

## 2. What changed, row by row

| family | before | after |
|---|---|---|
| Ortakių D100/125/160 + izoliacija + tvirtinimas | Pass-1 lengths, else diffusers × 5 m of D125, × 0,7, ÷ 1,5 | three blank rows „Ortakių … — suveskite ilgį / kiekį", only where the drawing shows ventilation (diffusers on the paths, or the reading saw duct marks) |
| Šiukšlių išvežimas | floor area × 0,075 m³ | blank, „Statybinių atliekų kiekio brėžinys nenurodo — įrašykite, kiek m³ išvešite." |
| Apsauginės dangos / juostos | whole floor area | blank; the sentence offers the rooms' floor area |
| LED nišų glaistymas/dažymas, Nišų formavimas GKP, LED juostos pajungimas | Pass-1 / niche locator lengths + room-type estimate | the legend's LED length (text layer, `plan_area_annotations` now reads „LED juosta; šviesos šaltinis – 24,00 m"), with an anchor ledger step and the sentence naming the legend and the plastered-in strip apart; no legend → blank when the reading saw niches at all |
| GKP lubų montavimas (+ siūlės, lapai, CD, UW, savisriegiai) | ceiling type from Pass-1 or the room type | only where every GKP room has a ceiling-plan altitude printed in it (`ceiling_plan_marker`); otherwise blank, the rooms named, their ceiling area offered; the goods leave the shopping list |
| Durų angų paruošimas beapvadinėms durims | frame type from one plan symbol extended to every door | kept from his answer, the door schedule, a governing note, or frameless doors the door-type reader read in the text (3c); otherwise blank with the frame-type sentence and where to choose |
| Heights | 2,82 m constant; Pass-1 2,2 / 2,0 m in bathrooms | Step 2.885 `fill_heights_from_read`: a room takes the height read elsewhere („kaip kitose"), else none — every height-dependent row blank; the question „Kokio aukščio lubos?" answers it; Step 2.4.5 marks a text-marker project height `pjuvio_zymuo` |
| Perimeters | Pass-1 figure; √A square; the 4·√A floor | rows blank while the room has no outline, strings or entry; floor flag OFF; Step 4.066 (`_perimeter_validation`) and `perimeter_warning` deleted |
| Rotband | 30 % prielaida | blank until he sets the share („Ką skaičiuoti") |
| Didžiaformačių plytelių (2 rows) | tile total × 0,30 | blank unless `didzformat_share` is set |
| Slenksniai | rooms − 1 | blank |
| Lentynėlės | 2 per shower | blank unless he set the number per shower and the plumbing plan counts the showers |
| Santechnika (WC rėmas, klozetas, praustuvė pairs, gyvatukas, latakas, dušo pair, nuolydis, skalbimo mašina, plautuvė, WC dėžutė) | room-type counts, Pass-1 glyph counts | the plumbing reader's counts stay (`model-3c`); room-type counts blank with „pagal patalpų paskirtį būtų N vnt."; Pass-1 glyph counts blank |
| Skylių gręžimas | glyphs × holes, else openings × 4 | from the plumbing reading only (3c); otherwise blank |
| Elektra (rozetės, šviestuvai, skylės, pakabinami, apdirbimas) | Pass-1 glyph counts | blank, „Suskaičiuokite įrankiu „Ženklai“ arba įrašykite" |
| Difūzoriai | vector count, else Pass-1 count anchored by the legend scan | vector count only (`drawing`); else the existing checklist row |
| Partition walls (corner term) | Vision adjacency `n_partition_walls` | not read any more; a stored value is ignored unless the room is his merge (`_sujungimas`) |

Kept and listed (not 3b): angokraščiai (rest on Pass-1 + lane openings; the lane's drawn openings are Phase 1, the
readers 3c), floor coverings and floor tiles by room type and the wall-tile band from the Nustatymai bathroom
height (the rules worker's scope / conventions profile), molio tinkas and wallpaper (apdailos reader, 3c),
„Reviziniai dureliai" 1 per wet room and the hydro `vnt` (conventions).

## 3. Deleted (plan §6)

`vision/bbox_locator`, `room_graph_extractor`, `adjacency_extractor`, `dimension_extractor` (its two helpers moved to
`vision/_image_json.py` for the height and schedule readers), `niche_locator`, `elevation_extractor`, `symbol_detector`,
`built_in_detector`, `perimeter_validator`, and the dead chain that only they fed: `per_room_zoom_pipeline`,
`page_dispatch`, `plan_assembler`, `geometry_solver`, `elevation_aggregator`, `tile_calculator`, `legend_injection`;
`niche_inference`, `objektas_d_estimator`, `agentic_crop`, `verify_pass` (+ flag), `vision_call_v2`,
`calibration_learner`, `cv_wand`, `cv_polygon`; `api/vision_fill`, `api/vision_readers`, `api/symbols`; routes
`/api/click-to-fill`, `/api/projects/{id}/detect-room-polygons`, `/api/cv/magic-wand`, `/api/projects/{id}/detect-symbols`;
`vision_call.vision_polygon_at_click`, `perimeter_warning`, `_meter_niche_call`, the agentic-zoom branch, the
adjacency pass in voting; scripts that only drove them. Frontend: `lib/clickToFillApi.js`,
`lib/detectRoomPolygonsApi.js`, `MagicWandTool.jsx`, the auto flood-fill effect and its banner in
`InteriorWorkspace`, the raster fallback of the room tool and the click flood fill in `TakeoffViewer` (a click now
says to use the room tool), „Kontūras paspaudus" in the legacy `PlanViewer`, „Aptikti simbolius" in the Annotator.
The one-click outline (`outline-at`) stays.

**Kept against the brief's list:** `cv_match.py` and `/api/cv/find-symbol` / `match-template` / `upload-pdf` /
`record-decision`. They are deterministic template matching on a glyph the person boxed, every count confirmed by
him — the raster count path plan §6 itself prescribes — and `legend_rows`, `sheet_zones` and `api/legend_count`
import them. `interior_v9/symbol_detector` and `/v9/symbols/*` were not in my list and stay. `wall_elevation.py`
(opt-in `WALL_ELEVATION_EXTRACT`, off) stays for 3c.

## 4. objektas_i — the cold runner's app variant (his scope, production's model readings carried in)

`scripts/cold_run/run_cold.py` got a sąmata stage: the app variant's lane rooms + production's model readings by old
key + the project text scans → Step 2.885 → per-room engine → builder → his scope filter. Upload A (B is identical):
29 rows — blank 16, derived 10, drawing 2, model-3c 1; **model/default with a number: none** (B the same).

| row | before (production) | after |
|---|---|---|
| Sienų lyginimas Knauf Rotband | 166,32 m² | — Rotband dalis: „Ką skaičiuoti" |
| Sienų glaistymas/dažymas | 554,4 m² | — „Lubų aukščio brėžinyje neradau — atsakykite klausimą „Kokio aukščio lubos?“" |
| Dažymo kampų montavimas | 622,12 m | — same (and the corner convention is the rules worker's) |
| Angokraščių glaistymas-dažymas / apdirbimas GKP | 83,22 m | 105,58 m (lane-drawn windows now, listed) |
| Durų angų paruošimas beapvadinėms durims | 75,3 m | — frame type sentence + „Nustatymai → Vidaus durys" |
| Lubų glaistymas/dažymas | 207,1 m² | 207,1 m² |
| LED nišų glaistymas/dažymas, Nišų formavimas GKP | 17,6 m | **24,0 m** (legend, sheet 7; „Priglaistoma LED juosta 2,40 m" named apart) |
| LED nišos — suveskite ilgį | blank | gone (folded) |
| GKP lubų montavimas + siūlės | 207,1 m² + 310,65 m | — no ceiling-plan altitude in any room; the 207,10 m² offered |
| Pertvaros sutvirtinimas WC (GKP dėžutė) | 4 | 4 (plumbing reader, 3c) |
| Ortakių D125 / izoliacija / tvirtinimas | 25 m / 17,5 m / 17 vnt | three blank rows „— suveskite ilgį / kiekį" |
| Šiukšlių išvežimas | 15,5 m³ | — |
| Apsauginės dangos | 207,1 m² | — (207,10 m² offered in the sentence) |
| Statybvietės sutvarkymas | 1 kompl | 1 kompl |
| Medžiagos | 17 rows | 6 (only the goods of rows that keep a number) |

## 5. Eval — one plain pass (`--rows --recompute --gate`), the pacing rule

| project | rows ±10 % before → after | € ±10 % before → after |
|---|---|---|
| objektas_a | 37,7 → 5,7 % | 32,4 → 10,1 % |
| objektas_b | 9,9 → 3,6 % | 21,0 → 6,8 % |
| objektas_c | 22,2 → 8,3 % | 12,1 → 5,9 % |
| objektas_d | 36,0 → 12,0 % | 60,3 → 13,8 % |
| objektas_g | 30,0 → 30,0 % | 55,6 → 55,6 % |
| objektas_h | 20,8 → 12,5 % | 26,7 → 2,0 % |
| corpus | **26,1 → 12,0 %** | **34,7 → 15,7 %** |

GATE FAIL on a, b, c, d, h — expected: a blanked row counts as missing. 103 of his lines moved (108 with romainiai);
**40 of them were within ±10 % on a model or default figure and are now missing** (a 17, b 7, c 2, d 12, h 2) —
R1/R7 win, they stay blank. Causes, every moved line in one of these:

- **heights** (no text height on a, b, c, d's other rooms, g, h in the frozen extracts): walls, corners, Rotband,
  scaffolding blank — a 16/17 (only the rooms whose heights the positioned markers read stay), b 16, d 13/14, b 111.
- **perimeters** (Pass-1 on a, b, c, d, h frozen): skirting, silicone, 45° cuts, tile skirting, wall tiles — a 34–36,
  25; b 28, 37, 38, 103; c 16, 17; d 20, 24, 25, 45; g 11, 14, 17 (g's room 07 has no outline); h 15.
- **GKP ceilings** (no ceiling-plan altitude in the frozen rooms): a 1–2, b 1–2, d 1, h 1.
- **LED** (no legend length in the frozen figures — they predate the reader fix; the replay pass re-reads): a 3, 23;
  b 4, 27; c 11; d 4 (2,2 m where a legend figure exists); h 4, 21; c 4, d 43 (LED juostos pajungimas).
- **frameless doors** (symbols / annotations only): a 18, b 19, h 14.
- **plumbing by room type / Pass-1 glyphs** (no plumbing reading on a, b, c, d): a 7, 30, 32, 33, 40–50; b 6, 33–36,
  85–88, 95, 97; c 13, 15, 18; d 5, 21, 23, 26–34.
- **electrical Pass-1 counts**: a 10, 20; b 11, 21; c 1, 2; d 41, 42; h 10, 17 (h keeps its 9 diffusers from the paths).
- **rubbish**: a 53, b 110, c 9, d 46. **Rotband share**: a 15, b 15, d 12, h 12. **Lentynėlės**: a 29, b 33.
- **corners**: also g 20 (room 07 perimeter).

Full per-line list (label, his figure, before → after) in the hand-back.

## 6. Checks

| check | result |
|---|---|
| touched backend tests (every file that mentions the builder, recompute, extract_interior, eval, golden replay, row provenance, cv tools, model warnings — 2668 tests) | 2668 passed, 48 skipped |
| golden replay of `extract_interior` on objektas_h (no stored adjacency / niche answers needed any more) | 7/7 |
| `test_kill_model_rows_2026_10_25.py` (corpus guard ×6, objektas_i A/B cold run with `SAMATU_COLD_PDFS`/`_BLOBS`, units) | 16 passed |
| frontend units / eslint / build | 1661 pass, 1 skipped / clean / built |
| full backend suite, totals and replay passes | not run by me (pacing rule) |

## 7. For the manager / the rules worker

1. **Rules worker (`universal_rules` / `backend/rules/`)**: delete `_perimeter_floor_enabled` and the `4,18·√A`
   fallback in `calc_room_quantities` (the flag is OFF here, the rows are blanked, the code is theirs); the corner row
   (620 m) convention; `ceiling_height_m = 2,82` default parameter; the tile band and floor covering by room type are
   scope-profile questions; a comment in `universal_rules.py` still names `niche_inference`.
2. **Openings**: angokraščiai and door/window deductions still rest on Pass-1 `elementai` merged with the lane's
   drawn openings. Blanking them is the next consistent step (or the lane's drawn openings as the only source).
3. **Plumbing**: the sanitary reader's counts are kept as `model-3c`; Phase 3c should read the plumbing legend /
   text. Rooms without a plumbing reading now show blank fixture rows with the room-type count in the sentence.
4. **UI**: blank rows render through `_assumption` today; the frontend could show `_tuscia_priezastis` as the „—"
   tooltip. The LED estimate switch in Nustatymai (`led_nisu_ivertinimas`) does nothing now (accepted, not read) — its
   control should go. `niche_depth` (flag `SAMATU_NICHE_DEPTH`, off) no longer applies: per-room niche lengths are
   not a source.
5. The `adjacency_unread` warning no longer fires (there is no pass to fail); unread partition walls are the corner
   convention's question.
6. A stored project gets the legend LED length only after the free re-read — LANE_VERSION 18 offers it.

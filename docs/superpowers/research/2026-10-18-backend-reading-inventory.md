# What the backend can read or detect from a construction PDF (branch togal-v2, 2026-10-18)

Read-only inventory produced for the v3 programme design (Explore worker, reviewed by the backend manager). Every entry cites its entry point; statuses were checked against the mounted UI.

**Path prefixes:** `B/` = `backend/`, `F/` = `frontend/src/`, `T/` = `backend/tests/`, `R/` = repo root.

**Cost column:** "€0" = vector, text or raster math only. "Paid(role)" = a Claude call whose model comes from `models_config.model_for(role)`.

**Status column:** LIVE = a route the mounted UI calls · PAID-PIPE = runs only inside the paid `/extract-interior` run · BE-ONLY = route exists, nothing in the UI calls it · DEV = only the `Annotator` page (mounted in DEV only, `F/App.jsx:141`) · BENCH = scripts/bench/tests only · DEAD = nothing calls it.

**Viewers:** default viewer `TakeoffViewer`; `PlanViewer` only with `?viewer=legacy` (`F/components/project/InteriorWorkspace.jsx:114`).

---

## 0. Models config

- Roles (`B/models_config.py:68-79`): `vision_pass1`, `vision_pass2`, `doors`, `apdailos`, `sanitary`, `legend`, `page_classifier`, `symbols`, `extraction`, `chat`. Every role defaults to `claude-opus-5` (`:66`).
- Resolution at call time (`:87`): `SAMATU_MODEL_<ROLE>` → `MODEL_OVERRIDE` → legacy `VISION_MODEL` / `EXTRACTION_MODEL` → default. Exposed at `GET /api/config` (`B/api/config.py:11`). Feature flags: `B/extractor/feature_flags.py`.
- Bypasses models_config: `R/detector_bench/core/legend_extractor.py:33` hardcodes `claude-sonnet-4-6`.

## 1. Page classification and the text layer

| Capability | Entry (file:line) | Input | Output | Cost | Route | Frontend caller | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Shared pdfplumber parse (text, words, title-block `dalis`) | `B/extractor/pdf_page_cache.py:146` `page_signals`, `:175` `page_texts` | PDF bytes | per page `{text, words[{text,x0,x1,top,bottom}], width, height, dalis}` | €0 | internal | – | `T/test_pdf_page_cache.py` | LIVE (internal) |
| Title-block (antspaudas) dalis code: fixed crop (0.40,0.70)-(1,1) + `_DOC_CODE_RE` | `B/extractor/page_classifier.py:49,:352`; folded into `pdf_page_cache.py:117-128` | page text | `BD/SP/SA/SK/VVN/ŠVOK/E` or None | €0 | internal | – | `T/test_page_classifier_antspaudas.py` | PAID-PIPE (`page_filter` drops `SP` pages) |
| Pass-1 page selection: vendor quotes, wrong dalis, photo pages | `B/extractor/page_filter.py:343` `select_pass1_pages` | PDF + rendered pages | `PageSelection{decisions[page,keep,reason,signals]}` → `_meta.page_selection` | €0 | inside extract | – | `T/test_page_selection.py` | PAID-PIPE |
| Hybrid page classifier: Vision page type + antspaudas text | `B/extractor/page_classifier.py:396` `classify_page` | page image b64 (+pdf_path) | `PageClassification{page_type, confidence, top_2, dalis, roof_type_hint}` | Paid(page_classifier) | none | – | `T/test_page_classifier_hybrid.py`, `_schema.py`, `T/vision/test_page_classifier_routing.py` | BENCH |
| One page vocabulary | `page_classifier.py:91` `CANONICAL_TIPAI`, `:127` `canonical_tipas` | label | canonical `tipas` | €0 | – | – | `T/test_page_vocabulary.py` | LIVE (room_facts, height_markers) |
| Live page classification: Pass-1 `puslapiai[]` | `B/extractor/prompt.py:55` (schema), produced in `vision_call.extract_interior` | whole PDF | `puslapiai[{nr, tipas (16-value enum, no "legend"), pavadinimas, confidence, pastabos}]` | Paid(vision_pass1) | `/extract-interior` (`B/main.py:6193`), `/extract-interior-stream` (`:6515`) | `SheetRail.jsx`, `PageStructureCard.jsx`; user edits in `sheet_overrides` | – | LIVE |
| Preflight ("is this PDF the right type?") | `B/extractor/preflight.py:377` `preflight_pdf`, `:219` text `classify_page` | PDF | page kinds, estimate, `hard_block` | €0 | `POST /api/pdf-preflight` `B/main.py:4223` | `F/lib/preflight.js:133` | `T/test_pdf_preflight.py` | LIVE |
| Project type peek (kz / interior) | `B/main.py:4210`; `_classify_page` `:3132` regex | PDF | `{type}` | €0 | `POST /detect-type` | `F/pages/NewProject.jsx:64` | – | LIVE |
| PDFium character reader (all text directions, display frame) | `B/extractor/plan_area_annotations.py:221` `_iter_pages_pdfium`, `:348` `_iter_pages` | PDF | `(pn, W, H, chars, to_display)` | €0 | internal | – | `T/test_plan_area_annotations.py` | LIVE (internal) |
| One text-layer pass: area labels, author figures, height statements, dimensions | `plan_area_annotations.py:878` `scan_text_layer` | PDF + pages | `{annotations, figures, heights, dimensions}` | €0 | inside extract | – | `T/test_plan_area_annotations.py`, `test_geometry_dimension_source.py` | PAID-PIPE |
| `skaitoma_lt` sentence | `B/api/detect_run.py:103` `SKAITOMA_LT` | – | string on every detect-run snapshot | – | detect-run | `F/lib/detectRun.js` | `T/test_detect_run_api.py` | LIVE |

## 2. Scale and sheet alignment

| Capability | Entry | Input | Output | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Dimension strings + hairline, per-sheet scale (1:20..1:500, stated-scale check, reduced print, slanted strings) | `B/extractor/plan_dimensions.py:530` `read_dimension_strings`; `geometry_lane.py:388` `geometry_dimension_strings` | PDF | `{page, text, value_m, bbox, orientation, span, line_pos, span_source, scale_m_per_pt, mastelis, ilgis_pt, mastelis_kitas, mastelis_atmestas}` | €0 | detect-run / free-reread / outline routes | – | `T/test_plan_dimensions.py`, `test_slanted_dimensions.py`, `test_dimension_ilgis_pt.py` | LIVE |
| Two-string rectangle perimeter (`plano_matmenys`) | `plan_dimensions.py:732` `apply_dimension_strings` | rooms + dims | `perimetras_m`, `_perimetras_matmenys(_siulymas)` | €0 | – | – | same | PAID-PIPE (Step 2.44b) |
| Sheet alignment: same walls → one plan; storey clash | `B/extractor/sheet_alignment.py:144` `align_sheets`, `:158` `to_base`, `:163` `from_base` | PDF + plan pages + seats | `{groups, transform{page:{base,k,dx,dy}}, storeys}` | €0 | geometry lane | – | `T/test_sheet_alignment.py` | LIVE |
| Lane scales for the viewer | `geometry_lane.py:634` (`_meta.geometrija.masteliai`), `:624` `sutapdinimas` | – | stored keys | €0 | lane result | `F/lib/durableScale.js`, `pageScales.js`, `scaleCheck.js`, `ScaleCheckCard`, `RoomDrawingPane`, `checkOverlay.js` | – | LIVE |
| Scale hint from title text ("M 1:50") | `B/main.py:8078` `detect_scale_hint` | PDF b64 | `{found, page, scale_ratio, scale_text, confidence}` | €0 | `POST /detect-scale-hint` | `NewProject.jsx:683` | `T/test_security_loop_caps.py` | LIVE |
| Area-prior raster scale | `B/extractor/room_seeds.py:107` `calibrate_page_scale` | fill-area samples | m² per % | €0 | detect-room-polygons | – | `T/test_room_polygon_detect.py` | LIVE |
| Scale validator (claimed scale vs door widths) | `B/extractor/scale_validator.py:72,:105` | parsed + scale | warnings | €0 | – | – | `T/test_scale_validator.py` | PAID-PIPE (Step 4.06) |
| Manual scale calibration | client: `F/components/viewer/CalibrateDialog.jsx` → `pageScalesDurable` | – | – | – | – | viewer | `F/lib/durableScale.test.js` | LIVE (frontend) |

## 3. Rooms: location, outlines, click-to-fill

| Capability | Entry | Input | Output | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Room location: area label → number badge → Vision box | `B/extractor/room_locator.py:113` `locate_rooms` | PDF + rooms + plan pages | `{nr:{page, cx, cy, W, H, saltinis}}` → room `_vieta` | €0 | geometry lane | (`_vieta` not read by the frontend) | `T/test_room_locator.py` | LIVE |
| Area labels → room table (confirm / adopt / flag) | `plan_area_annotations.py:406`, `:480` | PDF / rooms | `_meta.plan_area_lane`, `_plotas_uzrasas`, `_ceiling_anchor` | €0 | – | – | `T/test_plan_area_annotations.py` | PAID-PIPE (Step 2.44) |
| Vector room outlines from wall fills (open spaces, pockets, proposals) | `B/extractor/vector_rooms.py:405` `trace_vector_rooms` | PDF, page, seats, table areas, scale | rooms `{polygon_pct, plotas_m2, perimetras_m, paklaida, plotas_nesutampa, sujungta, durys_m, angos}`, groups, reasons, siulymai → `polygon_source="vektoriniai_konturai"`, `_konturas`, `_atvira_erdve`, `_konturo_priezastis`, `_konturo_siulymas` | €0 | detect-run / free-reread | DrawingGeometryLayer, CheckLayer, `roomOutline.js`, `checkOverlay.js` | `T/test_vector_rooms.py`, `test_geometry_lane.py` | LIVE |
| "Parodyti patalpą": one click → outline under the click | `vector_rooms.py:479` `outline_at`; route `B/api/room_outline.py:183` | PDF + click % | `{status: ok|taken|open|outside|no_walls|shared, …}` + geometry keys (nothing saved) | €0 | `POST …/rooms/{nr}/outline-at` | `roomOutlineApi.js:31` → `RoomSheet.jsx:255`, `PatikraQuestions.jsx:278` | `T/test_room_outline_api.py` | LIVE (check sheet / Patikra only, **not the main viewer**) |
| Drawn-outline set / merge rooms | `room_outline.py:356`, `:438` | ring (+holes) | geometry keys, merge warning | €0 | outline-set / outline-merge | `InteriorWorkspace.jsx:386` | `T/test_room_outline_api.py`, `test_room_holes_walls.py` | LIVE |
| Split a shared space (drawn line / proposal) | `vector_rooms.py:677` `split_space`, `:754` `propose_split`; routes `room_outline.py:629,:660` | two points / seats | both outlines + `riba_pct` | €0 | split-space / split-proposal | RoomSheet, PatikraQuestions:188, FactRow | `T/test_room_split_api.py` | LIVE |
| Raster wall-outline lane | `B/extractor/wall_outline.py:256` | PDF + dims + labels | `polygon_source="sienu_konturas"` | €0 | – | – | `T/test_wall_outline.py` | PAID-PIPE (Step 2.44c) |
| Click-to-fill (OpenCV flood fill on a poppler raster) | `B/extractor/cv_polygon.py:299`; route `B/main.py:8157` | project, page, click %, sensitivity | `{polygon_pdf, page dims, confidence, fill_method}` | €0 | `POST /api/click-to-fill` | `clickToFillApi.js` → `TakeoffViewer.jsx:1199`; PlanViewer:386 | `T/test_cv_polygon.py` | LIVE (**the main viewer's click tool is raster, not vector**) |
| Batch label-seeded flood fill + area prior + dedupe | `cv_polygon.py:197`, `room_seeds.py:72`, `polygon_dedupe`; route `B/main.py:8263` | page + rooms_json | per-room polygons + stats | €0 | `POST …/detect-room-polygons` | `detectRoomPolygonsApi.js` → `InteriorWorkspace.jsx:278` | `T/test_room_polygon_detect.py` + 3 | LIVE |
| Magic wand | `B/extractor/cv_wand.py:16`; `B/api/cv_tools.py:344` | click px | polygon | €0 | `POST /api/cv/magic-wand` | `MagicWandTool.jsx` (not mounted) | `T/extractor/test_cv_wand.py` | BE-ONLY |
| Vision polygon at a click | `vision_call.py:7787` | – | – | Paid | `/api/vision-fill` (router commented out) | – | `T/test_vision_fill.py` | DEAD |
| Room graph for the Annotator | `B/api/room_graph.py:168` | project | polygons mm | €0 | GET `…/room-graph` | `Annotator.jsx` | `T/test_room_graph_api.py` | DEV |

## 4. Walls, openings, wall geometry

| Capability | Entry | Input | Output | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Vector wall fills (PDFium paths, display frame) | `B/extractor/pdf_vectors.py:262` `wall_fills`, `:226`, `:204`, `:198` | PDF + page | shapely polygons, paths, `(W,H,rot)` | €0 | – | – | `T/test_pdf_vectors.py` | LIVE (internal) |
| Wall solid rings for snapping / QA layer | `B/api/page_geometry.py:33`; route `:63` | PDF + page | `{width_pt, height_pt, status, walls_pct, vertex_count, truncated}` | €0 | `GET …/pages/{p}/geometry` | `pageGeometryApi.js` → `usePageGeometry.js` → `TakeoffViewer.jsx:464`, `DrawingGeometryLayer` | `T/test_page_geometry_api.py` | LIVE |
| Openings in each outlined room's walls (`_angos_sienose`) | `vector_rooms.py:859` `wall_openings`; `geometry_lane.py:164` | PDF, outlines, scale | `_angos_sienose{page, angos[{plotis_m, storis_m, line_pct, i, nupiesta, be_tarpo}]}` | €0 | lane / outline-at | DrawingGeometryLayer, `detectRun.js`, `roomOutline.js`, check sheet | 3 test files (2026-09-23) | LIVE |
| Openings as drawn: swing arcs, glazing, doors without a gap | `B/extractor/drawn_openings.py:99`, `:310`, `:372` | PDF + page + scale | marks, kind langas/durys | €0 | lane | via `_angos_sienose` | `T/test_drawn_openings_2026_09_25.py` | LIVE |
| Perimeters summed from strings along the walls | `B/extractor/dimension_sum.py:366` `sum_perimeters` | rooms, dims, alignment, scales | `perimetras_m`, `perimetras_saltinis`, `_sienos`, `_perimetras_suma` | €0 | lane | `checkOverlay.js` | `T/test_dimension_sum.py` | LIVE |
| Vector lines for snap-to-lines | `B/interior_v8/line_extractor.py:24`; route `B/main.py:7424` | PDF + page | lines | €0 | `POST /pdf-lines` | `pdfLinesApi.js` (never called) | none | BE-ONLY |
| Polygon shared edges | `B/extractor/wall_adjacency.py:159` | Vision polygons | `shared_with_neighbors_m` | €0 | – | – | `T/test_wall_adjacency*.py` | PAID-PIPE |
| Wall graph | `B/extractor/wall_graph.py` | – | – | €0 | – | – | `T/extractor/test_wall_graph.py` | DEAD |

## 5. Legends and symbols

| Capability | Entry | Input | Output | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Vector symbol counter from legend rows (today: diffusers only) | `B/extractor/vector_symbols.py:291` `count_legend_symbols(pdf, label_re, pages)`, `:375` `scan_vector_symbols` | PDF + label regex (only `DIFFUSER_LABEL_RE` wired); first 4 candidate pages | `{defined, count, pages, rows[{page, label, colour, size_pt, parts, count, kartojasi}], per_label, instances[{page, x_pct, y_pct, label}], sakinys}` → `_vector_symbols.difuzoriai` | €0 | Step 2.44 + free-reread / detect-run | `freeReread.js`, `recomputeContext.js` (count only; instances not drawn) | `T/test_vector_symbols_2026_09_24.py` | LIVE (count only) |
| Symbol-legend anchor scan | `B/extractor/symbol_legend.py:68`, `:130` | PDF text | `_symbol_legend{text_layer_ok, difuzoriai, karnizas}` | €0 | Step 2.42 | `recomputeContext.js`, `roomSheetApi.js` | `T/test_symbol_and_tile_evidence_2026_07_29.py` | PAID-PIPE |
| Designer's own legend totals | `plan_area_annotations.py:932` `read_author_figures` | PDF text | `_autoriaus_kiekiai[{page, label, value, unit, family, bbox}]`, anchors | €0 | Step 2.44 | `GeneralFactsPanel.jsx`, `roomSheet.js:625` | `T/test_room_facts_designer_total.py` | PAID-PIPE |
| "Rasti panašius": box → similar symbols (chamfer shape score) | `B/extractor/cv_match.py:179` `find_symbol_by_shape`; route `B/api/cv_tools.py:259` | `project_id, page_idx, template_page_idx, box_pt` (mediabox pts), `min_score` | `candidates[{x, y, box_pt, score, scale, rotation, mirrored, is_source}]`, `page_ink_share`, `skipped:"raster"`, `warning_lt` | €0 | `POST /api/cv/find-symbol` | `cvToolsApi.js:29` → `SymbolReviewPanel.jsx:67`, `SymbolSearchLayer`, `symbolSearch.js` | `T/test_cv_find_symbol.py` | LIVE (one page per call) |
| Click → template match (multi-scale, rotation, NMS) | `cv_match.py:63`; `cv_tools.py:213` | page idx + bbox px | matches | €0 | `POST /api/cv/match-template` | `CountTool.jsx` (not mounted) | `T/extractor/test_cv_match.py`, `T/integration/test_cv_e2e.py` | BE-ONLY |
| Prime the CV PDF cache | `cv_tools.py:161` | upload | – | €0 | `/api/cv/upload-pdf` | never called | `T/api/test_cv_upload_limits.py` | BE-ONLY |
| Training crops from accept/reject decisions | `B/extractor/training_data.py:34`; route `cv_tools.py:363` | box + klass + decision | PNG under `R/data/symbol_training/<klass>/` + `labels.jsonl`; a `corrections` row | €0 | `POST /api/cv/record-decision` | `SymbolReviewPanel.jsx:153` | `T/extractor/test_training_data.py`, `test_learning_loop.py` | LIVE (write only; nothing reads the crops) |
| Vision legend extractor + prompt injection | `B/extractor/legend_injection.py:74` `extract_legend`, `:119`, `:145` | legend page image | `{symbols[{glyph, colored_line, colored_hatch, meaning, confidence}]}` | Paid(legend) | none | – | `T/vision/test_legend_injection.py` | DEAD (no importer) |
| Project / architect legend store | `B/api/legends.py:123,135,141,156` | JSON | `R/data/legends/<pid>.json` | €0 | `/api/legends/*` | none | `T/api/test_legends_d4.py` | BE-ONLY (no producer) |
| Bench legend extractor (glyph bbox + PNG templates) | `R/detector_bench/core/legend_extractor.py:61`, `:98` | PDF path + page | `[{symbol_code, description_lt, category, glyph_bbox_pct, color_hint}]` + PNGs | Paid (hardcoded sonnet-4-6) | – | – | bench tests | BENCH |
| Vision symbol detection (sockets, lights, vents…) | `B/extractor/vision/symbol_detector.py:109`; route `B/api/symbols.py:62` | page image | `{page_role, symbols[{type, subtype, room_nr, x_pct, y_pct, confidence, evidence}]}` | Paid(symbols); `R/prompts/symbol_detection.txt` | `POST …/detect-symbols` | `Annotator.jsx` | `T/test_symbol_detector.py` | DEV/DEAD (`db.get_project_pdf_bytes` missing → 409) |
| V9 symbol detect / count-by-template | `B/interior_v9/symbol_detector.py:240,:325,:569`; routes `B/main.py:7292,7326,7385` | PDF | counts + positions | Paid(symbols) | `/v9/symbols/*` | `PlanViewer.jsx` (legacy) | `T/test_free_endpoints_not_metered.py` | LIVE in legacy viewer only |
| Pass-1 symbol totals | `B/extractor/prompt.py:295` `detected_symbols_summary` | whole PDF | integer counts, no positions | Paid(vision_pass1) | extract | `GeneralFactsPanel.jsx`, `RoomSheet.jsx` | – | LIVE |

## 6. Schedules and tables

| Capability | Entry | Input | Output | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Room table (eksplikacija) from the text layer: `find_tables` + header-role map, continuation pages, totals | `B/extractor/pdfplumber_eksplikacija.py:712`, `:417` `_detect_header` | PDF | rooms with `eksplikacija_row_bbox`, `schedule_tables{durys:[], langai:[]}` (always empty here) | €0 | inside extract | row crop via evidence; `EksplikacijaSourcePopover` | `T/test_eksplikacija_table_tolerance.py`, `test_plotas_source.py` | PAID-PIPE (Step 1.5) |
| Eksplikacija + door/window schedule by Vision (pdfplumber miss only) | `B/extractor/eksplikacija_reader.py:302` | PDF 300 dpi | rooms + `schedule_tables{durys, langai}` (no geometry) | Paid(vision_pass1) | – | – | `T/test_dead_runs_metered.py` | PAID-PIPE |
| Is this table ours? / row contradiction / merge | `B/extractor/eksplikacija_guard.py:89,:78`; `vision_call.py:6153`, `:1148` | rooms + rows | merge meta, `eksplikacija_row_idx/_bbox` | €0 | – | – | `T/test_eksplikacija_guard.py` | PAID-PIPE |
| Door schedule (durų žiniaraštis): heading + code words, frame type, sizes, counts, notes, products | `B/extractor/door_schedule.py:185` `scan_door_schedule`, `:111` `_parse_table` | PDF words (first 3 heading pages) | `_duru_ziniarastis{status, pages, lentele{page, eilutes[{kodas, plotis_mm, aukstis_mm, tipas, kiekis, tekstas}]}, …, sakinys}`; **no row bboxes** | €0 | Step 2.43 + free-reread / detect-run "kiekiai" | `recomputeContext.js`, `roomSheetApi.js`, `freeReread.js` | 3 test files | LIVE |
| Schedule anchoring of opening sizes (±50 mm) | `vision_call.py:6490` (Step 2.45) | Vision `schedule_tables` | `_schedule_anchored`, `_schedule_id` | €0 | – | – | – | PAID-PIPE |
| Tile specification | `B/extractor/plyteliu_specifikacija.py:144` | PDF text | `_plyteliu_specs[…]` (no positions) | €0 | – | `WorkspacePanel.jsx` | `T/test_plyteliu_specifikacija.py` | PAID-PIPE (Step 2.89) |
| Finish plan per-room finishes | `B/extractor/apdailos_reader.py:298`, `:446`, `:172` | rendered finish page | `sienu_apdailos_breakdown`, `_apdailos_page` | Paid(apdailos) | – | room sheet "apdaila" | `T/test_apdailos_reader.py` + 2 | PAID-PIPE |
| Vision door/window schedule extractor | `B/extractor/vision/schedule_extractor.py:89` (`R/prompts/schedule.txt`) | page image | `{durys, langai}` | Paid | – | – | `T/test_schedule_extractor.py` | DEAD |
| Material specs for one room (on click) | `B/extractor/material_specs.py:96`; route `B/main.py:1571` | PDF + room | specs | Paid(vision_pass1) | `POST …/material-specs` | `RoomCard.jsx:499` | `T/test_model_stop.py` | LIVE |
| Wall elevations (zone mm boundaries) | `B/extractor/wall_elevation.py:304` | elevation pages | `_wall_elevations` | Paid | – | `WallElevationsPanel.jsx` | `T/test_wall_elevation.py` | PAID-PIPE, opt-in |

## 7. Floor covering, heights

| Capability | Entry | Input | Output | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Floor covering from the floor plan (label, or colour hatch + same-colour legend line) | `B/extractor/floor_coverings.py:217`, `:393`, `:241` | PDF, floor page, room polygons | `rooms{nr:{danga, irodymas, tekstas, plotas_m2, rect_pct, page}}`, `legenda[{tekstas, klase, spalva}]`, `dvi_dangos`. **`legenda` is thrown away** by `geometry_lane.py:293` | €0 | detect-run / free-reread ("grindys") | `mergeReextract.js`, `roomOutline.js`, room sheet | `T/test_floor_coverings.py` | LIVE |
| Height markers on sections | `B/extractor/height_markers.py:70`, `:113` | page text | candidates | €0 | – | – | `T/test_height_markers.py` | PAID-PIPE |
| Positioned ceiling markers → rooms | `height_markers.py:856`, `:563`, `:726` | PDF + rooms | `lubu_aukstis_m`, `_height_marker_evidence`, … | €0 | – | room sheet "aukstis" | 3 test files | PAID-PIPE |
| Plan height statements | `plan_area_annotations.py:1222`, `:1303` | text | `_meta.plan_height_statement` | €0 | – | – | `T/test_plan_height_statements.py` | PAID-PIPE |
| Height plausibility gate | `universal_rules.apply_height_plausibility_gate` (`vision_call.py:6843`) | rooms | corrections | €0 | – | – | `T/test_height_gate.py` | PAID-PIPE |
| Height fusion + Vision height extractor | `B/extractor/height_fusion.py:110`, `vision/height_extractor.py` | – | – | Paid | – | – | `T/test_height_fusion.py` | BENCH |

## 8. Revisions, cross-sheet callouts, evidence crops

| Capability | Entry | Input | Output | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|---|---|
| Revision alignment (new sheet → old by walls, else page edges) | `B/extractor/revision_alignment.py:59` `match_revision` | old + new PDF | per new page `{old page, k, dx, dy, scores, method}` | €0 | `B/api/pdf_revisions.py:143` POST, `:181` GET, `:187` DELETE, `:280` render, `:292` overlay | `pdfRevisions.js` → `RevisionCompareControl`, `RevisionOverlayLayer` | `T/test_revision_alignment.py`, `test_pdf_revisions_api.py` | LIVE |
| Sheet callouts + title-block codes | `B/api/sheet_refs.py:112`, `:175`, `:267`; `B/api/sheet_links.py:36,:106`; route `:136` | PDF text + sheet names | callout spans with boxes, target page | €0 | `GET …/pages/{p}/callouts` | `sheetLinksApi.js` → `CalloutLayer.jsx` | `T/test_sheet_refs.py`, `test_sheet_links_api.py` | LIVE |
| Evidence crop PNG for `(page, rect)` or a room | `B/api/evidence.py:415` | page+rect / room | PNG (disk cache) | €0 | `GET …/evidence` | `EvidenceCrop.jsx`, `GeneralFactsPanel`, `RoomPlanPane` | 3 test files | LIVE |

## 9. Vision passes, readers, voting (paid; inside `extract_interior`, `vision_call.py:5904`)

| Reader | Entry | Role | Voting | Status |
|---|---|---|---|---|
| Pass-1 whole-PDF extraction (native PDF) | `_run_pass1_once:5359`, `_run_pass1_voted:5618`; prompt `prompt.py:344` | vision_pass1 | N rounds, `extraction_voter.vote_extraction`; `ENABLE_EXTRACTION_VOTING` on, `VOTING_N` 3, parallel; `SAMATU_VOTING_MODELS` experiment | LIVE |
| Adjacency (partition walls) | `vision/adjacency_extractor.py` (`R/prompts/room_adjacency.txt`); `vision_call.py:5810` | vision_pass1 | per round | LIVE |
| Eksplikacija fallback | `eksplikacija_reader.py:302` | vision_pass1 | none | LIVE (pdfplumber miss only) |
| Pass-2 zoom per room | `_vision_zoom_room:557` (`prompt.py:870`); agentic `agentic_crop.py:191` (off) | vision_pass2 | none | LIVE |
| Apdailos (finish plan) | `apdailos_reader.py:298` | apdailos | none | LIVE |
| Doors count per plan sheet | `doors_reader.py:251` | doors | none | LIVE |
| Door type (frameless) from text tags | `door_type_reader.py:162` / `_voted:274` | doors | mode | LIVE |
| Sanitary fixtures | `sanitary_fixture_reader.py:181` / `_voted:291` | sanitary | mode/median | LIVE |
| Niche locator (LED niches) | `vision/niche_locator.py`; `vision_call.py:7265` | vision_pass1 | none | LIVE |
| Perimeter validator | `vision/perimeter_validator.py` (`vision_call.py:7652`) | €0 check | – | LIVE |
| Verify pass | `verify_pass.py:127` | vision_pass2 | – | flag off |
| Legacy KŽ `/extract`, facade/roof/earthworks/concrete | `B/main.py:2654`, `:4738-4884` | vision_pass1 / extraction | – | LIVE (other types) |
| Chat | `B/main.py:7922` (prompt `:7703`) | chat | – | LIVE |
| Bench/dead vision modules | bbox_locator, built_in_detector, dimension_extractor, room_graph_extractor, per_room_zoom_pipeline, height_extractor, elevation_extractor, schedule_extractor, page_dispatch, `vision_call_v2`, majority_voter | – | – | BENCH / DEAD |

Prompt files: `R/prompts/*.txt` (symbol_detection, niche_locator, room_adjacency, room_bbox, room_graph, schedule, dimension_list, built_in_furniture, ceiling_height, elevation_zones, elevation_tile_focus); only niche_locator and room_adjacency are on the production path. Inline prompts in `prompt.py:344/:870`, `eksplikacija_reader.py:33`, `apdailos_reader.py:70`, `doors_reader.py:48`, `door_type_reader.py:69`, `sanitary_fixture_reader.py:59`, `material_specs.py:33`, `wall_elevation.py:161`, `legend_injection.py:24` (dead), `page_classifier.py:182` (bench), `verify_pass.py:29`. `B/extractor/prompts/*.py` (`PROMPTS_BY_PAGE_TYPE`) has no production importer.

## 10. Check sheet: room facts, questions

| Capability | Entry | Output | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|---|
| Room facts | `B/extractor/room_facts.py:1872` `build_room_facts`; `FACT_KEYS:60` = plotas, perimetras, aukstis, apdaila, angos, grindys (+ `pertvaros:1813`) | `{room, facts[{key, value, unit, status, source{kind, page, rect_pct}, sentence, crop_url, editable, yours}], quantities, excluded, ledger_available}` | €0 | `GET …/rooms/{nr}/facts` (`B/api/room_facts.py:28`) | `roomSheetApi.js:40` → `RoomSheet.jsx` | 8 test files | LIVE |
| Project questions (Patikra) | `B/extractor/project_questions.py:377`; `ORDER:28` | `{questions[{id, kind, answer, title, why, unit, items}]}` | €0 | `GET …/questions` (`B/api/project_questions.py:25`) | `questionsApi.js` → `PatikraQuestions.jsx` | `T/test_project_questions*.py` | LIVE |

## 11. Learning loop

| Capability | Entry | Cost | Route | Frontend | Tests | Status |
|---|---|---|---|---|---|---|
| Corrections log (deduplicated 60 s) | `B/main.py:1723` POST, `:1739` GET, `:1751` CSV; `B/api/learning_journal.py` | €0 | `/api/projects/{id}/corrections[.csv]` | `learningEvents.js`, `projectStore.js`, `LearningJournal.jsx` | 3 test files | LIVE |
| Admin corrections summary | `B/main.py:1780` | €0 | `/api/admin/corrections-summary` | – | – | BE-ONLY |
| CV decision → crop + correction row | `B/api/cv_tools.py:363` | €0 | record-decision | `SymbolReviewPanel` | §5 | LIVE |
| Ground-truth corpus from the DB | `R/scripts/build_ground_truth.py` (`--with-corrections`) | €0 | – | – | `T/test_build_ground_truth.py` | BENCH |
| Prompt-suggestion / calibration reports | `B/extractor/learn_from_corrections.py`, `calibration_learner.py` | €0 | – | – | `T/test_calibration_learner.py` | DEAD (CLI) |
| Per-project quantity calibration | `B/api/calibrate.py:217/278/294` | €0 | `…/calibrate` | `Annotator.jsx` | `T/test_calibrate_api.py` | DEV |

## 12. Orchestration

- **Free re-read:** `B/api/free_reread.py:95` `read_drawing` (GET `:81`, POST `:147`): `apply_geometry` (`geometry_lane.py:399`) → `scan_door_schedule` → `scan_vector_symbols`. Returns `{status, lane, patalpos, _meta, _duru_ziniarastis, _vector_symbols, santrauka}`; saves nothing; the browser merges through `F/lib/freeReread.js` and `/recompute-interior`. GET returns `needed` when `_meta.geometrija.versija` < `LANE_VERSION = 12` (`geometry_lane.py:158`). LIVE.
- **Detect-run:** `B/api/detect_run.py` (POST `:560`, GET `:606`): same reading as a background job. `STAGES:54` = `mastelis, tekstas, planas, konturai, angos, sienos, grindys, kiekiai`; `FEATURES:75` = `plotai, konturai, sienos, angos, grindys`; snapshot `{job, stage, stages[], per_page, pages, features, skaitoma_lt, result_ready, failed, result}`. Frontend `detectRunApi.js` → `useDetectRun` → `DetectRunButton` / `DetectRunProgress`. LIVE.
- **Paid run:** `/extract-interior(-stream)` → `extract_interior` SSE events `rendering_pdf … post_processing`; jobs polled at `/api/extraction-jobs/{id}` (`B/main.py:6907`).

---

## Gaps

### For a legend-marking feature
1. **No legend-block detector.** Nothing finds a "SUTARTINIAI ŽENKLAI / ŽYMĖJIMAI" region and returns its bbox. `vector_symbols.count_legend_symbols` only finds rows for a caller-supplied regex (only diffusers wired), scans at most 4 pages, returns no row/glyph bbox, and instances are points only.
2. **Black-only symbols are never counted** by the vector counter (black paths are treated as walls). The fallback is the raster chamfer `find-symbol`, one page per call; no step uses a legend glyph box as the template, and no server-side all-pages batch exists.
3. **`floor_coverings` already reads colour legend lines** (`legenda[{tekstas, klase, spalva}]`) but `geometry_lane.py:293` throws them away.
4. **A Vision legend reader and a legend store exist but are not connected** (`legend_injection.extract_legend`, `api/legends.py`, bench `legend_extractor.py` with `glyph_bbox_pct`).
5. **No live page type "legend"** in Pass-1's `tipas` enum (`prompt.py:64`), although `F/lib/sheetRail.js:19` lists it.
6. **Nothing reads the training crops** (`R/data/symbol_training`).
7. **Three coordinate frames to reconcile:** pdfplumber page frame (`vector_symbols`, `door_schedule`); PDFium display frame (/Rotate applied: geometry, figures, callouts); unrotated mediabox points (`cv_tools` `box_pt`, the viewer's measurement space).

### For a schedule-reading feature
1. **Only the eksplikacija has a real table parser** with row bbox. The door schedule parser returns no row/cell bboxes; there is no deterministic window schedule reader; pdfplumber's `schedule_tables` is always empty; Vision `schedule_tables` carry no geometry.
2. `vision/schedule_extractor` (`R/prompts/schedule.txt`) exists but is unwired.
3. No deterministic finish-schedule (apdailos lentelė) table reader; `apdailos_reader` is Vision; `plyteliu_specifikacija` is regex text without positions.
4. **The free re-read / detect-run do not re-read tables, figures or heights** (eksplikacija, `scan_text_layer`, tile specs, height markers run only in the paid pass).
5. No generic route that maps a table region to cells, and no viewer highlight for schedule rows (only the eksplikacija row crop).

### For sheet-zone mapping and viewer clicking
- **Zones are fixed fractions only**: title block (0.40,0.70)-(1,1) in `page_classifier.py:49` and `sheet_refs.py:41`; `room_locator` treats anything below 0.88 of the height as title block. Nothing detects the plan viewport, legend, notes or title-block boxes, or two viewports on one sheet. The `page_geometry` wall solid's extent is the only implicit "plan area".
- **The main viewer's room click is the raster OpenCV fill** (`/api/click-to-fill`, `TakeoffViewer.jsx:1199`); the vector `outline_at` ("Parodyti patalpą") is wired only on RoomSheet and Patikra. `_vieta` badge positions are never sent to the frontend for hit-testing.
- **Unused routes/components that could be reused:** `/pdf-lines` (no caller), `CountTool` (match-template) and `MagicWandTool` (magic-wand) not mounted, Annotator-only routes (detect-symbols, room-graph, calibrate) DEV-only.

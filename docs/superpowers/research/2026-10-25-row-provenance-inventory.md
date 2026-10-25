# Row provenance inventory — where every sąmata quantity comes from (v4 Phase 3b, step 1)

Branch `v4/kill-model-rows` from `togal-v2` @ bc6005fe (room identity merged, LANE_VERSION 17). Report only: no
code changed in this commit. Line numbers are of that commit. Plan: `docs/superpowers/plans/2026-10-24-deterministic-hybrid-plan.md`
§1 R1–R3, R7; §6.

## Classes

| class | meaning | legal after 3b? |
|---|---|---|
| `drawing` | the text layer (room table, plan labels, legends, notes, height markers, door schedule), the geometry lane (vector outlines, perimeters summed from dimension strings, drawn openings, floor coverings read off the floor plan), vector symbol counts, or the person's own entry | yes |
| `derived` | a formula over drawing facts with a named convention (a waste factor, a per-m² material norm, a „one row per project" lump, a scope choice he can change) | yes — conventions are the rules worker's profile (R5) |
| `model` | a Vision reading of pixels or a Vision-estimated number (Pass-1 perimeters, heights, ceiling types, symbol counts, niche lengths; zoom re-reads) | **no** (R2/R3) — except readers of tables/text from images that Phase 3c reduces to text (apdailos, doors, door types, sanitary fixtures, eksplikacija image reader): marked `model-3c` and left for 3c, as the brief says |
| `default` | a constant standing in for a fact about THIS building that the drawing should tell (a height, a length, a count, a ceiling type, a frame type, a share) — by room type or project | **no** (R7): read, or blank with a reason |

The line between `derived` and `default`: a convention says how a contractor measures or bills what the drawing
shows (net area, +10 % skirting waste, 0,3 m PVC bead per m of corner); a default invents what the drawing does
not show (that the flat is 2,82 m high, that the ducts are 25 m, that 30 % of the walls are masonry).

## A. Room inputs every per-room row rests on

| input | where it is set | sources seen in production / corpus | class |
|---|---|---|---|
| area `plotas_m2` | `room_identity.identity_from_table` / `join_rows` (vision_call Step 2.4, l. 6195ff); `plan_area_annotations` Step 2.44 (l. 6455); geometry lane outline | text-layer room table, plan m² labels, outline; else Pass-1's copy of the table | `drawing`; Pass-1 copy = `model-3c` (eksplikacija image reader) |
| perimeter `perimetras_m` | geometry lane Step 2.44b–d (l. 6513–6585) writes `perimetras_saltinis` ∈ {`matmenu_eilutes`, `plano_matmenys`, `sienu_konturas`, …} or an outline estimate (`_perimetras_ivertis_m`, `konturo_ivertis` / `atviros_erdves_ivertis`); otherwise the Pass-1 figure stays (no source → `_walls_perimetras_saltinis = "vision"`), or the zoom re-read (`zoom`, `_apply_zoom_refinements` l. 629) | objektas_i prod: 17/17 `vision`; corpus frozen extracts: a, b, c, d, h all rooms no source (Pass-1), g 8/9 lane | lane/strings/user `drawing`; Pass-1 and zoom **`model`** |
| perimeter when absent | `universal_rules.calc_room_quantities` l. 2581–2583 `perim = 4.18 × √A` (`kvadrato_ivertis`) | rooms with no perimeter at all | **`default`** |
| perimeter floor on the wall path | `universal_rules.calc_room_quantities` l. 2590–2621 (`_perimeter_floor_enabled`, flag `perimeter_floor_synthetic` default ON): `max(perim, 4.0·√A)` / `1.3:1` coefficient on synthetic areas | rooms whose Pass-1 perimeter is below the square | **`default`** |
| perimeter estimator | `objektas_d_estimator.estimate_objektas_d` (whole-project estimator, tests only) | — | **`default`** |
| perimeter check | `vision_call.perimeter_warning` l. 433 + `_perimeter_validation` Step 4.066 (l. 7740–7765, isoperimetric bound on Pass-1 figures) | 17/17 pass on objektas_i A — too loose to catch a 2× error | check of a `model` figure |
| height `lubu_aukstis_m` | Step 2.4.5 marker scan (l. 6691, text), Step 2.4.6 positioned markers (l. 6781, text → `ceiling_plan_marker`), plan statement (`plano_uzrasas`, text), his entry (`user_override`); Pass-1 per-room name map / by-nr map / warnings salvage (`per_room`, l. 6847–6930), Pass-1 room label `section_pjuvis` / `ceiling_plan_annotation`, zoom (`zoom`); else `section_average` = `parsed.lubu_aukstis_m or 2.82` (l. 6913, `_apply_per_room_heights` l. 2031) | objektas_i prod: 13 × `section_average` 2,82 with no project height (= the constant), 4 bathrooms `per_room` 2,2 (B: 2,0) from the Pass-1 name map while every round voted 2,82; corpus: b, c, g, h `section_average` 2,82 with no project height; a Pass-1 `per_room`; d 2 × `plano_uzrasas` + 2 × `per_room` | text/user `drawing`; Pass-1 **`model`**; `section_average` with no read project height **`default`** |
| openings `elementai` (doors, windows, sizes) | Pass-1 (`elementai`), doors reader Step 2.86, door-type reader Step 2.865, door schedule Step 2.43 (text), geometry lane drawn openings (`drawn_openings`) | objektas_i: Pass-1; lane classified 0 before Phase 1, now reads | lane/schedule `drawing`; Pass-1 `model`; readers `model-3c` |
| ceiling type `lubu_tipas` | Pass-1 (`prompt.py` l. 158) or `ROOM_TYPE_RULES[paskirtis].ceiling_type` (universal_rules l. 345–405, default `gkp`), read at l. 2982 | objektas_i: 17 × `gkp` from Pass-1, no ceiling-plan evidence per room | **`model`** / **`default`** |
| floor covering | `grindu_danga` from the floor plan (geometry lane, `floor_coverings`) else `ROOM_TYPE_RULES[...].floor` | g, h read; a–d by room type | read `drawing`; by room type `default` |
| wall-tile band | `resolve_wall_tile_read` (universal_rules l. 2257): wall elevations (`wall_elevation`, Vision), apdailos reader, `plyteliu_specifikacija` (text) … else `tile_walls_to_m` by room type (2,0 m wet / 0,6 m kitchen) with an assumption sentence | | text `drawing`; elevation/apdailos `model-3c`; by room type **`default`** |
| LED niche length `nisu_metrai` | `_calc_nisu_metrai_m` (vision_call l. 1463) over `elementai` of `nisa_led` — Pass-1 / niche locator (`vision/niche_locator.py`, Step 2.87, l. 7361) — plus `niche_inference.infer_missing_niches` (Step 2.88, l. 7452: length by room type, billed once accepted) | objektas_i: 17,6 m = Pass-1/locator; legend says „LED juosta; šviesos šaltinis – 24,00 m" | **`model`** / **`default`** |
| frame type of interior doors | `universal_rules.settle_frameless_default` (l. 1838): `jusu` / `ziniarastis` / `ziniarastis_misrus` / `pastaba` / `anotacija` / `gaminiai` (text) / `brezinys` (only the plan's hidden-door symbols, Pass-1 glyphs) / `nera_pozymiu` | objektas_i: `brezinys` from one plan symbol (`plan_tagged` 1, reader 0) → every interior door frameless | text `drawing`; `brezinys` **`model`** + extension to all doors **`default`** |
| fixture counts (toilets, basins, showers, sinks) | `plumbing_reading` (l. 1580, sanitary reader Step 2.866 `model-3c`) else room type (`toilet_count` l. 1704, `shower_count` l. 1686, `paskirtis_default`) | | reader `model-3c`; room type **`default`** |
| electrical / diffuser counts | `detected_symbols_summary` / `v9_meta.symbols_detected` (Pass-1 symbol counts, `vision/symbol_detector`); diffusers also `vector_symbols` (paths, text legend) | objektas_i: diffusers 11 Pass-1, 5 vector | vector **`drawing`**; Pass-1 **`model`** |

## B. Row families (`vision_call._build_pozicijos_from_rooms`, l. 3444–5321, plus the consolidations)

„Rows" = the label as the builder emits it (after `_consolidate_paint_pozicijos` l. 2890 and
`_consolidate_led_niche_pozicijos` l. 3193). Material rows lifted into „Medžiagos" (`_extract_medziagos_section`
l. 2789) follow their work row and are not listed separately unless their quantity has its own source.

| # | row family (label) | quantity = (function : line) | rests on | class before | action in 3b |
|---|---|---|---|---|---|
| 1 | Sienų glaistymas/dažymas (iki / virš 3 m), Sienų šlifavimas Q4 | Σ `walls_paintable_m2` (calc l. 2636 `perim_walls × H` − openings − tiles) via `_consolidate_paint_pozicijos` l. 2925; legend anchor `_walls_base_meta` l. 2395 | perimeter, height, openings, tile band | `model` + `default` (perimeter, height); legend anchor `drawing` | blank the row while any room behind it has a model/default perimeter or height (reason names the rooms); legend anchor stays |
| 2 | Sienų lyginimas Knauf Rotband | walls × `scope.rotband_share` (l. 3735; 30 % `prielaida` until he chooses) | row 1 + share | `default` (share) | blank with reason until he chooses the share („Ką skaičiuoti"); his share → `derived` |
| 3 | Molio tinkas | Σ `molio_tinko_m2` (apdailos reader) l. 3785 | apdailos | `model-3c` | unchanged (3c) |
| 4 | Tapetai (flag `SAMATU_WALLPAPER_ROLLS`, off) | `wallpaper_flag.wallpaper_rows` | apdailos | `model-3c` | unchanged |
| 5 | Lubų glaistymas/dažymas (iki / virš 3 m) | eksplikacija total anchor `_ceiling_base_meta` l. 2586 else Σ `ceiling_paintable_m2` (= area) | area | `drawing` | unchanged; the iki/virš split rests on heights → the virš-3 m part only from a read height |
| 6 | Lubų glaistymas/dažymas (virš 3 m) — papildomas darbas | l. 3842 Σ ceilings of rooms with H ≥ 3 m | height | height class | follows the height rule |
| 7 | Dažymo kampų montavimas | Σ `kampu_metrai` (calc l. 3254–3290: inner × H + reveals + pusiniai + perim) l. 3860 | perimeter, height, openings | `model`/`default` + convention | **rules worker** (620 m on objektas_i is the corner convention); in 3b blanked with row 1's rule because it rests on perimeter × height |
| 8 | Angokraščių glaistymas-dažymas / apdirbimas GKP | Σ `angokrasciu_gkp_m` (calc l. 3322–3380, W + 2H per opening in scope) l. 3920 | openings | Pass-1 openings `model`; lane/schedule `drawing` | unchanged in 3b (openings are Pass-1 / readers; the lane's drawn openings replace them in the Phase 1 lane) — listed as open |
| 9 | Durų angų paruošimas beapvadinėms durims | Σ `pasleptu_duru_staktu_m` (calc l. 3366–3371) + text reconciliation l. 3934 | frame type source | `brezinys`/`anotacija`/`ziniarastis_neaiskus` → `model`/`default`; `jusu`/`ziniarastis`/`pastaba` → `drawing` | blank with the door question's sentence unless the frame type comes from his answer, the door schedule or a governing note |
| 10 | Grindjuosčių sumontavimas / dažymas | Σ `grindjuosciu_m` (calc l. 3387–3405, perimeter − doors + 10 %) or the floor-plan legend anchor l. 4008 | perimeter, floor covering | perimeter class | blank with row 1's perimeter rule; legend anchor stays |
| 11 | Lubų karnizo sumontavimas / dažymas | Σ `lubu_karnizo_m` (`_calc_lubu_karnizas_m` l. 1442, perim × 1,05, only with drawing evidence) | perimeter + legend evidence | perimeter class | perimeter rule |
| 12 | Nišų formavimas GKP / LED nišų glaistymas/dažymas | Σ `nisu_metrai` l. 4093 | niche lengths | **`model`/`default`** (17,6 m on objektas_i; legend 24 m) | the LED length the drawing's legend states („LED juosta … 24,00 m"), else blank with reason; niche locator + niche inference deleted |
| 13 | LED nišos — suveskite ilgį | `niche_inference.led_estimate_waiting_row` l. 4128 | estimate waiting | blank row | folded into row 12's blank |
| 14 | GKP lubų montavimas (standartinis / virš 3 m) | Σ `gkp_lubu_*` (calc l. 3020–3040 from `lubu_tipas`) l. 4136 | ceiling type, height | **`model`/`default`** | only rooms whose ceiling the drawing marks (a ceiling-plan altitude printed in the room, `ceiling_plan_marker`) or he set; otherwise blank with reason (the GKP note on the sheet is quoted, the rooms' area is offered) |
| 15 | GKP lapai luboms, CD / UW profiliai, siūlės, savisriegiai | ×norm of row 14 (l. 4160–4190, `build_gkp_pozicijos` l. 1974) | row 14 | `derived` over row 14 | blank with row 14 |
| 16 | Reviziniai dureliai | 1 per wet room l. 4193 | room names | `derived` (convention: one hatch per wet room) | unchanged — profile convention (rules worker) |
| 17 | Plytelių klijavimas / plytelės / fugavimas (6 locations) | Σ `plyteles_sienos_m2` / `plyteles_grindys_m2` (calc via `resolve_wall_tile_read`) l. 4245–4304 | perimeter, tile band, floor covering | wall tiles: perimeter + tile band (`default` by room type); floor tiles: area + covering (`default` by room type unless read) | wall tiles: perimeter rule + tile band read; floor tiles: unchanged in 3b (covering by room type is the scope profile's — rules worker), listed |
| 18 | Didžiaformačių plytelių klijavimas / lygio kontrolė | tile total × `didzformat_share` 0,30 l. 4316 | share | **`default`** | blank with reason unless he set the share |
| 19 | Plytelių 45° pjovimas (+ EPOKSIDU) | max(wet perim × 0,4, 2 × n × tile h) l. 4355 | perimeter, tile band | perimeter class | perimeter rule |
| 20 | Silikonavimas (2 rows) | tiled perim × 1,31 / 0,99 l. 4395 | perimeter | perimeter class | perimeter rule |
| 21 | Skylių gręžimas plytelėse | fixtures × holes (`detected_symbols_summary`) l. 4420; fallback openings × 4 l. 4446 | fixture counts | `model` / `default` (fallback) | from the plumbing reading only (3c), the openings × 4 fallback blanked |
| 22 | Nuolydžio formavimas dušo zonoje, Linijinis latakas, Dušo maišytuvas (pair) | `shower_count` l. 1686 | plumbing reading or room type | `model-3c` / **`default`** | room-type showers → blank with reason |
| 23 | Lentynėlių iš plytelių įrengimas | showers × 2 (`lentyneliu_per_vonia`) l. 4473 | showers + convention | `default` (count per shower) | blank unless he set the number per shower and the showers are read |
| 24 | Plytelių grindjuosčių supjovimas ir suklijavimas | perimeter − 0,85/door + 10 % l. 4510–4570, or floor legend anchor | perimeter | perimeter class | perimeter rule; anchor stays |
| 25 | Pertvaros sutvirtinimas WC mechanizmams (GKP dėžutė) | `toilet_count` l. 4588 | plumbing or room type | `model-3c` / **`default`** | room type → blank with reason |
| 26 | Hidroizoliacijos įrengimas (vnt) | count of wet rooms l. 4600 | room names | `derived` | unchanged (the m² detail is not billed) |
| 27 | Grindų išlyginamasis sluoksnis | Σ `isliginamasis_m2` | area, covering | `derived` (scope) | unchanged — rules worker's scope profile |
| 28 | Parketo / laminato klojimas + pamušalas | Σ `pvc_grindys_m2` or floor legend anchor | area, covering | covering by room type `default`, read `drawing` | unchanged in 3b (scope profile), listed |
| 29 | Slenksniai | rooms − 1 l. 4716 | room count | `default` (count of thresholds) | blank with reason |
| 30 | WC rėmas, Klozetas, Praustuvė (+ maišytuvas pair), Bidė | `toilet_count` / basins l. 4747–4830 | plumbing or room type | `model-3c` / **`default`** | room type → blank |
| 31 | Gyvatuko montavimas | n vonia + san (`paskirtis_default`) l. 4842 | room type | **`default`** | blank with reason |
| 32 | Plautuvė, Virtuvės maišytuvas | max(n kitchens, symbols) l. 4776 | room type / Pass-1 symbols | `default` / `model` | plumbing reading only, else blank |
| 33 | Vonios maišytuvas (pair), Vonia / Trapai (flag, off) | tub-only reader count | `model-3c` | unchanged |
| 34 | Skalbimo mašinos sifonas / montavimas | n laundry, or 1 when a bathroom exists (`paskirtis_default`) l. 4881 | room type | **`default`** | blank with reason |
| 35 | Santechnikos taškų koregavimas (1 kompl) | constant `baseline` l. 4895 | one per project | `derived` (lump) | unchanged |
| 36 | Rozetės / jungiklio pajungimas, Lubinių šviestuvų montavimas, Skylių šviestuvams gręžimas, Šviestuvų apdirbimas, Pakabinamų šviestuvų montavimas | Pass-1 `detected_symbols_summary` l. 4932–4975, l. 5120 | Pass-1 symbol counts | **`model`** | blank with reason (count tool / vector counter is the source) |
| 37 | LED juostos pajungimas | Pass-1 `led_juostos` l. 4970 | Pass-1 | **`model`** | the legend's LED length (row 12's reading), else blank |
| 38 | Difūzorių montavimas / apdirbimas | vector count (`_vector_symbols`, l. 4996) else Pass-1 count anchored by the legend scan l. 4984 | vector / Pass-1 | vector `drawing`; Pass-1 **`model`** | vector count only; else the existing blank row |
| 39 | Termoreguliatorių pajungimas — suveskite kiekį | blank | — | blank row | unchanged |
| 40 | Ortakių D100 / D125 / D160 montavimas | Pass-1 `ortakiai_*_m` (prompt l. 318) else **diffusers × 5,0 m as D125** l. 5074 | Pass-1 / constant | **`model`/`default`** (25 m on objektas_i) | blank with reason („suveskite ilgį"), emitted only where the drawing shows ventilation (diffusers counted) |
| 41 | Ortakių izoliacija / tvirtinimas | ducts × 0,7 / ducts ÷ 1,5 l. 5107 | row 40 | `default` over `default` | blank with row 40 |
| 42 | GKP dėžučių / nišų pertvarose / pertvarų storinimas / GK klijavimas / ortakių dėžutė / TRACK — suveskite | blank checklist rows l. 5160–5212 | — | blank | unchanged |
| 43 | Pastolių nuoma (d.d.) | Σ above-3 m paint ÷ 50 l. 5220 | height | height class | height rule |
| 44 | Šiukšlių išvežimas (m³) | floor area × 0,075 l. 5246 (factor fitted to one sąmata) | constant | **`default`** | blank with reason |
| 45 | Statybvietės sutvarkymas (1 kompl) | constant | one per project | `derived` (lump) | unchanged |
| 46 | Apsauginės dangos / juostos (m²) | floor area l. 5256 | area + „protect every floor" | `default` (how much is protected) | blank with reason, the floor area offered |
| 47 | Medžiagos (glaistas, gruntas, dažai, PVC kampuotės, GKP juostelės, profiliai, plytelių klijai…) | norms over their work rows | work row | `derived` | follow their work row: a blanked work row takes its materials out |

### Counts (row families above, 47)

| class (before) | families |
|---|---|
| `drawing` | 2 (5 ceilings; 38 diffusers when vector) |
| `derived` | 8 (15 when row 14 is legal, 16, 26, 27, 35, 45, 47, 3-as-reader-copy) |
| `model-3c` (reader of a table/text image, left for 3c) | 4 (3, 4, 33, 8's reader share) |
| `model` (pixel reading / model estimate) | 9 (1, 7, 12, 14, 36, 37, 38-Pass-1, 40, 32-symbols) |
| `default` | 18 (1/7/10/11/19/20/24 through the perimeter or height, 2, 9, 13, 17-wall-band, 18, 21-fallback, 22, 23, 25, 29, 30, 31, 34, 41, 43, 44, 46) |
| blank already | 3 (13, 39, 42) |

A family can sit in two classes (a model perimeter AND a default height); the table's last column is what 3b does.

## C. Model-driven extras outside the row builder (deleted in 3b, plan §6)

`vision/bbox_locator.py`, `room_graph_extractor.py`, `adjacency_extractor.py`, `dimension_extractor.py`,
`niche_locator.py`, `elevation_extractor.py`, `symbol_detector.py`, `built_in_detector.py`; `niche_inference.py`,
`objektas_d_estimator.py`, `agentic_crop.py`, `verify_pass.py`, `vision_call_v2.py`, `calibration_learner.py`,
`cv_wand.py`, `cv_polygon.py`; `api/vision_fill.py`, `api/vision_readers.py`, `api/symbols.py`;
routes `POST /api/click-to-fill`, `POST /api/projects/{id}/detect-room-polygons`, `vision_call.vision_polygon_at_click`.
Kept: `page_classifier` (text part), the text readers (apdailos, doors, door types, sanitary, eksplikacija,
schedules) — Phase 3c.

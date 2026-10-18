# Pathon v3 — coverage matrix: every reverse-engineered capability, the interior formulas, market readiness (2026-10-18)

> Documentation worker (Opus 5.5) for the "Togal-v2 backend manager". Read-only, €0, no code changed. Snapshot: `togal-v2` @ 8331799 (after the W1-E and W1-C merges).
> **Update (same day).** Every UNPLANNED row below now has a home (track, CONDITIONAL, SKIP or FOUNDER DECISION) in `2026-10-18-pathon-v3-wave5-7-plan.md`, appendix „Row → home"; the statuses here are the pre-plan snapshot.
> **Why.** The founder's rule: everything we reverse-engineered must be in the product or knowingly left out, for an interior-finishing app ready for the market. This file proves which items are covered and flags those that are not planned.

**Sources and the short codes used in the tables**

| Code | Document |
|---|---|
| TP | `docs/superpowers/research/2026-10-16-togal-pipeline-analysis.md` (§0–§11) |
| TE | `docs/superpowers/research/2026-10-18-togal-editor-ui-re.md` (§0–§10) |
| KE | `docs/superpowers/research/2026-10-18-kreo-editor-ui-re.md` (§1–§12) |
| PA | `docs/superpowers/research/2026-10-18-pathon-viewer-ui-audit.md` (§5, §7 lists A–D with rank numbers, §8, Appendix A–I) |
| BI | `docs/superpowers/research/2026-10-18-backend-reading-inventory.md` (Gaps: legend 1–7, schedule 1–5, zones/clicking) |
| TK | `docs/superpowers/research/2026-09-17-tyrimas-togal-kreo.md` (Togal / Kreo sections 1–8, check-sheet comparison) |
| CD | `docs/superpowers/research/2026-05-02-competitor-viewer-ui-deep-dive.md` (§2–§4) |
| design | `docs/superpowers/specs/2026-10-18-pathon-v3-design.md` |
| v2 map / v2 Wn | capability map A–L and merge log of `docs/superpowers/plans/2026-10-16-togal-v2-program.md` |
| W0-A … W4-A | v3 tracks in `2026-10-18-pathon-v3-program.md`, `…-wave1-plan.md`, `…-wave2-4-plan.md` |

**Status vocabulary.** The first status in the cell is the one counted.
- `shipped pre-v2`: in the code before the v2 programme (file cited).
- `shipped v2 (branch)`: a row of the v2 merge log.
- `merged v3 (W…)`: a row of the v3 merge log. Merged so far: W0-B, W1-A, W1-E, W1-C.
- `running (W…)`: a v3 track whose branch or worktree exists and is not merged. Running: W0-A (`v3/smoke-guide`, 3 commits), W1-B (`v3/click-model`) and W1-D (`v3/room-click`), both branched at 1381285 with no commits yet.
- `planned (W…)`: a v3 track with written tasks. Planned: W2-A, W2-B, W3-A, W3-B, W4-A.
- `planned-undecided (wave 5/6)`: named only in the scope of design §7 wave 5 (pro layer) or wave 6 (look). No track exists and the founder has not decided (design §9.5).
- `UNPLANNED`: not in any track. A suffix says why: `(skip)` = the research says not to copy it; `(superseded)` = an older verdict was replaced by the v3 design; `(conditional)` = copy only if a stated condition holds. With no suffix, the row is a gap.

"No verdict in research — manager decides" means none of the docs above gives a copy, adapt or skip verdict for that item.

---

## 1. Competitor capabilities and patterns

### 1A. Intake, sheets, zones

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 1 | TP§1 | Client-side page split and count; drop and name pages before upload (MuPDF WASM) | no verdict in research — manager decides | — | UNPLANNED |
| 2 | TK Kreo§1, KE§10 | Multi-format input (DWG/DXF/DGN, PNG/TIFF/JPG) and a multi-file project manager (grid/list, group by file, rasterize) | no verdict in research — manager decides | — | UNPLANNED |
| 3 | TP§1, TP§9 | Text layer per page with run bboxes, read once | no verdict in research — manager decides | BI §1 `pdf_page_cache.py:146`, `scan_text_layer` | shipped pre-v2 |
| 4 | TP§1, TE§7, KE§8 | Guard for pages that are not drawings, or not the supported drawing type ("Run anyway / Cancel", "Unsupported drawing detected") | no verdict in research — manager decides | BI §1 `preflight.py:377`, `page_filter.py:343` | shipped pre-v2 |
| 5 | TP§1, TK Togal§1, KE§10 | Sheet name, number and discipline from the title block; auto-naming with undo; Kreo's rename-with-AI | copy (v2 map F); naming is by text layer, not AI | v2 W7 | shipped v2 (togal/sheets) |
| 6 | CD§4.6, TE§9 | Navigator grouped by page type or discipline; list/grid cards | adapt (CD§4.6); KE§11 "Pathon is better" than tab cards | v2 W7 groups; W1-A 56 px strip | shipped v2 (togal/sheets) |
| 7 | KE§10, KE§11 | Open pages shown as thumbnail tab cards with a badge | skip (KE§11: Pathon's left rail is better) | — | UNPLANNED (skip) |
| 8 | TE§9, TE§10 | Sheet badge („A-101") + title in the header, "← 1 of 82 →" pager | copy (TE§10) | design §6 frame; no wave-1 task | UNPLANNED |
| 9 | TE§2b | PageUp / PageDown = previous / next sheet | no verdict in research — manager decides | — | UNPLANNED |
| 10 | KE§10, TK Kreo§1, BI zones | Sheet zones: plan viewport(s), legend, tables, title block, notes per sheet | copy (design §1, §4A) | W1-E `sheet_zones.py`, `GET …/pages/{page}/zones`, `_meta.zonos` | merged v3 (W1-E) |
| 11 | KE§10, design §4A | Zones used by the viewer: outline on hover, "show regions", a click in the title block is never a room | copy (design §4A consumers) | W1-E E4 "prepared, not wired"; no UI task | UNPLANNED |
| 12 | BI zones | Room location uses the zones instead of the fixed 0,88 title-block cut | copy (design §4A) | design §4A; no task | UNPLANNED |
| 13 | BI legend 7 | One conversion between the three coordinate frames (pdfplumber page, PDFium display, unrotated mediabox) | adapt (inventory gap) | W1-E `zone_to_mediabox_pt`; W3-B reader frame on /Rotate 270 | merged v3 (W1-E) |
| 14 | TP§1, TP§9, design §8 | Scans and raster-only sheets: text and vector reading go blind | adapt (design §8: the user's box + Vision behind a per-run OK is the product there) | W2-A A1 `be_teksto`, A3 raster batch | planned (W2-A) |
| 15 | TP§1, TP§9 | Server tile pyramid with high-resolution tiles on demand; fixed DPI loses hairlines | keep ours (TP§10: rasterizing before geometry is not worth copying) | EmbedPDF/PDFium viewer, `pdf_vectors.py:262` | shipped pre-v2 |
| 16 | KE§12.0, TE§2 | Map / site-view takeoff (OpenStreetMap snapshot, mapbox) | no verdict in research — manager decides | — | UNPLANNED |

### 1B. Scale

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 17 | TP§2, TK | Scale read from the printed scale string (OCR) and matched to a standard table | keep ours (TP§2: the dimension-string lane measures the scale, which is strictly stronger) | BI §2 `plan_dimensions.py:530`, `detect_scale_hint` | shipped pre-v2 |
| 18 | TP§2, KE§10, TK, TE§8 | Suggested scale the human confirms; "auto-detected, please check" callout; AI suggestion + one Apply | copy (v2 map E) | v2 W6 Masteliai confirm | shipped v2 (togal/scale-flow) |
| 19 | TE§1, TE§9, CD§2.7, PA§5 | Scale chip per sheet (green auto / orange missing / black manual; Kreo's lock badge), confirm in one click, "visiems lapams" | adapt (TE§10, CD§2.7): coloured by evidence | design §4E; W1-D D4 `ScaleChip.jsx` | running (W1-D) |
| 20 | TP§2, TE§2b, KE§3 | Draw-line calibration with "snap to standard scales" and the % difference | copy (TP§10 gap 1) | viewer-drawing-geometry Task 5 | shipped v2 (research/togal-pipeline-analysis) |
| 21 | KE§3, PA§5 | Calibrate in a popover next to the line with the standard scale pre-selected; key K; calibration never auto-exits | copy (KE§11; design §5) | W1-B B4 (K, Esc), W1-D D4 | running (W1-B) |
| 22 | TP§2, TE§9 | "Enter number" scale and "No scale needed" options | no verdict in research — manager decides | — | UNPLANNED |
| 23 | KE§10 | Standard scale chosen from paper-size and scale dropdowns | no verdict in research — manager decides | — | UNPLANNED |
| 24 | TP§2, KE§10 | Scale per page, apply to many pages, every measurement recalculated on a scale change | copy (v2 map E) | v2 W6 one effective scale per sheet | shipped v2 (togal/scale-flow) |
| 25 | TP§2, TE§7 | Run gate: the AI button reads "Set scale" until a scale exists | copy (v2 map E "gate detection on unset scale") | v2 W6 `scaleGateFor` soft chip; the DetectRunButton gate is a v2 follow-up with no v3 task | shipped v2 (togal/scale-flow) |
| 26 | TP§2, TK | Check the scale against a known dimension | keep ours: „Patikrinti mastelį" compares against the written strings | v2 W6 + scale-flow-caps (`ilgis_pt`) | shipped v2 (togal/scale-flow-caps) |
| 27 | TP§2 | Several scales on one sheet (plan 1:100 + details 1:20) | no verdict in research — manager decides. Zones find two `planas` viewports; no scale per viewport | W1-E viewports only | UNPLANNED |

### 1C. Reading run and progress

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 28 | TP§3, TK | One AI run per sheet with All / Custom / Focused feature selection | copy (v2 map A) | v2 W3 detect-run `FEATURES` | shipped v2 (togal/detect-run) |
| 29 | TP§3, TE§7, KE§8 | Run progress: Togal shows a % only; Kreo shows "Searching rooms · 15 s remaining · 44 %" | keep ours (TE§10: stage names are better); restyle as the dark pill (design §4G) | v2 W3 stages; the pill restyle is not in a W1-B task | shipped v2 (togal/detect-run) |
| 30 | TP§3, TP§6 | Predictions stored apart from the user's geometry; a re-run keeps reassigned items | copy (v2 map A "rerun keeps user edits") | v2 W3 narrowed landing | shipped v2 (togal/detect-run) |
| 31 | TP§11 | Keep working on other pages while one sheet is read | no verdict in research — manager decides | v2 W3 background job | shipped v2 (togal/detect-run) |
| 32 | TP§3, TE§7 | Specific failure messages (no walls, no doors, scaling in progress) | adapt: say why nothing changed, at the cursor | `outline_at` statuses (BI §3); W1-B B3 | running (W1-B) |
| 33 | TP§11, TK, KE§8 | What the AI can and cannot read, shown before the first run ("Will Togal wash my car?"; "residential floor plans only") | no verdict in research — manager decides | v2 W4 coach marks are the nearest | UNPLANNED |
| 34 | TP§11, TE§8 | Teaching while the run works (video or explanations during processing) | copy (TP§11 "still worth copying") | —; the paid read takes 25–28 min (v3 programme, paid runs log) | UNPLANNED |

### 1D. Rooms and outlines

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 35 | TP§3 | Raster segmentation network for walls, doors, windows, fixtures | keep ours (TP§10: vector lanes) | `vector_rooms.py:405`, `pdf_vectors.py:262` | shipped pre-v2 |
| 36 | TP§3, TP§10 | Rooms closed across door and window gaps | keep ours (TP§10 "already matched") | `vector_rooms.trace_vector_rooms` | shipped pre-v2 |
| 37 | TP§3, TP§6 | Open plans: splitting touching rooms (watershed / Hough) | keep ours (TP§10: split-space) | `split_space`, `propose_split` (BI §3) | shipped pre-v2 |
| 38 | TP§3, KE§10, TK | Room names joined from the text layer; Kreo falls back to "Undefined" | no verdict in research — manager decides | `room_locator.py:113` | shipped pre-v2 |
| 39 | TP§3, TP§6, KE§3, KE§11 | Room type / name suggestion chips right after creation; Auto Classify bulk apply | copy as a question (KE§11 „Ar tai Virtuvė? [Taip] [Kita…]"; design §1) | design §1; no task | UNPLANNED |
| 40 | TP§6, TE§2b, KE§3, TK | One-click room (click inside → outline). Togal has none | keep and promote (TE§10) | W1-D D2 room tool R (vector `outline_at`) | running (W1-D) |
| 41 | KE§3 | One-click area with positive and negative clicks (outside expands, inside shrinks), mask preview on hover | copy (design §1, §5), only if `outline_at` supports seeds | W1-D D2 (conditional) | running (W1-D) |
| 42 | PA§5, BI zones | The main viewer's click tool is the raster flood fill; the vector outline exists only on the room sheet | adapt: vector in the viewer, raster as the fallback | W1-D D2 | running (W1-D) |
| 43 | TK check-sheet section | Room schedule checked against the measured outline (neither competitor does this) | keep ours | `vector_rooms` `plotas_nesutampa`; Patikra questions | shipped pre-v2 |
| 44 | TP§4, TK Kreo§2 | Area variants: footprint, gross, GIA, net; Kreo GIA/GEA/NIA | no verdict in research — manager decides | — | UNPLANNED |
| 45 | TP§4 | Shared walls split between rooms by a dominance order (stairwell beats office, equal ranks 50/50) | no verdict in research — manager decides | — | UNPLANNED |
| 46 | TP§6 | Neighbouring rooms updated after a vertex edit (in Togal the split stays frozen) | no verdict in research — manager decides | — | UNPLANNED |

### 1E. Walls, openings, geometry to quantities

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 47 | TP§4, TK | Wall perimeter along the faces, wall centreline, door centreline | keep ours (TP§10: dimension-string perimeters) | `dimension_sum.py:366`, `_sienos` | shipped pre-v2 |
| 48 | TP§3, TK Kreo§2/§6, TK Togal§5 | Wall types from tags (exterior, shaft, corridor, interior, demising, bathroom); thickness/hatch classes; wall-type schedules | no verdict in research — manager decides | — | UNPLANNED |
| 49 | TP§3, TK Kreo§2 | Door type classification; doors and windows grouped by width | no verdict in research — manager decides | `door_type_reader.py:162`, `door_schedule.py:185` | shipped pre-v2 |
| 50 | TK Kreo§2/§6, KE§12.7 | Remove doorways and windows from wall-finish lines (full height / door height) | no verdict in research — manager decides | `_opening_should_deduct` (universal_rules.py:959), `REVEALS_SCOPE_DEFAULT` (:1020) | shipped pre-v2 |
| 51 | TP§4 | An opening deduction rule (NRM2 0,5 m²); Togal has none | no verdict in research — manager decides | `UNIVERSAL_RULES` LT / NRM2 / VOB (universal_rules.py:23–40) | shipped pre-v2 |
| 52 | TP§4, TK | Heights typed per classification, not read from the drawing | keep ours (TP§10: typed heights are not worth copying; Pathon reads height markers) | `height_markers.py:856` | shipped pre-v2 |
| 53 | KE§6, TK | Vertical area = perimeter × height; volume = area × height | keep ours (TK: height is a reviewed fact) | `universal_rules.calc_room_quantities` | shipped pre-v2 |
| 54 | TP§4, TK Kreo§4 | Every number recomputed from the geometry on each edit | no verdict in research — manager decides | `/recompute-interior` | shipped pre-v2 |
| 55 | TP§1, TP§10 | Snap to the drawing's own geometry (wall corners and faces) | copy (TP§10 gap 1) | viewer-drawing-geometry Task 4 | shipped v2 (research/togal-pipeline-analysis) |
| 56 | TP§1, TE§3, KE§4 | More snap modes: alignment, % or distance along a line, closed edges, intersection, midpoint, dynamic guideline; a snap-distance setting | no verdict in research — manager decides; KE§11: do not bind S to snapping | — | UNPLANNED |
| 57 | TP§10 | Whole-sheet geometry layer (wall solid, every outline, openings) | copy (TP§10 gap 2) | viewer-drawing-geometry Task 6 | shipped v2 (research/togal-pipeline-analysis) |

### 1F. Symbols, counts, legends

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 58 | TP§3 | Symbol counts inside the AI run (fixtures, doors, furniture, appliances) | copy (v2 map D; design §4B) | W2-A A2 generalised counter | planned (W2-A) |
| 59 | TP§3, TE§0, KE§3, CD§3.2 | Image search: box one symbol, get the matches, turn them into a count | copy (v2 map D; this reverses CD§3.2 "skip") | v2 W2 „Rasti panašius" (one sheet) | shipped v2 (togal/symbol-search) |
| 60 | TE§0, KE§3 | The same search over all sheets on the server ("find in other drawings") | copy (design §4B) | W2-A A3 `batch_find_symbol` | planned (W2-A) |
| 61 | KE§3 | Auto Count review: similarity slider, untick result tiles, rotation/flip, a search area, "Split by Text" | adapt: the v2 list and remove exist; rotation/mirror are scored in `cv_match`; split-by-text has no verdict | v2 W2; W2-B B2 | shipped v2 (togal/symbol-search) |
| 62 | TP§3, KE§10 | Matches inside legends, tables and title blocks create no count marks | copy (design §4A, Kreo's rule) | design §4A; not named in the W2-A tasks | UNPLANNED |
| 63 | TK Togal§8, TP§3 | Over-count honesty: AI-found marks look different („N rasta automatiškai") | copy (v2 map D honesty) | v2 W2 follow-up (hollow marks); W0-B copy | shipped v2 (togal/symbol-search) |
| 64 | TP§3 | Earlier searches kept for reuse in the project (`symbol_id`) | no verdict in research — manager decides | — | UNPLANNED |
| 65 | TP§3, TE§0 | Pattern (hatch) search into a classification with a hatch | no verdict in research — manager decides | nearest: `floor_coverings` colour hatch | UNPLANNED |
| 66 | BI legend 1, design §4B | Legend block found and split into rows (glyph box + text) | copy (design §4B; founder §9.3: suggest first) | W1-E `legenda` zones; W2-A A1 `split_legend_rows` | planned (W2-A) |
| 67 | BI legend 1 | Vector counter generalised from diffusers to any legend row, all pages, instances with boxes | copy (design §4B) | W2-A A2 | planned (W2-A) |
| 68 | BI legend 2 | Black-only glyphs counted by a server-side raster batch | copy (design §4B) | W2-A A3 | planned (W2-A) |
| 69 | KE§3, KE§11 | Review before create for legend counts (✔/🗑 per row, ✕ per instance, one Create button) | adapt (KE§11; no confidence slider) | W2-B B2 | planned (W2-B) |
| 70 | design §4B, PA§7 D21 | Legend counts flow live into sąmata rows with a ledger sentence | copy (PA D21) | W2-B B3 | planned (W2-B) |
| 71 | BI legend 4, design §4B | Legend stored per project and offered on the same architect's next project | copy (design §4B) | W2-A A4, W2-B B4 (`api/legends.py`) | planned (W2-A) |
| 72 | BI legend 4 | Vision legend reader as the fallback for raster legends (paid, OK per run) | adapt (design §4B) | design §4B; no task line in W2-A or W2-B | UNPLANNED |
| 73 | BI legend 3 | Floor-covering legend lines that are read today and thrown away (`geometry_lane.py:293`) brought to the user | copy (design §4B "surfaced the same way") | design §4B; no task | UNPLANNED |
| 74 | BI legend 5 | Page type "legend" in the Pass-1 `tipas` enum | no verdict in research — manager decides | — | UNPLANNED |
| 75 | BI legend 6 | Something reads the symbol training crops | no verdict in research — manager decides | — | UNPLANNED |
| 76 | KE§5 | Results clustered so that the same colour means the same size, look, label or type | no verdict in research — manager decides | — | UNPLANNED |
| 77 | KE§3, KE§7 | "Find similar areas" / "Select like" from a selected shape | no verdict in research — manager decides | — | UNPLANNED |
| 78 | TE§0 | Text-search hits turned into a count | no verdict in research — manager decides | — | UNPLANNED |

### 1G. Schedules and tables

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 79 | BI schedule 1, TK Kreo§5 | Generic table reader with row and cell bboxes | copy (design §4C) | W3-A T1 | planned (W3-A) |
| 80 | BI schedule 1, TK | Door and window schedules read cell by cell with bboxes | copy (design §4C) | W3-A T2 | planned (W3-A) |
| 81 | BI schedule 3 | Deterministic finish schedule (apdailos lentelė) and tile specification with positions | copy (design §4C) | W3-A T2 | planned (W3-A) |
| 82 | BI schedule 4 | The free re-read and detect-run read tables too (a „lentelės" stage) | copy (design §4C) | W3-A T3 | planned (W3-A) |
| 83 | BI schedule 4 | The free re-read and detect-run also read the designer's figures and height markers (today only the paid pass does) | no verdict in research — manager decides (the gap is listed; design §4C names tables only) | — | UNPLANNED |
| 84 | BI schedule 5 | A schedule row shown on the drawing („Rodyti brėžinyje") with its crop | copy (design §4C) | W3-A T4 | planned (W3-A) |
| 85 | TK Kreo§5, TK check-sheet | Reconciliation questions: schedule vs drawn openings, finish table vs plan, legend total vs computed | copy (design §4C; neither competitor reconciles) | W3-A T4 | planned (W3-A) |
| 86 | TK Kreo§5 | Count the schedule's tags where they sit on the plan (Kreo "Count Matching Tags") | design §1 names cross-reference; no explicit verdict for tag counting | W3-A matches by opening, not by tag | UNPLANNED |
| 87 | TK Kreo§5 | A table sent to a spreadsheet ("Export to Sheets") | no verdict in research — manager decides | — | UNPLANNED |
| 88 | BI schedule 2 | The Vision schedule extractor (`vision/schedule_extractor`) is not wired | no verdict in research — manager decides (design: deterministic first) | — | UNPLANNED |

### 1H. Editing gestures and the click vocabulary

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 89 | TP§10 gap 3, TE§2b, TK | Vertex editing: drag, insert at a midpoint, delete, wall snap, live consequence, red guard on a self-crossing ring | copy (TP§10 gap 3) | viewer-drawing-geometry Tasks 7, 8, 10 | shipped v2 (research/togal-pipeline-analysis) |
| 90 | KE§3, PA§5, design §5 | Double-click a room or shape to enter outline edit | adapt (KE§11; PA§5 "2 + n") | design §5; not in a W1-B or W1-D task | UNPLANNED |
| 91 | KE§3, KE§11, design §4D | Vertex pop-up: Ištrinti · Iškirpti angą (Cut Path); skip Align | adapt (KE§11) | design §4D, §5; no task | UNPLANNED |
| 92 | TE§2b, KE§3, design §4D | Drag an edge to move the whole segment (skip Ctrl-drag duplicate) | adapt (KE§11; design §4D) | design §4D; no task | UNPLANNED |
| 93 | KE§3 | Select several vertices (marquee or Ctrl-click) and delete them together | no verdict in research — manager decides | — | UNPLANNED |
| 94 | TP§6, TE§2b, KE§3, TK | Split (Knife), Merge, Subtract on outlines | keep Pathon's (TE§10) | v2 W5 Padalyti / Sujungti / Atimti | shipped v2 (togal/outline-tools) |
| 95 | TE§2b, PA§5 | Merge = click A, Shift-click B, M; subtract = X and a drag | adapt (PA§5; design §5) | W1-B B4 keys M/X; W1-D D1 Shift-click | running (W1-B) |
| 96 | TE§2b, TE§10 | Draw-to-subtract an island or opening the reader missed, saved as a deduction with its own evidence line | adapt (TE§10) | v2 W5 Atimti with „Kas atimama?" | shipped v2 (togal/outline-semantics) |
| 97 | KE§3, design §4D | One-click negative inside an outline | adapt (design §4D) | design §4D; no task | UNPLANNED |
| 98 | TE§2b | A split leaves a 0,001 cm gap | adapt only if splits are stored as geometry (TE§10) | — | UNPLANNED (conditional) |
| 99 | TP§6, KE§3 | Lasso / freehand selection | copy (v2 map C) | v2 W5 Laso (L) | shipped v2 (togal/outline-tools) |
| 100 | TE§2b, KE§3, design §5 | Box selection (left→right = whole shapes, right→left = touched) | adapt (design §5 Select "marquee") | design §5; no task | UNPLANNED |
| 101 | TP§6, TE§2b, KE§7 | Arcs, rectangle/circle shapes, rotate/flip, group, merge lines, offset, extract/join/enclose/split polylines | no verdict in research — manager decides (design §1 skips "feature breadth") | — | UNPLANNED |
| 102 | TE§2b, KE§3, KE§7 | Clipboard and duplicate (copy, paste, paste with a point, Alt-drag copy, smart paste), arrow-key nudge | no verdict in research — manager decides | — | UNPLANNED |
| 103 | TE§6 | Repeating groups | skip (design §1) | — | UNPLANNED (skip) |
| 104 | TE§2b | Type a length, angle or height while drawing (HUD) | no verdict in research — manager decides | — | UNPLANNED |
| 105 | TE§2b, KE§3 | Shift: Togal turns snapping off and locks the angle, Kreo forces 15° steps | keep ours (Shift = ortho + 45°, design §5) | `lib/viewerShortcuts.js` | shipped pre-v2 |
| 106 | TE§2b, design §5 | Hold Ctrl/Alt/Cmd to jump to the snap target | copy (design §5 "Ctrl held = jump to snap") | design §5; not in a W1-B task | UNPLANNED |
| 107 | KE§3, KE§11 | Esc removes the last point and exits only when no points are left | copy (KE§11) | W1-B B4 `escOrder.js` | running (W1-B) |
| 108 | KE§3, KE§11 | Right-click during a draft opens „Baigti / Atšaukti"; the visible buttons stay | adapt (KE§11) | W1-B B5 | running (W1-B) |
| 109 | TE§2b, KE§3, PA§7 D22 | Distance commits on the second click; Shift-click continues the chain (Kreo "Continue") | copy (PA D22) | W1-B B5 | running (W1-B) |
| 110 | TE§2b, KE§3 | Live segment length (and Kreo's angle arc) at the cursor | live length kept; no verdict on the angle arc | `MeasureLayer.jsx` | shipped pre-v2 |
| 111 | TE§2b | Full-screen 1 px crosshair | no verdict in research — manager decides | — | UNPLANNED |
| 112 | KE§3 | Cursor priority rules (wait > grabbing > grab > crosshair > pointer) | no verdict in research — manager decides | — | UNPLANNED |
| 113 | TE§2b, TE§10 | Count: one click adds a mark, a click on the mark removes it | keep Pathon's (TE§10: fewer clicks) | count tool, `CountLegendPanel` | shipped pre-v2 |
| 114 | KE§3 | Count marks in 9 shapes; a second click on the same spot is ignored; dashed trace between marks | no verdict in research — manager decides | — | UNPLANNED |
| 115 | PA§5, design §5 | Count type picked from a list beside the cursor | adapt (PA§5) | design §5 "type menu"; no task | UNPLANNED |
| 116 | KE§3 | One-click line (click a wall centre; bend or extend) | no verdict in research — manager decides | — | UNPLANNED |
| 117 | KE§3, KE§4 | Magic wand (Connect / Enclose) and dropper | no verdict in research — manager decides; design §4 keeps `MagicWandTool` dead | — | UNPLANNED |

### 1I. Selection, menus, panels

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 118 | PA§5 F1, PA§7 D18 | Click a room on the drawing to select it; Shift-click adds | copy (PA D18) | W1-D D1 | running (W1-D) |
| 119 | KE§7, KE§11, PA§7 B2 | Floating bar at the selection with icon and Lithuanian text (Taisyti kontūrą · Sujungti · Atimti · Neskaičiuoti · Rodyti įrodymus) | adapt (KE§11) | W1-B B6 `SelectionBar.jsx` | running (W1-B) |
| 120 | TP§11, TE§6, TE§10 | Right-click on a room: change type or finish, exclude, show evidence (Togal: searchable assign list with recently used) | copy for rooms (TE§10) | W1-B B6 (the menu holds the bar's items); design §5 | running (W1-B) |
| 121 | TP§5, TP§8, TE§5, TK | Quantities panel: totals, eye toggles, sort/filter, right-click, two-way highlight | copy (v2 map B) | v2 W1 Kiekiai; W1-A hooks | shipped v2 (togal/quantities-panel) |
| 122 | TP§8, TE§5, TP§10 | Classification tree (folders, items, instances) as the primary model | keep ours (TP§10: sąmata rows with ledgers are the product); Kiekiai groups by work family × room | v2 W1 | shipped v2 (togal/quantities-panel) |
| 123 | TE§0, TE§5, TE§10 | Isolate one line's geometry (Ctrl+click eye, „rodyti tik šią eilutę"), dim the rest | adapt (TE§10) | design §7 wave 5 "isolate" | planned-undecided (wave 5) |
| 124 | TE§5, TE§10 | Panel density: 32 px rows, 12 px right-aligned values, 60 px unit column; the hover-only eye is not copied | adapt (TE§10) | W1-C rows 39 px, 14 px text | merged v3 (W1-C) |
| 125 | TE§5, KE§6 | Keyboard in the panel (↑↓, ←→ fold, Shift range), Shift-click range, invert selection | no verdict in research — manager decides; multi-select is in wave 5 | design §7 wave 5 "multi-select" | planned-undecided (wave 5) |
| 126 | TE§5, KE§6, KE§12.3 | Folders with drag and drop, inline rename, colour inherited from the folder, pin | no verdict in research — manager decides | — | UNPLANNED |
| 127 | KE§6 | Filters by origin (AI vs manual), pages, colour | no verdict in research — manager decides | v2 W1 sort/filter covers part | UNPLANNED |
| 128 | KE§1, KE§11 | Right panel as a mode host | copy (design §3) | W1-A `RightPanelHost.jsx` | merged v3 (W1-A) |
| 129 | KE§6, KE§11 | Property sheet per selection (Name … Volume) with assemblies | keep ours (KE§11: the evidence sheet is ahead); borrow only the two-column label/value rhythm | room sheet (`room_facts.py:1872`) | shipped pre-v2 |
| 130 | KE§1, KE§6, KE§12.1 | Report pane: spreadsheet with formula bar, pivot, live link to measurements | no verdict in research — manager decides; the Sąmata view expands to full width instead | W1-A „Išskleisti" | UNPLANNED |
| 131 | KE§1, KE§12.3 | Measurements Manager toggled by M with a count badge | no verdict in research — manager decides (design §5 uses M for merge) | — | UNPLANNED |
| 132 | TK Kreo§3, KE§7 | Auto Focus: selecting a row or room zooms to it | adapt: F frames the selection | W1-B B4 (F); v2 follow-up "focus scrolls to the page, not the room" has no task | running (W1-B) |
| 133 | TE§5 | Empty-panel start ("Start with AI … or from scratch", library, video) | no verdict in research — manager decides | — | UNPLANNED |

### 1J. Overlay rendering and visual language

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 134 | TE§4, KE§5, CD§2.2, PA§7 A4 | One overlay vocabulary: solid = read, dashed = estimated or proposed, red = error only, selection = heavy neutral outline | adapt (TE§10, KE§11; founder §9.2) | W1-C `--ov-*`, `lib/overlayTokens.js` | merged v3 (W1-C) |
| 135 | TE§2, KE§5, CD§2.2, CD§4.3 | Rainbow palettes (Togal 50 colours, Kreo 18 random hues, one hue per room type) | skip (design §1; KE§11 calls it childish); replaced by one neutral zone tint with the type in the label | W1-C | UNPLANNED (skip) |
| 136 | TE§4, KE§2, KE§5 | Fill alpha with hover and selected steps; strokes constant in screen pixels | adapt (design §6: fills 0,16 / 0,24, strokes 2 / 3 px) | W1-C | merged v3 (W1-C) |
| 137 | KE§5, KE§11, TE§4 | One handle colour and one "proposed" style in every tool; the snap marker's shape says what it hits | adapt (KE§11) | W1-C C2 | merged v3 (W1-C) |
| 138 | KE§5, KE§11, KE§2 | Labels as neutral pills with tabular numbers (not Kreo's colour-filled pill) | adapt (KE§11) | W1-C `OverlayLabel` | merged v3 (W1-C) |
| 139 | TE§4, KE§5, TE§10 | Legend card on the drawing (kind → style → meaning) | adapt (TE§10) | W1-C `OverlayLegend` in every layer | merged v3 (W1-C) |
| 140 | TE§4, TP§11, TE§10 | User controls for polygon opacity and line width | adapt (TE§10: reduce Togal's settings to three) | design §7 wave 5 | planned-undecided (wave 5) |
| 141 | TP§1, TE§4, TE§10, KE§5 | Drawing opacity / „Išvalyti foną" (clear background); black and white | adapt (TE§10) | wave 5 names only overlay opacity and line width | UNPLANNED |
| 142 | TE§4, KE§5 | Toggle for shape names and dimensions on the drawing ("Show dimensions", also in the PDF) | no verdict in research — manager decides | — | UNPLANNED |
| 143 | TE§2 | Three-state visibility and selection icons (visible / partial / hidden) | no verdict in research — manager decides | — | UNPLANNED |
| 144 | CD§2.8, CD§4 | A faint blueprint grid behind the drawing | copy (CD, 2026-05); v3 does not mention it | — | UNPLANNED |
| 145 | CD§2.3, CD§4, KE§4, PA§6 | ✨ AI badges on AI features | conflicting: copy (CD§2.3) vs a toy trope (PA§6 item 7, „✨ Pathon"); manager decides | — | UNPLANNED |
| 146 | CD§2.5, CD§2.6 | Category cards in the right panel; [●] tag pills with a type pill | copy (CD, low impact, 2026-05), superseded by plain words and dense rows (W1-C) | W1-C C3 | UNPLANNED (superseded) |

### 1K. Chrome and layout

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 147 | TE§1, CD§2.1, design §6 | Dark slate frame (60 px header, dark pill) around a light canvas | adapt (TE§10, CD§2.1) with our colours; dark chrome is decided later | design §7 wave 6 "Look" | planned-undecided (wave 6) |
| 148 | KE§2, KE§11 | Dark theme by default, 8 tones, Proxima Soft, 10–20 px radii | skip (KE§11; design §1) | — | UNPLANNED (skip) |
| 149 | TE§2, TE§10 | Labs dark mode through `invert()` | skip (TE§10) | — | UNPLANNED (skip) |
| 150 | TE§1, TE§10, PA§7 B2 | Floating icon tool cards (45 px) with short Lithuanian labels, grouped, overflow „Daugiau" | adapt (TE§10, KE§11) | W1-B B1 `ToolRail.jsx` | running (W1-B) |
| 151 | TE§1, TE§10 | Bottom-centre pill with only the active mode's options and Baigti / Atšaukti | copy (TE§10) | W1-B B2 `ModePill.jsx` | running (W1-B) |
| 152 | KE§1, KE§11 | Zoom cluster bottom-right (fit, zoom, marquee zoom, minimap, full screen) | copy the cluster (KE§11) | design §3; no task | UNPLANNED |
| 153 | KE§1, CD§2.4, CD§4 | Three-row top chrome (project tabs / page tabs / tools) | copy (CD§2.4, 2026-05), superseded by design §3/§6 (one frame) | — | UNPLANNED (superseded) |
| 154 | TE§1, PA§7 C14 | The drawing gets the room: canvas ≈ 50 %, 56 px sheet strip, right panel 340 px resizable | adapt (PA C14) | W1-A (canvas 32 % → 51,6 %) | merged v3 (W1-A) |
| 155 | TE§1, KE§12.1 | Panels resizable and remembered; the toolbar must not overflow at 1280 px (Kreo just shrinks the canvas) | adapt (design T6) | W1-A width persisted; W1-B B1 e2e at 1280 | merged v3 (W1-A) |
| 156 | TE§1, CD§3.4 | 2D/3D toggle, 3D view; split panes (2–4) | skip 3D (design §1; CD§3.4); no verdict on split panes | — | UNPLANNED (skip) |
| 157 | CD§3.1, CD§3.3 | Bluebeam's tool-chest density and desktop menu bar | skip (CD§3) | — | UNPLANNED (skip) |
| 158 | PA§4, design §3 | One workspace: steps 1–3 are views of one persistent drawing | copy (design §3; founder §9.1) | W1-A | merged v3 (W1-A) |

### 1L. Feedback, notices, undo, history

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 159 | KE§3, KE§11 | One hint sentence beside the cursor per mode and AI state, instead of banners | copy (KE§11) | W1-B B3 `CursorHint.jsx` | running (W1-B) |
| 160 | PA§7 B5, TE§7 | One notice system (3 tones); the re-read banner becomes a one-line chip; instructions in one place | adapt (PA B5; founder §9.6) | W1-C `components/ui/Notice.jsx` | merged v3 (W1-C) |
| 161 | TE§7, TE§10 | Toasts bottom-right with a coloured bar for passing results | copy (TE§10) | design §6; W1-D D3 undo toast | running (W1-D) |
| 162 | TE§7, TE§10, KE§8 | Compact 300 px confirm box with a grey footer for destructive actions | copy (TE§10) | design §6; no task | UNPLANNED |
| 163 | PA§5 F5, PA§7 D20 | Undo after every outline, merge, split and subtract save | copy (PA D20; contractor-user rule "undo everywhere") | W1-D D3 (routes return `previous`) | running (W1-D) |
| 164 | TP§6, KE§8, KE§11 | „Kas pasikeitė — Atšaukti" after a re-read or AI proposal | copy (KE§11) | W4-A M3 | planned (W4-A) |
| 165 | TP§11, TE§6, TK | Undo/redo and a history with restore (Togal history mode; Kreo 25 steps per session) | copy (TP§11) | v2 W4 Istorija, v2 W10 Versijos; wave 5 "history" | shipped v2 (togal/comfort-shortcuts) |
| 166 | TK Togal§4 | Version history with a change log (neither competitor shows one) | keep ours | v2 W10 Lithuanian diff sentences | shipped v2 (togal/versions) |
| 167 | TE§2b, TE§10, PA§7 D23, PA App. G | Esc order: tool, then panel, then selection | copy (design §5) | W1-B B4 | running (W1-B) |
| 168 | KE§8 | Warning for "too many measurements" | no verdict in research — manager decides | — | UNPLANNED |
| 169 | KE§12.5 | Offline / lost-connection banner with Refresh | no verdict in research — manager decides | — | UNPLANNED |
| 170 | KE§8 | Rating plus text prompt after an AI run | no verdict in research — manager decides; 👍/👎 exist in Pokalbis (v2 W11) | — | UNPLANNED |
| 171 | TP§5, TP§10, TE§10, TK | Per-fact confidence with a reason sentence and an evidence crop (no competitor has it); evidence shown by stroke style, not dots | keep ours (TP§5; TE§10) | `room_facts.py:1872`, `evidence.py:415`; W1-C stroke styles | shipped pre-v2 |

### 1M. Onboarding, help, keyboard

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 172 | TP§11, TE§8, KE§9 | First-run coach marks and onboarding bubbles; shape-edit help card | copy (v2 map K) | v2 W4 coach marks | shipped v2 (togal/comfort-shortcuts) |
| 173 | TP§11, KE§9, KE§12.5 | Learn hub, academy, webinars, help widget (Intercom, Gleap), What's new | no verdict in research — manager decides | — | UNPLANNED |
| 174 | TP§11, TE§8, KE§7 | Printable shortcut guide and an in-app shortcuts panel | copy (TP§11) | v2 W4 „?" guide + PDF | shipped v2 (togal/comfort-shortcuts) |
| 175 | TE§8, TE§10 | Shortcut sheet that lights up the key being pressed | adapt (TE§10) | design §7 wave 5 "live keys" | planned-undecided (wave 5) |
| 176 | KE§7, KE§11, PA§7 D23 | A key for every tool (1/V select, 2/3/4/6, K, F, E, M, X, R, G); tooltip = key + one sentence | adapt (KE§11: 3 stays area, S stays walls) | W1-B B1, B4 | running (W1-B) |
| 177 | TE§2b, TE§10 | Hold Space to pan (or H); F frames the selection | copy (TE§10) | W1-B B4 | running (W1-B) |
| 178 | KE§3, KE§7 | Pan with the right or middle mouse button; zoom keys (+ / − / 0) | no verdict in research — manager decides | — | UNPLANNED |
| 179 | TE§2 | Markup / redline mode and text boxes | no verdict in research — manager decides | — | UNPLANNED |
| 180 | KE§4, KE§7 | Annotations: stickers, comments, callouts, dimension lines, TraceLink | no verdict in research — manager decides | — | UNPLANNED |
| 181 | TE§8 | Labs tools (carpet seams, polygon dimensions, auto 3D, quantities to Excel) | no verdict in research — manager decides | — | UNPLANNED |
| 182 | TP§11, TK Kreo§7 | English only, imperial first | keep ours (Lithuanian and metric: CLAUDE.md, design §1) | — | shipped pre-v2 |

### 1N. Export, pricing, organisation

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 183 | TP§8, TK, TE§0 | Excel: screen view with groupings, full flat export, filters, columns, copy all | copy (v2 map H) | v2 W8 „Grupuoti pagal" + preview | shipped v2 (togal/export) |
| 184 | TP§8, TK Kreo§7 | Customer-specific CSV/Excel template; formulas kept in Excel | keep ours: the „kaip mano sąmatose" template layout | `samata_template.py`, Excel `?layout=template` | shipped pre-v2 |
| 185 | TP§8, TK, TE§0 | PDF export with overlays and a legend (visible layers only, segment lengths) | copy (v2 map H) | v2 W8 „PDF su žymėjimais" | shipped v2 (togal/export) |
| 186 | TP§8 | Draw-log export (who drew what) | no verdict in research — manager decides | v2 W11 `corrections.csv` is the nearest | UNPLANNED |
| 187 | TP§4, TP§8 | Assemblies: components, formulas, waste, material and labour cost, cost codes | copy (v2 map G), not assemblies-first (design §1) | v2 W9 Rinkiniai, `kodas` | shipped v2 (togal/assemblies) |
| 188 | TP§8 | Breakdowns (tier / item / subitem tags per feature) | no verdict in research — manager decides | — | UNPLANNED |
| 189 | TP§8, TP§10 | One room in several classifications (floor, ceiling, paint) with nothing reconciling them | keep ours (TP§10: sąmata rows with ledgers) | `ledger.py` | shipped pre-v2 |
| 190 | TE§4, v2 map I | Compare two editions of the drawing as an overlay | copy (v2 map I) | v2 W10 „Palyginti leidimus" | shipped v2 (togal/versions-overlay) |
| 191 | PA§7 D21, design §4F, TK Kreo§3 | A measured length or count attached to a sąmata row, updated live with its own ledger line; drag onto a row | copy (PA D21) | W4-A M1, M2 | planned (W4-A) |
| 192 | PA§5, PA§7 D22 | Edit a quantity where it is shown (double-click in Kiekiai, Tab to the next) | copy (PA D22) | W4-A M2 (Kiekiai only; not the drawing label) | planned (W4-A) |
| 193 | TP§8, TK | Integrations (Procore, ServiceTitan, third-party OAuth, an API) | no verdict in research — manager decides | — | UNPLANNED |
| 194 | TP§8, KE§8, KE§11 | Billing, trial counters, add-on upsell dialogs | skip for now (KE§11; design §1 non-goal) | billing built, off (`billing/flag.py`) | UNPLANNED (skip) |
| 195 | TK Togal§7, TK Kreo§7 | Price points (Togal $299/user/month; Kreo $35/$70/$175, AI on Pro only, 7-day trial, free guests) | no verdict in research — manager decides | §3 below | UNPLANNED |

### 1O. Learning loop, chat, collaboration, agents

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 196 | TP§7, TK | Corrections logged as training data; labeller and reviewer roles; accept/reject | keep ours (TP§7: corrections are the corpus, per account) | v2 W11 journal, `build_ground_truth.py --with-corrections` | shipped v2 (togal/chat-learning) |
| 197 | TP§7, KE§8 | 👍/👎 on chat; accept/reject events on AI suggestions | copy (v2 map L) | v2 W11, `record-decision` | shipped v2 (togal/chat-learning) |
| 198 | TP§8, TK Togal§5 | Chat over the plans and specs | copy (v2 map J) | v2 W11 Pokalbis with pills | shipped v2 (togal/chat-learning) |
| 199 | TE§0, TP§6, KE§12.1 | Collaboration: users with permissions, one view per person merged, per-measurement author | skip until the core is done (design §1; §9.5 open) | — | UNPLANNED (skip) |
| 200 | KE§9, KE§10, TK Kreo§2 | Caddie agent and Spot voice copilot | skip (design §1 non-goal; §8 parked) | — | UNPLANNED (skip) |
| 201 | TK Kreo§2 | Detection from a typed prompt ("Objects: type what to look for") | no verdict in research — manager decides | — | UNPLANNED |
| 202 | TK Kreo§2 | Published accuracy measured against labelled ground truth (Kreo AM 3.0: outlines 72 → 94 %) | no verdict in research — manager decides | `eval_harness.py` (in-sample corpus) | UNPLANNED |
| 203 | KE§3 | "Fix with AI" per contour; 👎 "don't search areas like this" | no verdict in research — manager decides (KE§11 copies only ✔/🗑) | — | UNPLANNED |
| 204 | KE§3, KE§11 | AI confidence slider before create | skip (KE§11; founder: confidence is not the primary signal) | — | UNPLANNED (skip) |

### 1P. Pathon's own audit items (PA §7, §8, Appendix)

| # | Source | What it is | Verdict | Where in v3 | Status |
|---|---|---|---|---|---|
| 205 | PA§7 A1 | Contrast floor (provenance chip at 1,47:1, muted text, unit text) | rank 1 | W1-C (contrast failures 31 → 0) | merged v3 (W1-C) |
| 206 | PA§7 A3 | Type scale 12 / 14 / 16, at most 6 sizes | rank 3 | W1-C (font sizes on screen 9 → 4) | merged v3 (W1-C) |
| 207 | PA§7 A6 | Radius, shadow and z-index tokens | rank 6 | W1-C | merged v3 (W1-C) |
| 208 | PA§7 A8 | Sora/Hanken/JetBrains off the app; mono for numbers only | rank 8 | W1-C (landing keeps its fonts) | merged v3 (W1-C) |
| 209 | PA§7 A13 | Clean-up: inert `.dark` block, `dark:` classes, 266 `[hsl(var(--x))]` classes | rank 13 | manager decision (2026-10-18): codemod after wave 1; `.dark` still at `index.css:158`, `dark:` in 7 files | UNPLANNED |
| 210 | PA§7 B9 | Collisions: panel offset, hint pill against the walls legend, clipped save label at 1280 | rank 9 | W0-B | merged v3 (W0-B) |
| 211 | PA§7 B10 | Copy pass on banned words; one verb „Taisyti kontūrą" | rank 10 | W0-B | merged v3 (W0-B) |
| 212 | PA§7 B11 | Calmer step bar and the same top bar on every view | rank 11 | W1-A A5 | merged v3 (W1-A) |
| 213 | PA§7 B12 | Sąmata row actions: delete moves into a ⋯ menu; price-source dots become words | rank 12 | — | UNPLANNED |
| 214 | PA§7 C15 | One design language for the viewer and Patikra | rank 15 | W1-A hosting + W1-C tokens | merged v3 (W1-A) |
| 215 | PA§7 C16 | Sticky evidence pane on the room sheet and a room picker (no „Kitas" × n) | rank 16 | — | UNPLANNED |
| 216 | PA§7 C17, design §3 | Projektai as status rows; the mono gap inside numbers | rank 17 | design §3; no task | UNPLANNED |
| 217 | PA§7 D22 | Enter accepts a Patikra proposal and moves to the next question | copy (PA D22; design §2 "2 → 1") | — | UNPLANNED |
| 218 | PA§5 | Find similar from a right-click on a symbol, with the count linked to its row | adapt (PA§5) | W2-B links legend rows to counts; the right-click entry has no task | UNPLANNED |
| 219 | PA App. A–F, H | Seven side bugs (scale state between viewers, panel offset, hint side, dead „Peržiūra", stale tooltip, two number formats, clipped label) | fix | W0-B | merged v3 (W0-B) |
| 220 | PA App. I | The Kiekiai footer Σ adds unlike work types when no filter is set | fix (PA appendix) | — | UNPLANNED |
| 221 | PA§6 item 7 | Toy tropes: endless red pulse on the selected room, emoji in strings, „✨ Pathon", rounded-full pills | fix (PA§6) | W1-C: the focused room now pulses twice (`RoomZoneLayer.jsx:85`); ✨ is still in 9 frontend files and no task names it | merged v3 (W1-C) |
| 222 | PA§8 Q5, design §9.6 | Name of the account page (it also says „Nustatymai") | the founder names it later | — | UNPLANNED |
| 223 | PA§2, design T6 | A UI probe in the repo: font census and contrast check | copy (design T6) | W1-C `scripts/ui-probe.mjs` | merged v3 (W1-C) |
| 224 | TE§2b, KE§3, TK, design §2 | Clicks per correction (T1) and time from PDF to a checked sąmata (T2), measured against Togal and Kreo | design §2 targets | W0-A baselines; wave-1 acceptance item 4 | running (W0-A) |

### Counts (Table 1, first status per row)

| Status | Rows |
|---|---:|
| shipped pre-v2 | 24 |
| shipped v2 | 33 |
| merged v3 | 24 |
| running | 23 |
| planned | 18 |
| planned-undecided (wave 5/6) | 5 |
| UNPLANNED — gaps (no suffix): 25 should be planned (§4.1) + 58 to decide (§4.2) | 83 |
| UNPLANNED — skip / superseded / conditional (§4.3) | 14 |
| **Total** | **224** |

---

## 2. Interior calculation coverage (CLAUDE.md §1, §3, §6, §8), presence only

Engine files: `backend/extractor/universal_rules.py` (UR), `backend/extractor/vision_call.py` (VC), `backend/extractor/sanity_checks.py` (SC), `backend/main.py` (main). This table records only whether each item exists in the code. It does not judge whether the code is correct, and it changes no formula. Citations come from grep on togal-v2 @ 8331799.

### 2.1 Formulas §1.1–§1.15

| CLAUDE.md | Item | Status | Implemented where (grep citation) |
|---|---|---|---|
| 1.1 | Walls gross and net (perimeter × H − openings − tiled zones) | implemented | UR `calc_room_quantities` → `walls_gross_m2`, `walls_paintable_m2`, `_tile_zone_deducted_m2` (return dict ≈ :3383–3412) |
| 1.1 | Openings under 0,5 m² not deducted | implemented | the default is LT with a 1,0 m² threshold; NRM2 (0,5 m²) and VOB can be chosen. UR `UNIVERSAL_RULES` :25–40, `_opening_should_deduct` :959 |
| 1.1 | Furniture zones deducted | missing | no furniture-zone key; "spinta" appears only in room-name folding, UR :886–895 |
| 1.1 | Panel / wallpaper / clay zones | partially | finish factor `_walls_paint_factor`, `molio_tinko_m2` (UR `calc_room_quantities`, comments ≈ :2788–2797) |
| 1.1 | Reveals, niches, column surfaces added | implemented (niches as separate lines) | UR `_opening_adds_reveal` :2024, `holes_with_walls` :2497 → `_skyliu_sienos_m`; VC „LED nišų dažymas" :3591 |
| 1.1 | Ceiling = floor area; walls and ceiling, primer and each coat as separate lines | implemented | `ceiling_paintable_m2`; VC `_build_pozicijos_from_rooms` :3450 („Sienų dažymas (1 sluoksnis)/(2 sluoksnis)", „Lubų dažymas (2 sluoksniai)", „Sienų gruntavimas (1 sluoksnis)" :3771). `_consolidate_paint_pozicijos` :2896 (on by default) folds the coats into one display line |
| 1.2 | Angokraščiai (2h + w) × wall thickness | implemented | UR `angokrasciu_gkp_m`, `kampai_opening_reveals_m`, `REVEALS_SCOPE_DEFAULT` :1020 (interior doors off by default); VC „Angokraščių glaistymas-dažymas", „Angokraščių apdirbimas GKP (struktūra)" |
| 1.3 | Glaistymo kampai (outer corners × H) | implemented (with more terms) | UR `kampai_m` = inner + openings + partitions + perimeter + holes + outer, :3227–3255; `ring_corner_counts` :2423; choice `tik_isoriniai` (`scope.py:66`); VC „Dažymo kampų montavimas" :3861 |
| 1.4 | Grindjuostės = perimeter − door widths + 10 % | implemented | UR `SKIRTING_WASTE` :213, `grindjuostes_m` :3363, `_grindjuosciu_duru_m` |
| 1.4 | Lubų perimetras / cornice + 5 % | implemented (only with drawing evidence) | VC `_calc_lubu_karnizas_m` :1448, `CORNICE_LENGTH_WASTE` :1297; UR `KARNIZAS_KEY` :987 |
| 1.5 | Užuolaidų nišos: length = w + 2 × 0,20; area × depth × 3 | partially | length: VC `_calc_nisu_metrai_m` :1469 (fallback width + 0,40 m). Niche area × depth × 3: not found |
| 1.6 | Grindų danga area + pattern waste (8 / 12 / 16 / 12 %) | partially | areas `plyteles_grindys_m2`, `pvc_grindys_m2`, „Parketo / laminato klojimas", `floor_coverings.py:217`. Waste is a fixed `FLOOR_COVERING_WASTE` 1,10 (VC :1293); the pattern factors in `UNIVERSAL_RULES["waste_factors"]` (UR :94) are read only by `tests/test_universal_math.py` |
| 1.7 | Sienų plytelės: tiled length × tile height; bathroom 2,0–2,4 m; kitchen 0,6 m | implemented | `plyteles_sienos_m2`, UR `resolve_wall_tile_read` :2235, `tile_calculator.calculate_room_tile_area`, `bathroom_tile_height_m` 2,0, `ROOM_TYPE_RULES["virtuve"]` 0,6 m × counter 3,0 m (:344); VC `TILE_WASTE` :1286 |
| 1.8 | Gipskartonis sheets ⌈area / 3,0⌉ × 1,10; walls 12,5 / ceilings 9,5; screws, compound, bead; tikslus vs praktinis | partially | UR `gkp_sheet_count` :216 (`GKP_SHEET_WASTE` :209), VC `build_gkp_pozicijos` :1980 (separate wall and ceiling lines with thickness), `GKP_SCREWS_PER_M2`, „GKP siūlių glaistymas + armavimo juostelė". Tikslus/praktinis exists only in main `_calculate_finishing_quantities` :3407; its only caller, `_merge_interior_results` :3764, has no caller (grep) |
| 1.9 | Tapetai rolls = ⌈area / usable per roll⌉ | missing | only the constant `wallpaper_roll_usable_area_m2` (UR :106); no rolls line found |
| 1.10 | Dažų kiekis = area × coats / coverage, ×1,8 for two coats, rounded to containers | implemented (no container rounding found) | UR `calc_paint_liters` :119; VC `_calc_dazai_liters` :1329 (paint classes :1265); Medžiagos „Dažai … (2 sluoksniai)" |
| 1.11 | Glaistymas kg by Q level; 25 kg bags; Q4 sanding 0,30 h/m² as its own line | implemented (no 25 kg bag count found) | VC `_calc_glaistas_kg` :1315, Q rates and thickness :1244–1249, `putty_q_level` :1300, Medžiagos „Glaistas …", Q4 line :3175, `_Q4_SANDING_HOURS_PER_M2` :1251 |
| 1.12 | Hidroizoliacija: floor + perimeter × 0,30 + shower zone full height; corner tape | implemented | VC `_calc_hidroizoliacija_m2` :1516, `WATERPROOFING_KG_PER_M2`, the line „Hidroizoliacijos įrengimas (paruošimas + 2 sluoksniai + sandarinimo juostelė)" (≈ :4576) |
| 1.13 | Elektros taškai: outlets, switches, data/antenna | partially | VC „Rozetės / jungiklio pajungimas" :4906 from Pass-1 symbol totals (:4894, paid, no positions); data/antenna outlets: not found |
| 1.14 | Santechnikos taškai: toilets, sinks, showers, baths, washing machines; floor and linear drains | partially | VC „Klozeto montavimas" :3605/:4779, „Praustuvės / Plautuvės / Skalbimo mašinos montavimas", „Linijinio latako montavimas" :3611/:4810; `sanitary_fixture_reader.py:181`. Bathtub line and floor drains (trapai): not found |
| 1.15 | LED juostos from the ceiling plan | implemented | VC `refresh_led_metres` :1500 (`nisu_metrai`), „LED juostos pajungimas" :4929; `vision/niche_locator.py` (paid); `niche_inference.py` (estimate, opt-in) |

### 2.2 Waste factors §3 (one row per group)

| Group (CLAUDE.md range) | Status | Implemented where |
|---|---|---|
| Concrete 5–8 % | non-interior, present | main `_calculate_concrete_quantities` :4601 (`total_volume * 1.07`, :4669); the type is hidden from the launch UI |
| Rebar 2–4 % | missing | main concrete calc: `rebar_kg = total_volume * 120`, no waste |
| Bricks / blocks 3–5 % | missing | no masonry calculator found |
| Tiles straight 5–10 % | implemented | VC `TILE_WASTE` 1,08 :1286 (UR `waste_factors["tiles_straight"]` 0,10 is not read) |
| Tiles herringbone 10–15 % | partially (defined, not applied) | UR `waste_factors["tiles_herringbone"]` 0,13, read only by tests |
| Tiles hexagonal 15–17 % | missing | no key; `plyteliu_specifikacija.py:74` knows "šešiakampė" only as a pattern name |
| Drywall 10–15 % | implemented | UR `GKP_SHEET_WASTE` 1,10 :209 (`waste_factors["drywall"]` 0,12 is not read) |
| Paint 5–8 % | partially (defined, not applied) | UR `waste_factors["paint"]` 0,07 is not read; `calc_paint_liters` / `_calc_dazai_liters` have no waste term |
| Insulation EPS/MW 3–5 % | missing | facade calc `izoliacijos_plotas_m2 = A` (main `_calculate_facade_quantities` :4400) |
| Roofing 5–10 % | non-interior, present | main `stogo_danga_m2 = actual_area * 1.10` :4530 |
| Laminate flooring 5–10 % | implemented | VC `FLOOR_COVERING_WASTE` 1,10 :1293 |
| Wallpaper 10–15 % | missing | no wallpaper line |
| Pipe / cable 5–10 % | partially | VC `DUCT_WASTE` 1,05 :1294 for ventilation ducts; no cable or pipe lengths |
| Reinforcement mesh 10–15 % | non-interior, present | main `armavimo_tinklelis_m2 = A * 1.1` :4471 |

The engine has three more waste terms that §3 does not list: skirting +10 % (UR :213), cornice +5 % (VC :1297) and tile plinth +10 % (VC :1296).

### 2.3 Validation checks §6

| # | Check | Status | Implemented where |
|---|---|---|---|
| 1 | Paintable wall 2,5–4 × floor | implemented | SC `check_paintable_wall_to_floor` :86 |
| 2 | Ceiling ≈ floor | implemented | SC `check_ceiling_to_floor` :108 |
| 3 | Baseboard ≈ perimeter − 0,8 m per door | implemented | SC `check_baseboard_perimeter` :136 |
| 4 | Paint ≈ 0,22 l/m² | implemented | SC `check_paint_quantity` :222 |
| 5 | GK sheets = wall area / 3,0 × 1,1 | implemented | SC `check_gk_sheets_math` :248 |
| 6 | Insulation anchors 6–8 / m² | missing | facade calc sets `smeiges_vnt = A * 7` (main :4468); no check |
| 7 | Facade area ≈ perimeter × height − 15–25 % | missing | — |
| 8 | Roof area > plan area if pitched | missing | no check; `_calculate_roof_quantities` (main :4495) applies the slope factor |
| 9 | 100 mm slab on 100 m² = 10 m³ | missing | — |
| 10 | Window reveals ≈ 5 m per standard window | implemented | SC `check_window_reveals` :295 |

SC `run_all_checks` :352 (list `_ALL_CHECKS` :341) feeds `warnings`. It also runs `check_perimeter_geometric_minimum` :187, which is not in §6.

### 2.4 Common estimator mistakes §8

| # | Mistake | Status | Implemented where |
|---|---|---|---|
| 1 | Surface preparation (gruntas, glaistymas) as separate items | implemented | VC lines „Sienų gruntavimas (1 sluoksnis)" :3771, „Sienų pirminis glaistymas Q1" :3758, antrinis Q2, the same for ceilings |
| 2 | Primer separate from paint | implemented | gruntavimas lines; Medžiagos „Gruntas"; VC `PRIMER_COVERAGE_M2_PER_L` :1276 |
| 3 | Waterproofing in wet rooms | implemented | VC `_calc_hidroizoliacija_m2` :1516 |
| 4 | Wrong PDF scale; always verify | implemented | measured scale `plan_dimensions.read_dimension_strings` :530; `scale_validator.validate_scale_by_doors` :105 (paid pipe); „Patikrinti mastelį" (v2 W6) |
| 5 | The same wall counted from both sides | partially | doors counted once: UR `mark_shared_doors` :1098; no wall-level guard found |
| 6 | Deformation joints in long walls | partially | reminder `deformacine_siule` (main :4094) sits in `_merge_interior_results`, which has no caller (grep) |
| 7 | Corner bead, sealing tapes, edge profiles | implemented | „Dažymo kampų montavimas" + VC `CORNER_BEAD_M_PER_M` :1278; „GKP siūlių glaistymas + armavimo juostelė"; GKP UW profiles; tape inside the hidroizoliacija line |
| 8 | Different ceiling heights per room | implemented | VC `_apply_per_room_heights` :2037; `height_markers.py:856`; separate lines above 3 m |
| 9 | Fire-rated assemblies | missing | none found (`gaisro_davikliai` in main :4124 is a smoke-detector reminder in the same function with no caller) |
| 10 | MEP penetration sealing (firestops) | missing | none found |
| 11 | Ceiling 9,5 mm and wall 12,5 mm drywall mixed in one total | implemented | VC `build_gkp_pozicijos` :1980 (separate lines) |
| 12 | Sanding labour skipped | implemented | VC „Sienų šlifavimas" :3768, „Lubų šlifavimas" :3815, Q4 line :3175 |
| 13 | Touch-up buffer too low on rough walls (10–20 %) | partially | VC paint class 3 "rough textured walls" profile :1263–1270; no separate buffer found |
| 14 | Metal bead only on outside corners, paper tape inside | partially | inner partition corners are counted by default (UR comment :3207–3213); option `tik_isoriniai` (`scope.py:66`, UR :540) |
| — | "The app should WARN about these" | partially | reminder list `perspejimani` (main :4058–4124) sits in a function with no caller; `ExportDropdown.jsx:52` renders it when present |

**Rows marked missing:** 1.1 furniture zones · 1.9 wallpaper rolls · waste: rebar, bricks/blocks, tiles hexagonal, insulation, wallpaper · checks 6, 7, 8, 9 (all non-interior types) · mistakes 9 (fire-rated), 10 (firestops).

---

## 3. Market readiness beyond features (facts, with citations)

| Area | Status | Facts and citations |
|---|---|---|
| Billing | built, off | One switch, `BILLING_ENABLED` (must be exactly "1"; `backend/billing/flag.py`). RUNBOOK "Decisions deferred to launch day": "already built but dormant … keep it off for beta". Design §1: billing surfaces are a non-goal for v3. Open audit items: backend-security-7 (one-off credit granted on `checkout.session.completed` without a `payment_status` check; grep finds no `payment_status` in `api/billing_v2.py` today) and -8 (invoice VAT rule, `billing/invoice.py:13–15`, accountant to confirm) |
| Auth | live, gaps | Email + bcrypt sessions; Google OAuth switches on only when `GOOGLE_CLIENT_ID/SECRET` are set (`main.py:1102–1106`). Forgot password is a mailto link because there is no email service (`frontend/src/pages/Login.jsx:133–139`; RUNBOOK: the email service is deferred). Account deletion shipped in 01080ce (2026-10-05). Admin allowlist via `SAMATU_ADMIN_EMAIL`, otherwise the first user becomes admin (`main.py:917–925`; RUNBOOK §4 "SET THIS"). Open: -6 (admin by email match on register), -9 (no `email_verified` anywhere in the backend), -12, -18 |
| Security fixes from the 2026-09-29 audit | 4 fixed, 1 partial, 4 still in the code, 12 unknown (21 backend-security findings, full-audit §Security) | **Fixed** per docs and commits: -2 project delete purges the stored drawing (6bcb622; side stores left, week1-fixes "Privacy and deletion"), -3 path traversal via `klass` (6bcb622), -13 F2/F3 answer 404 (b1d4678), -20 lockfile (3532991, install from the lock f85b218). **Partial**: -1 phantom reservations removed and failed runs metered (cb4a820, 374f5cb), but the € cap is an env value the founder sets, and it defaults to 0 = off (`main.py:126`). **Still present by grep**: -7 (above), -9 (above), -14 architect legend routes (`api/legends.py:141,156`), -21 `stored_at` path returned (`api/calibrate.py:274`). **Unknown** (no fix documented, not checked): -4, -5, -6, -8, -10, -11, -12, -15, -16, -17, -18, -19 |
| Money correctness | three money bugs fixed, two open | Fixed: putty Q level reverting (c4e6f38), template line priced at the first row's price and PVM chosen by an AI label (73b9e3b; week1-fixes "Exports"). Open: the Settings PVM rate (21/9/0 %) does not reach `/generate-pdf` or `/generate-excel`, which hard-code 21 % (week1-fixes "Not covered"); the price-list reader („15 €/m2" read as 152) is deferred (week1-fixes "Deferred") |
| Export quality | Excel and PDF live | Excel with „Grupuoti pagal", preview and an optional „Kodas" column; „PDF su žymėjimais" with a legend (v2 W8, W9); the contractor template layout (`samata_template.py`). F2/F3 are backend-only by founder choice (CLAUDE.md "F2/F3 export"). Open: grouped exports carry a „Kaip gauta" column; the founder decides whether client exports keep it (v2 known follow-ups) |
| Onboarding | partial | `SetupWizard.jsx`, `OnboardingTooltips.jsx`, `ViewerCoachMarks.jsx`, the „?" shortcuts guide with PDF (v2 W4). Open: the coach mark renders above drawers and dialogs and cannot be dismissed (v2 follow-up W4); no processing-time education (Table 1 #34); no help centre (#173) |
| Legal pages | pages exist, review unknown | `frontend/src/pages/Privacy.jsx`, `Terms.jsx`, `Cookies.jsx`; Privacy §5 rewritten to match account deletion and backups (d0eaa13, 2026-10-06). Backup retention is unset by design until the founder chooses (RUNBOOK §4 `SAMATU_BACKUP_KEEP_DAYS`). Legal review by a lawyer: unknown |
| Performance and limits | measured | PDF ≤ 200 MB (`main.py:26`), Vision ≤ 100 pages (`main.py:24`). A paid read takes 25–28 min and costs €2–4 per project (v3 programme "Paid runs log"); the audit measured 12–34 min and €3,30–5,68 per extraction (full-audit "Measured numbers"). Hourly cap 20 extracts per user (`main.py:127`). `/recompute-interior` has no rate limit (week1-fixes "Risks"). The €0 detect-run reads a sheet in the background (v2 W3) |
| Accuracy evidence | measured, one contractor | Gate baseline (togal-v2 @ bad14b7): billed lines 22,60 %, rows within ±10 % 26,1 %, € share 34,7 % (v2 programme "Baseline"). Ground truth is still mostly AI-seeded (CLAUDE.md "Open / next"); every truth file comes from one contractor (full-audit verdict 7) |
| Production deploy | prod is behind; nothing from v2/v3 deployed | Hosting: `app.pathon.eu` → Vercel, `api.pathon.eu` → Railway (`docs/2026-05-07-launch-status.md:12–13`). SQLite on a volume, R2 required for PDFs and backups (RUNBOOK §2a, §2b, §4). The local `origin/main` ref is a68a56b (2026-10-07); `togal-v2` is 182 commits ahead; "Nothing is pushed or deployed" (v3 programme header). CI exists (3532991), but "Wait for CI" on Railway and Vercel, the required checks and the accuracy gate in CI are founder actions or decisions (batches-a-b "Actions only the founder can take") |
| Confidentiality | open item | Commit bad14b7 carries a denylisted term in its message; decide before any publication (v2 programme "Things to know"). Fixture PDFs are untracked; one tracked PDF was untracked but remains in git history (week1-fixes "Actions") |

---

## 4. UNPLANNED rows, grouped

### 4.1 Should be planned: the research says copy or adapt, and no v3 task holds it

8 header sheet badge + pager · 11 zones used by the viewer (hover outline, title-block click is never a room) · 12 room location from zones instead of the 0,88 cut · 34 processing-time education · 39 room type/name suggestion chips · 62 legend/table/title-block matches create no count marks · 72 Vision legend fallback for raster legends (paid, OK per run) · 73 surface the floor-covering legend lines · 90 double-click a room to edit its outline · 91 vertex pop-up (Ištrinti · Iškirpti angą) · 92 edge drag moves a segment · 97 one-click negative inside an outline · 100 box (marquee) selection · 106 hold Ctrl to jump to the snap target · 115 count type picked beside the cursor · 141 drawing opacity / „Išvalyti foną" · 152 zoom cluster bottom-right · 162 compact confirm box · 209 `.dark` / `dark:` / `[hsl(var())]` codemod (decided, no track) · 213 Sąmata row actions into a ⋯ menu · 215 sticky evidence pane + room picker on the room sheet · 216 Projektai as status rows · 217 Enter accepts a Patikra proposal · 218 right-click → find similar, linked to the row · 220 Kiekiai Σ adds unlike work types

The design names five more items that have no task line: the run-progress pill restyle (#29, design §4G), openings editable on the drawing (width, kind; design §4D), `zonos` in the `freeReread.js` merge (manager decision log, "wave 2 must add"), the DetectRunButton scale gate (#25, v2 follow-up), and focus scrolling to the room rather than the page (#132, v2 follow-up).

### 4.2 Should be decided: no verdict in the research, so the manager decides

1 page split and naming before upload · 2 DWG/image input and multi-file projects · 9 PageUp/PageDown · 16 map/site takeoff · 22 "Enter number" / "No scale needed" · 23 paper-size scale lists · 27 several scales on one sheet · 33 "what the AI can read" before the first run · 44 area variants (GIA, NIA …) · 45 shared-wall dominance split · 46 neighbours updated after a vertex edit · 48 wall types and wall-type schedules · 56 more snap modes · 64 reusable earlier searches · 65 hatch/pattern search · 74 page type "legend" in Pass-1 · 75 a reader for the training crops · 76 cluster results by size/look · 77 find similar areas / select like · 78 text hits into a count · 83 free re-read also reads figures and heights · 86 count schedule tags on the plan · 87 table to spreadsheet · 88 the Vision schedule extractor · 93 multi-vertex select and delete · 101 arcs, shapes, rotate, group, polyline operations · 102 clipboard / duplicate / nudge · 104 typed length/angle input · 111 full-screen crosshair · 112 cursor priority rules · 114 count mark shapes and trace · 116 one-click line · 117 magic wand / dropper · 126 folders, drag and drop, inline rename · 127 filters by origin, page, colour · 130 spreadsheet report pane · 131 Measurements Manager on M · 133 empty-panel start screen · 142 names/dimensions on the drawing · 143 three-state visibility icons · 144 blueprint grid · 145 ✨ AI badges (the verdicts conflict) · 168 too-many-measurements warning · 169 offline banner · 170 rating prompt after AI runs · 173 help centre / academy / What's new · 178 right/middle-mouse pan, zoom keys · 179 markup / redlines · 180 annotations (stickers, comments, callouts) · 181 Labs tools (carpet seams …) · 186 draw-log export · 188 breakdowns · 193 integrations / API · 195 price points · 201 detection from a typed prompt · 202 published accuracy against labelled ground truth · 203 "Fix with AI" / 👎 per contour · 222 account page name (founder)

### 4.3 Deliberately skipped (reason)

7 page tab cards: Pathon's left rail is better (KE§11) · 98 the 0,001 cm split gap: only if splits are stored as geometry (TE§10) · 103 repeating groups: feature breadth (design §1) · 135 rainbow palettes: "childish"; colour by meaning (KE§11, design §1) · 146 category cards and tag pills: superseded by dense rows and plain words (W1-C) · 148 dark theme and tones: professional feel comes from grammar, not dark chrome (KE§11) · 149 `invert()` dark mode (TE§10) · 153 three-row top chrome: superseded by the one-frame design (§3/§6) · 156 3D view and split panes: no takeoff value (design §1, CD§3.4) · 157 Bluebeam tool chest and menu bar (CD§3) · 194 billing, trials and upsell dialogs: revisit with the payment wall (KE§11, design §1) · 199 collaboration and per-person views: until the core is done (design §1, §9.5) · 200 Caddie agent and Spot voice copilot: non-goal (design §1, §8) · 204 AI confidence slider: confidence is not the primary signal (KE§11, founder)

### 4.4 v2 follow-ups that no v3 task carries (from the v2 merge log, not research rows)

Lines of written dimension strings 4–6 % longer than written on objektas_h sheet 1 (backend manager to look) · a project opening on page 2 jumps back for about 12 s · two things called „Kiekiai" (the tab and the priced-lines section) · chat history resets on reload · „Teisinga" on a row reachable only in the template layout · founder decision on the corner rule from outlines / kampai default (experiment numbers in the v2 programme).

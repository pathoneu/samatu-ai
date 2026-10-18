# Pathon v3 — Waves 5–7 plan: every unplanned coverage row gets a home

> Each worker executes one track; the manager reviews, gates and merges. Binding: `docs/superpowers/plans/2026-10-18-pathon-v3-program.md` (non-negotiables), `docs/superpowers/specs/2026-10-18-pathon-v3-design.md` §4–§6, and the coverage matrix `docs/superpowers/plans/2026-10-18-pathon-v3-coverage.md`.
>
> Row ids in brackets let the matrix be regenerated: `[#n]` = coverage Table 1 row · `[T2-…]` = a Table 2 item · `[F-…]` = a v2 follow-up (coverage §4.4) · `[D-…]` = a design item without a task (coverage §4.1) · `[W0-A-n]` = a bug the W0-A smoke run found.
>
> €0 by default. A paid call at use time runs only behind a flag and a per-run founder OK. Nothing is learned from the contractor's sąmata.

**Homing rules (manager, 2026-10-18)**

| Decision | When it applies |
|---|---|
| PLAN | Any one holds: it cuts clicks for a common interior act; it adds reading accuracy or evidence beside a number; both Togal and Kreo have it; it is €0 at use time |
| CONDITIONAL | It needs a paid model call at use time |
| SKIP | It is outside interior finishing (hidden types stay hidden), US-format specific, decoration, a chat/agent feature beyond Pokalbis, or a parity-only marketing feature |
| FOUNDER DECISION | Multi-user, roles, collaboration, the pro-layer switch |

**Engine rule.** Table 2 gaps become INPUT or REMINDER tasks. Any edit to `universal_rules.py`, `vision_call.py`, `line_items.py` or a lane is written by the worker and approved by the manager under the "measured" protocol (the manager never edits code — the founder's rule):
- behind a flag, default off;
- four eval passes (`--totals-only` and `--rows`, each with `--recompute --gate`, plus the `--replay-geometry` pair);
- deltas reported per codename;
- the manager decides.

**Order**
- **W1-F:** right after W1-D merges.
- **W5-A and W5-B:** after W1-B and W1-D. Both touch `TakeoffViewer.jsx`. W5-A owns tool and gesture code, W5-B owns the chrome; whichever starts second rebases on the first.
- **W5-C:** after W1-B (it needs the cursor hint and the pill).
- **W5-D:** after W2-A, W2-B and W3-A, because it closes their gaps.
- **W5-E:** reminders E8–E10 start at once; inputs E1–E7 start after W2-A and W3-A.
- **W6-A:** last; its codemod spans many files.
- **W7-A:** security items start at once; billing, email and deploy follow the founder's OK.

---

## Track W1-F — Merge bugs from the smoke run (`v3/merge-bugs`, 8133 / 5213) — after W1-D merges

**Files**
- Frontend: `frontend/src/components/project/WorkspacePanel.jsx` (room-list header total), `ProjectMainView.jsx` („Patalpų suvestinė"), `components/viewer/quantities/QuantitiesPanel.jsx` (Σ footer), `lib/projectStore.js`.
- Backend: `api/room_outline.py` (merge route ≈ :438, key loop ≈ :519) and `extractor/sanity_checks.py` (`_sum_field` :72). `extractor/` is the manager's: the worker writes the diff and its test, and the manager approves.

**Tasks**
- [ ] **F1** [W0-A-1] After „Sujungti" 04 → 05, the absorbed room's floor is counted twice outside the billed lines: the header and „Patalpų suvestinė" read 178,77 m² (35,50 twice) while billed lubos stay 143,27. The server's „Lubų plotas 0,80× grindų ploto" and „Dažomas sienų plotas 1,72×" are computed on the same doubled sum.
  - Fix: every summary and `_sum_field` skips rooms where `scope.is_absorbed` (:300) holds, because the kept room already bills both printed areas.
  - Test: the floor total is the same before and after the merge, and neither false check fires.
- [ ] **F2** [W0-A-2] The merge drops the kept room's floor covering read from the drawing („plytelės" → „—", and Patikra asks again).
  - Fix: `grindu_danga` and `grindu_danga_saltinis` of the kept room survive the merge. When the two coverings differ, the existing finishes warning stays.
  - Test: an API test, plus Patikra does not re-ask.
- [ ] **F3** [#220] With no filter, the Kiekiai footer shows Σ per unit and work family, never one number across unlike work. Unit test.
- [ ] **F4** [W0-A-4] Stale localStorage: once, the browser showed the merged state after a server restore.
  - Fix: on load, compare the cached blob's revision with the server's; if the server's is newer, take the server copy and say „Atnaujinta iš serverio". The alternative is to document why the write-through cache cannot drift.
  - Test: e2e — restore a version, reload, and the server state is shown.
- [ ] **F5** Verify:
  - W0-A smoke green, plus a merge-then-totals assertion.
  - Eval gate identical; quote both lines (the bug lives in demo state, not in the corpus).
  - Units, lint, build, and the touched backend tests.

## Track W5-A — Editing gestures (`v3/edit-gestures`, 8134 / 5214)

**Files**
- Frontend: `TakeoffViewer.jsx` (click routing only), `OutlineEditLayer.jsx`, `MeasureLayer.jsx`, `hooks/useOutlineTool.js`, `lib/viewerShortcuts.js`, `lib/drawingSnap.js`, `CountLegendPanel.jsx`, `SymbolReviewPanel.jsx`.
- New frontend: `VertexPopover.jsx`, `CountTypePicker.jsx`, `OpeningPopover.jsx`, `lib/cursors.js`.
- Backend: `api/room_outline.py` (hole from a click, opening edit), plus tests.

**Tasks**
- [ ] **A1** [#90] Double-click a room → „Taisyti kontūrą" (same as key E). Double-click a measurement → edit its points.
- [ ] **A2** [#91] Vertex pop-up with icon + text: „Ištrinti" · „Iškirpti angą". On an outline edge, „Iškirpti angą" adds a user opening through the existing one-click add path; on a perimeter or wall measurement it cuts the doorway gap. Undo in the toast; never hover-only.
- [ ] **A3** Vertex editing:
  - [#92] dragging an edge moves both of its vertices, with wall snap at both ends;
  - [#93] select several vertices (marquee or Ctrl-click) and press Delete; a ring is never reduced below a triangle.
- [ ] **A4** [#97] One-click negative: in „Atimti" (X), a click inside an outline on a closed drawn shape (column, shaft) proposes that shape as the hole, taken from `pdf_vectors.wall_fills`. Preview, then Enter. „Kas atimama?" keeps the kolona default.
- [ ] **A5** Selection:
  - [#100] box selection: left→right selects whole shapes, right→left selects touched ones; works for rooms, marks and measurements;
  - [#77] „Pažymėti panašias" in the selection bar selects the rooms with the same type or finish.
- [ ] **A6** Snapping and cursors:
  - [#106] hold Ctrl to jump to the snap target;
  - [#56] snap to midpoints and intersections of drawing lines, plus an alignment guide to existing vertices; the status line names the snap kind;
  - [#112] one cursor table in `lib/cursors.js`.
- [ ] **A7** Counts:
  - [#115] a count-type picker beside the cursor (list + „Naujas tipas", Enter);
  - [#114] every count type also gets a shape, so meaning never rides on colour alone; a second click on the same spot is ignored.
- [ ] **A8** [#218] Right-click a symbol → „Rasti panašius" with the template box already drawn. The created count is linked to its sąmata row (W2-B's row link).
- [ ] **A9** [D-openings] Openings are editable on the drawing: click an opening mark → a popover with width and kind (langas / durys / praėjimas). It saves like the room sheet's opening edit (`USER_OPENINGS_KEY`), with Undo.
- [ ] **A10** [#46] After an outline save, measure on objektas_h and objektas_g whether any neighbour's `_angos_sienose` changes. If one does, re-read that neighbour's walls in the same save; otherwise report "none". Measured if a key moves.
- [ ] **A11** Drawing:
  - [#101] a rectangle (2 clicks) and an arc segment in Plotas and Perimetras; rotate, flip, group and polyline operations are not built (CAD parity);
  - [#104] typing digits + Enter while drawing fixes the segment's length;
  - [#102] Ctrl+C / Ctrl+V copy a measurement to another sheet, Ctrl+D duplicates, arrow keys nudge a selected vertex (Shift = 10).
- [ ] **A12** [#116] Click a wall face (walls layer) → its length as a distance measurement.
- [ ] **A13** Verify:
  - units (no duplicate shortcut, cursor table, snap kinds);
  - e2e per gesture on demo-objektas_h, with click counts against design §2 T1 (fix a vertex 2+n; subtract a column 3);
  - eval gate identical (the routes save the same keys); screenshots.

## Track W5-B — Viewer chrome and zones in the viewer (`v3/viewer-chrome`, 8135 / 5215)

**Files**
- Frontend: `TakeoffViewer.jsx` (header, pager, zoom), `ScaleChip.jsx` (from W1-D), `SheetRail.jsx`, `DetectRunButton.jsx`, `WorkspacePanel.jsx` (Matavimai), `lib/viewerShortcuts.js`.
- New frontend: `SheetHeaderBadge.jsx`, `ZoomCluster.jsx`, `ViewSettingsPopover.jsx`, `components/ui/ConfirmBox.jsx`.
- Backend: `extractor/room_locator.py` (B3 only), plus tests.

**Tasks**
- [ ] **B1** [#8] The header shows the sheet badge (its number), the name and „← 1 iš N →". [#9] PageUp / PageDown change sheets.
- [ ] **B2** [#11] Only if W1-D's report says this is still open:
  - zone outline and name on hover („Legenda", „Lentelė", „Antspaudas"), with a toggle „Rodyti sritis";
  - a click in `antspaudas` or `pastabos` never selects or creates a room, and the cursor sentence says why.
- [ ] **B3** [#12] `room_locator.py` uses `planas` zones instead of the fixed 0,88 cut. Measured (flag `SAMATU_ROOMS_BY_ZONES=0`).
- [ ] **B4** View settings popover:
  - [#141] drawing opacity, „Išvalyti foną" (brightness threshold), „Nespalvotai";
  - [#142] labels on/off (names, dimensions), with the same switch in „PDF su žymėjimais";
  - [#111] full-screen crosshair.
  - #140 (polygon opacity, line width) lives in the same popover behind the pro-layer switch; the founder decides.
- [ ] **B5** [#152] Zoom cluster bottom-right: fit, +, −, area zoom, minimap, full screen. [#178] Middle mouse pans; keys + / − / 0 zoom.
- [ ] **B6** [#162] One 300 px confirm box with a consequence sentence for destructive acts (delete a row or a measurement, restore a version). It replaces the viewer's ad-hoc dialogs.
- [ ] **B7** Follow-ups:
  - [#25-gate] the DetectRunButton on a sheet without a scale shows „Nustatyti mastelį" and opens the chip; no silent run;
  - [#132-focus] focusing a room zooms to the room, not to its page;
  - [F-page2] a project that opens on page 2 no longer jumps back after about 12 s.
- [ ] **B8** [#22, #23] The scale popover accepts a typed 1:N, offers the standard list with the sheet size (from the page size), and has „Šiam lapui mastelio nereikia" for schedules and specifications. The measured check stays.
- [ ] **B9** [#1] The sheet rail gets „Neskaityti šio lapo": the sheet is skipped by the free re-read and detect-run but stays in the PDF; Undo in the toast. No pre-upload step is added.
- [ ] **B10** Matavimai:
  - [#126] named groups, inline rename (double-click), drag a measurement into a group;
  - [#127] filters „rasta automatiškai / jūsų", „šis lapas", tipas.
- [ ] **B11** Verify:
  - units;
  - e2e: pager, PageDown, zone hover on the objektas_h legend, confirm box, focus zoom;
  - screenshots at 1440 and 1280;
  - eval gate identical (B3 measured on its own).

## Track W5-C — Guidance and feedback (`v3/guidance`, 8136 / 5216)

**Files**
- Frontend: `pages/InteriorProject.jsx`, `pages/PatikraQuestions.jsx`, `pages/RoomSheet.jsx`, `components/project/ProjectMainView.jsx`, `pages/Dashboard.jsx`, `components/viewer/DetectRunProgress.jsx`, ModePill (from W1-B), `i18n/lt.json`.
- New frontend: `RunTeaching.jsx`, `RoomNameChips.jsx`, `DrawingNoteLayer.jsx`.
- Backend: a chat-history route (owner-gated), plus tests.

**Tasks**
- [ ] **C1** [#34] A „Kol skaitoma" panel during the paid read. It shows the stage being read now, what to check afterwards (Patikra), the time (25–28 min), and that the tab can be closed safely. It comes from the existing SSE stages; no new paid call.
- [ ] **C2** [#33] Before the first run, one dismissible card „Ką programa perskaito / ko neperskaito": interior plans yes; facades and roofs no; raster scans are slower and less certain. It never blocks.
- [ ] **C3** [#39] When a room is outlined without a table row, chips appear from the text under the outline: „Ar tai virtuvė? [Taip] [Kita…]". A proposal, one click.
- [ ] **C4** [#217] In Patikra, Enter accepts the proposal and moves to the next question; Esc returns to the list.
- [ ] **C5** [#29-pill] Run progress restyled as the bottom pill; stage names and ✓/●/✕ reasons stay. [#169] A lost-connection notice with „Bandyti dar kartą"; nothing fails silently.
- [ ] **C6** [#216] Projektai as status rows: name, state, last change, totals, next step. Fix the mono gap inside numbers.
- [ ] **C7** [#215] Room sheet: a sticky evidence pane, a room picker (list with state), and digits typed straight into the focused fact.
- [ ] **C8** [#213] Sąmata row delete moves into a ⋯ menu (the 6 s Undo stays); price-source dots become words („iš kainyno").
- [ ] **C9** [#133] Empty states say what to do next (no measurements, no rooms, no legend).
- [ ] **C10** [#170, #203] 👍/👎 plus one optional line:
  - offered after a paid read and on found items; recorded in the corrections journal (`record-decision`, source `ivertinimas`);
  - 👎 on a found symbol means „neieškoti tokių" and becomes a negative example for the next search;
  - no paid "Fix with AI".
- [ ] **C11** [#179, #180] Note pins on the drawing („Pastaba" with text), listed in Matavimai and printed in „PDF su žymėjimais". No sticker or redline toolset.
- [ ] **C12** Follow-ups:
  - [F-kiekiai-name] two things are called „Kiekiai": propose one name for each (LT copy polished by the founder);
  - [F-chat-history] Pokalbis keeps its history per project across reloads;
  - [F-teisinga] „Teisinga" is reachable in the default layout.
- [ ] **C13** Verify: units; e2e (Enter in Patikra, chips, room picker, ⋯ menu Undo); banned-word guard; screenshots.

## Track W5-D — Reading completeness (`v3/reading-completeness`, 8137 / 5217) — after W2-A, W2-B, W3-A

**Files**
- Backend: `extractor/geometry_lane.py` (:293), `floor_coverings.py`, `sheet_zones.py`, `legend_rows.py` (from W2-A), `vector_symbols.py`, `cv_match.py`, `plan_dimensions.py`, `table_reader.py` (from W3-A), `plan_area_annotations.py`, `api/free_reread.py`, `api/detect_run.py`; conditional only: `legend_injection.py`, `vision/schedule_extractor.py`; `main.py` (upload, D14 only).
- Frontend: `lib/freeReread.js`, the review panels; plus tests.

**Tasks**
- [ ] **D1** [#73] Keep `floor_coverings.legenda` (thrown away today at `geometry_lane.py:293`) in `_meta.grindu_legenda`, and show it on the floor fact with its crop („Legenda: plytelės — mėlyna"). LANE_VERSION stays unless a room key changes.
- [ ] **D2** [#62] Only if W2-A's report says it is not done: count matches inside `legenda`, `lentele` and `antspaudas` zones are listed but create no marks.
- [ ] **D3** [D-zonos] Only if W2-B does not do it: `freeReread.js` merges `zonos` into stored projects.
- [ ] **D4** [#72] CONDITIONAL: the Vision legend reader (`legend_injection.extract_legend`, role `legend`) on a raster legend box the user drew.
  - Behind flag `SAMATU_VISION_LEGEND=0` and a per-run OK dialog that names the cost.
  - Results go through the same review-before-create.
- [ ] **D5** [#88] CONDITIONAL: the Vision schedule reader for raster schedules, with the same flag and OK pattern. The deterministic reader stays first.
- [ ] **D6** [#83] The free re-read and detect-run also read the designer's figures (`read_author_figures`) and height markers. Measured.
- [ ] **D7** [#27] One scale per `planas` zone when a sheet carries two viewports whose dimension strings give different scales. Measured.
- [ ] **D8** [F-dimlen] Dimension-string lines on objektas_h sheet 1 come out 4–6 % longer than written. Establish with numbers whether `line_pct` includes the tick marks; fix only with the manager's OK (measured).
- [ ] **D9** [#48] Wall and partition types (GK pertvaros tipas from a legend or tags) become a room fact with its crop. A fact only; no formula.
- [ ] **D10** After W3-A:
  - [#86] the schedule's tags counted on the plan (door codes D1…) against the schedule rows become a reconciliation question;
  - [#87] „Eksportuoti lentelę" sends a read table to Excel.
- [ ] **D11** Search and grouping:
  - [#64] earlier searches are saved as count types and reused on other sheets;
  - [#65] hatch search: box a hatch → areas with the same colour and pattern (the `floor_coverings` machinery) → floor-covering proposals;
  - [#78] text-search hits can become a count;
  - [#76] found openings and counts are grouped by size in Kiekiai („Durys 900 × 2100 — 7").
- [ ] **D12** [#74] A sheet whose only zone is a legend gets type „legenda" in the €0 sheet classification. No paid prompt change.
- [ ] **D13** [#44] A project area summary: room-table total · outlines total · plan footprint, each with its source sentence. No new formula.
- [ ] **D14** [#2] Intake:
  - several PDFs go into one project (pages appended, sheets named after their file);
  - PNG/JPEG/TIFF pages are wrapped as PDF with the existing libraries;
  - DWG gets a spike only (converter options, licence, size) in a report; a new dependency needs the founder's OK.
- [ ] **D15** Verify:
  - synthetic tests per reader;
  - corpus report scripts (codenames only);
  - eval lines quoted for every lane-touching task;
  - full backend suite.

## Track W5-E — Calculation completeness, interior only (`v3/calc-completeness`, 8138 / 5218)

**Engine rule (repeated).** The worker writes inputs, notices and tests. Engine diffs are written by the worker behind a flag and approved by the manager under the measured protocol above. Formulas come only from CLAUDE.md §1; no factor or default is ever taken from the contractor's sąmata.

**Files**
- New backend: `extractor/reminders.py` (pure, €0), `api/reminders.py` (`GET …/reminders`, owner first), tests.
- Frontend: `RoomSheet.jsx`, `FactRow.jsx` (inputs); the Notice component in Patikra and Sąmata.
- Engine side (worker writes, manager approves): `universal_rules.py`, `vision_call.py`.

**Tasks**
- [ ] **E1** [T2-1.1-furniture, T2-1.1-panel] INPUT: furniture and panel zones per room.
  - Source: a box the user draws on an elevation or plan, or the built-in-furniture text.
  - Output: `_baldu_zonos_m2` and `_plokstes_zonos_m2`, each with its crop.
  - The CLAUDE.md §1.1 deduction is written behind flag `SAMATU_FURNITURE_ZONES=0` and approved by the manager.
- [ ] **E2** [T2-1.9, T2-W-wallpaper] Wallpaper rolls = ⌈area / usable area per roll⌉ (CLAUDE.md §1.9; the constant exists), with §3 waste.
  - Applies to rooms whose finish reads „tapetai"; the input is the tapetai m² already read.
  - Engine edit behind a flag, approved by the manager.
- [ ] **E3** [T2-1.5] INPUT: niche depth (`nisos_gylis_m`) from the ceiling-plan detail, or typed. The term length × depth × 3 is added behind a flag and approved by the manager.
- [ ] **E4** [T2-1.13] Data and TV outlets: the legend rows „Interneto lizdas" and „TV lizdas" (W2-A) get their own sąmata rows through W2-B's count → row path. A blank row with a question appears when the legend has no such row.
- [ ] **E5** [T2-1.14] A bathtub row from the sanitary reader's existing `vonia` count. Floor drains (trapai) come from legend counts (W2-A); no paid prompt change. Both rows are added behind a flag and approved by the manager.
- [ ] **E6** [T2-1.10, T2-1.11] Packaging shown beside the Medžiagos quantity: „N maišų po 25 kg", „N kibirų po 10 l". The container size is a visible assumption in Nustatymai. Kilograms and litres are unchanged.
- [ ] **E7** [T2-1.6, T2-W-herringbone, T2-W-hex, T2-W-paint] Measured:
  - flag `SAMATU_WASTE_BY_PATTERN=0` wires `UNIVERSAL_RULES["waste_factors"]` by the read pattern (tile spec, floor plan) instead of the fixed 1,08 / 1,10;
  - adds the hexagonal key and paint 7 % (CLAUDE.md §3);
  - four eval passes, deltas per codename, manager decides.
- [ ] **E8** [T2-1.8, T2-§8.6, T2-§8.9, T2-§8.10, T2-§8.13, T2-warn] REMINDERS. The dead `_merge_interior_results` list (main.py :4058–4124) returns as Patikra and Sąmata notices, one plain sentence each, never a quantity row:
  - GK „tikslus / praktinis", with both sheet counts in the sentence;
  - deformation joints (a wall longer than 8 m);
  - fire-rated assemblies and firestops: a specific notice when the text layer mentions EI / „ugniai atspari", otherwise one general reminder;
  - a touch-up buffer on rough walls (paint class 3);
  - the old commonly-missed list: hidroizoliacija, gruntas, glaistymas, kampų profiliai, GK sandarinimo juosta, LED transformatoriai, dūmų davikliai.
- [ ] **E9** [T2-§8.5] A Patikra notice when two room outlines overlap (the same floor or wall counted twice), naming both rooms.
- [ ] **E10** [F-kampai, T2-§8.14] A decision sheet for the founder: the kampai default (su vidiniais / tik išoriniai) and the corner-from-outline rule, with the existing experiment numbers per codename. No default changes.
- [ ] **E11** Verify:
  - pytest per input and notice;
  - eval gate identical for E4, E6, E8–E10;
  - measured reports for E1–E3, E5, E7.

## Track W6-A — Look hygiene (`v3/look-hygiene`, 8139 / 5219) — after the wave-5 frontend merges

- [ ] **G1** [#209] Codemod the inert `.dark` block (`index.css:158`), the `dark:` classes (7 files) and the `[hsl(var(--x))]` classes into configured utilities. Screenshot diff before and after.
- [ ] **G2** Replace the remaining palette classes in `InteriorProject.jsx` and `ProjectMainView.jsx` with tokens. [#145, #221] Remove the ✨ still in 9 frontend files.
- [ ] **G3** Room names cut short in the 340 px panel (manager decision → wave 6): screenshot both options, two-line rows or the source once in the header, for the founder.
- [ ] **G4** The look itself (#147 dark frame, any palette change) waits for the founder („set the look later"). Prepare two screenshots and merge nothing.
- [ ] **G5** Verify: `npm run probe:ui` no worse; units, lint, build; W0-A smoke green.

## Track W7-A — Market readiness (`v3/market-readiness`, 8141 / 5221)

Each item has three parts: the fact (coverage §3), the task, how it is verified.

- [ ] **M1** [#194] Billing switch-on checklist.
  - Fact: billing is built and off; audit -7: no `payment_status` check; audit -8: the invoice VAT rule is unconfirmed.
  - Task: grant and invoice only when `payment_status == 'paid'`, plus handling for async succeeded / failed; tier gates and limit messages in plain Lithuanian (no upsell dialogs); the DEVELOPING pre-flight as a script.
  - Verify: webhook tests with paid and unpaid sessions; the flag stays off.
- [ ] **M2** Email service.
  - Fact: none exists; forgot password is a mailto link; audit -9: no `email_verified` check.
  - Task: the founder picks the provider; then verification email, password reset, and OAuth requiring `email_verified`.
  - Verify: tests.
- [ ] **M3** Security -14 and -21, plus a re-audit.
  - Facts: the architect legend routes are global (`api/legends.py:141,156`) and must be scoped per owner before W2-B B4 reuses them — **-14 is fixed in W2-A** (it already edits `api/legends.py`; M3 only verifies it); `stored_at` is returned at `api/calibrate.py:274`.
  - Task: fix both; re-audit the 12 unknowns (-4, -5, -6, -8, -10, -11, -12, -15, -16, -17, -18, -19) with a fixed / still-open line each.
  - Verify: ownership-policy test and new tests.
- [ ] **M4** PVM.
  - Fact: the Settings rate (21 / 9 / 0 %) never reaches `/generate-excel` or `/generate-pdf`.
  - Task: wire it, and offer an account default.
  - Verify: export tests at all three rates.
- [ ] **M5** [#186, #188] Exports.
  - Task: the internal copy gets a „Pakeitimų žurnalas" sheet; grouping by aukštas / butas is added; whether client exports keep the „Kaip gauta" column is the founder's call.
  - Verify: export tests.
- [ ] **M6** [#173] Help and onboarding.
  - Task: a short „Pagalba" page (how to check a number, fix an outline, what each line style means) and „Kas naujo"; fix the coach mark that sits above dialogs (v2 follow-up W4).
  - Verify: e2e.
- [ ] **M7** [#168] Limits.
  - Task: warn before a sheet holds too many measurements (threshold measured); a rate-limit decision for `/recompute-interior`; the limits written down (200 MB, 100 pages, run time).
  - Verify: test plus doc.
- [ ] **M8** [#75] Data.
  - Task: the symbol training crops are purged with their project or moved under the data dir; backups and R2 checked with `scripts/report_backup_retention.py`; the retention value is the founder's.
  - Verify: report.
- [ ] **M9** [#202] Accuracy claims.
  - Task: public numbers come only from human-confirmed ground truth (`scripts/build_ground_truth.py`), labelled in-sample or out-of-sample.
  - Verify: the copy cites its source.
- [ ] **M10** Deploy plan.
  - Facts: prod is Vercel + Railway, both auto-deploying from `main`; togal-v2 reaches `main` only with the founder's OK.
  - Task: `scripts/safe_deploy_check.sh` before every push; "Wait for CI" and required checks (founder actions); a smoke run on the prod URLs after the deploy.
  - Verify: a written checklist run once on dev.
- [ ] **M11** Legal review of Privacy / Terms / Cookies is a founder action (a lawyer). The worker lists every promise those pages make against the code (deletion, backups, cookies).

## Wave 7 candidates — founder decides (no track)

- [#199] Multi-user, roles, collaboration, per-person views.
- The pro-layer switch and what sits behind it:
  - [#123] isolate;
  - [#125] panel keyboard and multi-select;
  - [#140] polygon opacity and line width;
  - [#143] three-state icons;
  - [#175] live-key shortcut sheet;
  - [#156] two sheets side by side.
- [#147] The dark frame and the look as a whole (W6-A G4 prepares the screenshots).
- [#195] Price points.
- [#222] The account page's name.
- [F-kampai] The kampai default (W5-E E10 prepares the numbers).
- Email provider (M2), backup retention (M8), legal review (M11).

## Wave 5–7 acceptance (manager)

1. Eval gate identical on every merge. Measured flags stay off by default, and each has its delta report per codename.
2. W0-A smoke green, plus each track's e2e. T1 click counts re-measured after W5-A and W5-B.
3. Coverage matrix regenerated from the bracketed ids: no UNPLANNED row without a home.
4. The founder's walk on 5173, with a written guide like the 2026-10-17 one.

---

## Appendix — Row → home

**Totals.** Of the 97 UNPLANNED rows in coverage Table 1: **69 PLAN**, **2 CONDITIONAL**, **22 SKIP**, **4 FOUNDER DECISION**, **0 without a home**. Table 2 and the follow-ups are listed after it.

| Row | Home | Reason |
|---|---|---|
| #1 page split / naming before upload | W5-B B9 | €0; „Neskaityti šio lapo" on the rail instead of a pre-upload step |
| #2 DWG / image input, multi-file projects | W5-D D14 | both competitors have it; DWG is a spike only |
| #7 page tab cards | SKIP | Pathon's left rail with page types is better (KE§11) |
| #8 sheet badge + pager | W5-B B1 | cuts clicks; Togal baseline |
| #9 PageUp / PageDown | W5-B B1 | €0, cuts clicks |
| #11 zones in the viewer | W5-B B2 | design §4A consumer (if W1-D leaves it) |
| #12 room location via zones | W5-B B3 | reading accuracy; measured |
| #16 map / site takeoff | SKIP | outside interior finishing |
| #22 typed scale / no scale needed | W5-B B8 | both have a typed scale |
| #23 standard list by sheet size | W5-B B8 | €0 |
| #27 several scales on one sheet | W5-D D7 | reading accuracy; measured |
| #33 what the AI can read | W5-C C2 | €0 guidance |
| #34 teaching during the paid read | W5-C C1 | PLAN (the run is already paid) |
| #39 room name / type chips | W5-C C3 | cuts clicks; a proposal |
| #44 area variants | W5-D D13 | both have it; summary only, no formula |
| #45 shared-wall dominance split | SKIP | whole-building centreline allocation; finishes are billed per room face |
| #46 neighbours after a vertex edit | W5-A A10 | accuracy; measured first |
| #48 wall / partition types | W5-D D9 | evidence beside a number; a fact only |
| #56 more snap modes | W5-A A6 | both have it |
| #62 no marks inside legend / table / title zones | W5-D D2 | accuracy (if W2-A leaves it) |
| #64 reusable searches | W5-D D11 | cuts clicks |
| #65 hatch search | W5-D D11 | reading accuracy, €0 |
| #72 Vision legend fallback | W5-D D4 — CONDITIONAL | paid call at use time; flag + per-run OK |
| #73 floor-covering legend lines | W5-D D1 | evidence, €0 |
| #74 page type „legenda" | W5-D D12 | €0 from zones, no prompt change |
| #75 training-crop reader | W7-A M8 | data and privacy decision on the crop store |
| #76 group results by size | W5-D D11 | evidence for checking |
| #77 select like | W5-A A5 | cuts clicks |
| #78 text hits into a count | W5-D D11 | cuts clicks, €0 |
| #83 figures and heights in the free re-read | W5-D D6 | accuracy; measured |
| #86 count schedule tags | W5-D D10 | accuracy (Kreo) |
| #87 table to spreadsheet | W5-D D10 | €0 |
| #88 Vision schedule extractor | W5-D D5 — CONDITIONAL | paid call at use time |
| #90 double-click to edit | W5-A A1 | cuts clicks |
| #91 vertex pop-up | W5-A A2 | cuts clicks |
| #92 edge drag | W5-A A3 | cuts clicks |
| #93 multi-vertex delete | W5-A A3 | both have it |
| #97 one-click negative | W5-A A4 | cuts clicks |
| #98 0,001 cm split gap | SKIP | split outlines must keep touching; „Sujungti" needs touching outlines (v2 W5) |
| #100 box selection | W5-A A5 | both have it |
| #101 arcs, shapes, rotate, polylines | W5-A A11 | rectangle + arc only; the rest is CAD parity, not built |
| #102 clipboard / duplicate / nudge | W5-A A11 | both have it |
| #103 repeating groups | SKIP | parity-only (design §1) |
| #104 typed length while drawing | W5-A A11 | €0 |
| #106 Ctrl jumps to snap | W5-A A6 | design §5 |
| #111 full-screen crosshair | W5-B B4 | €0 toggle |
| #112 cursor priority rules | W5-A A6 | one cursor table |
| #114 count mark shapes | W5-A A7 | meaning never by colour alone |
| #115 count type beside the cursor | W5-A A7 | cuts clicks |
| #116 one-click wall length | W5-A A12 | cuts clicks, €0 (walls layer) |
| #117 magic wand / dropper | SKIP | covered by the room tool R and click-to-fill (design §4 keeps the wand dead) |
| #126 folders, inline rename | W5-B B10 | both have it |
| #127 filters by origin / page | W5-B B10 | evidence (rasta automatiškai / jūsų) |
| #130 spreadsheet report pane | SKIP | parity; the Sąmata view is the report, and Excel export covers formulas |
| #131 Measurements Manager on M | SKIP | M is „Sujungti" (design §5); Matavimai already lives in the right panel |
| #133 empty-panel start | W5-C C9 | €0 guidance |
| #135 rainbow palettes | SKIP | decoration |
| #141 drawing opacity / „Išvalyti foną" | W5-B B4 | §4.1 row |
| #142 labels on/off | W5-B B4 | both have it |
| #143 three-state icons | FOUNDER DECISION | pro layer (with #123) |
| #144 blueprint grid | SKIP | decoration |
| #145 ✨ AI badges | SKIP | decoration and a toy trope (PA§6); leftovers removed in W6-A G2 |
| #146 category cards, tag pills | SKIP | decoration, superseded by dense rows (W1-C) |
| #148 dark theme and tones | SKIP | decoration; the look is the founder's (W6-A G4) |
| #149 `invert()` dark mode | SKIP | decoration (TE§10) |
| #152 zoom cluster | W5-B B5 | Kreo baseline, cuts clicks |
| #153 three-row top chrome | SKIP | superseded by the one-frame design (§3/§6) |
| #156 3D, split panes | SKIP | 3D is outside the takeoff value; two sheets side by side → wave 7 candidate |
| #157 Bluebeam density, menu bar | SKIP | parity (CD§3) |
| #162 compact confirm box | W5-B B6 | §4.1 row |
| #168 too-many-measurements warning | W7-A M7 | limits |
| #169 offline banner | W5-C C5 | no silent fail |
| #170 rating after an AI run | W5-C C10 | feeds the corrections journal, €0 |
| #173 help centre / What's new | W7-A M6 | onboarding |
| #178 middle-mouse pan, zoom keys | W5-B B5 | both have it |
| #179 markup / redlines | W5-C C11 | note pins only |
| #180 annotations, comments | W5-C C11 | note pins printed in the PDF |
| #181 Labs tools | SKIP | parity; carpet seams would be a new formula (engine rule); dimensions = #142 |
| #186 draw-log export | W7-A M5 | the change journal goes into the internal Excel copy |
| #188 breakdowns | W7-A M5 | grouping by aukštas / butas |
| #193 integrations / API | SKIP | parity / marketing; Excel, PDF and F2 cover hand-off |
| #194 billing, trials, upsell | W7-A M1 | gates and limit messages only; upsell dialogs skipped |
| #195 price points | FOUNDER DECISION | commercial |
| #199 collaboration, multi-user | FOUNDER DECISION | homing rule |
| #200 Caddie, Spot | SKIP | chat / agent beyond Pokalbis |
| #201 detection from a typed prompt | SKIP | agent-style (design §8); legend marking and find-similar cover it at €0 |
| #202 accuracy against labelled truth | W7-A M9 | honest claims |
| #203 "Fix with AI", 👎 per contour | W5-C C10 | 👎 €0; paid "Fix with AI" skipped (the room tool R is wall-exact at €0) |
| #204 AI confidence slider | SKIP | design §1: confidence sliders are not the primary signal |
| #209 `.dark` / `dark:` codemod | W6-A G1 | §4.1 row |
| #213 Sąmata row ⋯ menu | W5-C C8 | §4.1 row |
| #215 sticky evidence + room picker | W5-C C7 | §4.1 row |
| #216 Projektai as status rows | W5-C C6 | §4.1 row |
| #217 Enter accepts the proposal | W5-C C4 | §4.1 row |
| #218 right-click → find similar | W5-A A8 | §4.1 row |
| #220 Kiekiai Σ across unlike work | W1-F F3 | bug |
| #222 account page name | FOUNDER DECISION | the founder names it |

**Table 2 → home**

| Item | Home |
|---|---|
| T2-1.1 furniture zones (missing); panel zones (partial) | W5-E E1 (INPUT; deduction by the manager behind a flag) |
| T2-1.5 niche area term | W5-E E3 (INPUT + manager flag) |
| T2-1.6 pattern waste; T2-W herringbone, hexagonal, paint | W5-E E7 (measured) |
| T2-1.8 GK tikslus / praktinis | W5-E E8 (notice) |
| T2-1.9 wallpaper rolls; T2-W wallpaper waste | W5-E E2 |
| T2-1.10 paint containers; T2-1.11 25 kg putty bags | W5-E E6 |
| T2-1.13 data / antenna outlets | W5-E E4 |
| T2-1.14 floor drains, bathtub | W5-E E5 |
| T2-§8.5 double counting | W5-E E9 |
| T2-§8.6, §8.9, §8.10, §8.13, the commonly-missed warning list | W5-E E8 (notices, never rows) |
| T2-§8.14 metal bead only outside | W5-E E10 + FOUNDER DECISION (kampai default) |
| T2-W pipe / cable | SKIP: cable and pipe runs are MEP (CLAUDE.md type 10), outside interior; ducts keep 5 % |
| T2-W concrete, rebar, bricks / blocks, insulation, roofing, mesh | SKIP: outside interior; hidden types stay hidden |
| T2-§6 checks 6, 7, 8, 9 | SKIP: facade / roof / concrete checks, outside interior |

**Follow-ups and design items → home**

| Item | Home |
|---|---|
| [W0-A-1] doubled floor total | W1-F F1 |
| [W0-A-2] floor covering lost on merge | W1-F F2 |
| [W0-A-4] stale localStorage | W1-F F4 |
| [W0-A-3] flat „Rasti panašius" scores | W2-A (routed by the manager) |
| [#25-gate] | W5-B B7 |
| [#132-focus] | W5-B B7 |
| [F-page2] | W5-B B7 |
| [#29-pill] | W5-C C5 |
| [F-kiekiai-name] | W5-C C12 |
| [F-chat-history] | W5-C C12 |
| [F-teisinga] | W5-C C12 |
| [D-openings] | W5-A A9 |
| [D-zonos] | W5-D D3 |
| [F-dimlen] | W5-D D8 |
| [F-kampai] | W5-E E10 + FOUNDER DECISION |

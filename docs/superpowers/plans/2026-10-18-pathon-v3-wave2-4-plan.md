# Pathon v3 — Waves 2–4 backend plan: legends and symbol counts, tables, measurements into the sąmata

> Workers execute one track each; the manager reviews, gates and merges. Binding: `docs/superpowers/plans/2026-10-18-pathon-v3-program.md` (non-negotiables), `docs/superpowers/specs/2026-10-18-pathon-v3-design.md` §4 (tracks B, C, F), §5. Facts: `docs/superpowers/research/2026-10-18-backend-reading-inventory.md` (§5, §6, §12 and the Gaps). €0 only; Vision only as a fallback behind a per-run founder OK. The founder reviews nothing until these waves work end to end.

**Order.** W2-A (backend) and W3-A (backend) start as soon as worker slots free; W2-B (UI) starts when W2-A's route exists; W4-A after W1-D is merged (it extends the save/Undo paths). W1-E's zones are an input to W2-A's legend suggestion but not a blocker (fallback: the user's box).

---

## Track W2-A — Legend rows and symbol counting (`v3/legend-count`, 8128 / 5208)

**Files:** create `backend/extractor/legend_rows.py`, `backend/api/legend_count.py`, tests `backend/tests/test_legend_rows.py`, `test_legend_count_api.py`; modify `backend/extractor/vector_symbols.py` (generalise), `backend/extractor/cv_match.py` (batch), `backend/api/legends.py` (store rows), `tests/synthetic_plan.py` (legend block with coloured and black glyphs on two sheets).

- [ ] **A1. Legend rows.** `split_legend_rows(pdf_bytes, page, bbox_pct) -> [{row_id, glyph_bbox_pct, glyph_kind: 'spalvotas'|'juodas'|'tekstas', colour, text, text_bbox_pct}]` from the text layer + vector paths inside the box (pdfplumber frame → display frame via W1-E's `zone_to_mediabox_pt` or the module's own converter; test both). Suggestion input: W1-E's `legenda` zones when present. Raster-only page → `{status: 'be_teksto'}`; never guess.
- [ ] **A2. Vector counter generalised.** `count_legend_symbols(pdf_bytes, label_re, pages)` → `count_glyph_instances(pdf_bytes, template_glyph, pages=None)`: any coloured glyph from a legend row, all plan pages (not 4), instances with `box_pct` (not points), the repeated-sheet rule kept (`kartojasi`). Diffusers keep working through the old entry (regression test with the eye-verified counts H 9 / D 6 / B 20 / G 8 on the untracked fixtures — report only, never asserted in the repo).
- [ ] **A3. Raster batch for black glyphs.** `find_symbol_by_shape` runs server-side over all plan pages for one template box (`batch_find_symbol(project_pdf, template_page, box_pt, pages, min_score)`), dpi budget as today, `skipped: 'raster'` per page, results with score; PDFIUM_LOCK respected; a time cap with a partial result flag.
- [ ] **A4. Route.** `POST /api/projects/{id}/legend/rows` (bbox → rows; ownership first) and `POST …/legend/count` (row_id or template → `{rows: [{row_id, count, instances[{page, box_pct, score|null, saltinis: 'vektoriai'|'rastras'}], sentence_lt}]}`). Nothing is saved by these routes. `api/legends.py` gains `rows` in the project legend (saved only when the UI commits) and the architect promotion keeps working.
- [ ] **A5. Tests + gate.** Synthetic legends (3 rows: coloured square, hairline circle, black cross; instances on two sheets, one sheet a repeat) with exact counts; ownership policy; eval gate lines identical; full suite.

## Track W2-B — „Pažymėti legendą" UI with review-before-create (`v3/legend-ui`, 8129 / 5209)

**Files:** create `frontend/src/components/viewer/LegendTool.jsx`, `LegendReviewPanel.jsx`, `frontend/src/lib/legendApi.js`, `lib/legendReview.js` (+ test); modify the tool rail (key G, from W1-B), `SymbolSearchLayer`/count marks (hollow „rasta automatiškai" style from W1-C), `WorkspacePanel.jsx` Matavimai (counts per legend row), `countTypes` model (a row becomes a count type with `legend_row_id`).

- [ ] **B1. Tool G.** Suggest the legend zone (W1-E `legenda` zone → dashed proposal with „Tai legenda? Taip / Nubrėžti kitaip"), else draw a box. Cursor hint per state.
- [ ] **B2. Review panel.** Rows from A4 with glyph crop (`/evidence`), text, count per page, examples; per row: ✔ (becomes a count type + marks), 🗑, „Kitas pavadinimas"; per instance ✕ on the drawing; one „Sukurti kiekius (N)" button. Nothing exists before it. Accept/reject → `record-decision` + corrections journal (`source: 'legenda'`).
- [ ] **B3. Counts live into rows.** Created counts use the existing `measurement_count` row path but update live (no „Į sąmatą" click): recount → row `kiekis` follows; the row's ledger line says „suskaičiuota pagal legendą: eilutė „…", N ženklai lape 1, M lape 3".
- [ ] **B4. Reuse.** Saved legend offered on the next project of the same architect („Rasta ankstesnio projekto legenda — pritaikyti?"), via `api/legends.py` promote/load.
- [ ] **B5. Verify.** e2e on demo-objektas_h: G → suggestion → accept → rows → create → marks + rows; Undo removes them; journal rows; screenshots.

## Track W3-A — Tables with row bboxes, „lentelės" stage, reconciliation (`v3/tables`, 8130 / 5210)

**Files:** create `backend/extractor/table_reader.py`, `backend/extractor/schedules.py`, tests; modify `door_schedule.py` (cells + bboxes), `free_reread.py` + `detect_run.py` (stage `lenteles`, LANE_VERSION bump only if room keys change — they should not), `project_questions.py` (reconciliation kinds), `room_facts.py` (schedule-backed sentences), `api/evidence.py` (row crops already work by rect).

- [ ] **T1. Generic reader.** `read_tables(pdf_bytes, page) -> [{table_id, bbox_pct, header: [str], rows: [{cells: [str], bbox_pct, cell_bboxes}]}]` on pdfplumber `find_tables` + the eksplikacija's tolerance tricks (continuation pages, merged cells, decimal normalisation reused, not copied).
- [ ] **T2. Schedules.** Header-role maps: `durys` (kodas, plotis, aukštis, tipas, kiekis, pastaba), `langai` (same), `apdailos` (patalpa, grindys, sienos, lubos, grindjuostės), `plyteles` (vieta, formatas, gamintojas). Output per schedule `{rows with values + bbox_pct + page}`; `door_schedule.scan_door_schedule` keeps its contract but is fed by T1 rows and now carries `bbox_pct`.
- [ ] **T3. Stage.** `lenteles` stage in `apply_geometry`'s `on_stage` order after `tekstas`; results under `_meta.lenteles` and `_duru_ziniarastis`/`_langu_ziniarastis`/`_apdailos_lentele` with bboxes; free re-read and detect-run include it; the browser merge keeps user edits.
- [ ] **T4. Reconciliation questions.** `project_questions`: „Durų žiniaraštis sako 7 durų, sienose rasta 5 — kurios teisingos?" (per room list, proposed answer = drawn), „Apdailos lentelė: patalpa 04 grindys — plytelės, plane — laminatas" (proposal = plan), „Legendos suma 202 m² vs skaičiuota 198,4 m²" (information only). Facts get `Rodyti brėžinyje` through the row bbox.
- [ ] **T5. Tests + gate.** Synthetic tables (continuation page, merged header) + objektas_d's real schedule in a report script (codenames only); eval gate identical (no formula input changes; if the schedule anchoring moves a number, STOP and report); full suite.

## Track W4-A — Measurements ↔ sąmata rows, Kiekiai inline edit, „Kas pasikeitė — Atšaukti" (`v3/measure-rows`, 8131 / 5211)

**Files:** `frontend/src/lib/quantityOverride.js`, `lib/quantitiesTree.js`, `WorkspacePanel.jsx` Matavimai, Kiekiai panel, `RereadDiffBanner`→ change banner; backend `/recompute-interior` ledger contribution kind `matavimas` (a measured length/area/count attached to a row id), tests.

- [ ] **M1. Model.** A measurement carries `eilute_id` (row) and `kaip: 'kiekis'|'pridėti'|'atimti'`; the row's `kiekis` = engine value ± measurements, each a ledger line „matavimas 4,20 m (lapas 1)". Manual override semantics unchanged.
- [ ] **M2. UI.** Drag a measurement from Matavimai onto a Kiekiai/Sąmata row, or right-click → „Į eilutę…"; Kiekiai inline edit of the number (double-click, Enter; Tab to the next); the row shows „iš matavimų" chip with the list.
- [ ] **M3. Change banner.** After a lane re-read or AI proposal: „Kas pasikeitė — N eilučių · Peržiūrėti · Atšaukti" (one component, from the existing `_reread_diff`), Undo restores the previous blob through Versijos.
- [ ] **M4. Tests + gate.** node:test for the model, pytest for the ledger kind, e2e drag/edit/undo; eval gate identical (measurements are user input, never a default).

---

## Wave 2–4 acceptance (manager, before the founder is invited)

1. Eval gate identical on the merged head; full backend suite green; W0-A smoke + wave e2e green.
2. T4 on the corpus plan sheets: legend counts within ±1 of hand counts where a legend exists (report per project by codename); schedules read with bboxes on every project that has one.
3. Manager browser walk: mark a legend → counts → rows; open a schedule row's evidence; answer a reconciliation question; drag a length onto a row; undo everything.
4. Only then: the founder's walk on 5173 with a written guide like the 2026-10-17 one.

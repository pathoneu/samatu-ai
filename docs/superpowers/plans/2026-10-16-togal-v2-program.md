# Togal-v2 programme — the whole Togal.AI capability set inside Pathon, interior finishing first

> Founder brief (2026-10-16): "I need every single one, everything that I asked you to reverse engineer. Keep interior finishing only now. Reuse the same PDFs. We're trying to make a million dollar business here: all steps relooked, tests run." Two manager sessions (Fable 5.1) run the programme, Opus 5.5 workers build in isolated worktrees. **Nothing is deployed; the founder reviews on localhost when a wave is done.**

Source of truth for *what Togal does*: `docs/superpowers/research/2026-10-16-togal-pipeline-analysis.md` (§1–§11). Already built: `docs/superpowers/plans/2026-10-16-viewer-drawing-geometry.md` (snap to walls, standard-scale suggestion, walls layer, outline editing, comfort layer).

## Non-negotiables (every worker, every task)

1. **Read first:** `CLAUDE.md` (all of it; "How to work with me" and "Operational rules" bind you), `docs/DEVELOPING.md`, `docs/ARCHITECTURE.md`, then the research note sections your scope names.
2. **The calculation engine is not rewritten.** `backend/extractor/universal_rules.py`, `vision_call.py`, `line_items.py` and the lanes under `backend/extractor/` are owned by the backend manager. A worker whose scope needs a new *input* to the engine writes the input and a test, and reports it; a worker never changes a formula, a default or a factor. Any change that moves a billed quantity must be measured with `venv/bin/python eval_harness.py --totals-only --recompute --gate` and `--rows --recompute --gate` from the repo root and the WORSE/BETTER lines quoted in the report.
3. **UI text Lithuanian, identifiers English.** shadcn + the Nordic Slate tokens in `frontend/src/index.css`; never `bg-gray-*`. Every quantity shows its assumptions and confidence; every AI result is editable; honest disclosure beats a clever fix.
4. **Verify in a browser, on your own ports** (table below), with the demo projects copied into your worktree. "Lint passes" is not "it works".
5. **Tests:** backend `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q tests` (≈4700, ~7 min; run the relevant files during work, the full suite before reporting); frontend `cd frontend && npm run test:units && npx eslint . --quiet && npm run build`. New behaviour gets tests in the repo's style (node:test for `lib/*.js`, pytest for routes). `tests/test_route_ownership_policy.py` walks every `{project_id}` route automatically: a new project-scoped route must check ownership before validating its body.
6. **No new dependencies** without writing it in the report first. No Vision/Anthropic calls from tests. Do not run `/extract-interior` (paid, ~$2.37, 12 min) — use the saved extracts in the demo projects and the €0 lanes.
7. **Scope discipline.** Touch only the files your brief names (plus tests and docs for them). If you must touch a shared file (`TakeoffViewer.jsx`, `InteriorWorkspace.jsx`, `main.py`), keep the diff minimal and say so in the report; the manager merges.
8. **Commits:** small, one concern each, message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push, never deploy, never touch `main` or `viewer-rebuild`.
9. **Report format** (your final message): what was built · how the founder verifies it on localhost (URL, clicks) · tests run with counts · what is not done or not verified · risks and open questions.

## Worktree setup (do this first, every worker)

```bash
# in your worktree root
ln -s /Users/ignasgaldikas/samatu-ai/frontend/node_modules frontend/node_modules
mkdir -p backend/data && cp /Users/ignasgaldikas/samatu-ai/backend/data/samatu.db backend/data/ \
  && cp -R /Users/ignasgaldikas/samatu-ai/backend/data/pdf_store backend/data/pdf_store
cp /Users/ignasgaldikas/samatu-ai/backend/.env backend/.env
# eval gate fixtures (untracked PDFs the €0 lanes read; without them every --recompute drifts, e.g. 22,60 → 22,72 %)
mkdir -p docs/superpowers/fixtures && cp -R /Users/ignasgaldikas/samatu-ai/docs/superpowers/fixtures/. docs/superpowers/fixtures/
cp /Users/ignasgaldikas/samatu-ai/backend/.confidential-terms backend/.confidential-terms   # the denylist is untracked too
# backend (your port from the table; --reload is fine in dev)
cd backend && SAMATU_AUTH_DISABLED=1 /Users/ignasgaldikas/samatu-ai/venv/bin/uvicorn main:app --port <BACKEND_PORT> --reload
# frontend, pointed at your backend
cd frontend && VITE_BACKEND_URL=http://localhost:<BACKEND_PORT> npm run dev -- --port <VITE_PORT>
```
Demo project with vector PDF, 11 rooms, 8 sheets: `http://localhost:<VITE_PORT>/project/demo-objektas_h`. Also `demo-objektas_g`. The main checkout's servers are on 8000/5173 — never use those ports.

| Worker | Branch | Backend port | Vite port |
|---|---|---|---|
| W1 quantities panel | `togal/quantities-panel` | 8101 | 5181 |
| W2 symbol search + count | `togal/symbol-search` | 8102 | 5182 |
| W3 detection run + progress | `togal/detect-run` | 8103 | 5183 |
| W4 shortcuts + history + onboarding | `togal/comfort-shortcuts` | 8104 | 5184 |
| W5 outline tools (split/merge/subtract/lasso) | `togal/outline-tools` | 8105 | 5185 |
| W6 scale flow per sheet | `togal/scale-flow` | 8106 | 5186 |
| W7 sheets: naming, links, discipline | `togal/sheets` | 8107 | 5187 |
| W8 export (Excel groupings, PDF overlays) | `togal/export` | 8108 | 5188 |
| W9 assemblies + cost codes | `togal/assemblies` | 8109 | 5189 |
| W10 versions + compare | `togal/versions` | 8110 | 5190 |
| W11 chat pills + learning loop | `togal/chat-learning` | 8111 | 5191 |

## Capability map (Togal → Pathon, interior finishing) and waves

| # | Togal capability (research §) | Pathon today | Target | Wave |
|---|---|---|---|---|
| A | Green Togal button: one run per sheet, named progress stages, layered results, Re-Togal, All/Custom features (§3) | `/extract-interior` whole project; `api/free_reread.py` €0 lane rerun; no per-sheet progress | „Perskaityti lapą" button per sheet with stage progress (scale → text → rooms → walls → openings → quantities), results into viewer layers, rerun keeps user edits | 1 (W3) |
| B | Quantities Panel: classification tree, totals, eye toggles, sort, right-click reclassify, two-way highlight (§5, §8) | Rooms list + Matavimai list + sąmata table | Panel with families (dažymas, grindys, plytelės, GKP…) × rooms, totals, eye, right-click „Priskirti", click row ↔ highlight on sheet, drill to ledger | 1 (W1) |
| C | Editing: vertex, split, merge, subtract, lasso, arcs, groups (§6) | Vertex edit + snap (done); click-to-fill; split-space via check sheet | Split / merge / subtract tools on outlines in the viewer, lasso select of measurements and counts | 2 (W5) |
| D | Symbol counting + AI image search + pattern search (§3) | `/api/cv/match-template`, v9 symbol detector, count tool | Draw a box → find similar on the sheet/set → review list with delete → convert to count classification; honesty: over-count warning, confidence filter | 1 (W2) |
| E | Scale: predicted per sheet, confirm hint, standard scales, measure check, gate (§2) | Lane scale + manual calibration + suggestion (done) | Per-sheet scale overview (set-wide table: which sheets have which scale, source), confirm flow, gate detection on unset scale | 2 (W6) |
| F | Sheets: auto name/number, organize by discipline, thumbnails, links/callouts, text search (§1) | `page_classifier`, thumbnails, text search exist | Sheet rail with names/types/discipline groups, link callouts between sheets, undo auto-naming | 2 (W7) |
| G | Assemblies: components, formulas, waste, material/labour cost, cost codes; AI suggestions (§8) | `assembly_library.json`, price lists, `universal_rules` formulas | Assemblies UI mapping families → materials/labour with waste and unit prices; cost codes in LT sąmata structure | 3 (W9) |
| H | Export: Excel Screen/Full with groupings, PDF with overlays + legend, CSV template (§8) | Excel/PDF export, „kaip mano sąmatose" template | Grouping options, PDF of sheets with overlays and legend, export preview | 2 (W8) |
| I | Versions, history mode, drawing comparison overlay (§6) | Version history & snapshot articles exist? (check) | History mode with restore; compare two sheet revisions as overlay | 3 (W10) |
| J | Togal.CHAT over plans with selection pills (§8) | `/chat-project` exists | Chat docked in viewer, selected rooms/rows as context pills | 3 (W11) |
| K | Comfort: shortcut guide, in-app shortcuts panel, undo everywhere, right-click, processing-time education, onboarding (§11) | Partial | Shortcuts panel + printable guide, measurement/outline history, onboarding tooltips for first run | 1 (W4) |
| L | Learning loop: corrections as training data, accept/reject (§7) | `scripts/build_ground_truth.py` harvests corrections | Accept/reject on AI results recorded; „Įsiminta" counters; export of the correction corpus | 3 (W11) |

## Manager duties

- **Viewer / UI / integration manager** (this session, "Togal.AI PDF to quantities pipeline"): owns `togal-v2`, briefs and reviews W1, W2, W4, W5, W6, W7, W8; merges after reading the diff, running lint/units/build and the backend files the worker touched; keeps this document current.
- **Backend / calculation-input manager** (session ref d39d76): owns everything under `backend/extractor/`, the geometry lanes, scale lanes and `api/free_reread.py`; briefs and reviews W3, W9, W10, W11; runs the eval gate on every merge that touches a lane.
- Reviews ask: does it work on objektas_h in a browser; what did the tests prove; did any billed quantity move; is anything AI-seeded presented as read; does the UI say what it is unsure about.

## Review and merge protocol

1. Worker reports. Manager reads the diff (`git diff togal-v2...togal/<scope>`), runs the worker's verification steps on the worker's ports or after a local merge.
2. Manager merges into `togal-v2` with `git merge --no-ff togal/<scope>`; conflicts are resolved by the manager, never by force.
3. After each merge: `npm run test:units && npx eslint . --quiet && npm run build` and the touched backend test files; the full backend suite at the end of each wave.
4. Wave done → founder reviews on 5173/8000 from `togal-v2`. No PR, no push, no deploy until the founder says so.

## Baseline for every lane-touching merge (togal-v2 @ bad14b7, `eval_harness.py --recompute --gate`, zero API, taken by the backend manager 2026-10-16 11:49)

- Totals: his billed lines **22,60 %** (a 6,21 · b 18,07 · c 36,29 · d 16,22 · g 56,83 · h 17,12); legacy totals MAE 15,44 %; gate OK. Run: `eval_runs/2026-10-16_11-49-56_multi_totals_only`.
- Rows: within ±10 % corpus mean **26,1 %**, € share 34,7 % (a 37,7/32,4 · b 9,9/21,0 · c 22,2/12,1 · d 36,0/60,3 · g 30,0/55,6 · h 20,8/26,7); gate OK.

Merge key: the viewer manager merges into togal-v2; the backend manager reviews and gates W3/W9/W10/W11 and signals „merge-ready". W3 review (backend manager): stage progress through an explicit `on_stage` callback on `geometry_lane.apply_geometry` (authorised, pass-through only), per-room landing for narrowed runs, a fixed honesty sentence in every job snapshot (the lane reads the whole drawing; the sheet only narrows what lands). Detection stages follow the lane's real order, not Togal's: mastelis „Mastelis" → tekstas „Patalpos lape" (locate_rooms places the table's rooms on the sheets from the text layer) → planas „Planas" (align_sheets lays one plan's sheets over each other) → konturai „Kontūrai" → angos „Angos" (openings are read before the walls are summed) → sienos „Sienos" → grindys „Grindų dangos" → kiekiai „Kiekiai" (closed by the browser after /recompute-interior). No separate „Patalpos" stage.

**Confidentiality:** `backend/.confidential-terms` is the founder's denylist; before every commit on togal-v2 run `git diff --cached | grep -i -n -F -f backend/.confidential-terms` and commit only when it prints nothing. Worker reports and session titles are not exempt.

## Merge log (togal-v2)

| When | Branch | What | Checks at merge |
|---|---|---|---|
| 2026-10-16 | research/togal-pipeline-analysis (ff) | snap to walls, standard scale, walls layer, outline editing, comfort layer | backend 4698 pass, units 1047, lint, build |
| 2026-10-16 | togal/quantities-panel (W1) | „Kiekiai" tab: lines × rooms tree, two-way highlight, eye, right-click, sort/filter | units 1059, lint |
| 2026-10-16 | togal/comfort-shortcuts (W4) | shortcut table + „?" guide + PDF, Istorija undo/redo, coach marks, right-click on marks, keys S/U for layers | units 1089, lint, build |
| 2026-10-16 | togal/symbol-search (W2) | „Rasti panašius": box a symbol → OpenCV matches on the sheet (dpi budget ≈3 Mpx, raster sheets skipped with a warning), review list, add as count | units 1104, lint, build, backend cv + ownership 105 pass; A3 search 5,04 s |
| 2026-10-16 | togal/detect-run (W3) | „Perskaityti lapą / iš naujo": €0 whole-drawing read per sheet with stage progress (mastelis → tekstas → planas → kontūrai → angos → sienos → grindys → kiekiai), narrowed landing, toast names the plan | units 1116, lint, build; six backend files 142 pass; backend manager: replay-geometry pair identical to baseline, branch suite 4675 pass |
| 2026-10-16 | togal/scale-flow (W6) | „Masteliai" per-sheet overview (scale, source, state nenustatytas · spėjamas · patvirtintas), confirm one / all with the same lane scale (lane-confirmed), „Patikrinti mastelį" readout against written strings, scaleGateFor soft chip, one effective per-sheet scale for viewer + Matavimai + export (no more „nekalibruota") | units 1140, lint, build (frontend only) |
| 2026-10-16 | togal/symbol-search follow-up (W2, 4032489) | AI-found counts drawn hollow, „N AI" in the legend with an explanation line, rejections recorded on cancel | units 1142, lint, build (frontend only) |
| 2026-10-16 | togal/outline-tools (W5) | „Padalyti" (two-click chord, keep a half, give the other to a room or drop), „Sujungti" (union of touching outlines, `outline-merge` route; absorbed room excluded via `_apimtis.patalpos_ne`), „Atimti" (holes on `outline-set`, `skyliu_perimetras_m`), „Laso" (key L, batch right-click) | units 1164, lint, build; outline + ownership 64 pass |
| 2026-10-16 | togal/sheets (W7) | sheet rail with discipline groups, number/name/type, rename with toast undo (`sheet_overrides`), search hit counts; `GET …/pages/{page}/callouts` (`api/sheet_links.py`, `sheet_refs.py`) + CalloutLayer | units 1176, lint, build; sheet refs/links + ownership 78 pass |
| 2026-10-16 | togal/export (W8) | `/generate-excel` „Grupuoti pagal" (skyrius · patalpas · darbų šeimas · lapus · be grupavimo; `api/export_grouping.py`), preview route, „PDF su žymėjimais" (`api/export_overlay_pdf.py`: outlines, measurements, counts, walls, legend) with sheet preview | units 1186, lint, build; export + ownership 121 pass |

Wave-1 end, togal-v2 @ 99a8a29: full backend suite on the main checkout 4742 passed, 3 skipped (7 min 26 s).

Known follow-ups from the reports: W6 „Skirtumas" compares the RAW span (one stroke width too long, +1 pt): fix authorised by the backend manager (`ilgis_pt` on plan_dimensions / dimension_sum, card formula), given to W7 on togal/scale-flow-caps. W5 — kept room bills only its own printed area after „Sujungti"; hole perimeters stored, no formula reads them; the lane may re-outline a „sujungta" room (backend manager). W8 — possible viewer stretch on /Rotate 90/270 sheets (EmbedPDF page.size vs mediabox; check objektas_a); grouped exports carry a „Kaip gauta" column (founder decides whether client exports keep it). W7 — a project opening on page 2 jumps back for ~12 s (viewer, own task). W6 — the drawn lines of written dimension strings on objektas_h sheet 1 come out 4–6 % longer than written (lane line_pct likely includes tick marks; backend manager to look before „Skirtumas" is read as a scale error); the scale chip sits partly under the open Masteliai panel; the DetectRunButton should call scaleGateFor and show „Nustatyti mastelį" when the sheet has no scale (not block). focusing a room scrolls to its page, not to the room (TakeoffViewer focus scrolling); the Matavimai list says „nekalibruota" where the viewer shows metres (it ignores the lane scale); AI-found count marks look like hand-placed ones on the sheet; two things are now called „Kiekiai" (the new tab and the priced-lines section). W2 leftovers sent back to the worker: AI-found counts marked „legendoje", rejected candidates recorded on cancel, AI marks visually distinct. W3 follow-up sent back: toast and pill must say „planui (lapai 1–7)" when the chosen sheet belongs to a multi-sheet plan.

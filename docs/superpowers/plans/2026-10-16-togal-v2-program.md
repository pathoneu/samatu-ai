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
- **Backend / calculation-input manager** ("Ciurliu dimension re-extraction"): owns everything under `backend/extractor/`, the geometry lanes, scale lanes and `api/free_reread.py`; briefs and reviews W3, W9, W10, W11; runs the eval gate on every merge that touches a lane.
- Reviews ask: does it work on objektas_h in a browser; what did the tests prove; did any billed quantity move; is anything AI-seeded presented as read; does the UI say what it is unsure about.

## Review and merge protocol

1. Worker reports. Manager reads the diff (`git diff togal-v2...togal/<scope>`), runs the worker's verification steps on the worker's ports or after a local merge.
2. Manager merges into `togal-v2` with `git merge --no-ff togal/<scope>`; conflicts are resolved by the manager, never by force.
3. After each merge: `npm run test:units && npx eslint . --quiet && npm run build` and the touched backend test files; the full backend suite at the end of each wave.
4. Wave done → founder reviews on 5173/8000 from `togal-v2`. No PR, no push, no deploy until the founder says so.

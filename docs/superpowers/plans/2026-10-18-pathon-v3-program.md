# Pathon v3 programme — "Skaitymas ir spustelėjimas" (reading and clicking)

> Founder brief (2026-10-18): merge Pathon's own interior-finishing product with the best of Togal and Kreo and make it clearly better; the backend is the core (legends marked on drawings, schedules, zones — "all the comfortable and understandable using of the app"); users are Rimas **and** bigger firms; keep our colours while working, decide the look later; €0 by default, a paid run only when absolutely necessary and asked for first. One manager session (Fable 5.1, "Togal-v2 backend manager") directs and reviews; Opus 5.5 workers build in isolated worktrees. **Nothing is pushed or deployed; the founder reviews on localhost at the end of each wave.**

Design contract: `docs/superpowers/specs/2026-10-18-pathon-v3-design.md` (targets, workspace decision, tracks A–G, click vocabulary, waves, founder decisions). Research: `docs/superpowers/research/2026-10-18-{togal-editor-ui-re,kreo-editor-ui-re,pathon-viewer-ui-audit,backend-reading-inventory}.md`. Previous programme and its merge log: `docs/superpowers/plans/2026-10-16-togal-v2-program.md`.

## Non-negotiables (every worker, every task)

1. **Read first:** `CLAUDE.md` (all of it), `docs/DEVELOPING.md`, `docs/ARCHITECTURE.md`, the design doc, the research sections your brief names, and `docs/superpowers/plans/2026-09-04-rimo-kelione.md` (the user).
2. **The calculation engine is not rewritten.** `backend/extractor/universal_rules.py`, `vision_call.py`, `line_items.py` and the lanes under `backend/extractor/` are owned by the manager. A worker whose scope needs a new *input* to the engine writes the input and a test and reports it; never a formula, a default or a factor. Any change that could move a billed quantity is measured with `venv/bin/python eval_harness.py --totals-only --recompute --gate` and `--rows --recompute --gate` from the repo root, WORSE/BETTER lines quoted in the report. The manager reruns all four passes (incl. `--replay-geometry`) on every lane-touching merge.
3. **UI text Lithuanian, identifiers English.** shadcn + the Nordic Slate tokens in `frontend/src/index.css`; never `bg-gray-*`; no new fonts or palettes (the look is decided later). The design doc's overlay vocabulary and type floor apply to anything you touch: solid = read or confirmed, dashed = estimated or proposed only, red = error only; 14 px interface minimum; meaning never by colour alone.
4. **Rimas rules.** Plain Lithuanian, no jargon (the banned-word guard test enforces part of it), every number keeps its evidence sentence and crop, **every AI or lane result is reviewed before it exists** (preview → ✔/🗑 → create), **every write offers Undo**, nothing hover-only, instructions at the cursor or in the pill — not banners.
5. **Verify in a browser, on your own ports** (table below), with the demo projects copied into your worktree. Playwright screenshots of the before and after go in the report. "Lint passes" is not "it works".
6. **Tests:** backend `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q tests` (≈5050, ~8 min; relevant files during work, full suite before reporting); frontend `cd frontend && npm run test:units && npx eslint . --quiet && npm run build`. New behaviour gets tests in the repo's style. `tests/test_route_ownership_policy.py` walks every `{project_id}` route: ownership before body validation.
7. **No new dependencies** without writing it in the report first. No Vision/Anthropic calls from tests or from browser verification. Never run `/extract-interior` (paid). Never upload any project PDF to a third-party service.
8. **Scope discipline.** Touch only the files your brief names (plus their tests and docs). Shared files (`TakeoffViewer.jsx`, `InteriorWorkspace.jsx`, `WorkspacePanel.jsx`, `main.py`, `index.css`): minimal diff, listed in the report; the manager merges.
9. **Commits:** small, one concern each, message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Before every commit: `git diff --cached | grep '^+' | grep -v '^+++' | grep -i -F -f backend/.confidential-terms` must print nothing. Never push, never deploy, never touch `main` or `viewer-rebuild`; branch off the current `togal-v2` HEAD unless the brief names another base.
10. **Shared machine.** Never stop a process by name (`pkill -f …`, `killall python`); stop only your own PIDs. The main checkout's servers (8000/5173) and the old v2 worktree servers (8101–8111) are not yours.
11. **Report format** (final message, also sent to the manager with SendMessage): what was built · how the founder verifies it on localhost (URL, clicks) · tests run with counts · what is not done or not verified · risks and open questions · shared files touched.

## Worktree setup (do this first, every worker)

```bash
# in your worktree root (git worktree add ../<name> -b <branch> togal-v2, or the app's worktree)
ln -s /Users/ignasgaldikas/samatu-ai/frontend/node_modules frontend/node_modules
mkdir -p backend/data && cp /Users/ignasgaldikas/samatu-ai/backend/data/samatu.db backend/data/ \
  && cp -R /Users/ignasgaldikas/samatu-ai/backend/data/pdf_store backend/data/pdf_store
cp /Users/ignasgaldikas/samatu-ai/backend/.env backend/.env
mkdir -p docs/superpowers/fixtures && cp -R /Users/ignasgaldikas/samatu-ai/docs/superpowers/fixtures/. docs/superpowers/fixtures/
cp /Users/ignasgaldikas/samatu-ai/backend/.confidential-terms backend/.confidential-terms
cd backend && SAMATU_AUTH_DISABLED=1 /Users/ignasgaldikas/samatu-ai/venv/bin/uvicorn main:app --port <BACKEND_PORT> --reload
cd frontend && VITE_BACKEND_URL=http://localhost:<BACKEND_PORT> npm run dev -- --port <VITE_PORT>
```
Demo projects: `http://localhost:<VITE_PORT>/project/demo-objektas_h` (vector PDF, 11 rooms, 8 sheets) and `demo-objektas_g`. The live DB file is `backend/data/samatu.db` (not `backend/samatu.db`).

| Worker | Branch | Backend | Vite | Wave |
|---|---|---|---|---|
| W0-A smoke suite of the founder's walkthrough guide | `v3/smoke-guide` | 8121 | 5201 | 0 |
| W0-B audit bugs + banned-word copy pass | `v3/audit-bugs` | 8122 | 5202 | 0 |
| W1-A workspace frame (one workspace, right-panel mode host, rail strip, canvas share) | `v3/workspace-frame` | 8123 | 5203 | 1 |
| W1-B toolbar → icon cards + bottom pill, keys, Esc order, Space-pan, floating action bar, cursor hints | `v3/click-model` | 8124 | 5204 | 1 |
| W1-C overlay tokens + vocabulary, type scale, density, one notice system | `v3/overlay-vocabulary` | 8125 | 5205 | 1 |
| W1-D select by click, room tool R (vector outline in the viewer), Undo after every save, scale chip | `v3/room-click` | 8126 | 5206 | 1 |
| W1-E sheet zones backend (`extractor/sheet_zones.py`, `_meta.zonos`, route) | `v3/sheet-zones` | 8127 | 5207 | 1 |
| W2-A legend rows + generalised vector counter + raster batch | `v3/legend-count` | 8128 | 5208 | 2 |
| W2-B legend marking UI with review-before-create, counts → rows | `v3/legend-ui` | 8129 | 5209 | 2 |
| W3-A table reader with row bboxes (door/window/finish schedules), "lentelės" stage | `v3/tables` | 8130 | 5210 | 3 |

Wave-1 rows are briefed only after the wave-1 implementation plan is written and reviewed; W1-B/C/D branch off W1-A once its frame is merged (they all touch the viewer).

## Waves (summary; details in the design doc §7)

| Wave | Scope | Done when |
|---|---|---|
| 0 | Playwright smoke of the 2026-10-17 review guide; the 7 small bugs and the banned-word copy pass from the audit; baselines T1–T3 noted | smoke green on togal-v2; bugs merged; numbers in this doc |
| 1 | One workspace + click model + overlay vocabulary + room tool + Undo + scale chip; sheet zones backend | founder walks the guide on the new frame; eval gate identical; T1 clicks measured against the targets |
| 2 | Legend marking and symbol counting with review-before-create; counts → rows live | T4 on the corpus plan sheets; legend reuse across projects |
| 3 | Tables: door/window/finish schedules with row bboxes; "lentelės" stage; reconciliation questions | T4 schedule part; Patikra asks the new questions |
| 4 | Measurements → sąmata model; Kiekiai inline edit; "Kas pasikeitė — Atšaukti" | counts and lengths flow live |
| 5 | Pro layer (decision pending) | – |
| 6 | Look (decision pending) | – |

## Manager duties and merge protocol

- Single manager (this session) owns `togal-v2`, briefs and reviews every worker, merges with `git merge --no-ff`, runs lint/units/build and the touched backend tests after each merge, the full backend suite at the end of each wave, and the four eval passes on any lane-touching merge (baseline: togal-v2 @ bad14b7 — billed lines 22,60 %, rows ±10 % 26,1 %, € 34,7 %; every v2 merge was identical to it, last confirmed at 167dc94).
- Review questions: does it work on objektas_h in a browser; what did the tests prove; did any billed quantity move; is anything AI-seeded presented as read; does the UI say what it is unsure about; does every write have Undo; does it follow the overlay vocabulary and the type floor.
- Wave done → founder reviews on 5173/8000 from `togal-v2`. No PR, no push, no deploy until the founder says so.

## Paid runs log

None so far. Candidates (each asked for first, with purpose and cost): Vision legend reading on raster-only legends; a fresh read of an out-of-sample project to measure T2/T3 after waves 1–3. Unit costs: one project €2–4 (25–28 min), six-project corpus pass ≈ €15.

## Merge log (togal-v2, v3 programme)

| When | Branch | What | Checks at merge |
|---|---|---|---|
| | | | |

## Founder decisions log

- 2026-10-18: one workspace with four views — yes; overlay vocabulary — yes; legend zone suggested then confirmed (least manual work); wave order and small UI words — manager's call (frame first, zones in parallel; chip banner, 14 px, „Taisyti kontūrą", „Prielaidos"); pro layer / multi-user — open; €0 default, no paid run without asking; Kreo trial opened by the founder himself (the manager never types credentials); only the synthetic plan may be uploaded to a competitor.

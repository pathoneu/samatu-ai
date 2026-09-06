# Pathon — Developer Runbook

How to run, test, debug and change Pathon **without re-learning it the hard way.**
Written 2026-07-06 (Fable 5 handoff). Pairs with [`ARCHITECTURE.md`](ARCHITECTURE.md) (data flow + which-file-is-canonical) and [`RUNBOOK.md`](RUNBOOK.md) (production launch/DNS/hosting — a separate concern).

## Layout

- `backend/` — FastAPI. `main.py` is huge (most endpoints + Excel/PDF export). `extractor/` = the accuracy engine. `api/` = split routers (e.g. `recompute_quantities.py` — the LIVE recompute). `billing/` = dormant, flag-gated. `auth.py`, `db.py` (SQLite).
- `frontend/` — React + **Vite + JSX (NOT TypeScript)**. `src/pages/`, `src/components/project/`, `src/lib/`.
- `venv/` — Python env at repo root (`../venv` from `backend/`).
- `ground_truth/` + `docs/superpowers/fixtures/` — the contractor's real sąmatos, used as accuracy ground truth.

## Run it locally

- **Frontend:** `cd frontend && npm run dev` → http://localhost:5173
- **Backend:** `cd backend && ../venv/bin/uvicorn main:app --port 8000` (`main.py` calls `load_dotenv()` → reads `backend/.env`).
- Vite proxies `/api`, `/extract-interior`, `/export/*` to :8000 (`frontend/vite.config.js`).

### Storage: dev and tests write to LOCAL DISK, even with R2 credentials loaded

`backend/.env` carries the four `R2_*` vars, and until 2026-09-04 their mere
presence selected R2 — so a dev server and the whole test suite wrote into the
**production bucket** (35 test-seed objects landed in the live `projects/`
prefix on 09-02/09-04, mixed in with real customers' drawings).

`storage.r2_decision()` now needs a second signal that this process may use the
bucket. Precedence, top wins:

| Env | Backend |
|---|---|
| `STORAGE_BACKEND=local` | local disk (even in production — the ERROR below still fires) |
| any `R2_*` var missing | local disk (**WARNING**, names the missing vars) |
| `STORAGE_BACKEND=r2` | R2 |
| `ENV=production` | R2 |
| otherwise (your machine) | local disk (**INFO**, says the credentials are present and deliberately unused) |

Every start logs one line saying which backend and why; production on local disk
is still an **ERROR** (`PRODUCTION uploads are NOT durable`). To exercise the
real R2 path deliberately: `STORAGE_BACKEND=r2 ../venv/bin/uvicorn main:app`
— and remember that writes land in the live bucket. Local objects go to
`backend/data/pdf_store` (or `LOCAL_STORAGE_DIR`). Matrix:
`backend/tests/test_storage_backend_gate.py`.

> Related, **not** fixed: `backup_scheduler.is_enabled()` still defaults on
> whenever `R2_BUCKET` is set, so a dev box runs the nightly DB backup. It is now
> harmless — `backup.py` goes through `get_storage()`, so the snapshot lands on
> local disk — just pointless. Set `SAMATU_NIGHTLY_BACKUP=0` to silence it.

### ⚠️ The gotcha that WILL waste an hour: the dev backend has no `--reload`.
After you edit backend code, the running uvicorn keeps serving the **old** code.
Symptom: the frontend gets `400 Unknown field '…'`, or "my change didn't take."
Fix: `pkill -f "uvicorn main:app"` and relaunch — or run with `--reload` while developing.

## Auth config

- **Dev:** `backend/.env` sets `SAMATU_AUTH_DISABLED=1` → every request is the bootstrap dev user, no login. Fine for UI work; **useless for security testing** (masks all authz).
- **To test auth/authz like production:** run a second instance with the flag forced off —
  `cd backend && SAMATU_AUTH_DISABLED=0 ../venv/bin/uvicorn main:app --port 8001`
  (`load_dotenv(override=False)` won't clobber the shell var). Unauthenticated requests then return **401**.
- **Guardrail:** the app hard-fails at startup if `SAMATU_AUTH_DISABLED=1` **and** `ENV=production`, so prod can't ship with the auth wall off.

## Tests — what "green" means

- **Backend:** `cd backend && ../venv/bin/python -m pytest -q` → **≈1468 passed** (~71 s) as of 2026-07-25. `conftest` autouse-clears rate-limit buckets between tests.
- **Frontend units:** `cd frontend && node --test src/lib/*.test.js src/lib/viewerEngine/*.test.js` → **≈258 pass** as of 2026-07-25. These use **node:test, not vitest** — running vitest errors "No test suite found."
  - ⚠️ **The bare `src/lib/*.test.js` glob silently skips `src/lib/viewerEngine/*.test.js`** — 3 files, 23 tests (`embedPdfAdapter`, `pageRotation`, `pageViewport`). `*` does not recurse into subdirectories, and the glob still matches plenty of files in `src/lib/` itself, so nothing errors: you get a green run that quietly proves less than you think. Those 23 tests do pass — they just never ran. `package.json`'s `test:units` still carries the narrow glob (being fixed separately) — until then, type the full command above.
  - Treat both counts as **drifting**. They are a smell test, not a contract: run the suite and read its own total rather than diffing against a number in a doc.
- **Lint:** `cd frontend && npx eslint . --quiet`.
- There is no frontend component-test harness and **no Playwright config in the repo** (no `playwright.config.*`, no `e2e/`) — browser verification is done ad-hoc via the Playwright MCP. **Verify UI changes in a real browser**, not just a type-check.
- **SEO build (opt-in):** `cd frontend && npm run build:seo` — `vite build` + prerenders the **11** public routes (`/`, `/en`, `/about`, `/duk`, `/privacy`, `/terms`, `/cookies` + the 4 BoFu pages) into `dist/<route>/index.html` (pinned `playwright@1.55.1` via npm exec; chromium cached in `~/Library/Caches/ms-playwright`). Default `npm run build` untouched. Spot-check with `python3 -m http.server -d dist` — **`vite preview` skips the directory index files**, so it will misleadingly show the SPA shell.

## Run the extractor on a real PDF ($ + slow)

`cd backend && RUN_ID=x ../venv/bin/python scripts/variance_run.py`
→ loads `.env`, runs `extract_interior` on the Objektas A fixture, dumps `/tmp/opus48_objektas_a_run<id>.json`.
**~$2.37/project, ~12 min** on the Opus 4.8 full pipeline (voting + zoom + readers). That's the real per-project COGS — don't re-run casually.

## Measure accuracy BEFORE claiming an accuracy change works

Ground truth = the contractor's real sąmatos:
- **Objektas A** — `docs/superpowers/fixtures/2026-05-26-objektas-a/` (`samata-truth.pdf`, `gap-analysis-2026-07-05.md`, `app-output-2026-07-05-opus48.json`).
- **Objektas B** — `ground_truth/objektas_b/`.

**In-sample baseline restated 2026-09-05: `--totals-only --recompute` reads 11,83 % (was 7,82 %).** The 7,82 % contained a compensating error — a wall tiled to a partial band was billed as tile AND as paint, and on objektas_c/d that phantom paint cancelled real under-counts (c's bathroom sheets are not even in the fixture PDF; d's „2,39 m tile height" is the ceiling drop). The table now also prints an **Out-of-sample** line (objektas_g/h, never tuned on; 12,84 % after the fix, 24,42 % before) — that line is the generalisation number and is never blended into the in-sample mean. Founder rule (2026-09-05): the engine computes from the drawing; a sąmata is used only to CHECK afterwards — never tune a rule, default or factor until it matches his number.

**Headline restated 2026-09-06 (walls and ceilings scored separately, founder rule): in-sample 9,75 %, out-of-sample 5,85 %** (walls / ceilings / LED / floor; the combined paint line is printed as „Combined(info)" and never pooled). Ceilings are anchored to the eksplikacija total — or, when a drawing prints no table, to the sum of the room areas written on the plan (`backend/extractor/plan_area_annotations.py`, Step 2.44; `scripts/backfill_plan_areas.py` for cached extracts). Row scorecard: `--rows --recompute --detailed`; the paint family is four leaves (Sienų/Lubų × iki/virš 3 m) + five parents in his aggregations — a change to the concept table is a mapping change: diff the per-row table before/after and report it.

**RULE: never change *billed quantities* without measuring against these.** The deterministic math already matches the contractor within ~1% on correct inputs — the remaining gap is Vision *detection*, not the formulas. An unverified formula "fix" is a regression risk.

**Provenance is an accuracy invariant too (2026-09-02).** Any change to the builder must keep `backend/tests/test_contribution_ledger.py` green — it replays every row's `roll_up` over its `contributions` on all corpus fixtures and fails if the ledger stops reproducing `kiekis`. If you wire a new family into the ledger, add it there (and to the LT-string vocabulary guard). To eyeball Patikra locally: start `backend-dev` + `frontend-dev` from `.claude/launch.json` (restart the backend after backend edits — no `--reload`), open a local project, toggle anything in Prielaidos (the rebuilt list carries ids + ledger), then click a row → tree, and use the right-hand PATIKRA rail (card → „Pataisyti" → Prielaidos focus → recompute → „Perskaičiuota: N eilučių" → „Įsiminta"). The shipped demo snapshot carries no ledger on disk until it is recomputed.

**To eyeball the contractor's own layout (2026-09-05):** the switch („Pathon" | „Kaip mano sąmatose") appears on the Sąmata step only when the dev account has a template. Seed one from the gitignored parsed sąmatas — never from anything that could carry a client name into a tracked file:

```bash
venv/bin/python -c "import json;print(json.dumps({'name':'Mano sąmatos šablonas','is_default':True,'samatas':[{'slug':s,'line_items':json.load(open(f'ground_truth/{s}/contractor_samata_parsed.json'))['line_items']} for s in ['objektas_a','objektas_b','objektas_c','objektas_d']]},ensure_ascii=False))" > /tmp/seed_template.json && curl -s -X POST http://localhost:8000/api/samata-templates -H 'Content-Type: application/json' --data-binary @/tmp/seed_template.json | head -c 200
```

Then: Sąmata → switch → type into a blank cell (becomes an `rnk-` row in `darbu_sarasas`), „Teisinga" on a greyed suggestion (stamps the source rows), Eksportuoti → „Excel — kaip mano sąmatose"; Patikra → last page → „Jūsų eilutės". `DELETE /api/samata-templates/{id}` removes the seed. The render is a view — `POST …/samata-render` never writes.

## Deploy / billing (dev-relevant bits — full launch steps in `RUNBOOK.md`)

- `BILLING_ENABLED` defaults `'0'` (dormant). Don't flip without the pre-flight: Stripe secret + webhook secret + price IDs present, webhook signature verified live, and `usage_events` logging confirmed (a silent-fail there could let a user drain the API budget uncharged).
- Prod needs `R2_*` env vars (PDF + DB-backup storage); `.env` is gitignored → set on the host.
- All work is on `viewer-rebuild`; nothing auto-deploys.

## Housekeeping gotchas

- Real listeners: `lsof -nP -iTCP -sTCP:LISTEN | grep -E "python|node"`.
- The "N running tasks" panel can show **zombie agents** (40 h+ timers = finished-but-not-cleared). They cost nothing and clear on app/session restart.
- Spun-off task-sessions live in `.claude/worktrees/*` on their own branches, sometimes based on an **older** commit than `viewer-rebuild` — merge their results forward deliberately, don't assume a clean fast-forward.

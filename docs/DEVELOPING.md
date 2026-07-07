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

- **Backend:** `cd backend && ../venv/bin/python -m pytest -q` → **1392 passed** (~71 s). `conftest` autouse-clears rate-limit buckets between tests.
- **Frontend units:** `cd frontend && node --test src/lib/*.test.js` → **224 pass**. These use **node:test, not vitest** — running vitest errors "No test suite found."
- **Lint:** `cd frontend && npx eslint . --quiet`.
- There is no frontend component-test harness — **verify UI changes in a real browser** (Playwright), not just a type-check.
- **SEO build (opt-in):** `cd frontend && npm run build:seo` — `vite build` + prerenders the 10 public routes into `dist/<route>/index.html` (pinned `playwright@1.55.1` via npm exec; chromium cached in `~/Library/Caches/ms-playwright`). Default `npm run build` untouched. Spot-check with `python3 -m http.server -d dist` — **`vite preview` skips the directory index files**, so it will misleadingly show the SPA shell.

## Run the extractor on a real PDF ($ + slow)

`cd backend && RUN_ID=x ../venv/bin/python scripts/variance_run.py`
→ loads `.env`, runs `extract_interior` on the Beржų fixture, dumps `/tmp/opus48_berzas_run<id>.json`.
**~$2.37/project, ~12 min** on the Opus 4.8 full pipeline (voting + zoom + readers). That's the real per-project COGS — don't re-run casually.

## Measure accuracy BEFORE claiming an accuracy change works

Ground truth = the contractor's real sąmatos:
- **Beржų** — `docs/superpowers/fixtures/2026-05-26-berzu-g-24/` (`samata-truth.pdf`, `gap-analysis-2026-07-05.md`, `app-output-2026-07-05-opus48.json`).
- **Objektas B** — `ground_truth/objektas_b/`.

**RULE: never change *billed quantities* without measuring against these.** The deterministic math already matches the contractor within ~1% on correct inputs — the remaining gap is Vision *detection*, not the formulas. An unverified formula "fix" is a regression risk.

## Deploy / billing (dev-relevant bits — full launch steps in `RUNBOOK.md`)

- `BILLING_ENABLED` defaults `'0'` (dormant). Don't flip without the pre-flight: Stripe secret + webhook secret + price IDs present, webhook signature verified live, and `usage_events` logging confirmed (a silent-fail there could let a user drain the API budget uncharged).
- Prod needs `R2_*` env vars (PDF + DB-backup storage); `.env` is gitignored → set on the host.
- All work is on `viewer-rebuild`; nothing auto-deploys.

## Housekeeping gotchas

- Real listeners: `lsof -nP -iTCP -sTCP:LISTEN | grep -E "python|node"`.
- The "N running tasks" panel can show **zombie agents** (40 h+ timers = finished-but-not-cleared). They cost nothing and clear on app/session restart.
- Spun-off task-sessions live in `.claude/worktrees/*` on their own branches, sometimes based on an **older** commit than `viewer-rebuild` — merge their results forward deliberately, don't assume a clean fast-forward.

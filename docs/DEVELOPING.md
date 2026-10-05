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
> local disk — just pointless. Set `SAMATU_NIGHTLY_BACKUP=0` to silence it. (It
> also records its outcome in the dev DB's `app_state`; pruning stays off unless
> `SAMATU_BACKUP_KEEP_DAYS` is set — RUNBOOK §2a.)

### ⚠️ The gotcha that WILL waste an hour: the dev backend has no `--reload`.
After you edit backend code, the running uvicorn keeps serving the **old** code.
Symptom: the frontend gets `400 Unknown field '…'`, or "my change didn't take."
Fix: `pkill -f "uvicorn main:app"` and relaunch — or run with `--reload` while developing.

## Python dependencies — the lock is what runs (2026-10-05)

Two files you edit, two you generate, all in `backend/`:

| File | Holds | Installed by |
|---|---|---|
| `requirements.txt` | production dependencies (human-edited, some loose bounds) | nothing directly |
| `requirements-dev.txt` | `-r requirements.txt` + test-only packages (pytest, pytest-asyncio, pikepdf) | nothing directly |
| `requirements.lock` | exact pins of the full production closure (58 packages) | `backend/Dockerfile`, `nixpacks.toml` |
| `requirements-dev.lock` | `-r requirements.lock` + the test-only closure (8 packages) | CI, your venv |

Every install is `pip install --no-deps -r <lock>` followed by `pip check`: a
dependency missing from a lock fails the build instead of being resolved to
whatever is newest on deploy day. Production runs CPython **3.12** (nixpacks),
the Dockerfile and the dev venv **3.14**; both locks resolve to wheels on both
(Linux x86_64). `backend/tests/test_dependency_locks.py` holds the contract:
exact pins, no package in both locks, the production closure complete and free
of test packages, the builds installing the lock, installed = locked, and no
production module importing a test-only package.

- **Your venv:** `venv/bin/python -m pip install --no-deps -r backend/requirements-dev.lock && venv/bin/python -m pip check`.
  The current venv also carries ~34 packages that are in neither lock (pip-audit, scipy,
  scikit-*, pymupdf, defusedxml…). The code imports none of them, but **defusedxml
  switches openpyxl's XML parsing locally** — for an exact production twin, build a fresh
  venv from the dev lock.
- **lxml is a production dependency on purpose.** openpyxl picks its XML engine by whether
  lxml imports; production always had it (pulled in by pikepdf, now test-only).

**To change a version or add a package:**

1. Edit `requirements.txt` (production) or `requirements-dev.txt` (tests only).
2. Resolve it in a throwaway venv on the dev Python:
   ```bash
   python3.14 -m venv /tmp/lockvenv
   /tmp/lockvenv/bin/pip install -r backend/requirements.txt
   /tmp/lockvenv/bin/pip freeze --exclude pip | sort > /tmp/runtime.txt   # body of requirements.lock
   /tmp/lockvenv/bin/pip install -r backend/requirements-dev.txt
   /tmp/lockvenv/bin/pip freeze --exclude pip | sort > /tmp/all.txt
   comm -13 /tmp/runtime.txt /tmp/all.txt     # body of requirements-dev.lock, after its `-r requirements.lock` line
   ```
   Keep both file headers. If the second install moved a version the first one chose, that
   package lands in both locks and the test fails — pin it in `requirements.txt` and redo.
3. Prove both locks install on production's interpreter and the Dockerfile's, wheels only,
   as Linux sees them — for each lock file and for `3.12`/`cp312` and `3.14`/`cp314`:
   ```bash
   venv/bin/python -m pip install --dry-run --ignore-installed --only-binary=:all: \
     --python-version 3.12 --implementation cp --abi cp312 \
     --platform manylinux_2_28_x86_64 --platform manylinux2014_x86_64 \
     --target /tmp/lockcheck -r backend/requirements.lock --report /tmp/lock-312.json
   ```
   Exit 0, and the report's `install` list holds exactly the locked packages (58 / 66) — an
   extra one is a missing pin. A pin with no wheel for 3.12 must not ship: production would
   try to compile it.
4. Reinstall your venv from the dev lock, run the full backend suite, and commit the four
   files together. Never hand-edit a single pin in a lock.

## Auth config

- **Dev:** `backend/.env` sets `SAMATU_AUTH_DISABLED=1` → every request is the bootstrap dev user, no login. Fine for UI work; **useless for security testing** (masks all authz).
- **To test auth/authz like production:** run a second instance with the flag forced off —
  `cd backend && SAMATU_AUTH_DISABLED=0 ../venv/bin/uvicorn main:app --port 8001`
  (`load_dotenv(override=False)` won't clobber the shell var). Unauthenticated requests then return **401**.
- **Guardrail:** the app hard-fails at startup if `SAMATU_AUTH_DISABLED=1` **and** `ENV=production`, so prod can't ship with the auth wall off.

## Tests — what "green" means

- **Backend:** `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q` → **≈4390 passed, 3 skipped** (~6 min) as of 2026-10-05. `conftest` autouse-clears rate-limit buckets between tests.
- **Frontend units:** `cd frontend && npm run test:units` (= `node --test src/lib/*.test.js src/lib/viewerEngine/*.test.js`) → **958 pass** as of 2026-10-05. These use **node:test, not vitest** — running vitest errors "No test suite found."
  - ⚠️ **The bare `src/lib/*.test.js` glob silently skips `src/lib/viewerEngine/*.test.js`.** `*` does not recurse into subdirectories, and the glob still matches plenty of files in `src/lib/` itself, so nothing errors: you get a green run that quietly proves less than you think. `test:units` carries both globs; type both if you call `node --test` yourself.
  - Treat both counts as **drifting**. They are a smell test, not a contract: run the suite and read its own total rather than diffing against a number in a doc.
- **CI:** `.github/workflows/ci.yml` runs the backend suite (Python 3.12, installed from the dev lock) and the frontend units, lint and build on every push and PR to `main` and `viewer-rebuild`. It has **not run yet** — nothing has been pushed since it was added — it does not hold a deploy back by itself, and it does **not** run the eval (the fixture PDFs the eval reads are gitignored; see the regression gate below).
- **Lint:** `cd frontend && npx eslint . --quiet`.
- There is no frontend component-test harness and **no Playwright config in the repo** (no `playwright.config.*`, no `e2e/`) — browser verification is done ad-hoc via the Playwright MCP. **Verify UI changes in a real browser**, not just a type-check.
- **SEO build (opt-in):** `cd frontend && npm run build:seo` — `vite build` + prerenders the **11** public routes (`/`, `/en`, `/about`, `/duk`, `/privacy`, `/terms`, `/cookies` + the 4 BoFu pages) into `dist/<route>/index.html` (pinned `playwright@1.55.1` via npm exec; chromium cached in `~/Library/Caches/ms-playwright`). Default `npm run build` untouched. Spot-check with `python3 -m http.server -d dist` — **`vite preview` skips the directory index files**, so it will misleadingly show the SPA shell.

## Run the extractor on a real PDF ($ + slow)

`cd backend && RUN_ID=x ../venv/bin/python scripts/variance_run.py`
→ loads `.env`, runs `extract_interior` on the Objektas A fixture, dumps `/tmp/opus48_objektas_a_run<id>.json`.
**~$2.37/project, ~12 min** on the Opus 4.8 full pipeline (voting + zoom + readers). That's the real per-project COGS — don't re-run casually.

## Measure accuracy BEFORE claiming an accuracy change works

Ground truth = ONE contractor's real sąmatos: six scored projects, `ground_truth/objektas_a`–`d`, `objektas_g`, `objektas_h` (`ground_truth/registry.yaml`; Objektas A's own files also live in `docs/superpowers/fixtures/2026-05-26-objektas-a/`). Every one of them has been developed against.

**What the eval says (2026-10-05, `venv/bin/python eval_harness.py --totals-only --recompute`, zero API):**
- **There is no blind project.** Every number is measured on drawings the engine was developed against, and the output says so first. objektas_g/h were blind for ONE run on 2026-09-05 (`blind_result` in the registry) and have been tuned on since: the „out-of-sample" line that printed until 2026-10-05 was in-sample (audit testing-eval-1). How a real blind batch is added and scored once per release candidate (`--blind-once`): [`docs/superpowers/plans/2026-10-05-blind-batch-protocol.md`](superpowers/plans/2026-10-05-blind-batch-protocol.md).
- **Headline — his billed lines: 22,60 %** mean |error| over 31 family observations on six projects (a 6,21 · b 18,07 · c 36,29 · d 16,22 · g 56,83 · h 17,12 %). Families: paint (sienos + lubos), kampai, angokraščiai, GKP lubos, Rotband, plytelės — Σ of his rows against Σ of ours per family, through the same frozen concept table as `--rows`. A family he bills and we do not produce counts as −100 %.
- **Copied, not measured** (listed, in no new average): a metric whose truth and our value are the same figure printed on the drawing — ceilings on a/b/d/h and the floor total on a/h (the truth was taken from the room table's printed total, and our figure equals that total — mostly because the engine bills it), and d's GKP lubos. Where the walls are billed at the designer's legend (g, h), the engine's own Σ-room walls are printed beside them.
- **Legacy totals MAE** (walls / ceilings / LED / floor, the headline until 2026-10-05, kept so history compares): 9,47 % on a–d (4 of its 13 points copied), 7,06 % on g/h (2 of 5 copied).
- **His rows within ±10 %** (`--rows --recompute`): 28,2 % over the six (27,5 % over a–d, the figure before g/h were relabelled).
- **Caveats:** one contractor's conventions; each project's Vision read was saved once, and the eval re-runs today's deterministic engine on that saved read — reading variance and reader changes are not in these numbers (a paid `--vision` run measures them); every engine input is Vision-derived. The row-scorecard holdout is empty (its project has no extract) and the harness says so.

Founder rule (2026-09-05): the engine computes from the drawing; a sąmata is used only to CHECK afterwards — never tune a rule, default or factor until it matches his number.

Ceilings are anchored to the eksplikacija total — or, when a drawing prints no table, to the sum of the room areas written on the plan (`backend/extractor/plan_area_annotations.py`, Step 2.44; `scripts/backfill_plan_areas.py --refresh-lane --refresh-author` for cached extracts). **Text-layer gotcha:** pdfplumber takes a minute per page on a 20 MB drawing (pdfminer parses the object streams the renders live in) — that module reads with pypdfium2 (0.6 s for the whole sheet set), every text direction in its own frame, boxes mapped into the display frame; do not add another pdfplumber pass to the live pipeline without timing it on `objektas_g`. Row scorecard: `--rows --recompute --detailed`; the paint family is four leaves (Sienų/Lubų × iki/virš 3 m) + five parents in his aggregations — a change to the concept table is a mapping change (it moves the headline too): diff the per-row table before/after and report it.

**Scope is server-side (2026-09-06).** The contractor's „ką skaičiuoti" (`_apimtis`: rooms, families, ceilings, wall area) is enforced in `extractor/scope.py` on every compute path; a frontend sender that posts overrides must fold it in with `rulesWithScope` (lib/scope.js) or a Prielaidos edit silently un-scopes the sąmata. An excluded room is kept and marked `_neskaiciuoti` — never deleted — and the ceiling anchor subtracts it as its own roll-up step. `tests/test_scope.py` is the contract.

**Regression gate (2026-09-29).** The plain exit code of `--totals-only` is 1 on every run (the old 2 % cap) — ignore it. Run `venv/bin/python eval_harness.py --totals-only --recompute --gate` and `... --rows --recompute --gate`: exit 1 only when a project or metric is missing, or a metric is worse than `ground_truth/eval_baseline.json` by more than 0,25 pp (totals error) / 1,0 pp (rows ±10 % share); improvements are printed and never fail.
- The totals gate holds, per project, `billed MAE` and every `billed · <family>` first, then `legacy MAE` and the legacy metrics (2026-10-05). Copied ones are gated too: they are in no new average, but a copy that stops matching is a regression.
- Accept a new baseline (`--totals-only --recompute --accept-baseline`, then the same with `--rows`) only when a change is MEANT to move the numbers and you have read every WORSE/BETTER line — commit the JSON diff with the change and say why in the message.
- Never accept to make a red gate green. The file is tracked and holds codenames and numbers only.
- It needs the gitignored fixture PDFs (height markers, legend, door schedule read them), so it runs locally, not in CI: a tracked-only checkout scores objektas_a/d differently.
- `--replay-geometry` (with `--recompute`) re-runs only the paid pipeline's €0 drawing lanes (plan text scan and its stated heights/area labels/anchors, rectangle pairs, raster outlines, the geometry lane, then the polygon prepass, stored zoom answers and niche inference) on each frozen extract before the tail, after taking back what older lane versions froze in, and prints per project what changed — no Vision call. It is not the default eval and never the baseline (`--accept-baseline` refuses it): run it with `--gate` to see how far a lane change moves the numbers; `tests/test_golden_replay_extract_interior.py` holds it equal to production's `extract_interior` on objektas_h.

**RULE: never change *billed quantities* without measuring against these.** Neither the formulas nor the reads are "solved": fed objektas_a's hand-entered room dimensions (`--use-gt-inputs`, the only project that has them, some back-derived from his sąmata — see ARCHITECTURE.md › Known fragilities), walls still read −7,4 % and combined paint −5,4 % (2026-10-05). An unverified formula "fix" is a regression risk.

**Provenance is an accuracy invariant too (2026-09-02).** Any change to the builder must keep `backend/tests/test_contribution_ledger.py` green — it replays every row's `roll_up` over its `contributions` on all corpus fixtures and fails if the ledger stops reproducing `kiekis`. If you wire a new family into the ledger, add it there (and to the LT-string vocabulary guard). To eyeball Patikra locally: start `backend-dev` + `frontend-dev` from `.claude/launch.json` (restart the backend after backend edits — no `--reload`), open a local project, toggle anything in Prielaidos (the rebuilt list carries ids + ledger), then click a row → tree, and use the right-hand PATIKRA rail (card → „Pataisyti" → Prielaidos focus → recompute → „Perskaičiuota: N eilučių" → „Įsiminta"). The shipped demo snapshot carries no ledger on disk until it is recomputed.

**To eyeball the contractor's own layout (2026-09-05):** the switch („Pathon" | „Kaip mano sąmatose") appears on the Sąmata step only when the dev account has a template. Seed one from the gitignored parsed sąmatas — never from anything that could carry a client name into a tracked file:

```bash
venv/bin/python -c "import json;print(json.dumps({'name':'Mano sąmatos šablonas','is_default':True,'samatas':[{'slug':s,'line_items':json.load(open(f'ground_truth/{s}/contractor_samata_parsed.json'))['line_items']} for s in ['objektas_a','objektas_b','objektas_c','objektas_d']]},ensure_ascii=False))" > /tmp/seed_template.json && curl -s -X POST http://localhost:8000/api/samata-templates -H 'Content-Type: application/json' --data-binary @/tmp/seed_template.json | head -c 200
```

Then: Sąmata → switch → type into a blank cell (becomes an `rnk-` row in `darbu_sarasas`), „Teisinga" on a greyed suggestion (stamps the source rows), Eksportuoti → „Excel — kaip mano sąmatose"; Patikra → last page → „Jūsų eilutės". `DELETE /api/samata-templates/{id}` removes the seed. The render is a view — `POST …/samata-render` never writes.

## Deploy / billing (dev-relevant bits — full launch steps in `RUNBOOK.md`)

- `BILLING_ENABLED` defaults `'0'` (dormant). Don't flip without the pre-flight: Stripe secret + webhook secret + price IDs present, webhook signature verified live, and `usage_events` logging confirmed (a silent-fail there could let a user drain the API budget uncharged).
- Prod needs `R2_*` env vars (PDF + DB-backup storage); `.env` is gitignored → set on the host.
- Nightly DB backups are checked (`PRAGMA integrity_check`) before upload, their outcome shows in the admin cockpit's health panel, and old ones are **never deleted** until `SAMATU_BACKUP_KEEP_DAYS` is set — a founder decision; `scripts/report_backup_retention.py --days N` shows what a value would delete. Details: `RUNBOOK.md` §2a.
- All work is on `viewer-rebuild`; nothing auto-deploys.

## Housekeeping gotchas

- **A response key that starts with `_sa` never reaches the browser.** FastAPI's
  `jsonable_encoder` runs with `sqlalchemy_safe=True` and silently drops every dict
  key beginning with `_sa` (meant for SQLAlchemy's `_sa_instance_state`). A row flag
  named `_salyga` was on the row right up to `return` and absent in the JSON
  (2026-09-08, an hour lost). Name private row keys anything else (`_only_while`).

- Real listeners: `lsof -nP -iTCP -sTCP:LISTEN | grep -E "python|node"`.
- The "N running tasks" panel can show **zombie agents** (40 h+ timers = finished-but-not-cleared). They cost nothing and clear on app/session restart.
- Spun-off task-sessions live in `.claude/worktrees/*` on their own branches, sometimes based on an **older** commit than `viewer-rebuild` — merge their results forward deliberately, don't assume a clean fast-forward.

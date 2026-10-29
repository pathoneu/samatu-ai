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
- **Email (v3 M2, 2026-10-18) — provider-agnostic, console by default.** `backend/email_sender.py`: no `SMTP_HOST`+`SMTP_FROM` → the console backend (dev logs the whole message, so the link is clickable from the backend log; `ENV=production` logs only recipient domain + subject, sends nothing). Any SMTP relay → set `SMTP_HOST/PORT/USER/PASSWORD/FROM` (3 attempts). Routes in `backend/api/auth_email.py`: forgot / reset password (1 h, single use, hashed, spends older links, logs every other device out), verify / resend (48 h), at most 3 links per account per hour, the same answer whether or not an account exists. Pages: `/pamirsau-slaptazodi`, `/slaptazodzio-keitimas?token=`, `/el-pasto-patvirtinimas?token=` (`pages/AuthEmailPages.jsx`); the login page shows the reset link only when `GET /api/auth/email-status` says a link can reach the person, else the old write-to-us link. **Gate:** `SAMATU_REQUIRE_EMAIL_VERIFIED=1` → register starts no session and password login answers 403 `email_not_verified` (after the password matched) until the link is opened; default 0 = today's behaviour. Always on, no mail needed: Google sign-in requires Google's `email_verified` and never merges into a password account whose inbox was never proven (audit -9); an address on `SAMATU_ADMIN_EMAIL` becomes admin only once verified — by our link or by Google (audit -6). Users that predate this have `email_verified_at` NULL. Tests: `tests/test_auth_email.py`.

## Tests — what "green" means

- **Backend:** `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q` → **≈4390 passed, 3 skipped** (~6 min) as of 2026-10-05. `conftest` autouse-clears rate-limit buckets between tests.
- **Frontend units:** `cd frontend && npm run test:units` (= `node --test src/lib/*.test.js src/lib/viewerEngine/*.test.js`) → **958 pass** as of 2026-10-05. These use **node:test, not vitest** — running vitest errors "No test suite found."
  - ⚠️ **The bare `src/lib/*.test.js` glob silently skips `src/lib/viewerEngine/*.test.js`.** `*` does not recurse into subdirectories, and the glob still matches plenty of files in `src/lib/` itself, so nothing errors: you get a green run that quietly proves less than you think. `test:units` carries both globs; type both if you call `node --test` yourself.
  - Treat both counts as **drifting**. They are a smell test, not a contract: run the suite and read its own total rather than diffing against a number in a doc.
- **CI:** `.github/workflows/ci.yml` runs the backend suite (Python 3.12, installed from the dev lock) and the frontend units, lint and build on every push and PR to `main` and `viewer-rebuild`. It has **not run yet** — nothing has been pushed since it was added — it does not hold a deploy back by itself, and it does **not** run the eval (the fixture PDFs the eval reads are gitignored; see the regression gate below).
- **Lint:** `cd frontend && npx eslint . --quiet`.
- There is no frontend component-test harness. Browser verification of a change is done in a real browser (the Playwright MCP); the one scripted browser suite is the E2E smoke below. **Verify UI changes in a real browser**, not just a type-check.
- **E2E smoke (founder guide).** `frontend/e2e/founder-guide.spec.js` walks the founder's localhost review guide (`docs/superpowers/plans/2026-10-16-togal-v2-program.md` › „Founder review on localhost") on `demo-objektas_h` — one test per guide step 1–10 plus „Versijos" and the Sąmata export previews, asserting the guide's numbers (04 = 26,31 + 35,50 = 61,81 m², lubos 143,27, kampai 475,66 → 489,76 → 501,04 → 495,40 …); `workspace-frame.spec.js` (W1-A) runs with it. It starts nothing — bring up a backend with the auth wall off and a Vite pointing at it, then run the suite:
  ```bash
  cd backend  && SAMATU_AUTH_DISABLED=1 ../venv/bin/uvicorn main:app --port 8121
  cd frontend && VITE_BACKEND_URL=http://localhost:8121 npm run dev -- --port 5201   # in a worktree: own Vite cacheDir, see the v3 programme doc
  cd frontend && npm run test:e2e        # other ports: E2E_BASE_URL=… E2E_API_URL=…
  ```
  Playwright is not a dependency: the script runs the pinned `playwright@1.55.1` through `npm exec` (same as `build:seo`); `e2e/pw.js` resolves `playwright/test` from it. The suite writes to the database it runs against and puts it back: global setup takes a pristine snapshot of `backend/data/samatu.db` with the SQLite online-backup API (`sqlite3 … .backup`, consistent while the backend runs) plus a copy of `pdf_store`, derives the guide's start state (the newest stored version with 04 not merged and no confirmed scale, restored through the versions route) into `e2e/.state/start.db`; every test restores that with `sqlite3 … .restore` and proves it (every table identical, the project's numbers read back through the API); teardown restores the pristine snapshot the same way. Never `cp` over the live WAL database. Screenshots land in `e2e/__screens__/` (gitignored), a table of the asserted numbers prints at the end. Step 9 builds a synthetic second edition with `e2e/make_revision.py` (pikepdf from the repo venv; `E2E_PYTHON` overrides). No Vision call, no paid route, no chat message.
- **Two engines: chromium + webkit (Safari).** `playwright.config.js` has two projects: `chromium` runs every spec, `webkit` a smoke subset — `workspace-frame`, founder-guide steps 1–3 and `safari-robustness.spec.js` (no raw translation key on screen, a second react-i18next copy still translates, a 6 MB project cache under Safari's quota, storage blocked outright). One-time install of the engine: `npm exec --yes --package=playwright@1.55.1 -- playwright install webkit` (lands in `~/Library/Caches/ms-playwright/webkit-2203`). One engine only: `npm run test:e2e -- --project=webkit` (or `--project=chromium`). Safari facts the suite guards: WebKit counts localStorage in UTF-16 (~2,5 M characters per origin — a real account's project cache is more; `projectStore` caches the newest that fit), and „Block all cookies" makes the mere `window.localStorage` read throw — use `lib/browserStorage.js`. Components take `useTranslation` from `@/i18n/react`, never `react-i18next` (eslint + `i18nKeys.test.js`): a Vite dev server whose shared `node_modules/.vite` deps were re-optimised under it can serve a second react-i18next copy, and without the explicit instance every t() printed its key.
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

**Public accuracy claims (v3 W7-A M9, 2026-10-18).** A number about accuracy may appear on a public page only if it comes from the human-confirmed corpus (`scripts/build_ground_truth.py` — outlines a person corrected or drew, quantities a person typed over or verified) and says which kind it is: **in-sample** (projects the engine was developed against — every eval project today) or **out-of-sample** (a blind batch scored once, `docs/superpowers/plans/2026-10-05-blind-batch-protocol.md`). The eval harness figures above (22,60 % billed lines etc.) are measured against ONE contractor's sąmatos on in-sample projects — internal, not public. `frontend/src/lib/publicCopyClaims.test.js` fails on a percentage in a sentence about accuracy without that label. On 2026-10-18 `build_ground_truth.py` on the dev database gave 4 confirmed outlines and 9 confirmed quantities — not enough for any public number, and none is published. Public numbers found on that date and their basis:

| Where | Claim | Basis | Verdict |
|---|---|---|---|
| `landing.hero.sub`, `Duk.jsx`, `KiekiaiIsBrezinio.jsx`, `public/llms.txt` | a read takes 15–35 min | v3 "Paid runs log" 25–28 min; audit measured 12–34 min | supported |
| `SamatininkoKaina.jsx` table | „Su Pathon ~1 val. (peržiūra + kainos)" / „~15 min." | no measured time-to-finish (pilot telemetry is thin) | **flag — unsupported, and „~15 min" undercuts the 15–35 min read; founder to reword or drop** |
| `ApvaRenovacijosKiekiai.jsx` table | „Laikas kiekiams … ~15 min. + peržiūra" | same | **flag — same** |
| `KiekiaiIsBrezinio.jsx` | paint area 2,5–4 × floor area; a wrong scale drifts lengths 10–20 %; tile waste +10–15 % | CLAUDE.md §6 check 1, §3 waste table (estimating practice, not our measurement) | domain rule — fine as stated |
| `ApvaRenovacijosKiekiai.jsx` | mesh 1,1 m² (10 %), facade net 15–25 % below gross, roofing +8 %, film ×1,10, class B ≈ 40 % savings | CLAUDE.md §2.1, §6 check 7, §3, Type 4 | domain rule — fine |
| `landing.steps`, `landing.exportSec`, `Duk.jsx` | „21 % PVM eilutė" | the default; 9 % and 0 % are now choosable (M4) | true; founder may add „ar 9 / 0 %" |
| pricing tiers | 0 € / 12 € / 49 € (10 projects) / 149 € (35) | `backend/billing/plans.py` | matches code; price points are the founder's |
| `public/llms.txt` | „promises no accuracy percentage" | — | true |

**Provenance is an accuracy invariant too (2026-09-02).** Any change to the builder must keep `backend/tests/test_contribution_ledger.py` green — it replays every row's `roll_up` over its `contributions` on all corpus fixtures and fails if the ledger stops reproducing `kiekis`. If you wire a new family into the ledger, add it there (and to the LT-string vocabulary guard). To eyeball Patikra locally: start `backend-dev` + `frontend-dev` from `.claude/launch.json` (restart the backend after backend edits — no `--reload`), open a local project, toggle anything in Prielaidos (the rebuilt list carries ids + ledger), then click a row → tree, and use the right-hand PATIKRA rail (card → „Pataisyti" → Prielaidos focus → recompute → „Perskaičiuota: N eilučių" → „Įsiminta"). The shipped demo snapshot carries no ledger on disk until it is recomputed.

**To eyeball the contractor's own layout (2026-09-05):** the switch („Pathon" | „Kaip mano sąmatose") appears on the Sąmata step only when the dev account has a template. Seed one from the gitignored parsed sąmatas — never from anything that could carry a client name into a tracked file:

```bash
venv/bin/python -c "import json;print(json.dumps({'name':'Mano sąmatos šablonas','is_default':True,'samatas':[{'slug':s,'line_items':json.load(open(f'ground_truth/{s}/contractor_samata_parsed.json'))['line_items']} for s in ['objektas_a','objektas_b','objektas_c','objektas_d']]},ensure_ascii=False))" > /tmp/seed_template.json && curl -s -X POST http://localhost:8000/api/samata-templates -H 'Content-Type: application/json' --data-binary @/tmp/seed_template.json | head -c 200
```

Then: Sąmata → switch → type into a blank cell (becomes an `rnk-` row in `darbu_sarasas`), „Teisinga" on a greyed suggestion (stamps the source rows), Eksportuoti → „Excel — kaip mano sąmatose"; Patikra → last page → „Jūsų eilutės". `DELETE /api/samata-templates/{id}` removes the seed. The render is a view — `POST …/samata-render` never writes.

## Deploy / billing (dev-relevant bits — full launch steps in `RUNBOOK.md`)

- `BILLING_ENABLED` defaults `'0'` (dormant). Don't flip without the pre-flight: Stripe secret + webhook secret + price IDs present, webhook signature verified live, and `usage_events` logging confirmed (a silent-fail there could let a user drain the API budget uncharged).
  - **The pre-flight is a script (2026-10-18):** `venv/bin/python scripts/billing_preflight.py` in the environment that is about to flip — read-only, no network; prints env NAMES (never values), the key's test/live mode, an offline signature self-test through `stripe_client.construct_event`, `usage_events` rows of the last 7 days (DB opened read-only), the spend guards (`SAMATU_USER_DAILY_SPEND_EUR` must be > 0) and which invoice VAT branch applies, then the manual checks (webhook subscriptions incl. `checkout.session.async_payment_succeeded/_failed`, delayed payment methods, accountant, prices). Exit 1 until every scripted check passes.
  - **Money only when it arrived (audit backend-security-7):** a one-off credit and its PVM invoice are granted only for `payment_status == "paid"`; an "unpaid" session (SEPA, bank transfer) waits for `checkout.session.async_payment_succeeded`, `_failed` grants nothing. An unpaid subscription is stored as `plan_status = "incomplete"` and reads as the free tier (`billing/entitlements._plan`) until Stripe reports it active; a €0 `invoice.paid` (trial) emits no invoice. Tests: `tests/test_billing_payment_status.py`.
  - **Tier gates:** `entitlements.require_feature(user, feature)` → 403 `feature_not_in_plan` with a plain message; wired on the F2/F3 routes (`f2f3_export`), after ownership. Quota / trial 402s say what is used, of how much, and when it renews (`quota_message`). All of it is a no-op while the flag is off.
  - **Invoice VAT rule as coded (audit backend-security-8, NOT changed — accountant to confirm):** `billing/invoice.build_invoice_fields` → (1) buyer typed any `pvm_code` → reverse charge, no VAT line, note „Atvirkštinis PVM (PVMĮ 96 str.)" — applied even to an LT buyer and even when Pathon itself is not VAT-registered; (2) else Pathon has no `PATHON_COMPANY_PVM` → „Pardavėjas nėra PVM mokėtojas", no VAT; (3) else 21 %. The likely-correct rule (21 % for LT buyers once Pathon is registered; reverse charge only for other-EU VAT-registered buyers, format/VIES checked) is the accountant's call. Buyer fields are now escaped before reportlab lays them out.
- Prod needs `R2_*` env vars (PDF + DB-backup storage); `.env` is gitignored → set on the host.
- **Symbol-training crops (v3 M8, 2026-10-18)** live under `SAMATU_DATA_DIR/symbol_training` (unset → the legacy `data/symbol_training`), one folder per project; `DELETE /api/projects/{id}` and account deletion remove them (`training_data.purge_project`, also the pre-M8 root-level crops whose log line names the project). Account deletion also removes the per-owner architect legends (`project_purge.purge_account_files`, `<legends>/architect/<user id>/`). On 2026-10-18 the main checkout held 3 legacy crops; prod's are on the container disk and die with each deploy until `SAMATU_DATA_DIR` is set.
- Nightly DB backups are checked (`PRAGMA integrity_check`) before upload, their outcome shows in the admin cockpit's health panel, and old ones are **never deleted** until `SAMATU_BACKUP_KEEP_DAYS` is set — a founder decision; `scripts/report_backup_retention.py --days N` shows what a value would delete. Details: `RUNBOOK.md` §2a.
- All work is on `viewer-rebuild`; nothing auto-deploys.

## Limits (v3 W7-A M7, 2026-10-18)

What the app refuses or warns about, where it lives, and the measurement behind each number.

| Limit | Value | Where | Basis |
|---|---|---|---|
| Uploaded PDF size | 200 MB | `main.MAX_PDF_SIZE_BYTES`, `_validate_pdf_upload` | magic bytes + size, before parsing |
| Pages a paid read sends | 100 | `main.py` (MAX_PAGES note), Vision pipeline | Anthropic request limit |
| Page dimensions | ≤ 4320 pt edge, ≤ 11,52 M pt² area | `_MAX_PAGE_DIM_PT`, `_MAX_PAGE_AREA_PT2` | ≈ 200 MP at 300 DPI; page 1 only (audit -19 open) |
| Paid interior read time | 25–28 min typical (12–34 min in the 2026-09-29 audit) | `/extract-interior-stream`, no overall server timeout; 10 s keepalive, survives a dropped stream | programme "Paid runs log" |
| Other extract routes | 900 s timeout | `/extract`, facade / roof / earthworks / concrete | `asyncio.timeout(900)` |
| Paid reads per user per hour | 20 (`SAMATU_USER_HOURLY_EXTRACTS`; 0 = off) | `_check_user_spend_cap` | env; € daily cap `SAMATU_USER_DAILY_SPEND_EUR` defaults 0 = off |
| Default per-client rate | 30 / min per bucket | `_check_rate_limit` | sliding 60 s window, keyed by `_client_key` |
| `/recompute-interior` | 120 / min per client, ≤ 500 rooms per call | `RECOMPUTE_INTERIOR_PER_MIN` | measured below |
| Emailed links | 3 per purpose per account per hour | `api/auth_email.MAX_LINKS_PER_HOUR` | on top of the per-IP bucket |
| Telemetry session | ≤ 2000 gestures | `api/telemetry.MAX_GESTURES` | — |
| Measurements on one sheet | warning at 1500 (never blocked) | `frontend/src/lib/measureLimits.js` | measured below |

**Measurements per sheet** (headless Chromium 1440×900 on the dev Mac, demo-objektas_h sheet 1, a mix of areas / lines / perimeters / counts; open time, then 40 pans + 16 Ctrl-wheel zooms, rAF frame gaps and long tasks; script `m7_measure.mjs` in the W7-A scratchpad, numbers copied here):

| Measurements | Drawing + overlay on screen | Slowest frame | p95 frame | Long tasks (longest) | JS heap |
|---|---|---|---|---|---|
| 0 | 1,1 s | 17 ms | 17 ms | 0 | ≈ 100–140 MB |
| 1000 | 1,2 s | 50 ms | 17 ms | 0 | 131 MB |
| 2000 | 1,3 s | 117 ms | 17 ms | 2 (74 ms) | 148 MB |
| 4000 | 1,8 s | 250 ms | 17 ms | 4 (142 ms) | 177 MB |
| 8000 | 2,7 s | 533 ms | 67 ms | 19 (317 ms) | 239 MB |

The first stutter a person notices (a frame over 100 ms) appears between 1000 and 2000 here, sooner on a slower laptop: the warning fires once per sheet at 1500.

**`/recompute-interior`** (local single uvicorn worker, auth off, `m7_recompute_timing.py`): 11 rooms (demo-objektas_h) p50 50 ms, ~20 calls/s max; 8 parallel callers → p50 485 ms each. 110 rooms p50 391 ms, 2,5 calls/s; 8 parallel → p50 3,6 s. It is CPU-only and every room edit calls it, and production runs one worker for everyone, so a loop from one client could stall everybody. Decision: its own bucket of 120/min per client (2/s, far above a person editing rooms); the 500-room cap bounds one call. Residual: a client sending 500-room payloads at 2/s could still keep a worker busy — a per-user CPU budget is the next step if that is ever seen.

## Housekeeping gotchas

- **A response key that starts with `_sa` never reaches the browser.** FastAPI's
  `jsonable_encoder` runs with `sqlalchemy_safe=True` and silently drops every dict
  key beginning with `_sa` (meant for SQLAlchemy's `_sa_instance_state`). A row flag
  named `_salyga` was on the row right up to `return` and absent in the JSON
  (2026-09-08, an hour lost). Name private row keys anything else (`_only_while`).

- Real listeners: `lsof -nP -iTCP -sTCP:LISTEN | grep -E "python|node"`.
- The "N running tasks" panel can show **zombie agents** (40 h+ timers = finished-but-not-cleared). They cost nothing and clear on app/session restart.
- Spun-off task-sessions live in `.claude/worktrees/*` on their own branches, sometimes based on an **older** commit than `viewer-rebuild` — merge their results forward deliberately, don't assume a clean fast-forward.

## Engine flags (v3 W5-E) — all default off

Each changes billed or material quantities only when set to `1`; with all of them unset every gate pass is
identical to baseline. The manager / founder decides each one on the measured report.

| Flag | What it does | Status |
|---|---|---|
| `SAMATU_WASTE_BY_PATTERN` | tile / floor-covering waste by the laying pattern the drawing writes, paint +7 % (`extractor/waste_pattern.py`); material names stay stable | off, founder decides |
| `SAMATU_BATH_DRAIN_ROWS` | „Vonios montavimas" from the tub-only count; „Trapų montavimas" from `parsed["_legendos_kiekiai"]` (`extractor/fixture_rows_flag.py`, contract in its docstring) | off |
| `SAMATU_WALLPAPER_ROLLS` | wallpaper rolls for walls whose finish reads „tapetai" (`extractor/wallpaper_flag.py`) | off |
| `SAMATU_NICHE_DEPTH` | niche finishing in m² = metres × depth × 3 (`extractor/niche_depth.py`) | **never default-on**: every contractor bills niche finishing in metres |
| `SAMATU_FURNITURE_ZONES` | furniture zones off the paintable walls; panels are information only (`extractor/wall_zones.py`) | off |
| `SAMATU_REREAD_FIGURES` (v3 W5-D D6) | the lane also runs step 2.44: designer's figures, the walls / floors anchors from them, room heights the plan states (`api/free_reread.read_figures_and_heights`). Reaches the product only through the paid re-read now (the free re-read was removed 2026-10-29). | off — on stored objektas_h it adds a 320 m² walls anchor the project lacks |
| `SAMATU_DEV_TOOLS` (2026-10-29) | mounts the `/api/projects/{id}/free-reread` route for `scripts/` and tests; the product no longer exposes it (`api/free_reread.py`, decision in `docs/superpowers/research/2026-10-29-remove-free-reread.md`) | off in prod; the pytest conftest sets it to `1` for all tests |
| `SAMATU_DIM_LINE_TICKS` (v3 W5-D D8) | a dimension string's evidence line (`line_pct`) ends where the drawn line ends, without the stroke caps (`extractor/dimension_sum._drawn_ends`); no perimeter moves | off, four passes identical with it on |
| `SAMATU_VISION_LEGEND` (v3 W5-D D4/D5) | the PAID raster legend / schedule readers (`api/vision_readers.py`), each run with its own OK and cost | off ("0"); a paid run needs the founder's OK |


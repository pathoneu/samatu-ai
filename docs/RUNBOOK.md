# Pathon — production launch runbook

**Audience:** Pathon owner / DevOps. The CLI agent cannot reach DNS, billing,
or hosting consoles, so this is the manual checklist for going live.

> **Database reality check (read before anything else):** Pathon has **no
> Postgres**. `backend/db.py` is `sqlite3`-only and `DATABASE_URL` appears
> nowhere in the codebase. The whole app runs off one SQLite file — see §2a.
> Any older text about "managed Postgres" was aspirational and is now removed
> from this runbook. **`render.yaml` still carries the same stale comment in
> its header** ("Postgres can be attached … via `DATABASE_URL`") — ignore it;
> nothing reads that variable.

---

## 0. Prerequisites (one-time)

- [ ] Anthropic API key with spending limit set (recommend €100/mo).
      Console: https://console.anthropic.com/settings/keys
- [ ] (Optional, for Google login) Google Cloud OAuth 2.0 client.
      https://console.cloud.google.com/apis/credentials
- [ ] Pathon registrar access for DNS records.
- [ ] Cloudflare account (free tier OK) — DDoS + auto-TLS + DMARC dashboard.
- [ ] Cloudflare R2 bucket + API token (PDF storage **and** the nightly DB
      backup — see §7). Without the `R2_*` vars there are no backups at all.
- [ ] Hosting platform decision. The repo ships configs for exactly two:
      **Render** (`render.yaml`) and **Railway** (`railway.toml` +
      `nixpacks.toml`). There is **no Fly.io config** — ignore older advice
      to use it. See §2 for the one difference that actually matters
      (system packages).

## 1. Pick a domain target

Canonical, and what ships today: the **apex `pathon.eu`** for the frontend.
(`samatu.pathon.eu` / `samatu-api.pathon.eu` were the pre-rebrand plan — do
not use them.) The **API host** is whatever the platform assigns
(e.g. `samatu-api.onrender.com`) unless you configure a custom domain for it.
Whichever you end up with: `SAMATU_CORS_ORIGINS` must equal the **real
frontend origin**, exactly, or the browser blocks every API call.

## 2. Hosting setup — Render.com path

**Deploys track the repo's GitHub default branch (`main`), not your working
branch.** Active development lives on `viewer-rebuild`. Fast-forward `main`
to the branch you want live before deploying, or Render will happily ship
months-old code and report a green deploy.

1. Sign up at render.com using your Pathon Google account.
2. Click **New → Web Service** (or point Render at `render.yaml` as a Blueprint —
   the blueprint already declares everything in steps 3–8).
3. Connect this GitHub repo (or push from local — Render supports both).
4. **Runtime: Docker.** The repo ships `backend/Dockerfile` (build context =
   repo root; the blueprint wires `dockerfilePath` + `dockerContext`). Do NOT
   pick the native Python runtime — it cannot install the native libs
   extraction hard-depends on (see the ⚠️ below). The image installs the
   pinned `backend/requirements.lock` (no test packages), not
   `requirements.txt`.
5. **Build/start commands: none to enter** — the Dockerfile bakes both. The
   baked start command is:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips='*'
   ```
   `--proxy-headers --forwarded-allow-ips='*'` is **not optional**: the per-IP
   login/register rate limiter keys on the **rightmost `X-Forwarded-For` hop**
   (2026-07-15 hardening). Drop the flags and every request looks like it came
   from Render's proxy — one abuser then locks out everyone's auth. `'*'` is
   safe here because the service is only reachable via Render's edge. If you
   ever override the start command in the dashboard, carry the flags with you.
6. **Region:** Frankfurt (closest EU).
7. **Instance type:** Starter ($7/mo).
8. **Persistent disk** — the blueprint declares a 1 GB disk mounted at `/data`
   with `SAMATU_DB_PATH=/data/samatu.db`; on a manual (non-blueprint) setup
   you must attach it yourself — see §2a. Skipping this is the single most
   destructive mistake available: every deploy silently wipes all users and
   projects.
9. Add the env vars (see §4).

⚠️ **System packages.** `pdf2image` needs the **poppler** binaries and
`opencv-python-headless` needs **libglib2** (plus `libgl1` for parity with
Railway) at runtime. This is WHY the blueprint uses the Docker runtime:
`backend/Dockerfile` apt-installs `poppler-utils`, `libglib2.0-0` and
`libgl1` — the same set Railway's `nixpacks.toml` declares. A native-Python
Render service has no apt step, and the failure mode is loud but late:
extraction returns *"Nepavyko konvertuoti PDF — įdiekite poppler (pdf2image)"*
at the first upload, long after the deploy went green. Verify with a real PDF
upload in the §5 smoke test, not with `/health`.

For the **frontend**:
1. **New → Static Site**
2. Connect same repo.
3. **Root directory:** `frontend`
4. **Build:** `npm install && npm run build`
5. **Publish dir:** `dist`
6. Add `VITE_BACKEND_URL=<the real backend origin>` (the blueprint currently
   ships `https://samatu-api.onrender.com`).

## 2a. The database — one SQLite file, and how not to lose it

- `backend/db.py` is **`sqlite3`-only**. Path: `SAMATU_DB_PATH`, defaulting to
  **`backend/data/samatu.db`**. 10 tables (users, projects, extractions,
  usage_events, corrections, consumed_trials, billing_usage, webhook_events,
  invoices, admin_audit_log).
- On Render/Railway the container filesystem is **ephemeral**. You **MUST**
  attach a persistent disk and mount it over `backend/data` (or mount it
  elsewhere and point `SAMATU_DB_PATH` at it, e.g. `/data/samatu.db`).
  Without that, the DB is recreated empty on every deploy and restart.
- **Backups:** `backend/backup_scheduler.py` runs a nightly in-process
  snapshot (default 03:15 UTC; `SAMATU_BACKUP_HOUR_UTC` /
  `SAMATU_BACKUP_MINUTE_UTC`). It is **default-on in prod** — enabled
  automatically when `R2_BUCKET` is set, or explicitly via
  `SAMATU_NIGHTLY_BACKUP=1`. It uploads to the R2 bucket as
  **`backups/samatu-<utc-stamp>.db`**. It runs in-process on purpose: on
  Render a separate cron service cannot see this service's disk.
- **Every snapshot is checked before upload** (2026-10-05): `PRAGMA
  integrity_check` on the copy; one that fails is **not uploaded** and the
  night is recorded as failed. The outcome of the last attempt (time, ok /
  failed, key, size, error) and of the last good one is kept in the database
  (`app_state`, key `backup_last_outcome`), so a deploy no longer blanks it.
- **Watch it in the admin cockpit** (`/admin` → Sistema → „Atsarginė DB
  kopija"). It turns red when there is no good snapshot, the last good one is
  older than 26 h, the latest attempt failed, or the nightly backup is off. It
  also says where files are stored (R2 or this server's disk).
- **Retention is OFF until someone chooses it.** With
  `SAMATU_BACKUP_KEEP_DAYS` unset or empty — the default — no snapshot is ever
  deleted, which also means a deleted account's data lives on in old
  snapshots. Set it to N (whole days ≥ 1) and, after each night whose own
  snapshot was stored, snapshots taken more than N days ago are deleted —
  except the **newest 7, which are always kept** whatever their age. Only keys
  named exactly `backups/samatu-<YYYYMMDDTHHMMSSZ>.db` are ever touched; any
  other file under `backups/` is left alone. Before setting N, see what it
  would delete (read-only, never deletes):
  `python scripts/report_backup_retention.py --days N` — with the production
  storage selected (`STORAGE_BACKEND=r2` plus the four `R2_*` vars, or inside
  the container). An invalid value (`0`, `abc`) also means no pruning, logged
  as a warning.
- **There is NO automated restore.** Restoring is manual: download the chosen
  `backups/samatu-<stamp>.db` object from the R2 bucket, stop the service,
  replace the file at `SAMATU_DB_PATH`, restart. Nothing in the codebase does
  this for you — rehearse it once before you need it.
- Run a single uvicorn worker. N workers = N identical snapshots per night
  (harmless, just redundant).

## 2b. Hosting setup — Railway path (the alternative that's already wired)

`railway.toml` + `nixpacks.toml` at repo root are complete and current. The
build creates a venv at `/opt/venv`, installs the pinned
`backend/requirements.lock` (`--no-deps`, then `pip check` — the Dockerfile
does the same; see `DEVELOPING.md` › Python dependencies), and —
the reason to prefer it — **declares the native deps Render doesn't**:
`poppler_utils` (nixPkgs) plus `libgl1` + `libglib2.0-0` (aptPkgs). The start
command carries the same `--proxy-headers --forwarded-allow-ips='*'` flags;
health check is `/`. Same rules otherwise: attach a **Volume**, point
`SAMATU_DB_PATH` at its mount (e.g. `/data/samatu.db`), set the §4 env vars.

## 3. DNS records on Pathon registrar

Frontend on the apex, API on whatever host the platform gives you.

```
pathon.eu                 A     <render-frontend-ip>      (or ALIAS/CNAME flattening)
www.pathon.eu             CNAME pathon.eu
```

Or use Render-provided CNAMEs if no static IPs. If you give the API its own
custom domain, add it here too **and** update `SAMATU_CORS_ORIGINS` +
`VITE_BACKEND_URL` + `GOOGLE_REDIRECT_URI` to match.

If using Cloudflare in front:
```
pathon.eu                 CNAME proxy → samatu-web.onrender.com
```

## 4. Environment variables (backend)

Set in Render dashboard → Environment:

```bash
# Required
ENV=production
ANTHROPIC_API_KEY=sk-ant-...
SAMATU_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(48))">

# Admin allowlist — comma-separated emails (case/whitespace tolerant).
# SET THIS. If it is unset or empty, the backend falls back to legacy
# behaviour: the FIRST account registered on a fresh DB becomes admin.
SAMATU_ADMIN_EMAIL=solutions@pathon.eu

# Cost protection
SAMATU_USER_DAILY_SPEND_EUR=0.50
SAMATU_USER_HOURLY_EXTRACTS=10

# CORS — exact frontend origin(s), comma-separated. Must match reality.
SAMATU_CORS_ORIGINS=https://pathon.eu

# Database — SQLite file. Point at the PERSISTENT DISK mount (§2a). Must
# match the disk mountPath the blueprint declares (/data in render.yaml).
SAMATU_DB_PATH=/data/samatu.db

# Storage + backups (Cloudflare R2). All four required, or PDFs fall back to
# local disk and the nightly DB backup never runs.
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=samatu-pdfs

# Backup retention in days — UNSET on purpose until the founder chooses (§2a).
# Unset/empty = no backup is ever deleted. When set, the newest 7 always stay.
# SAMATU_BACKUP_KEEP_DAYS=

# Optional — Google OAuth. Redirect URI must match the real API origin.
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://<api-host>/api/auth/google/callback
```

**Boot-time guards (the app refuses to start rather than run insecure):**
- `ENV=production` + `SAMATU_SECRET_KEY` unset (or left at the dev fallback)
  → **FATAL, process exits.** Every session cookie would be forgeable.
- `ENV=production` + `SAMATU_AUTH_DISABLED=1` → **FATAL, process exits.**
  `SAMATU_AUTH_DISABLED` is a dev-only bypass; it must never reach prod.

CRITICAL: never commit `.env`. Render's secret manager handles this safely.
`render.yaml` declares every key above — `SAMATU_DB_PATH` ships its value
(`/data/samatu.db`, matching the blueprint's disk mount); the rest are
`sync: false`, so a Blueprint sync prompts for their values in the dashboard
(no secret ever lives in the repo).

## 5. Smoke test (after first deploy)

From your laptop, with browser DevTools open:

1. Open `https://pathon.eu/`
   → Expected: the Pathon landing page (no "Sąmatų AI" branding anywhere).
2. **Before sharing the URL with anyone:** register the founder account
   yourself, and make sure `SAMATU_ADMIN_EMAIL` already lists that email.
   Belt and braces — the allowlist is the real control (2026-07-15
   hardening, commit `5adac1c`); pre-registering also closes the legacy
   first-user-wins path if the allowlist is ever cleared. Do not rely on
   "whoever registers first is admin": on a public URL that is a stranger.
3. Open **DevTools → Application → Cookies** — verify `samatu_session`
   has `Secure` + `HttpOnly` flags ticked, `SameSite=Lax`.
4. Open **DevTools → Network** for a backend request — verify response
   headers contain `Strict-Transport-Security`, `Content-Security-Policy`,
   `X-Frame-Options: DENY`.
5. Upload a small test PDF — verify extraction returns without a
   *"įdiekite poppler"* error (that's the §2 native-package check) and
   completes. This is slow: budget minutes, not ~30s.
6. Visit `/admin` as the founder account — must show the stats dashboard.
7. Open in incognito → register a SECOND test user → visit `/admin` →
   must redirect to `/dashboard` (non-admin can't see admin). If the second
   user *does* get admin, `SAMATU_ADMIN_EMAIL` is not set — fix immediately.
8. Confirm the DB survives a deploy: redeploy, then log in again. Still
   there = the persistent disk (§2a) is mounted correctly. Gone = it isn't.

## 6. Cost monitoring (first week)

- Anthropic console → Usage tab. Daily check first week.
- If a single user exceeds daily cap, the new requests get a friendly LT
  429 ("Pasiekta dienos AI biudžeto riba"). User waits or contacts you.
- If anonymous traffic spikes (shouldn't — auth required), check Render
  logs for the `IP rate limit hit` warnings.

## 7. Post-launch

- **Backups:** there is no managed-DB snapshot service — the only backup is
  the app's own nightly R2 upload (§2a). Verify it: after the first night,
  list the bucket and confirm a `backups/samatu-<stamp>.db` object exists,
  then check the log line `nightly backup ok: ...` and the admin cockpit's
  „Atsarginė DB kopija" block (green, with that key and its size). **Also
  rehearse the manual restore once** — it is not automated, and discovering
  that during an outage is the wrong time.
- **Uptime monitoring:** UptimeRobot free tier — ping every 5 min
  (`/health` is the backend health check path).
- **Error tracking:** Sentry free tier (5k events/mo) — wire later if needed.
- **Email (v3 M2, 2026-10-18):** password reset and email verification are
  built and provider-agnostic: set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
  `SMTP_PASSWORD`, `SMTP_FROM` (any SMTP relay) plus `PATHON_APP_URL`
  (the links point there). Until SMTP is set, nothing is sent and the login
  page keeps the write-to-us link. Only after a test reset email arrives,
  consider `SAMATU_REQUIRE_EMAIL_VERIFIED=1` (no session until the emailed
  link is opened). Provider choice is the founder's.

## 8. Rollback plan

If a deploy breaks production:

1. Render → Deploys tab → previous deploy → **Rollback**. ~30s downtime.
2. If rollback also broken: comment out the broken endpoint, redeploy.
3. Worst case: pause Anthropic API key in console — paid endpoints stop
   returning, app stays available without AI.

## 8a. Deploy checklist — a togal-v2 batch to `main` (v3 W7-A M10, 2026-10-18)

Production today is **Vercel (`app.pathon.eu`) + Railway (`api.pathon.eu`), both auto-deploying from `main`** (Render above is the older path). Every step marked **[founder]** is the founder's: no worker pushes, merges or touches Railway / Vercel.

**Before**

1. **[founder]** Say OK for this batch. Nothing reaches `main` without it.
2. Local gates on the batch head (a worker or the manager runs these and quotes the lines):
   - `cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/python -m pytest -q -p no:cacheprovider` — 0 failed;
   - `cd frontend && npm run -s test:units && npm run -s lint && npm run -s build`;
   - eval gate, both passes identical to the baseline: `venv/bin/python eval_harness.py --totals-only --recompute --gate` and `--rows --recompute --gate` (four passes incl. `--replay-geometry` when a lane changed) — `GATE OK`;
   - `npm run test:e2e` against a local backend + Vite (DEVELOPING.md › Tests).
3. Confidential terms over everything that becomes public with the push: `git diff origin/main...togal-v2 | grep '^+' | grep -v '^+++' | grep -i -F -f backend/.confidential-terms` and `git log origin/main..togal-v2 --format=%B | grep -i -F -f backend/.confidential-terms` must print nothing. Known: commit bad14b7's message carries a denylisted term — **[founder]** decide (rewrite that message or accept) before pushing.
4. **[founder]** Environment, names only (values on the host, never in the repo) — new since `main`: `SMTP_HOST/PORT/USER/PASSWORD/FROM` (optional, email off without them), `SAMATU_REQUIRE_EMAIL_VERIFIED` (leave unset), `PATHON_APP_URL=https://app.pathon.eu` (emailed links, Google return, Checkout), `SAMATU_DATA_DIR` on the volume (symbol-training crops, telemetry, annotations, calibrations). Check: `BILLING_ENABLED` unset or `0`; `SAMATU_USER_DAILY_SPEND_EUR` > 0 is advised (audit -1).
5. Database: every change is additive (`users.email_verified_at`, `email_tokens`), applied on boot; old code ignores them, so a rollback is safe. **[founder]** Make sure last night's R2 backup exists (admin cockpit „Atsarginė DB kopija" green) or take one.
6. **[founder]** CI as a gate: open the PR `togal-v2 → main` and wait for `.github/workflows/ci.yml` to pass; turn on "Wait for CI" in Railway and Vercel and make the CI jobs required checks on `main` (both are settings only the founder can change). CI does not run the eval — step 2 does.
7. **[founder]** Right before merging: `scripts/safe_deploy_check.sh` (needs the Railway CLI logged in) must print `✅ no extraction in flight` — a redeploy kills a running paid read.
8. **[founder]** Merge. Railway and Vercel deploy on their own.

**After — smoke on the production URLs (≈ 10 min, no paid read)**

1. `curl -s https://api.pathon.eu/health` → 200 and `"commit"` = the merged head's short sha.
2. `https://app.pathon.eu/` loads; log in; `/pagalba` opens; the sidebar shows „Pagalba".
3. `/login` → „Pamiršote slaptažodį?": with SMTP set it opens the reset form, without it the write-to-us link — both are correct, depending on step 4.
4. Open an existing project: the drawing renders, Patikra opens, „Nustatymai" opens and closes.
5. Export Excel and PDF with PVM 21 % (and once at 9 %): the totals line says „PVM 9%:" and the sum matches the screen. Internal copy has „Pakeitimų žurnalas".
6. `curl -s https://api.pathon.eu/api/billing/v2/status` → `"enabled": false`.
7. Headers on an API response: `Strict-Transport-Security`, `Content-Security-Policy`, `X-Frame-Options: DENY`.

**Rollback**: Railway → Deployments → the previous deployment → Redeploy; Vercel → Deployments → the previous production deployment → Promote to Production. Additive migrations mean the old code runs on the new database.

Status 2026-10-18: written, not yet run on dev or prod (workers may not touch either); the local gates of step 2 are what W7-A ran.

## 8b. What Privacy / Terms / Cookies promise, against the code (v3 W7-A M11, 2026-10-18)

The legal review itself is the founder's (a lawyer). This is the list of promises the three pages make and what the code on `v3/market-readiness` actually does. **MISMATCH** rows need a founder decision — change the setting or change the text.

| Page § | Promise | Code | State |
|---|---|---|---|
| Privacy §5 | Account deletion is immediate and irreversible; all projects (bin included) with drawings and sąmatos, company data and logo, settings, price lists, templates go; signed out everywhere | `api/account.py` → `project_purge.delete_project_and_files` per project (row, stored PDF + editions, renders, annotations, calibrations, legend, evidence crops, F2/F3 lines, held re-reads, and since M8 the symbol-training crops), `db.delete_account` (settings, jobs, price lists, templates, assemblies, email tokens; session_version bump), and since M8 `purge_account_files` (per-owner architect legends) | matches |
| Privacy §5 | The deleted account keeps a minimal record without email, name, company data or Google link | tombstone row: email replaced, name / company / Google / avatar / company code / PVM code cleared; invoices kept. **But `consumed_trials` keeps the company code (with the user id) after deletion** — the free-trial anti-abuse gate | **MISMATCH (small)**: say so in the text, or drop the user id from that row |
| Privacy §5 | Nightly backups are kept 30 days, so deleted data leaves them within 30 days | `backend/backup.py` prunes only when `SAMATU_BACKUP_KEEP_DAYS` is set; it is unset by design (§2a) → **every backup is kept forever** | **MISMATCH**: set `SAMATU_BACKUP_KEEP_DAYS=30` on Railway (check first with `scripts/report_backup_retention.py --days 30` in that environment), or change the text |
| Privacy §5 | Server logs with IP are deleted automatically after up to 90 days | no app-side log store; the access log lives in Railway's log retention, which depends on the plan | unverified — founder checks the Railway plan's retention |
| Privacy §5 | Drawings sent to Anthropic are kept there per their policy (usually up to 30 days) | external | not code |
| Privacy §2 | Passwords only as bcrypt hashes; Google: only the account id, email and name | `auth.hash_password` (bcrypt 12); Google stores `google_sub`, email, name, avatar URL | matches (the avatar URL is not named) |
| Privacy §2 | IP kept briefly in server logs for rate limiting / abuse | rate limiter is in memory (60 s windows); IPs appear in access / security logs | matches |
| Privacy §2 | Prices and price lists are only in your account | `price_lists`, settings, templates are per user | matches |
| Privacy §8 | HTTPS everywhere; session cookie HTTPOnly, SameSite=Lax, signed | `SessionMiddleware(same_site="lax", https_only=ENV=production)` | matches |
| Privacy §4 (processors) | Anthropic, Stripe, Google named; „debesijos priegloba ir failų saugykla" described generically, provider „on request" | also Cloudflare R2 (drawings, backups), Railway, Vercel hosting; **an email provider once SMTP is chosen (M2)**; the app stylesheet loads IBM Plex from **Google Fonts** (`frontend/src/index.css:3`), so every visitor's IP reaches Google before any consent | **gap**: the email provider is not covered by any line; Google Fonts is neither a listed processor nor in Cookies §5 — self-host the two fonts or name it |
| Privacy | (not mentioned) | in-app usage events (`/api/telemetry/session`: event type, target such as a room number, timings, per project) are written to a server log for the pilot report; since M3 only for a signed-in owner; the lines are **not** removed when the project is deleted | **gap**: mention it, and/or purge by project id |
| Cookies §3 | `samatu_session` lasts for the session / until sign-out | `SESSION_MAX_AGE_S` = 30 days (a persistent cookie, invalidated by sign-out) | **MISMATCH**: the table should say „iki 30 dienų arba iki atsijungimo" |
| Cookies §2–3 | No analytics / marketing cookie before consent; exact cookies listed once a tool is installed | `lib/analytics.js` loads gtag.js only after consent (Consent Mode defaults denied) | matches; if a GA id is configured in production, its cookies (`_ga`, `_ga_*`) should now be listed |
| Cookies | similar technologies (localStorage) | also `samatu_projects` / settings caches, IndexedDB copies of drawings — cleared on logout and on another person's sign-in since M3 | matches in spirit; the list is not exhaustive |
| Terms §7 | You can delete the account any time, by email or in settings | Settings › account deletion (2026-10-05) | matches |
| Terms §4 | Cancel a subscription any time, it runs to the end of the paid period | billing is off; Stripe `customer.subscription.deleted` → free | matches once billing is on |
| Privacy §2.3 | Device and browser data (browser type, OS, language) for compatibility and security | not collected by the app as a record; the browser's own user-agent reaches `/api/log-error` only when a page crashes (optional `user_agent` field, written to the server log) | matches (narrower than the text) |
| Privacy §2.4 | From Stripe we receive only payment status, amount, date and partial invoice details | `webhook_events` keeps only the event id and time; `invoices` keeps the owner-scoped invoice index; card data never reaches the backend | matches |
| Privacy §3 | Newsletters by consent | no newsletter, no mailing list, no marketing email code exists | matches (nothing sent); the text promises a consent flow that does not exist yet |
| Privacy §6 | Data portability: projects in Excel / PDF / JSON | Excel and PDF exports exist; JSON exists only for the viewer measurements (`matavimai.json`) and the backend-only F2/F3 routes — **no whole-project JSON in the UI** | **MISMATCH (small)**: drop „JSON" from the text, or answer such requests by hand from the stored project blob |
| Privacy §8 | Access to data is restricted | admin routes are allowlisted, the allowlist applies only to a verified inbox since M3, and state-changing admin actions are written to `admin_audit_log` | matches |
| Privacy §9, Terms §4 / §7 / §8 | Material changes (policy, prices, features, terms) are announced by email in advance | M2 adds a sender (console default, SMTP when configured) used only for verification and password reset; there is no bulk-announcement path | process: the founder sends such notices by hand until a mailing path exists |
| Terms §2 | An account needs a valid email | verification email goes out on registration (M2), but sign-in without opening it is allowed unless `SAMATU_REQUIRE_EMAIL_VERIFIED=1` | founder decision: turn the gate on for launch, or accept unverified addresses |
| Terms §4 | Reverse VAT may apply to business clients | sąmata exports take 21 / 9 / 0 % (M4); the billing invoice VAT rule is still unconfirmed (audit -8, M1 pre-flight lists it) | open until the accountant confirms the invoice rule; billing stays off |
| Cookies §1 | localStorage is used to remember the cookie choice | localStorage / IndexedDB also hold project caches and drawing copies (see the row above) | **MISMATCH (wording)**: the sentence reads as „only for consent" |
| Cookies §3 | `samatu_session` stores only the user id | the signed session also holds `sv` (session nonce for sign-out-everywhere) and, during a Google sign-in, the OAuth `state` and the return path | **MISMATCH (small)**: „naudotojo ID ir techninius saugos žymenis" |

## 9. Decommission / shutdown

If you ever need to take the service down:

1. Render → Suspend service. Frontend + backend stop serving immediately.
2. Take a final DB snapshot **before** deleting the persistent disk — the
   disk *is* the database. Either run a manual backup to R2 or copy
   `SAMATU_DB_PATH` off the disk; deleting the disk is irreversible.
3. Notify users via email at least 30 days in advance per Privacy policy §11.
4. Export user data on request before final shutdown (BDAR Art. 20 — duomenų
   perkeliamumas).

---

## Decisions deferred to launch day

- **Email service** (Postmark / Resend / AWS SES) — pick when password
  reset becomes a real need. Without it, register-only flow is fine.
- **Stripe / billing** — the code is **already built but dormant**, gated by
  `BILLING_ENABLED` (defaults `'0'`). Not "add in a separate sprint" — it is
  "run the pre-flight, then flip the flag" (see `DEVELOPING.md` for that
  checklist). Keep it off for beta.
- **Multi-floor / multi-tenant** — not in scope for beta.
- **Mobile-native UI** — web responsive is good enough.

## Owner contact for AI dev questions

This RUNBOOK was generated by Claude Code (Anthropic CLI). Re-running
the brainstorming + writing-plans skills can produce updated plans for
new sprints.

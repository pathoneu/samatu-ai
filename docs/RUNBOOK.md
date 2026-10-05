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
- **Email:** until SMTP is set up, password reset is unavailable. For beta,
  this is acceptable — users can register fresh.

## 8. Rollback plan

If a deploy breaks production:

1. Render → Deploys tab → previous deploy → **Rollback**. ~30s downtime.
2. If rollback also broken: comment out the broken endpoint, redeploy.
3. Worst case: pause Anthropic API key in console — paid endpoints stop
   returning, app stays available without AI.

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

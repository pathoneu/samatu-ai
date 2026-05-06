# Sąmatų AI — Launch Checklist (beta)

**Date drafted:** 2026-05-06 · **Target:** beta launch this week.

This checklist covers what's done in code (✓) vs. what needs you (the
human owner) to do before flipping production traffic on.

---

## ✓ Done in code (M1–M5 + M3)

- [x] Codex PlanViewer layout on main `/project/:id` route
- [x] Click → pulsing room-number marker (deterministic via pdfplumber)
- [x] Provenance pills (eksplikacija / manual / AI / dimension) — subtle
- [x] Eksplikacija rooms now render 🟢 not 🔴 (saltinis→source mirror fix)
- [x] Formula fixes: window reveal `2H+W` → `2H+2W` + tile waste 8% → 10%
- [x] Sanity warnings dismissible; totals show all rooms (no review gate)
- [x] Email/password registration (open, no beta codes)
- [x] Google OAuth wiring (lights up when env vars set)
- [x] Admin dashboard at `/admin` (users, projects, Vision spend)
- [x] Per-user daily Vision spend cap (env-configurable)
- [x] Per-user hourly extract count cap
- [x] Security headers: X-Content-Type, X-Frame=DENY, Referrer, Permissions
- [x] HSTS + CSP in production (when `ENV=production`)
- [x] Session cookie `https_only` in production
- [x] CORS origins from env
- [x] Landing page at `/` (public)
- [x] Privacy + Terms pages
- [x] Cookie banner

## You need to do — auth & domain

- [ ] **Generate `SAMATU_SECRET_KEY`** (32+ bytes random)
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
- [ ] **Get Anthropic API key** at console.anthropic.com → set spending
  limit on the key (recommend €100/mo for beta)
- [ ] **Pick a domain target.** Suggestion: `samatu.pathon.eu` subdomain
- [ ] **Pick hosting platform.** My pick: Render.com (cheapest,
  built-in Postgres, auto-TLS) or Fly.io. Vercel/Netlify won't run
  the FastAPI backend.
- [ ] **DNS records on pathon.eu registrar:**
  - `samatu` → A or CNAME to your hosting platform
  - SPF, DKIM, DMARC TXT records for outgoing email (skip for now if
    no email service yet — spammers can impersonate but you only pay
    if you actually send)

## You need to do — Google OAuth (optional, can skip for v1)

- [ ] Go to https://console.cloud.google.com/apis/credentials
- [ ] Create OAuth 2.0 Client ID, type = Web application
- [ ] Authorized redirect URI: `https://samatu.pathon.eu/api/auth/google/callback`
- [ ] Set in `.env`: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
  `GOOGLE_REDIRECT_URI=https://samatu.pathon.eu/api/auth/google/callback`
- [ ] Verify OAuth consent screen settings + add @pathon.eu to test users
  while in dev/staging mode

## You need to do — email service (later, when you want)

User said they'll research alternatives to Postmark. Until then, app
runs without email — only password reset will be unavailable. Suggested
order of preference:

1. **Resend.com** — $0/mo first 3000 emails, easy DKIM
2. **AWS SES** — $0.0001/email, requires DMARC setup
3. **Postmark** — $10/mo, fastest deliverability LT
4. **Self-hosted Postal** — free but operationally heavy

When picked, integrate via `python-dotenv` env var like
`SMTP_URL=...`; backend already has stub points where this hooks in.

## You need to do — production env

Create `backend/.env` (NEVER commit):

```bash
ANTHROPIC_API_KEY=sk-ant-...
SAMATU_SECRET_KEY=...generated above...
ENV=production

# Cost protection
SAMATU_USER_DAILY_SPEND_EUR=0.50
SAMATU_USER_HOURLY_EXTRACTS=10

# CORS (comma-separated, no spaces)
SAMATU_CORS_ORIGINS=https://samatu.pathon.eu

# DB (point at persistent volume)
SAMATU_DB_PATH=/var/lib/samatu/samatu.db

# OAuth (when ready)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://samatu.pathon.eu/api/auth/google/callback
```

## Pre-launch QA

- [ ] Upload 3+ test PDFs (use `training-data/projektas_1..5/` as
  baseline). Verify:
  - [ ] Room numbers in panel match drawing (click → marker pulses on
    correct number)
  - [ ] Σ neto in right panel ≠ 0 €
  - [ ] No red 🔴 neaišku pills on rooms with eksplikacija data
  - [ ] Sanity warnings show only when math is genuinely off
- [ ] Register a fresh account, log in, log out
- [ ] (If OAuth set) sign in with Google
- [ ] Check `/admin` shows you (the first user) as admin
- [ ] Try to extract while at hourly cap — should see 429 friendly message

## What's in flight after launch (Sprint 6 backlog)

These are NOT blocking launch but they're queued:

- **#52 Phase C-3 click-to-fill walls** — 12-task plan exists at
  `docs/superpowers/plans/2026-05-02-phase-c-3-click-to-fill.md`.
  Replaces unreliable Vision bbox with user-driven click + OpenCV
  flood-fill on the rasterized PDF. Big UX win.
- **#51 Symbol counting workflow** — legend → click example → find
  similar → review pile. Per-project memory.
- **#53 Multi-floor reconciliation** — sum-of-eksplikacijos vs final
  patalpos sum on multi-floor PDFs (P3 case).
- **#54 Per-project legend memory** — depends on #51.
- **GKP frame profile split** (CW+UW) — formula audit deferral.
- **Acoustic insulation auto-emission** between dwellings.

---

## What can break after launch — risk register

| Risk | Likelihood | Mitigation in code |
|---|---|---|
| Vision API rate-limited / down | Medium | Catch + show friendly error; per-user cap means no runaway cost |
| User uploads scanned (raster) PDF | Medium | pdfplumber falls through to Vision; quality degrades but doesn't crash |
| Different drawing style than training-data 5 | High | Sanity warnings surface obvious failures; user manually edits any line |
| User wants to undo an AI extraction | Low | No undo in v1 — they can re-extract or edit pozicijos |
| Anthropic API key leaks | Catastrophic | `.env` gitignored; rotate via console.anthropic.com on suspicion |
| 5+ users sign up day 1 and burn through quota | Low | Per-user spend cap + hourly extract limit + low-priority queue (not impl) |

If you see Vision spend climbing fast, tighten
`SAMATU_USER_DAILY_SPEND_EUR=0.25` (1-2 extracts/day) until you understand
who's burning it.

# Security posture — Pathon (Sąmatų AI)

**Last hardened:** 2026-07-04 (pre-launch security engagement) · supersedes/extends the Sprint 11 (2026-05-06) baseline below.

This is the living security reference: how auth/authorization work, what the pre-launch engagement found and fixed, the recurring bug classes eliminated, and the config that **must** be set in production. **Read §6 "Production deploy checklist" before every deploy.**

---

## 1. Pre-launch engagement summary (2026-07-04)

Owner-authorized, pre-production. A **static audit** plus **four escalating live red-team passes** (real auth on, local server, two throwaway tenants A-vs-B, non-destructive — prod never touched). Each pass attacked; findings were fixed with a regression test replaying the exact PoC; the next pass re-attacked to confirm closure and hunt the same bug class elsewhere. The loop ran until a full pass returned clean.

| Metric | Value |
|---|---|
| Red-team passes | 4 (each escalating) |
| Findings fixed | 8 (F1–F8) + 5 (N1,N3,N4,N5,N6) + 3 (P1–P3) + 1 LOW body-cap = **17** |
| Recurring classes eliminated | fixture-before-auth; project-id-keyed store with no owner check; formula-injection swept across all export paths |
| Final pass | **ALL CLOSED — no exploitable vulnerability** |
| Backend tests | ~1175 passing; every fix carries a regression test |

Crown-jewel data (projects, PDFs, corrections, extractions, share links, admin) held across all four passes. The bugs found were peripheral routers and export paths that had drifted from the ownership-gate pattern; all are closed and structurally guarded against reintroduction.

---

## 2. Authentication

- **Bcrypt**-hashed passwords (work factor 12); constant-time dummy-verify on unknown users closes the login timing/enumeration oracle (N4).
- Session cookie is **HttpOnly**, signed (`itsdangerous`), `SameSite=lax`, `Secure` forced when `ENV=production`.
- Cookie carries `{user_id, sv}` — `sv` is the per-user `session_version`; **no PII**. (Updated from the May baseline, which stored only `user_id`.)
- **Session invalidation:** logout and change-password bump `session_version`, invalidating **every** outstanding cookie for that user (F2) — not just the current browser.
- Session lifetime: 30 days idle.
- Dev bypass `SAMATU_AUTH_DISABLED=1` short-circuits to a default admin user; **hard-fails if combined with `ENV=production`**.
- **OAuth:** Google `state` is stored, compared, single-use-popped; `next` path guarded by `_safe_next_path` (no open redirect / SSRF). Since 2026-10-05 the frontend sends the whole address the user was on, so the guard keeps a same-site path WITH its query and hash (`/project/x/patikra?kambarys=02#a`) and turns everything else into `/`: absolute URLs, `//host`, a backslash in the path, the same percent-encoded once or more (`%2F%2F`, `%5C`, `%252F`), dot segments, control characters, spaces and non-ASCII (raw, or encoded in the path), and anything over 2000 characters (it rides in the session cookie). Pinned by `backend/tests/test_oauth_next_path.py`.

## 3. Authorization model

- **Dependencies:** `require_user` / `require_billable_user` (also reserves spend) / `require_admin`.
- **Ownership:** `db.get_project(project_id, user_id=...)` — a miss returns **404, not 403**, so the API never leaks whether a project id exists.
- **Canonical gate:** `auth.require_owned_project(request, project_id)` runs auth **then** owner-scoped `get_project`, with admin bypass. New project-scoped routes must use it (as `Depends()` or a pre-branch call) rather than hand-rolling the order.
- **Share links:** 128-bit `uuid4`, **GET-only, read-only, redacted** (strips `user_id`, `_meta`, cost, polygon geometry); no token-scoped write route; token never logged.

> The May 2026 audit made every billable/CPU endpoint require **login**. The July engagement added the missing **ownership** dimension on top — several logged-in routes still let a user act on *another* user's project id (F1/F3/F4/N1/N6/P1/P2). That gap is now closed.

## 4. Findings & fixes (ledger)

**Static audit + red-team pass 1 — F1–F8**

| ID | Sev | Finding | Commit |
|---|---|---|---|
| F1 | HIGH | Anonymous cross-tenant IDOR on file-backed routers (annotations, legends, calibrate GET/DELETE) | `c239631` |
| F2 | MED | Logout didn't invalidate the signed cookie → `session_version` | `f52b208` |
| F3 | MED | vision-fill / lasso-rerun authed but no ownership check | `2ee750b` |
| F4 | LOW | Unauthenticated compute (recompute, `/api/cv/*`) | `36c1d33` |
| F5 | LOW | `/extract` masked validation errors as 200 + echoed exception text | `9891205` |
| F6 | LOW | CSV/Excel formula injection on exports (`= + - @`) | `78041cd` |
| F7 | LOW | `/api/log-error` unauth, unbounded logging → rate-limit + truncate + strip | `d92850e` |
| F8 | HIGH-ish | Dependency CVEs (starlette/multipart/pdfminer; frontend react-router). **2026-10-05:** the frontend is on `react-router` 7.18.4 (`react-router-dom` 6 is gone — v7 folds it into `react-router`), and both remaining router advisories are resolved: GHSA-wrjc-x8rr-h8h6 (open redirect) and GHSA-337j-9hxr-rhxg (SSR deserialize) | `ea2e7f0`, `ff8bf90`, `2918ff4` |

**Red-team pass 2 — N-series (residual same-class gaps)**

| ID | Sev | Finding | Commit |
|---|---|---|---|
| N1 | MED | `?fixture=` returned before `require_user` in calibrate write | `0a15757` |
| N3 | LOW | User/AI text unescaped before reportlab `Paragraph` (offer PDF) | `72eb1d1` |
| N4 | LOW | Login timing oracle (user enumeration) | `149a191` |
| N5 | LOW | `/extract` Path-2 fallback leaked exception text at 200 | `f2d2170` |
| N6 | MED | `/api/cv/*` + detect-room-polygons + click-to-fill: PDF cache read/written with no owner check | `e6618d9`, `1510f75` |

**Red-team pass 3 — P-series + class sweep**

| ID | Sev | Finding | Commit |
|---|---|---|---|
| P1 | MED | `GET /stats?fixture=` unauth cross-tenant metadata read | `621aeaa` |
| P2 | MED-HIGH | `POST /export-excel?fixture=` — XLSX leaked victim's secret calibration values | `5a4150f` |
| P3 | MED | `/generate-excel` (+`/export/excel`) formula injection (F6 sibling) | `a04e590` |
| — | — | **Class sweep:** canonical `require_owned_project`; audited every fixture route + project-id-keyed store; warning comments on no-store fixture routes | `1ae00c0` |

**Red-team pass 4 — final confirmation (clean)**

- P1/P2/P3 confirmed closed with live PoCs; the **fixture-before-auth class is dead** across all 8 fixture routes + value-tricks (`fixture=<other UUID>`, `../`, encoded traversal, unknown, empty, wrong verb — all 404/405).
- Seven not-previously-deep-tested classes all clean: **CSRF** (SameSite=lax + credentialed CORS allowlist, no state-changing GET), **mass-assignment/privesc** (`register`/`PUT profile`/`PUT project` ignore `is_admin`/`user_id`/`session_version`/`id`; ownership derives from the DB row not the body), **ownership TOCTOU** (checked id == written id everywhere), **billing bypass** (reservation keyed to the authenticated caller), **share-token write abuse** (none), **auth/session** (email case-collision blocked, no fixation, OAuth `state` single-use).
- One LOW note closed: `/api/log-error` now caps request body size (64 KB) before buffering — a stream-level guard plus `Content-Length` fast-path, so a spoofed/absent length can't smuggle a large body — commit `6b79e48`.

## 5. Recurring classes we structurally eliminated

1. **"`?fixture=` returns before auth."** Router `_load_project(id, fixture=...)` helpers short-circuited before `require_user`, exposing a `{URL_id}`-keyed per-user store under an attacker id. **Fixed everywhere:** store-reading fixture routes auth+own before the fixture branch; no-store fixture routes read only the public allowlisted fixture asset (+ a `SECURITY` comment). All enumerated and re-attacked in pass 4.
2. **"Project-id-keyed store with no owner check."** Every per-project disk/cache read (`data/annotations`, `data/calibrations`, `data/legends`, F2/F3 lines, the in-memory PDF raster cache) is now preceded by an ownership gate; pass 4 mapped all call sites.
3. **Spreadsheet formula injection** swept across *all* export paths (F6 + P3).

## 6. Production deploy checklist — MUST set before going live

Config, not code — the app is safe only when the environment is correct:

- [ ] **`SAMATU_SECRET_KEY`** — strong random (`python -c "import secrets; print(secrets.token_urlsafe(48))"`). App hard-exits on the dev fallback in production.
- [ ] **`ENV=production`** — turns on HSTS + CSP + `Secure` cookie; hard-exits on dev secret / `SAMATU_AUTH_DISABLED`.
- [ ] **`SAMATU_CORS_ORIGINS=https://app.pathon.eu,https://pathon.eu`** — else defaults to localhost. Explicit allowlist, never wildcard-with-credentials.
- [ ] **Run with `--proxy-headers --forwarded-allow-ips=<lb-ip>`** — so the rate limiter keys on the real client IP (present in render.yaml/railway.toml/nixpacks.toml — verify active behind the real LB).
- [ ] **`SAMATU_AUTH_DISABLED` unset/empty** in production.
- [ ] **R2 credentials** — the four `R2_*` env vars set in the host dashboard (`.env` is gitignored, does not deploy).
- [ ] Optional beta throttles: `SAMATU_USER_DAILY_SPEND_EUR` (≈0.50), `SAMATU_USER_HOURLY_EXTRACTS` (default 20).

## 7. Rate limiting

- Per-IP sliding window: 30 req/min on auth-mutating endpoints (login/register/change-password) + extract endpoints + `/api/log-error`.
- Per-user daily Vision spend cap when `SAMATU_USER_DAILY_SPEND_EUR` set. Per-user hourly extract count when `SAMATU_USER_HOURLY_EXTRACTS` set. Reservation is keyed to the authenticated caller (no cross-user charging); pre-charge is written before the Claude call (closes the concurrent race).

## 8. File upload

- Max size 200 MB. Magic-byte check (`%PDF` header). Filename sanitization (rejects `..`, leading `/`). Page-count probe via pdfplumber; warns > 100 pages (Vision cap).
- `/api/log-error` has its own small body-size cap (it's intentionally unauthenticated) — see §9.

## 9. Response headers (production only — `ENV=production`)

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy` — restrictive `default-src 'self'`, allows Google OAuth domains for the OAuth flow only. **These headers are on the API's responses (api.pathon.eu).** The app itself is served by Vercel from `frontend/vercel.json`, which sets nosniff / X-Frame-Options / Referrer-Policy but **no CSP yet** (audit backend-security-17, still open 2026-10-18: a CSP for the SPA must be tried on a production build first — EmbedPDF's wasm and workers, blob: URLs for drawings, Google Fonts and analytics all need their sources listed).
- `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()` (all always on).

## 10. Accepted / residual risk

- **`/api/log-error` is intentionally unauthenticated** (the frontend must report boot-time errors before a session exists). Defended in depth: 30/min per-IP rate limit + body-size cap + output truncation + control-char stripping. Residual: bounded junk in the error log within the rate limit. Accepted — no leak, no crash.
- **Deeply-nested JSON** returns a generic HTTP 500 (RecursionError in the encoder); server survives, **no stack trace leaks**. Accepted.
- **`GET /api/legends/architect/{architect}`** requires login but not per-architect ownership — by design (architect legends are built only from a user's own verified projects).
- **CSRF** relies on `SameSite=lax` + credentialed CORS allowlist; no explicit CSRF tokens. Pass 4 confirmed no exploitable vector (no state-changing GET, cross-site POST can't carry the cookie). Re-evaluate if cross-origin embedding is ever added.
- **Spend caps are env-disabled during beta.** The reservation path is exploit-safe when enabled; re-enable tiered (admin/free/paid) when the payment wall ships.
- **`POST /api/billing/v2/webhook` is intentionally unauthenticated** (Stripe, not a logged-in user, calls it) but **Stripe-signature-verified**: the raw request bytes are checked against `STRIPE_WEBHOOK_SECRET` via `stripe_client.construct_event`; a missing/tampered signature or unset secret → **400** before any handler runs. Events are de-duped on `event.id` (a re-delivery is a 200 no-op), and a handler exception never 500s the endpoint. Accepted — the signature is the auth. **Invoice retrieval is owner-scoped:** `GET /api/billing/v2/invoices/{id}` runs `db.get_invoice(id, user_id=caller)`, so a non-owner (or unknown) id returns **404, not 403** — same no-existence-leak convention as `get_project` (§3).

## 11. Secrets & rotation runbook

- Never committed (`.gitignore` covers `.env`, `*.env`). `SAMATU_SECRET_KEY` rotation invalidates ALL sessions (users logged out — by design). `ANTHROPIC_API_KEY`: set a spending limit on the key itself (console.anthropic.com/settings/keys).
- **Rotate a secret:** 1) generate `python -c "import secrets; print(secrets.token_urlsafe(48))"`; 2) update the host secret manager (Render/Fly); 3) restart; 4) users are logged out — communicate beforehand if needed.
- **Anthropic key:** cycle in console, update env, restart, revoke old.
- **Google OAuth:** rotate in Google Cloud Console → Credentials → reset secret; update env, restart (no user-visible disruption).

## 12. Ongoing practice

- New project-scoped routes: use `auth.require_owned_project` — never hand-roll auth-then-ownership ordering.
- New export paths: run all user/AI text cells through `sanitize_spreadsheet_cell`.
- New fixture/demo params: auth before any per-user store read, or read only public allowlisted assets — leave the `SECURITY` comment.
- Every security fix ships with a regression test replaying the attack PoC.
- Re-run `pip-audit` + `npm audit` before each release; the FastAPI/starlette bump is the one to test carefully.

*Full engagement findings: `docs/superpowers/research/2026-07-04-security-pentest-findings.md`.*

## 13. Re-audit of the 2026-09-29 findings (v3 W7-A, 2026-10-18)

The twelve `backend-security-*` items the coverage matrix listed as "unknown", plus -14 and -21, checked against the code on `v3/market-readiness`. Tests: `backend/tests/test_security_reaudit_2026_10_18.py`, `test_auth_email.py`, `test_billing_payment_status.py`.

| Id | State | What |
|---|---|---|
| -4 | fixed now | Unparseable kiekis/kaina: Excel cell goes through `sanitize_spreadsheet_cell`, PDF `_n` escapes; the two frontend CSV builders use `lib/csvSafe.js` |
| -5 | fixed now | `/api/projects/{id}/material-specs`: rate bucket, spend cap and reservation after ownership and the free cache hit (actual tokens still not recorded — reservation only) |
| -6 | fixed now | An `SAMATU_ADMIN_EMAIL` address becomes admin only once its inbox is verified (our link or Google) |
| -8 | half fixed | Buyer fields escaped before reportlab. The VAT rule is unchanged and needs the accountant (DEVELOPING.md › Deploy / billing) |
| -10 | fixed now | `room_recalc ?fixture=` ignored when `ENV=production` |
| -11 | fixed now | `/api/telemetry/session`: login, owned project (404), ≤ 2000 gestures, rate bucket, log under `SAMATU_DATA_DIR` |
| -12 | fixed now | `auth.public_user` on /register, /login, /me, /profile |
| -14 | W2-A's | Architect legend routes — fixed in `api/legends.py` by worker W2-A, not here |
| -15 | fixed now | Logout and a different person's sign-in clear the per-project keys (`lib/userStorage.js`) and the IndexedDB drawings (`pdfStore.clearAllPdfs`); a same-person re-login keeps them |
| -16 | fixed earlier | The chat's help text says the client link shows the sąmata (prices included) |
| -17 | still open | CORS is env-driven (`SAMATU_CORS_ORIGINS`; the prod value is the founder's). The SPA has no CSP (§9 corrected); needs a production-build trial |
| -18 | still open | Register answers 409 for a taken address; no per-account login throttle, no admin TOTP |
| -19 | still open | No ASGI body cap before parsing; some `dpi` inputs unclamped; page-size check reads page 1 only |
| -21 | fixed now | `calibrate` no longer returns `stored_at`; v9 symbol routes log the exception under a reference and answer a plain sentence |

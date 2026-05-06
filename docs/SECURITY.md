# Security posture (Sprint 11 — 2026-05-06)

## Authentication

- Bcrypt-hashed passwords (work factor 12).
- Session cookie is HTTPOnly, signed (`itsdangerous`), `SameSite=lax`,
  `Secure` flag forced when `ENV=production`.
- Cookie carries only `user_id`; no PII.
- Session lifetime: 30 days idle.
- Dev bypass: `SAMATU_AUTH_DISABLED=1` short-circuits to a default admin
  user. Hard-fails if combined with `ENV=production`.

## Authorization audit (2026-05-06)

All Anthropic-billable + server-CPU endpoints now require login. Previously
9 endpoints were unauthenticated — anyone with the URL could drain the
Anthropic budget. Every `@app.post` is now annotated with either:

- `_auth.require_user(request)` — must be logged in
- `_auth.require_admin(request)` — must have `is_admin=1`
- explicit comment "intentionally public" (e.g. `/api/log-error`,
  `/api/auth/login`, `/api/auth/register`)

Routes guarded:
- `/extract`, `/extract-interior`, `/extract-interior-stream`,
  `/extract-facade`, `/extract-roof`, `/extract-earthworks`,
  `/extract-concrete`, `/recompute-interior`
- `/v9/symbols/detect`, `/v9/symbols/detect-page`,
  `/v9/symbols/count-by-template`
- `/api/click-to-fill`
- `/detect-type`, `/detect-scale-hint`, `/pdf-lines`
- `/generate-excel`, `/generate-pdf`
- `/chat-project`
- `/api/admin/*` (admin-only)

## Rate limiting

- Per-IP sliding window: 30 req/min on auth-mutating endpoints
  (login/register/change-password) + extract endpoints.
- Per-user daily Vision spend cap when `SAMATU_USER_DAILY_SPEND_EUR` env
  set (recommend 0.50 EUR for beta).
- Per-user hourly extract count when `SAMATU_USER_HOURLY_EXTRACTS` env
  set (default 20).

## File upload

- Max size 200 MB.
- Magic bytes check (`%PDF` header).
- Filename sanitization (rejects `..`, leading `/`).
- Page count probe via pdfplumber; warns if > 100 pages (Vision pipeline cap).

## Response headers (production only — `ENV=production`)

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy` — restrictive default-src 'self', allows
  Google OAuth domains for the OAuth flow only.
- `X-Content-Type-Options: nosniff` (always)
- `X-Frame-Options: DENY` (always)
- `Referrer-Policy: strict-origin-when-cross-origin` (always)
- `Permissions-Policy: camera=(), microphone=(), geolocation=()` (always)

## CORS

- Origins read from `SAMATU_CORS_ORIGINS` (comma-separated). Default
  localhost in dev. In production set to the exact domain(s).

## Secrets

- Never committed (.gitignore covers `.env`, `*.env`).
- `SAMATU_SECRET_KEY` rotation invalidates ALL sessions (users get
  logged out — by design).
- `ANTHROPIC_API_KEY` rotation: console.anthropic.com/settings/keys.
  Set spending limit on the key itself ($100/mo recommended for beta).

## Known caveats

- CSRF protection relies on `SameSite=lax` + same-origin policy. No
  explicit CSRF tokens. Acceptable while the only state-changing surface
  is `/api/*` JSON POST from same origin. Re-evaluate if cross-origin
  embedding is added.
- PostCSS dev-time vulnerability flagged by `npm audit` is build-time
  only, not user-facing. PostCSS 8.5.9 is the latest available.
- React-Quill removed in Sprint 11 — was unused, transitively brought
  Quill 0.x XSS advisory.

## Rotation runbook

When rotating secrets in production:

1. Generate new value: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. Update `.env` on the host (Render/Fly.io secret manager).
3. Restart the app.
4. Users will be logged out — communicate beforehand if needed.

For Anthropic key: cycle the key in Anthropic console, update env, restart,
revoke old key.

For Google OAuth: rotate via Google Cloud Console → Credentials → edit
client → reset secret. Update env, restart. No user-visible disruption.

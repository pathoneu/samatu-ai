# Sąmatų AI — production launch runbook

**Audience:** Pathon owner / DevOps. The CLI agent cannot reach DNS, billing,
or hosting consoles, so this is the manual checklist for going live.

---

## 0. Prerequisites (one-time)

- [ ] Anthropic API key with spending limit set (recommend €100/mo).
      Console: https://console.anthropic.com/settings/keys
- [ ] (Optional, for Google login) Google Cloud OAuth 2.0 client.
      https://console.cloud.google.com/apis/credentials
- [ ] Pathon registrar access for DNS records.
- [ ] Cloudflare account (free tier OK) — DDoS + auto-TLS + DMARC dashboard.
- [ ] Hosting platform decision. Recommended: **Render.com** (easiest +
      managed Postgres, $7/mo for the basic web instance) or **Fly.io**
      (more flexible, slightly more setup).

## 1. Pick a domain target

Subdomain on Pathon registry: `samatu.pathon.eu` (recommended), or apex
domain if you want.

## 2. Hosting setup — Render.com path

1. Sign up at render.com using your Pathon Google account.
2. Click **New → Web Service**.
3. Connect this GitHub repo (or push from local — Render supports both).
4. **Root directory:** `backend`
5. **Build command:**
   ```
   pip install -r requirements.txt
   ```
6. **Start command:**
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
7. **Region:** Frankfurt (closest EU).
8. **Instance type:** Starter ($7/mo).
9. Add a **Postgres** instance (Render → New → Postgres). Copy the
   internal connection string.
10. Add the env vars (see §4).

For the **frontend**:
1. **New → Static Site**
2. Connect same repo.
3. **Root directory:** `frontend`
4. **Build:** `npm install && npm run build`
5. **Publish dir:** `dist`
6. Add `VITE_BACKEND_URL=https://samatu-api.pathon.eu` (or whatever the
   backend URL ends up being).

## 3. DNS records on Pathon registrar

Replace `<ip>` with the IP Render assigns to your services.

```
samatu.pathon.eu          A     <render-frontend-ip>
samatu-api.pathon.eu      A     <render-backend-ip>
```

Or use Render-provided CNAMEs if no static IPs.

If using Cloudflare in front:
```
samatu.pathon.eu          CNAME proxy → samatu.onrender.com
samatu-api.pathon.eu      CNAME proxy → samatu-api.onrender.com
```

## 4. Environment variables (backend)

Set in Render dashboard → Environment:

```bash
# Required
ENV=production
ANTHROPIC_API_KEY=sk-ant-...
SAMATU_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(48))">

# Cost protection
SAMATU_USER_DAILY_SPEND_EUR=0.50
SAMATU_USER_HOURLY_EXTRACTS=10

# CORS — exact frontend domain(s), comma-separated
SAMATU_CORS_ORIGINS=https://samatu.pathon.eu

# Database
SAMATU_DB_PATH=/var/data/samatu.db   # or use Render's managed Postgres if you wire DATABASE_URL through

# Optional — Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://samatu-api.pathon.eu/api/auth/google/callback
```

CRITICAL: never commit `.env`. Render's secret manager handles this safely.

## 5. Smoke test (after first deploy)

From your laptop, with browser DevTools open:

1. Open `https://samatu.pathon.eu/`
   → Expected: Landing page with "Sąmatos per minutes, ne dienas" hero.
2. Click **Sukurti paskyrą** → register with your email.
3. Open **DevTools → Application → Cookies** — verify `samatu_session`
   has `Secure` + `HttpOnly` flags ticked, `SameSite=Lax`.
4. Open **DevTools → Network** for a backend request — verify response
   headers contain `Strict-Transport-Security`, `Content-Security-Policy`,
   `X-Frame-Options: DENY`.
5. Upload a small test PDF — verify extraction returns within ~30s.
6. As the FIRST registered user, you should be admin. Visit `/admin` —
   must show stats dashboard.
7. Open in incognito → register a SECOND test user → visit `/admin` →
   must redirect to `/dashboard` (non-admin can't see admin).

## 6. Cost monitoring (first week)

- Anthropic console → Usage tab. Daily check first week.
- If a single user exceeds daily cap, the new requests get a friendly LT
  429 ("Pasiekta dienos AI biudžeto riba"). User waits or contacts you.
- If anonymous traffic spikes (shouldn't — auth required), check Render
  logs for the `IP rate limit hit` warnings.

## 7. Post-launch

- **Backups:** Render Postgres has daily snapshots. Verify they're enabled.
- **Uptime monitoring:** UptimeRobot free tier — ping every 5 min.
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
2. Snapshot Postgres before deleting.
3. Notify users via email at least 30 days in advance per Privacy policy §11.
4. Export user data on request before final shutdown (BDAR Art. 20 — duomenų
   perkeliamumas).

---

## Decisions deferred to launch day

- **Email service** (Postmark / Resend / AWS SES) — pick when password
  reset becomes a real need. Without it, register-only flow is fine.
- **Stripe / billing** — not in scope for beta. Add in a separate sprint.
- **Multi-floor / multi-tenant** — not in scope for beta.
- **Mobile-native UI** — web responsive is good enough.

## Owner contact for AI dev questions

This RUNBOOK was generated by Claude Code (Anthropic CLI). Re-running
the brainstorming + writing-plans skills can produce updated plans for
new sprints.

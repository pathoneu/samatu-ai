# Launch Readiness — Consolidated Design

**Date:** 2026-05-06
**Scope:** All work between current state and production launch on `samatu.pathon.eu`.
**Approach:** 6 sequential sub-sprints. 3 autonomous (7, 9, 11) execute back-to-back; 3 blocked sprints (8, 10, 12) pause for owner action.

---

## Goals

1. Ship a polished beta accessible at `samatu.pathon.eu`.
2. Real LT estimators can run a project end-to-end without UI surprises.
3. No sensitive data leaks; admin features actually admin-only.
4. Code base stripped of dead experiments; future maintainers can read it.

## Non-goals

- Mobile-native UI (web responsive is enough for v1)
- Multi-tenant billing (open access during beta)
- Multi-language (LT only)
- Real-time collaboration

---

## Sprint 7 — Core polish (autonomous, ~1 day)

**Bugs:**
- `/exports` route 404 (sidebar links to non-existent page) — either remove sidebar link or build minimal Eksportai page listing user's recent exports.
- 50% Paruošimas progress bar in Kiekiai header — misleading when prices not entered. Remove or rebrand to "Pozicijų patikra" (no %).
- Export PDF/Excel must include company name from Settings instead of leaving blank.
- Admin route restriction — verify only `is_admin=1` users can hit `/admin`. Backend guard exists; frontend should hide sidebar link too if not admin (already done — verify).

**Codex review workflow port:**
Each pozicija row already has the ✓ ✏ ✕ pattern code in codex copy. Port to main:
- ✓ "Patvirtinti" → flips poz.user_verified=true, suppresses warning indicator
- ✏ "Pataisyti" → inline edit kiekis (existing G7 flow)
- ✕ "Pašalinti" → soft-removes pozicija from active set

**Cleanup:**
- Walk through tasks #42-#61, verify each commit landed on `main`. Re-open / fix anything that regressed.
- Identify dead-code candidates: `.codex-backup-*` files (none in main), `/v2` route (Sprint 1 takeoff canvas, replaced by codex layout), unused `gestures/` library if not wired, unused symbol_detector backups.
- Delete with grep audit per file before remove.

**Acceptance:**
- `/exports` no longer 404
- Kiekiai header no misleading %
- Export contains company name
- Codex ✓ ✏ ✕ buttons functional on every pozicija
- `git diff --stat` shows code shrinkage from cleanup
- Backend + frontend tests pass

## Sprint 8 — Auth + onboarding visibility (PARTIAL autonomous)

**Autonomous:**
- Privacy policy full LT GDPR text (replace existing stub).
- Landing page content audit + improvements (current is acceptable; tighten copy, add screenshots).

**Blocks owner action:**
- Google OAuth credentials needed in `.env`. Code path is ready (M4); button shows automatically once env vars set. I leave a clear "TODO owner" in the launch checklist with the steps.

## Sprint 9 — Kainynai feature (autonomous, ~1-2 days)

**Goal:** owner uploads a price list (CSV/Excel), system auto-fills `kaina_eur` per pozicija via fuzzy match on aprašymas, totals update.

**Architecture:**
- Backend: `POST /api/price-lists/upload` accepts CSV (cols: aprašymas, vnt, kaina). Stores per-user.
- `POST /api/projects/{id}/apply-price-list` matches each pozicija aprašymas against the price list using fuzzy string distance (rapidfuzz), fills kaina if confidence >0.85, leaves blank otherwise.
- Frontend `/price-lists` page: upload + list. Project header gets "Taikyti kainyną" dropdown.
- Existing `/exports` link → in Sprint 7 either remove link OR add the page; if added, lists past exports per user.

**Acceptance:**
- Owner uploads sample CSV, opens project, applies → most pozicijos get kaina, total updates.

## Sprint 10 — AI learning (PARTIAL autonomous)

**Autonomous half — prompt iteration from corrections (small):**
- Existing `corrections` table logs every user edit. Add `extractor/learn_from_corrections.py` script that:
  - Aggregates last 30 days of corrections per field type
  - Identifies fields where >20% of users override
  - Generates a one-line annotation appended to `prompt.py` Pass-1 system text under "Common corrections to watch:" section
- Run weekly via cron (manual for now, document command). Owner reviews diff and commits.

**Blocked half — model fine-tuning (large, deferred):**
- Anthropic doesn't offer Claude fine-tuning publicly. OpenAI does for GPT-4o-mini.
- Architecture would be: dataset = (page raster, user-confirmed JSON) tuples → fine-tune GPT-4o-mini → use as cheap pre-screener before Claude.
- This is a research project, ~$200 + multi-day, blocks on dataset privacy decision.
- I document the architecture but DO NOT execute autonomously.

## Sprint 11 — Security hardening (autonomous, ~2 days)

- OWASP Top 10 audit of existing code paths.
- Per-endpoint rate limit (currently per-IP on a few endpoints; extend to all auth-mutating endpoints).
- File upload deep validation (already has magic bytes; add filename sanitization, max-pages cap, password-protected PDF rejection).
- Session security: CSRF tokens for state-changing POST endpoints (FastAPI middleware).
- Secrets rotation procedure documented.
- `.gitignore` audit — make sure no `.env` or DB committed.
- Dependency audit (`npm audit`, `pip list --outdated`).
- Admin endpoints actually require `is_admin=1` (verify with curl, not just unit tests).

## Sprint 12 — Domain deploy (BLOCKED — owner action)

- I can't reach the registrar / hosting console. I document a step-by-step launch runbook (`docs/RUNBOOK.md`) covering:
  - Render or Fly.io setup
  - Postgres connection string
  - Env var checklist (every var the app reads + recommended values)
  - DNS records on Pathon registrar
  - Cloudflare proxy + TLS
  - Smoke test plan once deployed

---

## Execution rules

- After each sprint: backend + frontend tests must pass, vite build clean, dev server smoke OK.
- Use systematic-debugging skill when something fails after a code change (not preemptively).
- Commit incrementally per task within a sprint.
- After Sprint 11: STOP. Owner reviews 3-sprint diff before deciding on Sprint 12.
- Anything destructive (DB migration, mass file delete) → ask owner first.

## Risks

| Risk | Mitigation |
|---|---|
| /exports decision (delete link or build page) — picked wrong | If in doubt, remove sidebar link (smaller scope) and revisit if owner wants the page |
| Cleanup deletes something still referenced | Grep before delete; tests catch obvious breakage |
| Kainynai fuzzy match too aggressive (wrong prices applied) | Confidence threshold + UI shows "iš kainyno" provenance pill so user can review |
| Privacy policy uses generic template missing LT-specific clauses | Use Lithuanian Data Protection Inspectorate template + add Sąmatų-AI-specific clauses; flag for owner-lawyer review before launch |
| 8-hour autonomous run drifts off scope | After Sprint 11 mandatory pause; commits are incremental so any sub-step is reversible |

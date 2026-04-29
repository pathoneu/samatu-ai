# Code Audit — 2026-04-29

> Systematic-debugging skill audit pre-PDF-rewrite. Backend + frontend reviewed for bugs, race conditions, security, performance.

## ✅ Verified clean

- **F2/F3 removal** — no orphan imports/endpoints/buttons (all references in comments only)
- **SKYRIUS_LEGACY_MIGRATION** — frontend + backend maps in sync
- **Auth gating on `/api/projects/*`** — all endpoints require auth; ownership filter consistent
- **DB schema migrations** — `_migrate_schema()` append-only + idempotent
- **Backend pytest** — 168/168 pass
- **Frontend Vite build** — clean, 311KB main bundle (under 350KB target)
- **Playwright comprehensive UX audit** — ALL pass (7 test groups)

## 🔴 CRITICAL bugs found + FIXED in this audit

| # | File:Line | Issue | Fix |
|---|---|-------|-----|
| 1 | main.py:539-542 | Duplicate `@app.delete` decorator (stacked) — second was dead route | Removed empty decorator |
| 2 | ReextractButton.jsx:47-95 | `setInterval` not cleared on error path → leaks indefinitely | Wrapped in try/finally with `clearInterval` |
| 3 | ProjectMainView.jsx:484-503 | Bare `<>` Fragment missing key + `darbai.indexOf` O(n²) per render (~6,400 iters per keystroke on 80-row projects) | `React.Fragment key={cat}` + `useMemo` Map for O(1) lookup |
| 4 | main.py:3560, 3889 | `/generate-excel` + `/generate-pdf` were unauthenticated (abuse risk) | Added `_auth.require_user(request)`; frontend now sends `credentials: 'include'` |
| 5 | NewProject.jsx:351-354 | Base64 encoding of huge PDFs via `String.fromCharCode` reduce → V8 heap overflow on 200MB files | Skip if >50MB; use `FileReader.readAsDataURL` for chunked encoding |

## 🟡 IMPORTANT issues fixed in this audit

| # | File:Line | Issue | Fix |
|---|---|-------|-----|
| 6 | projectStore.js:104 | `_hasPulled` module-level flag persists across logout → user B sees user A's archive entries | Added `resetPullCache()` export; `authContext.logout()` calls it |
| 11 | cross_page_validator.py:24, 125 | Dead `import math`; typo `"sklypa"` (no such LT term) in ceiling skip rule | Removed import; replaced with `("mansard", "kabina", "pakabinam", "slope", "slai", "atvira")` set |
| AUDIT | projectStore.js:_syncToBackend | `_archived` flag accidentally synced to backend → restoreProject didn't stick after refresh | Strip `_archived/_archived_at` from PUT payload (frontend-only soft-delete state) |

## 🟡 IMPORTANT issues — ALL FIXED in this audit

| # | File:Line | Issue | Fix applied |
|---|---|-------|-----|
| 7 | PdfViewer.jsx:1251-1258 | `fetchPageLines` no AbortController → race conditions | Added `cancelled` guard + `.catch()` + cleanup return |
| 8 | WorkspacePanel.jsx:60-66 | `setInterval` polls forever in background tabs | Page Visibility API: pause on hidden, refresh + resume on visible |
| 9 | ExportDropdown.jsx:20-40 | Duplicate warnings in export | `seen` Set dedupes by lowercase `tekstas` |
| 10 | vision_call.py:_apply_wall_elevation_tile_override | Matches by name → "Vonia 1" + "Vonia 2" overwritten | Match by `nr` first; fallback to name only when unambiguous; emits `lt_sanity` warning when ambiguous + 2 new tests |
| 12 | projectStore.js:358-359 | Backup version one-way check | Migration table scaffolding + `_migrateProject` applied to imported data |
| 13 | main.py:69-82 | Rate-limiter unbounded growth | Janitor evicts empty buckets every 10 min, logs eviction count |
| 14 | auth.py:45-50 | `SAMATU_AUTH_DISABLED=1` + `ENV=production` = silent prod bypass | Hard `sys.exit(2)` at startup if both detected, with stderr message |

## 🟢 NICE-TO-HAVE — ALL FIXED in this audit

| # | Issue | Fix |
|---|-------|-----|
| 15 | Pricing duplication (5e-6/25e-6 in both backend + frontend) | Shared `frontend/src/lib/pricing.js` + `backend/pricing.py`; both reference single source |
| 16 | errorTracker re-wraps console.error on HMR (dev) | `WRAP_SENTINEL` property on wrapped function prevents stacking across reloads |
| 17 | OnboardingTooltips backdrop assumes positioned parent | Verified InteriorWorkspace has `relative` (line 130); inline doc added |
| 18 | LT pluralisation incorrect | New `lib/ltPlural.js` with proper LT grammar (1=vienaskaita, 2-9=dauginis, 10-19+0=nulinis); applied in WallElevationsPanel + Settings |
| 19 | PdfViewer auto-nav re-runs on pageMeta updates | Set `autoNavDone=true` IMMEDIATELY on entry (was after pageMeta loop) — prevents stream-driven re-trigger |
| 20 | Three polling rates uncoordinated | OnboardingTooltips also visibility-aware now (matches WorkspacePanel pattern); 800ms/1000ms intervals all pause when tab hidden |

## Final state after audit fixes (full sweep)

- **Backend pytest**: **170/170** ✅ (added 2 new tests for wall_elevation `nr` match + ambiguous warning)
- **Frontend Vite build**: 311.77 KB main bundle (under 350KB target) ✅
- **Playwright UX audit**: ALL 7 test groups PASS ✅
- **Trash persist test**: PASS ✅ (refresh + restore work correctly)
- **F2/F3 endpoints**: 404 (cleanly removed) ✅
- **Backend routes**: 37 total (1 duplicate removed) ✅
- **Critical bugs fixed**: **5 / 5** ✅
- **Important issues fixed**: **9 / 9** ✅ (was 3/9, then user requested all)
- **Nice-to-have fixed**: **6 / 6** ✅ (was 0/6, then user requested all)

## Total: 20 / 20 issues addressed

## New shared modules introduced

- `frontend/src/lib/pricing.js` + `backend/pricing.py` — single source of truth for Claude API token pricing
- `frontend/src/lib/ltPlural.js` — proper LT grammar pluralisation helper (used in WallElevationsPanel + Settings)
- `frontend/src/lib/projectStore.resetPullCache()` — exported for authContext logout flow

## Recommendation for next steps

**Before Phase C (PDF rewrite)**: ✅ Codebase is fully clean. All audit findings addressed.

**Before production deploy** (separate from this audit, deferred per user preferences):
- §1 Production hardening (auth re-enable, Sentry, monitoring) — already in TASKS.md
- E2E tests against fresh PDF extraction (Vision API spend ~$5)

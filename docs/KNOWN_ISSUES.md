# Sąmatų AI — Known Issues (Pre-Launch Assessment)

**Last updated:** 2026-04-27
**Status:** Pre-production refactor complete + Phase 9 production-readiness fixes landed.
**Honest production-readiness for AI extraction:** ~93% (Phase 10 + cleanup + Phase 11 safety/observability).
**Honest production-readiness for full app (auth, design polish, multi-tenancy, browser cross-test):** ~70% — significant gaps remain.

User audit (2026-04-27) flagged: dizainas, togal.ai UX, brėžinio žiūrėjimas, debugging, safety features. Phase 11 addressed safety + debugging + browser PDF overlay verification. Design polish + togal-style UX remain for separate plan.

This document is the result of an Explore-subagent UI audit + manual stress testing. It exists so the launch decision is made with full visibility into what works, what's been tested, and what's deferred.

---

## ✅ Fixed in Phase 9

| Issue | Resolution |
|-------|-----------|
| `lt_sanity` field name mismatch — banner silently broken on new projects | Backend mirrors `_lt_warnings` + `warnings[]` into `lt_sanity: {warnings, summary}` shape. WARN→WARNING normalization. |
| Backend `status: "error"` not caught — generic "Netikėtas atsakymo formatas" for all errors | NewProject.jsx now explicitly checks `status === 'error'` + `_error` before rendering. |
| ProcessingState fake completion at 8s while backend ran 3-8 min | Rewrote to map steps to elapsed seconds (0/15/90/300s) — animation reflects real progress. |
| 4-min frontend timeout vs 8-min backend pipeline | Bumped to 600s. AbortError shows friendly message, not stack trace. |
| RoomsGrid `default_window_area_m2` formula drift (1.40 frontend vs 1.80 backend) | Frontend uses 1.80 m² (LT STR standard) + grindjuostes 10% NRM2 waste applied. |
| `ConfidenceDot` used heuristic, not real backend `confidence` field | Now uses `room.confidence` + `plotas_saltinis` / `lubu_aukstis_saltinis` source tags. Heuristic only as fallback. |
| Excel export missing warnings sheet (perspejimani always empty) | ExportDropdown collects warnings from `lt_sanity.warnings[]` and maps to `{tekstas, kategorija}` shape Excel expects. |
| `archetipas` field unused | Now displayed as a metadata row in ProjectMainView header. |

---

## ⚠ Known limitations status (Phase 10 update)

### ✅ Limitation 1: AssumptionsPanel — FIXED in Phase 10
Backend `/recompute-interior` endpoint + frontend `RulesOverridePanel.jsx`. 6 per-paskirtis toggles + 3 numeric inputs + per-room override table. Sub-second roundtrip (~8ms measured). "Prielaidos" tab restored to TabBar.

### Limitation 2: Hidden tabs (`puslapiai`, `kiekiai`, `workspace`)
**Severity:** LOW. Tab content code exists but unreachable. **Note:** "Prielaidos" was added back as a working tab in Phase 10; the others remain dead.
**Future fix:** Delete dead tab code or add to TabBar.

### ✅ Limitation 3: Mobile sidebar — FIXED in Phase 10 follow-up
`AppLayout.jsx` now uses `useIsMobile()` hook (was unused). Mobile (<768px) gets top bar + hamburger + off-canvas drawer. Desktop unchanged.

### ✅ Limitation 4: `_zoom_changes[]` audit trail — FIXED in Phase 10 follow-up
RoomCard now has expandable details section showing zoom audit trail, calculation_trace formula, and Vision-perskaityti mm. Demonstrates two-pass zoom transparency.

### Limitation 5: Dead V8 references in InteriorProject.jsx
**Severity:** LOW (cosmetic). References to `project.v8_pages`, `project.raw_calc_data`, `project.page_classifications`. All nil-safe.
**Future fix:** Cleanup pass — most cleared in Phase 10 follow-up; one PageStructureCard block remains gated `{false && ...}`.

---

## Phase 11 — production safety + observability (2026-04-27)

**Fixed:**
- ✅ File size limits (50 MB max, 100 B min) — HTTP 413 / 400
- ✅ File type validation (%PDF magic bytes check)
- ✅ Filename sanity (path traversal rejection)
- ✅ Rate limit (30 req/min per IP, 60s sliding window) — HTTP 429
- ✅ Backend logger setup (replaced print statements)
- ✅ Global FastAPI exception handler (no stack trace leak; ref-ID for support)
- ✅ Frontend ErrorBoundary (catches render errors, shows friendly UI)
- ✅ window.onerror + unhandledrejection global listeners
- ✅ /api/log-error backend endpoint receives frontend errors → log
- ✅ aiRooms PdfViewer prop defensive fallback (`v8_rooms || patalpos`)
- ✅ _meta debug panel in ProjectMainView (cost/tokens/zoom transparency)

## Phase 11 — STILL PENDING

### Limitation 8: No authentication / multi-tenancy
**Severity:** MED for public-facing deployment, LOW for in-house tool.
**Status:** App is open. Anyone with URL can upload + extract.
**Future fix:** Add Auth0 / Clerk / simple email+pw before public launch. Currently OK for soft-launch with known users.

### Limitation 9: Project data only in localStorage
**Severity:** MED. **Impact:** Projects lost if user clears browser data. No cross-device sync.
**Future fix:** Backend `/api/projects` CRUD with database (SQLite or Postgres). LocalStorage as offline cache.

### Limitation 10: No "re-extract" button on existing projects
**Severity:** LOW. **Impact:** If user wants to redo extraction (eg. after upgrading prompt), they must delete + re-upload.
**Future fix:** Add "Re-extract" button that re-uses the saved PDF (in IndexedDB) with current pipeline.

### Limitation 11: No design polish / accessibility audit
**Severity:** LOW for MVP, MED for public launch. **Impact:** UI is functional but not "designed." No keyboard nav audit, no ARIA labels review, no empty/loading state polish across all views.
**Future fix:** Dedicated design pass (likely separate plan with togal.ai UX research).

### Limitation 12: No browser cross-test
**Severity:** MED. **Impact:** Pipeline + UI tested only via curl + Vite dev server. Chrome/Safari/Firefox compatibility not verified by automated test.
**Future fix:** Manual smoke test by user before launch + Playwright/Cypress test in CI.

### Limitation 6: Plytelės sienos high variance without sienų išklotinės
**Severity:** MED for projects without wall-development pages.
**Measurement:** P2 (no eksplikacija) determinism: plytelės_sienos CV 79% even WITH zoom (was 154% without zoom). Vision can't reliably classify "tile zone" without išklotinės.
**Mitigation:** `lt_sanity.warnings` includes "no eksplikacija" INFO when relevant — banner alerts user. They can manually adjust per-room `plyteles_sienos_aukstis_m`.
**Future fix:** When išklotinės are detected on later pages, give them special treatment in prompt.

### Limitation 7: Plytelės grindys classifier ambiguity in non-wet rooms
**Severity:** MED. **Impact:** P1 plytelės_grindys CV 32% across 3 zoom runs (40-80 m² range).
**Root cause:** Vision deterministically classifies bathroom/WC/skalbykla as tile floors, but flips on:
- Koridoriai / hallway floors (sometimes interpreted as tile, sometimes parquet)
- Open-plan kitchen tile zones (partial tile area within larger gyvenamoji room)
This is a CLASSIFICATION ambiguity (not measurement) — even high-res zoom on the floor plan doesn't fully resolve it without `grindų planas` (separate floor finish drawing) or `apdailos lentelė` (finish schedule) showing finish codes per room.
**Mitigation in production:** User can edit per-room values inline via RoomCard. The aggregate works/materials list will reflect their override.
**Future fix:** Reactivate AssumptionsPanel (Limitation 1 above) so user sets default per-paskirtis tile/parquet preferences AND triggers backend re-extract with rules_override. This is the highest-impact UX improvement post-launch.

---

## Benchmark accuracy ceiling — paint & LED residuals (2026-06-06)

After the square-perimeter-synthesis fix (commit `771fb7e`: avg benchmark MAE
**6.87% → 5.78%**, zero regression on eksplikacija projects), two residuals remain.
A multi-round investigation (perimeter priors, niche-prompt tuning, coverage gating,
area priors, scale calibration, ceiling overage, **two live Vision spikes**) established
that BOTH are Vision **measurement ceilings**, not code bugs — do not re-litigate:

- **Čiurlių paint −10.5%** — the bundled `project_pdf` (planning + lighting sheets)
  has **no wall-dimension chains, only furniture dimensions**, so Vision sizes rooms
  from furniture + assumed 1:50 scale → uniform ~10% under-read. Empirical proof
  (live `claude-opus-4-7` calls, 2026-06-06):
    - lighting plan (pg 3): ceiling area → **78 m²** @ conf 0.35 (truth 111.84)
    - floor plan (pg 1): footprint → **87.7 m²** @ conf 0.35, **0/7 rooms from written
      dims**; model's own note: *"Brėžinyje nėra eksplikacijos… pateikti tik baldų
      matmenys, o ne sienų ilgių grandinės."*
  Nuance: truth ceiling-GKP (111.84) exceeds real floor/PVC (98.0) by ~14% — the
  contractor's ceiling includes soffit/boxing surface a flat-ceiling model can't
  derive. AI floor (95.5) is only **−2.6%** vs the real floor (98.0); the headline
  −10.5% is mostly the unmodellable ceiling-soffit gap.
- **Bacevičiaus LED −18%** — Vision *recall* gap (niche prompt already recall-hardened;
  multi-page locator already runs pgs 5/6/7). The inference fallback over-bills Čiurlių
  (+12.5%) while under-recovering Bacevičiaus; **no global ratio change is safe**
  (verified: dropping san/vonia/wc → Bacevičiaus −29.6%).

**Root cause is DATA/input-completeness, same pattern as lazunu** — the dimensioned
architectural plan lives on a separate sheet not in the bundle.

**Answers (no further extraction cleverness warranted):**
1. **`/calibrate`** — contractor enters the exact floor/ceiling/LED value per project
   ($0, exact, never mutates the global calculator; `led_nisos_m` + `dazymo_plotas_m2`
   already registered as calibration metrics).
2. Bundle the **dimensioned architectural plan** into Čiurlių's `project_pdf`.
3. Expand the **no-eksplikacija ground-truth set** (currently N=1–2) before any further
   "global" no-schedule fix — that's the only thing that unblocks this regime.

---

## 🚫 Untested scenarios (cannot resolve without sample data)

We have only 5 training projects, all private residential new-builds. The pipeline has NEVER been validated on:

| Scenario | Risk | Mitigation if encountered |
|----------|------|---------------------------|
| Renovation projects (red=demo, green=existing color conventions) | Vision may misinterpret as new-build | User can manually verify warnings + edit inline |
| Multi-apartment / commercial buildings | Different room types, larger plotas | Pipeline should adapt; no validation done |
| Multi-floor with basement | May confuse floor numbers | Eksplikacija usually disambiguates |
| Mansardiniai (sloped ceilings) | STR 1.05.06 svoris should apply | `lt_rules.mansardinis_svoris` exists but path not fully exercised |
| Mixed-language drawings (LT + EN) | Vision should handle but untested | Likely OK |
| Scanned/raster PDFs (low-DPI photocopies) | Mm annotations may be illegible | Pipeline returns empty with warning |
| Tiny rooms (<2m²), open-plan >40m² | Edge of formula range | Sanity warnings should fire |
| PDFs with security/password protection | pdf2image will fail | Backend returns `pdf_to_images_failed` error |
| PDFs >100 pages | Hits MAX_PAGES cap (rare in LT residential) | Will silently cap at 100; document as known limit |

**Recommendation:** Soft-launch with ≤5 friendly contractors on private-residential projects FIRST. Collect 10-20 real PDFs across the untested scenarios above before broad launch.

---

## 📊 Stress test coverage (what we DID validate)

| Test | Result |
|------|--------|
| 5 training projects (P1-P5) end-to-end | All status=ok with new pipeline |
| Determinism × 3 runs on P2 (no eksplikacija) WITH zoom | rooms CV 7.9% (was 22.9% without zoom), dažymas CV 2.1% (was 12%) |
| Determinism × 3 runs on P1, P3 with zoom | **In progress at time of writing — see DETERMINISM_REVIEW.md** |
| Concurrent load: 3 simultaneous requests | All HTTP 200, no crashes, linear latency degradation |
| Failure modes (empty PDF, garbage bytes, missing field, bad JSON) | All graceful errors with descriptive messages |
| HTTP smoke test of `/extract-interior` | Returns full schema with darbu_sarasas + v8_totals + v8_rooms + lt_sanity |
| Frontend: localhost upload + render | Confirmed working by user (rooms + works/materials list) |
| MAX_PAGES = 100 (Anthropic API hard max) | Tested up to 65-page P1 successfully |
| Two-pass zoom architecture | Validated — measurable variance reduction (3-6× on key metrics) |

---

## 🎯 Production launch checklist

Before flipping the switch:

- [x] Phase 1-6 refactor (backend simplification + frontend switch + Phase 6.6 V8-compat)
- [x] Phase 8 two-pass zoom for accuracy
- [x] Phase 9 UI blockers fixed (5/5)
- [x] Phase 9 failure mode tests (4/4 graceful)
- [x] Phase 9 concurrent load (3 simultaneous OK)
- [ ] Phase 9 determinism on P1, P3 with zoom (in progress)
- [ ] Browser smoke test in Chrome / Safari / Firefox by a real user
- [ ] Set up monitoring / error reporting (Sentry, LogRocket, or similar)
- [ ] Document the soft-launch scope (which contractors, which project types)
- [ ] Plan for post-launch sample collection (10-20 real PDFs across untested scenarios)

---

## 📅 Post-launch follow-ups (recommended cadence)

- **Week 1:** Daily review of upload errors + warnings emitted. Patch obvious data-quality issues.
- **Week 2:** Sample 5 real production projects, manually verify accuracy vs backend output. Calibrate prompts.
- **Week 4:** Validate kampai variance vs real contractor proposals (Phase 8 known issue — rangovas counts more outer corners than universal NRM2).
- **Month 2:** Begin togal.ai-inspired UX iteration (separate plan, post-accuracy).
- **Month 3:** Add per-contractor personalization layer if multiple rangovai onboard.

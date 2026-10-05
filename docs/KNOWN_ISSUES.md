# Pathon — Known Issues (Pre-Launch Assessment)

**Last updated:** 2026-07-25 (doc-truth pass — limitation statuses re-verified
against code). The body below is still the 2026-04-27 assessment; entries that
have since shipped are marked inline rather than deleted, so the history reads.
**Status:** Pre-production refactor complete + Phase 9 production-readiness fixes landed.
**Honest production-readiness for AI extraction:** ~93% (Phase 10 + cleanup + Phase 11 safety/observability).
**Honest production-readiness for full app (auth, design polish, multi-tenancy, browser cross-test):** ~70% — significant gaps remain.
*(2026-07-25: three of those four have since shipped — auth, per-user multi-tenancy, and the Nordic Slate design pass. The remaining items from that list are **automated browser cross-test** and an **accessibility audit**. The ~70% figure was never re-measured, so treat it as a stale April number, not a current score.)*

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
**Update 2026-07-25:** `RulesOverridePanel` was **removed from the UI 2026-05-06** (founder request: too heavy); the orphan file was **deleted 2026-10-05**. The live surface is `AssumptionsPanel`, opened from the **Prielaidos** button in `ProjectTopBar`, and it recomputes via `POST /api/recompute-quantities`, not `/recompute-interior`. `/recompute-interior` is still live — it now serves the room/polygon-edit path (`handleRoomsChange`).

### Limitation 2: Hidden tabs (`puslapiai`, `kiekiai`, `workspace`, `prielaidos`)
**Severity:** LOW. Tab content code exists but unreachable. **Status 2026-07-25: still true, and the TabBar shrank.** It now renders only `brezinys` / `main` / `aichat`; `rules` and `eksport` are reachable only via `ProjectTopBar` buttons, and the `prielaidos` block in `InteriorProject.jsx` is explicitly dead-gated `{false && tab === 'prielaidos'}`.
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
- ✅ File size limits — HTTP 413 / 400. *(Current values, 2026-07-25: `MAX_PDF_SIZE_BYTES = 200 MB`, `MIN_PDF_SIZE_BYTES = 100 B`. The "50 MB" written here in April is stale.)*
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

## Phase 11 — SHIPPED SINCE (verified against code 2026-07-25)

### ✅ Limitation 8: No authentication / multi-tenancy — FIXED
Session auth shipped: email + password (**bcrypt**, work factor 12) **and** Google OAuth (`/api/auth/google*`). `backend/auth.py` + `require_user` / `require_admin`. Every project-scoped endpoint requires auth and scopes the query by `user_id`; `db.upsert_project` has an ownership barrier. `SAMATU_AUTH_DISABLED=1` is a dev-only bypass and the app **hard-fails at boot** if it is set with `ENV=production`. Admin is an explicit `SAMATU_ADMIN_EMAIL` allowlist (legacy first-user fallback only when unset).

### ✅ Limitation 9: Project data only in localStorage — FIXED
SQLite backing store (`backend/db.py`, 10 tables) behind `/api/projects` CRUD. `frontend/src/lib/projectStore.js` is write-through: every mutation hits localStorage (instant) **and** the backend (durable, cross-device). Backend is the source of truth; the cache is purged on logout.
**Residual (small):** `pullProjectsFromBackend` replaces the cache wholesale rather than merging, so a project that only ever existed in localStorage (created while the backend write was failing) is dropped on the next pull.

### ✅ Limitation 10: No "re-extract" button — FIXED
`frontend/src/components/project/ReextractButton.jsx`, wired into `ProjectMainView`'s action row.

### ◐ Limitation 11: Design polish / accessibility audit — PARTLY FIXED
**Design:** done. The app runs the founder-approved **Nordic Slate** light theme (2026-07-11) — parchment/ink/evergreen tokens in `frontend/src/index.css`, plus the viewer chrome tokens. The old "functional but not designed" note no longer holds.
**Accessibility:** still open. No formal keyboard-nav audit, no WCAG contrast pass; ARIA labels exist in only ~18 components. Treat a11y as unaudited.

## Phase 11 — STILL PENDING

### Limitation 12: No browser cross-test
**Severity:** MED. **Impact:** Chrome/Safari/Firefox compatibility is not verified by any automated test.
**Status 2026-07-25:** UI changes *are* verified in a real browser, but ad-hoc via the Playwright MCP — there is **no `playwright.config.*` and no `e2e/` suite in the repo**, so nothing runs in CI and nothing is repeatable.
**Future fix:** Commit a Playwright config + a smoke spec, then run it in CI.

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
**Future fix:** ~~Reactivate AssumptionsPanel~~ — done (Limitation 1). `AssumptionsPanel` is live and `ReextractButton` exists, so the user *can* set overrides and re-run. What remains open is the narrower piece: **default per-paskirtis tile/parquet preferences** that persist across projects.

---

## Benchmark accuracy ceiling — paint & LED residuals (2026-06-06)

After the square-perimeter-synthesis fix (commit `771fb7e`: avg benchmark MAE
**6.87% → 5.78%**, zero regression on eksplikacija projects), two residuals remain.
A multi-round investigation (perimeter priors, niche-prompt tuning, coverage gating,
area priors, scale calibration, ceiling overage, **two live Vision spikes**) established
that BOTH are Vision **measurement ceilings**, not code bugs — do not re-litigate:

- **Objektas C paint −10.5%** — the bundled `project_pdf` (planning + lighting sheets)
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
- **Objektas B LED −18%** — Vision *recall* gap (niche prompt already recall-hardened;
  multi-page locator already runs pgs 5/6/7). The inference fallback over-bills Objektas C
  (+12.5%) while under-recovering Objektas B; **no global ratio change is safe**
  (verified: dropping san/vonia/wc → Objektas B −29.6%).

**Root cause is DATA/input-completeness, same pattern as objektas_d** — the dimensioned
architectural plan lives on a separate sheet not in the bundle.

**Answers (no further extraction cleverness warranted):**
1. **`/calibrate`** — contractor enters the exact floor/ceiling/LED value per project
   ($0, exact, never mutates the global calculator; `led_nisos_m` + `dazymo_plotas_m2`
   already registered as calibration metrics).
2. Bundle the **dimensioned architectural plan** into Objektas C's `project_pdf`.
3. Expand the **no-eksplikacija ground-truth set** (currently N=1–2) before any further
   "global" no-schedule fix — that's the only thing that unblocks this regime.

**Update 2026-06-06 — objektas_d unblocked (benchmark 3 → 4 scored projects):**
Bundled objektas_d's split single-page Layout4 sheets (Apmatavimai + Naujai-pertvaru floor
plan + Pakabinamu-lubu ceiling + Sviestuvu lighting → `objektas_d_TP_bundled.pdf`) and
re-extracted ($0.49 Vision). Areas now read correctly from the **eksplikacija** (4 rooms,
`plotas_saltinis=eksplikacija`; perimeter floor correctly did NOT fire). Overall MAE
**5.78% (3 proj) → 6.66% (4 proj)** — *added coverage*, not a regression
(objektas_a/objektas_b/objektas_c byte-identical). objektas_d paint is still **−14.2%**, but for a
**distinct** reason from objektas_c: **multi-level suspended ceilings with bulkhead faces
(kaktos at 2.39/2.51/2.66/2.26 m)**. Vision detects the heights (prose warning) but NOT the
bulkhead boundary lengths, and `calc_room_quantities` has no bulkhead-face-paint term → not
cleanly code-fixable from the current extract. **The no-schedule regime is hard for ≥2
distinct reasons** (no readable dimensions; multi-level ceilings). sernu remains blocked
(architectural plan absent from the fixtures; must be requested from Rangovas A).

---

## 🚫 Untested scenarios (cannot resolve without sample data)

We have **6** ground-truth projects (`ground_truth/`: objektas_a, objektas_c, objektas_d, objektas_b, romainiai, sernu — was 5 when this was written), all private residential new-builds. The pipeline has NEVER been validated on:

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
| PDFs >100 pages | Hits MAX_PAGES cap (rare in LT residential) | No longer silent — `_validate_pdf_upload` returns an LT warning naming the page count and that only the first 100 are analysed |

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
- [x] Document the soft-launch scope — **project types decided 2026-07-25: interior only.** Fasadai / Stogas / Žemės / Betonas are hidden behind the "kitas tipas" advanced disclosure in `NewProject.jsx` because their endpoints are thin (e.g. roof silently assumes a 30° pitch). Which contractors: still open.
- [ ] Plan for post-launch sample collection (10-20 real PDFs across untested scenarios)

---

## 📅 Post-launch follow-ups (recommended cadence)

- **Week 1:** Daily review of upload errors + warnings emitted. Patch obvious data-quality issues.
- **Week 2:** Sample 5 real production projects, manually verify accuracy vs backend output. Calibrate prompts.
- **Week 4:** Validate kampai variance vs real contractor proposals (Phase 8 known issue — Rangovas counts more outer corners than universal NRM2).
- **Month 2:** Begin togal.ai-inspired UX iteration (separate plan, post-accuracy).
- **Month 3:** Add per-contractor personalization layer if multiple rangovai onboard.

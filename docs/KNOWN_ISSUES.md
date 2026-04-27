# Sąmatų AI — Known Issues (Pre-Launch Assessment)

**Last updated:** 2026-04-27
**Status:** Pre-production refactor complete + Phase 9 production-readiness fixes landed.
**Honest production-readiness:** ~85% (was ~60% before Phase 9; up from 30% before refactor).

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

## ⚠ Known limitations (not fixed; documented for transparency)

### Limitation 1: AssumptionsPanel doesn't recalculate post-extraction
**Severity:** MED. **Impact:** "Edit assumptions and see updated quantities" feature broken for all new projects.
**Root cause:** New extractor returns pre-computed `patalpos[]`; the legacy frontend recalc path (`calculateInteriorQuantities` with `raw_calc_data`) is skipped because `raw_calc_data` is no longer emitted. Also: AssumptionsPanel ("Prielaidos" tab) is hidden from `TabBar` entirely.
**Workaround:** Users can edit individual room values inline (RoomCard) which DOES recalculate via `calcRoomQuantities` in RoomsGrid.
**Future fix:** Either re-trigger backend with `rules_override` on assumption change, or add Python-side recalc that takes patalpos + rules_override and replays `calc_room_quantities`.

### Limitation 2: Hidden tabs (`prielaidos`, `puslapiai`, `kiekiai`, `workspace`)
**Severity:** LOW. Tab content code exists in `InteriorProject.jsx` but tabs aren't in `TabBar`. They're unreachable but cause no runtime errors.
**Future fix:** Either delete the code or add tabs back if the features are wanted.

### Limitation 3: Mobile sidebar always visible
**Severity:** MED for on-site estimators using tablets/phones. **Impact:** Unusable on screens <600px wide.
**Root cause:** `AppLayout.jsx` doesn't use the `useIsMobile()` hook that exists in the codebase.
**Future fix:** Add hamburger toggle + responsive hide below `md` breakpoint.

### Limitation 4: `_zoom_changes[]` audit trail not displayed
**Severity:** LOW (transparency feature, not functional). Backend emits zoom adjustments per room ("perimetras: 7.5→7.3") but UI never shows them.
**Future fix:** Add expandable "Zoom refinements" section in RoomCard.

### Limitation 5: Dead V8 references in InteriorProject.jsx
**Severity:** LOW (cosmetic dead code). References to `project.v8_pages`, `project.raw_calc_data`, `project.page_classifications`, `project.confidence` (top-level). All gracefully nil-safe — no runtime errors.
**Future fix:** Cleanup in a dedicated commit.

### Limitation 6: Plytelės sienos high variance without sienų išklotinės
**Severity:** MED for projects without wall-development pages.
**Measurement:** P2 (no eksplikacija) determinism: plytelės_sienos CV 79% even WITH zoom (was 154% without zoom). Vision can't reliably classify "tile zone" without išklotinės.
**Mitigation:** `lt_sanity.warnings` includes "no eksplikacija" INFO when relevant — banner alerts user. They can manually adjust per-room `plyteles_sienos_aukstis_m`.
**Future fix:** When išklotinės are detected on later pages, give them special treatment in prompt.

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

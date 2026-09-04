# Full Correction Workspace — Production Architecture & Build Sequence

> Source: heavy-viewer architecture council (flood-fill reliability deep-dive + corrections-wiring deep-dive + 5 advisors → chairman). Supersedes the polygon/correction parts of `2026-06-14-viewer-correction-loop.md`. The halo transform fix (PR1 Tasks 1-2) is already shipped (`3915301`, `ae758bc`).

## The two decisive rulings (resolved against empirical reality, not averaged)
1. **Canonical store = the project blob** (`updateProject → localStorage + PUT /api/projects/{id}`). It already persists every edit (quantity overrides via `quantityOverride.js`, room polygons via `updateRoomPolygon`) AND replays on load for free (the row *is* the stored state). corrections_v2 JSONL is demoted to a **write-only ground-truth sidecar**; `db.log_correction` stays for assumption-bias only. Do NOT rebuild the live loop on JSONL (impedance mismatch: `apply_corrections` is `quantity_line`-only, keys on `code`/`quantity` which `darbu_sarasas` rows lack).
2. **Polygons = on-select lazy flood-fill, NOT auto-batch** (batch persists garbage for the leaky ~third). Seed-locating IS batched at build time (pdfplumber label locator — most rooms have no bbox to seed from).

## Empirical flood-fill reality (measured on Objektas A, area-checked vs contractor `plotas_m2`)
- **~4/11 auto-solve <15% area err, ~6/11 <30%, ~45% need a manual click.** Hard ceiling: annotated LT plans have uniform thin lineweight (walls = annotations thickness, no morphological separation) + fragmented interiors (room 110 = 44 white components). Pure-CV flood-fill caps near half.
- **The area-prior gate is the key**: `est_m2 = poly_area_pct × page_scale` vs known `plotas_m2`; reject if `area_err > 0.40`. It *detects its own failures* (flagged 105/106/108/109/110) → routes them to manual instead of shipping wrong polygons. Matches CLAUDE.md "ship 50% AI + fast correction, don't chase a perfect detector."
- Seeds: room-number text centroid (pdfplumber, filter `x_pct>0.1` to drop eksplikacija column), but sample a **dense local grid around it** (centroid lands on glyph ink → fails). Caveat: label-locator is PDF-format-dependent (Objektas A yes, Objektas D no) → graceful degrade to `manual_needed`.

## Canonical shapes (in the blob)
- **Quantity correction** (`darbu_sarasas` row, id `_id || ${eil_nr}-${aprasymas}`): `kiekis`, `quantity_source ∈ {manual_override, user_verified, ai}`, `verified:bool`, `ai_kiekis_original`, `manual_override_at`, `user_verified_at`.
- **Polygon correction** (`patalpos` row, id `nr`+`puslapio_nr`): `polygon_pdf`, `page_width_pdf`, `polygon_pct`, `polygon_source ∈ {auto_floodfill, bbox_fallback, manual_needed, corrected, manual}`, `plotas_m2`, `confidence`, `area_err`, `polygon_verified_at`.

## Build sequence (each independently shippable + browser-tested on Objektas A)
- **Step 0 — keystone check (NO code, first):** does a corrected `kiekis` reach F2 export, or do `darbu_sarasas` (UI) and `pozicijos` (export) silently diverge? Accept: corrected number reaches F2, or a concrete bug report.
- **Step 1 — Quantity verify + GT sidecar (reuse-heavy):** `acceptPositionQuantity` → `verified:true` + `quantity_source:'user_verified'`; `getQuantitySourceKind → 'verified'` (lights existing green UI); fix `correctionsApi` op builders (`targetCode:rowId`, `after:{kiekis}`); fire-and-forget `postCorrections` after blob write. Accept: "Patvirtinti" → green "Patikrinta" → reload → still green; JSONL gains an event.
- **Step 2 — Seed-locator + `auto_room_polygon` (read-only):** new `backend/extractor/room_seeds.py` (label locator); new `auto_room_polygon()` in `cv_polygon.py`; lower `validate_polygon` `max_area_pct` 0.80→0.42; area-err confidence; `room_graph.py` calls them + populates provenance. Accept: 102/105 tight halos; 110 shows 🔴 fallback NOT an 82% blob.
- **Step 3 — On-select lazy flood-fill + cache** (page basins memoized; cache result on room).
- **Step 4 — Polygon accept + persist + reseed** via existing `updateRoomPolygon` (`polygon_source:'corrected'`, derive `polygon_pct`) + existing `/api/click-to-fill` for reseed + GT append.
- **Step 5 — Manual SVG vertex trace** (reuse pure `polygonGeometry.js`/`takeoffStore.js`, Konva-free).
- **Step 6 — Verify badges + risk worklist** ("Tikrinti pirmiausia" sorted by polygon_source/confidence/area_err; verified drops off).

## Cut / retire (anti-gold-plating)
Auto-batch flood-fill; Konva `PolygonEditor` revival; mounting `CorrectionPanel.jsx` (wrong `code`/`quantity` model — retire); making `apply_corrections` the live read path; any DB migration. Honest flagged-not-broken: the ~45% manual rooms; Objektas D-class all-manual PDFs.

## Files
NEW: `backend/extractor/room_seeds.py`, `auto_room_polygon()` in `cv_polygon.py`, SVG vertex overlay in `PlanViewer.jsx`, worklist panel. MODIFY: `cv_polygon.py` (validate + confidence), `room_graph.py`, `quantityOverride.js`, `takeoffWorkflow.js`, `correctionsApi.js`, `projectStore.js`(`updateRoomPolygon`). REUSE: `page_raster_cache`, `click_to_fill_pipeline`/`/api/click-to-fill`, `VerifiedBadge.jsx`, `polygonGeometry.js`, `takeoffStore.js`, `planOverlayGeometry.js`, PositionsPanel dots. LEAVE: `exports_v2.py`, `corrections_v2.py`. RETIRE: `CorrectionPanel.jsx`.

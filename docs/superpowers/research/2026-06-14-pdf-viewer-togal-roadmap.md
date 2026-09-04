# PDF Viewer → togal.ai level — roadmap + adversarial critique (2026-06-14)

7-agent workflow: live togal re-check, existing-research distill, gap analysis vs our 3 viewers, Fabric/consolidation tech path, "what makes analysis faster" lever-ranking → synthesized roadmap → adversarial critique. Builds on the already-rich togal research (`togal-ux-patterns`, `togal-clickcount-ux`, `2026-05-02-competitor-viewer-ui-deep-dive`, etc.) — did NOT re-derive it.

## The core finding
**Getting to "togal-level" is a CONSOLIDATION problem, not a feature build.** ~70% of it is already written and scattered across three viewer generations:
- **PlanViewer** (LIVE, react-pdf + SVG) — page rail + page-type chips, zoom/pan, click-to-fill, confidence-colored overlays, bidirectional row↔drawing highlight. The spine.
- **PdfViewer** (LEGACY Konva, **zero imports — dead**) — richest features (PolygonEditor, AiRoomOverlay, CountTool, MagicWand) but parked.
- **Annotator** (rebuild target, **not wired into UI**) — raw-canvas, calibrate/measure, verification walkthrough that already persists `verification_state`.

## THE DECISION (both roadmap + critique agree)
**PlanViewer is the spine. Delete the dead Konva PdfViewer, harvest its pure math into `lib/`, retire the Annotator as a separate surface (parts donor, not a destination). Do NOT adopt Fabric.js (it's `extraneous` in node_modules — noise, not a decision). Do NOT build the mip-pyramid/tiling.**

## The critique's correction — SEQUENCING (this is the load-bearing part)
The roadmap crowned a **verification walkthrough** as #1. The critique killed that ordering, correctly:
- **Measured 50% false-green rate** (Objektas A, `2026-06-11-experiments-results.md`). A fast ✓/✗ sweep over a list where *half the greens are wrong* trains the founder to **rubber-stamp confidently-wrong numbers** — speed *amplifies* the error. A correct halo can't catch a right-polygon/wrong-number failure.
- This is exactly the **validate-first** verdict from today's councils (`2026-06-14-council-backend-vs-frontend.md`).
- The **keystone — `build_ground_truth.py` — still does not exist** (council named it 3×). The viewer's verify-loop is worthless until the numbers it surfaces are human-calibrated AND reproducible (kampai still swings 333/386/420).

## The merged plan

### NOW — two cheap viewer wins, zero accuracy dependency (ship this week)
1. **Delete dead code + page-type filter.** Delete `PdfViewer.jsx` (2324 lines, 0 imports) + Konva children; `npm rm fabric konva react-konva`; salvage `polygonGeometry.js` math. Then add filter pills + jump-to-first-of-type to PlanViewer's existing page rail (`pageTypes.js` data already flows — today it only tints chips). Kills the most-repeated friction: scrolling 40 sheets for the 3 išklotinės that drive interior numbers. **Highest ROI/hour in the codebase.**
2. **Triage-row → sheet flash.** Wire the **already-shipped** "N tikrinti" confidence rows in `PositionsPanel.jsx` to PlanViewer's **existing** bidirectional highlight: click a flagged pozicija → jump to its sheet + flash its polygon. The verify loop at ~20% of the cost of porting the Annotator walkthrough — and it inherits the honest triage framing instead of inventing a rubber-stamp sweep. (Fix the polygon→render-coords transform here only if the flash lands on the wrong room; verify on a real LT PDF.)

### THE PREREQUISITE for the deep viewer (the real #1, not a viewer task)
3. **`build_ground_truth.py` + variance-localization diagnostic.** Human-confirm a handful of quantities; log per-run counted primitives so kampai's ±13% scatter is localized before any formula touch. This is what turns the confidence dots from "decoration" into a real triage product and makes a full verification walkthrough worth building.

### LATER — the deep viewer build (AFTER numbers are reproducible + calibrated)
- Full verification walkthrough (port Annotator loop into PlanViewer).
- All-rooms overlay (paint every detected room confidence-colored, not just the focused one; reference dead `AiRoomOverlay.jsx`, reimplement in SVG).
- Editable click-to-fill (ungate + vertex-drag correction via salvaged `polygonGeometry`/`takeoffStore`, no Konva).
- Bbox visual search → cross-page count — **gated**: our bake-off shows `cv2.matchTemplate` over-counts ~100× on busy drawings; ships only with click-to-delete + confidence filter, behind the experimental flag until measured.

## NON-GOALS
Fabric.js · mip-pyramid/tiling · resurrecting any Konva component · Repeating-Groups/typical-floor (no instance model; founder's PDFs are single-unit) · revision-diff · Togal.CHAT measurement · multi-user collaboration · US-style schedules (CSI/imperial) · per-category rainbow palette (locked to single blue `#2a6fb5` on `#f6f5f2`).

## Net-new togal ideas worth noting (June 2026 live re-check)
- **Wall classification** (NEW) — auto-labels wall *type* (bathroom/corridor/shaft/interior/exterior). Directly relevant to LT: wet-room vs interior wall drives tiling/waterproofing/paint deductions. Worth stealing later.
- **Version overlay + change quantification** (NEW) — diff two plan revisions, quantify the delta. Later.
- Independent review confirms togal is **60–95% by sheet type** (not the "99%" marketing) and the load-bearing capability is the **correction loop**, not the detection — validating our own CLAUDE.md thesis ("ship ~50% AI + a fast correction tool").

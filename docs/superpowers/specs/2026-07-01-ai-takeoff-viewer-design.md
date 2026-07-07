# AI Takeoff Viewer — Design Spec

**Date:** 2026-07-01
**Status:** Draft for review
**Author:** brainstorming session (Sąmatų AI)

---

## 1. Goal (one sentence)

Turn the interior-project viewer from a **raw PDF with a number marker** into an **AI-first takeoff canvas** that draws the app's *already-computed* rooms, areas, counts and interior-finish quantities onto the plan — honestly flagged by confidence, corrected in seconds, and confirmed by the estimator so the final number is trustworthy.

## 2. Why (the problem, honestly)

- **Today the viewer shows almost nothing.** Vision extraction already produces every room with `plotas_m2`, `perimetras_m`, `elementai`, `bbox_pct` and (sometimes) `polygon_pct`, plus the full interior-finish žiniaraštis. But `AiRoomOverlay` is **not mounted** in `PlanViewer`, it only renders rooms that have `polygon_pdf` (which extraction never produces), and `AUTO_DETECT_POLYGONS` was disabled (founder, 2026-06-17) after auto-traced polygons proved inaccurate + costly. Net result the founder saw: open a real project → raw plan + a blue number circle. The AI's work is invisible on the drawing.
- **Two prior attempts failed on accuracy, and we must not repeat them:** (a) auto-traced room polygons (reverted to the number marker), and (b) the symbol counter (`cv2.matchTemplate`, Pipeline 3) which **over-counted ~100×** — 1772 hits where truth was 5 — because tiny legend glyphs match anywhere, with no way to prune.
- **The market gap we can own:** three independent research threads converge — togal (the leader) is ~85% accurate (≈60% on messy plans) and **signals uncertainty nowhere**; estimators need "4–6 weeks to learn when to trust it," low-confidence areas are silently skipped, bad scans degrade with no warning. **No takeoff tool tells the estimator *where* the AI is weak.** Our app already computes per-quantity provenance/confidence (🟢🟡🔴, CLAUDE.md §7). Surfacing it is a real, defensible differentiator, not decoration.
- **Togal literally cannot do interior-finish quantities** (paint net of openings, reveals, tile-from-elevations, waterproofing, drywall assemblies). That's the app's moat.

## 3. Core principle (the spine of every decision)

> **The AI proposes (imperfectly). The tool is honest about what it's unsure of. The estimator confirms or corrects in seconds. The final number is 100%-trustworthy because *they* signed off — not because the AI was perfect.**

This is the app's own bake-off conclusion ("ship 50–85% AI + a fast correction tool, don't chase a perfect detector") and exactly what the external research says estimators demand. **We do not claim a hero accuracy number.** 100%-automatic is not achievable (nobody's is); a 100%-*trustworthy* result, reached fast, is.

**Non-negotiable corollary (the founder's requirement):** the viewer is a *face*; **all quantities, confidence, and recompute flow through the app's existing engine** — Vision extraction → `interiorCalc`/`universal_rules` formulas → confidence system → `/api/recompute-quantities` → žiniaraštis. Nothing in the viewer is a parallel/mock calculation.

## 4. The experience (approved in brainstorming via interactive prototypes)

1. **One-click seed.** Open a project (or hit "Analizuoti") → the plan fills: rooms get translucent color + name + area, count markers drop, interior-finish quantities populate the panel — all from the existing extraction, drawn on the canvas for the first time.
2. **Honest confidence, on the drawing.** Every room/quantity carries 🟢 (read from eksplikacija/table), 🟡 (assumption, e.g. area synthesized from bbox), 🔴 (fallback/disagreement). Low-confidence items **pulse/badge on the plan** and collect into a **"Tikrinti pirmiausia" (check-first) worklist** in the panel, so the estimator's eye goes straight to the ~15% that matters instead of re-checking everything.
3. **Confirm → trust.** Click a flagged item → a card explains *why* it's unsure and offers **Patvirtinti** (lock as verified) / **Taisyti** (correct). Confirming turns it 🟢 and **locks** it (survives recompute). When the worklist hits zero: "✓ Viskas patikrinta — kiekiai patikimi."
4. **Fast correction** (stolen from togal, proven): Merge / Cut-Subtract / Split polygon primitives + single-key hotkeys (M/C/S/Esc) + bulk reclassify; and for room boundaries, the existing **click-to-fill flood-fill** upgraded with positive/negative-point refinement (Kreo/SAM pattern) + an "add boundary" closing line for leaky rooms.
5. **The counter, done right.** Draw a box around one symbol → the matcher **over-returns a little** (scale-aware glyph size + anchored to legend references, so ~30 candidates, not 1772) → candidates shown as keep/ignore markers with a **sensitivity slider**, **click-to-prune**, and an **eksplikacija cross-check** ("24 — matches the table's 24 rozetės 🟢"). Confirm → locked into counts.
6. **Bidirectional sync.** Click a room/quantity in the panel → the drawing pans/highlights it; click on the drawing → the panel row selects. (Cheapest high-impact interaction per the research.)
7. **Interior-finish superpowers togal can't match** (the moat, surfaced in the panel): auto-deducted window/door openings (with a `tikslus`/`praktinis` threshold toggle), reveals/angokraščiai, tile zones read from wall elevations (išklotinės), wet-room waterproofing zones, and one-surface→assembly expansion (primer + coats + Q-level sanding + corner bead).

## 5. Architecture

**Principle: the viewer is a rendering + interaction layer over the existing engine. No new quantity math in the viewer.**

```
Vision extraction (backend) ──▶ project.patalpos[] (plotas_m2, polygon_pct, bbox_pct, elementai, confidence)
                                project.pozicijos[]/darbu_sarasas[] (interior-finish quantities)
                                        │
                                        ▼
        ┌──────────────────────── AI Takeoff Viewer (frontend) ───────────────────────┐
        │  Canvas layers (SVG over react-pdf page):                                    │
        │    • RoomZoneLayer     — colored polygons (polygon_pct→screen) + labels+conf │
        │    • ConfidenceLayer   — flags/badges on low-confidence items                │
        │    • CountLayer        — count markers (from elementai + counter tool)        │
        │    • CorrectionLayer   — merge/cut/split + flood-fill refine (edit mode)      │
        │  Panel:                                                                       │
        │    • Kiekiai (grouped: Patalpos / Apdailos darbai) w/ confidence dots        │
        │    • "Tikrinti pirmiausia" worklist                                          │
        │  Sync: shared selection state (panel ⇄ canvas)                               │
        └───────────────┬───────────────────────────────────────────────┬─────────────┘
                        │ user confirms / edits / corrects              │ counter confirms
                        ▼                                               ▼
        POST /api/recompute-quantities  ◀── merges user edits + LOCKS (existing) ──▶ project.pozicijos
        POST /api/projects/{id}/corrections  (feeds build_ground_truth — the learning loop)
```

**Key integration points (existing code to reuse, not rebuild):**
- **Coordinate bridge (the missing link):** convert `polygon_pct` (fractions) → screen using `page_width_pdf/height` × render scale. This is the single thing that makes the AI's rooms visible; it was never wired. Where a room has no polygon, render a tasteful bbox+label with 🟡, never a fake precise polygon.
- **Confidence:** reuse the provenance→🟢🟡🔴 logic already in the extractor/confidence system; do not invent a new one.
- **Recompute + locks:** reuse `/api/recompute-quantities` and its existing user-edit/lock merge (`project_recompute_architecture`). "Patvirtinta/užrakinta" is a first-class value that survives rebuild — the app already supports this; the viewer just exposes it.
- **Corrections → learning:** every confirm/correct logs to the `corrections` table and feeds `build_ground_truth` — the viewer *is* the correction-workspace, closing the AI-improvement loop.
- **Flood-fill / click-to-fill / detect-room-polygons:** these already exist (backend CV). The viewer wires them as on-demand correction, not auto-on-load (respecting the founder's cost/accuracy call).
- **Rendering base:** stay on the app's existing `react-pdf`/`pdfjs-dist@4` (no engine swap). For 100+ page perf, virtualize page rendering (the verified virtualization work from the reverted branch `backup/measurement-viewer` can be salvaged for this).

## 6. Key design decisions & the honest constraints they answer

| Decision | Why (constraint it answers) |
|---|---|
| **Lead with surfacing existing data + confidence — NOT auto-tracing polygons** | The auto-polygon attempt already failed on accuracy. v1 must show value *without* depending on perfect segmentation: color the rooms we can (polygon_pct), label the rest (bbox), flag honestly. Polygon accuracy is an *opt-in correction*, not a load-time gamble. |
| **Per-item provenance confidence 🟢🟡🔴 + "check-first" worklist** | The market gap. More meaningful than togal/Kreo pixel-similarity %. Directs attention so estimators don't re-verify everything. |
| **Confirm-to-lock (verified state survives recompute)** | Underdeveloped market-wide; the app's recompute-merge already supports locks. Turns "AI said 85%" into "I verified 100%." |
| **Counter = little-over-return matcher + review layer + eksplikacija cross-check** | Directly fixes the 100× failure. A slider can't prune 1772→5; a scale-aware, legend-anchored matcher returning ~30 + fast prune + table cross-check can. |
| **Steal togal's correction primitives (merge/cut/split + hotkeys)** | Proven-fast; correction speed is the whole ballgame (tools get abandoned when "fixing ate the time saved"). |
| **Interior-finish assemblies + auto-deduct openings + tile-from-išklotinės + waterproofing zones** | The moat; togal stops at footprints. Uses formulas the app already has. |
| **Graceful low-quality-scan handling** | LT PDFs are flattened raster; vector snapping does nothing. Warn up front; lean on ortho snap + manual fallback; never AI-only. |
| **Verify in the REAL app (InteriorWorkspace + real project), not a harness** | The measurement-viewer attempt passed a harness but broke in the real app. Real-app verification is mandatory before "done." |

## 7. Phasing (each phase independently shippable; ordered by value ÷ risk)

**Phase 1 — Make the AI visible + honest (the core "wow", lowest risk).**
Mount a RoomZoneLayer in `PlanViewer`; polygon_pct→screen bridge; colored zones + area labels for rooms that have polygons, tasteful bbox+label for those that don't; per-room confidence dot; the "Tikrinti pirmiausia" worklist; bidirectional panel⇄canvas sync. **No new detection.** This alone transforms the "raw plan" complaint and is near-zero accuracy risk (it only *shows* what's already computed, honestly).

**Phase 2 — Confirm & correct (trust).**
Confirm/lock (verified state via recompute merge); "why unsure" cards; flood-fill click-to-fill upgraded with positive/negative-point refine + add-boundary; corrections logged to `build_ground_truth`.

**Phase 3 — The counter, done right.**
Scale-aware, legend-anchored candidate matcher (backend) that over-returns modestly; review UI (sensitivity slider, click-to-prune, Matches/Possible-Matches); eksplikacija cross-check; confirm→counts.

**Phase 4 — Interior-finish superpowers (the moat).**
Per-surface assignment; auto-deduct openings with `tikslus`/`praktinis` toggle; assemblies (surface→primer/coats/sanding/corner bead); tile zones from išklotinės; wet-room waterproofing zone tool; merge/cut/split polygon primitives + hotkeys.

**Phase 5 (later) — Polish & scale.**
100+ page virtualization (salvage from `backup/measurement-viewer`); revision Compare overlay (red/blue diff); background-dim/isolate; keyboard hot-path; repeating-groups for identical floors.

## 8. Non-goals (YAGNI)

3D view; a perfect auto-segmentation model; MEP/structural takeoff; imperial units; vector snap-to-content (raster PDFs have no vectors); a hero accuracy claim; replacing the react-pdf engine.

## 9. Error handling & edge cases

- **Uncalibrated scale:** areas show, but flagged 🟡 "mastelis nepatvirtintas" until confirmed; never present unverified metres as green.
- **Low-quality / low-res scan:** detect + banner up front ("brėžinys neaiškus — matavimai gali būti netikslūs") rather than letting the estimator discover mid-work.
- **Room with no geometry:** bbox+label + 🟡, with a one-click "nubrėžti kontūrą" (flood-fill) — never a fabricated polygon.
- **Counter over/under-return:** always reviewable; cross-check against eksplikacija count and *tell the user* when they disagree.
- **Recompute failure / partial:** surface `_degradations` from the recompute API; never silently drop a quantity.

## 10. Testing strategy

- **Ground-truth fixture:** the contractor-validated Beržų g. 24 project (known 419.92 paint, 42.3 LED, 165.61 ceiling) — the viewer's displayed/confirmed quantities must match, and confidence must correctly flag the synthesized ones.
- **Confidence correctness:** provenance→color mapping unit-tested; low-confidence items appear in the worklist + on the plan.
- **Counter:** on a known sheet, matcher over-returns modestly (not 100×); prune-to-truth reachable in a few actions; eksplikacija cross-check fires.
- **Coordinate bridge:** polygon_pct→screen round-trips + aligns to the rendered page (numeric + visual).
- **Real-app verification (mandatory):** every phase verified in the actual `InteriorWorkspace` route with a real logged-in project — not a standalone harness (the lesson from the reverted measurement viewer).

## 11. Risks (named, not hidden)

- **Segmentation accuracy** remains the hard, unsolved part — mitigated by *not* depending on it in Phase 1 and making correction cheap.
- **Counter matcher** must be tamed from 100× to ~1.3× over-return; if the legend-anchor + scale approach underperforms, the review layer still helps but the feature slips.
- **Scope size** — this is a multi-phase product, not one change; each phase must ship and be verified independently, and each phase gets its own implementation plan.
- **Raster-PDF reality** limits snapping/vector tricks; designed around it.

## 12. Open questions for the user (before/along the implementation plan)

1. Phase 1 first (make the AI visible + honest) as the shippable slice — agreed?
2. Confidence source: use the extractor's existing provenance flags as-is for v1, or refine the mapping first?
3. Counter (Phase 3): acceptable to start with the *review UI* over the current matcher (even if it over-returns) while the legend-anchored matcher is built in parallel?

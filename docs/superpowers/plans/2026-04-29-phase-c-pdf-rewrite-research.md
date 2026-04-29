# Phase C — PDF Interactivity Plan (Synthesis)

**Date:** 2026-04-29
**Status:** Research complete — implementation gated on user go/no-go after reviewing this doc.

This plan synthesises four parallel research streams into a single, actionable Phase C strategy. It is opinionated: it recommends one path, names the gates that would make us deviate, and lists the things we will explicitly NOT do.

**Source research (read these for full depth — this doc references them, doesn't duplicate them):**
1. `research/2026-04-29-phase-c-competitor-tech.md` — how Bluebeam / Togal / Kreo / STACK actually solve this
2. `research/2026-04-29-phase-c-libraries.md` — PDF + overlay stack decision matrix
3. `research/2026-04-29-phase-c-opencv-feasibility.md` — honest assessment of CV / pretrained models on LT plans
4. `research/2026-04-29-phase-c-polygon-ux.md` — Bluebeam-style polygon edit UX, library shootout, anti-patterns

---

## 1. Executive verdict

**Stop using Claude Vision for polygon coordinates. Build a manual-trace polygon editor first, spike a grid-calibrated Vision experiment second, and only then decide whether to invest 4-6 weeks in a hybrid OpenCV + Vision-labelling pipeline.**

The bbox_pct disaster (clicking "Sandėliukas", garage highlights) is not a prompt-tuning problem. LLMs are bad at pixel geometry — every competitor that solved this (Kreo, Togal, STACK) solved it with deterministic CV server-side, with the LLM relegated to room *labelling* not room *finding*. Bluebeam doesn't even use ML; their Dynamic Fill is classical flood-fill on PDF line weights.

We are a one-developer team with no CV expertise. Trying to build a Mask R-CNN pipeline as the *first* step is the trap that kills small teams. The right shape is:

- **Always-works floor** = manual polygon trace with Bluebeam-style UX (2-3 weeks)
- **Cheap accuracy spike** = grid-calibrated Vision (2 days, may unlock 80% accuracy without any CV)
- **Real automation** = hybrid OpenCV-finds + Vision-labels, behind a feature flag, only if the spike fails (4-6 weeks)

This sequence guarantees Phase C ships in 3 weeks even if every automation experiment fails. It buys us optionality without betting the timeline on research.

---

## 2. Strategic shape

```
┌──────────────────────────────────────────────────────────────────┐
│  PHASE C-1   Path A: Manual polygon editor    [2-3 weeks]        │  ← REQUIRED
│              react-konva + Bluebeam UX, ortho-90° default         │
│              Always-works floor. Ships even if everything else    │
│              fails.                                                │
├──────────────────────────────────────────────────────────────────┤
│  PHASE C-2   Path C spike: grid-calibrated Vision  [2 days]      │  ← GATE
│              Render PDF with overlaid coordinate grid → ask        │
│              Vision for polygons in grid coords, not 0-1 pct.     │
│              IF mIoU ≥ 0.80 on 5 sample LT projects → Phase C-3   │
│              demoted to "future enhancement"; ship Path A only.    │
├──────────────────────────────────────────────────────────────────┤
│  PHASE C-3   Hybrid CV + Vision-labelling   [4-6 weeks]          │  ← CONDITIONAL
│              ONLY if Path C spike fails (mIoU < 0.80).             │
│              Server-side OpenCV (Bluebeam Dynamic-Fill recipe) →   │
│              candidate polygons → Vision labels them with room     │
│              names → presented as "suggestions, please verify" in  │
│              the Path A editor.                                    │
└──────────────────────────────────────────────────────────────────┘
```

The decision points are explicit. Phase C-1 is unconditional. C-2 is a 2-day spike gating C-3. C-3 only runs if C-2 fails.

---

## 3. Architecture

### Data model — the polygon_pdf gap

`AiRoomOverlay.jsx` and `TraceOverlay.jsx` already render `polygon_pdf` (V9 — array of `[x, y]` in PDF point space) when present, falling back to `bbox_pct` (V8) when not. **No producer in `backend/extractor/` populates `polygon_pdf` today.** The renderer is polygon-ready; the gap is upstream.

Phase C is therefore primarily a **producer + editor** problem, not a renderer rewrite.

```
                ┌─────────────────────┐
                │  PDF page rendered  │ ← react-pdf + pdfjs-dist (KEEP)
                └──────────┬──────────┘
                           │
              ┌────────────┴────────────┐
              │ Konva 3-layer overlay   │ ← react-konva (KEEP)
              │  L1: PDF backdrop       │
              │  L2: committed polys    │ listening:false
              │  L3: active edit        │ listening:true
              └────────────┬────────────┘
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
   ┌───▼────┐         ┌────▼─────┐        ┌────▼────────┐
   │ MANUAL │         │  GRID-   │        │  HYBRID     │
   │ TRACE  │         │  VISION  │        │  CV+LABEL   │
   │ (C-1)  │         │  (C-2)   │        │  (C-3)      │
   └────────┘         └──────────┘        └─────────────┘
   user clicks        Claude Vision        OpenCV finds,
   corners            with grid prompt     Vision labels
   ALWAYS WORKS       2-day spike          server-side,
                                           4-6 weeks
                           │
                           ▼
                ┌─────────────────────┐
                │ polygon_pdf written │ ← single output schema
                │ to project state    │   regardless of source
                └─────────────────────┘
```

All three producers write to the **same** `polygon_pdf` field. The editor edits whatever's there. There is no fork in the data model.

### Locked stack decisions (from research)

| Concern | Decision | Why |
|---|---|---|
| PDF rendering | **KEEP** `react-pdf@9.1` + `pdfjs-dist@4.6` | Free, mature, already in stack. Apryse not justified <€60k ARR. |
| Worker setup | Move `pdf.worker.mjs` to `public/` via `vite-plugin-static-copy`; configure `workerSrc` inside the PdfViewer module, not `main.jsx` | Documented prod-cache bug we already see intermittent symptoms of |
| Memory | Explicit `pdf.destroy()` + `page.cleanup()` on unmount; render only viewport ± 1 | Mobile Safari kills tabs at ~250 MB; 100-pg sessions leak |
| Overlay | **KEEP** `react-konva@18.2` + `konva@9.3` | Bundle ~70 KB, best edit ergonomics, already integrated. PixiJS only if real customer PDF blows past 500 polygons at <30fps. |
| Konva config | `perfectDrawEnabled: false`, `transformsEnabled: 'position'`, `shadowForStrokeEnabled: false` globally; replace deprecated `FastLayer` with `new Konva.Layer({ listening: false })` | Free perf wins, stays current with Konva 9 deprecations |
| Drag perf | Imperative `useRef` + `.position()` during drag, commit on `dragend` | 5-10× faster than React state on every move |
| Drag layer | Only the active-edit layer is `listening: true`; committed polygons live on a non-listening layer | Hit-graph cost is per-listening-shape |
| Server CV (if needed) | Server-side Python OpenCV, not browser opencv.js | opencv.js is 8 MB + memory-leaks; server-side runs 300-700 ms/page |
| Mobile editing | **View-only banner in v1** | Estimators don't draw on tablets; honest defer to v2 |

### Locked anti-decisions (from research)

- **NO** mupdf-wasm — AGPL incompatible with closed SaaS; commercial license costs same as Apryse without the annotation UI.
- **NO** Fabric.js — documented memory leaks via `canvas.clear()` and pattern fills.
- **NO** paper.js / PixiJS / Three.js as overlay — Konva covers our 2D needs; mixing engines is pure overhead.
- **NO** Mapbox-GL-Draw / Leaflet.draw — drag entire map engines for a non-map use case.
- **NO** Apryse / Nutrient SDK in Phase C — re-evaluate at €60k ARR or 200 seats; $5-15k/yr eats 40% of Y1 revenue today.
- **NO** browser-side opencv.js for full page processing — kills mobile, leaks memory.
- **NO** fine-tuning ML models — we don't have the labelled LT corpus (200-500 plans needed); CubiCasa5K hits 57.5% mIoU cross-dataset.
- **NO** Bezier polygons — estimators get confused; floor plans are polygonal.
- **NO** forced pixel-perfect close — accept Enter, double-click, AND click-first-vertex.

---

## 4. Phase C-1 — Manual polygon editor (always-works floor)

**Effort:** 2-3 weeks solo dev with Claude Code.
**Risk:** low — every interaction pattern is documented in `phase-c-polygon-ux.md`.

### Acceptance criteria (v1 done)

1. User can enter polygon-trace mode for any room from the right panel
2. Click adds vertex; Enter / dblclick / click-first-vertex all close the polygon
3. Esc cancels mid-edit (never commits)
4. Backspace removes last vertex during trace
5. Ctrl+Z = operation-level undo post-commit
6. **Ortho-90° mode default ON** (toggleable via Shift to free-angle); rubber-band shows the snapped 90° preview
7. Vertex drag-to-move with snapping (vertex 12px > edge 8px > grid 6px); Alt overrides snap
8. Midpoint ghost circles for vertex insertion (Google Maps pattern)
9. Right-click vertex → delete; right-click edge → split
10. Polygon area auto-recalculates on commit; updates `plotas_m2` in room data
11. Self-intersecting polygons rejected on commit with a toast
12. Mobile: edit mode disabled with banner "Polygon editing on desktop only"
13. Polygon persists to `polygon_pdf` field; round-trips through localStorage + backend sync

### Critical UX rules (from research)

- Single active snap target highlighted, never multiple — confusion source
- Mode indicator visible at all times (am I editing or viewing?)
- Vertex hit areas ≥ 8 px desktop, 44 px touch (when v2 mobile arrives)
- Lithuanian tooltip labels for every shortcut

### Files to touch (estimated)

- **Modify:** `PdfViewer.jsx` — wire polygon-edit tool into LeftToolRail
- **Create:** `PolygonEditor.jsx` — the active-edit Konva layer, ~400 lines
- **Create:** `polygonGeometry.js` — area, ortho-snap, self-intersection check, simplify
- **Create:** `polygonOperations.js` — undo/redo log, op-level granularity
- **Modify:** `projectStore.js` — `polygon_pdf` write path
- **Modify:** `AiRoomOverlay.jsx` — committed-polygon listening: false split from in-progress edit

The full keyboard table, snap algorithm pseudocode, and 13-item acceptance checklist are in `research/2026-04-29-phase-c-polygon-ux.md`. The implementer should treat that doc as the spec.

---

## 5. Phase C-2 — Grid-calibrated Vision spike (2 days, gate)

**Effort:** 2 days. **Risk:** low (it's a spike; outcome is "ship or skip C-3").

### Hypothesis

Vision is bad at returning normalised 0-1 coordinates because LLMs don't think in floating-point pixel space. They are however good at reading text labels and following grid coordinate systems (chess notation, lat/long).

**Test:** render the PDF page with a numbered overlay grid (e.g., 20×20, labelled A1-T20), include the grid in the prompt, ask Vision to return polygons as a sequence of grid cells (`["B3", "B4", "C4", "C3"]`). Convert grid cells back to PDF coordinates server-side.

### Pass/fail gate

- **Pass:** mean polygon-IoU ≥ 0.80 on 5 sample LT projects (apartments) we have under `training-data/projektas_1-5`. → Ship Path A only; demote Path B to "future enhancement"; close Phase C.
- **Fail:** mIoU < 0.80. → Trigger Phase C-3 hybrid pipeline.

### Implementation outline (don't pre-build, this is a spike)

1. Write a one-shot Python script that overlays a labelled grid on a rendered page (`pdf2image` + `Pillow.ImageDraw`)
2. Modify the Vision prompt to ask for polygons-as-grid-cells, single page
3. Run on 5 known projects, score against polygons traced manually via Phase C-1 editor
4. Decide

This is genuinely 2 days. If it works, we save 4-6 weeks of CV work. If it doesn't, we lost 2 days.

---

## 6. Phase C-3 — Hybrid CV + Vision-labelling (conditional, 4-6 weeks)

**Triggered only if C-2 fails.** Effort: 4-6 weeks solo. Risk: medium.

### Architecture (Bluebeam Dynamic-Fill recipe + Kreo's labelling split)

```
PDF page (raster) ──→ OpenCV pipeline (server-side, Python)
                       ├─ Adaptive threshold
                       ├─ Morphological close (gap-fill at doors)
                       ├─ Find external contours
                       ├─ Polygon simplification (Douglas-Peucker)
                       ├─ Filter by area + aspect ratio
                       └─→ candidate polygons (no labels)
                                    │
                                    ▼
                       Vision labelling pass
                       (Claude Opus, but only "what room is THIS polygon")
                       Tightly cropped image around each candidate +
                       eksplikacija text → room name + paskirtis
                                    │
                                    ▼
                       polygon_pdf populated; presented to user as
                       "AI suggestions — please verify each one"
                       in the Phase C-1 editor (which already supports
                       editing them).
```

This is the architecture every serious competitor uses. We are doing it last (after Path A) because we cannot afford to bet 4-6 weeks of timeline on it before the always-works floor is shipping.

### Realistic accuracy expectations (from research)

- Standard LT apartments: 70-80% room-level mIoU
- Commercial / complex layouts: 30-50% — likely unusable, user falls back to manual
- Hand-annotated drawings, photocopied scans: <30%, manual fallback

We will frame this in UI as "AI siūlymai — patikrinkite kiekvieną" (suggestions, please verify), not "extracted rooms". Path A remains the primary path; C-3 is acceleration.

### Tooling shortlist (don't build all)

- **`opencv-python`** (server) — adaptive threshold + contour finding (NEW dep)
- **`shapely`** (already in stack) — polygon simplification, intersection, area
- **`zcemycl/TF2DeepFloorplan`** — most production-friendly pretrained model to spike *if* classical OpenCV plateaus below 70%
- **`Pillow`** (already via pdf2image) — grid overlay for C-2 spike

### Kill switches

- If after week 2 of C-3 the classical OpenCV recipe is below 60% on apartments, stop and run TF2DeepFloorplan spike (1 week)
- If after week 4 of C-3 the hybrid is below 70% on apartments, stop and ship Path A as the only flow with a "improvements coming" banner. The 4 weeks become an investment in the labelling corpus.
- We will NOT spend more than 6 weeks on C-3 in this phase regardless of accuracy. Better to revisit in Phase D once we have a labelled LT corpus from real users.

---

## 7. What this displaces from the current pipeline

`backend/extractor/vision_call.py` currently extracts rooms with `bbox_pct` from a single Vision pass. Phase C does NOT remove this — it adds a new producer that writes `polygon_pdf` and `bbox_pct` becomes a fallback shadow field.

**Migration plan:**
- Phase C-1 only: existing Vision rooms still extracted with `bbox_pct`; user can promote any room to a manually-traced polygon. The right panel shows a "🟢 polygon set" / "🟡 bbox only — please trace" badge per room.
- Phase C-2 pass (if successful): re-extraction populates `polygon_pdf` directly; bbox path retained as legacy fallback.
- Phase C-3 hybrid: replaces `bbox_pct` extraction entirely for new projects; old projects keep `bbox_pct` until user manually re-traces.

We DO NOT remove Vision room *labelling*. Vision remains the labelling brain throughout — it's only the *coordinate* pass we're replacing.

---

## 8. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| pdf.worker prod-cache bug breaks deploys mid-Phase-C | medium | high | Repro & fix in a 30-min spike BEFORE Phase C-1 begins |
| Konva drag perf collapses past 500 polygons | low | medium | We have no real PDF >300 today; revisit trigger documented |
| Path C grid-Vision spike hits 70-79% (ambiguous) | medium | medium | Pre-decided gate at 0.80; do NOT move the goalposts mid-spike |
| Path C-3 plateaus below 70% | medium | medium | Hard 6-week cap; ship Path A as primary regardless |
| Self-intersecting polygons silently break area calc | medium | high | Reject on commit with toast; unit test with known crossing case |
| User edits polygon, area updates, but kiekiai don't recompute | high | high | Polygon edit MUST trigger `interiorCalc.js` recompute (just like Prielaidos changes do today) |
| Mobile users complain about view-only | low | low | Banner is honest; Phase D adds magnifier loupe + 44px hit areas |
| New `opencv-python` Python dep adds 70 MB to backend | low | low | Only if C-3 triggers; mitigated by pinning version + `--no-deps` for transitive |

---

## 9. Decision gates (with explicit go/no-go criteria)

```
GATE 1 — Before Phase C kickoff
  □ pdf.worker prod-cache bug reproduced & fixed (30 min)
  □ User signs off on Path A as primary (this doc)

GATE 2 — End of Phase C-1 (week 3)
  □ All 13 acceptance criteria pass
  □ Konva drag stays >30 fps on 100-polygon test page
  □ Polygon edit triggers interiorCalc.js recompute correctly
  → Ship Path A. Begin Phase C-2 spike.

GATE 3 — End of Phase C-2 (day +2)
  □ Run grid-Vision on 5 LT projects, score mIoU
  IF mIoU ≥ 0.80:
    → Ship grid-Vision behind feature flag; Phase C closed
  IF mIoU < 0.80:
    → Trigger Phase C-3 hybrid

GATE 4 — Mid Phase C-3 (week +2 of C-3)
  □ Classical OpenCV recipe accuracy on apartments
  IF ≥ 70%: continue
  IF 60-70%: spike TF2DeepFloorplan (1 week sidequest)
  IF < 60%: STOP. Ship Path A as primary; close Phase C; revisit in Phase D with corpus.

GATE 5 — End of Phase C-3 (week +6 of C-3)
  HARD CAP. Ship whatever state C-3 is in (behind flag if <70%).
  No "one more week" — research agent specifically warned about this trap.
```

---

## 10. Decisions (locked 2026-04-29 with user)

1. **Mobile editing** — view-only banner in v1; full editing deferred to Phase D. ✓
2. **Path C spike timing** — runs after C-1 ships, scored against C-1's manually-traced ground truth. ✓
3. **`opencv-python` dep** — approved for C-3 if triggered; Apache 2.0, ~70 MB backend image hit. ✓
4. **Quality bar** — aim for full quality on C-1, no pre-planned shortcut budget. We'll handle overruns if/when they happen. ✓
5. **Old project migration** — no migration. Renderer already falls back to `bbox_pct` when `polygon_pdf` is missing, so old projects keep working unchanged. Per-room badge ("🟡 bbox only" / "🟢 polygon traced") signals state; user can manually trace any room to upgrade it. The existing "Re-extract" button stays as-is — kept for edge cases, not auto-triggered. ✓

---

## 11. Files / endpoints expected to change in Phase C-1

(Approximate — actual planning happens in the implementation plan after user approval.)

**Frontend (new):**
- `components/project/PolygonEditor.jsx` — active edit layer
- `components/project/PolygonReviewBadge.jsx` — per-room "polygon ready" indicator
- `lib/polygonGeometry.js` — area, snap, self-intersection
- `lib/polygonOperations.js` — undo/redo log

**Frontend (modify):**
- `components/project/PdfViewer.jsx` — add polygon-edit tool to LeftToolRail
- `components/project/AiRoomOverlay.jsx` — split listening:true active edit from listening:false committed
- `components/project/TraceOverlay.jsx` — already supports polygon_pdf, no changes
- `lib/projectStore.js` — `polygon_pdf` write path
- `utils/interiorCalc.js` — accept polygon-derived `plotas_m2` override

**Backend (Phase C-1 — minimal):**
- No backend changes required for C-1 (polygons round-trip through existing project sync)
- `prompt.py` — add a "polygon hint" field for users who want to seed Vision from a manual trace

**Backend (Phase C-3 — conditional):**
- `extractor/cv_polygon.py` — new module, OpenCV pipeline
- `extractor/vision_call.py` — split labelling pass from coordinate pass
- New endpoint `POST /api/projects/:id/recompute-polygons-cv`
- New dep `opencv-python`

---

## 12. Why this beats every alternative we considered

- **"Just fix the Vision prompt"** — every prompt-engineering attempt at LLM coordinate accuracy plateaus at 50-65% on real plans. Path C-2 is the maximum prompt-engineering can buy.
- **"Use Apryse, they have polygon tools"** — $5-15k/yr eats 40% of projected Y1 revenue. Re-evaluate at €60k ARR.
- **"Build OpenCV first, manual editor as fallback"** — bets 4-6 weeks on research before shipping anything. Solo team can't afford that.
- **"Train our own ML model"** — we don't have 200-500 labelled LT plans. Path A users will produce that corpus over 6-12 months; revisit in Phase D.
- **"Use opencv.js in browser"** — 8 MB bundle, memory leaks, kills mobile. Server-side OpenCV is 300-700 ms/page; latency is fine for "click → AI suggestions" UX.

---

## 13. Recommendation

**Proceed with Phase C-1 (manual polygon editor) as a 2-3 week dedicated sprint.** Run Phase C-2 grid-Vision spike at the end of week 3. Decide on Phase C-3 from the gate score.

Before kickoff, please:
1. Confirm the mobile view-only decision
2. Confirm Path C spike timing (recommended: between C-1 and C-3)
3. Read `phase-c-polygon-ux.md` end-to-end — that doc is the C-1 spec
4. Read the executive sections of the other three research docs (skim, ~10 min total)

Once confirmed, the next step is the implementation plan for C-1 (separate document, written via `superpowers:writing-plans`, broken into bite-sized tasks).

---

## 14. References

**Research bundle:**
- [Competitor PDF tech](../research/2026-04-29-phase-c-competitor-tech.md)
- [PDF + overlay libraries](../research/2026-04-29-phase-c-libraries.md)
- [OpenCV / pretrained model feasibility](../research/2026-04-29-phase-c-opencv-feasibility.md)
- [Polygon edit UX](../research/2026-04-29-phase-c-polygon-ux.md)

**Code touchpoints surveyed for this synthesis:**
- `frontend/src/components/project/PdfViewer.jsx` (1739 lines)
- `frontend/src/components/project/AiRoomOverlay.jsx` (213 lines, polygon_pdf renderer ready)
- `frontend/src/components/project/TraceOverlay.jsx` (155 lines, polygon_pdf consumer)
- `backend/extractor/vision_call.py` — current bbox_pct producer
- `backend/extractor/prompt.py` — Vision prompt with bbox_pct schema
- `backend/requirements.txt` — confirmed: shapely ✓, no opencv ✗

**Strategic anchors:**
- CLAUDE.md §1 (interior finishing formulas — any polygon must round-trip through `interiorCalc.js`)
- CLAUDE.md §6 (validation checks — polygon area must satisfy "wall area = 2.5-4× floor area" sanity)
- CLAUDE.md §7 (confidence levels — manual-traced polygon = 🟢 HIGH, AI-suggested = 🟡 MEDIUM until verified)

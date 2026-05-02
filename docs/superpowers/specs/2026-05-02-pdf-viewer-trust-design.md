# PDF Viewer — Trust + Click-to-Fill + Visual Polish

**Date:** 2026-05-02
**Status:** Direction approved; design ready for implementation planning.

This spec is the parent design for three sequenced workstreams that fix the "PDF viewer is authoritative-but-wrong" problem identified after Phase C-1 ship. Each workstream gets its own implementation plan; this doc is the strategic anchor.

**Source brainstorm:** session 2026-05-02. User directives:
- Drop the broken bbox-flash highlight (eksplikacija numbers on the drawing already serve "where" navigation).
- Trust through provenance, not through pretending the AI is accurate.
- Pursue Togal-style **classical-CV** features (click-to-fill walls, à la Bluebeam Dynamic Fill). Skip Togal-style ML auto-detection (no training data).
- Visual polish needed — current viewer "still looks ugly".
- All three at the end. Sequence them; pause for user smoke at natural boundaries.

---

## 1. Goal

Make the PDF viewer assistive for a Lithuanian estimator: trust the numbers via provenance (Phase C-2), eliminate manual tracing as the default work via click-to-fill walls (Phase C-3), and ship a visual polish pass (Phase C-4).

## 2. Three phases

```
┌──────────────────────────────────────────────────────────────────┐
│  C-2  Trust through provenance        [~2 weeks]                  │
│       Confidence badges from area-confidence (not polygon-state)  │
│       Per-number "iš kur tai?" trail                              │
│       Kill the wrong-flash bbox highlight                         │
│       Backend: NO changes (sources already extracted)             │
├──────────────────────────────────────────────────────────────────┤
│  C-3  Click-to-fill walls             [~4-6 weeks]                │
│       Server-side OpenCV flood-fill (Bluebeam Dynamic Fill)       │
│       Replaces manual tracing as DEFAULT for un-traced rooms      │
│       New backend dep: opencv-python (~70 MB)                     │
│       New endpoint: POST /api/click-to-fill                       │
├──────────────────────────────────────────────────────────────────┤
│  C-4  Visual polish pass              [~1 week, parallel-able]    │
│       PDF viewer chrome (toolbar, thumbnails, zoom motion)        │
│       Right panel hierarchy + badge integration                   │
│       Tightened color palette + motion                            │
│       Run /superpowers:frontend-design against running app        │
└──────────────────────────────────────────────────────────────────┘
```

Each phase ships independently. C-2 is the immediate ship. C-3 builds on C-2's confidence framework. C-4 can interleave at any point — it's paint, not architecture.

## 3. Phase C-2 — Trust through provenance

### 3.1 The problem to fix

Today, when an estimator clicks a room name in the right panel, a blue bounding box flashes on the PDF in a roughly-correct-but-often-wrong location. This is dishonest UX — it claims precision the AI doesn't have.

Worse: the per-room status badge shipped in Phase C-1 (`🟢 polygonas` / `🟡 tik bbox — apvesk`) reflects polygon EXISTENCE, not number CONFIDENCE. A room with no polygon but accurate eksplikacija-derived area shows 🟡 — implying low confidence — when the area is actually rock-solid. The badge is lying about what matters.

### 3.2 What ships

**3.2.1 AreaConfidenceCalculator** — pure function in `frontend/src/lib/areaConfidence.js`

Computes per-room confidence from available sources:

| Source | Reliability | How detected |
|---|---|---|
| `eksplikacija` text | high | `room.plotas_source === 'eksplikacija'` OR `room.plotas_m2` matches eksplikacija table row |
| `manual_polygon` | high | `room.polygon_source === 'manual'` AND `polygon_pdf` set |
| `dimension` annotations | medium | (future — when dimension extractor is wired) |
| `vision` only | low | `room.polygon_source === undefined` AND only `bbox_pct` exists |

Returns `{ confidence: 'high'|'medium'|'low', primarySource: string, agreeingSources: string[] }`.

The "agreeingSources" array is the key insight: when eksplikacija and manual_polygon BOTH agree on plotas_m2 within ±2%, confidence is `high` regardless of which is primary. When they disagree, confidence drops to `low` and the badge surfaces the disagreement.

**3.2.2 ConfidenceBadge** — replaces `PolygonReviewBadge.jsx`

```
🟢 tikslus      — multiple sources agree (or single source + verified by user)
🟡 tikrinti     — single source, plausible
🔴 neaišku     — sources disagree, OR weak Vision-only
```

Tooltip: short LT explanation listing sources and values. No "bbox" or "polygon" terminology in user-visible labels.

Mounts in same locations as PolygonReviewBadge today (RoomCard, WorkspacePanel). Replaces it.

**3.2.3 ProvenanceChip** — per-number "iš kur tai?"

Small chip next to each kiekiai number in the right panel. Click → highlights the source on the PDF.

| Source label (LT) | What it points to |
|---|---|
| iš eksplikacijos | The eksplikacija table row on page 2 (or wherever) |
| iš dimensijos | The dimension annotation drawn on the floor plan |
| iš mastelio | Manual polygon × calibrated scale |
| iš AI | Vision-derived (the lowest-trust source) |
| manualu | User-overridden value |

The "highlight on PDF" is the action that justifies the chip. Without it, it's just decoration. So this chip drives a "show source" interaction:
- For eksplikacija sources → jump PDF to page 2, draw a halo around the row
- For dimension sources → jump PDF to the page, draw an arrow pointing at the dimension number
- For manual sources → no PDF highlight needed, just a "you set this 2026-04-29" tooltip

**3.2.4 Kill bbox highlight on room click**

Remove `AiRoomOverlay.jsx`'s rendering of `bbox_pct` rectangles entirely. When user clicks a room: jump to the page (existing behavior), no flashing rectangle.

The eksplikacija numbers printed on the drawing (visible in the screenshot — "01, 02, 03..." next to each room) handle the visual "where" question for free. The wrong-flash bbox was net-negative UX.

Keep `polygon_pdf` rendering on `AiRoomOverlay` for rooms that DO have a manual polygon — those are accurate and worth showing.

**3.2.5 Confirmation action — "✓ patvirtinta"**

For 🟡 rooms (single source, no disagreement), one-click confirmation: user reads the value, clicks ✓, badge flips to 🟢. Stored as `room.user_verified_at`. Lets users chip away at the verification queue without forcing a polygon trace.

### 3.3 What does NOT ship in C-2

- No backend changes (no new endpoints, no new dep)
- No removal of Phase C-1 manual polygon trace — it stays as the power-user fallback
- No automated dimension extraction (future phase — for now, dimension source is a placeholder)
- No visual polish on the badge/chip styling beyond functional clarity (that's C-4)

### 3.4 Acceptance

- [ ] Every room shows a confidence badge based on AREA confidence, not polygon-existence
- [ ] No "bbox" or "polygon" word appears in any user-visible string
- [ ] Clicking a room name does NOT flash a wrong rectangle
- [ ] Provenance chips appear next to each kiekiai number
- [ ] Clicking a chip highlights the source in the PDF (eksplikacija row OR dimension)
- [ ] User can "✓ patvirtinta" any 🟡 room to flip it to 🟢
- [ ] All UI text Lithuanian
- [ ] Existing manual polygon trace still works (regression test)
- [ ] Frontend bundle stays under 350 KB main chunk
- [ ] All existing unit tests still pass

---

## 4. Phase C-3 — Click-to-fill walls (Dynamic Fill)

### 4.1 The problem to fix

Phase C-1 manual polygon trace works but takes ~30-60 seconds per room. For a 15-room project that's 7-15 minutes of pure ceremony. Estimators won't do this every project — they'll just trust the AI numbers and ship.

Bluebeam solves this with **Dynamic Fill**: user clicks inside a room, app flood-fills to the room's wall boundaries, polygon comes back. 2-3 seconds per room. We can replicate this with classical OpenCV; no ML or training data required.

### 4.2 What ships

**4.2.1 POST /api/click-to-fill** (new backend endpoint)

Request body:
```json
{
  "project_id": "uuid",
  "page_nr": 1,
  "click_x_pct": 0.42,
  "click_y_pct": 0.61,
  "edge_sensitivity": 0.7
}
```

Response:
```json
{
  "polygon_pdf": [[123.4, 567.8], [234.5, 567.8], ...],
  "page_width_pdf": 842,
  "page_height_pdf": 595,
  "confidence": "high|medium|low",
  "fill_method": "flood_fill_v1"
}
```

Pipeline (server-side, Python + OpenCV):
1. Load the cached rendered page raster (we already render at 300 DPI for the existing extraction)
2. Adaptive threshold (binarize: walls become black, room interiors white)
3. Morphological close (gap-fill at door openings — if doors are drawn open, the room flood-fills out into corridors otherwise)
4. Flood-fill from the click point on the binarized image → fills the connected component (the room interior)
5. Find external contours of the filled region
6. Simplify with Douglas-Peucker (epsilon ~ 1% of bounding diagonal)
7. Filter: reject if area < 0.5 m² or > 200 m² (sanity); reject if perimeter / sqrt(area) > 8 (too jagged — likely flood-filled to outside)
8. Convert canvas-px coordinates back to PDF-point space
9. Return polygon

Cache key: `(project_id, page_nr, edge_sensitivity, click_grid_cell)` — clicks within ~10 px of each other return the same polygon. Cache hit = <50ms response.

**4.2.2 opencv-python** — new backend dep

- Apache 2.0 license (already pre-approved by user during synthesis-plan brainstorm)
- ~70 MB Docker image hit
- Version: pin `opencv-python-headless` (no GUI bindings) to keep size minimum

**4.2.3 Frontend wiring**

- New tool in `LeftToolRail`: "Užpildyti" (Fill) — distinct from "Polygon (zona)" (which becomes the manual fallback)
- User picks Užpildyti → cursor becomes crosshair → user clicks inside a room
- Frontend POSTs to `/api/click-to-fill` with the click coords + page
- On success: polygon appears as if traced, immediately enters PolygonEditor for fine-tuning if needed
- On failure (toast): "Nepavyko užpildyti — apveskite rankiniu būdu"
- Sensitivity slider in advanced settings (default 0.7) — user can dial up if doors leak the fill

**4.2.4 Smart-detect: pre-fill all rooms in one click**

After click-to-fill works per-room, add a "Užpildyti visus" button. Server iterates over the eksplikacija-derived room positions (we KNOW the room labels are at known positions on the drawing — they're `01`, `02`, etc.), runs flood-fill from each, returns N polygons in one round-trip. ~10-15 seconds for a 15-room project. This is the **killer feature** — turns a 15-minute ceremony into a single button.

### 4.3 What does NOT ship in C-3

- No ML model. No training data. No Mask R-CNN. (Skipping the harder Phase C synthesis plan paths.)
- No symbol counting (Repeating Groups) — that's a separate future feature
- No browser-side OpenCV. All processing server-side.
- Mobile editing still view-only (no change from Phase C-1)

### 4.4 Acceptance

- [ ] User clicks Užpildyti tool, clicks inside a room, gets a polygon back in <5 sec on a 15-page project
- [ ] Polygon area matches eksplikacija value within ±10% (verifies fill quality)
- [ ] Flood-fill rejects implausible results (toast + manual fallback)
- [ ] "Užpildyti visus" button fills all detected rooms in <30 sec for typical apartment plan
- [ ] Backend pytest stays green (no regression to existing 170+ tests)
- [ ] Frontend tests still pass
- [ ] Manual smoke on 3 sample LT plans (Visi techniniai 01.28, projektas_1, projektas_3): ≥70% of rooms get usable polygons

### 4.5 Risk + fallback

- **Flood-fill quality on hand-annotated drawings is the main risk.** Drawings with hand-drawn dimensions intersecting walls can break the binarization. Bluebeam handles this with their Edge Sensitivity slider.
- **Doors-open-into-corridors** — the morphological close handles most cases but not all. Fall back to manual if flood-fill returns a polygon spanning multiple rooms.
- **Hard cap: 6 weeks of work.** If by week 4 the click-to-fill quality is below 60% on standard apartment plans, ship what we have behind a feature flag and revisit. Manual polygon trace stays as the user's reliable path.

---

## 5. Phase C-4 — Visual polish pass

### 5.1 Scope

Pure UI/UX polish. Don't redesign the workflow — improve how it looks and feels.

**5.1.1 PDF viewer chrome**
- Cleaner toolbar (consolidate buttons, less crowded; current state has both top + left rails competing)
- Better page thumbnails (current renders look like dev placeholders)
- Smoother zoom transitions (current snaps abruptly)
- Modern type stack, better whitespace

**5.1.2 Right panel hierarchy**
- Better visual hierarchy for room rows (the table-of-rooms looks like a spreadsheet today)
- Cleaner badge integration (after C-2 lands)
- Per-row accent for selected/hovered state

**5.1.3 Color and motion**
- Tighter color palette (currently using Tailwind defaults somewhat ad-hoc)
- Motion: subtle, fast, intentional. Currently there's some accidental jankiness on tab switches and zoom

### 5.2 How to do this

- Run `/superpowers:frontend-design` against the running app
- Take baseline screenshots, redesign, iterate
- This is paint, not architecture — separate workstream from C-2/C-3
- User signs off on each iteration (visual taste isn't testable headlessly)

### 5.3 Acceptance

- [ ] Side-by-side screenshots before/after show visible improvement
- [ ] User signs off on the visual direction
- [ ] No functional regressions (Playwright smoke clean)
- [ ] Bundle size unchanged or smaller

---

## 6. Sequencing + handoff

1. **C-2 first.** I write the implementation plan, dispatch subagents per task, run Playwright smoke at end of C-2. C-2 mostly testable headlessly — DOM presence of badges, click handlers, source-highlight interactions. I can autonomously verify most of it.

2. **User smoke gate after C-2.** Confidence badges, provenance chips, removed bbox flash — these need a quick "looks right to me" from the user. ~5-min review on the running project.

3. **C-3 plan + execute.** Larger surface area (new backend dep, new endpoint, new tool). I can run the headless flood-fill against test PDFs but the final "feels right" check needs user.

4. **User smoke gate after C-3.** Click on 5-10 rooms, check polygon quality. This is unavoidable — flood-fill quality is subjective and project-dependent.

5. **C-4 plan + execute.** Visual polish. Cannot be tested headlessly — needs user eye on every iteration.

6. **Final acceptance.** All three together: full project flow from upload → review badges → click-to-fill → kiekiai → export.

---

## 7. What this displaces from prior plans

- The Phase C synthesis plan's **Phase C-2 grid-Vision spike** is dropped. We're going direct to flood-fill (the synthesis plan's Phase C-3) without the spike, because:
  1. The user explicitly asked for Togal-style features. Flood-fill is the Togal-style feature; grid-Vision is just Vision-bbox-with-better-prompt.
  2. Grid-Vision's upside ceiling is "bbox slightly less wrong"; flood-fill's upside ceiling is "manual tracing eliminated as default." Different magnitudes.
  3. We've already removed the wrong-flash bbox UX, so improving bbox accuracy wouldn't help anything visible to the user.

- The Phase C synthesis plan's **mobile editing deferral** stays. Mobile remains view-only.

- Phase C-1 manual polygon trace stays — it's the fallback for when click-to-fill fails or the user wants pixel precision.

---

## 8. Open questions deferred

- **Auto-symbol-counting** (outlets, switches, doors) — Togal's Repeating Groups. Future phase. OpenCV cv2.matchTemplate is the recipe. Add when we have user demand.
- **Auto-detect-rooms via ML** — out of reach until labeled corpus exists. Phase D+.
- **Apryse SDK reconsideration** — re-evaluate at €60k ARR per Phase C synthesis plan §4.

---

## 9. References

- Brainstorm session 2026-05-02 (this conversation)
- `docs/superpowers/plans/2026-04-29-phase-c-pdf-rewrite-research.md` — synthesis plan
- `docs/superpowers/plans/2026-04-29-phase-c-1-polygon-editor.md` — Phase C-1 (just shipped)
- `docs/superpowers/research/2026-04-29-phase-c-competitor-tech.md` — Bluebeam Dynamic Fill recipe
- `docs/superpowers/research/2026-04-29-phase-c-opencv-feasibility.md` — solo-dev OpenCV viability
- CLAUDE.md §7 (confidence levels) — the framework C-2's badge system extends

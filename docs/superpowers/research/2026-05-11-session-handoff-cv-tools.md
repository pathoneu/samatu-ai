# Session handoff — CV tools status as of 2026-05-11

**Why this doc exists:** the next "samatu-ai claude" session will pick up CV-tools strategy with a council. This file is the cold-start brief — read it first instead of skimming the whole branch.

**Branch state:** `week1-canonical-execution`, ahead of `main` by ~13 commits, NOT yet merged.

**Live UX (after revert):** `Užpildyti polygoną` (V1 click-to-fill) is the only room-suggestion tool exposed in the experimental Ženklai (β) panel. CV V2 tools are unwired.

---

## 30-second summary

We shipped the full `2026-05-10-drawing-analysis-tools.md` plan (11/11 tasks, 30/30 tests). On 2026-05-11 the user tested it on a real interior PDF and concluded the approach has architectural limits we can't iterate past:

1. **Drag interactions on pdf.js are structurally janky** (pdf.js owns canvas events; our overlay competes; Togal/Kreo built custom WebGL viewers exactly for this reason).
2. **cv2.matchTemplate recall ~40%** on small symbols in real-world testing — matches the bake-off ceiling, no threshold tuning will move it.

User's call: revert the new UI, keep all the infra on disk, hand off to a future session for council to decide the strategic pivot.

---

## What's on disk RIGHT NOW

### Backend (kept, tested, mounted)
- `backend/api/cv_tools.py` — 4 routes: `/upload-pdf`, `/match-template`, `/magic-wand`, `/record-decision`
- `backend/extractor/cv_render_cache.py` — pypdfium2-based page rasterizer (1h LRU)
- `backend/extractor/cv_match.py` — multi-scale × multi-rotation template matcher with NMS + 500-cap-per-variant
- `backend/extractor/cv_wand.py` — flood-fill + morph polygon suggester
- `backend/extractor/training_data.py` — append-only crop+label store
- `backend/tests/extractor/test_cv_*.py` + `backend/tests/api/test_cv_tools.py` + `backend/tests/integration/test_cv_e2e.py` — 30 tests, all passing
- `backend/main.py` includes `cv_tools_router` — endpoints reachable at runtime

### Frontend (components on disk, NOT mounted)
- `frontend/src/components/project/CountTool.jsx` — drag-rect tool
- `frontend/src/components/project/CountReviewPanel.jsx` — accept/reject queue
- `frontend/src/components/project/MagicWandTool.jsx` — click-to-suggest-polygon tool
- `frontend/src/components/project/DrawingOverlay.jsx` — count_marker + polygon canvas renderer
- `frontend/src/lib/cvToolsApi.js` — `matchTemplate`, `magicWand`, `recordDecision`, `uploadPdf` fetch wrappers
- `frontend/src/lib/spatialIndex.js` — RBush wrapper (unused after revert; safe to delete if council picks Vision-pivot)
- `frontend/src/hooks/useCanvasOverlay.js` — coord transforms (also unused after revert)
- `rbush` dep in `frontend/package.json`

### Frontend (unwired on 2026-05-11)
`PlanViewer.jsx` no longer imports/mounts any of the CV V2 components. The two toggle buttons in the experimental panel are gone. `InteriorWorkspace.jsx` no longer passes `projectId` or `onCvCountAccepted` to `PlanViewer` (the bridge to `darbu_sarasas` pozicija is removed).

### `PdfViewer.jsx` (dead code, but I wired it earlier — also unused)
`frontend/src/components/project/PdfViewer.jsx` is not mounted anywhere in the live app. Earlier in this session I wired CV V2 into it before realizing it was dead code; the wiring stays as a reference. Safe to delete in a future cleanup if it stays dead.

---

## Real-PDF test findings (2026-05-11)

| Aspect | Verdict | Evidence |
|--------|---------|----------|
| Coord transforms (screen↔PDF↔image-px) | ✓ correct | L1 markers landed on actual L1 symbols in the screenshot |
| Wand polygon visibility | ✓ after UX fix | Green dashed overlay visible on patalpa 102 |
| Wand polygon area | ⚠ "grybauja" (jagged, overshoots into adjacent rooms at default sensitivity) | User screenshot shows polygon over rooms 101+102 area |
| Drag-rect interaction | ✗ "fiziškai sunku, bugginasi" | pdf.js event conflicts |
| Small-symbol recall | ✗ 2/5 on L1 (~40%) | Matches bake-off ceiling |
| Old V1 (Rozetės/Jungikliai/Šviestuvai buttons) | ✗ markers placed outside drawing | Pre-existing; documented in CLAUDE.md |

Full findings: `docs/superpowers/research/2026-05-11-cv-tools-real-world-limits.md`

---

## What the next session should NOT do

- Do not re-wire CV V2 into PlanViewer hoping UX polish will fix it. The user already tested.
- Do not tune cv2.matchTemplate threshold/scales hoping recall goes up. Bake-off + this test together close that question.
- Do not delete the backend or component files. They're working infra; council may revive in pivoted form.
- Do not "fix" the V1 Rozetės/Jungikliai/Šviestuvai buttons. They're broken at the model layer (49% Vision accuracy in bake-off). Fixing UX won't help.

## What the next session SHOULD do

1. **Convene council** with this doc + `2026-05-11-cv-tools-real-world-limits.md` + the bake-off (`detector_bench/results/2026-05-03-bakeoff.md`) loaded. Decide between:
   - **B.** Vision-bulk + click-to-delete UI (no drag) — claude.opus rec
   - **C.** Spike custom WebGL viewer (Togal-style)
   - **D.** License commercial CAD viewer SDK (Autodesk Forge / Bluebeam)
   - **E.** Wait for YOLO V2 (training-data writer is already collecting)
2. If B is picked: replace the existing V1 `runSymbolDetect` calls with a thin wrapper that uses CV V2 coords + click-to-delete pattern. ~1-2 weeks.
3. If C/D: scope a spike. Both are months of work; need business-side green-light first.
4. Either way: keep the training-data writer running (it's the moat for E).

## Open questions you'll need answered before deciding

1. Is licensing a commercial CAD viewer ($20–100k/year) acceptable for current business model? (User is pre-revenue.)
2. Do users actually need the drag-rect interaction, or is "click each marker individually" good enough? (rangovas pasiūlymai analysis would help.)
3. Should V1 `/v9/symbols/detect` be deprecated entirely (broken + confusing alongside CV V2), or kept as a "best-effort" fallback?

---

## What THIS session is doing instead

After the handoff, this session is pivoting to non-CV work the user explicitly named:
- backend hardening
- accuracy calculation work (the existing Vision pipeline + interior calc)
- frontend design polish
- payment wall

So if you (next session) need anything cross-functional with code that landed today, check the recent commits:
- `0e71e8a` CV API endpoints
- `70a63bf` canvas overlay foundation (now unused on the frontend)
- `bd89049` PdfViewer wiring (dead code surface)
- `b8ff036` PlanViewer wiring (REVERTED in `<this commit>`)
- `6593d58` integration tests
- `c282b77` UAT script
- `2dabeac` plain-Lithuanian UX + research findings
- `<this revert commit>` — unwire CV V2 from PlanViewer

---

## TL;DR for the council

> The plan shipped. Real testing showed the approach has two architectural blockers (pdf.js drag, cv2.matchTemplate ceiling) that no amount of polish will fix. Backend infra + training-data writer are usable as-is for a future pivot. Decide: Vision-bulk pivot, custom viewer, commercial SDK, or wait for YOLO. Recommend B + E (combined). Avoid C/D until revenue underwrites them.

# CV Tools — real-world testing reveals architectural limits

**Date:** 2026-05-11
**Tester:** Ignas (project owner, on a real interior project PDF)
**Branch:** `week1-canonical-execution`
**Plan executed:** `2026-05-10-drawing-analysis-tools.md` — fully shipped through Task 11
**Verdict:** Functional but fundamentally limited; further iteration unlikely to reach pardavimo lygį without architectural change

---

## What was tested

Two new tools landed in PlanViewer's experimental Ženklai (β) panel:
- **Skaičiuoti pažymint** — drag bbox around a symbol → `/api/cv/match-template` returns hits
- **Pažymėti patalpą** — click inside a room → `/api/cv/magic-wand` returns polygon

User exercised both on `pažintinio projekto` PDF (page 7, electrical layout).

## What works (verified on real PDF)

- **Coordinate transforms.** When the user marked an `L1` symbol, the 2 hits returned landed visually on actual `L1` markings on the drawing. Math (screen ↔ PDF pt ↔ image px @ 200 DPI) is correct.
- **Wand polygon visibility** (after the `2026-05-11` UX fix). Green dashed outline now appears clearly on the marked room (verified on patalpa 102 svetainė/virtuvė).
- **Backend cap** (`MAX_CANDIDATES_PER_VARIANT=500`) prevents NMS OOM on featureless templates.
- **Plain Lithuanian copy** in the chips: "✓ Patalpa pažymėta brėžinyje" / "Žalias punktyras rodo, kur sistema rado sienas. Ar pridėti šią patalpą į kiekius?"

## What doesn't work (confirmed in testing)

### 1. Drag interaction is structurally janky on pdf.js
- pdf.js owns canvas events (selection, scroll, zoom). Our overlay competes.
- User: *"negaliu draginti pelyte aplink simbolį, fiziškai neįmanoma pdfviewer'i pačiam … imanoma bet sunku, bugginasi"*
- This is **not a code-quality issue we can polish away**. It's an architectural mismatch: pdf.js was not built for tool-driven canvas overlays. Togal, Kreo, STACK all built custom WebGL viewers exactly for this reason.

### 2. Recall on small symbols is low (~40% on L1 test)
- Marked `L1` on page → 2 hits returned, ~5 visible on page → **40% recall**.
- Tuning levers (threshold 0.80→0.65, more scales/rotations) trade recall for precision. Bake-off `2026-05-03` already measured this ceiling: cv2.matchTemplate ~49% on legend symbols.
- User: *"tik du rado. kas yra labai negerai"*
- **No threshold tuning will move the floor materially.** The matcher is wrong tool for variable-printed CAD glyphs.

### 3. Featureless templates produce false positives "everywhere"
- If the user's bbox includes whitespace + a small symbol, the matcher returns hits on every whitespace-with-noise patch. The 500-cap saves the server but presents the user with ~100 garbage candidates.
- Was not directly tested in this session, but observed in earlier API tests (the OOM bug we fixed).

### 4. Old V1 (Vision-based "Rozetės" button) places markers outside the drawing area
- User: *"pažymėjo net ne brėžinio viduje, o kažkur random ant lapo"*
- This is `runSymbolDetect('rozete')` → `/v9/symbols/detect`, **not** the new CV V2 tools. Already documented as 49% accurate in `2026-05-03-bakeoff.md`.
- Both V1 and V2 sit in the same Ženklai (β) panel right now → user confusion compounded the frustration.

## Root cause: the viewer, not the matcher

The `2026-05-10` plan and Council R3 underweighted the viewer/interaction quality issue. Council R3 voted "click-to-count primary, OpenCV not commercial SDK." That's defensible *only if* pdf.js + canvas overlays can support the interactions. Real-world testing shows they can't, at least not without significant custom work.

cv2.matchTemplate's accuracy ceiling is a known, documented fact. Council R3 hoped iteration would close the gap; testing confirms iteration won't.

## Options forward (user's call, not ours)

| Path | Effort | Likelihood of pardavimo-grade product |
|------|--------|---------------------------------------|
| A. Continue polishing pdf.js + OpenCV | low | low — architectural mismatch |
| B. **Pivot to Vision + bulk-find + click-to-delete UI** (no drag needed; use existing pdf.js fine) | 1–2 sav. | medium (~70% accuracy ceiling) |
| C. Spike custom WebGL viewer (à la Togal) | 2–3 mėn. | medium-high if executed well |
| D. License a commercial CAD viewer SDK (Autodesk Forge, Bluebeam Viewer SDK) | 1 mėn. integration + $20–100k/year | high |
| E. Wait for YOLO V2 (need 6–12 mo. of training-data writer feeding `data/symbol_training/`) | months | high (eventual) |

## Recommendation (Claude's read, not a decision)

**Combine B + E.** Drop the drag-rect tool from "primary" status. Replace with:
- One button per common symbol class (Rozetės, Jungikliai, Šviestuvai) that runs the V1 Vision call but with the new coordinate transforms (verified correct in CV V2).
- Each returned marker is a click-to-delete circle (works fine in pdf.js — no drag).
- Missing markers are added with a single click (also no drag).

This gives the same "click-to-count" outcome with workable interactions, ships in days not months, and continues to feed the training-data writer for the eventual YOLO V2 jump.

C and D stay as Q3+ bets when the rest of the product is solid and there's revenue to underwrite the investment.

## What we keep

- All CV V2 backend infra (`/api/cv/match-template`, `/magic-wand`, `/upload-pdf`, `/record-decision`, training_data writer). Useful when YOLO is trained.
- `data/symbol_training/` accept/reject corpus — every interaction continues to seed it.
- Coordinate-transform code (verified correct against real PDF).
- Wand polygon rendering (verified visible after UX fix).

## What we mark as research, not product

- The drag-rect Skaičiuoti pažymint as the primary count UX. Demote to "advanced" or remove.
- Council R3's assumption that 85% precision is reachable through threshold tuning. Bake-off + this test together close that question.

## Open questions for the next council

1. Is B (Vision + click-to-delete) worth pursuing now, or do we go straight to C/D?
2. Is licensing a commercial CAD viewer (D) acceptable for the business model?
3. Should we delete the V1 Vision symbol detection (Rozetės/Jungikliai/Šviestuvai buttons) since it's measurably broken, or keep as fallback?

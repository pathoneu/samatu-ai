# Phase C — PDF + Overlay Library Stack Research

**Date:** 2026-04-29
**Goal:** lock the rendering + annotation stack for the takeoff workspace (Phase C). We already ship `react-pdf@9.1` + `pdfjs-dist@4.6` + `react-konva@18.2` + `konva@9.3`. The question is: do we keep this, or graduate to a paid SDK (Apryse / Nutrient) or a faster engine (mupdf-wasm + PixiJS) before scaling polygon counts past ~500.

---

## 1. Decision matrix

Legend: `OK` = production-ready free, `$$` = paid/commercial, `partial` = works with caveats, `no` = unsuitable.

| Capability | PDF.js / react-pdf | mupdf-wasm | react-pdf-viewer | Apryse WebViewer | Nutrient (PSPDFKit) |
|---|---|---|---|---|---|
| Render 100-pg arch PDF | OK (slow cold start) | OK (fastest WASM) | OK (PDF.js wrapper) | OK | OK |
| Vector text extraction (for OCR-free dim parsing) | partial | OK (best) | partial | OK | OK |
| Built-in annotation UI | no | no | partial | OK | OK |
| Measurement tools (length/area/calibration) | no | no | no | OK | OK |
| Pinch-zoom on iPad | partial (jank) | OK | partial | OK | OK |
| License | Apache 2 / free | AGPL or commercial | Commercial only | Commercial | Commercial |
| Indicative annual cost | $0 | $0 (AGPL) / ~$1.5k+ | ~$250-1k/dev | ~$5-15k+ | ~$5-15k+ |

| Overlay engine | Free? | 500+ polygons | Hit testing | Notes |
|---|---|---|---|---|
| **Konva** (current) | MIT | OK with tuning | built-in (hitGraph) | best DX for React; 23 fps at 8k boxes |
| Fabric.js | MIT | poor | built-in | older, slower, leaks if `dispose()` skipped |
| PixiJS (WebGL) | MIT | excellent | manual | 60 fps at 8k boxes; harder hit-testing for polygons |
| paper.js | MIT | OK | built-in | great vector math (boolean ops, simplify), smaller community |
| Three.js | MIT | overkill | manual | no benefit for 2D takeoff |
| rough.js | MIT | n/a | n/a | sketchy aesthetic only — not for production overlays |
| Native SVG + React | free | poor >300 | DOM events | fine for ≤200 elements; reflow kills it past that |

---

## 2. Hidden gotchas

### PDF.js + Vite
- `workerSrc` must be set in the same module that renders `<Document>`. Setting it in `main.jsx` lets Vite's module-execution order silently overwrite your URL with the default — works in dev, breaks in prod.
- Vite content-hashes `pdf.worker.mjs`; cached browsers load `pdf.worker-OLDHASH.js` after deploy and break. Fix: copy the worker into `public/` via `vite-plugin-static-copy`, do not let Vite manage it.
- pnpm needs `.npmrc` `public-hoist-pattern[]=pdfjs-dist`.
- Memory: PDF.js does not aggressively release page render contexts. On long sessions with 100-page PDFs the worker keeps growing (Mozilla #20198, #10451). Need explicit `pdf.destroy()` + `page.cleanup()` on unmount, cap `cMapPacked` cache.
- Mobile Safari kills tabs around ~250 MB. Mitigation: render only viewport pages, destroy off-screen ones.

### Konva at scale
- `FastLayer` is deprecated since Konva 9 — use `new Konva.Layer({ listening: false })`.
- Each layer = scene canvas + hit canvas. Cap at 3 (PDF, committed polygons, active edit).
- `shape.cache()` is a footgun: 500 cached polygons = 500 off-screen buffers. Only cache shapes with filters/shadows.
- Set `perfectDrawEnabled: false`, `transformsEnabled: 'position'`, `shadowForStrokeEnabled: false` globally on overlays — measurable wins for free.
- `Konva.Tween` must be `.destroy()`-ed manually; react-konva's reconciler will not do it.
- Hit-graph: every `listening: true` shape doubles draw cost. Keep committed polygons on a non-listening layer; only the actively-edited one is interactive.
- State updates touching `<Stage>` props re-render everything. Use `useRef` + imperative `.position()` during drag, commit on `dragend` — typically 5-10× perf.

### Fabric.js (why we won't switch)
- `canvas.clear()` does not dispose objects. You must `forEachObject(o => o.dispose())` then `dispose()`. Most tutorials skip this and leak.
- Pattern fills hold refs to source canvases.

### mupdf-wasm — the trap
- AGPL by default. SaaS deployment forces us to publish all interacting code to every user — non-starter for closed-source freemium.
- Commercial license: quoted from $1.5k, real SaaS deals trend $5-15k/year.
- 2-3× faster cold render, 30-50% less memory — but only meaningful at 200+ pg PDFs (not our common case; our typical is 30-65 pg).

### react-pdf-viewer (Wojtek's project — separate from `react-pdf`)
- Commercial-only since v3, ~$250-1k/year/dev. License blocks usage where the viewer is "core value" — borderline for a takeoff app.
- Built on PDF.js so the same gotchas apply, just with a bill attached.

### Apryse / Nutrient
- Apryse WebViewer powers many AEC takeoff products. Measurement tools, calibration, XFDF persistence are turn-key.
- Opaque pricing: starter $1.5k, real SaaS deals $5-30k/year. Multi-year prepay -15-25%.
- Lock-in: their flavoured XFDF needs a translator if you migrate.

---

## 3. Cost-of-ownership (single-dev, freemium SaaS, LT market)

Assumption: ~50 paying customers Y1 at €40/mo ≈ €24k ARR. A $10k/yr SDK eats 40% of revenue.

| Path | Y1 license | Dev hours | Risk |
|---|---|---|---|
| react-pdf + Konva (current) | €0 | ~120 h for measurement + calibration + persistence | We re-invent Bluebeam UX |
| PixiJS overlay swap | €0 | ~80 h | Konva DX lost, no user-visible win <500 polygons |
| mupdf-wasm (AGPL) | €0 | ~60 h | AGPL incompatible with closed SaaS |
| mupdf-wasm commercial | €5-10k | ~40 h | Only worth it past 200 pg PDFs |
| Apryse WebViewer | €5-15k | ~20 h | Lock-in; cost > ARR for first 12 months |

**Verdict:** at current scale paid SDKs are a 12-18 month early purchase. The ~80h saved does not offset $5-10k/yr until ~150 paying seats.

---

## 4. Recommendation

**Stay with react-pdf + react-konva for Phase C.**

1. **PDF rendering — keep `react-pdf@9.1` + `pdfjs-dist@4.6`.**
   - Move `pdf.worker.mjs` to `public/` via `vite-plugin-static-copy`.
   - Configure `workerSrc` inside the PdfViewer module, not `main.jsx`.
   - Explicit `pdf.destroy()` + `page.cleanup()` on unmount; cap rendered pages to viewport ± 1; virtualise the page list.

2. **Overlay — keep `react-konva`.**
   - 3 layers: PDF backdrop, committed polygons (`listening: false`), active edit.
   - Global `perfectDrawEnabled: false`, `transformsEnabled: 'position'`, `shadowForStrokeEnabled: false`.
   - Imperative drag (refs + `.position()`), commit on `dragend`.
   - No `shape.cache()` without filters; manual `Tween.destroy()`.
   - **Revisit trigger:** real PDF with 500+ polygons and sub-30 fps drag → prototype PixiJS overlay (PDF.js stays). Do not rewrite preemptively.

3. **Measurement / calibration UI — build.** This is our differentiator vs togal.ai / Kreo for LT specifics (mūro mastelis, sienų storis prielaidos).

4. **Re-evaluate Apryse at €60k ARR or 200 seats.** At that point $5-15k/yr is rounding error and saved hours on persistence + collab justify it.

5. **Do NOT** add mupdf-wasm (AGPL incompatible; commercial costs same as Apryse without annotation UI).

6. **Do NOT** add Fabric.js, paper.js, or Three.js. Konva covers 2D; mixing engines = pure overhead.

---

## 5. Open questions

- Real customer PDF with 500+ positions? (P1 ≈ 300, below threshold.) If yes → run Konva stress test before locking.
- Any LT customer needs XFDF round-trip to Bluebeam? If yes → pulls Apryse evaluation forward.
- Reproduce the pdf.worker prod-cache bug on dashboard before Phase C kickoff (we see intermittent symptoms).

---

## Sources

- [PDF.js memory leaks #20198, #10021, #10451](https://github.com/mozilla/pdf.js/issues/20198)
- [react-pdf Vite worker setup #1377, #1148](https://github.com/wojtekmaj/react-pdf/issues/1377)
- [How I Fixed the PDF.js Nightmare in Vite (Medium, Dec 2025)](https://medium.com/@prospercoded/how-i-fixed-the-it-works-on-my-machine-pdf-js-nightmare-in-vite-54adfe92e7f2)
- [Konva All Performance Tips](https://konvajs.org/docs/performance/All_Performance_Tips.html)
- [Konva memory leak guide](https://konvajs.org/docs/performance/Avoid_Memory_Leaks.html)
- [Konva FastLayer deprecation](https://konvajs.org/api/Konva.FastLayer.html)
- [Canvas engines benchmark (slaylines)](https://benchmarks.slaylines.io/)
- [Fabric vs Konva vs PixiJS 2026 (PkgPulse)](https://www.pkgpulse.com/blog/fabricjs-vs-konva-vs-pixijs-canvas-2d-graphics-libraries-2026)
- [Artifex MuPDF licensing](https://artifex.com/licensing)
- [Apryse pricing (Vendr)](https://www.vendr.com/marketplace/apryse)
- [Nutrient (PSPDFKit) vs Apryse comparison](https://www.nutrient.io/sdk/vs/apryse/)
- [react-pdf-viewer license terms](https://react-pdf-viewer.dev/license/)
- [Bluebeam markup & measurement product page](https://www.bluebeam.com/product/markups-and-data/)

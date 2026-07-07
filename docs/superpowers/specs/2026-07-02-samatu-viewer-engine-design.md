# Sąmatų Viewer — Commercial Rendering Engine Design Spec

**Date:** 2026-07-02
**Status:** Draft for founder review
**Author:** brainstorming session (Sąmatų AI)
**Related research:** [`2026-07-02-commercial-viewer-engine.md`](../research/2026-07-02-commercial-viewer-engine.md) · engine-adapter grounding workflow (`wf_62ea18f1-a75`) · togal legend-count research (`wf_3e86b75a-eeb`)

---

## 1. Goal (one sentence)

Replace the app's `react-pdf` viewer with **our own commercial-grade takeoff viewer** — a rendering core we own behind a swappable **engine adapter**, delivering crisp, smooth, tiled deep-zoom and a professional visual language — while every existing AI overlay (room zones, confidence, measurement) re-homes onto it unchanged.

## 2. Why (the problem, validated with the founder)

- **The current viewer is the weak link, for a specific, verified reason.** `react-pdf` → `pdfjs-dist@4` renders **one flat `<canvas>` per page**, with a **16-megapixel canvas cap** (`maxCanvasPixels`, unchanged since 2015) and **no tiling**. Deep-zoom a large sheet → pdf.js blows memory or falls back to CSS rescale → **blur + jank**. Verified against [Apryse's pdf.js guide](https://apryse.com/blog/pdf-js/guide-to-pdf-js-rendering) + [pdf.js #17371](https://github.com/mozilla/pdf.js/issues/17371). This is precisely the "feels like a simple PDF viewer" complaint.
- **The fix is tiling, and it was validated interactively.** The founder confirmed the target feel via a side-by-side zoom demo: current = mush on zoom; tiled = re-renders sharp at every level. That crispness-under-zoom + smoothness is what separates a commercial takeoff tool from a plain viewer.
- **We're building our own on purpose — but not from scratch.** "Our authentic creation" = the whole viewer experience + AI takeoff overlays (100% ours). The invisible "PDF bytes → pixels" core is borrowed from a free, self-hostable engine. We do **not** write a PDF parser (multi-year tar pit) or a custom WebGL renderer (our inputs are flattened raster, so a vector renderer buys almost nothing).

## 3. Core principle

> **One boundary we own: the `TakeoffEngineAdapter`.** Our overlays already speak one dialect — *fractional/`pct` coords × a `renderedSize`*. The adapter's whole job is to hand each overlay a `renderedSize` + an inverse (screen→page), and keep it glued to the raster through deep zoom. Because of that, **all our overlay math is untouched**; we only swap *where* `renderedSize` and `scale` come from. The rendering engine becomes a swappable implementation detail, not a dependency woven through the app.

**Honest boundaries (stated up front so we don't overspend on the engine):**
- This does **not** fix the wrong-shaped room zones (`synthesized_from_bbox` rectangles) — that's a CV problem solved by flood-fill, a **separate track**.
- No engine sharpens a raster beyond its native DPI; tiling re-renders *up to* that limit instead of CSS-stretching a blurry canvas. For low-DPI scans we improve perceived quality upstream (§9), not by swapping engines.

## 4. Scope

**v1 (this spec):**
1. **Tiled crisp deep-zoom + HiDPI rendering core** — the commercial-feel essence.
2. **Smooth interaction** — inertial pan, wheel-zoom-to-cursor, no white-flash-on-zoom, fit-width/fit-page + zoom-% control.
3. **Layer toggles** — show/hide AI zones · measurements · symbols · raw plan.
4. **Re-homed overlays** — RoomZoneLayer (AI zones + confidence), measurement/calibration, symbol-count points, click-to-fill, focused-room marker — all mounted on the adapter, internals unchanged.
5. **Scan quality** — server-side HiDPI re-raster + honest low-DPI badge (§9).
6. **Professional visual language** — no emoji; line-icon set; restrained, refined chrome (§8).

**Non-goals (v1):** the legend-driven symbol counter (separate, proof-gated — §12); flood-fill zone-shape correction (separate CV track); a custom WebGL/vector renderer; multi-document; a from-scratch PDF parser; revision-compare/dim-isolate (later polish).

## 5. Architecture

**The viewer is a rendering + interaction layer over a swappable core. No new quantity math.**

```
PDF bytes ─▶ Rendering core (EmbedPDF/PDFium-WASM primary · OpenSeadragon+DZI fallback)
                     │  implements ▼
        ┌──────────────── TakeoffEngineAdapter (the boundary WE own) ────────────────┐
        │  • page coordinate system (Viewport + ViewportTransform: pct/pdf ⇄ screen)  │
        │  • zoom / pan / page nav / devicePixelRatio                                 │
        │  • onPointerInPageSpace (click → pdf+pct, for click-to-fill / symbol pick)  │
        │  • mountOverlay({pageNumber, zIndex, render: t => ReactNode})               │
        │  • getTextItems (label search)                                              │
        └───────────────────────────────┬────────────────────────────────────────────┘
     overlays consume ONLY the adapter ▼ (never import react-pdf / @embedpdf/*)
   RoomZoneLayer · MeasureLayer · SymbolOverlayLayer · FillPolygonOverlay · PlanOverlayLayer
        │  (props unchanged: renderedSize, pct→screen — sourced from ViewportTransform)
        ▼
   lib/* math UNTOUCHED: planOverlayGeometry · roomZones · measureGeometry · areaConfidence
```

### 5.1 The `TakeoffEngineAdapter` interface (one instance per open PDF)

Coordinate spaces (names are load-bearing — used verbatim in overlay props):
- **`pdf`** — PDF user-space points, origin top-left, `/Rotate` applied (matches the rendered canvas).
- **`pct`** — fractional 0..1 of the rotated page (our `polygon_pct` / `x_pct`).
- **`screen`** — device px inside the page's overlay mount element.
- `renderedWidth = pageWidthPdf × scale`, `renderedHeight = pageHeightPdf × scale` (what today's overlays call `renderedSize`).

```js
// Viewport — immutable per-page snapshot at the current zoom (pageNumber-tagged
// to preserve PlanViewer's async-drift guard).
// { pageNumber, pageWidthPdf, pageHeightPdf, scale, rotation(0|90|180|270),
//   renderedWidth, renderedHeight }

// ViewportTransform — what overlays actually hold. All coord bridges live here.
// { viewport,
//   pdfToScreen(pt), screenToPdf(pt),   // inverse: click-to-fill / symbol pick
//   pctToScreen(pt), screenToPct(pt),
//   renderedSize() -> {width,height} }  // == our legacy overlay prop, verbatim

// TakeoffEngineAdapter
//  ── lifecycle:    open(File|Blob|url) -> Promise, close(), numPages
//  ── nav/zoom/pan: getPageNumber()/setPageNumber(n), getScale()/setScale(s),
//                   scrollTo({x?,y?,center?}), getScrollContainer()
//  ── coordinates:  getViewport(pageNumber) -> Viewport|null   // null until page ready
//                   getTransform(pageNumber) -> ViewportTransform|null
//  ── pointer:      onPointerInPageSpace(pageNumber, cb:({pdf,pct,native})=>void) -> unsub
//  ── overlays:     mountOverlay({pageNumber, zIndex, interactive,
//                                 render:(t:ViewportTransform)=>ReactNode}) -> unmount
//  ── text:         getTextItems(pageNumber) -> Promise<{items:[{str,x,y,width,height}]}>
//  ── events:       on('page-loaded'|'scale-changed'|'page-changed'|'error', cb) -> unsub
//                   getDevicePixelRatio()
```

Design note — **`mountOverlay(render: t => ReactNode)`** is the one non-obvious call: overlays don't position themselves against a DOM ref; they receive a `ViewportTransform` each frame and return SVG. That is what makes the *same overlay code* run on both cores. `renderedSize()` is kept first-class so today's `renderedSize={…}` props survive the migration verbatim.

### 5.2 Primary core — EmbedPDF (PDFium-WASM, MIT)

- License: MIT core + PDFium Apache-2.0 — clean for a bootstrapped, self-hosted app (verified on GitHub). No AGPL/GPL contamination.
- Tiling: base `RenderLayer scale={1}` + `<TilingLayer tileSize:768>` — the crisp-under-zoom behavior ([tiling docs](https://www.embedpdf.com/docs/react/headless/plugins/plugin-tiling)).
- Adapter wiring (verified against docs/source): `usePdfiumEngine({wasmUrl, worker:true})` (self-host the `.wasm` via Vite); `getViewport` from the `renderPage` `PageLayout` (`{width,height,rotatedWidth,rotatedHeight,scale,rotation}`); `pdfToScreen`/`screenToPdf` wrap `transformPosition`/`restorePosition` from `@embedpdf/models`; `setScale` via `useZoom`; `scrollTo` via `useViewportCapability`; `onPointerInPageSpace` via `<PagePointerProvider>`; **`mountOverlay` = the `<Scroller renderPage>` render-prop** (our overlays are siblings of the render/tiling layers inside the page's `position:relative` div).
- **The one real risk:** EmbedPDF has **no *named* public "custom layer" API** — `renderPage` is the sanctioned mount, and it *is* how EmbedPDF's own layers mount, so the risk is "version-pin + prove it," not "unsupported." Pin `@embedpdf/*` exact versions.

### 5.3 Fallback core — OpenSeadragon + server-side DZI tiles

- If the EmbedPDF spike fails on glue-in-motion or sharpness: pivot to OSD. We generate a **DZI tile pyramid** server-side (`vips dzsave` on our existing PDF→PNG raster; tiles → R2, already wired).
- Overlay story is actually *cleaner*: the official `svg-overlay` plugin returns a `<g>` the library transforms every frame; `viewport ⇄ image` coordinate API gives us `pdfToScreen`/`screenToPdf` directly.
- Cost is the extra server tiling pipeline + tile storage — which is exactly why it's the fallback, not the default. Natural fit for our flattened-raster inputs.

## 6. Phase 0 — the engine spike (go/no-go, ~1 day)

**Do this before the port. It decides EmbedPDF vs OpenSeadragon; we don't gamble the whole migration on faith.**

**Question:** does EmbedPDF keep real `polygon_pct` room zones + one draggable measure handle pixel-glued through deep zoom/pan on a real large LT raster sheet, sharp, with a correct inverse?

**Fixture:** the contractor-validated **Beržų g. 24 PDF** (`docs/superpowers/fixtures/2026-05-26-berzu-g-24/project.pdf`) — a real flattened-raster sheet, not a synthetic ebook.

**Build (~½ day):** a scratch route wiring `EmbedPDF → Viewport → Scroller`; install `@embedpdf/{core,engines,plugin-viewport,plugin-scroll,plugin-render,plugin-zoom,plugin-interaction-manager}` (+ `plugin-tiling` on standby). A `RoomZoneSpikeLayer` mounted via `renderPage` that **reuses the real `getPolygonPctPoints`** with `renderedWidth/Height` from `PageLayout`, drawing 2–3 real zones + a confidence dot + one draggable vertex; a click probe via `PagePointerProvider`.

**Pass — ALL must hold:**

| ID | Criterion |
|---|---|
| P1 glue at rest | at 1× / 4× / 8× every vertex sits **≤2 device px** from its feature |
| P2 glue in motion | during active pinch/wheel+pan, overlays track with **no perceptible lag/swim** |
| P3 sharpness | at 8× the raster is legible (lines/text not mush) — tiling actually kicks in |
| P4 inverse | a clicked point round-trips to within **≤1% of page dimension** of true `polygon_pct` |
| P5 rotation | rotate 90° — overlays + inverse still hold (LT sheets are sometimes landscape) |

**Fallback trigger (hard):** if **P2 or P3 fails and `plugin-tiling` doesn't fix it within a further ½ day** → pivot to the OSD spike (`vips dzsave` one Beržų page → DZI → OSD `svgOverlay()` → same `polygon_pct` → re-run P1–P5; P3 is free with DZI). **P1/P4/P5 failures are almost certainly our transform-wiring bugs, not core defects** — fix in place, don't pivot on those alone.

## 7. Migration map

**Untouched — the whole point of the adapter (pure math / data):**
`lib/planOverlayGeometry.js`, `lib/roomZones.js`, `lib/measureGeometry.js`, `lib/areaConfidence.js`, and the zoom/clamp/anchor helpers. They already take `{renderedWidth,renderedHeight}` / `{pageWidthPdf,pageHeightPdf}`; the adapter feeds those from `Viewport`. Backend click-to-fill contract (`polygon_pdf`, `page_width_pdf`) unchanged.

**Rewired — swap the *source* of `renderedSize`/`scale`, keep the props:**

| File | Change |
|---|---|
| `PlanViewer.jsx` | Replace `<Document>/<Page>` + pdfjs worker setup with the adapter-backed core. `scale`/`pageNumber`/`pageSize` useState → `adapter.getScale/getPageNumber/getViewport`. `renderedSize` → `transform.renderedSize()` (keep the pageNumber identity tag). Wheel-zoom + drag-pan call `adapter.setScale`/`getScrollContainer`. Overlays mount via `adapter.mountOverlay(...)` at existing z-orders **16/20/25/27/30**. |
| `RoomZoneLayer.jsx`, `SymbolOverlayLayer`, `FillPolygonOverlay`, `PlanOverlayLayer` | Prop-compatible; only their *mount site* moves into `mountOverlay`. Preserve dismissible focused-room logic (`focusedRoomKey !== dismissedRoomKey`, Esc). |
| click-to-fill / symbol-pick | Manual `(clientX-rect.left)/rect.width` → pct deleted; use `adapter.onPointerInPageSpace`. |
| text-label search | Replace `pdfDoc.getPage().getTextContent()` + `pdfjs.Util.transform` with `adapter.getTextItems(pageNumber)`; `getTextLabelRect` multiplies by scale. **[verify PDFium text geometry parity in spike stretch goals]** |
| page-rail thumbnails | Replace `<Page width={104}>` with a low-res adapter render. **[verify PDFium renders tiny]** |
| `main.jsx` | Add `usePdfiumEngine` provider + self-hosted `wasmUrl`; drop `pdf.worker.mjs` asset + version check. |

## 8. Professional visual language (hard rule)

- **No emoji anywhere** in the viewer UI. A takeoff tool estimators show clients must look like paid software.
- Line-icon set (lucide, already in the app) for all tools/toggles; consistent stroke weight.
- Restrained palette (app tokens: `#f6f5f2` paper, `#2a6fb5` accent, refined greys); confidence colors reserved for 🟢🟡🔴 semantics only.
- Overlay markers are thin, precise, color-coded by meaning — never thick dashed "toy" boxes. Room labels are clean chips; confidence is a small dot.
- Refined type scale + spacing; subtle shadows; a status bar (page, scale 1:x, zoom %).

## 9. Scan quality (raster reality)

- **Server-side HiDPI re-raster:** render PDF pages to tiles/images at 300–400 DPI, capped at the source's native raster DPI (never upsample a 200-DPI scan to 600).
- **Honest low-DPI badge:** when native DPI is low, show a per-page banner "Žemos kokybės skenas — matavimai gali būti netikslūs" (consistent with CLAUDE.md "honest disclosure").
- Optional cheap enhancement pass on ingest (deskew → contrast normalize → gentle despeckle → adaptive unsharp). Deferred within v1 if time-boxed.

## 10. Error handling & edge cases

- **PDF fails to load / missing:** the existing "Brėžinys nepasiekiamas" state; never a blank canvas.
- **Page not yet ready:** `getViewport` returns `null`; overlays render nothing until ready (no stale-dimension draw — preserves the page-identity guard).
- **`/Rotate` 90/270 pages:** adapter reports rotated dims; overlays + inverse must hold (P5).
- **WASM load failure (EmbedPDF):** surface a clear error + fall back to a static message; log for diagnosis. (Escape hatch: OSD path has no WASM.)
- **Huge sheet / many pages:** tiling handles zoom; page virtualization for 100+ pages (salvageable from `backup/measurement-viewer`).
- **Uncalibrated scale:** measurements/areas flagged until scale confirmed (existing behavior).

## 11. Testing strategy

- **Spike gates the engine choice** (P1–P5 on the real Beржų sheet).
- **Coordinate parity unit-checkable** where pure (the `ViewportTransform` math can have node tests; pct→screen round-trips).
- **Real-app verification (mandatory)** — every phase verified in the actual `InteriorWorkspace` route with a real logged-in project, driving the live DOM, exactly as Phase 1 was verified (bring up the stack, open a real project, assert overlays land pixel-accurate, zoom/pan/rotate hold). Not a standalone harness.
- **No regressions:** existing lib unit suite (`npm run test:units`) stays green; overlays behave identically post-migration (same zones/measurements on the Beржų fixture).

## 12. Phasing (each independently shippable + verified)

1. **Phase 0 — Engine spike** (§6). Go/no-go → EmbedPDF or OSD.
2. **Phase 1 — Adapter + core swap.** Implement `TakeoffEngineAdapter` on the chosen core; replace `PlanViewer`'s render core; tiling + HiDPI + smooth pan/zoom-to-cursor + no-flash. Real-app verified.
3. **Phase 2 — Re-home overlays.** RoomZoneLayer, measurement/calibration, symbol points, click-to-fill, focused-room marker onto `mountOverlay`; layer toggles; professional-aesthetic pass. Real-app verified against Phase-1 overlay behavior.
4. **Phase 3 — Scan quality.** HiDPI re-raster + low-DPI badge (+ optional enhancement).

**Separate, proof-gated tracks (NOT part of this spec):**
- **Legend-driven symbol counter** — a genuine differentiator (research shows no major reads the legend), but the single hardest, least-proven part of the project, and it failed badly once ("all over wrong"). It gets **no full spec until a measured detector spike passes on a real electrical sheet**: box one symbol → scale-aware + NMS-deduped + embedding-similarity match (robust to raster noise) → on-canvas keep/ignore review → write one editable `vnt.` row. **Success bar: a human can prune/add to the correct count faster than counting by hand.** If it can't clear that bar on a real sheet, we don't ship it — no fake green. (The "markers in random places" coordinate cause is already fixed + verified in the current viewer; what remains to prove is detector quality.) It re-homes onto this viewer's overlay layer once proven; the backend matcher can be built in parallel.
- **Flood-fill zone-shape correction** — turns `synthesized_from_bbox` rectangles into real room outlines (the "wrong spaces" complaint). Existing backend (`/api/click-to-fill`, `/api/projects/{id}/detect-room-polygons`); wire as on-demand correction.

## 13. Risks (named, not hidden)

- **[U] EmbedPDF glue-in-motion + 8× raster sharpness** — the exact reason Phase 0 exists; OSD is the de-risked fallback.
- **EmbedPDF has no named custom-layer API** — mitigated by `renderPage` (how its own layers mount) + version-pin + the spike smoke test.
- **PDFium text-item geometry** may differ from pdf.js (label search) — parity check in the spike's stretch goals; label search is non-critical (has an eksplikacija fallback).
- **`pdfium.wasm` size + Vite self-host path** — measure at integration; acceptable for a self-hosted app.
- **OSD fallback owes a server tiling pipeline** — real infra, but R2 + PDF→PNG already exist.
- **Scope** — a multi-phase subsystem; each phase must ship + be verified independently.

## 14. Open questions for the founder

1. **Spike now vs. more design first?** Recommendation: run Phase 0 spike immediately — it's the highest-information, lowest-cost step and de-risks everything downstream.
2. **Enhancement pass in v1** or defer? (deskew/despeckle/unsharp on ingest — nice, not essential.)
3. **Counter first slice discipline** — electrical (densest, most defensible) confirmed as the eventual first target?
4. Anything to cut from v1 scope (§4) to ship the "commercial feel" faster?

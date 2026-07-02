# Commercial-Grade Viewer Engine — Research & Recommendation (2026-07-02)

**Question:** How do we make the takeoff viewer feel commercial-grade (Bluebeam/Togal/Kreo class) instead of "a simple PDF viewer"? Adopt a commercial SDK, upgrade our pdf.js pipeline, or build our own?

**Method:** 4 parallel web-research agents (commercial SDKs · competitor tech · open-source premium path · raster-crispness constraint) → adversarial fact-check against primary sources → synthesis tailored to our constraints. Every decision-critical claim below survived fact-check against a primary URL.

---

## The fact that reframes everything

**No rendering engine makes a flattened-raster page vector-sharp.** For our typical LT input (Ghostscript/iLovePDF re-exports, no vector XObjects), the crispness ceiling is the baked-in bitmap DPI. Verified against Apryse's own PDF.js guide (names CAD/scanned docs as exactly where zoom "cannot reach the required image depth"). A new engine is a **"feels premium / interacts smoothly" upgrade, not a "the scan got sharper" upgrade.**

**The actual defect that makes us look "simple":** react-pdf → pdfjs-dist@4 renders **one flat `<canvas>` per page**, with a **16-megapixel canvas cap** (pdf.js `maxCanvasPixels`, unchanged since 2015) and **no tiling**. Deep-zoom a large E-size sheet → pdf.js blows memory or falls back to CSS rescale → **blur + jank**. Verified ([Apryse PDF.js guide](https://apryse.com/blog/pdf-js/guide-to-pdf-js-rendering), [pdf.js #17371](https://github.com/mozilla/pdf.js/issues/17371)). **Tiling is the fix.**

## Two problems, do not conflate
1. **Wrong-shaped room ZONES** ("wrong spaces, too big/small") = DATA/CV problem (`synthesized_from_bbox` rectangles). **No engine swap fixes this** — real outlines come from flood-fill (`/api/click-to-fill`, `/api/projects/{id}/detect-room-polygons` → `auto_floodfill`, already built).
2. **Render feel** (blur/jank on zoom) = ENGINE problem. This doc is about #2.

---

## Options (fact-checked; $ figures are secondary-source estimates unless noted)

| | (A) Upgrade pdf.js | (B-embed) **EmbedPDF** PDFium-WASM + tiling | (B-osd) OpenSeadragon + server DZI tiles | (C) Commercial SDK |
|---|---|---|---|---|
| Premium feel | ~60% (Retina/mid-zoom only) | **~85%** (true tiling, base+overlay) | ~85–90% (gigapixel deep-zoom) | ~100% (Apryse/Nutrient) |
| Effort | days | ~1–2 wk + overlay spike | ~2–3 wk + server tiling pipeline | low integ., high procurement |
| $ / license | **$0** | **$0 — MIT** (PDFium Apache-2.0) ✔ | **$0** (libvips LGPL + OSD BSD) | quote-only; Apryse ~$3–5k/seat est, Nutrient ~$25–40k+/yr est; **none vendor-published** |
| Self-host / privacy | ✅ | ✅ in-browser WASM, zero egress | ✅ static tiles in our R2 | ✅ all client-side WASM |
| Keeps our AI overlays? | ✅ | 🟡 **spike required** (no documented "arbitrary SVG in page coords" API) | ✅ **best** (official `svg-overlay` + viewport↔image API) | ✅ (Apryse strongest) |
| Risk | low, misses goal | overlay-API unknown | more infra | cost + sales gate; **MuPDF-WASM = AGPL SaaS trap, avoid** |

Disqualified: **PDF.js Express** ($595/mo) — same engine we already have. **MuPDF-WASM** — AGPL; a closed SaaS needs the paid commercial license ([Artifex](https://artifex.com/licensing)).

Competitor tech (verified where possible): **Autodesk Takeoff** uses pdf.js only as a *decoder*, then renders in its own WebGL 2D engine ([APS blog](https://aps.autodesk.com/blog/fast-pdf-viewingmarkup-inside-aps-viewer)). **Kreo** renders vector for accuracy (vendor page; underlying SDK unconfirmed). Togal/STACK/Procore/Bluebeam-Cloud engines are **not publicly confirmed** — do not assume "Togal = Apryse."

---

## Recommendation

**Primary: adopt EmbedPDF (PDFium-WASM, MIT, free, mature — 4.3k★, v2.14.4 Jun 2026) with its tiling plugin, gated on a 1-day overlay spike.** Runner-up: **OpenSeadragon + server-side DZI tiles** (libvips `dzsave` → R2; its overlay story is actually better, and its raster-only downside barely applies since our inputs are mostly raster). **Keep Apryse as an escape hatch** if a paying client ever demands true-CAD fidelity. Not first — every commercial dollar figure is real recurring spend at a spend-capped concierge stage.

**The gate:** EmbedPDF documents annotation layers + a plugin architecture but not a public "draw arbitrary SVG/canvas in page coordinates" API. A 1-day spike mounts our existing `polygon_pct → page-coordinate` overlay (zones, confidence, measurement) as an EmbedPDF layer and confirms it stays glued through deep zoom. **Green → EmbedPDF; red → OpenSeadragon.**

## Staged path
- **Stage 0 (days, $0, do regardless):** render at `devicePixelRatio`, raise `maxCanvasPixels` toward 32 MP, add inertial pan + wheel-zoom-to-cursor + no-white-flash-on-zoom + fit-width/page controls. Immediate visible lift. Does **not** fix deep-zoom-on-large-sheets (only tiling does).
- **Stage 1 (~1–2 wk):** EmbedPDF overlay spike → port `PlanViewer.jsx` render core to EmbedPDF + tiling; re-home overlays. (Measurement math `measureGeometry.js` + durable per-page scale are engine-agnostic and port.)
- **Stage 2:** server-side ingest enhancement (deskew → contrast → despeckle → adaptive unsharp) at 300–400 DPI (capped at native — don't upsample) + honest low-DPI badge ("Žemos kokybės skenas — apytiksliai matavimai"). If OSD fork, the `dzsave` tiling pipeline lands here.
- **Stage 3:** Apryse only if triggered by a paying client.

## Open questions before committing
1. **Budget:** hard $0/self-hosted, or is modest recurring SDK spend acceptable? (If hard $0 → EmbedPDF/OSD, decision basically made.)
2. **Input mix:** % true-vector vs flattened-raster real client PDFs? (Mostly raster → OSD very attractive; meaningful vector share → EmbedPDF/PDFium keeps crispness.)
3. **Cloud tolerance:** confirm self-host / no drawing egress required. (All recommended options satisfy this.)
4. **Spike result:** does our overlay stay page-aligned in an EmbedPDF layer?

**Sources:** [EmbedPDF repo](https://github.com/embedpdf/embed-pdf-viewer) · [tiling plugin](https://www.embedpdf.com/docs/react/headless/plugins/plugin-tiling) · [Apryse pdf.js guide](https://apryse.com/blog/pdf-js/guide-to-pdf-js-rendering) · [pdf.js #17371](https://github.com/mozilla/pdf.js/issues/17371) · [OpenSeadragon svg-overlay](http://openseadragon.github.io/svg-overlay/) · [libvips dzsave](https://www.libvips.org/API/current/method.Image.dzsave.html) · [Artifex licensing](https://artifex.com/licensing) · [PDF.js Express pricing](https://pdfjs.express/pricing). All commercial-SDK $ figures are secondary estimates — get real quotes before relying on them.

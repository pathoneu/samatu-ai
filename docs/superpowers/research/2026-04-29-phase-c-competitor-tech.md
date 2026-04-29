# Phase C — Competitor PDF Interactive Layer: Tech Reverse-Engineering

**Date:** 2026-04-29
**Goal:** Reverse-engineer how takeoff competitors implement their PDF + interactive overlay layer, to inform our Sąmatų AI rewrite (currently react-pdf + Konva, polygons unreliable from Vision).

---

## 1. Togal.AI

**Stack guess:** Cloud SaaS, browser-rendered. Likely raster-pipeline (server-side rasterization → CV model → polygon JSON → canvas overlay). Patents confirm raster-image processing, not vector-PDF parsing.

| Layer | Best evidence |
|---|---|
| PDF lib | Server-side rasterizer (page → PNG) — patent says "controller receives and processes raster images" |
| Overlay | HTML canvas with custom snapping engine ("New Snapping UI", "snapping engine" rewritten in 2025) |
| Polygon backend | Proprietary CV pipeline (closed); patent USPTO assigned to Togal.AI Inc. mentions "pixel-pattern analysis" on "user-defined segments" |
| AI use | Patents: "two-dimensional references" → "user interactive interface and quantities of items" — pixel-level segmentation, not vector parsing |

**2025 release notes (key architecture clues):**
- "fully rewritten caching and loading system" → progressive page loading (suggests they outgrew naive PDF.js render-on-demand).
- "responsive canvas performance" → confirms HTML canvas, not WebGL.
- "Repeating Groups" (master unit copy/instance/aggregate) implies a scene graph with parent-child instancing — Konva-style, but built in-house.
- "Advanced snapping" with 22.5°/45°/percentages/edges → custom geometry engine on top of canvas (not Fabric.js — Fabric has no edge-snap).
- "3D Takeoff" with "grayscale and opaque rendering" → almost certainly Three.js / WebGL on a separate layer. Lifts 2D polygons by extrusion; not BIM-import.

**Trade secret:** Proprietary auto-classify ("AIA measurement standards", "98% accuracy"), training data from Coastal Construction's archive (founder Patrick Murphy is EVP there).

---

## 2. Bluebeam Revu

**Stack guess:** Native Windows desktop, .NET/WPF UI, **Skia (C++) renderer**, in-house PDF parser. Cloud is a separate, much-thinner web app.

| Layer | Best evidence |
|---|---|
| PDF lib | In-house PDF parser; renderer = Skia (C++ 2D library, same engine that powers Chrome/Flutter). Old engine was GDI; switched to Skia for hardware-accelerated drawing. |
| Overlay | WPF (Windows Presentation Foundation) — confirmed by Bluebeam refactor docs ("transition much of Revu off WinForms and onto WPF") |
| Polygon backend | "Dynamic Fill" = flood-fill on the PDF's content layer with an "Edge Sensitivity" knob. Operates on rasterized line weights — not vector. |
| AI use | None (still zero AI in core takeoff as of 2026); manual flood-fill is their hero feature. |

**Dynamic Fill mechanics (from Bluebeam support docs):**
- "Dynamic Fill uses the line weights defined by the PDF to determine its boundaries"
- "Edge Sensitivity adjusts detection sensitivity for shape boundaries"
- User can paint Add Boundary strokes for non-enclosed regions

This is **classic 4-connected flood-fill** with adjustable edge threshold — commodity CV, not ML. The win is UX polish, not algorithm secrecy.

**Bluebeam Cloud (web)** — feature-light read/markup product; PDF SDK not disclosed but pattern matches Apryse/PDFTron WebViewer (their AEC vertical literally markets "set drawing scale, measure distance, area, perimeter with snap-to geometry"). Apryse and Bluebeam are not corporate-related.

---

## 3. STACK

**Stack guess:** React + Cloudflare + Kubernetes (LeadIQ/Tracxn confirm). Likely uses a commercial PDF SDK (Apryse or similar) — too expensive to build from scratch on $29.3M total funding ($3M Series B Aug 2025).

| Layer | Best evidence |
|---|---|
| PDF lib | Likely Apryse/PDFTron WebViewer — matches their "color-coded blueprint" + cloud-native + measurement-tool pattern |
| Overlay | React + canvas (StackShare/LeadIQ confirmed React) |
| Polygon backend | "Floor Plan AI" auto-detects doors/windows/rooms/walls; "Draw Mode suggests potential room areas" → ML segmentation server-side, polygon JSON returned to client |
| AI use | Floor Plan AI (rooms, walls, doors, windows); single-click conversion of suggestions to measurements |

**Architecture inference:** STACK's "Draw Mode that suggests rooms and lets you accept with one click" is the same UX pattern Togal pioneered. The room polygons are server-computed; client just renders + accepts/rejects.

---

## 4. Kreo

**Stack guess:** Cloud SaaS, almost certainly **U-Net + Mask R-CNN** stack server-side, React/Vue front-end. They literally name the architectures in their own engineering blog.

| Layer | Best evidence |
|---|---|
| PDF lib | Cloud upload → server rasterization (kreo.net/floor-plan-recognition-technologies) |
| Overlay | Web canvas (their docs/videos show standard browser UI; no WebGL signature) |
| Polygon backend | Named: **U-Net** ("encoder-decoder, skip connections, pixel-perfect segmentation for walls/rooms") + **Mask R-CNN** ("count and segment every individual instance" — doors/windows). "Vision Transformer (ViT) and GNN" called out as emerging additions. |
| AI use | "Auto Measure" = semantic segmentation (U-Net rooms/walls) + instance segmentation (Mask R-CNN for countables). "Caddie AI" = LLM/NLP layer for text on drawings. |

**This is the most architecturally honest competitor blog post in the entire space.** They explicitly distinguish FPR (Floor Plan Recognition) as a hybrid CV+OCR pipeline. **Direct relevance for us — they spell out the exact stack we need.**

**Auto Measure 2.0 marketing:** "neural network constantly updates and learns from your drawings." Per-tenant fine-tuning is plausible but unconfirmed.

---

## 5. eTakeoff (SnapAI) — and the older players

**Stack guess:** Native Windows; **vector-PDF parser only** (no raster path). This is the architectural opposite of Togal.

| Layer | Best evidence |
|---|---|
| PDF lib | Custom parser of vector PDF page content stream — extracts line segments, points, polylines |
| Overlay | Native Windows GDI/WPF |
| Polygon backend | No polygons. Snap-to-point / snap-to-line / snap-to-polyline against the parsed vector geometry. Patented. |
| AI use | None in SnapAI (the "AI" branding refers to their Togal partnership). |

eTakeoff explicitly: "SnapAI only works with vector PDF files." If the PDF is scanned/raster, it's useless — which is why they OEM Togal for the raster case.

**PlanSwift** — Windows desktop, drag-drop assemblies. No public PDF SDK info. Architecture is the legacy native-Windows pattern (same family as Bluebeam, eTakeoff, OST).

---

## Common Patterns Across All Five

1. **Two camps split by PDF type:**
   - **Vector camp** (eTakeoff SnapAI, Bluebeam Dynamic Fill): parse PDF content stream, snap to geometry, use flood-fill on line weights. Fast, deterministic, but breaks on scanned/image-based PDFs.
   - **Raster + ML camp** (Togal, Kreo, STACK): rasterize at high DPI, run U-Net / Mask R-CNN, return polygons. Robust to any input but server-bound and approximate.

2. **All 3 cloud players (Togal/Kreo/STACK) use server-side ML, client-side canvas overlay.** Polygons come back as JSON; the browser is a thin renderer + edit UI. Nobody runs Mask R-CNN in WASM.

3. **Snapping is a separate engine from rendering.** Togal rewrote it in 2025 explicitly. eTakeoff patented theirs. This is the differentiating UX layer once polygons exist.

4. **No one uses Fabric.js publicly.** Custom canvas code or Konva-shaped scene graphs dominate. Konva's layer-cache + dirty-region model maps cleanly to "static PDF layer + dynamic markup layer."

5. **Apryse (formerly PDFTron) is the de-facto commercial choice for AEC web takeoff.** Their AEC-vertical landing page literally markets "snap-to geometry, set scale, area/perimeter measurement." Costly ($10K+/yr) but it's the off-the-shelf alternative to building custom.

6. **Dynamic Fill / flood-fill is commodity** — not a moat. The moat is ML model quality + training data + snapping UX.

---

## Trade Secrets vs. Commodity

| Trade secret (proprietary) | Commodity (off-the-shelf) |
|---|---|
| Togal: training corpus + classifier | PDF rasterization (pdfplumber, pdf2image, PDFium) |
| Kreo: U-Net/Mask R-CNN weights, Caddie LLM tuning | Flood-fill (any CV lib, OpenCV `cv2.floodFill`) |
| eTakeoff: vector-snap algorithm (patented) | Canvas rendering (Konva / custom) |
| Bluebeam: Skia-based PDF renderer integration | PDF parsing (PDFium, MuPDF, Apryse SDK) |
| Togal: Repeating Groups instancing engine | LLM extraction (Claude / GPT) |

Everything in the right column is commoditized. The fight is in the left column.

---

## Implication for Our Rewrite

**Match the cloud-ML camp (Togal/Kreo/STACK), not the legacy desktop camp.** Concretely: keep raster-pipeline (300-DPI PNG → Vision/CV → polygons-as-JSON), but stop relying on Claude Vision for polygon coordinates — Vision LLMs are bad at pixel-precise geometry. Move polygon detection to a deterministic CV pipeline (OpenCV flood-fill on rasterized PDF, like Bluebeam Dynamic Fill, with edge-sensitivity tuning per LT drawing line-weights), and use the LLM only for **classification** (which polygon = bathroom, which = bedroom) and **text extraction** (room names, dimensions). For the front-end: keep PDF.js for the raster layer, replace Konva with a thin custom canvas layer if instancing/snapping become bottlenecks, but Konva is fine for v1 — it's what every modern web canvas app converges on. Add an Apryse WebViewer evaluation only if measurement-tool fidelity becomes a competitive issue; the $10K+/yr is justified vs. building snap engines from scratch. The single highest-leverage move is replacing Vision-derived polygons with deterministic flood-fill + a small Mask R-CNN trained on LT brėžiniai for door/window/symbol detection — that's the Kreo recipe, and Kreo published it.

---

## Sources

- [Togal.AI 2025 Features Roundup](https://www.togal.ai/blog/2025-features-roundup)
- [Togal.AI patents (Justia)](https://patents.justia.com/assignee/togal-ai-inc)
- [Togal.AI Release Notes — Jan/Mar 2025](https://help.togal.ai/release-notes-january-25-2025)
- [Togal.AI 3D Tool (YouTube)](https://www.youtube.com/watch?v=bCM_2ea46h4)
- [Bluebeam Dynamic Fill official docs](https://support.bluebeam.com/online-help/revu21/Content/RevuHelp/Menus/Tools/Measure/Dynamic-Fill--T.htm)
- [Bluebeam Dynamic Fill overview](https://support.bluebeam.com/revu/features/dynamic-fill-overview.html)
- [Bluebeam rendering modes (GDI vs Skia)](https://ideatebb.com/three-rendering-engine-options)
- [Bluebeam on web/mobile (Cloud)](https://support.bluebeam.com/bluebeam-cloud/bluebeam-cloud.html)
- [STACK Floor Plan AI](https://www.stackct.com/floor-plan-ai/)
- [STACK Floor Plan AI Draw Mode](https://www.stackct.com/blog/floor-plan-ai-draw-mode/)
- [STACK funding/tech (Tracxn)](https://tracxn.com/d/companies/stack/__UB9jkZv9m-tcW-JXoSwpNTO5LLC9d7H9XvcC401NIeA)
- [Kreo Floor Plan Recognition Technologies blog](https://www.kreo.net/news-2d-takeoff/floor-plan-recognition-technologies)
- [Kreo Auto Measure 2.0](https://www.kreo.net/news-2d-takeoff/auto-measure-2-0)
- [eTakeoff SnapAI documentation](https://etakeoff.com/Help/Snap.html)
- [eTakeoff x Togal.AI partnership](https://etakeoff.com/ai/)
- [Apryse WebViewer for AEC](https://apryse.com/industries/aec)
- [Apryse PDF SDK product page](https://apryse.com/products/webviewer)
- [Konva vs Fabric.js technical comparison](https://medium.com/@www.blog4j.com/konva-js-vs-fabric-js-in-depth-technical-comparison-and-use-case-analysis-9c247968dd0f)
- [Patrick Murphy founder interview (Beck Technology)](https://www.beck-technology.com/podcast/interview-with-togal.ai-ceo-and-founder-and-executive-vice-president-of-coastal-construction-patrick-e.-murphy)

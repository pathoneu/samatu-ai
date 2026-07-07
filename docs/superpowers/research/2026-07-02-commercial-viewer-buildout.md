# Commercial-Grade Viewer: Build vs Adopt vs Buy (2026-07-02)

**Question:** Founder: "we need a commercial grade viewer, I don't care if it's built by you or copied from somewhere." Full audit of our code + every realistic option, adversarially verified (licenses/prices checked against primary sources: GitHub API SPDX, npm registry, vendor pricing pages).

**Verdict: build on our EmbedPDF headless base — the entire commercial feature set exists as MIT React plugins at our exact installed version (2.14.4), $0, zero engine migration. The gap is chrome + features we never turned on, not the foundation.** Copy the exact UX grammar of Bluebeam/Togal/STACK/Kreo (documented below).

---

## 1. The decisive facts (all primary-source verified)

- EmbedPDF ships **29 stable plugins at 2.14.4, every one with `/react` bindings** (checked individually on npm): thumbnail, search, selection, annotation (19 default tools incl. polygon/callout/cloudy-borders), rotate, print, export, fullscreen, capture (area screenshot), history (undo/redo), commands (shortcuts + i18n labels), i18n (custom locales → LT), ui (schema toolbar/sidebar), redaction, bookmark, spread, stamp, signature, attachment, view-manager. We installed only 11 — the rendering core.
- Project health: 4.26k stars, ~360k weekly downloads (@embedpdf/pdfium), repo pushed 2026-07-02 (same day as research), sponsor-backed, MIT.
- **The prebuilt shells (@embedpdf/react-pdf-viewer / snippet) CANNOT host our AI room-zone overlay** — verified architecturally: thin wrapper over a closed Preact web component, no page-layer injection API. Custom toolbar yes (registry/schema), page overlays no. Our overlay IS the product → prebuilt shell disqualified; headless (current path) is EmbedPDF's own "100% UI freedom" recommendation.
- Licensing nuances: `plugin-form@2.14.4` published with NO license field (avoid until upstream fixes); `public/pdfium.wasm` is **Apache-2.0** (not MIT — attribution/NOTICE applies); fonts-* are OFL-1.1; snippet bundles 10 locales, **Lithuanian not among them** → we supply our own LT locale via plugin-i18n.
- Experimental `@embedpdf/plugin-ai-manager` + `plugin-layout-analysis` (v0.0.1, 2026-02) exist — ecosystem is moving toward our AI-overlay direction.

## 2. Alternatives scanned (15) — why each loses

| Option | Verdict |
|---|---|
| EmbedPDF prebuilt viewer | Polished, $0, MIT — but no page-overlay API (verified REFUTED). Would strand RoomZoneLayer + click-to-fill + future legend counter. |
| Mozilla pdf.js full viewer (Apache-2.0) | Engine swap BACKWARDS — re-imports the deep-zoom/canvas-cap problem we left react-pdf over. Fork-to-customize monolith. |
| PDFSlick (MIT) | pdf.js engine regression AND you still build your own chrome. Dominated by status quo. |
| react-pdf-viewer.dev | DEAD — repo archived 2026-03-25, domain no longer resolves, license cannot even be purchased. |
| Stirling-PDF | Not an embeddable viewer (server tools suite). |
| OpenSeadragon/Leaflet + pdf→DZI tiles | Best-in-class zoom but new server tiling pipeline, loses text layer; right answer *before* EmbedPDF tiling existed. Fallback only. |
| OSS takeoff projects (ProTakeoff, OpenConstructionERP) | Not adoptable: one has NO license file (README claims MIT), other AGPL (viral for our SaaS). Mine for UX ideas only. |
| **Apryse WebViewer** | The only genuine leapfrog: built-in calibrated measurement/takeoff suite + custom overlays supported. Quote-only; the ONLY vendor-published number is "entry packages from $1,500"; third-party buyer data suggests low-five-figures/yr realistic. Still needs our overlay re-mounted. Keep as the fallback if our measurement rebuild stalls. |
| Nutrient (PSPDFKit) | Quote-only, buyer data ~$8k–31k+/yr. Dominated by Apryse for takeoff. |
| ComPDFKit / Foxit | No public prices; no takeoff differentiator. Skip. |
| pdf.js Express | $595/mo for a stagnant (last real release 2022) wrapper around the engine we left. Worst deal on the list. |
| Adobe PDF Embed API | Genuinely free but sealed iframe — no custom overlays possible. Disqualified. |
| Syncfusion React PDF Viewer | Dark horse: FREE Community License (<$1M revenue, ≤5 devs, ≤10 employees — we qualify) + built-in calibrated measurement. But black-box shell; mounting our page-glued overlay unproven; re-license trigger at $1M/10 employees. Only worth a spike if our measurement rebuild fails. |
| Bluebeam/Togal/STACK/Kreo products | $260–$2,999/user/yr — products, not embeddable SDKs. Not a shell shortcut. |

## 3. What "commercial grade" concretely means (7-product benchmark)

**Tier-1 table stakes (absence reads "not commercial"), ranked by visibility:**
1. **Measurement palette + calibration** — even Bluebeam's *web* viewer ships 4 tools (length, area, polylength, count-with-running-total) = the credible minimum. We have ZERO (reverted) — the single loudest gap.
2. **Drawing grammar**: click vertices; **double-click/Enter** finish; **Esc** cancel; **Backspace** delete last vertex; **Shift** ortho-snap (45/90°); **S** toggle snapping; **Space-pan without dropping the in-progress shape** (the detail that makes long polygons feel pro); single-key tool switching (Kreo: 1=select 2=polyline 3=polygon 6=count 0=fit).
3. **Thumbnail page rail** (prev/next-only toolbar is below the bar).
4. Zoom/pan chrome (we mostly have), 5. **Right panel live-synced to canvas with per-item eye toggles**, 6. Snapping with visible toggle, 7. Undo/redo, 8. Text search w/ hit highlighting (raster caveat: most LT PDFs are flattened — search only works on text-layer PDFs; be honest in UI), 9. Page rotation UI, 10. **Scale always visible + editable (status bar + cursor coords)**, 11. Export incl. what's on the drawing, 12. Markup basics, 13. Shortcuts + discoverable "?" cheat-sheet.

**Verified NOT table stakes (skip):** minimap (none of the 7 ship one), tabbed multi-doc (Bluebeam desktop only), dark chrome.

**Label declutter — the 6 documented pro patterns (fixes our overlapping-chips bug):**
1. Captions optional + granular (default: **fill only, numbers live in the panel**).
2. Panel = source of truth; canvas = picture (Togal rooms are identified by fill color/pattern, NOT text chips).
3. Movable captions with auto leader lines (Bluebeam Shift+drag).
4. One on-canvas legend replaces N chips (Kreo Drawing Legend).
5. Visibility isolation: eye per classification, **Ctrl+click eye = isolate**, search = visual canvas filter (Togal).
6. Hover/selection-revealed detail rather than persistent text.

**Togal's post-AI-detection rendering (our closest benchmark):** detections land as color+pattern-coded classification polygons + Quantities Panel rows in one atomic result; click classification name = select all its polygons; correction via Merge/Cut&Subtract/Split; select-classification-then-draw starts a polygon already in that class's color. G2 complaints = load speed on high-res pages → raw perf IS part of "commercial" perception (our tiling core is ahead here).

## 4. Gap map for our TakeoffViewer (= the build roadmap)

1. **Measurement tools** (length/area/count + calibration; Bluebeam-web parity minimum) — we already own verified geometry (`measureGeometry.js`) + durable-scale calibration from the reverted subsystem; resurrect on the EmbedPDF adapter.
2. **Thumbnail rail** — `plugin-thumbnail` (`ThumbnailsPane` render-prop + `scrollToThumb`).
3. **Keyboard contract** — `plugin-commands` (`shortcuts`, i18n `labelKey`, active/visible predicates); copy snippet's default map (Ctrl+F/P/0/1, +/-, h=pan, p=pointer, F11) + the drawing grammar above; tooltips show shortcuts.
4. **RoomZoneLayer declutter** — Togal pattern: fill-only polygons, right-panel quantities w/ eye toggles + Ctrl-click isolate, chips on hover/selection only.
5. **Text search** — `plugin-search` (SearchLayer per-page highlights) + honest raster caveat.
6. **Rotation UI** — `plugin-rotate` (we already handle /Rotate internally).
7. **Status bar** — scale + cursor coordinates + snap state (cheap, high pro-feel).
8. Print/export — `plugin-print` (`usePrint`, hidden PrintFrame), `plugin-export` (`saveAsCopy`/`download`).
9. Later (differentiators): revision compare overlay, split view, hyperlinked callouts. Never: minimap/tabs.

## 5. Audit snapshot (what we have today)

New TakeoffViewer: page nav, zoom/fit/zoom-to-cursor, pan, 3-tier AI room zones (traced/marker/chip), click-to-fill ("Taisyti zoną"), auto-detect flood-fill, focus→scroll, /Rotate-270 correction. Legacy PlanViewer (safety net at ?viewer=legacy): thumbnail rail, pdfjs text-layer room search, keyboard nav, Konva PolygonEditor, experimental symbol UI. Missing from BOTH: measurement, calibration UI, annotations, print/export, fullscreen, status bar. Bundle: both engines currently ship (react-pdf/pdfjs-dist lazy-chunked ~200KB gz) — deletable after parity.

**Sources:** embedpdf.com docs + GitHub (embedpdf/embed-pdf-viewer, tag v2.14.4 source), npm registry (per-package exports/license/time), support.bluebeam.com, help.togal.ai, STACK/Kreo help centers, Apryse/Adobe/Syncfusion pricing pages, Vendr/SpendHound buyer data (flagged as estimates), GitHub API SPDX for every OSS license claim.

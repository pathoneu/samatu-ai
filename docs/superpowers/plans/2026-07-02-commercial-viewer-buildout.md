# Commercial Viewer Buildout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (one implementer per phase; controller browser-verifies between phases). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every table-stakes gap between our TakeoffViewer and commercial takeoff viewers (Bluebeam-web parity + Togal declutter), per research `docs/superpowers/research/2026-07-02-commercial-viewer-buildout.md`.

**Architecture:** All work on the existing EmbedPDF 2.14.4 headless base (viewer-rebuild branch). New capability comes from installing more `@embedpdf/plugin-*` packages (all MIT, all `/react`) + resurrecting the reverted measurement subsystem from `backup/measurement-viewer`. The AI room-zone overlay contract (page-glued SVG, pct×renderedSize) is untouched.

**Tech Stack:** React 18 + Vite, EmbedPDF `@embedpdf/*@2.14.4` (exact version — matches installed core), lucide-react icons, Tailwind, `node --test` for lib tests, Playwright MCP for browser verification (controller does this).

**Hard rules (repeat in every phase):** UI text Lithuanian. No emoji — lucide line icons only. Light palette (`#fbfaf7` chrome, `#e6e2da` borders, `#4a4640` text, `#2a6fb5` accent). Never touch `backend/`. Exact-version installs (`npm install @embedpdf/plugin-X@2.14.4`). `node --check` fails on `.jsx` — use esbuild parse: `node -e "require('esbuild').transformSync(require('fs').readFileSync('<file>','utf8'),{loader:'jsx'}); console.log('OK')"`. Commit per task.

---

## Phase 1 — Declutter: fill-only zones + quantities-panel visibility (Togal pattern)

The founder's overlap complaint, fixed at the architecture level: **canvas is a picture, panel is the source of truth.**

### Task 1.1: RoomZoneLayer — fill-only default, chip on hover/focus only

**Files:** Modify `frontend/src/components/project/RoomZoneLayer.jsx`

- [ ] Default zone render: fill-only polygon — `fillOpacity 0.16`, `strokeWidth 1.5`, NO label chip.
- [ ] New local state `hoverNr` (`onMouseEnter`/`onMouseLeave` on each `<g>`). Hovered zone: `fillOpacity 0.30`, `strokeWidth 2.5`, chip visible.
- [ ] Focused zone (existing `focusedRoomNr` prop): `fillOpacity 0.34`, `strokeWidth 3.5`, chip pinned.
- [ ] Chip (shown only when hovered or focused): dynamic width — `w = Math.max(90, 14 + 8 + label.length * 6.4)` clamped to 200, so names don't truncate at 12 chars anymore. Keep confidence dot + area line + `apytikslė vieta` suffix. Render chips AFTER all polygons (second map pass) so a chip is never under a neighbor zone.
- [ ] New prop `hiddenRoomNrs` (Set or array of String nrs). Zones whose `String(z.nr)` is in it are not rendered at all (markers included). `missingCount` chip unaffected.
- [ ] Markers (Tier 2): unchanged visual, but respect `hiddenRoomNrs` and get the same hover brightening (`strokeWidth 2→3`).
- [ ] esbuild parse + commit: `feat(viewer): fill-only zones with hover/focus chips + per-room visibility`

### Task 1.2: roomZones.test.js remains green; add visibility tests at layer level — SKIP unit tests for JSX (no component harness); instead verify via controller browser pass

- [ ] Run `node --test src/lib/roomZones.test.js` — must stay 25/25 (Task 1.1 touches only the JSX layer, not the lib). If lib changes were needed, stop and report.

### Task 1.3: WorkspacePanel — per-room eye toggles + isolate

**Files:** Modify `frontend/src/components/project/WorkspacePanel.jsx`, `frontend/src/components/project/InteriorWorkspace.jsx`

- [ ] Read WorkspacePanel fully first (856 lines). Find the Patalpos room rows.
- [ ] State lives in InteriorWorkspace: `const [hiddenRoomNrs, setHiddenRoomNrs] = useState(() => new Set())`. Pass down: `<TakeoffViewer hiddenRoomNrs=...>` (thread to RoomZoneLayer via PageOverlayHost) and `<WorkspacePanel hiddenRoomNrs onToggleRoomVisibility onIsolateRoom onShowAllRooms>`.
- [ ] Each Patalpos row: an Eye/EyeOff button (16px, right-aligned, `text-[#8a857d] hover:text-[#4a4640]`, EyeOff + row dimmed `opacity-50` when hidden). Plain click = toggle that room. **Ctrl/Cmd+click = isolate** (hide all OTHER rooms; if already isolated to this room, restore all). Tooltip: `Rodyti/slėpti zoną plane · Ctrl+spustelėjimas — rodyti tik šią`.
- [ ] Patalpos section header: when any room hidden, show a small `Rodyti visas (N paslėpta)` button that clears the set.
- [ ] Row hover → canvas: pass `onRoomRowHover(nr|null)` up to InteriorWorkspace → `hoveredRoomNr` state → TakeoffViewer → RoomZoneLayer new prop `hoveredRoomNrExternal` (OR-ed with internal hover for chip/brightening). Cheap bidirectional feel.
- [ ] PageOverlayHost + TakeoffViewer: thread `hiddenRoomNrs` + `hoveredRoomNrExternal` props through (TakeoffViewer → Scroller renderPage → PageOverlayHost → RoomZoneLayer).
- [ ] Also DELETE the dead `{false && manualRooms.length > 0 && (...)}` JSX block in InteriorWorkspace (~lines 300-320) — dead code found in review.
- [ ] esbuild parse all changed files + `node --test src/lib/*.test.js` green + commit: `feat(viewer): quantities-panel eye toggles, Ctrl-click isolate, hover sync`

### Task 1.4: BUGFIX — click-to-fill sends display-space pct to a mediabox-space backend

**Files:** Modify `frontend/src/lib/viewerEngine/pageRotation.js` (+ its test), `frontend/src/components/viewer/TakeoffViewer.jsx`

Live bug: on a `/Rotate`-rotated page (Beržų p2 = 270), `handlePagePoint` computes `clickXPct = x/pageWidth` in the ROTATED display space and posts it to `/api/click-to-fill`, whose raster is UNROTATED (pdf2image ignores /Rotate). The flood-fill seed lands rotated ~90° away from where the user clicked. Zones render correctly only because PageOverlayHost applies the forward transform — clicks need the INVERSE.

- [ ] Add to pageRotation.js: `export function inverseRotatePctPoint(x, y, rot) { return rotatePctPoint(x, y, (360 - normalizeRotation(rot)) % 360); }` — the exact inverse of `rotatePctPoint` (inverse of 90 is 270 and vice versa; 180 is self-inverse).
- [ ] Unit tests: round-trip `inverseRotatePctPoint(...rotatePctPoint(x,y,r), r) === [x,y]` for r ∈ {0,90,180,270}, plus a concrete case: display click (0.66, 0.30) on a page whose DISPLAY rotation is 90 (i.e. reported /Rotate 270 after the complement swap) must map back to mediabox (0.30, 0.34)-ish — mirror of the verified room-102 forward mapping.
- [ ] TakeoffViewer `handlePagePoint`: compute the display rotation the same way PageOverlayHost does (`reported = normalizeRotation(pages[pageIndex].rotation); rot = reported===90?270:reported===270?90:reported`) — extract that swap into a shared helper `displayRotationFor(reported)` in pageRotation.js so the two sites can never diverge — then `const [mx, my] = inverseRotatePctPoint(x/pageWidth, y/pageHeight, rot)` and send `clickXPct: mx, clickYPct: my`.
- [ ] PageOverlayHost: use the new shared `displayRotationFor` helper (replace its inline swap; comment stays).
- [ ] `node --test src/lib/viewerEngine/pageRotation.test.js` green + esbuild parse + commit: `fix(viewer): inverse-rotate click-to-fill seeds on rotated pages`

---

## Phase 2 — Shell chrome: thumbnail rail, keyboard contract, status bar

### Task 2.1: Thumbnail rail (plugin-thumbnail)

**Files:** Modify `frontend/package.json` (install), `frontend/src/lib/viewerEngine/embedEngine.js`, `frontend/src/components/viewer/TakeoffViewer.jsx`

- [ ] `npm install @embedpdf/plugin-thumbnail@2.14.4 --save-exact`
- [ ] Register in `makeViewerPlugins`: `createPluginRegistration(ThumbnailPluginPackage, { width: 120, gap: 8, labelHeight: 16 })` (import from `@embedpdf/plugin-thumbnail/react`; match the registration style of existing plugins in embedEngine.js).
- [ ] TakeoffViewer: left rail `<aside>` (w-[148px], `bg-[#fbfaf7] border-r border-[#e6e2da]`, collapsible). Use `<ThumbnailsPane>` render-prop per docs (`https://www.embedpdf.com/docs/react/headless/plugins/plugin-thumbnail`): each thumb = `<ThumbImg meta>` + page number label; current page (from `useScroll.state.currentPage`) gets `ring-2 ring-[#2a6fb5]`; click → `scrollApi.scrollToPage({ pageNumber, behavior: 'smooth' })`.
- [ ] Toolbar toggle button (lucide `PanelLeft`), title `Puslapių juosta (T)`. Rail open state → `localStorage['samatu_viewer_thumbs']` (default OPEN when pageCount > 1).
- [ ] esbuild parse + `npm run build` green + commit: `feat(viewer): thumbnail page rail`

### Task 2.2: Keyboard contract + tooltips

**Files:** Modify `frontend/src/components/viewer/TakeoffViewer.jsx`

- [ ] One `useEffect` keydown listener on `window` inside ViewerInner. GUARD: return if `e.target` is input/textarea/select/contentEditable, or if `e.metaKey/ctrlKey` (except our explicit combos), or if any modal is open.
- [ ] Map (match snippet defaults + market grammar): `+`/`=` zoomIn · `-` zoomOut · `0` FitPage · `1` FitWidth · `PageDown`/`]` next page · `PageUp`/`[` prev page · `T` toggle thumbnail rail · `Esc` — cancels fill-mode if armed, else clears focused room (call new optional prop `onClearFocus`).
- [ ] InteriorWorkspace: pass `onClearFocus={() => setLocalFocusedRoom(null)}`.
- [ ] Update every toolbar `title` to include its shortcut: `Artinti (+)`, `Tolinti (−)`, `Visas puslapis (0)`, `Pritaikyti plotį (1)`, `Ankstesnis puslapis (PgUp)`, `Kitas puslapis (PgDn)`, `Puslapių juosta (T)`.
- [ ] esbuild parse + commit: `feat(viewer): keyboard shortcuts + shortcut tooltips`

### Task 2.3: Status bar

**Files:** Modify `frontend/src/components/viewer/TakeoffViewer.jsx`

- [ ] Bottom strip below Viewport (h-6, `bg-[#fbfaf7] border-t border-[#e6e2da] text-[11px] text-[#8a857d] px-3 flex items-center gap-3`):
  - left: `psl. {cur} / {total}` · `{zoom}%`
  - middle: page size in mm — from `documentState.document.pages[currentPage-1].size` (points → mm ×25.4/72), format `841×594 mm (A1)` with nearest-A-format label when within 2mm, else no label.
  - right: when fill-mode armed show `Spustelėkite patalpos {nr} viduje` (MOVE the hint here from the toolbar chip); else `Mastelis: nekalibruotas` placeholder (Phase 3 replaces with real scale).
- [ ] esbuild parse + commit: `feat(viewer): status bar (page, zoom, sheet size, mode hint)`

---

## Phase 3 — Measurement palette + calibration (resurrect from backup/measurement-viewer)

**The single loudest commercial gap.** Bluebeam-web parity: distance, area, count + calibration.

### Task 3.1: Restore the pure libs verbatim

**Files:** Create `frontend/src/lib/{measureGeometry,measurements,measureOverlayReducer,measureExport,durableScale}.js` + their `.test.js`

- [ ] `git show backup/measurement-viewer:frontend/src/lib/<file>` → write each file + its test file to `src/lib/`. NO edits to the pure libs.
- [ ] `node --test src/lib/measureGeometry.test.js src/lib/measurements.test.js src/lib/measureOverlayReducer.test.js src/lib/measureExport.test.js src/lib/durableScale.test.js` — ALL green. If a test imports something missing (e.g. an old adapter), fix the IMPORT PATH only, never the logic; report any deeper mismatch instead of hacking.
- [ ] Commit: `feat(measure): restore verified measurement libs from backup/measurement-viewer`

### Task 3.2: MeasureOverlay port to the EmbedPDF page contract

**Files:** Create `frontend/src/lib/viewerEngine/embedPdfAdapter.js` (+ `.test.js`); Modify `frontend/src/components/viewer/PageOverlayHost.jsx`. The backup `MeasureOverlay.jsx` (505 lines) is mounted **as-is** — it is fully props-driven through an adapter and must NOT be rewritten.

**Key facts (verified against backup source):** MeasureOverlay works in **PDF-point space**; its only coordinate boundary is an `adapter` object `{ width, height, scale, toViewport(pdfPt)→screenPx, toPdf(screenPx)→pdfPt }` (see `git show backup/measurement-viewer:frontend/src/lib/reactPdfAdapter.js` — replicate this interface exactly, including the name `toViewport`). It imports `polygonGeometry.js` which ALREADY EXISTS on this branch (verified identical). Supported tools: distance / perimeter / area / count, plus snap (S), ortho (Shift), selection, and 2-point calibration. Keep PDF-point storage — `measurements.js` / `durableScale.js` / `measureExport.js` are all tested in that space and PDF points are rotation-independent (mediabox coords).

- [ ] Copy `MeasureOverlay.jsx` verbatim from backup → `frontend/src/components/viewer/MeasureLayer.jsx` (rename component; fix import paths only).
- [ ] Create `embedPdfAdapter.js`: `makeEmbedAdapter({ renderedWidth, renderedHeight, pageWidthPt, pageHeightPt, reportedRotation })` returning the same interface. Math (all rotation via Task 1.4 helpers — `displayRotationFor`, `rotatePctPoint`, `inverseRotatePctPoint`):
  - `rot = displayRotationFor(normalizeRotation(reportedRotation))`
  - `toViewport(p)`: `[fx,fy] = rotatePctPoint(p.x / pageWidthPt, p.y / pageHeightPt, rot)` → `{ x: fx*renderedWidth, y: fy*renderedHeight }`
  - `toPdf(sp)`: `[fx,fy] = inverseRotatePctPoint(sp.x / renderedWidth, sp.y / renderedHeight, rot)` → `{ x: fx*pageWidthPt, y: fy*pageHeightPt }`
  - `scale = renderedWidth / (rot === 90 || rot === 270 ? pageHeightPt : pageWidthPt)` (px per PDF point — the snap-tolerance divisor)
  - `width = renderedWidth`, `height = renderedHeight`
- [ ] Unit tests: round-trip `toPdf(toViewport(p)) ≈ p` for rot 0/90/180/270; the verified room-102 anchor (mediabox pct (0.30,0.34) on a reported-270 page lands at display pct (0.66,0.30)); scale uses the swapped axis on 90/270.
- [ ] Mount in PageOverlayHost: sibling div AFTER RoomZoneLayer (`position:absolute, inset:0`, `pointerEvents: activeTool ? 'auto' : 'none'`) hosting `<MeasureLayer adapter={...} pageNr={layout.pageNumber} tool={activeTool} measurements scale onCommit onCalibrate onSelect selectedId/>`. Page size in points comes from `documentState.document.pages[i].size` — thread via TakeoffViewer renderPage the same way pageRotation already is. While a measure tool is active, suppress RoomZoneLayer pointer events (zones must not swallow measure clicks).
- [ ] Drawing grammar (market-verified): click adds vertex · **double-click or Enter finishes** · **Esc cancels** draft · **Backspace removes last vertex** · **Shift constrains to 0/45/90°** · min 2 pts distance, 3 pts area. Live segment preview follows cursor. Numbers formatted `formatNumberLT`.
- [ ] Rendering: distance = polyline + length label at midpoint; area = polygon (`fillOpacity 0.12`, #2a6fb5 family) + area label at centroid; count = numbered dot markers. Labels: white chip, 11px, only while tool active OR measurement selected/hovered (declutter rule applies here too).
- [ ] If no scale calibrated for the page: draw in px but label `nekalibruota — spauskite Mastelis` in amber; never invent meters.
- [ ] esbuild parse + commit: `feat(measure): MeasureLayer on EmbedPDF page contract`

### Task 3.3: Tool palette + calibration dialog + persistence

**Files:** Modify `frontend/src/components/viewer/TakeoffViewer.jsx`; Create `frontend/src/components/viewer/CalibrateDialog.jsx` (port of backup `ScaleCalibrationDialog.jsx`, reuse existing `ScaleCalibrationModal.jsx` if API-compatible — read both first)

- [ ] Toolbar gains a measure group (left of the fill button): lucide icons `Ruler` (distance, key `2`), `Pentagon` (area, key `3`), `Hash` (count, key `6`), `Scaling` (calibrate). Active tool = pressed style (`bg-[#eef4fb] text-[#2a6fb5]`). Same button re-click or Esc = deactivate. Keys added to the Task 2.2 keymap (guard: only when no fill-mode).
- [ ] Calibrate flow: activate → user draws a 2-point line on the plan → dialog: known length input (m, comma decimal ok) + `Taikyti šiam puslapiui` / `Taikyti visiems puslapiams` → `takeoffStore.setPageScale` / `applyScaleToAll` (+ `durableScale` bridge exactly as backup wired it — read `git show backup/measurement-viewer:frontend/src/lib/durableScale.js` usage).
- [ ] Persistence: measurements list per project via the backup's P-persist pattern — read how backup persisted (`git log backup/measurement-viewer --oneline -- frontend/src/lib/measurements.js` + the store file) and reuse: save to project JSON via `updateProject` (localStorage path already used by takeoffStore) — measurements survive reload.
- [ ] Status bar (Task 2.3): replace `Mastelis: nekalibruotas` with real value when set: `Mastelis: 1:{ratio} ({pixelsPerMeter.toFixed(0)} px/m)` or `M 1:50`-style if ratio known.
- [ ] A measurements list section in WorkspacePanel is OUT OF SCOPE this phase (panel rework is its own later step) — measurements visible on canvas only, but each finished measurement shows a small delete `×` on hover/selection.
- [ ] esbuild parse + `node --test src/lib/*.test.js` all green + `npm run build` green + commit: `feat(measure): tool palette, calibration, persistence`

---

## Phase 4 — Search, print/export, attribution, bug sweep

### Task 4.1: Text search (plugin-search)

**Files:** install `@embedpdf/plugin-search@2.14.4 --save-exact`; Modify `embedEngine.js`, `TakeoffViewer.jsx`, `PageOverlayHost.jsx`

- [ ] Register SearchPluginPackage. Toolbar: `Search` icon (Ctrl+F / `/` focuses) expands an inline input (right side). `useSearch` API per docs (`docs/react/headless/plugins/plugin-search`): query → result count `X / Y` + prev/next chevrons + Esc closes.
- [ ] `<SearchLayer>` (from plugin) mounted in PageOverlayHost next to RoomZoneLayer for hit highlighting.
- [ ] Raster honesty: if a non-empty query returns 0 results, show muted hint under the input: `Rezultatų nėra — šis PDF gali neturėti teksto sluoksnio`.
- [ ] Commit: `feat(viewer): text search with per-page hit highlights`

### Task 4.2: Print + export buttons

**Files:** install `@embedpdf/plugin-print@2.14.4 @embedpdf/plugin-export@2.14.4 --save-exact`; Modify `embedEngine.js`, `TakeoffViewer.jsx`

- [ ] Register both. Toolbar right group: `Printer` icon → `usePrint().print()` (+ hidden `<PrintFrame/>` mounted once per docs); `Download` icon → `useExport` capability `download()`. Titles: `Spausdinti (Ctrl+P)`, `Atsisiųsti PDF`. Wire Ctrl+P in keymap (preventDefault).
- [ ] Commit: `feat(viewer): print + download from viewer`

### Task 4.3: PDFium attribution (Apache-2.0 compliance)

**Files:** Create `frontend/public/PDFIUM-LICENSE.txt`

- [ ] File containing: PDFium Apache-2.0 notice (fetch the license text from the @embedpdf/pdfium package's LICENSE.pdfium or standard Apache-2.0 text with PDFium copyright header) + one-line provenance (`pdfium.wasm from @embedpdf/pdfium@2.14.4, Apache-2.0`).
- [ ] Commit: `chore(viewer): PDFium Apache-2.0 attribution`

### Task 4.4: Full regression gate (controller runs browser pass after this)

- [ ] `node --test src/lib/*.test.js src/lib/viewerEngine/*.test.js` — every suite green (expect ~37 prior + restored measure tests).
- [ ] `npm run build` — green.
- [ ] Report: total tests, build result, any deviation.

**NOT in scope (explicitly deferred):** plugin-rotate UI (user-rotation × overlay-rotation interplay is high-risk — separate spike with Playwright gate on the /Rotate-270 fixture), annotations/markup suite, revision compare, split view, deleting legacy PlanViewer, WorkspacePanel measurements list. Minimap/tabs/dark theme: never (verified not table stakes).

---

## Verification protocol (controller, after each phase)

Bring up stack (`SAMATU_AUTH_DISABLED=1` backend :8000 + vite :5173), open Beržų project `2e7a5a36-…` → Brėžinys, Playwright:
- P1: zones render fill-only; hover → chip + brighten; panel eye hides zone; Ctrl+click isolates; `Rodyti visas` restores; no chips at rest; no console errors.
- P2: rail thumbnails render + click navigates + current-page ring; `+`/`-`/`0`/`1`/`[`/`]`/`T`/Esc all work; status bar shows psl/zoom/mm.
- P3: draw distance + area on calibrated page → sane numbers vs known room dims (Beržų 102 ≈ 50.5 m²); Esc/Enter/Backspace/Shift grammar; scale persists reload; measurements persist reload.
- P4: search on a text PDF finds hits (Beržų has text layer — verify with a room name), 0-result hint on raster; print dialog opens; download saves; build green.

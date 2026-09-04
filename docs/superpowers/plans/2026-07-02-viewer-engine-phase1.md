# Sąmatų Viewer Engine — Phase 1 Implementation Plan (Adapter + EmbedPDF core swap)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stand up our own commercial-grade viewer on EmbedPDF/PDFium behind a `TakeoffEngineAdapter` boundary, with the AI room-zone overlay re-homed and pixel-glued, mounted behind a toggle in `InteriorWorkspace` so the current `react-pdf` viewer stays the default fallback until the new one is verified on a real project.

**Architecture:** A new `TakeoffViewer` React component wraps EmbedPDF (Viewport + Scroller + tiling). Its `renderPage` render-prop hands each page a `viewport` object (from EmbedPDF's `PageLayout`) that exposes `renderedSize` + `pct⇄screen` transforms — the exact contract our overlays already consume. Overlays render *inside* `renderPage` as siblings of the render/tiling layers. **All `lib/*` geometry math is untouched.** EmbedPDF runs in a Web Worker with a self-hosted wasm.

**Tech Stack:** React 18 (JSX), EmbedPDF `@embedpdf/*@2.14.4` (PDFium-WASM, MIT), Vite 6, `node --test` for lib. Grounded in the Phase 0 spike (`frontend/src/pages/ViewerSpike.jsx`, live-verified: 0 px overlay glue at 1/4/8×, tiling re-raster confirmed, click-inverse correct).

---

## Spike learnings this plan is built on (all verified in-browser 2026-07-02)

- **Overlay mount = `Scroller` `renderPage={(layout) => …}`.** `PageLayout` = `{ pageNumber, pageIndex, x, y, width, height, rotatedWidth, rotatedHeight, elevated }`. `width`/`height` are **already scale+rotation-applied CSS px** → an overlay point is simply `x_pct * width`. No scale/rotation math needed. **Glue measured at 0.00 px at 1×/4×/8×.**
- **Doc load:** `initialDocuments: [{ url, autoActivate: true }]`; read the id via **`useActiveDocument()`** (NOT the `EmbedPDF` render-prop) inside `DocumentContent`'s `{ isLoaded }`.
- **Zoom:** `useZoom(documentId)` → `{ state:{currentZoomLevel}, provides:{ requestZoom(n), zoomIn(), zoomOut() } }`.
- **Page-space clicks:** wrap the page in `<PagePointerProvider documentId pageIndex style>`, register `usePointerHandlers({documentId,pageIndex}).register({ onClick:(pos)=>… })` — `pos` is already page-space (inverse verified: ratio exactly 2.0).
- **wasm self-host:** the Vite `?url` dev import serves a **300-byte stub** (broken); copying `node_modules/@embedpdf/pdfium/dist/pdfium.wasm` → `public/pdfium.wasm` and passing `wasmUrl: '/pdfium.wasm'` serves the real 4.63 MB `application/wasm`.
- **THE ONE OPEN CAVEAT (Task 1):** default `worker: true` **hung** on the worker's wasm fetch; `worker: false` (main thread) works. Production needs the worker on (main-thread raster janks big sheets), so fixing worker+wasm is task 1.

---

## File Structure

**Create:**
- `frontend/src/lib/viewerEngine/pageViewport.js` — pure transforms: `makeViewport(pageLayout)` → `{ pageNumber, renderedSize(), pctToScreen(pt), screenToPct(pt) }`. The only unit-tested surface.
- `frontend/src/lib/viewerEngine/pageViewport.test.js` — node:test.
- `frontend/src/lib/viewerEngine/embedEngine.js` — the engine config: `usePdfiumEngine` options (self-host wasm, worker) + the shared `plugins` factory. One place to own the worker/wasm decision.
- `frontend/src/components/viewer/TakeoffViewer.jsx` — the EmbedPDF-based viewer: engine gate → `EmbedPDF` → `useActiveDocument`/`DocumentContent` → `Viewport`/`Scroller`; `renderPage` renders base+tiling + `PageOverlayHost`; a clean line-icon toolbar (zoom/page); routes page-space clicks up. Accepts `{ fileUrl|pdfFile, rooms, focusedRoom, onRoomZoneClick, ...same-shape-as-PlanViewer }`.
- `frontend/src/components/viewer/PageOverlayHost.jsx` — inside `renderPage`; builds the `viewport` from `PageLayout` and renders the registered overlays (Phase 1: RoomZoneLayer) with `renderedSize`.

**Modify:**
- `frontend/src/components/project/RoomZoneLayer.jsx` — **no prop change**; confirm it renders correctly when given `renderedSize` from the adapter (it already takes `renderedSize` + `rooms` + `page` + `focusedRoomNr` + `onRoomClick`). If it assumes an absolutely-positioned parent, ensure the host provides `position:relative`.
- `frontend/src/components/project/InteriorWorkspace.jsx` — add a viewer toggle (`localStorage 'samatu_viewer_engine' === 'embed'` or a dev query `?viewer=embed`) that renders `TakeoffViewer` instead of `PlanViewer`, passing the identical props already wired (`rooms`, `focusedRoom`/`effectiveFocusedRoom`, `onRoomZoneClick`, `fileUrl`, `pdfFile`).
- `frontend/vite.config.js` — only if Task 1 needs a worker/wasm config (e.g. `worker.format` or `optimizeDeps.exclude`); otherwise untouched.
- `frontend/public/pdfium.wasm` — committed as a real static asset (from the spike). (Add nothing to .gitignore; it must ship.)

**Reuse untouched:** `lib/planOverlayGeometry.js`, `lib/roomZones.js`, `lib/areaConfidence.js` (RoomZoneLayer's math); the current `PlanViewer.jsx` stays as the default fallback.

**Throwaway from spike (delete in Task 8):** `src/pages/ViewerSpike.jsx`, the `/viewer-spike` route in `App.jsx`, `public/spike.pdf`.

---

## Task 1: Get EmbedPDF running with a Web Worker + self-hosted wasm

**Files:** Modify: `frontend/src/pages/ViewerSpike.jsx` (the existing spike is our test rig); maybe `frontend/vite.config.js`. Create: `frontend/public/pdfium.wasm` (already staged).

- [ ] **Step 1: Reproduce the hang** — in `ViewerSpike.jsx`, set `usePdfiumEngine({ wasmUrl: '/pdfium.wasm', worker: true })`. Load `http://localhost:5173/viewer-spike`. Expected: stuck on "Kraunamas dokumentas…" (worker can't fetch the wasm).

- [ ] **Step 2: Fix attempt A — absolute wasm URL.** Change to `wasmUrl: new URL('/pdfium.wasm', window.location.origin).href` (absolute, resolvable from the worker context). Reload.
Run (verify in browser via Playwright/console): the page renders the plan + overlay (`document.querySelectorAll('img').length > 0`, `window.__spikeZoom` truthy).
Expected: renders. If it renders → worker+wasm solved; skip to Step 4.

- [ ] **Step 3: Fix attempt B — if A fails, Vite worker format.** In `vite.config.js` add `worker: { format: 'es' }` and/or `optimizeDeps: { exclude: ['@embedpdf/engines', '@embedpdf/pdfium'] }`. Reload and re-verify. If still failing, capture the worker error (`browser_console_messages` all levels + the worker's network tab) and record it; **fall back to `worker: false` for Phase 1 with a `// TODO(worker)` and a logged risk** — do NOT block the whole port on this (main-thread works; worker is a perf optimization we can land in Phase 1b).

- [ ] **Step 4: Confirm self-host (no CDN).** With the working config, assert no request goes to `cdn.jsdelivr.net` (grep `browser_network_requests` / DevTools). The wasm must load from `/pdfium.wasm` (4.63 MB, `application/wasm`).

- [ ] **Step 5: Commit**
```bash
cd frontend && git add public/pdfium.wasm vite.config.js src/pages/ViewerSpike.jsx
git commit -m "feat(viewer): EmbedPDF worker+self-hosted wasm working (spike rig)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `pageViewport.js` — the viewport transform (pure, TDD)

**Files:** Create `frontend/src/lib/viewerEngine/pageViewport.js` + `.test.js`.

- [ ] **Step 1: Write the failing test** — `frontend/src/lib/viewerEngine/pageViewport.test.js`:
```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeViewport } from './pageViewport.js';

const layout = { pageNumber: 2, pageIndex: 1, width: 1000, height: 800, rotatedWidth: 500, rotatedHeight: 400 };

test('makeViewport: renderedSize = layout width/height', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.renderedSize(), { width: 1000, height: 800 });
  assert.equal(vp.pageNumber, 2);
  assert.equal(vp.pageIndex, 1);
});

test('makeViewport: pctToScreen multiplies by rendered size', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.pctToScreen({ x: 0.25, y: 0.5 }), { x: 250, y: 400 });
});

test('makeViewport: screenToPct is the inverse', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.screenToPct({ x: 250, y: 400 }), { x: 0.25, y: 0.5 });
});

test('makeViewport: null-safe on bad layout', () => {
  assert.equal(makeViewport(null), null);
  assert.equal(makeViewport({ width: 0, height: 0 }), null);
});
```

- [ ] **Step 2: Run → fail.** `cd frontend && node --test src/lib/viewerEngine/pageViewport.test.js` → "Cannot find module".

- [ ] **Step 3: Implement** — `frontend/src/lib/viewerEngine/pageViewport.js`:
```js
/**
 * pageViewport — wraps EmbedPDF's per-page PageLayout into the coordinate
 * contract our overlays already speak: renderedSize + pct⇄screen. width/height
 * from PageLayout are ALREADY scale+rotation-applied CSS px (verified in the
 * Phase 0 spike), so pct→screen is a plain multiply — no scale/rotation math.
 */
export function makeViewport(layout) {
  if (!layout || !layout.width || !layout.height) return null;
  const width = layout.width;
  const height = layout.height;
  return {
    pageNumber: layout.pageNumber,
    pageIndex: layout.pageIndex,
    width,
    height,
    renderedSize: () => ({ width, height }),
    pctToScreen: (p) => ({ x: p.x * width, y: p.y * height }),
    screenToPct: (p) => ({ x: p.x / width, y: p.y / height }),
  };
}
```

- [ ] **Step 4: Run → pass.** `cd frontend && node --test src/lib/viewerEngine/pageViewport.test.js` → 4 pass. Then `npm run test:units` → no regressions.

- [ ] **Step 5: Commit**
```bash
cd frontend && git add src/lib/viewerEngine/pageViewport.js src/lib/viewerEngine/pageViewport.test.js
git commit -m "feat(viewer): pageViewport transform (PageLayout -> renderedSize + pct<->screen)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `embedEngine.js` — engine + plugins config (single source of truth)

**Files:** Create `frontend/src/lib/viewerEngine/embedEngine.js`.

- [ ] **Step 1: Implement** — encode the working engine config from Task 1 + the plugin set, so the viewer component stays declarative:
```js
/**
 * embedEngine — one place that owns the EmbedPDF engine config (self-hosted
 * wasm + worker decision from Task 1) and the plugin registration factory.
 */
import { createPluginRegistration } from '@embedpdf/core';
import { ViewportPluginPackage } from '@embedpdf/plugin-viewport/react';
import { ScrollPluginPackage } from '@embedpdf/plugin-scroll/react';
import { DocumentManagerPluginPackage } from '@embedpdf/plugin-document-manager/react';
import { RenderPluginPackage } from '@embedpdf/plugin-render/react';
import { ZoomPluginPackage, ZoomMode } from '@embedpdf/plugin-zoom/react';
import { TilingPluginPackage } from '@embedpdf/plugin-tiling/react';
import { InteractionManagerPluginPackage } from '@embedpdf/plugin-interaction-manager/react';

// Self-hosted, no CDN. Absolute URL so the worker context can resolve it.
export const PDFIUM_WASM_URL = '/pdfium.wasm';
export function engineOptions() {
  return {
    wasmUrl: new URL(PDFIUM_WASM_URL, window.location.origin).href,
    worker: true, // Task 1 outcome; flip to false only if Task 1 Step 3 fell back
    fontFallback: null, // no external font fetches (self-host guarantee)
  };
}

export function makeViewerPlugins(initialUrl) {
  return [
    createPluginRegistration(DocumentManagerPluginPackage, {
      initialDocuments: [{ url: initialUrl, autoActivate: true }],
    }),
    createPluginRegistration(ViewportPluginPackage),
    createPluginRegistration(ScrollPluginPackage),
    createPluginRegistration(RenderPluginPackage),
    createPluginRegistration(ZoomPluginPackage, { defaultZoomLevel: ZoomMode.FitPage }),
    createPluginRegistration(TilingPluginPackage),
    createPluginRegistration(InteractionManagerPluginPackage),
  ];
}
```
(If Task 1 fell back to `worker:false`, set `worker: false` here with the `// TODO(worker)` note.)

- [ ] **Step 2: Sanity build.** `cd frontend && npm run build 2>&1 | tail -3` → succeeds (imports resolve).

- [ ] **Step 3: Commit**
```bash
cd frontend && git add src/lib/viewerEngine/embedEngine.js
git commit -m "feat(viewer): embedEngine config (self-host wasm + plugin factory)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `PageOverlayHost.jsx` — render overlays inside a page

**Files:** Create `frontend/src/components/viewer/PageOverlayHost.jsx`.

Renders inside `Scroller.renderPage`. Builds the `viewport` from `PageLayout` and mounts the Phase-1 overlay set (RoomZoneLayer). Mirrors the spike's page-sibling pattern (base + tiling + our SVG); `PagePointerProvider` is the page-sized relative wrapper so clicks resolve to page space.

- [ ] **Step 1: Implement**
```jsx
/**
 * PageOverlayHost — mounted once per page by TakeoffViewer's renderPage. Lays
 * out base render + hi-res tiling, then our overlays as page-glued siblings.
 * Overlays consume `renderedSize` (== our legacy prop) from the page viewport.
 */
import { useEffect } from 'react';
import { RenderLayer } from '@embedpdf/plugin-render/react';
import { TilingLayer } from '@embedpdf/plugin-tiling/react';
import { PagePointerProvider, usePointerHandlers } from '@embedpdf/plugin-interaction-manager/react';
import { makeViewport } from '@/lib/viewerEngine/pageViewport';
import RoomZoneLayer from '@/components/project/RoomZoneLayer';

function PageClicks({ documentId, pageIndex, onPagePoint }) {
  const { register } = usePointerHandlers({ documentId, pageIndex });
  useEffect(() => register({
    onClick: (pos) => onPagePoint?.({ pageIndex, x: pos.x, y: pos.y }),
  }), [register, pageIndex, onPagePoint]);
  return null;
}

export default function PageOverlayHost({ documentId, layout, rooms, focusedRoomNr, onRoomZoneClick, onPagePoint }) {
  const vp = makeViewport(layout);
  if (!vp) return null;
  const { width, height } = vp.renderedSize();
  return (
    <PagePointerProvider documentId={documentId} pageIndex={layout.pageIndex} style={{ position: 'relative', width, height }}>
      <RenderLayer documentId={documentId} pageIndex={layout.pageIndex} />
      <TilingLayer documentId={documentId} pageIndex={layout.pageIndex} />
      <PageClicks documentId={documentId} pageIndex={layout.pageIndex} onPagePoint={onPagePoint} />
      {/* Absolutely-positioned overlay host, page-sized; RoomZoneLayer draws inside */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <RoomZoneLayer
          rooms={rooms}
          page={layout.pageNumber}
          renderedSize={{ width, height }}
          focusedRoomNr={focusedRoomNr}
          onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: layout.pageNumber })}
        />
      </div>
    </PagePointerProvider>
  );
}
```

- [ ] **Step 2: Verify RoomZoneLayer parent assumption.** Read `RoomZoneLayer.jsx`: it renders an absolutely-positioned `<svg className="absolute left-0 top-0 z-[16]">`. The wrapping `<div position:absolute inset:0>` gives it the page-sized positioning context. Confirm no change needed; if RoomZoneLayer's `z-[16]`/pointer-events conflict inside the host, note it (fix in Task 5 verification).

- [ ] **Step 3: Sanity build.** `npm run build` → succeeds.

- [ ] **Step 4: Commit**
```bash
cd frontend && git add src/components/viewer/PageOverlayHost.jsx
git commit -m "feat(viewer): PageOverlayHost — per-page base+tiling+RoomZoneLayer, page-glued

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `TakeoffViewer.jsx` — the viewer component

**Files:** Create `frontend/src/components/viewer/TakeoffViewer.jsx`.

- [ ] **Step 1: Implement** — engine gate → EmbedPDF → active doc → Viewport/Scroller; renderPage → PageOverlayHost; a minimal line-icon toolbar (zoom −/%/+, page indicator). Props mirror `PlanViewer` so it's a drop-in. `fileUrl` is an object URL created by the caller (same as PlanViewer's `fileUrl`).
```jsx
/**
 * TakeoffViewer — our commercial viewer on EmbedPDF/PDFium behind the engine
 * boundary. Drop-in for PlanViewer (same-shape props). Phase 1: renders the PDF
 * with tiling + the AI room-zone overlay, page-glued. Measurement/symbol/fill
 * overlays + full toolbar aesthetics land in Phase 2.
 */
import { useMemo } from 'react';
import { EmbedPDF } from '@embedpdf/core/react';
import { usePdfiumEngine } from '@embedpdf/engines/react';
import { Viewport } from '@embedpdf/plugin-viewport/react';
import { Scroller } from '@embedpdf/plugin-scroll/react';
import { DocumentContent, useActiveDocument } from '@embedpdf/plugin-document-manager/react';
import { useZoom } from '@embedpdf/plugin-zoom/react';
import { ZoomIn, ZoomOut } from 'lucide-react';
import { engineOptions, makeViewerPlugins } from '@/lib/viewerEngine/embedEngine';
import PageOverlayHost from './PageOverlayHost';

function Toolbar({ documentId }) {
  const { state, provides } = useZoom(documentId);
  const pct = typeof state?.currentZoomLevel === 'number' ? Math.round(state.currentZoomLevel * 100) : 100;
  return (
    <div className="h-9 shrink-0 border-b border-[#e6e2da] bg-[#fbfaf7] px-3 flex items-center gap-2 text-[12px] text-[#4a4640]">
      <button className="p-1 rounded hover:bg-[#efece6]" title="Tolinti" onClick={() => provides?.zoomOut()}><ZoomOut className="w-4 h-4" /></button>
      <span className="mono tabular w-12 text-center">{pct}%</span>
      <button className="p-1 rounded hover:bg-[#efece6]" title="Artinti" onClick={() => provides?.zoomIn()}><ZoomIn className="w-4 h-4" /></button>
    </div>
  );
}

function ViewerInner({ rooms, focusedRoom, onRoomZoneClick, onPagePoint }) {
  const { activeDocumentId } = useActiveDocument();
  const focusedRoomNr = focusedRoom?.nr ?? null;
  if (!activeDocumentId) return <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>;
  return (
    <DocumentContent documentId={activeDocumentId}>
      {({ isLoaded }) => (isLoaded ? (
        <div className="flex flex-col h-full">
          <Toolbar documentId={activeDocumentId} />
          <Viewport documentId={activeDocumentId} style={{ flex: 1, background: '#e9e7e2' }}>
            <Scroller
              documentId={activeDocumentId}
              renderPage={(layout) => (
                <PageOverlayHost
                  documentId={activeDocumentId}
                  layout={layout}
                  rooms={rooms}
                  focusedRoomNr={focusedRoomNr}
                  onRoomZoneClick={onRoomZoneClick}
                  onPagePoint={onPagePoint}
                />
              )}
            />
          </Viewport>
        </div>
      ) : <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>)}
    </DocumentContent>
  );
}

export default function TakeoffViewer({ fileUrl, rooms = [], focusedRoom = null, onRoomZoneClick = null, onPagePoint = null }) {
  const { engine, isLoading, error } = usePdfiumEngine(engineOptions());
  const plugins = useMemo(() => (fileUrl ? makeViewerPlugins(fileUrl) : null), [fileUrl]);
  if (error) return <div className="p-5 text-sm text-red-600">Variklio klaida: {String(error.message || error)}</div>;
  if (isLoading || !engine || !plugins) return <div className="p-5 text-sm text-muted-foreground">Kraunamas PDF variklis…</div>;
  return (
    <div className="h-full">
      <EmbedPDF engine={engine} plugins={plugins}>
        <ViewerInner rooms={rooms} focusedRoom={focusedRoom} onRoomZoneClick={onRoomZoneClick} onPagePoint={onPagePoint} />
      </EmbedPDF>
    </div>
  );
}
```

- [ ] **Step 2: Build.** `npm run build` → succeeds.

- [ ] **Step 3: Commit**
```bash
cd frontend && git add src/components/viewer/TakeoffViewer.jsx
git commit -m "feat(viewer): TakeoffViewer — EmbedPDF core + tiling + room-zone overlay

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Toggle `TakeoffViewer` into `InteriorWorkspace` (behind a flag)

**Files:** Modify `frontend/src/components/project/InteriorWorkspace.jsx`.

- [ ] **Step 1: Add the flag + conditional render.** Where `InteriorWorkspace` renders `<PlanViewer …>` (around `:303`), gate on a flag so the current viewer stays default:
```jsx
const useEmbedViewer = (() => {
  try {
    return new URLSearchParams(window.location.search).get('viewer') === 'embed'
      || localStorage.getItem('samatu_viewer_engine') === 'embed';
  } catch { return false; }
})();
```
Then:
```jsx
{pdfUrl ? (
  useEmbedViewer ? (
    <TakeoffViewer
      fileUrl={pdfUrl}
      rooms={project?.v8_rooms || project?.patalpos || []}
      focusedRoom={effectiveFocusedRoom}
      onRoomZoneClick={(room) => {
        if (room?.puslapio_nr) setLocalFocusedPage(room.puslapio_nr);
        setLocalFocusedRoom(room);
        onJumpToPage?.(room.puslapio_nr, room);
      }}
    />
  ) : (
    <PlanViewer /* …existing props unchanged… */ />
  )
) : /* …existing pdfMissing branch… */}
```
Add `import TakeoffViewer from '@/components/viewer/TakeoffViewer';`.

- [ ] **Step 2: Build.** `npm run build` → succeeds.

- [ ] **Step 3: Commit**
```bash
cd frontend && git add src/components/project/InteriorWorkspace.jsx
git commit -m "feat(viewer): mount TakeoffViewer behind ?viewer=embed flag (PlanViewer stays default)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Real-app verification (mandatory — the gate)

**Files:** none (verification; small fixes if needed).

Verify in the REAL `InteriorWorkspace`, exactly as Phase 1 of the AI Takeoff Viewer was verified (bring up the stack, real project, drive the live DOM). The known-good local flow: register a throwaway user, open the Objektas A project (`2e7a5a36…`), inject the fixture PDF into IndexedDB (`samatu_pdfs`/`pdfs`), append `?viewer=embed` to the URL.

- [ ] **Step 1: Bring up stack + open the project with `?viewer=embed`.**
- [ ] **Step 2: Assert (Playwright evaluate):**
  - EmbedPDF renders: page `<img>`s present; no request to `cdn.jsdelivr.net`.
  - RoomZoneLayer overlays render on the plan page (`svg[...] polygon` count > 0), colored + dashed + confidence dots — same as the current viewer.
  - **Glue:** zone vertices sit at `pct × renderedSize` (≤2 px) at 1×/4×/8× (reuse the spike's measurement).
  - **Bidirectional sync:** clicking a zone fires `onRoomZoneClick` → panel row highlights; clicking a panel row focuses the zone.
  - Deep-zoom is crisp on the plan lines (tiling); pan is smooth.
- [ ] **Step 3: Screenshot** the plan page at fit + at 6× for the record.
- [ ] **Step 4: Honest report** — what passed, anything that didn't (e.g. worker fell back to main-thread), any visual gaps vs the current viewer. If a check fails, STOP and fix before proceeding.

---

## Task 8: Clean up spike scaffolding

**Files:** Delete `frontend/src/pages/ViewerSpike.jsx`, `frontend/public/spike.pdf`; remove the `/viewer-spike` route + lazy import from `App.jsx`. Keep `public/pdfium.wasm` (real asset) + EmbedPDF deps.

- [ ] **Step 1: Remove throwaway files + route.**
- [ ] **Step 2: Build + lib tests green.** `npm run build && npm run test:units`.
- [ ] **Step 3: Commit**
```bash
cd frontend && git rm src/pages/ViewerSpike.jsx public/spike.pdf && git add src/App.jsx
git commit -m "chore(viewer): remove Phase 0 spike scaffolding (keep pdfium.wasm + deps)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-review notes (checked against the spec)

- **Spec §5 adapter boundary** → `pageViewport` (transforms) + `PageOverlayHost`/`TakeoffViewer` (the React composition that IS the adapter for EmbedPDF); overlays consume only `renderedSize` + page-space clicks.
- **Spec §5.2 EmbedPDF + tiling** → `embedEngine` plugins incl. `TilingPluginPackage`; verified crisp in the spike.
- **Spec §6 worker/wasm** → Task 1 leads, self-host confirmed, worker-fallback allowed with logged risk.
- **Spec §4 v1 scope** → tiling core (Tasks 3–5), re-homed room zones (Task 4), behind a toggle (Task 6). *Deferred to the Phase 2 plan (stated):* measurement/symbol/fill/focused-marker re-home, layer toggles, smooth-inertia/no-flash polish, full professional toolbar, scan quality, and flipping `TakeoffViewer` to default + deleting `PlanViewer`.
- **Spec §8 aesthetic** → line icons only (lucide), no emoji — Toolbar uses `ZoomIn/ZoomOut`; full aesthetic pass is Phase 2.
- **Spec §11 testing** → `pageViewport` node:test; mandatory real-app verification (Task 7) mirroring the AI-Takeoff-Viewer Phase-1 method.
- **No placeholders:** every code step has complete code; the only intentionally-open item is Task 1's worker outcome, which has explicit A/B/fallback branches.
- **Name consistency:** `makeViewport`/`renderedSize`/`pctToScreen`/`onRoomZoneClick`/`onPagePoint` used identically across lib, host, viewer, and workspace.

## Non-goals for this plan (Phase 2)

Re-home measurement + symbol-count + click-to-fill + focused-room marker; layer toggles; inertial pan + zoom-to-cursor + no-white-flash; full professional toolbar (page rail, minimap); scan-quality (HiDPI re-raster + low-DPI badge); make `TakeoffViewer` the default and delete `PlanViewer`. The **legend-driven counter** and **flood-fill zone correction** remain separate proof-gated tracks.

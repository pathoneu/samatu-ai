# Sprint 1 — Tile-Based Rendering — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace the laggy `react-pdf-viewer` chrome with a new `<TakeoffCanvas>` that renders pdf.js content as a 3-level mip-pyramid (0.5× / 1.5× / 3×), uses CSS transform during pan/zoom for 60 fps interaction, settles high-res via OffscreenCanvas, and caps concurrent renders to 2. Lag pain (zoom + pan) is structurally solved.

**Architecture:** Three new front-end modules — `viewerStore.js` (zustand), `renderQueue.js` (p-limit), `tileCache.js` (LRU + ImageBitmap.close on evict) — drive a new `<TakeoffCanvas>` component. Old `<PdfViewer>` stays on the legacy route during migration; new route `/project/:id?v=2` mounts the takeoff workspace. Default switches at end of Sprint 3.

**Tech Stack:** React 18, Vite, pdfjs-dist 4.6+, p-limit, lru-cache, zustand. No commercial libraries.

**Spec:** `docs/superpowers/specs/2026-05-03-takeoff-workspace-design.md` §4.1, §6 (Sprint 1)

---

## File Structure

### Created
- `frontend/src/lib/viewerStore.js` — zustand store for viewport state (transform, zoom, currentTool, hoveredRoomId)
- `frontend/src/lib/viewerStore.test.js`
- `frontend/src/lib/renderQueue.js` — `p-limit(2)` concurrent render queue
- `frontend/src/lib/renderQueue.test.js`
- `frontend/src/lib/tileCache.js` — LRU `ImageBitmap` cache (max 30, close-on-evict)
- `frontend/src/lib/tileCache.test.js`
- `frontend/src/lib/mipPyramid.js` — pick zoom level for current scale (0.5× / 1.5× / 3×) + render PDF page at fixed scale
- `frontend/src/lib/mipPyramid.test.js`
- `frontend/src/components/canvas/TakeoffCanvas.jsx` — main canvas component
- `frontend/src/components/canvas/MemoryWatchdog.jsx` — observes `performance.memory`, triggers reset when >500 MB
- `frontend/src/pages/InteriorProjectV2.jsx` — new route mounting `<TakeoffCanvas>` + existing panels (skeleton; full chrome arrives Sprint 3)

### Modified
- `frontend/package.json` — add `p-limit`, `lru-cache`, `zustand` deps
- `frontend/src/App.jsx` (or wherever routes are declared) — add route `/project/:id?v=2` → `InteriorProjectV2`
- `docs/sprint-1-followups.md` (created at end) — track issues found during Sprint 1

---

## Task 1: Install Dependencies

**Files:**
- Modify: `frontend/package.json` (via `npm install`)

- [ ] **Step 1.1: Verify deps not yet present**

```bash
cd frontend && grep -E '"(p-limit|lru-cache|zustand)"' package.json
```
Expected: no matches (per Task 1 of Sprint 0 audit confirming none present).

- [ ] **Step 1.2: Install three deps**

```bash
cd frontend && npm install p-limit lru-cache zustand
```

- [ ] **Step 1.3: Verify lock file updated**

```bash
cd frontend && grep -E '"(p-limit|lru-cache|zustand)"' package.json
```
Expected: 3 matches in `dependencies` block.

- [ ] **Step 1.4: Frontend tests still green**

```bash
cd frontend && node --test 2>&1 | tail -3
```
Expected: 38+ tests pass.

- [ ] **Step 1.5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore(sprint-1): add p-limit, lru-cache, zustand deps"
```

---

## Task 2: viewerStore.js — Zustand Viewport State

**Files:**
- Create: `frontend/src/lib/viewerStore.js`
- Create: `frontend/src/lib/viewerStore.test.js`

- [ ] **Step 2.1: Failing test**

```javascript
// frontend/src/lib/viewerStore.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createViewerStore } from './viewerStore.js';

test('createViewerStore: defaults', () => {
  const store = createViewerStore();
  const state = store.getState();
  assert.equal(state.scale, 1);
  assert.deepEqual(state.translate, { x: 0, y: 0 });
  assert.equal(state.currentPage, 1);
  assert.equal(state.currentTool, 'pan');
  assert.equal(state.hoveredRoomId, null);
});

test('createViewerStore: setScale updates and notifies', () => {
  const store = createViewerStore();
  let calls = 0;
  store.subscribe(() => calls++);
  store.getState().setScale(2);
  assert.equal(store.getState().scale, 2);
  assert.equal(calls, 1);
});

test('createViewerStore: setTransform sets both scale and translate', () => {
  const store = createViewerStore();
  store.getState().setTransform({ scale: 1.5, translate: { x: 10, y: 20 } });
  const s = store.getState();
  assert.equal(s.scale, 1.5);
  assert.deepEqual(s.translate, { x: 10, y: 20 });
});

test('createViewerStore: setHoveredRoomId triggers single update', () => {
  const store = createViewerStore();
  let calls = 0;
  store.subscribe(() => calls++);
  store.getState().setHoveredRoomId('K1');
  store.getState().setHoveredRoomId('K1');  // same value
  assert.equal(store.getState().hoveredRoomId, 'K1');
  // zustand by default re-runs subscribers on every set; that's fine for this test
  assert.ok(calls >= 1);
});
```

- [ ] **Step 2.2: Run, verify fails**

```bash
cd frontend && node --test src/lib/viewerStore.test.js
```
Expected: FAIL — module not found.

- [ ] **Step 2.3: Implement**

```javascript
// frontend/src/lib/viewerStore.js
/**
 * Sprint 1: zustand store for viewer state.
 *
 * Holds viewport transform (scale + translate), current page, current tool,
 * and bidirectional-highlight target. The PDF render layer and Konva
 * annotation layer both subscribe to (different parts of) this store, so
 * they stay in sync without prop drilling.
 */
import { createStore } from 'zustand/vanilla';

export function createViewerStore() {
  return createStore((set) => ({
    scale: 1,
    translate: { x: 0, y: 0 },
    currentPage: 1,
    currentTool: 'pan',           // 'pan' | 'g1' | 'g2' | 'g3' | 'g4' | 'g5'
    hoveredRoomId: null,

    setScale: (scale) => set({ scale }),
    setTranslate: (translate) => set({ translate }),
    setTransform: ({ scale, translate }) => set({ scale, translate }),
    setCurrentPage: (currentPage) => set({ currentPage }),
    setCurrentTool: (currentTool) => set({ currentTool }),
    setHoveredRoomId: (hoveredRoomId) => set({ hoveredRoomId }),
  }));
}

// Singleton shared across React tree (each project view reuses).
export const viewerStore = createViewerStore();
```

- [ ] **Step 2.4: Tests pass**

```bash
cd frontend && node --test src/lib/viewerStore.test.js
```
Expected: 4/4 pass.

- [ ] **Step 2.5: Commit**

```bash
git add frontend/src/lib/viewerStore.js frontend/src/lib/viewerStore.test.js
git commit -m "feat(sprint-1): zustand viewer store (transform, tool, hover)"
```

---

## Task 3: renderQueue.js — Concurrent Render Queue

**Files:**
- Create: `frontend/src/lib/renderQueue.js`
- Create: `frontend/src/lib/renderQueue.test.js`

- [ ] **Step 3.1: Failing test**

```javascript
// frontend/src/lib/renderQueue.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRenderQueue } from './renderQueue.js';

test('renderQueue runs at most 2 jobs concurrently', async () => {
  const queue = createRenderQueue(2);
  let inFlight = 0;
  let maxObserved = 0;
  const job = async () => {
    inFlight++;
    maxObserved = Math.max(maxObserved, inFlight);
    await new Promise(r => setTimeout(r, 20));
    inFlight--;
    return 'ok';
  };
  const results = await Promise.all(Array(8).fill(0).map(() => queue(job)));
  assert.equal(results.length, 8);
  assert.ok(results.every(r => r === 'ok'));
  assert.equal(maxObserved, 2);
});

test('renderQueue propagates errors', async () => {
  const queue = createRenderQueue(2);
  await assert.rejects(
    () => queue(async () => { throw new Error('boom'); }),
    /boom/
  );
});
```

- [ ] **Step 3.2: Run, verify fails**

```bash
cd frontend && node --test src/lib/renderQueue.test.js
```
Expected: FAIL — module missing.

- [ ] **Step 3.3: Implement**

```javascript
// frontend/src/lib/renderQueue.js
/**
 * Sprint 1: bounded concurrency for pdf.js page renders.
 *
 * pdf.js spawns one worker thread already, but each `page.render()` call
 * eats main-thread cycles for canvas blitting. Without a cap, scrolling
 * 65 thumbnails kicks off 65 parallel renders and the UI thrashes.
 *
 * Wrap each render in queue() to limit to N concurrent jobs.
 * Default N=2 matches `navigator.hardwareConcurrency / 2` on typical
 * 4-core devices.
 */
import pLimit from 'p-limit';

export function createRenderQueue(concurrency = 2) {
  const limit = pLimit(concurrency);
  return (job) => limit(job);
}

export const renderQueue = createRenderQueue(2);
```

- [ ] **Step 3.4: Tests pass**

```bash
cd frontend && node --test src/lib/renderQueue.test.js
```
Expected: 2/2 pass.

- [ ] **Step 3.5: Commit**

```bash
git add frontend/src/lib/renderQueue.js frontend/src/lib/renderQueue.test.js
git commit -m "feat(sprint-1): p-limit(2) render queue for pdf.js page renders"
```

---

## Task 4: tileCache.js — LRU ImageBitmap Cache

**Files:**
- Create: `frontend/src/lib/tileCache.js`
- Create: `frontend/src/lib/tileCache.test.js`

- [ ] **Step 4.1: Failing test**

```javascript
// frontend/src/lib/tileCache.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createTileCache } from './tileCache.js';

// Stub ImageBitmap with a close() method so we can assert eviction calls it.
class StubBitmap {
  constructor(id) { this.id = id; this.closed = false; }
  close() { this.closed = true; }
}

test('tileCache: get returns set value', () => {
  const cache = createTileCache({ max: 5 });
  const b = new StubBitmap('a');
  cache.set('a', b);
  assert.equal(cache.get('a'), b);
});

test('tileCache: evicts oldest and calls close() on evicted', () => {
  const cache = createTileCache({ max: 2 });
  const a = new StubBitmap('a');
  const b = new StubBitmap('b');
  const c = new StubBitmap('c');
  cache.set('a', a);
  cache.set('b', b);
  cache.set('c', c);  // evicts 'a'
  assert.equal(cache.get('a'), undefined);
  assert.equal(a.closed, true, 'evicted bitmap.close() should have been called');
  assert.equal(b.closed, false);
  assert.equal(c.closed, false);
});

test('tileCache: clear() closes all and empties', () => {
  const cache = createTileCache({ max: 5 });
  const a = new StubBitmap('a');
  const b = new StubBitmap('b');
  cache.set('a', a);
  cache.set('b', b);
  cache.clear();
  assert.equal(cache.get('a'), undefined);
  assert.equal(cache.get('b'), undefined);
  assert.equal(a.closed, true);
  assert.equal(b.closed, true);
});
```

- [ ] **Step 4.2: Run, verify fails**

```bash
cd frontend && node --test src/lib/tileCache.test.js
```
Expected: FAIL — module missing.

- [ ] **Step 4.3: Implement**

```javascript
// frontend/src/lib/tileCache.js
/**
 * Sprint 1: LRU cache for rendered ImageBitmap tiles.
 *
 * Browsers don't eagerly GC ImageBitmaps — confirmed pdf.js memory pain
 * in long sessions. We MUST call .close() on evicted bitmaps to free
 * GPU memory.
 *
 * Key shape: `${pageIdx}:${zoomLevel}` — e.g. "0:1.5" for page 0 at 1.5×.
 */
import { LRUCache } from 'lru-cache';

export function createTileCache({ max = 30 } = {}) {
  const cache = new LRUCache({
    max,
    dispose: (value /* , key, reason */) => {
      // Free GPU memory; safe to call even if already closed.
      if (value && typeof value.close === 'function') {
        try { value.close(); } catch { /* ignore */ }
      }
    },
  });

  return {
    get: (k) => cache.get(k),
    set: (k, v) => cache.set(k, v),
    has: (k) => cache.has(k),
    clear: () => cache.clear(),
    size: () => cache.size,
  };
}

export const tileCache = createTileCache({ max: 30 });
```

- [ ] **Step 4.4: Tests pass**

```bash
cd frontend && node --test src/lib/tileCache.test.js
```
Expected: 3/3 pass.

- [ ] **Step 4.5: Commit**

```bash
git add frontend/src/lib/tileCache.js frontend/src/lib/tileCache.test.js
git commit -m "feat(sprint-1): LRU ImageBitmap cache with close-on-evict"
```

---

## Task 5: mipPyramid.js — Zoom Level Selection + Pure Math

**Files:**
- Create: `frontend/src/lib/mipPyramid.js`
- Create: `frontend/src/lib/mipPyramid.test.js`

- [ ] **Step 5.1: Failing test**

```javascript
// frontend/src/lib/mipPyramid.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pickZoomLevel, MIP_LEVELS } from './mipPyramid.js';

test('MIP_LEVELS is the canonical 3-level pyramid', () => {
  assert.deepEqual(MIP_LEVELS, [0.5, 1.5, 3.0]);
});

test('pickZoomLevel: scale 0.3 → 0.5 (smallest preview)', () => {
  assert.equal(pickZoomLevel(0.3), 0.5);
});

test('pickZoomLevel: scale 1.0 → 1.5 (canonical)', () => {
  assert.equal(pickZoomLevel(1.0), 1.5);
});

test('pickZoomLevel: scale 2.5 → 3.0 (deep zoom)', () => {
  assert.equal(pickZoomLevel(2.5), 3.0);
});

test('pickZoomLevel: scale 5.0 → 3.0 (cap at deepest level)', () => {
  assert.equal(pickZoomLevel(5.0), 3.0);
});

test('pickZoomLevel: scale exactly at boundary 1.5 → 1.5', () => {
  assert.equal(pickZoomLevel(1.5), 1.5);
});
```

- [ ] **Step 5.2: Run, verify fails**

```bash
cd frontend && node --test src/lib/mipPyramid.test.js
```
Expected: FAIL.

- [ ] **Step 5.3: Implement**

```javascript
// frontend/src/lib/mipPyramid.js
/**
 * Sprint 1: 3-level mip-pyramid for PDF page rendering.
 *
 * Render each page at a small set of fixed zoom levels rather than
 * tile-by-tile. For viewport scale S, pick the closest level >= S so
 * blits look crisp on settle. CSS transform handles in-between scales
 * during interactive pan/zoom.
 */

export const MIP_LEVELS = [0.5, 1.5, 3.0];

/**
 * Given the user's current viewport scale (e.g. 1.0 = 100% zoom),
 * return the mip-level we should render against.
 */
export function pickZoomLevel(scale) {
  for (const level of MIP_LEVELS) {
    if (scale <= level) return level;
  }
  return MIP_LEVELS[MIP_LEVELS.length - 1];
}

/**
 * Build a cache key for (pageIdx, zoomLevel).
 */
export function tileKey(pageIdx, zoomLevel) {
  return `${pageIdx}:${zoomLevel}`;
}

/**
 * Render a pdf.js page at the given mip-zoom level into an ImageBitmap.
 *
 * Uses OffscreenCanvas so the heavy bitmap work happens on a background
 * canvas; we transferToImageBitmap() at the end for fast blits.
 *
 * Caller is responsible for caching the returned bitmap and calling
 * .close() when evicting.
 */
export async function renderPageToImageBitmap(page, zoomLevel) {
  const dpr = Math.min(globalThis.devicePixelRatio || 1, 2);
  const viewport = page.getViewport({ scale: zoomLevel * dpr });
  const offscreen = new OffscreenCanvas(viewport.width, viewport.height);
  const ctx = offscreen.getContext('2d');
  await page.render({ canvasContext: ctx, viewport }).promise;
  return offscreen.transferToImageBitmap();
}
```

- [ ] **Step 5.4: Tests pass**

```bash
cd frontend && node --test src/lib/mipPyramid.test.js
```
Expected: 6/6 pass.

- [ ] **Step 5.5: Commit**

```bash
git add frontend/src/lib/mipPyramid.js frontend/src/lib/mipPyramid.test.js
git commit -m "feat(sprint-1): mip-pyramid math + OffscreenCanvas page renderer"
```

---

## Task 6: TakeoffCanvas.jsx — Component Skeleton

**Files:**
- Create: `frontend/src/components/canvas/TakeoffCanvas.jsx`

- [ ] **Step 6.1: Implement skeleton**

```jsx
// frontend/src/components/canvas/TakeoffCanvas.jsx
/**
 * Sprint 1: TakeoffCanvas — pdf.js renderer with mip-pyramid + CSS
 * transform during interaction.
 *
 * Renders ONE page at a time at the canonical mip level. During pan/zoom
 * (mouse drag, wheel), CSS transform animates the canvas at 60 fps. After
 * 150 ms of inactivity, re-render at the new scale via OffscreenCanvas.
 *
 * Sprint 2 will add the Konva annotation overlay; Sprint 3 wires
 * bidirectional highlight via viewerStore.
 */
import { useEffect, useRef, useState } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { renderQueue } from '../../lib/renderQueue';
import { tileCache } from '../../lib/tileCache';
import { pickZoomLevel, tileKey, renderPageToImageBitmap } from '../../lib/mipPyramid';

const SETTLE_DEBOUNCE_MS = 150;

export function TakeoffCanvas({ pdfDoc, pageIdx = 0 }) {
  const canvasRef = useRef(null);
  const settleTimerRef = useRef(null);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const [renderedLevel, setRenderedLevel] = useState(null);

  // Render the current page at the current mip-zoom level when scale settles.
  useEffect(() => {
    if (!pdfDoc) return;
    if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
    settleTimerRef.current = setTimeout(() => {
      const targetLevel = pickZoomLevel(scale);
      if (targetLevel === renderedLevel) return;

      const key = tileKey(pageIdx, targetLevel);
      const cached = tileCache.get(key);
      if (cached) {
        blit(canvasRef.current, cached);
        setRenderedLevel(targetLevel);
        return;
      }

      renderQueue(async () => {
        const page = await pdfDoc.getPage(pageIdx + 1);
        const bitmap = await renderPageToImageBitmap(page, targetLevel);
        tileCache.set(key, bitmap);
        blit(canvasRef.current, bitmap);
        setRenderedLevel(targetLevel);
      }).catch((err) => {
        console.error('[TakeoffCanvas] render failed:', err);
      });
    }, SETTLE_DEBOUNCE_MS);

    return () => clearTimeout(settleTimerRef.current);
  }, [pdfDoc, pageIdx, scale, renderedLevel]);

  // CSS transform during interaction — GPU-accelerated, no re-render.
  const transformStyle = {
    transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale / (renderedLevel || 1)})`,
    transformOrigin: '0 0',
    willChange: 'transform',
  };

  return (
    <div style={{ overflow: 'hidden', width: '100%', height: '100%', position: 'relative' }}>
      <canvas ref={canvasRef} style={transformStyle} />
    </div>
  );
}

function blit(targetCanvas, bitmap) {
  if (!targetCanvas || !bitmap) return;
  targetCanvas.width = bitmap.width;
  targetCanvas.height = bitmap.height;
  const ctx = targetCanvas.getContext('2d');
  ctx.drawImage(bitmap, 0, 0);
}
```

- [ ] **Step 6.2: Smoke-check that the file imports cleanly**

```bash
cd frontend && npx vite build 2>&1 | tail -20
```
Expected: no import errors. Some warnings OK.

If `vite build` is slow, alternative: `cd frontend && node --input-type=module -e "import('./src/components/canvas/TakeoffCanvas.jsx').catch(e => { console.error(e); process.exit(1); })"`

If build/import fails on JSX, that's expected for a one-line check — you can also just verify the file syntax with `node --check` or skip the smoke check and trust the next task's mount-test.

- [ ] **Step 6.3: Commit**

```bash
git add frontend/src/components/canvas/TakeoffCanvas.jsx
git commit -m "feat(sprint-1): TakeoffCanvas skeleton — mip-pyramid + CSS transform settle"
```

---

## Task 7: Pan/Zoom Interaction Handlers

**Files:**
- Modify: `frontend/src/components/canvas/TakeoffCanvas.jsx` (add wheel + drag)

- [ ] **Step 7.1: Extend TakeoffCanvas with interaction**

In `TakeoffCanvas.jsx`, add inside the component (above the return):

```jsx
const containerRef = useRef(null);
const setTransform = useStore(viewerStore, (s) => s.setTransform);
const setScale = useStore(viewerStore, (s) => s.setScale);

// Wheel zoom: relative-to-pointer
const onWheel = (e) => {
  e.preventDefault();
  const rect = containerRef.current.getBoundingClientRect();
  const px = e.clientX - rect.left;
  const py = e.clientY - rect.top;
  const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
  const newScale = Math.max(0.25, Math.min(scale * factor, 6));
  // Adjust translate so the pixel under cursor stays under cursor
  const newTranslate = {
    x: px - (px - translate.x) * (newScale / scale),
    y: py - (py - translate.y) * (newScale / scale),
  };
  setTransform({ scale: newScale, translate: newTranslate });
};

// Mouse drag pan
const dragRef = useRef({ active: false, startX: 0, startY: 0, baseTx: 0, baseTy: 0 });
const onPointerDown = (e) => {
  if (e.button !== 0) return;
  dragRef.current = {
    active: true,
    startX: e.clientX, startY: e.clientY,
    baseTx: translate.x, baseTy: translate.y,
  };
  e.currentTarget.setPointerCapture(e.pointerId);
};
const onPointerMove = (e) => {
  if (!dragRef.current.active) return;
  const dx = e.clientX - dragRef.current.startX;
  const dy = e.clientY - dragRef.current.startY;
  setTransform({
    scale,
    translate: { x: dragRef.current.baseTx + dx, y: dragRef.current.baseTy + dy },
  });
};
const onPointerUp = (e) => {
  dragRef.current.active = false;
  e.currentTarget.releasePointerCapture(e.pointerId);
};
```

Then update the return JSX to attach handlers on the container:

```jsx
return (
  <div
    ref={containerRef}
    onWheel={onWheel}
    onPointerDown={onPointerDown}
    onPointerMove={onPointerMove}
    onPointerUp={onPointerUp}
    style={{ overflow: 'hidden', width: '100%', height: '100%', position: 'relative', cursor: dragRef.current.active ? 'grabbing' : 'grab', touchAction: 'none' }}
  >
    <canvas ref={canvasRef} style={transformStyle} />
  </div>
);
```

- [ ] **Step 7.2: Commit**

```bash
git add frontend/src/components/canvas/TakeoffCanvas.jsx
git commit -m "feat(sprint-1): pan/zoom handlers with relative-to-pointer wheel zoom"
```

---

## Task 8: MemoryWatchdog Component

**Files:**
- Create: `frontend/src/components/canvas/MemoryWatchdog.jsx`

- [ ] **Step 8.1: Implement**

```jsx
// frontend/src/components/canvas/MemoryWatchdog.jsx
/**
 * Sprint 1: address pdf.js #20198 memory leak in long sessions.
 *
 * Polls performance.memory every 30 s. If usedJSHeapSize > 500 MB AND the
 * user is idle (last interaction >30 s ago), call onReset() so the parent
 * can pdfDoc.destroy() and recreate from the cached Blob.
 *
 * No-op in browsers without performance.memory (Firefox, Safari).
 */
import { useEffect, useRef } from 'react';

const HEAP_THRESHOLD = 500 * 1024 * 1024;  // 500 MB
const IDLE_MS = 30_000;
const POLL_MS = 30_000;

export function MemoryWatchdog({ onReset }) {
  const lastInteractionRef = useRef(Date.now());

  useEffect(() => {
    const bumpInteraction = () => { lastInteractionRef.current = Date.now(); };
    window.addEventListener('pointerdown', bumpInteraction);
    window.addEventListener('keydown', bumpInteraction);
    window.addEventListener('wheel', bumpInteraction, { passive: true });

    const interval = setInterval(() => {
      const mem = performance.memory;
      if (!mem) return;
      const heap = mem.usedJSHeapSize;
      const idleFor = Date.now() - lastInteractionRef.current;
      if (heap > HEAP_THRESHOLD && idleFor > IDLE_MS) {
        console.warn(`[MemoryWatchdog] heap=${(heap / 1024 / 1024).toFixed(0)} MB idle=${(idleFor / 1000).toFixed(0)}s — resetting`);
        onReset?.();
        lastInteractionRef.current = Date.now();
      }
    }, POLL_MS);

    return () => {
      window.removeEventListener('pointerdown', bumpInteraction);
      window.removeEventListener('keydown', bumpInteraction);
      window.removeEventListener('wheel', bumpInteraction);
      clearInterval(interval);
    };
  }, [onReset]);

  return null;
}
```

- [ ] **Step 8.2: Commit**

```bash
git add frontend/src/components/canvas/MemoryWatchdog.jsx
git commit -m "feat(sprint-1): MemoryWatchdog — auto-reset >500MB heap when idle"
```

---

## Task 9: New /project/:id?v=2 Route

**Files:**
- Create: `frontend/src/pages/InteriorProjectV2.jsx`
- Modify: `frontend/src/App.jsx` (or wherever routes live)

- [ ] **Step 9.1: Implement skeleton page**

```jsx
// frontend/src/pages/InteriorProjectV2.jsx
/**
 * Sprint 1: new dual-route mount for the takeoff workspace.
 *
 * URL: /project/:id?v=2 — opt-in during Sprints 1-3, default at end of
 * Sprint 3, legacy /project/:id removed Sprint 4.
 *
 * For Sprint 1 this page only mounts <TakeoffCanvas>; full chrome
 * (top bar, side panel, verification panel) arrives Sprint 3.
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import * as pdfjsLib from 'pdfjs-dist';
import { getPdfBlob } from '../lib/pdfStore';
import { TakeoffCanvas } from '../components/canvas/TakeoffCanvas';
import { MemoryWatchdog } from '../components/canvas/MemoryWatchdog';
import { tileCache } from '../lib/tileCache';

// pdfjsLib worker setup is shared with the legacy viewer; if undefined here,
// import the existing setup from wherever PdfViewer.jsx wires it.

export default function InteriorProjectV2() {
  const { id } = useParams();
  const [pdfDoc, setPdfDoc] = useState(null);
  const [error, setError] = useState(null);

  const loadPdf = useCallback(async () => {
    try {
      const blob = await getPdfBlob(id);
      if (!blob) {
        setError('Brėžinys nerastas (uždaryk + atidaryk projektą iš naujo).');
        return;
      }
      const buf = await blob.arrayBuffer();
      const doc = await pdfjsLib.getDocument({ data: buf }).promise;
      setPdfDoc(doc);
    } catch (err) {
      setError(`Nepavyko užkrauti PDF: ${err.message}`);
    }
  }, [id]);

  useEffect(() => { loadPdf(); }, [loadPdf]);

  // Memory reset: destroy doc + clear tile cache + reload
  const handleReset = useCallback(() => {
    pdfDoc?.destroy().catch(() => {});
    tileCache.clear();
    setPdfDoc(null);
    loadPdf();
  }, [pdfDoc, loadPdf]);

  if (error) return <div style={{ padding: 20, color: '#fff' }}>{error}</div>;
  if (!pdfDoc) return <div style={{ padding: 20, color: '#aaa' }}>Kraunamas brėžinys…</div>;

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#0e1216' }}>
      <MemoryWatchdog onReset={handleReset} />
      <TakeoffCanvas pdfDoc={pdfDoc} pageIdx={0} />
    </div>
  );
}
```

- [ ] **Step 9.2: Add route**

Find the routes file (likely `frontend/src/App.jsx` or a `routes.jsx`). Search:
```bash
cd frontend && grep -rn "project/:id" src/ | head -3
```

Add the new route alongside (do NOT remove the legacy route):

```jsx
import InteriorProjectV2 from './pages/InteriorProjectV2';

// inside <Routes>:
<Route path="/project/:id" element={<InteriorProject />} />
<Route path="/project/:id/v2" element={<InteriorProjectV2 />} />
```

(Alternative: detect `?v=2` query param in the existing route. Path-based is simpler and what the spec calls for. Pick path-based.)

- [ ] **Step 9.3: Smoke-test build**

```bash
cd frontend && npx vite build 2>&1 | tail -10
```
Expected: builds without errors.

- [ ] **Step 9.4: Commit**

```bash
git add frontend/src/pages/InteriorProjectV2.jsx frontend/src/App.jsx
git commit -m "feat(sprint-1): /project/:id/v2 route mounts TakeoffCanvas"
```

---

## Task 10: Browser Smoke Test + Performance Snapshot

**Files:**
- (Verification only — no code changes; document findings in commit message + follow-ups)

- [ ] **Step 10.1: Run dev servers**

```bash
cd backend && uvicorn main:app --reload &
cd frontend && npm run dev
```

- [ ] **Step 10.2: Open `/project/<existing-id>/v2` in browser**

Manual verification:
- PDF page renders within 2-3 seconds of load
- Wheel zoom at 60 fps (smooth, no flicker)
- Drag pan at 60 fps
- After zoom/drag stops, image re-rasterizes to crisp resolution within ~150 ms
- No console errors

- [ ] **Step 10.3: Performance benchmark**

Open DevTools → Performance → Record 5 seconds of zooming + panning. Note frame rate. Compare to legacy `/project/<id>`.

- [ ] **Step 10.4: Memory check**

Open multiple PDFs in succession (5+). Watch `performance.memory.usedJSHeapSize` in console. After ~5 minutes of churn, verify either (a) heap stays bounded under 500 MB, or (b) MemoryWatchdog logs a reset.

- [ ] **Step 10.5: Document findings**

Append to `docs/sprint-1-followups.md`:

```markdown
# Sprint 1 Follow-Ups

## Smoke test results 2026-05-XX

- Frame rate during zoom: ~60 fps ✓ / __ fps if degraded
- Frame rate during pan: ~60 fps ✓ / __ fps if degraded
- Settle render latency: ~__ ms (target <200 ms)
- Memory after 5 min of churn: __ MB (cap 500 MB)
- Console errors: __ (target 0)

## Issues found
(list anything broken — to triage into Sprint 2 plan or fix immediately)
```

- [ ] **Step 10.6: Commit findings doc**

```bash
git add docs/sprint-1-followups.md
git commit -m "chore(sprint-1): smoke test results + follow-ups doc"
```

---

## Task 11: Sprint 1 Acceptance — CHANGELOG + Tests

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 11.1: Verify all tests still pass**

```bash
cd backend && ./venv/bin/python -m pytest tests/ 2>&1 | tail -3
cd frontend && node --test 2>&1 | tail -5
```
Expected: 196+ backend pass, 38+12 = 50 frontend pass (4 new test files added).

- [ ] **Step 11.2: Update CHANGELOG**

Prepend to `CHANGELOG.md`:

```markdown
## Sprint 1 — Tile-Based Rendering — 2026-05-XX

### Added
- New `<TakeoffCanvas>` component with mip-pyramid (3 fixed zoom levels) +
  CSS-transform-during-interaction + OffscreenCanvas settle render. Zoom
  and pan should now hit 60 fps even on large PDFs.
- New route `/project/:id/v2` mounts the takeoff workspace. Legacy route
  `/project/:id` continues to use the old viewer; default switches at end
  of Sprint 3.
- `MemoryWatchdog` auto-resets the PDF doc when JS heap exceeds 500 MB
  and the user is idle for 30 s, addressing pdf.js #20198 leak.

### Internal
- New libs: `viewerStore.js` (zustand), `renderQueue.js` (p-limit(2)),
  `tileCache.js` (LRU + ImageBitmap close-on-evict), `mipPyramid.js`
  (zoom-level math + OffscreenCanvas page renderer).
- 4 new frontend test files; pure-function math for mip selection and
  cache eviction is fully unit-tested.

### Known follow-ups
See `docs/sprint-1-followups.md`.
```

- [ ] **Step 11.3: Commit acceptance**

```bash
git add CHANGELOG.md
git commit -m "chore(sprint-1): acceptance — CHANGELOG, tests verified"
```

---

## Sprint 1 Wrap

After Task 11 commits cleanly, Sprint 1 is done. Next: writing-plans skill writes the Sprint 2 plan (gestures G1-G5+G7 + shared-walls polygon pre-pass).

---

## Self-Review

- **Spec coverage:** §6 Sprint 1 deliverables = mip-pyramid + CSS transform + OffscreenCanvas + p-limit(2) — covered by Tasks 5, 6, 7, 3 respectively. Memory watchdog (Sprint 3 in spec but research said do it now) covered by Task 8. New route migration covered by Task 9.
- **Placeholder scan:** Steps 7.1, 9.2, 10.X have "if existing structure differs, adapt" hedges — these are necessary because the implementer needs to read actual code. No "TBD" / "implement later" in step bodies.
- **Type consistency:** `pickZoomLevel` returns a number; `tileKey(pageIdx, zoomLevel)` consumes it — consistent. `viewerStore.scale` is a number; `pickZoomLevel(scale)` consumes — consistent. `tileCache` `dispose` callback closes `ImageBitmap` — `renderPageToImageBitmap` returns one — consistent.
- **Scope:** 11 tasks, ~5-7 days estimated. No subsystem decomposition needed; everything is the same workspace/canvas concern.

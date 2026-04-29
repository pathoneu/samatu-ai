# Phase C-1 — Manual Polygon Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Bluebeam-style manual polygon editor inside the existing PdfViewer so users can trace and edit room boundaries with vertex drag, midpoint-ghost insertion, ortho-90° default, snap-to-other-polygons, multi-select, and operation-level undo/redo. Polygons round-trip into the room data model so `polygon_pdf` becomes the precise replacement for unreliable `bbox_pct` highlights.

**Architecture:** Extend the existing polygon tool in `MarkupCanvas` (PdfViewer.jsx). Storage and CRUD already live in `takeoffStore.js`. We add a new `PolygonEditor` Konva sub-component for vertex/edge editing, a pure `polygonGeometry.js` module for the new math (ortho snap, self-intersection, vertex/edge spatial hash, point-in-polygon), and small UI surfaces (mode banner, first-time hint, per-room badge, mobile banner). When a polygon is committed against a specific room, we mirror it into `room.polygon_pdf` so `AiRoomOverlay` and `TraceOverlay` (already polygon-aware) light up automatically. Pure functions are tested with Node's built-in `node:test` runner — no new dev deps.

**Tech Stack:**
- Frontend: react-konva 18.2 / konva 9.3 / react-pdf 9.1 / pdfjs-dist 4.6 (locked, see `2026-04-29-phase-c-libraries.md`)
- Existing modules reused: `frontend/src/lib/takeoffStore.js` (CRUD, undo/redo, area, perimeter, snap-to-lines), `frontend/src/components/project/MarkupCanvas` inside `PdfViewer.jsx`, `frontend/src/components/project/AiRoomOverlay.jsx` and `TraceOverlay.jsx` (already render `polygon_pdf`)
- Test runner: `node --test` (built-in, Node 18+; no new dep)

**Spec sources:**
- `docs/superpowers/plans/2026-04-29-phase-c-pdf-rewrite-research.md` §4 — 13-item acceptance checklist
- `docs/superpowers/research/2026-04-29-phase-c-polygon-ux.md` §3, §5, §10.9 — interaction details, keyboard table, acceptance criteria
- `docs/superpowers/research/2026-04-29-phase-c-libraries.md` §4 — Konva perf flags, PDF.js worker hardening

---

## File Structure

### Existing files MODIFIED
- `frontend/src/components/project/PdfViewer.jsx` — extend `MarkupCanvas` with active-edit layer; add keyboard handlers, mode state, room-target prop wiring
- `frontend/src/lib/takeoffStore.js` — extend `addPolygon/updatePolygon` semantics for vertex-level edits (already supports update_polygon op) and write-through to room data
- `frontend/src/lib/projectStore.js` — write `polygon_pdf` to a room's data when a polygon is committed against that room; strip on outbound sync if user is offline
- `frontend/src/components/project/WorkspacePanel.jsx` — mount `PolygonReviewBadge` per room row
- `frontend/src/components/project/RoomCard.jsx` — same badge, on the room card surface
- `frontend/src/components/project/AiRoomOverlay.jsx` — split into `committed-polygons` layer (`listening:false`) and let `PolygonEditor` own the active-edit layer. Tiny diff: pass through whether each room has a manual polygon so the overlay can defer to the editor for that room
- `frontend/vite.config.js` — `vite-plugin-static-copy` for `pdf.worker.mjs` (Gate 1 fix)
- `frontend/src/main.jsx` — remove any `workerSrc` setting if present (move into `PdfViewer`)

### New files CREATED
- `frontend/src/lib/polygonGeometry.js` — pure functions: `selfIntersects(points)`, `orthoSnap(prev, cursor, opts)`, `pointInPolygon(p, poly)`, `nearestVertex(point, polygons, tol)`, `nearestEdge(point, polygons, tol)`, `polygonCentroid(points)`
- `frontend/src/lib/polygonGeometry.test.js` — `node:test` unit tests for the above
- `frontend/src/components/project/PolygonEditor.jsx` — the active-edit Konva sub-tree: vertex handles, midpoint ghosts, snap indicator, multi-select, drag with imperative `.position()`
- `frontend/src/components/project/TraceModeBanner.jsx` — top-of-canvas Lithuanian banner shown only while tracing or editing
- `frontend/src/components/project/FirstTimePolygonHint.jsx` — one-time overlay; persists `samatu_polygon_hint_seen` in localStorage
- `frontend/src/components/project/PolygonReviewBadge.jsx` — small pill: 🟢 polygonas / 🟡 tik bbox; click jumps to PDF + activates room
- `frontend/src/components/project/MobileViewOnlyBanner.jsx` — Lithuanian banner shown when `pointer:coarse` matches; suppresses edit affordances

### Test files NEW (run via `node --test`)
- `frontend/src/lib/polygonGeometry.test.js`

Add `package.json` script: `"test:units": "node --test src/lib/*.test.js"` (one-line edit)

---

## Pre-flight (Gate 1 from synthesis plan)

### Task 0: Reproduce + fix the pdf.worker prod-cache bug

**Files:**
- Modify: `frontend/vite.config.js`
- Modify: `frontend/package.json` (add `vite-plugin-static-copy`)
- Modify: `frontend/src/components/project/PdfViewer.jsx:14-18` (worker config)
- Modify: `frontend/src/main.jsx` (strip worker config if present)

This is the only Phase-C blocker the libraries research flagged as already symptomatic in production. Fix before any polygon work — broken PDF rendering breaks the whole sprint.

- [ ] **Step 0.1: Confirm the symptom**

Run: `cd frontend && grep -rn "workerSrc\|pdf.worker" src/ vite.config.js`
Expected output: shows current worker setup. Note where `workerSrc` is currently assigned (if it's in `main.jsx`, that is the bug).

- [ ] **Step 0.2: Install vite-plugin-static-copy**

Run: `cd frontend && npm install --save-dev vite-plugin-static-copy@^2.1.0`
Expected: clean install, lockfile updated.

- [ ] **Step 0.3: Update vite.config.js to copy worker to public output**

Add to `frontend/vite.config.js`:

```javascript
import { viteStaticCopy } from 'vite-plugin-static-copy';
// ... existing imports

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        {
          src: 'node_modules/pdfjs-dist/build/pdf.worker.mjs',
          dest: '.',
          rename: 'pdf.worker.mjs',
        },
      ],
    }),
  ],
  // ... rest unchanged
});
```

- [ ] **Step 0.4: Move workerSrc into PdfViewer module-level**

In `frontend/src/components/project/PdfViewer.jsx` near line 15 (after `import { Document, Page, pdfjs } from 'react-pdf';`), add:

```javascript
// Worker is copied to /pdf.worker.mjs via vite-plugin-static-copy in vite.config.
// Set workerSrc here, not in main.jsx — Vite's module-execution order can let
// later imports overwrite a workerSrc set globally, breaking prod after deploy.
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs';
```

If `main.jsx` had any `pdfjs.GlobalWorkerOptions.workerSrc = ...` line, delete it.

- [ ] **Step 0.5: Smoke test build + dev**

Run: `cd frontend && npm run dev`
Expected: PDF renders in workspace; no `Failed to fetch worker` or `version mismatch` console errors.
Run (separate terminal): `cd frontend && npm run build && npm run preview`
Expected: production build serves `/pdf.worker.mjs` at the root URL; PDF renders identically.

- [ ] **Step 0.6: Commit**

```bash
cd ~/samatu-ai
git add frontend/vite.config.js frontend/package.json frontend/package-lock.json frontend/src/components/project/PdfViewer.jsx frontend/src/main.jsx
git commit -m "fix(pdf): pin pdf.worker to /public via vite-plugin-static-copy

PDF.js worker file was content-hashed by Vite, breaking prod cache after
deploys. Copy worker to a stable /pdf.worker.mjs path and set workerSrc
inside the PdfViewer module to avoid Vite's module-execution race in main.jsx."
```

---

### Task 1: Konva perf flags + PDF cleanup on unmount

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — add cleanup effects and Konva globals

- [ ] **Step 1.1: Set Konva global perf flags at PdfViewer module top**

In `frontend/src/components/project/PdfViewer.jsx`, near the top (after the konva imports around line 25), add:

```javascript
import Konva from 'konva';

// Phase C-1 (2026-04-29): see docs/superpowers/research/2026-04-29-phase-c-libraries.md §4.2.
// These globals are write-once; turning them off shaves 10-30% draw cost on
// overlays with no transforms or shadows, which is our case.
Konva.pixelRatio = 1;
Konva.autoDrawEnabled = true;
```

Then on every Konva `Layer` we own (search for `<Layer` occurrences in PdfViewer.jsx — there should be 1 inside `MarkupCanvas`), set `listening` only on the active-edit layer (Task 12 splits this) and add `transformsEnabled="position"` on shapes that don't rotate/skew.

- [ ] **Step 1.2: Verify FastLayer is not used**

Run: `cd frontend && grep -rn "FastLayer" src/`
Expected: zero matches. (FastLayer is deprecated as of Konva 9; use `<Layer listening={false}>` instead — covered in Task 12.)

- [ ] **Step 1.3: Add explicit pdf.destroy() + page.cleanup() on unmount**

In `frontend/src/components/project/PdfViewer.jsx`, locate the `<Document file={fileUrl}>` mount. Capture the returned PDFDocumentProxy via `onLoadSuccess`:

```javascript
const pdfDocRef = useRef(null);

// inside <Document onLoadSuccess={...}>:
onLoadSuccess={(pdf) => {
  pdfDocRef.current = pdf;
  setNumPages(pdf.numPages);
}}

// cleanup effect:
useEffect(() => {
  return () => {
    try {
      pdfDocRef.current?.destroy?.();
    } catch (e) {
      console.warn('[PdfViewer] pdf.destroy failed', e);
    }
  };
}, []);
```

For per-page cleanup, capture page proxy via `<Page onLoadSuccess={(page) => pageProxyRef.current = page}>` and call `page.cleanup()` in the same useEffect cleanup.

- [ ] **Step 1.4: Smoke test memory**

Run: `cd frontend && npm run dev`
Open a 50+ page PDF in the workspace. Open Chrome DevTools → Memory → take heap snapshot. Switch pages 10 times. Take a second snapshot. Compare: heap delta should be < 20 MB (was unbounded).
This is a manual check; if heap grows by hundreds of MB, the cleanup didn't wire up.

- [ ] **Step 1.5: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "perf(pdf): explicit pdf.destroy + page.cleanup on unmount; Konva globals

Long sessions with multi-page PDFs leak ~30 MB/page without explicit
cleanup. Add a ref-tracked destroy on PdfViewer unmount and set Konva
pixelRatio=1 globally per the Phase C library research."
```

---

## Phase A: Geometry foundation (TDD)

### Task 2: polygonGeometry.js — selfIntersects()

**Files:**
- Create: `frontend/src/lib/polygonGeometry.js`
- Create: `frontend/src/lib/polygonGeometry.test.js`
- Modify: `frontend/package.json` — add `"test:units"` script

This and the next 5 tasks are pure functions, perfectly TDD-able with `node:test`. Do all six in TDD order to keep the cycle tight.

- [ ] **Step 2.1: Create the test file with a failing test**

Create `frontend/src/lib/polygonGeometry.test.js`:

```javascript
import test from 'node:test';
import assert from 'node:assert/strict';
import { selfIntersects } from './polygonGeometry.js';

test('selfIntersects: simple square is not self-intersecting', () => {
  const square = [
    { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(square), false);
});

test('selfIntersects: bowtie is self-intersecting', () => {
  // Classic bowtie — edges (p0→p1) and (p2→p3) cross
  const bowtie = [
    { x: 0, y: 0 }, { x: 10, y: 10 }, { x: 10, y: 0 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(bowtie), true);
});

test('selfIntersects: triangle is not self-intersecting', () => {
  const tri = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 5, y: 10 }];
  assert.equal(selfIntersects(tri), false);
});

test('selfIntersects: shared vertex between adjacent edges is allowed', () => {
  // Adjacent edges share a vertex — that's NOT self-intersection
  const square = [
    { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(square), false);
});
```

- [ ] **Step 2.2: Add the test:units script to package.json**

Edit `frontend/package.json` → `"scripts"` block → add: `"test:units": "node --test src/lib/*.test.js"`

- [ ] **Step 2.3: Run test, verify FAIL**

Run: `cd frontend && npm run test:units`
Expected: `Cannot find module './polygonGeometry.js'` (or similar).

- [ ] **Step 2.4: Implement selfIntersects**

Create `frontend/src/lib/polygonGeometry.js`:

```javascript
/**
 * polygonGeometry — pure geometry helpers for the Phase C-1 polygon editor.
 *
 * Coordinate convention: all functions take {x, y} objects in canvas pixel
 * space (matching takeoffStore polygon points). Pixels-per-meter is applied
 * upstream by takeoffStore.polygonAreaM2.
 */

/**
 * Returns true if any non-adjacent edges of `points` cross each other.
 * Adjacent edges (sharing a vertex) are NOT considered intersecting.
 *
 * @param points {x,y}[] — closed polygon, first ≠ last
 * @returns boolean
 */
export function selfIntersects(points) {
  if (!points || points.length < 4) return false;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const a1 = points[i];
    const a2 = points[(i + 1) % n];
    for (let j = i + 1; j < n; j++) {
      // Skip the edge starting at j if it's adjacent to edge i
      // (shares a vertex). Adjacent = consecutive in either direction
      // including wraparound (last→first vs first→second).
      if (j === i || j === (i + 1) % n || (i === 0 && j === n - 1)) continue;
      const b1 = points[j];
      const b2 = points[(j + 1) % n];
      if (segmentsCross(a1, a2, b1, b2)) return true;
    }
  }
  return false;
}

function segmentsCross(p1, p2, p3, p4) {
  const d1 = direction(p3, p4, p1);
  const d2 = direction(p3, p4, p2);
  const d3 = direction(p1, p2, p3);
  const d4 = direction(p1, p2, p4);
  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
      ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) {
    return true;
  }
  return false;
}

function direction(a, b, c) {
  return (c.x - a.x) * (b.y - a.y) - (b.x - a.x) * (c.y - a.y);
}
```

- [ ] **Step 2.5: Run test, verify PASS**

Run: `cd frontend && npm run test:units`
Expected: 4 tests pass.

- [ ] **Step 2.6: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/lib/polygonGeometry.js frontend/src/lib/polygonGeometry.test.js frontend/package.json
git commit -m "feat(geometry): selfIntersects predicate for polygon validation

Phase C-1 commit guard rejects polygons whose edges cross. Pure function,
node:test runner — no new dev deps."
```

---

### Task 3: orthoSnap()

**Files:**
- Modify: `frontend/src/lib/polygonGeometry.js`
- Modify: `frontend/src/lib/polygonGeometry.test.js`

- [ ] **Step 3.1: Add failing tests**

Append to `polygonGeometry.test.js`:

```javascript
import { orthoSnap } from './polygonGeometry.js';

test('orthoSnap: cursor near horizontal locks to horizontal', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 5 };  // 2.86° from horizontal — within 15° tolerance
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: false, altHeld: false });
  assert.equal(out.y, 0);
  assert.equal(out.x, 100);
});

test('orthoSnap: cursor far from any axis returns cursor unchanged', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 100 };  // 45° — outside tolerance for {0, 90}
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: false, altHeld: false });
  assert.deepEqual(out, cursor);
});

test('orthoSnap: shiftHeld enables 45° increments', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 100 };
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: true, altHeld: false });
  // Should snap to 45° → x ≈ y ≈ 100
  assert.ok(Math.abs(out.x - 100) < 1);
  assert.ok(Math.abs(out.y - 100) < 1);
});

test('orthoSnap: altHeld disables ortho regardless', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 5 };
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: false, altHeld: true });
  assert.deepEqual(out, cursor);
});

test('orthoSnap: orthoEnabled=false passes through', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 5 };
  const out = orthoSnap(prev, cursor, { orthoEnabled: false, shiftHeld: false, altHeld: false });
  assert.deepEqual(out, cursor);
});

test('orthoSnap: vertical lock', () => {
  const prev = { x: 50, y: 0 };
  const cursor = { x: 53, y: 100 };  // ~1.7° from vertical
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: false, altHeld: false });
  assert.equal(out.x, 50);
  assert.equal(out.y, 100);
});
```

- [ ] **Step 3.2: Run, verify FAIL**

Run: `cd frontend && npm run test:units`
Expected: 6 new tests fail with `orthoSnap is not a function`.

- [ ] **Step 3.3: Implement orthoSnap**

Append to `polygonGeometry.js`:

```javascript
const ORTHO_TOLERANCE_DEG = 15;

/**
 * Snap cursor to the nearest of [0°, 90°, 180°, 270°] (or 45° increments
 * when shiftHeld) measured from the previous vertex direction. Returns
 * a new {x, y}; pass-through when ortho disabled, alt held, or cursor
 * is outside tolerance from any snap angle.
 *
 * @param prev {x,y} — last placed vertex (origin of the rubber band)
 * @param cursor {x,y} — current pointer position
 * @param opts {orthoEnabled, shiftHeld, altHeld}
 * @returns {x,y}
 */
export function orthoSnap(prev, cursor, opts) {
  if (!opts.orthoEnabled || opts.altHeld) return cursor;

  const dx = cursor.x - prev.x;
  const dy = cursor.y - prev.y;
  if (dx === 0 && dy === 0) return cursor;

  const angleDeg = Math.atan2(dy, dx) * 180 / Math.PI;
  const snapAngles = opts.shiftHeld
    ? [-180, -135, -90, -45, 0, 45, 90, 135, 180]
    : [-180, -90, 0, 90, 180];

  let nearest = null;
  let nearestDelta = ORTHO_TOLERANCE_DEG;
  for (const a of snapAngles) {
    const d = Math.abs(angleDeg - a);
    if (d < nearestDelta) {
      nearestDelta = d;
      nearest = a;
    }
  }
  if (nearest === null) return cursor;

  const dist = Math.hypot(dx, dy);
  const rad = nearest * Math.PI / 180;
  return {
    x: Math.round(prev.x + dist * Math.cos(rad)),
    y: Math.round(prev.y + dist * Math.sin(rad)),
  };
}
```

- [ ] **Step 3.4: Run, verify PASS**

Run: `cd frontend && npm run test:units`
Expected: all 10 tests pass.

- [ ] **Step 3.5: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/lib/polygonGeometry.js frontend/src/lib/polygonGeometry.test.js
git commit -m "feat(geometry): orthoSnap — 90° default, Shift→45°, Alt disables

Phase C-1 floor-plan-specific snap that eliminates ~80% of crooked-polygon
complaints per Bluebeam UX research."
```

---

### Task 4: pointInPolygon()

**Files:**
- Modify: `frontend/src/lib/polygonGeometry.js`
- Modify: `frontend/src/lib/polygonGeometry.test.js`

- [ ] **Step 4.1: Add failing tests**

Append to `polygonGeometry.test.js`:

```javascript
import { pointInPolygon } from './polygonGeometry.js';

test('pointInPolygon: center of square is inside', () => {
  const sq = [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}];
  assert.equal(pointInPolygon({x:5,y:5}, sq), true);
});

test('pointInPolygon: outside is outside', () => {
  const sq = [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}];
  assert.equal(pointInPolygon({x:15,y:5}, sq), false);
});

test('pointInPolygon: on edge is true (consistent with click-to-select)', () => {
  const sq = [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}];
  // On the right edge — hitting an edge during click-to-select must register
  assert.equal(pointInPolygon({x:10,y:5}, sq), true);
});
```

- [ ] **Step 4.2: Run, verify FAIL**

Run: `cd frontend && npm run test:units`

- [ ] **Step 4.3: Implement pointInPolygon**

Append to `polygonGeometry.js`:

```javascript
/**
 * Ray-casting point-in-polygon. Returns true for points strictly inside
 * AND on edges (so click-to-select-by-body works for clicks on the border).
 */
export function pointInPolygon(p, poly) {
  if (!poly || poly.length < 3) return false;
  // Edge-on test first (cheap)
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    if (pointOnSegment(p, poly[j], poly[i])) return true;
  }
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y;
    const xj = poly[j].x, yj = poly[j].y;
    const intersect = ((yi > p.y) !== (yj > p.y))
      && (p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function pointOnSegment(p, a, b, eps = 1) {
  const cross = (p.y - a.y) * (b.x - a.x) - (p.x - a.x) * (b.y - a.y);
  if (Math.abs(cross) > eps) return false;
  const minX = Math.min(a.x, b.x) - eps;
  const maxX = Math.max(a.x, b.x) + eps;
  const minY = Math.min(a.y, b.y) - eps;
  const maxY = Math.max(a.y, b.y) + eps;
  return p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY;
}
```

- [ ] **Step 4.4: Run, verify PASS**

Run: `cd frontend && npm run test:units`

- [ ] **Step 4.5: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/lib/polygonGeometry.js frontend/src/lib/polygonGeometry.test.js
git commit -m "feat(geometry): pointInPolygon for click-to-select hit testing"
```

---

### Task 5: nearestVertex() — snap-to-vertex of OTHER polygons

**Files:**
- Modify: `frontend/src/lib/polygonGeometry.js`
- Modify: `frontend/src/lib/polygonGeometry.test.js`

The existing `snapToLines` in `takeoffStore.js` snaps to PDF *vector lines* — a different concept. We need a separate function that snaps to vertices of OTHER polygons on the same page (so adjacent rooms share corners cleanly).

- [ ] **Step 5.1: Add failing tests**

Append to `polygonGeometry.test.js`:

```javascript
import { nearestVertex } from './polygonGeometry.js';

test('nearestVertex: snaps to nearest within tolerance', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:5,y:10}] }];
  const result = nearestVertex({x:1,y:1}, polys, 12);
  assert.deepEqual(result.point, {x:0,y:0});
  assert.equal(result.polygonId, 'a');
});

test('nearestVertex: returns null when no vertex within tolerance', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:5,y:10}] }];
  const result = nearestVertex({x:50,y:50}, polys, 12);
  assert.equal(result, null);
});

test('nearestVertex: skips excludePolygonId (so a polygon does not snap to itself)', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:5,y:10}] }];
  const result = nearestVertex({x:1,y:1}, polys, 12, { excludePolygonId: 'a' });
  assert.equal(result, null);
});

test('nearestVertex: returns closest of multiple candidates', () => {
  const polys = [
    { id: 'a', points: [{x:0,y:0},{x:10,y:0}] },
    { id: 'b', points: [{x:5,y:5},{x:15,y:5}] },
  ];
  const result = nearestVertex({x:6,y:5}, polys, 12);
  assert.deepEqual(result.point, {x:5,y:5});
  assert.equal(result.polygonId, 'b');
});
```

- [ ] **Step 5.2: Run, verify FAIL**

Run: `cd frontend && npm run test:units`

- [ ] **Step 5.3: Implement**

Append to `polygonGeometry.js`:

```javascript
/**
 * Find the nearest vertex among polygons within tolerance.
 *
 * @param point {x,y}
 * @param polygons {id, points}[]
 * @param tolerance px
 * @param opts {excludePolygonId?: string} — skip vertices belonging to this polygon
 * @returns {point: {x,y}, polygonId, vertexIndex} | null
 */
export function nearestVertex(point, polygons, tolerance, opts = {}) {
  let best = null;
  let bestDist = tolerance;
  for (const poly of polygons) {
    if (opts.excludePolygonId && poly.id === opts.excludePolygonId) continue;
    for (let i = 0; i < poly.points.length; i++) {
      const v = poly.points[i];
      const d = Math.hypot(v.x - point.x, v.y - point.y);
      if (d < bestDist) {
        bestDist = d;
        best = { point: { x: v.x, y: v.y }, polygonId: poly.id, vertexIndex: i };
      }
    }
  }
  return best;
}
```

- [ ] **Step 5.4: Run, verify PASS**

Run: `cd frontend && npm run test:units`

- [ ] **Step 5.5: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/lib/polygonGeometry.js frontend/src/lib/polygonGeometry.test.js
git commit -m "feat(geometry): nearestVertex for inter-polygon corner snapping

Today's snapToLines covers PDF vector lines but not adjacent polygons.
Adjacent rooms must share corners cleanly to avoid double-counting walls."
```

---

### Task 6: nearestEdge() — snap-to-edge of OTHER polygons

**Files:**
- Modify: `frontend/src/lib/polygonGeometry.js`
- Modify: `frontend/src/lib/polygonGeometry.test.js`

- [ ] **Step 6.1: Add failing tests**

Append to `polygonGeometry.test.js`:

```javascript
import { nearestEdge } from './polygonGeometry.js';

test('nearestEdge: snaps to perpendicular foot on edge', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}] }];
  // Cursor at (5, 2) — perpendicular foot on the bottom edge is (5, 0)
  const result = nearestEdge({x:5,y:2}, polys, 8);
  assert.deepEqual(result.point, {x:5,y:0});
  assert.equal(result.polygonId, 'a');
  assert.equal(result.edgeIndex, 0);
});

test('nearestEdge: returns null beyond tolerance', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}] }];
  const result = nearestEdge({x:50,y:50}, polys, 8);
  assert.equal(result, null);
});

test('nearestEdge: skips edges of excludePolygonId', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}] }];
  const result = nearestEdge({x:5,y:2}, polys, 8, { excludePolygonId: 'a' });
  assert.equal(result, null);
});
```

- [ ] **Step 6.2: Run, verify FAIL**

Run: `cd frontend && npm run test:units`

- [ ] **Step 6.3: Implement**

Append to `polygonGeometry.js`:

```javascript
/**
 * Find the nearest perpendicular-foot on any polygon edge within tolerance.
 *
 * @returns {point, polygonId, edgeIndex} | null
 */
export function nearestEdge(point, polygons, tolerance, opts = {}) {
  let best = null;
  let bestDist = tolerance;
  for (const poly of polygons) {
    if (opts.excludePolygonId && poly.id === opts.excludePolygonId) continue;
    const n = poly.points.length;
    for (let i = 0; i < n; i++) {
      const a = poly.points[i];
      const b = poly.points[(i + 1) % n];
      const foot = perpFoot(point, a, b);
      if (!foot) continue;
      const d = Math.hypot(foot.x - point.x, foot.y - point.y);
      if (d < bestDist) {
        bestDist = d;
        best = { point: foot, polygonId: poly.id, edgeIndex: i };
      }
    }
  }
  return best;
}

function perpFoot(p, a, b) {
  const dx = b.x - a.x, dy = b.y - a.y;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) return null;
  const t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq;
  if (t < 0 || t > 1) return null;  // foot is outside segment
  return { x: a.x + t * dx, y: a.y + t * dy };
}
```

- [ ] **Step 6.4: Run, verify PASS**

Run: `cd frontend && npm run test:units`

- [ ] **Step 6.5: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/lib/polygonGeometry.js frontend/src/lib/polygonGeometry.test.js
git commit -m "feat(geometry): nearestEdge for inter-polygon edge snapping

Edge snap is the second-priority snap target after vertex (per UX spec)."
```

---

### Task 7: polygonCentroid()

**Files:**
- Modify: `frontend/src/lib/polygonGeometry.js`
- Modify: `frontend/src/lib/polygonGeometry.test.js`

Used for label placement and as fallback when `centroid_pct` is missing.

- [ ] **Step 7.1: Add failing tests**

Append:

```javascript
import { polygonCentroid } from './polygonGeometry.js';

test('polygonCentroid: square center is at 5,5', () => {
  const sq = [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}];
  const c = polygonCentroid(sq);
  assert.ok(Math.abs(c.x - 5) < 0.001);
  assert.ok(Math.abs(c.y - 5) < 0.001);
});

test('polygonCentroid: degenerate polygon (< 3 pts) returns null', () => {
  assert.equal(polygonCentroid([{x:0,y:0},{x:1,y:1}]), null);
});
```

- [ ] **Step 7.2: Run, verify FAIL**

Run: `cd frontend && npm run test:units`

- [ ] **Step 7.3: Implement**

```javascript
/**
 * Area-weighted centroid (correct for non-convex polygons).
 * Returns null for degenerate input.
 */
export function polygonCentroid(points) {
  if (!points || points.length < 3) return null;
  let cx = 0, cy = 0, areaSum = 0;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const p1 = points[i];
    const p2 = points[(i + 1) % n];
    const f = p1.x * p2.y - p2.x * p1.y;
    cx += (p1.x + p2.x) * f;
    cy += (p1.y + p2.y) * f;
    areaSum += f;
  }
  if (areaSum === 0) return null;
  const a = areaSum / 2;
  return { x: cx / (6 * a), y: cy / (6 * a) };
}
```

- [ ] **Step 7.4: Run, verify PASS**

Run: `cd frontend && npm run test:units`

- [ ] **Step 7.5: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/lib/polygonGeometry.js frontend/src/lib/polygonGeometry.test.js
git commit -m "feat(geometry): polygonCentroid for label placement"
```

---

## Phase B: Trace mode improvements

### Task 8: Esc cancels mid-trace

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — add window keydown listener gated on `tool === 'polygon'`

- [ ] **Step 8.1: Add the keydown handler**

In `PdfViewer.jsx`, near the other useEffects (after the polygon tool init around line 1280):

```javascript
useEffect(() => {
  if (tool !== 'polygon') return;
  const onKey = (e) => {
    if (e.key === 'Escape') {
      if (polygonDraft) {
        setPolygonDraft(null);
        toast?.('Atšaukta', { duration: 1500 });
      }
    }
  };
  window.addEventListener('keydown', onKey);
  return () => window.removeEventListener('keydown', onKey);
}, [tool, polygonDraft]);
```

If `toast` isn't already imported in PdfViewer.jsx (check existing imports), use `import { toast } from 'react-hot-toast';` — already in deps.

- [ ] **Step 8.2: Manual smoke test**

Run: `cd frontend && npm run dev`
Open a project → Brėžinys tab → click "Polygon" tool (or press P). Click 2-3 vertices. Press Esc.
Expected: in-progress polygon disappears, no console errors, "Atšaukta" toast briefly visible.

- [ ] **Step 8.3: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): Esc cancels mid-trace

Universal expectation; never commits on Esc per UX research §3.3."
```

---

### Task 9: Backspace removes last vertex during trace

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — extend the keydown handler from Task 8

- [ ] **Step 9.1: Extend the keydown handler**

In the `onKey` from Task 8, add:

```javascript
if (e.key === 'Backspace' || e.key === 'Delete') {
  if (polygonDraft && polygonDraft.points.length > 0) {
    e.preventDefault();
    setPolygonDraft({
      ...polygonDraft,
      points: polygonDraft.points.slice(0, -1),
    });
  }
}
```

Place this OUTSIDE any input-focus check (estimators expect Backspace to undo while drawing, not navigate browser history — `e.preventDefault()` blocks the back-nav).

- [ ] **Step 9.2: Manual smoke test**

Run: `cd frontend && npm run dev`
Trace: click 4 vertices. Press Backspace.
Expected: last vertex disappears; rubber band updates from 3rd vertex. Press again — 3rd disappears. Continue until 0 — drafted polygon is `{ points: [] }` and rubber band shows nothing.

- [ ] **Step 9.3: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): Backspace removes last vertex during trace

Distinguishes vertex-undo (Backspace) from operation-undo (Ctrl+Z) per
PlanSwift convention."
```

---

### Task 10: Enter closes polygon

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — extend the keydown handler

- [ ] **Step 10.1: Extend the keydown handler**

In `onKey`, add (after the Backspace branch):

```javascript
if (e.key === 'Enter') {
  if (polygonDraft && polygonDraft.points.length >= 3) {
    e.preventDefault();
    onFinalizePolygon();   // existing handler in PdfViewer
  } else if (polygonDraft) {
    toast?.('Polygonui reikia mažiausiai 3 taškų', { duration: 2000 });
  }
}
```

`onFinalizePolygon` already exists — search the file for the existing handler (around line 1310-1330 area). Re-use it; do not duplicate the close logic.

- [ ] **Step 10.2: Manual smoke test**

Run dev. Trace 3 vertices. Press Enter. Expected: polygon closes, modal opens (existing flow). Trace 1 vertex, press Enter — toast warns minimum 3 needed.

- [ ] **Step 10.3: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): Enter closes polygon (third close-method per UX spec)"
```

---

### Task 11: Ortho-90° rubber band, default ON, Shift→45°, Alt disables

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — wire `orthoSnap` into the rubber-band cursor calc inside `MarkupCanvas.handleMouseMove` and into `handleMouseDown` for vertex placement

- [ ] **Step 11.1: Add ortho state to PdfViewer top-level**

Near other useState (around line 1290):

```javascript
// Phase C-1: ortho-90° default on for floor plans (per UX research).
// Toggle via F8 (AutoCAD convention); Alt-while-moving disables temporarily.
const [orthoEnabled, setOrthoEnabled] = useState(true);
const modKeysRef = useRef({ shift: false, alt: false });
```

- [ ] **Step 11.2: Track shift/alt globally**

Add a useEffect (next to the other key handlers):

```javascript
useEffect(() => {
  const onKD = (e) => {
    if (e.key === 'Shift') modKeysRef.current.shift = true;
    if (e.key === 'Alt')   modKeysRef.current.alt = true;
    if (e.key === 'F8')    { e.preventDefault(); setOrthoEnabled(v => !v); }
  };
  const onKU = (e) => {
    if (e.key === 'Shift') modKeysRef.current.shift = false;
    if (e.key === 'Alt')   modKeysRef.current.alt = false;
  };
  window.addEventListener('keydown', onKD);
  window.addEventListener('keyup', onKU);
  return () => {
    window.removeEventListener('keydown', onKD);
    window.removeEventListener('keyup', onKU);
  };
}, []);
```

- [ ] **Step 11.3: Pass ortho state into MarkupCanvas**

Find the `<MarkupCanvas ... />` JSX in PdfViewer (around line 1500-1600) and add props:

```jsx
<MarkupCanvas
  // ... existing props
  orthoEnabled={orthoEnabled}
  modKeysRef={modKeysRef}
/>
```

Then in the `MarkupCanvas` component signature, accept the props:

```javascript
function MarkupCanvas({
  // ... existing
  orthoEnabled,
  modKeysRef,
}) {
```

- [ ] **Step 11.4: Apply orthoSnap inside handleMouseMove and handleMouseDown**

Add at the top of `MarkupCanvas`:

```javascript
import { orthoSnap } from '@/lib/polygonGeometry';
```

Inside `handleMouseDown` (around line 811), replace the `if (tool === 'polygon')` block's `points: [...points, { x: snapped.x, y: snapped.y }]` with ortho-applied placement:

```javascript
if (tool === 'polygon') {
  let candidate = snapPoint(pos);
  // Ortho applies AFTER vector-line snap; if snap engaged, ortho is bypassed
  // (snap wins — user explicitly hit a wall point).
  if (!candidate.snapped && polygonDraft && polygonDraft.points.length > 0) {
    const prev = polygonDraft.points[polygonDraft.points.length - 1];
    candidate = orthoSnap(prev, candidate, {
      orthoEnabled,
      shiftHeld: modKeysRef.current.shift,
      altHeld: modKeysRef.current.alt,
    });
  }
  // existing close-on-first-vertex check uses `candidate`
  if (polygonDraft && polygonDraft.points.length >= 3) {
    const first = polygonDraft.points[0];
    const dist = Math.sqrt((candidate.x - first.x)**2 + (candidate.y - first.y)**2);
    if (dist < 12) {  // bumped from 10 to match UX spec 12px tolerance
      onFinalizePolygon();
      return;
    }
  }
  const points = polygonDraft ? polygonDraft.points : [];
  onPolygonDraftChange({ points: [...points, { x: candidate.x, y: candidate.y }] });
  return;
}
```

Then in `handleMouseMove`, apply same ortho to `setHoverPos`:

```javascript
const handleMouseMove = (e) => {
  const rawPos = e.target.getStage().getPointerPosition();
  let pos = rawPos;
  if (tool === 'polygon') {
    pos = snapPoint(rawPos);
    if (!pos.snapped && polygonDraft && polygonDraft.points.length > 0) {
      const prev = polygonDraft.points[polygonDraft.points.length - 1];
      pos = orthoSnap(prev, pos, {
        orthoEnabled,
        shiftHeld: modKeysRef.current.shift,
        altHeld: modKeysRef.current.alt,
      });
    }
  }
  setHoverPos(pos);
  // ... rest unchanged (drawing rect logic etc.)
};
```

- [ ] **Step 11.5: Manual smoke test**

Run dev. Trace mode. Click somewhere. Move cursor close to horizontal — rubber band should LOCK to horizontal (cursor jumps to same y as previous vertex). Move 45° — no lock. Hold Shift — 45° also locks. Hold Alt — no lock at any angle. Press F8 — ortho indicator off (rubber band always free). Press F8 again — back on.

- [ ] **Step 11.6: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): ortho-90° default ON, Shift→45°, Alt disables, F8 toggles

Floor plans are overwhelmingly axis-aligned; this single behavior eliminates
~80% of crooked-polygon complaints per UX research §3.8."
```

---

### Task 12: Self-intersection rejection on commit

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — guard inside `onFinalizePolygon`

- [ ] **Step 12.1: Find the existing finalize handler**

Run: `cd frontend && grep -n "onFinalizePolygon\|setPendingPolygon" src/components/project/PdfViewer.jsx`
Note the line where the polygon is committed to `pendingPolygon` for the modal.

- [ ] **Step 12.2: Add self-intersection guard**

At the top of the finalize handler:

```javascript
import { selfIntersects } from '@/lib/polygonGeometry';

// inside onFinalizePolygon, BEFORE setting pendingPolygon:
if (polygonDraft && polygonDraft.points.length >= 3) {
  if (selfIntersects(polygonDraft.points)) {
    toast.error('Polygonas susikerta — pataisykite linijas', { duration: 3000 });
    return;
  }
  setPendingPolygon(polygonDraft);
  setPolygonDraft(null);
}
```

- [ ] **Step 12.3: Manual smoke test**

Run dev. Trace a deliberate bowtie (4 vertices in zig-zag order). Press Enter or click first vertex.
Expected: error toast in Lithuanian; polygonDraft remains active so user can fix it (Backspace to remove the bad vertex). Toast says "Polygonas susikerta — pataisykite linijas".

- [ ] **Step 12.4: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): reject self-intersecting polygons on commit

Self-intersecting polygons silently break shoelace area calc; reject with
Lithuanian error toast per UX research §9 anti-pattern #12."
```

---

### Task 13: First-time hint overlay

**Files:**
- Create: `frontend/src/components/project/FirstTimePolygonHint.jsx`
- Modify: `frontend/src/components/project/PdfViewer.jsx` — mount when entering trace mode for the first time

- [ ] **Step 13.1: Create the component**

`frontend/src/components/project/FirstTimePolygonHint.jsx`:

```javascript
import { useEffect, useState } from 'react';

const STORAGE_KEY = 'samatu_polygon_hint_seen';

export default function FirstTimePolygonHint({ active, onDismiss }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!active) { setVisible(false); return; }
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') return;
    } catch { return; }
    setVisible(true);
  }, [active]);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch {}
    setVisible(false);
    onDismiss?.();
  };

  if (!visible) return null;
  return (
    <div
      className="absolute top-4 left-1/2 -translate-x-1/2 z-50 max-w-md"
      onClick={dismiss}
      style={{
        background: 'rgba(15, 23, 42, 0.95)',
        color: '#e2e8f0',
        borderRadius: 8,
        padding: '12px 16px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
        cursor: 'pointer',
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
        Apveskite kambarį spustelėdami kampus
      </div>
      <div style={{ fontSize: 11, lineHeight: 1.5, opacity: 0.85 }}>
        <strong>Enter</strong> arba dvigubas paspaudimas — užbaigti<br/>
        <strong>Esc</strong> — atšaukti  ·  <strong>Backspace</strong> — pašalinti paskutinį tašką<br/>
        <strong>Shift</strong> — laisva kryptis  ·  <strong>Alt</strong> — laikinas snap'o išjungimas
      </div>
    </div>
  );
}
```

- [ ] **Step 13.2: Mount in PdfViewer**

In the JSX where the workspace renders (inside the `<Document>` page area), add:

```jsx
<FirstTimePolygonHint active={tool === 'polygon'} />
```

Also add the import at the top.

- [ ] **Step 13.3: Manual smoke test**

Clear localStorage key: in dev console run `localStorage.removeItem('samatu_polygon_hint_seen')`. Reload. Click Polygon tool.
Expected: hint appears. Click hint → dismisses. Click Polygon tool again → hint does NOT reappear (sticky).

- [ ] **Step 13.4: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/FirstTimePolygonHint.jsx frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): one-time hint overlay on first trace mode entry"
```

---

## Phase C: Edit-after-commit (PolygonEditor sub-component)

### Task 14: PolygonEditor scaffold + listening:false split

**Files:**
- Create: `frontend/src/components/project/PolygonEditor.jsx`
- Modify: `frontend/src/components/project/PdfViewer.jsx` — separate committed-polygons (listening:false) from active-edit (listening:true) layers

This is the largest task in the plan. The existing `MarkupCanvas` renders polygons inline; we extract editing into `PolygonEditor` and split into two Konva layers per the libraries-research perf guidance.

- [ ] **Step 14.1: Create the component skeleton**

`frontend/src/components/project/PolygonEditor.jsx`:

```javascript
/**
 * PolygonEditor — active-edit Konva sub-tree for the Phase C-1 polygon tool.
 *
 * Renders ON TOP of committed polygons. Only the polygon currently
 * `selectedId` is editable here; everything else lives on a non-listening
 * layer in MarkupCanvas for perf.
 *
 * Imperative drag pattern: vertex circles use refs + .position() during
 * drag, commit to React state on dragend (5-10x faster than re-render
 * on every mousemove per Konva perf guide).
 */

import { useRef, useState, useMemo } from 'react';
import { Group, Circle, Line, Rect } from 'react-konva';
import { nearestVertex, nearestEdge } from '@/lib/polygonGeometry';

const VERTEX_R = 6;
const VERTEX_HIT_R = 12;
const GHOST_R = 4;

export default function PolygonEditor({
  polygon,             // {id, points, ...} — the currently selected polygon
  allPolygons,         // {id, points}[] for snap targets
  pageNumber,
  selectedVertexIndices = [],
  onVerticesUpdate,    // (newPoints, opLog) => void
  onVertexInsert,      // (index, vertex) => void
  onVertexDelete,      // (index) => void
  onSelectVertex,      // (index, multi) => void
  modKeysRef,          // {shift, alt}
  snapEnabled = true,
  snapTolerance = 12,
}) {
  if (!polygon) return null;

  const pts = polygon.points;

  return (
    <Group>
      {/* Edges first so vertex hit-areas are on top */}
      {pts.map((_, i) => {
        const a = pts[i];
        const b = pts[(i + 1) % pts.length];
        const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
        return (
          <Group key={`mid-${i}`}>
            {/* Midpoint ghost — Google Maps pattern */}
            <Circle
              x={mid.x} y={mid.y} radius={GHOST_R}
              fill="#00B8D9" opacity={0.35}
              onMouseDown={(e) => {
                e.cancelBubble = true;
                onVertexInsert(i + 1, mid);
              }}
              onMouseEnter={(e) => { e.target.opacity(0.85); e.target.getLayer().batchDraw(); }}
              onMouseLeave={(e) => { e.target.opacity(0.35); e.target.getLayer().batchDraw(); }}
            />
          </Group>
        );
      })}

      {/* Vertex handles */}
      {pts.map((p, i) => (
        <VertexHandle
          key={`v-${i}`}
          point={p}
          index={i}
          isSelected={selectedVertexIndices.includes(i)}
          allPolygons={allPolygons}
          excludePolygonId={polygon.id}
          modKeysRef={modKeysRef}
          snapEnabled={snapEnabled}
          snapTolerance={snapTolerance}
          onSelect={onSelectVertex}
          onDragEnd={(newPoint) => {
            const newPts = pts.map((q, j) => j === i ? newPoint : q);
            onVerticesUpdate(newPts, {
              type: 'move-vertex',
              polygonId: polygon.id, index: i,
              from: p, to: newPoint,
            });
          }}
        />
      ))}
    </Group>
  );
}

function VertexHandle({
  point, index, isSelected, allPolygons, excludePolygonId,
  modKeysRef, snapEnabled, snapTolerance,
  onSelect, onDragEnd,
}) {
  const ref = useRef(null);

  return (
    <>
      {/* Visible vertex */}
      <Circle
        x={point.x} y={point.y} radius={VERTEX_R}
        fill={isSelected ? '#00B8D9' : '#ffffff'}
        stroke="#00B8D9" strokeWidth={1.5}
        listening={false}
      />
      {/* Hit area (transparent, larger) */}
      <Circle
        ref={ref}
        x={point.x} y={point.y} radius={VERTEX_HIT_R}
        fill="rgba(0,0,0,0.001)"  // hit-graph requires non-zero alpha
        draggable
        onMouseDown={(e) => {
          e.cancelBubble = true;
          onSelect(index, modKeysRef.current.shift);
        }}
        onDragMove={(e) => {
          if (!snapEnabled || modKeysRef.current.alt) return;
          const pos = { x: e.target.x(), y: e.target.y() };
          const v = nearestVertex(pos, allPolygons, snapTolerance, { excludePolygonId });
          if (v) {
            e.target.position(v.point);
            return;
          }
          const ed = nearestEdge(pos, allPolygons, Math.round(snapTolerance * 0.66), { excludePolygonId });
          if (ed) e.target.position(ed.point);
        }}
        onDragEnd={(e) => {
          onDragEnd({ x: e.target.x(), y: e.target.y() });
        }}
      />
    </>
  );
}
```

- [ ] **Step 14.2: Wire selectedPolygonId state into PdfViewer**

In `PdfViewer.jsx` near the polygon state:

```javascript
const [selectedPolygonId, setSelectedPolygonId] = useState(null);
const [selectedVertexIndices, setSelectedVertexIndices] = useState([]);
```

- [ ] **Step 14.3: Mount PolygonEditor in MarkupCanvas with split layers**

Inside `MarkupCanvas`, find the `<Layer>` block that currently renders both committed polygons and the in-progress draft. Split it:

```jsx
<Stage ...>
  {/* Layer 1: committed polygons — listening:false for perf */}
  <Layer listening={false} transformsEnabled="position">
    {pagePolygons.filter(p => p.id !== selectedPolygonId).map(poly => (
      <Line
        key={poly.id}
        points={poly.points.flatMap(pt => [pt.x, pt.y])}
        closed
        fill="rgba(0, 184, 217, 0.12)"
        stroke="#00B8D9" strokeWidth={2} opacity={0.7}
        perfectDrawEnabled={false}
        shadowForStrokeEnabled={false}
      />
    ))}
  </Layer>

  {/* Layer 2: active edit (selected polygon body + handles + in-progress trace) */}
  <Layer listening={true}>
    {selectedPolygon && (
      <Line
        points={selectedPolygon.points.flatMap(pt => [pt.x, pt.y])}
        closed
        fill="rgba(0, 184, 217, 0.18)"
        stroke="#00B8D9" strokeWidth={3}
        onClick={() => {/* keep selected */}}
      />
    )}
    {selectedPolygon && (
      <PolygonEditor
        polygon={selectedPolygon}
        allPolygons={pagePolygons}
        pageNumber={page}
        selectedVertexIndices={selectedVertexIndices}
        onVerticesUpdate={(newPts, op) => onPolygonVerticesUpdate(selectedPolygon.id, newPts, op)}
        onVertexInsert={(i, v) => onPolygonVertexInsert(selectedPolygon.id, i, v)}
        onVertexDelete={(i) => onPolygonVertexDelete(selectedPolygon.id, i)}
        onSelectVertex={(i, multi) => setSelectedVertexIndices(multi ? [...selectedVertexIndices, i] : [i])}
        modKeysRef={modKeysRef}
      />
    )}
    {/* existing in-progress draft rendering, unchanged */}
  </Layer>
</Stage>
```

Define `selectedPolygon` from `pagePolygons.find(p => p.id === selectedPolygonId)` near the top of `MarkupCanvas`.

- [ ] **Step 14.4: Click polygon body → select**

Add to the committed-polygons rendering — wait, `listening:false` means we can't click. Move the click handlers to a thin invisible "select layer". Add a third layer between:

```jsx
{/* Layer 1.5: invisible select-targets — small listening area for un-selected polys */}
<Layer listening={true}>
  {pagePolygons.filter(p => p.id !== selectedPolygonId).map(poly => (
    <Line
      key={poly.id + '-hit'}
      points={poly.points.flatMap(pt => [pt.x, pt.y])}
      closed
      fill="rgba(0,0,0,0.001)"
      stroke="rgba(0,0,0,0)" strokeWidth={6}
      listening={true}
      onClick={() => {
        if (tool === 'select' || tool === null) {
          setSelectedPolygonId(poly.id);
          setSelectedVertexIndices([]);
        }
      }}
    />
  ))}
</Layer>
```

This keeps draw-paint on Layer 1 (cheap) and pure hit-testing on Layer 1.5 (cheap fills).

- [ ] **Step 14.5: Add the polygon CRUD callbacks in PdfViewer**

```javascript
const onPolygonVerticesUpdate = (polygonId, newPoints, op) => {
  setTakeoff(t => updatePolygon(t, polygonId, { points: newPoints }, op));
};
const onPolygonVertexInsert = (polygonId, index, vertex) => {
  setTakeoff(t => {
    const poly = t.polygons.find(p => p.id === polygonId);
    if (!poly) return t;
    const newPoints = [...poly.points.slice(0, index), vertex, ...poly.points.slice(index)];
    return updatePolygon(t, polygonId, { points: newPoints }, {
      type: 'insert-vertex', polygonId, index, vertex,
    });
  });
};
const onPolygonVertexDelete = (polygonId, index) => {
  setTakeoff(t => {
    const poly = t.polygons.find(p => p.id === polygonId);
    if (!poly || poly.points.length <= 3) {
      toast?.('Polygonui reikia mažiausiai 3 taškų', { duration: 2000 });
      return t;
    }
    const newPoints = poly.points.filter((_, i) => i !== index);
    return updatePolygon(t, polygonId, { points: newPoints }, {
      type: 'delete-vertex', polygonId, index, vertex: poly.points[index],
    });
  });
};
```

- [ ] **Step 14.6: Manual smoke test**

Run dev. Trace a polygon, finalize. Click another polygon (or the same body) — vertex circles appear. Drag a vertex — polygon updates after release. Hover an edge — ghost circle visible at midpoint. Click ghost — new vertex inserted at midpoint, polygon now has N+1 vertices.

- [ ] **Step 14.7: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PolygonEditor.jsx frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): vertex drag + midpoint ghosts + listening:false perf split

Active-edit Konva sub-component with imperative drag (.position() during,
commit on dragend) per Phase C library research."
```

---

### Task 15: Snap-to-vertex/edge of OTHER polygons during drag

Already implemented as part of Task 14's `VertexHandle.onDragMove` — verify it works.

**Files:**
- (Verification only; no new files)

- [ ] **Step 15.1: Manual smoke test for inter-polygon vertex snap**

Run dev. Trace 2 adjacent polygons sharing an approximate corner (don't snap during trace yet — just rough). Select one polygon. Drag the corner near the OTHER polygon's corner.
Expected: cursor jumps onto the other polygon's exact vertex when within 12 px (cyan glow optional in Task 18). Drop — vertex now exactly coincident with neighbor.

- [ ] **Step 15.2: Manual smoke test for inter-polygon edge snap**

Drag a vertex near the middle of another polygon's edge (not near a vertex).
Expected: cursor jumps to perpendicular foot on that edge within 8 px. Drop.

- [ ] **Step 15.3: Manual smoke test for Alt override**

Drag a vertex near another polygon's corner while holding Alt.
Expected: NO snap; vertex moves freely.

- [ ] **Step 15.4: Commit (no code changes — verification only)**

```bash
# No commit; this is a verification gate before Task 16.
```

---

### Task 16: Multi-select vertices via Shift+click; drag-together

**Files:**
- Modify: `frontend/src/components/project/PolygonEditor.jsx` — extend drag to move all selected vertices by same offset

- [ ] **Step 16.1: Update VertexHandle drag to handle multi**

Replace `VertexHandle.onDragMove` and `onDragEnd` with offset-aware versions:

```javascript
function VertexHandle({
  point, index, isSelected, polygonPoints, selectedIndices,
  // ... rest
  onDragEndAll,   // (offset: {dx, dy}) => void
}) {
  const startRef = useRef(null);
  const isMulti = isSelected && selectedIndices.length > 1;

  return (
    <>
      <Circle x={point.x} y={point.y} radius={VERTEX_R}
        fill={isSelected ? '#00B8D9' : '#ffffff'}
        stroke="#00B8D9" strokeWidth={1.5} listening={false} />
      <Circle
        ref={ref}
        x={point.x} y={point.y} radius={VERTEX_HIT_R}
        fill="rgba(0,0,0,0.001)"
        draggable
        onDragStart={(e) => {
          startRef.current = { x: point.x, y: point.y };
        }}
        onMouseDown={(e) => {
          e.cancelBubble = true;
          onSelect(index, modKeysRef.current.shift);
        }}
        onDragMove={(e) => {
          // snap as before
        }}
        onDragEnd={(e) => {
          const newPos = { x: e.target.x(), y: e.target.y() };
          if (isMulti) {
            const dx = newPos.x - startRef.current.x;
            const dy = newPos.y - startRef.current.y;
            onDragEndAll({ dx, dy });
          } else {
            onDragEnd(newPos);
          }
        }}
      />
    </>
  );
}
```

- [ ] **Step 16.2: Add the onDragEndAll prop in PolygonEditor**

```javascript
onDragEndAll={(offset) => {
  const newPts = polygon.points.map((p, j) =>
    selectedVertexIndices.includes(j)
      ? { x: p.x + offset.dx, y: p.y + offset.dy }
      : p
  );
  onVerticesUpdate(newPts, {
    type: 'move-vertices-batch',
    polygonId: polygon.id,
    indices: [...selectedVertexIndices],
    offset,
  });
}}
```

- [ ] **Step 16.3: Manual smoke test**

Run dev. Select a polygon. Click vertex 1 (becomes cyan-filled). Shift-click vertex 3 (also cyan-filled). Drag vertex 1.
Expected: BOTH vertices move together preserving offset. Drop — polygon updates with both moved.

- [ ] **Step 16.4: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PolygonEditor.jsx
git commit -m "feat(polygon): multi-select vertices via Shift+click; drag together

Per UX research §3.7 — frequent use case is fixing AI polygon offset by
grabbing all corners and shifting together."
```

---

### Task 17: Delete key removes selected vertex(es)

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — extend keydown for Delete

- [ ] **Step 17.1: Extend keydown handler from Tasks 8-10**

In the same `onKey` (gated on `tool === 'polygon' || tool === 'select'`):

```javascript
if ((e.key === 'Delete' || e.key === 'Backspace') && tool === 'select') {
  if (selectedPolygonId && selectedVertexIndices.length > 0) {
    e.preventDefault();
    // Delete vertices in descending index order so earlier indices stay valid
    const sortedDesc = [...selectedVertexIndices].sort((a, b) => b - a);
    setTakeoff(t => {
      let nt = t;
      const poly = nt.polygons.find(p => p.id === selectedPolygonId);
      if (!poly || poly.points.length - sortedDesc.length < 3) {
        toast?.('Polygonui reikia mažiausiai 3 taškų', { duration: 2000 });
        return t;
      }
      const newPoints = poly.points.filter((_, i) => !sortedDesc.includes(i));
      nt = updatePolygon(nt, selectedPolygonId, { points: newPoints }, {
        type: 'delete-vertices', polygonId: selectedPolygonId, indices: sortedDesc,
      });
      return nt;
    });
    setSelectedVertexIndices([]);
  } else if (selectedPolygonId) {
    // No vertex selected, delete the whole polygon
    e.preventDefault();
    setTakeoff(t => removePolygon(t, selectedPolygonId));
    setSelectedPolygonId(null);
  }
}
```

- [ ] **Step 17.2: Manual smoke test**

Run dev. Select polygon → click 1 vertex → Delete. Vertex removed (or rejected if min 3 reached). Select polygon → click vertex 1, Shift-click vertex 2 → Delete. Both vertices removed (rejected if it would leave < 3). Click polygon body (no vertex selected) → Delete. Whole polygon removed.

- [ ] **Step 17.3: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): Delete key removes vertex(es) or polygon

Polygon-vs-vertex resolved by what's selected (PlanSwift convention)."
```

---

### Task 18: Snap visual indicator (cyan halo + Lithuanian label)

**Files:**
- Modify: `frontend/src/components/project/PolygonEditor.jsx` — render an `<SnapIndicator>` shape when drag is snapping

- [ ] **Step 18.1: Add snap state and render**

Inside `VertexHandle`:

```javascript
const [snapTarget, setSnapTarget] = useState(null);

// onDragMove:
onDragMove={(e) => {
  if (!snapEnabled || modKeysRef.current.alt) {
    setSnapTarget(null);
    return;
  }
  const pos = { x: e.target.x(), y: e.target.y() };
  const v = nearestVertex(pos, allPolygons, snapTolerance, { excludePolygonId });
  if (v) {
    e.target.position(v.point);
    setSnapTarget({ ...v.point, type: 'vertex', label: 'kampas' });
    return;
  }
  const ed = nearestEdge(pos, allPolygons, Math.round(snapTolerance * 0.66), { excludePolygonId });
  if (ed) {
    e.target.position(ed.point);
    setSnapTarget({ ...ed.point, type: 'edge', label: 'kraštas' });
    return;
  }
  setSnapTarget(null);
}}

// onDragEnd:
onDragEnd={(e) => {
  setSnapTarget(null);
  // ... existing
}}
```

Then add to the JSX (sibling of the hit Circle):

```jsx
{snapTarget && (
  <Group listening={false}>
    <Circle x={snapTarget.x} y={snapTarget.y} radius={10}
      stroke="#00B8D9" strokeWidth={2} opacity={0.6} />
    <Rect x={snapTarget.x + 12} y={snapTarget.y - 22}
      width={56} height={18} fill="rgba(15,23,42,0.85)" cornerRadius={3} />
    <KonvaText x={snapTarget.x + 16} y={snapTarget.y - 20}
      text={snapTarget.label} fontSize={11} fill="#e2e8f0" />
  </Group>
)}
```

(Add `Text as KonvaText` to the `react-konva` imports at the top of the file if not already.)

- [ ] **Step 18.2: Manual smoke test**

Drag a vertex near another polygon's corner.
Expected: cursor snaps; cyan ring + "kampas" label appears next to cursor. Drag toward edge → label changes to "kraštas". Hold Alt → labels disappear, no snap.

- [ ] **Step 18.3: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PolygonEditor.jsx
git commit -m "feat(polygon): cyan halo + Lithuanian snap-type label during drag

Without active-snap feedback users disable snap and double-place vertices."
```

---

## Phase D: Operation undo/redo + room association

### Task 19: Wire Ctrl+Z / Ctrl+Shift+Z to existing undo/redo

The takeoffStore already has `undo(takeoff)` and `redo(takeoff)`. Hook them up.

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — extend keydown

- [ ] **Step 19.1: Extend keydown handler**

```javascript
import { undo, redo, canUndo, canRedo } from '@/lib/takeoffStore';

// inside onKey:
const isMod = e.metaKey || e.ctrlKey;
if (isMod && (e.key === 'z' || e.key === 'Z')) {
  e.preventDefault();
  if (e.shiftKey) {
    if (canRedo(takeoff)) setTakeoff(redo(takeoff));
  } else {
    if (canUndo(takeoff)) setTakeoff(undo(takeoff));
  }
}
```

- [ ] **Step 19.2: Verify takeoffStore.undo handles 'move-vertex' / 'insert-vertex' / 'delete-vertex' / 'delete-vertices'**

Run: `grep -n "type ===" /Users/ignasgaldikas/samatu-ai/frontend/src/lib/takeoffStore.js`
Expected: branches for `add_polygon`, `remove_polygon`, `update_polygon`. The new op types from Tasks 14-17 (`move-vertex`, `insert-vertex`, `delete-vertex`, `delete-vertices`, `move-vertices-batch`) all funnel through `update_polygon` because they all call `updatePolygon(takeoff, id, {points: newPoints}, op)`. Confirm `updatePolygon` records before/after points for inverse:

```javascript
// Open takeoffStore.js around line 162. Verify it captures `before` and `after` snapshots:
export function updatePolygon(takeoff, polygonId, updates, opMeta) {
  const before = takeoff.polygons.find(p => p.id === polygonId);
  if (!before) return takeoff;
  const after = { ...before, ...updates };
  return {
    ...takeoff,
    polygons: takeoff.polygons.map(p => p.id === polygonId ? after : p),
    actionStack: pushAction(takeoff, {
      type: 'update_polygon',
      payload: { polygonId, before, after, op: opMeta },
    }),
    redoStack: [],   // any new action invalidates redo
  };
}
```

If `redoStack: []` clearing isn't already there, add it (otherwise undo→edit→redo replays a stale future).

- [ ] **Step 19.3: Manual smoke test**

Trace polygon. Drag a vertex. Ctrl+Z → vertex restored. Ctrl+Z → polygon disappears. Ctrl+Shift+Z → polygon back. Ctrl+Shift+Z → vertex moved again. Edit again — redo stack cleared (next Ctrl+Shift+Z does nothing).

- [ ] **Step 19.4: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PdfViewer.jsx frontend/src/lib/takeoffStore.js
git commit -m "feat(polygon): Ctrl+Z / Ctrl+Shift+Z operation-level undo/redo

Wire keyboard to existing takeoffStore undo/redo; clear redo stack on
new actions to prevent stale-future replay."
```

---

### Task 20: Mirror polygon to room.polygon_pdf when committed against a room

**Files:**
- Modify: `frontend/src/components/project/PdfViewer.jsx` — accept `targetRoom` prop and forward to PolygonRoomModal commit
- Modify: `frontend/src/components/project/PolygonRoomModal.jsx` — on save, write `polygon_pdf` + recompute `plotas_m2` to the room
- Modify: `frontend/src/lib/projectStore.js` — `updateRoomPolygon(projectId, roomNr, polygonPoints, pageWidthPdf, pageHeightPdf)` helper

This is the bridge between Phase C-1 (polygons) and the existing data model (rooms with `polygon_pdf` field). The renderers (`AiRoomOverlay`, `TraceOverlay`) already render polygon_pdf — we just need to populate it.

- [ ] **Step 20.1: Add helper in projectStore.js**

In `frontend/src/lib/projectStore.js`, append:

```javascript
/**
 * Phase C-1 (2026-04-29): write a manually-traced polygon onto a room.
 * Stores polygon in PDF coordinates (matches polygon_pdf schema in
 * vision_call.py / AiRoomOverlay).
 */
export function updateRoomPolygon(projectId, roomNr, polygonPoints, pageMeta) {
  // pageMeta = { page_nr, page_width_pdf, page_height_pdf, pixels_per_meter }
  const projects = loadProjects();
  const proj = projects.find(p => p.id === projectId);
  if (!proj) return;
  const data = proj.data || {};
  const rooms = data.patalpos || data.rooms || [];
  const roomIdx = rooms.findIndex(r => String(r.nr) === String(roomNr));
  if (roomIdx < 0) return;

  // Compute area in m² from polygon (shoelace) — overrides Vision's plotas_m2
  // when user has manually traced. Uses pixelsPerMeter from page scale.
  const room = rooms[roomIdx];
  const updatedRoom = {
    ...room,
    polygon_pdf: polygonPoints,                   // [[x, y], ...] in PDF pts
    page_width_pdf: pageMeta.page_width_pdf,
    page_height_pdf: pageMeta.page_height_pdf,
    page_nr: pageMeta.page_nr,
    polygon_source: 'manual',
    polygon_confidence: 'high',
    polygon_traced_at: new Date().toISOString(),
  };

  // Recompute plotas_m2 if scale available — shoelace in pixel space ÷ ppm²
  if (pageMeta.pixels_per_meter) {
    let sum = 0;
    for (let i = 0; i < polygonPoints.length; i++) {
      const [x1, y1] = polygonPoints[i];
      const [x2, y2] = polygonPoints[(i + 1) % polygonPoints.length];
      sum += x1 * y2 - x2 * y1;
    }
    const areaPx = Math.abs(sum) / 2;
    const areaM2 = areaPx / (pageMeta.pixels_per_meter * pageMeta.pixels_per_meter);
    updatedRoom.plotas_m2 = Math.round(areaM2 * 100) / 100;
    updatedRoom.plotas_source = 'manual_polygon';
  }

  rooms[roomIdx] = updatedRoom;
  data.patalpos = rooms;
  proj.data = data;
  saveProject(proj);
}
```

(Use the existing `saveProject` and `loadProjects` from the same file; if signature differs, adapt — `grep -n "saveProject\|loadProjects" frontend/src/lib/projectStore.js`.)

- [ ] **Step 20.2: Wire PolygonRoomModal to call it on save**

In `frontend/src/components/project/PolygonRoomModal.jsx`, locate the save handler (search for `onClose` / `onSave` / where the modal commits the polygon). Add:

```javascript
import { updateRoomPolygon } from '@/lib/projectStore';

// inside the save handler:
if (selectedRoomNr && polygonDraft && pageScale) {
  const polygonPdfPoints = polygonDraft.points.map(p => [
    p.x / canvasToPdfX, p.y / canvasToPdfY,
  ]);
  updateRoomPolygon(projectId, selectedRoomNr, polygonPdfPoints, {
    page_nr: page,
    page_width_pdf: pageWidthPdf,
    page_height_pdf: pageHeightPdf,
    pixels_per_meter: pageScale.pixels_per_meter,
  });
}
```

The exact prop names depend on what PolygonRoomModal already receives — read the file first; reuse existing prop names; do not invent new ones.

- [ ] **Step 20.3: Manual smoke test**

Trace a polygon over an existing room. Modal opens. Pick room "Vonia" (nr 3). Save.
Expected: AiRoomOverlay now shows the polygon for room 3 (instead of bbox). Open the right panel — `plotas_m2` for that room reflects the traced area. Close and reopen project — polygon persists.

- [ ] **Step 20.4: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/lib/projectStore.js frontend/src/components/project/PolygonRoomModal.jsx
git commit -m "feat(polygon): mirror manual polygon to room.polygon_pdf

Bridges Phase C-1 editor with the existing AiRoomOverlay/TraceOverlay
renderers (already polygon-aware). Computes plotas_m2 via shoelace; marks
polygon_source='manual'."
```

---

### Task 21: Trigger interiorCalc recompute on polygon change

**Files:**
- Modify: `frontend/src/lib/projectStore.js` — call recompute after `updateRoomPolygon`
- Verify: `frontend/src/utils/interiorCalc.js` — accepts manually-overridden `plotas_m2`

- [ ] **Step 21.1: Find the existing recompute trigger**

Run: `cd frontend && grep -rn "recompute\|interiorCalc\|recalc" src/lib/projectStore.js src/components/project/AssumptionsPanel.jsx | head -20`
Identify the existing recompute pattern (the Prielaidos panel triggers it on assumption change).

- [ ] **Step 21.2: Trigger recompute after updateRoomPolygon**

In `updateRoomPolygon` (Task 20.1), after `saveProject(proj)`, add a call matching the existing pattern. Most likely:

```javascript
// existing pattern from AssumptionsPanel — emit a custom event
// other components listen for to recompute kiekiai.
window.dispatchEvent(new CustomEvent('samatu:project-recompute', {
  detail: { projectId },
}));
```

If the existing pattern is different (e.g., a direct call into `interiorCalc.recompute(projectData)`), use that pattern verbatim.

- [ ] **Step 21.3: Manual smoke test**

Trace polygon for room "Vonia" with a known area (calibrated scale). Save. Switch to "Kiekiai" tab.
Expected: kiekiai for that room (dažomas plotas, plytelės, etc.) reflect the new polygon-derived plotas_m2 — they should NOT still show the old Vision-extracted area.

- [ ] **Step 21.4: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/lib/projectStore.js
git commit -m "feat(polygon): trigger kiekiai recompute on polygon commit

Polygon-derived plotas_m2 must propagate through interiorCalc."
```

---

### Task 22: PolygonReviewBadge per-room indicator

**Files:**
- Create: `frontend/src/components/project/PolygonReviewBadge.jsx`
- Modify: `frontend/src/components/project/RoomCard.jsx` — render badge
- Modify: `frontend/src/components/project/WorkspacePanel.jsx` — render badge in room rows

- [ ] **Step 22.1: Create the badge component**

`frontend/src/components/project/PolygonReviewBadge.jsx`:

```javascript
/**
 * PolygonReviewBadge — per-room indicator showing whether the room has
 * a manual polygon (🟢 polygonas) or only Vision-extracted bbox (🟡 tik bbox).
 *
 * Click → activates the room and switches PDF to its page so the user
 * can trace it.
 */

export default function PolygonReviewBadge({ room, onClick }) {
  const hasPolygon = Array.isArray(room.polygon_pdf) && room.polygon_pdf.length >= 3;
  const hasBbox = !hasPolygon && room.bbox_pct
    && room.bbox_pct.w > 0 && room.bbox_pct.h > 0;

  if (!hasPolygon && !hasBbox) return null;

  const cls = hasPolygon
    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    : 'bg-amber-500/15 text-amber-300 border-amber-500/30';
  const dot = hasPolygon ? '🟢' : '🟡';
  const label = hasPolygon ? 'polygonas' : 'tik bbox — apvesk';
  const title = hasPolygon
    ? `Manualiai apibrėžtas polygonas (${room.polygon_pdf.length} taškų)`
    : 'AI rado bendrą zoną, bet tikslus polygon dar neapibrėžtas. Spauskite, kad apvesti.';

  return (
    <button
      onClick={onClick}
      title={title}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium ${cls}`}
    >
      <span>{dot}</span>
      <span>{label}</span>
    </button>
  );
}
```

- [ ] **Step 22.2: Mount in RoomCard**

In `RoomCard.jsx` near the room name/area block, render the badge:

```jsx
import PolygonReviewBadge from './PolygonReviewBadge';

// ... in the JSX:
<PolygonReviewBadge room={room} onClick={() => onJumpToRoom?.(room)} />
```

`onJumpToRoom` likely already exists; if not, plumb it from the parent (it should set the active room + switch the PDF to room.page_nr).

- [ ] **Step 22.3: Mount in WorkspacePanel room rows**

Same pattern — in the row rendering (search `WorkspacePanel.jsx` for the room loop, likely around the patalpos map).

- [ ] **Step 22.4: Manual smoke test**

Open project with mixed state. Some rooms (those with traced polygons) → green badge. Others (bbox only) → yellow. Click yellow → PDF jumps to that page, room highlighted, polygon tool ready.

- [ ] **Step 22.5: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/PolygonReviewBadge.jsx frontend/src/components/project/RoomCard.jsx frontend/src/components/project/WorkspacePanel.jsx
git commit -m "feat(polygon): per-room polygon-vs-bbox status badge

🟢/🟡 indicator per UX research; click to navigate + arm trace tool."
```

---

## Phase E: Mode UX polish

### Task 23: TraceModeBanner

**Files:**
- Create: `frontend/src/components/project/TraceModeBanner.jsx`
- Modify: `frontend/src/components/project/PdfViewer.jsx` — mount when `tool === 'polygon'`

- [ ] **Step 23.1: Create the banner**

`frontend/src/components/project/TraceModeBanner.jsx`:

```javascript
export default function TraceModeBanner({ visible, polygonDraft, orthoEnabled }) {
  if (!visible) return null;
  const vertexCount = polygonDraft?.points?.length || 0;

  return (
    <div
      className="absolute top-3 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3"
      style={{
        background: 'rgba(0, 184, 217, 0.95)', color: '#0f172a',
        padding: '6px 14px', borderRadius: 999,
        fontSize: 12, fontWeight: 600,
        boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
      }}
    >
      <span>📐 Apvedinėjamas kambarys</span>
      <span style={{ opacity: 0.7 }}>·</span>
      <span style={{ opacity: 0.85, fontWeight: 500 }}>
        {vertexCount} {vertexCount === 1 ? 'taškas' : vertexCount < 10 && vertexCount > 1 ? 'taškai' : 'taškų'}
      </span>
      <span style={{ opacity: 0.7 }}>·</span>
      <span style={{ opacity: 0.85, fontWeight: 500 }}>
        Enter užbaigti  ·  Esc atšaukti
      </span>
      {!orthoEnabled && (
        <>
          <span style={{ opacity: 0.7 }}>·</span>
          <span style={{ background: 'rgba(255,255,255,0.4)', padding: '1px 6px', borderRadius: 4, fontSize: 10 }}>
            ortho IŠJUNGTA (F8)
          </span>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 23.2: Mount in PdfViewer**

```jsx
import TraceModeBanner from './TraceModeBanner';

<TraceModeBanner
  visible={tool === 'polygon'}
  polygonDraft={polygonDraft}
  orthoEnabled={orthoEnabled}
/>
```

- [ ] **Step 23.3: Manual smoke test**

Click Polygon tool. Banner appears with "0 taškų". Click vertices — count updates. Press F8 — "ortho IŠJUNGTA" pill appears. Tab away from polygon tool — banner disappears.

- [ ] **Step 23.4: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/TraceModeBanner.jsx frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): trace-mode top banner with live vertex count + ortho status

Modal-mode indicator per UX research §7 (no-mode-indicator = #1 support
ticket on every annotation tool)."
```

---

### Task 24: Mobile view-only banner

**Files:**
- Create: `frontend/src/components/project/MobileViewOnlyBanner.jsx`
- Modify: `frontend/src/components/project/PdfViewer.jsx` — mount; suppress polygon tool button on coarse pointer

- [ ] **Step 24.1: Create the banner**

`frontend/src/components/project/MobileViewOnlyBanner.jsx`:

```javascript
import { useState, useEffect } from 'react';

const STORAGE_KEY = 'samatu_mobile_banner_dismissed';

export default function MobileViewOnlyBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const isCoarse = typeof window !== 'undefined'
      && window.matchMedia?.('(pointer: coarse)').matches;
    if (!isCoarse) return;
    try {
      if (localStorage.getItem(STORAGE_KEY) === '1') return;
    } catch { return; }
    setVisible(true);
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, '1'); } catch {}
    setVisible(false);
  };

  if (!visible) return null;
  return (
    <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-40 max-w-md text-center"
      style={{
        background: 'rgba(15,23,42,0.95)', color: '#fef3c7',
        padding: '10px 16px', borderRadius: 8, fontSize: 12,
      }}>
      Geriausia naudoti kompiuteryje. Mobilus režimas — peržiūros tik.
      <button onClick={dismiss} className="ml-3 underline">
        Aišku
      </button>
    </div>
  );
}
```

- [ ] **Step 24.2: Suppress the polygon tool button on coarse pointer**

In `LeftToolRail` inside `PdfViewer.jsx`, gate the Polygon button:

```javascript
const isCoarse = typeof window !== 'undefined'
  && window.matchMedia?.('(pointer: coarse)').matches;

const TOOLS = [
  // ... other tools
  ...(isCoarse ? [] : [
    { id: 'polygon', Icon: PenTool, label: 'Polygon (zona)', hint: '...' },
  ]),
];
```

- [ ] **Step 24.3: Manual smoke test**

Open in Chrome DevTools → Toggle device toolbar → iPhone 14. Reload.
Expected: banner at bottom; Polygon tool button absent from left rail; PDF still pans/pinch-zooms.

- [ ] **Step 24.4: Commit**

```bash
cd ~/samatu-ai
git add frontend/src/components/project/MobileViewOnlyBanner.jsx frontend/src/components/project/PdfViewer.jsx
git commit -m "feat(polygon): mobile view-only banner; hide polygon tool on coarse pointer

Phase C-1 is desktop-only (per locked decision); mobile editing is Phase D."
```

---

## Phase F: Final acceptance

### Task 25: Full smoke test against the 13-item acceptance checklist

**Files:**
- (No new code — verification only)

This is the gate before we declare Phase C-1 done. Run all 13 criteria from the synthesis plan §4 / UX research §10.9 manually against a known sample project (e.g., `~/Desktop/Visi techniniai 01.28.pdf` already used as Phase B test data).

- [ ] **Step 25.1: Setup — load test project**

Run: `cd ~/samatu-ai && (cd backend && uvicorn main:app --reload) &` then in another shell `cd frontend && npm run dev`.
Open `http://localhost:5173`, log in, upload `~/Desktop/Visi techniniai 01.28.pdf`. Wait for extraction.

- [ ] **Step 25.2: Run the 13-item checklist (each is a manual smoke check)**

```
[ ] 1. Press P, click 4 corners of "Svetainė", press Enter → labelled polygon visible
[ ] 2. Trace 3 polygons closing each via: (a) Enter, (b) double-click, (c) click first vertex.
       All three close cleanly.
[ ] 3. Trace 2 vertices, press Esc → in-progress polygon disappears, no residue
[ ] 4. Trace 4 vertices, press Backspace twice → 2 vertices remain, rubber band updates
[ ] 5. Trace mode: cursor naturally near horizontal locks to 90°. Hold Alt → free angle.
[ ] 6. Click committed polygon → cyan vertex circles + cyan stroke appear
[ ] 7. Hover an edge of selected polygon → small cyan ghost circle visible at midpoint;
       click ghost → new vertex inserted; polygon now has N+1 vertices
[ ] 8. Drag a vertex of polygon A near a corner of polygon B → cyan halo + "kampas"
       label, vertex snaps onto B's corner
[ ] 9. Drag a vertex near middle of B's edge → vertex snaps to perpendicular foot,
       "kraštas" label visible
[ ] 10. Trace polygon → drag a vertex → Ctrl+Z reverts drag → Ctrl+Z reverts polygon →
        Ctrl+Shift+Z restores polygon → Ctrl+Shift+Z restores vertex move
[ ] 11. Open right panel — selected room shows plotas_m2 matching shoelace area of
        traced polygon (within 0.1 m²)
[ ] 12. Trace a deliberate bowtie (zig-zag 4 vertices), try Enter →
        "Polygonas susikerta — pataisykite linijas" toast, polygon NOT committed
[ ] 13. All UI labels are Lithuanian (banner, toasts, badges, hint, mobile message)
[ ] PERF: drag a 30-vertex polygon — visibly smooth (no stutter on 2021 MacBook Pro
          or equivalent). If stutter, confirm imperative .position() is wired and
          state commit happens only on dragend.
```

- [ ] **Step 25.3: Run unit tests one more time**

Run: `cd frontend && npm run test:units`
Expected: all polygonGeometry tests pass.
Run: `cd frontend && npm run build`
Expected: clean build, bundle size for `pdf-viewer` and `canvas` chunks < 350 KB main bundle (per project standards).

- [ ] **Step 25.4: Run backend tests for regression**

Run: `cd backend && pytest -q`
Expected: existing 170 tests pass (Phase C-1 doesn't touch backend, so no regressions expected).

- [ ] **Step 25.5: Commit a final marker**

```bash
cd ~/samatu-ai
git commit --allow-empty -m "milestone: Phase C-1 polygon editor complete

All 13 acceptance criteria pass on Visi-techniciai-01.28.pdf sample.
Frontend bundle clean. Backend regression OK. Ready for Phase C-2 spike
(grid-calibrated Vision)."
```

---

## Self-Review

### 1. Spec coverage

Cross-checking each of the 13 items in §4 of the synthesis plan + §10.9 of UX research:

| # | Acceptance criterion | Implemented in |
|---|---|---|
| 1 | User can enter polygon-trace mode and click 4 corners → labelled polygon | Existing tool (already works) + Tasks 8/10 (Esc/Enter); Task 20 (room association) |
| 2 | Closing via Enter / dblclick / click-first all work | Task 10 (Enter); existing tool covers dblclick + click-first; Task 11 bumps tolerance to 12 px |
| 3 | Esc cancels mid-trace | Task 8 |
| 4 | Backspace removes last vertex during trace | Task 9 |
| 5 | Default ortho-90° on; Alt disables | Task 11 |
| 6 | Selected polygon shows draggable vertex circles | Task 14 |
| 7 | Midpoint ghost circles → drag becomes vertex | Task 14 |
| 8 | Snap to vertex of adjacent polygon at 12 px | Tasks 5 + 14 + 18 |
| 9 | Snap to edge of adjacent polygon at 8 px | Tasks 6 + 14 + 18 |
| 10 | Ctrl+Z / Ctrl+Shift+Z undo/redo across all ops | Task 19 + (existing takeoffStore.undo) |
| 11 | Polygon area via shoelace shown in sidebar pill | Task 20.1 (mirrors plotas_m2 to room) + existing right panel |
| 12 | Self-intersection refused on commit with LT toast | Task 12 |
| 13 | All UI labels Lithuanian | Tasks 8/9/10/11/12/13/22/23/24 (every user-facing string) |
| Bonus | Self-intersect detection (LT toast) | Task 12 |
| Bonus | Mode banner | Task 23 |
| Bonus | First-time hint | Task 13 |
| Bonus | Mobile view-only | Task 24 |
| Bonus | Per-room badge | Task 22 |
| Bonus | Trigger interiorCalc recompute | Task 21 |
| Bonus | PDF.js worker hardening (Gate 1) | Task 0 |
| Bonus | Konva perf flags + cleanup | Task 1 |

All 13 + bonuses covered.

### 2. Placeholder scan

- No "TBD" / "implement later" / "fill in details" — every step has either runnable code or an explicit verification command.
- "Add appropriate error handling" pattern → not used; every error path has a specific behavior (e.g., min-3-vertex toast text is verbatim).
- "Write tests for the above" without code → not used; every TDD task has the literal test source.
- "Similar to Task N" → checked; the few cross-references (Task 9 extending Task 8's handler, etc.) include the actual code to add, not just a reference.
- Steps that describe what without showing how → checked; UI tasks include either component source or specific JSX/handler edits.

One soft note for the implementer: a few code blocks (e.g., the existing `MarkupCanvas` mounting in Task 14.3) reference structure that requires reading the existing PdfViewer.jsx to integrate cleanly. The plan calls these out explicitly as "search the file for X" steps so the implementer doesn't paste blindly.

### 3. Type consistency

- Polygon storage: `{ id, page, points: [{x,y}], room_nr, type, label, source, confidence }` — matches existing takeoffStore schema; we add `polygon_source` and `polygon_traced_at` to the room record (Task 20), distinct fields from polygon-record fields.
- Op log type names: `'add_polygon'`, `'remove_polygon'`, `'update_polygon'` — match existing takeoffStore. New op meta sub-types (`'move-vertex'`, `'insert-vertex'`, `'delete-vertex'`, `'delete-vertices'`, `'move-vertices-batch'`) all funnel through the same `'update_polygon'` outer type, so `undo()` doesn't need new branches (Task 19.2 verifies).
- Snap result shape: `{ point: {x,y}, polygonId, vertexIndex }` (vertex) and `{ point, polygonId, edgeIndex }` (edge) — consistent across tasks 5/6/14/18.
- Room.polygon_pdf shape: `[[x, y], ...]` arrays of arrays — matches existing AiRoomOverlay/TraceOverlay expectation (line 84-90 of AiRoomOverlay.jsx). Task 20.1 emits this format, not `{x,y}` objects.
- `pageMeta` parameter to `updateRoomPolygon` (Task 20.1): `{ page_nr, page_width_pdf, page_height_pdf, pixels_per_meter }` — matches existing room field names in vision_call.py.

All consistent.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-phase-c-1-polygon-editor.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 25-task plan; isolates each task's context so the implementing agent isn't drowning in the full 1700-line PdfViewer.jsx.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints. Faster iteration if you want to watch each step land in real-time, but eats more context per task.

Which approach?

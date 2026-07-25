# PDF Takeoff-Viewer Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold the verified PDF-takeoff-viewer research + module (`~/Desktop/PDFViewerModule/`) into the live Sąmatų AI frontend — adding the measurement tools the app lacks (distance, perimeter, count-by-type, annotations), a durable zoom-invariant scale model, and a path to 100+ page performance — **without** ripping out the working react-pdf/Konva viewer.

**Architecture:** Adopt the module's *engine-agnostic* layers (verified geometry, calibration, measurement store, tools) on top of the existing `react-pdf@9` + `pdfjs-dist@4` + Konva stack via a thin adapter. Port to **JS/JSX** (the repo's language) with the TypeScript module as the reference spec; test the pure math with the repo's native `node --test`. The direct `pdfjs-dist@6` engine + full virtualization from the module is deferred behind the adapter boundary as a gated, optional phase.

**Tech Stack:** React 18 + Vite 6 (JS/JSX), react-pdf 9.1.1 / pdfjs-dist 4.6.82, react-konva 18 / konva 9, zustand 5 (present), Tailwind 3 + shadcn, Node built-in test runner (`node --test`). Backend: FastAPI (project JSON in `projects.data`, `PUT /api/projects/{id}`, `POST /api/projects/{id}/corrections`, `POST /api/recompute-quantities`, `GET /api/projects/{id}/pdf`).

---

## Why this shape (read before starting — two decisions are already made)

Three read-only explorations of the codebase produced the constraints below. They are not negotiable defaults; they're what the code forces.

**Decision 1 — Adapt onto `react-pdf@4`, do NOT introduce `pdfjs-dist@6`.**
The app already renders client-side with `react-pdf@9.1.1` (→ `pdfjs-dist@4.6.82`), worker copied to `dist/` by `viteStaticCopy`. The delivered module pins `pdfjs-dist@6.1.200`. **You cannot run both** — a worker whose version doesn't byte-match the API throws `The API version X does not match the Worker version Y`. Bumping to `@6` also forces Node 22+ (the repo has no Node lock) and would rip out a working Konva room-editor. The module's `PdfEngineAdapter` exists precisely so the measurement layer never imports the engine — so we adapt onto react-pdf's viewport and keep `@4`. The `@6` direct engine + virtualization is **Phase 4**, gated on a *measured* perf problem.

**Decision 2 — Port to JS/JSX, do NOT add a TypeScript island.**
The frontend is 196 JS/JSX files + 1 stray `.ts`, with `jsconfig.json` (`checkJs`) and a **`node --test`** runner (`"test:units": "node --test src/lib/*.test.js"`, using `node:test` + `node:assert/strict`). The writing-plans rule "follow established patterns" applies: the verified TypeScript module at `~/Desktop/PDFViewerModule/src/` is the **reference spec**; we port the pure geometry to `frontend/src/lib/measureGeometry.js` (plain JS, natively testable) and the UI to `.jsx`. This keeps the test story native and avoids a TS/JS seam.

**The honest reframing:** this is **not** "drop in a new viewer." The app already has client pdf.js rendering, a Konva polygon editor, 2-point scale calibration, client-side area math, and multi-source confidence. What it genuinely lacks — and what the research/module add — is: (a) measurement tools beyond room polygons, (b) a **durable, zoom-invariant** scale (today's `pixels_per_meter` lives only in `localStorage` and is lost on cache-clear), (c) the verified geometry (anisotropic area for stretched scans, separate-axis calibration), and (d) a 100+ page perf path. We add exactly those.

---

## Current-state map (exact files this plan touches)

| Concern | File | Today |
|---|---|---|
| Interior viewer (live) | `frontend/src/components/project/PlanViewer.jsx` (1064 ln) | react-pdf **single page** (`pageNumber`, `[`/`]`, thumbnail rail), SVG room overlays (`polygon_pdf × sx,sy`), not virtualized |
| Room polygon editor | `frontend/src/components/project/PolygonEditor.jsx` | Konva vertex-drag editor, snapping |
| Read-only room overlay | `frontend/src/components/project/AiRoomOverlay.jsx` | Konva `<Line>` per room, color by paskirtis |
| Count/suggestion overlay | `frontend/src/components/project/DrawingOverlay.jsx` | vanilla-canvas count markers |
| Takeoff state | `frontend/src/lib/takeoffStore.js` | `pageScales[n].pixels_per_meter` (localStorage), `polygons[]`, `polygonAreaM2/polygonPerimeterM/distanceM`, undo/redo |
| Geometry helpers | `frontend/src/lib/polygonGeometry.js` | nearestVertex/Edge, orthoSnap, pointInPolygon, centroid |
| Plan overlay geometry + test | `frontend/src/lib/planOverlayGeometry.js` / `.test.js` | the `node:test` pattern to copy |
| Scale calibration UI | `frontend/src/components/project/ScaleCalibrationModal.jsx` | 2-point → `pixels_per_meter`, "apply to all" |
| Room polygon persistence | `frontend/src/lib/projectStore.js` (`updateRoomPolygon`, ~ln 282-348) | writes `patalpos[].polygon_pdf` + `page_width_pdf/height` + `plotas_m2` + `plotas_source` |
| Confidence | `frontend/src/lib/areaConfidence.js`, `components/project/ConfidenceBadge.jsx` | multi-source agreement → 🟢🟡🔴 |
| Backend persistence | `PUT /api/projects/{id}` → `db.upsert_project` | full project JSON upsert |
| Backend corrections | `POST /api/projects/{id}/corrections` → `db.log_correction` | audit log |
| Backend recompute | `POST /api/recompute-quantities` (`backend/api/recompute_quantities.py`) | rooms+edits → pozicijos |
| Raw PDF | `GET /api/projects/{id}/pdf` | bytes (R2/local) — client pdf.js source |

**Reference spec (verified, do not import — port from):** `~/Desktop/PDFViewerModule/src/geometry/{measure,units,snapping}.ts`, `state/MeasurementStore.ts`, `components/*`, `export/exporters.ts`. These are tsc-clean + unit-tested (19/19).

---

## File Structure (new + modified)

**New (Phase 0–2):**
- `frontend/src/lib/measureGeometry.js` — verified geometry ported to JS: calibration (uniform + separate X/Y), distance, anisotropic shoelace, perimeter, net-area-with-holes, scaleFromRatio, LT number / ft-in formatting. **Single math source of truth.**
- `frontend/src/lib/measureGeometry.test.js` — `node --test` port of the module's 19 assertions.
- `frontend/src/lib/durableScale.js` — per-page durable scale model (`meters_per_point`), (de)serialize into `project.data.pageScalesDurable`, and bridge to/from legacy `pixels_per_meter`.
- `frontend/src/lib/durableScale.test.js`.
- `frontend/src/lib/measurements.js` — measurement entity model + pure ops (distance/perimeter/area/count/annotation), reusing `measureGeometry`. Persisted into `project.data.measurements`.
- `frontend/src/lib/measurements.test.js`.
- `frontend/src/components/project/MeasureToolbar.jsx` — tool selector (distance/perimeter/count/annotate) + scale pill + export, in the viewer chrome.
- `frontend/src/components/project/MeasureOverlay.jsx` — SVG overlay over the react-pdf page: draws + handles input for the new tools (reuses existing snapping from `polygonGeometry.js`).
- `frontend/src/components/project/CountLegendPanel.jsx` — typed count legend + tallies.
- `frontend/src/lib/measureExport.js` — JSON + CSV export of measurements (port of `exporters.ts`).

**Modified:**
- `frontend/src/lib/takeoffStore.js` — `polygonAreaM2`/`polygonPerimeterM`/`distanceM` delegate to `measureGeometry` (API unchanged); add measurement + durable-scale slices.
- `frontend/src/components/project/PlanViewer.jsx` — mount `<MeasureOverlay>` + `<MeasureToolbar>`; pass page viewport (the react-pdf adapter point).
- `frontend/src/components/project/ScaleCalibrationModal.jsx` — write durable `meters_per_point`, add separate-axis + self-check echo, persist + log correction.
- `backend/main.py` — accept/return `pageScalesDurable` + `measurements` in the project payload (they ride in `projects.data` already; just ensure they're not stripped).

---

# PHASE 0 — Verified geometry + durable scale (engine-agnostic keystone)

**Why first:** every later tool and the durable-scale UX depend on one trustworthy math module. This phase has zero UI and zero engine dependency — pure JS + `node --test`. It also fixes a real correctness gap (zoom-dependent scale) before building on it.

## Task 0.1: Port the verified geometry to JS

**Files:**
- Create: `frontend/src/lib/measureGeometry.js`
- Test: `frontend/src/lib/measureGeometry.test.js`

- [ ] **Step 1: Write the failing test** (port of the module's validated 19 assertions, `node:test` style)

```js
// frontend/src/lib/measureGeometry.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  calibrateUniform, realDistanceM, shoelaceAreaM2, realPathLengthM,
  netAreaM2, scaleFromRatio, parseFeetInches, formatFeetInches, formatNumberLT,
} from './measureGeometry.js';

const rect = [{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 100 }, { x: 0, y: 100 }];

test('calibrateUniform solves metres-per-point', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  assert.ok(Math.abs(s.metersPerPointX - 0.05) < 1e-9);
});
test('realDistanceM under scale', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  assert.ok(Math.abs(realDistanceM({ x: 0, y: 0 }, { x: 200, y: 0 }, s) - 10) < 1e-9);
});
test('anisotropic shoelace gives correct m² for stretched scans', () => {
  const aniso = { metersPerPointX: 0.01, metersPerPointY: 0.03, calibrated: true };
  assert.ok(Math.abs(shoelaceAreaM2(rect, aniso) - 6) < 1e-9);
  assert.ok(Math.abs(shoelaceAreaM2([...rect].reverse(), aniso) - 6) < 1e-9); // orientation-independent
});
test('closed perimeter 30 m, open polyline 25 m', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  assert.ok(Math.abs(realPathLengthM(rect, s, true) - 30) < 1e-9);
  assert.ok(Math.abs(realPathLengthM(rect, s, false) - 25) < 1e-9);
});
test('net area subtracts holes', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  const holes = [[{ x: 10, y: 10 }, { x: 60, y: 10 }, { x: 60, y: 60 }, { x: 10, y: 60 }]];
  assert.ok(Math.abs(netAreaM2(rect, holes, s) - 43.75) < 1e-9);
});
test('scaleFromRatio 1:50', () => {
  assert.ok(Math.abs(scaleFromRatio(50).metersPerPointX - (50 / 72) * 0.0254) < 1e-12);
});
test('imperial parse/format edge cases (the fixed bugs)', () => {
  assert.ok(parseFeetInches('-0\'6"') < 0);                                  // keeps negative sign
  assert.ok(Math.abs(parseFeetInches('5\' 1/2"') - 60.5 * 0.0254) < 1e-9);   // fraction-only inches
  assert.ok(!formatFeetInches(-0.0001).includes('−'));                       // no minus on rounded-zero
  assert.equal(formatFeetInches(3.81), '12\' 6"');
});
test('LT number formatting', () => {
  assert.equal(formatNumberLT(1234.5, 2), '1 234,50');
  assert.equal(formatNumberLT(1234, 0), '1 234');
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && node --test src/lib/measureGeometry.test.js`
Expected: FAIL — `Cannot find module './measureGeometry.js'`

- [ ] **Step 3: Write the minimal implementation** (JS port of `measure.ts` + `units.ts`; geometry stored in PDF points, scale = metres-per-point with separate axes)

```js
// frontend/src/lib/measureGeometry.js
// Verified geometry ported from ~/Desktop/PDFViewerModule/src/geometry (tsc-clean, 19/19 tests).
// CORE INVARIANT: all geometry is in PDF-point space (zoom/rotation invariant). One calibration
// ratio per page (metres of reality per PDF point, separate X/Y for stretched scans). Convert last.

const TO_M = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254, ft: 0.3048 };

export function pdfDistance(a, b) { return Math.hypot(b.x - a.x, b.y - a.y); }

export function calibrateUniform(a, b, knownLength, unit = 'm', opts = {}) {
  const d = pdfDistance(a, b);
  if (d <= 1e-9) throw new Error('Kalibravimo linija per trumpa');
  const mpp = (knownLength * TO_M[unit]) / d;
  return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true,
           source: opts.source || 'user', label: opts.label, anisotropic: false };
}

export function calibrateAxis(a, b, knownLength, unit, base, axis) {
  const dx = Math.abs(b.x - a.x), dy = Math.abs(b.y - a.y);
  const useAxis = axis || (dx >= dy ? 'x' : 'y');
  const span = useAxis === 'x' ? dx : dy;
  if (span <= 1e-9) throw new Error('Kalibravimo ašis per trumpa');
  const mpp = (knownLength * TO_M[unit]) / span;
  const prev = base || { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: false, source: 'user' };
  const next = { ...prev, calibrated: true, source: 'user',
    metersPerPointX: useAxis === 'x' ? mpp : prev.metersPerPointX,
    metersPerPointY: useAxis === 'y' ? mpp : prev.metersPerPointY };
  next.anisotropic =
    Math.abs(next.metersPerPointX - next.metersPerPointY) /
      Math.max(next.metersPerPointX, next.metersPerPointY) > 0.02;
  return next;
}

export function scaleFromRatio(ratio, label) {
  const mpp = (ratio / 72) * 0.0254;
  return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true,
           source: 'standard', label: label || `1:${ratio}`, anisotropic: false };
}

export function uncalibratedScale() {
  return { metersPerPointX: 0, metersPerPointY: 0, calibrated: false, source: 'none' };
}

export function realDistanceM(a, b, s) {
  return Math.hypot((b.x - a.x) * s.metersPerPointX, (b.y - a.y) * s.metersPerPointY);
}

export function realPathLengthM(pts, s, closed = false) {
  const n = pts.length;
  if (n < 2) return 0;
  let m = 0;
  const last = closed ? n : n - 1;
  for (let i = 0; i < last; i++) m += realDistanceM(pts[i], pts[(i + 1) % n], s);
  return m;
}

export function shoelaceAreaM2(pts, s) {
  const n = pts.length;
  if (n < 3) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const p = pts[i], q = pts[(i + 1) % n];
    sum += (p.x * s.metersPerPointX) * (q.y * s.metersPerPointY)
         - (q.x * s.metersPerPointX) * (p.y * s.metersPerPointY);
  }
  return Math.abs(sum) / 2;
}

export function netAreaM2(outer, holes, s) {
  const gross = shoelaceAreaM2(outer, s);
  const cut = (holes || []).reduce((acc, h) => acc + shoelaceAreaM2(h, s), 0);
  return Math.max(0, gross - cut);
}

// ── formatting (LT-locale + imperial) ──
export function formatNumberLT(value, decimals = 2) {
  if (!Number.isFinite(value)) return '—';
  const fixed = value.toFixed(decimals);
  const dot = fixed.indexOf('.');
  const intRaw = dot >= 0 ? fixed.slice(0, dot) : fixed;
  const frac = dot >= 0 ? fixed.slice(dot + 1) : '';
  const neg = intRaw.startsWith('-');
  const digits = neg ? intRaw.slice(1) : intRaw;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const sign = neg ? '−' : '';
  return decimals > 0 ? `${sign}${grouped},${frac}` : `${sign}${grouped}`;
}

function gcd(a, b) { while (b) { [a, b] = [b, a % b]; } return a; }

export function formatFeetInches(meters, denom = 16) {
  const totalInches = meters / 0.0254;
  let inches = Math.abs(totalInches);
  let feet = Math.floor(inches / 12);
  inches -= feet * 12;
  let whole = Math.floor(inches);
  let num = Math.round((inches - whole) * denom);
  if (num === denom) { num = 0; whole += 1; }
  if (whole === 12) { feet += 1; whole = 0; }
  let frac = '';
  if (num > 0) { const g = gcd(num, denom); frac = ` ${num / g}/${denom / g}`; }
  const sign = totalInches < 0 && (feet > 0 || whole > 0 || num > 0) ? '−' : '';
  return `${sign}${feet}' ${whole}${frac}"`;
}

export function parseFeetInches(raw) {
  const s = String(raw).trim();
  if (!s) return null;
  const m = s.match(/^-?\s*(\d+(?:\.\d+)?)\s*'\s*(?:(\d+(?:\.\d+)?)\s*)?(?:(\d+)\/(\d+))?\s*"?$/);
  if (m) {
    const sign = /^\s*-/.test(s) ? -1 : 1;
    const feet = parseFloat(m[1]);
    const inches = m[2] ? parseFloat(m[2]) : 0;
    const fr = m[3] && m[4] ? parseInt(m[3], 10) / parseInt(m[4], 10) : 0;
    return sign * (feet * 12 + inches + fr) * 0.0254;
  }
  const mf = s.match(/^(-?\d+(?:\.\d+)?)\s*'$/);
  if (mf) return parseFloat(mf[1]) * 12 * 0.0254;
  const md = s.match(/^(\d{3,})$/);
  if (md) {
    const d = md[1];
    const inches = parseInt(d.slice(-2), 10);
    if (inches > 11) return null;
    return (parseInt(d.slice(0, -2), 10) * 12 + inches) * 0.0254;
  }
  return null;
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && node --test src/lib/measureGeometry.test.js`
Expected: PASS (9 test blocks)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/measureGeometry.js frontend/src/lib/measureGeometry.test.js
git commit -m "feat(viewer): verified PDF-point geometry as single math source"
```

## Task 0.2: Durable per-page scale model + legacy bridge

**Why:** today `pixels_per_meter` lives only in `localStorage` (lost on cache-clear; zoom-coupled). Store a durable, zoom-invariant `meters_per_point` per page inside `project.data` so it survives, and bridge the legacy value so nothing breaks.

**Files:**
- Create: `frontend/src/lib/durableScale.js`
- Test: `frontend/src/lib/durableScale.test.js`

- [ ] **Step 1: Write the failing test**

```js
// frontend/src/lib/durableScale.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { setPageScaleDurable, getPageScaleDurable, pxPerMeterFromDurable, durableFromPxPerMeter } from './durableScale.js';

test('set/get durable scale on a project object', () => {
  let project = {};
  project = setPageScaleDurable(project, 2, { metersPerPointX: 0.05, metersPerPointY: 0.05, calibrated: true, source: 'user' });
  const s = getPageScaleDurable(project, 2);
  assert.equal(s.metersPerPointX, 0.05);
  assert.equal(s.calibrated, true);
});
test('uncalibrated page returns calibrated:false', () => {
  assert.equal(getPageScaleDurable({}, 9).calibrated, false);
});
test('bridge px/m <-> metres/point at a render scale (px per pdf-point)', () => {
  // at renderScale=2 px/pt and 0.05 m/pt → px/m = 2 / 0.05 = 40
  assert.ok(Math.abs(pxPerMeterFromDurable({ metersPerPointX: 0.05 }, 2) - 40) < 1e-9);
  const dur = durableFromPxPerMeter(40, 2);   // inverse
  assert.ok(Math.abs(dur.metersPerPointX - 0.05) < 1e-9);
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && node --test src/lib/durableScale.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

```js
// frontend/src/lib/durableScale.js
// Durable, zoom-invariant per-page scale stored in project.data.pageScalesDurable[pageNr].
// Canonical unit: metres of reality per PDF point. Survives cache-clear (rides project JSON).
import { uncalibratedScale } from './measureGeometry.js';

export function getPageScaleDurable(project, pageNr) {
  const map = (project && project.pageScalesDurable) || {};
  return map[pageNr] || uncalibratedScale();
}

export function setPageScaleDurable(project, pageNr, scale, applyToPages) {
  const map = { ...((project && project.pageScalesDurable) || {}) };
  map[pageNr] = scale;
  if (Array.isArray(applyToPages)) for (const p of applyToPages) map[p] = scale;
  return { ...project, pageScalesDurable: map };
}

// renderScale = CSS px per PDF point (react-pdf viewport.scale at the current zoom).
export function pxPerMeterFromDurable(scale, renderScale) {
  const mpp = scale.metersPerPointX || 0;
  return mpp > 0 ? renderScale / mpp : 0;
}

export function durableFromPxPerMeter(pixelsPerMeter, renderScale) {
  const mpp = pixelsPerMeter > 0 ? renderScale / pixelsPerMeter : 0;
  return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: mpp > 0, source: 'user', anisotropic: false };
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && node --test src/lib/durableScale.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/durableScale.js frontend/src/lib/durableScale.test.js
git commit -m "feat(viewer): durable zoom-invariant per-page scale model + legacy bridge"
```

## Task 0.3: Route `takeoffStore` area/length math through `measureGeometry`

**Why:** one math source. `takeoffStore.polygonAreaM2` keeps its signature (callers unchanged) but delegates, so the verified anisotropic-safe formula is used everywhere.

**Files:**
- Modify: `frontend/src/lib/takeoffStore.js` (`polygonAreaM2`, `polygonPerimeterM`, `distanceM`)
- Test: `frontend/src/lib/takeoffStore.test.js` (create if absent)

- [ ] **Step 1: Write the failing test**

```js
// frontend/src/lib/takeoffStore.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { polygonAreaM2 } from './takeoffStore.js';

test('polygonAreaM2 matches verified math (isotropic): 200x100 px at 100 px/m = 2 m²', () => {
  const pts = [{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 100 }, { x: 0, y: 100 }];
  assert.ok(Math.abs(polygonAreaM2(pts, 100) - 2) < 1e-6);
});
```

- [ ] **Step 2: Run it to verify it fails (or passes trivially — then make it delegate)**

Run: `cd frontend && node --test src/lib/takeoffStore.test.js`
Expected: PASS with the legacy impl too (sanity), but we still refactor to delegate so anisotropic scales are correct.

- [ ] **Step 3: Refactor to delegate** (replace the body of `polygonAreaM2`; keep the exported signature `(points, pixelsPerMeter)`)

```js
// in frontend/src/lib/takeoffStore.js — add import at top:
import { shoelaceAreaM2, realPathLengthM, realDistanceM } from './measureGeometry.js';

// replace polygonAreaM2 / polygonPerimeterM / distanceM bodies:
export function polygonAreaM2(points, pixelsPerMeter) {
  if (!pixelsPerMeter || points.length < 3) return 0;
  const mpp = 1 / pixelsPerMeter;                 // metres per pixel (isotropic legacy)
  const s = { metersPerPointX: mpp, metersPerPointY: mpp };
  return Math.round(shoelaceAreaM2(points, s) * 100) / 100;
}
export function polygonPerimeterM(points, pixelsPerMeter) {
  if (!pixelsPerMeter || points.length < 2) return 0;
  const mpp = 1 / pixelsPerMeter;
  const s = { metersPerPointX: mpp, metersPerPointY: mpp };
  return Math.round(realPathLengthM(points, s, true) * 100) / 100;
}
export function distanceM(p1, p2, pixelsPerMeter) {
  if (!pixelsPerMeter) return 0;
  const mpp = 1 / pixelsPerMeter;
  return Math.round(realDistanceM(p1, p2, { metersPerPointX: mpp, metersPerPointY: mpp }) * 100) / 100;
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && node --test src/lib/takeoffStore.test.js src/lib/measureGeometry.test.js`
Expected: PASS (and no other `takeoffStore` consumers break — signatures unchanged).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/takeoffStore.js frontend/src/lib/takeoffStore.test.js
git commit -m "refactor(viewer): takeoffStore area/length delegate to verified geometry"
```

---

# PHASE 1 — Measurement tools the app lacks (engine-agnostic UI)

**Why:** distance, standalone perimeter, count-by-type, and freehand/shape annotations are the genuinely new capabilities. They reuse Phase 0 geometry + the existing `polygonGeometry.js` snapping and mount as an SVG overlay inside `PlanViewer` (no engine change).

## Task 1.1: Measurement entity model + pure ops

**Files:**
- Create: `frontend/src/lib/measurements.js`
- Test: `frontend/src/lib/measurements.test.js`

- [ ] **Step 1: Write the failing test**

```js
// frontend/src/lib/measurements.test.js
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeMeasurement, measurementValue, DEFAULT_COUNT_TYPES } from './measurements.js';

const s = { metersPerPointX: 0.05, metersPerPointY: 0.05, calibrated: true };

test('distance measurement value = metres', () => {
  const m = makeMeasurement('distance', 2, [{ x: 0, y: 0 }, { x: 200, y: 0 }]);
  assert.ok(Math.abs(measurementValue(m, s).value - 10) < 1e-9);
});
test('area measurement reports value (m²) + secondary (perimeter m)', () => {
  const m = makeMeasurement('area', 2, [{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 100 }, { x: 0, y: 100 }]);
  const r = measurementValue(m, s);
  assert.ok(Math.abs(r.value - 50) < 1e-9);
  assert.ok(Math.abs(r.secondary - 30) < 1e-9);
});
test('seed count types exist', () => {
  assert.ok(DEFAULT_COUNT_TYPES.find(t => t.id === 'rozetes'));
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && node --test src/lib/measurements.test.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

```js
// frontend/src/lib/measurements.js
// Measurement entities live in project.data.measurements[]. Geometry in PDF points.
import { realPathLengthM, shoelaceAreaM2, netAreaM2 } from './measureGeometry.js';

let _seq = 0;
const uid = () => (typeof crypto !== 'undefined' && crypto.randomUUID)
  ? crypto.randomUUID() : `m_${Date.now()}_${_seq++}`;

export const DEFAULT_COUNT_TYPES = [
  { id: 'rozetes', label: 'Rozetės', color: '#2a6fb5', shape: 'circle' },
  { id: 'jungikliai', label: 'Jungikliai', color: '#7c3aed', shape: 'square' },
  { id: 'sviestuvai', label: 'Šviestuvai', color: '#d97706', shape: 'diamond' },
  { id: 'durys', label: 'Durys', color: '#16a34a', shape: 'check' },
  { id: 'langai', label: 'Langai', color: '#dc2626', shape: 'square' },
  { id: 'santechnika', label: 'Santechnikos taškai', color: '#0d9488', shape: 'circle' },
];

// kind: 'distance' | 'perimeter' | 'area' | 'count' | 'annotation'
export function makeMeasurement(kind, pageNr, points, extra = {}) {
  return {
    id: uid(), kind, page: pageNr, points,
    holes: kind === 'area' ? (extra.holes || []) : undefined,
    classification: extra.classification || '',
    color: extra.color || '#2a6fb5',
    confidence: extra.confidence || 'amber',
    source: extra.source || 'user',
    created_at: new Date().toISOString(),
    ...extra,
  };
}

export function measurementValue(m, scale) {
  if (m.kind === 'area') {
    return { value: netAreaM2(m.points, m.holes, scale), secondary: realPathLengthM(m.points, scale, true) };
  }
  if (m.kind === 'distance' || m.kind === 'perimeter') {
    return { value: realPathLengthM(m.points, scale, false) };
  }
  return { value: 0 };
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd frontend && node --test src/lib/measurements.test.js`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/measurements.js frontend/src/lib/measurements.test.js
git commit -m "feat(viewer): measurement entity model + pure value ops"
```

## Task 1.2: `MeasureOverlay.jsx` — SVG tool overlay over the page

**Files:**
- Create: `frontend/src/components/project/MeasureOverlay.jsx`
- Modify: `frontend/src/components/project/PlanViewer.jsx` (mount the overlay; pass viewport)

**Spec (port of `MeasurementLayer.tsx` to JSX, reusing existing snapping):**
- Props: `{ pageNr, viewport, tool, scale, measurements, onCommit, onSelect, snapTargets }`. `viewport` is the react-pdf page viewport (provides `convertToViewportPoint`/`convertToPdfPoint` or the transform — see Task 1.3 adapter).
- An absolutely-positioned `<svg>` sized to the rendered page. Pointer handlers add PDF-point vertices (converted via the adapter), with a rubber-band + live readout (reuse `measurementValue` for the in-progress shape).
- Tools: `distance` (polyline, Enter/dblclick finish), `perimeter` (open), `area` (polygon, click-first/Enter/dblclick close), `count` (drop typed marker), `annotation` shapes (rect/circle/freehand/text/highlight via drag).
- Snapping: reuse `nearestVertex`/`nearestEdge`/`orthoSnap` from `frontend/src/lib/polygonGeometry.js` (already battle-tested) — do **not** add a second snapping impl.
- On finish: `onCommit(makeMeasurement(...))`.

> This task is a **JSX port** of the reference `~/Desktop/PDFViewerModule/src/components/MeasurementLayer.tsx` (strip types; swap the engine `toViewport/toPdf` for the Task 1.3 react-pdf adapter; swap `geometry/snapping` for `lib/polygonGeometry.js`). Because it's a large component, implement it behind these tests:

**Test:** `frontend/src/lib/measureOverlayReducer.test.js` — extract the pure input→draft reducer (add vertex, finish, close-detect) into `measureOverlayReducer.js` and unit-test it with `node:test` (the SVG rendering itself is verified in a browser per the project's "open a browser for UI" rule). Reducer test:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import { draftReducer } from './measureOverlayReducer.js';

test('area close on click-first within tolerance', () => {
  let d = { tool: 'area', points: [{x:0,y:0},{x:10,y:0},{x:10,y:10}] };
  const r = draftReducer(d, { type: 'click', point: { x: 0.5, y: 0.5 }, closeTolerance: 2 });
  assert.equal(r.committed, true);
  assert.equal(r.points.length, 3);   // does not append the closing click
});
test('distance appends vertices', () => {
  let d = { tool: 'distance', points: [{x:0,y:0}] };
  const r = draftReducer(d, { type: 'click', point: { x: 5, y: 0 } });
  assert.equal(r.points.length, 2);
  assert.equal(r.committed, false);
});
```

Steps follow the 0.1 TDD pattern (write reducer test → fail → implement `measureOverlayReducer.js` → pass → commit), then build `MeasureOverlay.jsx` around the reducer and **verify in a browser** (load a real project, draw a distance + an area, confirm the live readout matches a known dimension). Commit the component separately with a note that browser verification was done.

## Task 1.3: react-pdf viewport adapter (the engine boundary)

**Files:**
- Create: `frontend/src/lib/reactPdfAdapter.js`
- Test: `frontend/src/lib/reactPdfAdapter.test.js`

**Why:** the overlay needs screen-px ↔ PDF-point conversion. react-pdf's `onRenderSuccess` hands you the pdf.js `page`; build a viewport via `page.getViewport({ scale })` and expose `toPdf`/`toViewport` using its affine matrix — the exact pattern verified in the module (`applyMatrix`/`applyInverseMatrix`).

```js
// frontend/src/lib/reactPdfAdapter.js
export function makeViewportAdapter(viewport) {
  // viewport from pdfjs page.getViewport({scale}); viewport.transform = [a,b,c,d,e,f]
  const m = viewport.transform;
  return {
    width: viewport.width, height: viewport.height, scale: viewport.scale,
    toViewport(p) { return { x: m[0]*p.x + m[2]*p.y + m[4], y: m[1]*p.x + m[3]*p.y + m[5] }; },
    toPdf(sp) {
      const [a,b,c,d,e,f] = m, det = a*d - b*c;
      return { x: (d*(sp.x-e) - c*(sp.y-f))/det, y: (-b*(sp.x-e) + a*(sp.y-f))/det };
    },
  };
}
```

Test asserts round-trip `toPdf(toViewport(p)) ≈ p` for a sample matrix (the module proved this to machine precision). TDD per the 0.1 pattern. **This is the single file a future `pdfjs@6` engine swap (Phase 4) would replace.**

## Task 1.4: `MeasureToolbar.jsx` + `CountLegendPanel.jsx`

Port `MeasurementToolbar.tsx` / `CountLegend.tsx` to JSX using shadcn `Button`/`Select` from `frontend/src/components/ui/` and the viewer-chrome tokens (`--viewer-chrome`). Toolbar shows the **durable** scale pill (🟢 kalibruota / 🟡 nepatvirtinta), tool buttons, unit toggle, and JSON/CSV export. Wire into `PlanViewer`'s toolbar row. Browser-verify. (No pure-logic test needed beyond the tally count, which `measurements.test.js` covers via a `countByType` helper added there.)

---

# PHASE 2 — Durable-scale calibration UX

## Task 2.1: Upgrade `ScaleCalibrationModal` to write durable scale + persist

**Files:**
- Modify: `frontend/src/components/project/ScaleCalibrationModal.jsx`
- Modify: `frontend/src/lib/projectStore.js` (persist `pageScalesDurable`) + `backend/main.py` (don't strip it)
- Test: `frontend/src/lib/durableScale.test.js` (extend with an apply-to-all case)

**Spec:**
- On confirm, call `calibrateUniform`/`calibrateAxis` (Phase 0) → `setPageScaleDurable(project, pageNr, scale, applyToAll ? allPages : undefined)` → `PUT /api/projects/{id}` (existing) + `POST /api/projects/{id}/corrections` with `field_path: "pageScalesDurable[<n>]"`, `source: "scale_calibration"`.
- Add the module's extras: separate-axis option (for stretched scans), the self-check echo ("pagal esamą mastelį ši linija = X m"), and the longest-baseline tip.
- Keep writing legacy `pixels_per_meter` too (via `pxPerMeterFromDurable(scale, renderScale)`) so existing consumers keep working during migration.
- Backend: confirm `pageScalesDurable` + `measurements` survive the `GET /api/projects/{id}` strip at `main.py:~1017` (only `_meta` internals are stripped; these are top-level data — add a regression test in `backend/tests/` that round-trips a project with `pageScalesDurable` through `db.upsert_project`/`get_project`).

**Backend test (TDD):**
```python
# backend/tests/test_durable_scale_roundtrip.py
import db
def test_pagescales_durable_survives_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMATU_DB_PATH", str(tmp_path / "t.db")); import importlib; importlib.reload(db); db.init_db()
    pid = "p1"
    db.upsert_project(pid, {"patalpos": [], "pageScalesDurable": {"2": {"metersPerPointX": 0.05, "calibrated": True}}}, "u1")
    got = db.get_project(pid, "u1")
    assert got["data"]["pageScalesDurable"]["2"]["metersPerPointX"] == 0.05
```
(Adapt to the real `db.upsert_project`/`get_project` signatures.)

## Task 2.2: Surface durable scale in `PlanViewer` + room areas

Make `PlanViewer` and the room-area display read the durable scale (via `getPageScaleDurable(project, pageNr)`) when present, falling back to legacy `pixels_per_meter`. Room polygon areas recompute from `polygon_pdf` × durable scale — fixing the "areas wrong after cache-clear" gap. Browser-verify against the contractor fixture (Beržų g. 24: known 419.92 m² paint etc.).

---

# PHASE 3 — Persistence & export (port)

Port `~/Desktop/PDFViewerModule/src/export/exporters.ts` → `frontend/src/lib/measureExport.js` (JSON + CSV, LT-locale, BOM for Excel). Measurements already persist in `project.data.measurements` via `PUT /api/projects/{id}`. Add:
- A "Eksportuoti matavimus" action (JSON + CSV) in `MeasureToolbar`.
- Optional bi-directional link: a measurement with `linkedRowId` pushes its quantity into the žiniaraštis via `POST /api/recompute-quantities` (reuse the existing edit-merge). TDD `measureExport.js` with `node:test` (CSV row count + LT number format); browser-verify the download.

---

# PHASE 4 — 100+ page performance (THE ENGINE DECISION — needs sign-off)

> **Status: decision point.** Do **not** start without choosing the path. Phases 0–3 work on the current single-page react-pdf viewer regardless.

Today `PlanViewer` renders **one page at a time**. For 100+ page scans that's fine for review but not for scroll-through takeoff. Two paths:

**Path A (recommended): virtualize on top of react-pdf@4.**
Wrap the page list in `@tanstack/react-virtual` (add dep), render visible ± overscan react-pdf `<Page>`s, apply DPR cap + the safe-area guard + `renderTask` cancel/cleanup patterns from the module's `PdfjsEngine`/`PdfPageCanvas` (ported to react-pdf's `onRenderSuccess`/`onRenderError`). Keeps `@4`, no Node-22, no rewrite. Risk: react-pdf gives less control over the worker/canvas than the raw engine.

**Path B: replace react-pdf with the module's direct `pdfjs-dist@6` engine.**
Adopt `PdfjsEngine.ts` + `pdfWorker.ts` + virtualization wholesale (port to JSX). Unlocks the full perf story (tiling, OffscreenCanvas, exact cleanup). Cost: bump `pdfjs-dist` 4→6 (breaks react-pdf — remove it), require **Node 22+** in CI/prod (set `engines` + Render/Railway Node), re-wire the worker (drop `viteStaticCopy`, use the `?url` import), and re-validate every existing viewer feature (clickToFill, symbol detection, room overlays) against the new engine.

**Recommendation:** ship Phases 0–3 first; measure react-pdf scroll perf on a real 100+ page A1 scan; choose Path A unless it demonstrably can't hold 60fps + bounded memory. Path B is a **separate plan** (it's a viewer-engine migration, not a feature). Either way the only code that changes is `reactPdfAdapter.js` (Task 1.3) + the page-list renderer — the measurement layer is untouched, which is the whole point of the adapter.

The detailed Path-A tasks (virtualizer wiring, DPR cap, cancel/cleanup) mirror the module's `PERFORMANCE_CHECKLIST.md` `[done]` items; write them once the path is chosen.

---

## Self-Review

**Spec coverage** (against the stated goal + research/module):

| Requirement | Covered by |
|---|---|
| Distance / perimeter / area / count tools | Phase 1 (1.1 model, 1.2 overlay, 1.4 toolbar/legend) ✓ |
| Annotations (rect/circle/freehand/text/highlight) | Phase 1.2 (annotation tools in overlay) ✓ |
| Scale calibration (2-point, durable) | Phase 0.2 + Phase 2 ✓ |
| Anisotropic / stretched-scan correctness | Phase 0.1 (`shoelaceAreaM2` separate axes) + 2.1 (separate-axis UI) ✓ |
| Snapping | Phase 1.2 reuses `polygonGeometry.js` ✓ |
| JSON/CSV persistence + export | Phase 3 ✓ |
| 100+ page performance | Phase 4 (gated decision) ✓ |
| Reuse, don't break, the working viewer | Decisions 1–2; takeoffStore signatures preserved (0.3) ✓ |
| Durable scale (fix localStorage-only gap) | Phase 0.2 + 2.1 backend round-trip ✓ |

No gaps for the in-scope viewer. (Interior-finishing upgrades are a *separate* plan — `2026-06-30-interior-finishing-upgrades.md` — not folded in here, per the "previous research plus this" = viewer reading.)

**Placeholder scan:** Phases 0–1.1, 1.3, 2.1 have complete code + tests. The large UI components (1.2 `MeasureOverlay`, 1.4 toolbar) are specified as **JSX ports of named, verified reference files** with their *pure logic* extracted and TDD'd, and explicit browser-verification — this is deliberate (a full SVG component pasted blind would violate the project's "verify UI in a browser" rule), not a TBD. Phase 4 is an explicit decision point, not a placeholder.

**Type/signature consistency:** the scale object shape `{ metersPerPointX, metersPerPointY, calibrated, source }` is identical across `measureGeometry.js`, `durableScale.js`, `measurements.js`, and the calibration modal. `makeMeasurement`/`measurementValue` signatures match between 1.1 and their consumers. `polygonAreaM2(points, pixelsPerMeter)` keeps its legacy signature in 0.3. The adapter's `toPdf`/`toViewport` (1.3) match the names the overlay (1.2) calls.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-30-pdf-takeoff-viewer-integration.md`.**

Recommended order: **Phase 0 → 1 → 2 → 3**, then **decide Phase 4** with a real perf measurement. Phases 0 and the pure-logic tasks are fully TDD'd with `node --test`; the UI tasks need a browser pass on a real project.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks. Best for the TDD tasks in Phases 0–1.
2. **Inline Execution** — work the tasks here with checkpoints.

**One thing I need from you before Phase 4:** the engine decision (Path A virtualize-on-react-pdf vs Path B migrate-to-pdfjs@6). Phases 0–3 don't depend on it — but I won't write Phase 4's detailed tasks until you pick, because Path B is a viewer-engine migration that deserves its own plan.

Which execution approach — and do you want to start with Phase 0?

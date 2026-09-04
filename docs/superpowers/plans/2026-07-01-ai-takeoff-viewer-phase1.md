# AI Takeoff Viewer — Phase 1 Implementation Plan (Make the AI visible + honest)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Draw the app's already-computed interior rooms onto the PDF page as colored, labeled, confidence-flagged zones — turning today's "raw plan + one blue number" into an AI-first takeoff canvas — with bidirectional panel⇄canvas selection and zero new detection.

**Architecture:** The viewer is a **face** over the existing engine (design spec `docs/superpowers/specs/2026-07-01-ai-takeoff-viewer-design.md` §3). A new pure lib (`roomZones.js`) bridges each room's `polygon_pct`/`bbox_pct` → screen pixels (reusing `planOverlayGeometry.js`) and attaches the room's area confidence (reusing `areaConfidence.js`). A new SVG overlay (`RoomZoneLayer.jsx`) renders those descriptors inside `PlanViewer`'s existing relative page container. `InteriorWorkspace` threads the rooms array down and a click-back handler up; `WorkspacePanel` reflects the focused room. No quantity math is added anywhere in the viewer.

**Tech Stack:** React 18 (JSX, not TS), react-pdf/pdfjs-dist@4, plain SVG overlays (mirroring the existing `FillPolygonOverlay` pattern — no Konva), Tailwind, `node --test` for lib unit tests.

---

## Why these boundaries (grounding facts verified in code)

- **The coordinate bridge already exists but was never shown.** `frontend/src/lib/planOverlayGeometry.js:89` `getPolygonPctPoints(polygon, { renderedWidth, renderedHeight })` converts fractional `polygon_pct` → screen pixels; `getBboxPctRect(bbox, renderedSize)` (line 11) does the same for `bbox_pct`. `AiRoomOverlay.jsx` is **not mounted** and filters on `polygon_pdf` (which extraction never produces), so nothing renders today. Phase 1 wires the pct bridge into a visible layer.
- **Confidence logic is audited — reuse it, don't reinvent.** `frontend/src/lib/areaConfidence.js:36` `computeAreaConfidence(room)` returns `{ confidence: 'high'|'medium'|'low'|'unknown', ... }`. Key behavior (verified lines 64-87): a single `eksplikacija` source → **`high`** (deterministic pdfplumber); a single `vision` source → **`low`**; `plotas_m2 == null` → **`unknown`**; `user_verified_at` → **`high`**.
- **Area confidence ≠ location confidence.** Most Objektas A rooms have `plotas_saltinis: 'eksplikacija'` (area is trustworthy → green dot) yet `polygon_source: 'synthesized_from_bbox'` (shape is approximate → dashed border). Encoding these as two axes is the honest core of Phase 1 (spec §9: "never a fabricated polygon").
- **The "Tikrinti pirmiausia" worklist already exists.** `frontend/src/components/project/ReviewQueueSidebar.jsx` (mounted inside `WorkspacePanel.jsx`) already filters low/medium-confidence rooms, sorts them, and calls `onJumpToPage(page, room)`. Phase 1 does **not** rebuild it — it makes those jumps land on a *visible* highlighted zone (via the focused-room path already in `PlanViewer`) and closes the reverse (canvas→panel) direction.
- **The test runner is lib-only.** `frontend/package.json:13` → `"test:units": "node --test src/lib/*.test.js"` (node:test + node:assert/strict). There is **no** component-test harness (no Vitest/Jest). Therefore: **all testable logic lives in `src/lib/` pure functions (TDD there); every JSX/wiring task is verified in the real app** (spec §10 mandates real-`InteriorWorkspace` verification — the lesson from the reverted measurement viewer).

---

## File Structure

**Create:**
- `frontend/src/lib/roomZones.js` — pure helpers: paskirtis→color, confidence→color, `buildRoomZone` (geometry + confidence + approximate flag), `buildPageRoomZones`, `countRoomsMissingGeometry`. The single unit-tested surface of Phase 1.
- `frontend/src/lib/roomZones.test.js` — node:test unit tests for the above.
- `frontend/src/components/project/RoomZoneLayer.jsx` — SVG overlay that renders zone descriptors. Presentation only; imports its logic from `roomZones.js`.

**Modify:**
- `frontend/src/components/project/PlanViewer.jsx` — add `rooms` + `onRoomZoneClick` props; mount `<RoomZoneLayer>` in the page container (after `<Document>`, `PlanViewer.jsx:976`).
- `frontend/src/components/project/InteriorWorkspace.jsx` — pass `rooms` down to `PlanViewer` and add the canvas→panel `onRoomZoneClick` handler; pass `focusedRoomNr` to `WorkspacePanel`.
- `frontend/src/components/project/WorkspacePanel.jsx` — accept `focusedRoomNr`, highlight + scroll the matching room row (completes bidirectional sync, spec §4.6).

**Reuse unchanged:** `planOverlayGeometry.js` (`getPolygonPctPoints`, `getBboxPctRect`), `areaConfidence.js` (`computeAreaConfidence`), `ReviewQueueSidebar.jsx` (worklist), `PlanOverlayLayer` / `getFocusedRoomRect` (existing focused-room marker).

---

## Task 1: `roomZones.js` — color maps (paskirtis + confidence)

**Files:**
- Create: `frontend/src/lib/roomZones.js`
- Test: `frontend/src/lib/roomZones.test.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/roomZones.test.js`:

```js
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  roomZoneColor, confidenceHex, ROOM_ZONE_COLORS, CONFIDENCE_HEX,
} from './roomZones.js';

test('roomZoneColor: known paskirtis → its hue', () => {
  assert.equal(roomZoneColor('miegamoji'), '#3b82f6');
  assert.equal(roomZoneColor('vonia'), '#06b6d4');
  assert.equal(roomZoneColor('virtuve'), '#f59e0b');
});

test('roomZoneColor: unknown / missing paskirtis → default green', () => {
  assert.equal(roomZoneColor('nesamone'), '#10b981');
  assert.equal(roomZoneColor(undefined), '#10b981');
});

test('confidenceHex: maps the four confidence levels', () => {
  assert.equal(confidenceHex('high'), '#16a34a');
  assert.equal(confidenceHex('medium'), '#d97706');
  assert.equal(confidenceHex('low'), '#dc2626');
  assert.equal(confidenceHex('unknown'), '#9ca3af');
});

test('confidenceHex: unrecognised value → unknown grey', () => {
  assert.equal(confidenceHex('bogus'), '#9ca3af');
  assert.equal(confidenceHex(undefined), '#9ca3af');
});

test('color maps are frozen-ish plain objects', () => {
  assert.equal(typeof ROOM_ZONE_COLORS, 'object');
  assert.equal(CONFIDENCE_HEX.high, '#16a34a');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/lib/roomZones.test.js`
Expected: FAIL — `Cannot find module './roomZones.js'`.

- [ ] **Step 3: Write the minimal implementation**

Create `frontend/src/lib/roomZones.js`:

```js
/**
 * roomZones.js — pure helpers that turn extracted patalpos[] rooms into
 * render-ready zone descriptors for the AI Takeoff Viewer's RoomZoneLayer.
 *
 * The viewer is a FACE over the existing engine (design spec 2026-07-01 §3):
 * these functions add NO new quantity math. They only
 *   1. map a room's paskirtis → a stable fill color (identity),
 *   2. bridge polygon_pct / bbox_pct → screen pixels (reusing
 *      planOverlayGeometry — the coordinate bridge that was never wired into a
 *      visible overlay),
 *   3. attach the room's AREA confidence (reusing computeAreaConfidence — the
 *      audited provenance→🟢🟡🔴 logic; spec §5 "do not invent a new one"),
 *   4. flag geometry that is only APPROXIMATE (synthesized from bbox), so the
 *      viewer never draws a fabricated-precise polygon (spec §9).
 */

import { computeAreaConfidence } from './areaConfidence.js';
import { getPolygonPctPoints, getBboxPctRect } from './planOverlayGeometry.js';

// paskirtis → hex. Moved verbatim from AiRoomOverlay (Kreo per-category hues)
// so a glance reveals functional zones without reading labels.
export const ROOM_ZONE_COLORS = {
  gyvenamoji: '#10b981', svetaine: '#10b981',
  miegamoji: '#3b82f6', miegamasis: '#3b82f6', vaikui: '#3b82f6',
  virtuve: '#f59e0b', valgomasis: '#f59e0b',
  vonia: '#06b6d4', vonios: '#06b6d4', wc: '#06b6d4', san: '#06b6d4', sanitarine: '#06b6d4',
  koridorius: '#a78bfa', holas: '#a78bfa', prieskambaris: '#a78bfa',
  drabuzine: '#ec4899', 'rūbinė': '#ec4899',
  sandeliukas: '#94a3b8', saugykla: '#94a3b8', katiline: '#94a3b8', ukio: '#94a3b8',
  garazas: '#64748b', 'tambūras': '#64748b', tamburas: '#64748b',
  balkonas: '#22c55e', terasa: '#22c55e',
};

const DEFAULT_ZONE_COLOR = '#10b981';

export function roomZoneColor(paskirtis) {
  return ROOM_ZONE_COLORS[paskirtis] || DEFAULT_ZONE_COLOR;
}

// confidence → hex for the on-canvas dot + stroke. Matches the app's 🟢🟡🔴
// language and the count-tool prototype's green/amber/red.
export const CONFIDENCE_HEX = {
  high: '#16a34a',
  medium: '#d97706',
  low: '#dc2626',
  unknown: '#9ca3af',
};

export function confidenceHex(confidence) {
  return CONFIDENCE_HEX[confidence] || CONFIDENCE_HEX.unknown;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test src/lib/roomZones.test.js`
Expected: PASS — 5 tests pass.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/lib/roomZones.js src/lib/roomZones.test.js
git commit -m "feat(viewer): roomZones color maps (paskirtis + confidence)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `roomZones.js` — `buildRoomZone` (geometry + confidence + approximate flag)

**Files:**
- Modify: `frontend/src/lib/roomZones.js`
- Test: `frontend/src/lib/roomZones.test.js`

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/lib/roomZones.test.js`:

```js
import { buildRoomZone } from './roomZones.js';

const SIZE = { renderedWidth: 1000, renderedHeight: 800 };

// A real-shaped eksplikacija room WITH a polygon (synthesized from bbox).
const roomPolygon = {
  nr: '102', pavadinimas: 'Svetainė/virtuvė', paskirtis: 'valgomasis',
  puslapio_nr: 2, plotas_m2: 50.54, plotas_saltinis: 'eksplikacija',
  polygon_source: 'synthesized_from_bbox',
  polygon_pct: [[0.1, 0.13], [0.5, 0.13], [0.5, 0.55], [0.1, 0.55]],
  bbox_pct: { x: 0.1, y: 0.13, w: 0.4, h: 0.42 },
};

test('buildRoomZone: polygon_pct → scaled polygon geometry', () => {
  const z = buildRoomZone(roomPolygon, SIZE);
  assert.equal(z.geometry.type, 'polygon');
  assert.deepEqual(z.geometry.points[0], [100, 104]);      // 0.1*1000, 0.13*800
  // NOTE: 0.55*800 === 440.00000000000006 in IEEE-754 — assert X exactly, Y within epsilon.
  assert.equal(z.geometry.points[2][0], 500);              // 0.5*1000
  assert.ok(Math.abs(z.geometry.points[2][1] - 440) < 1e-6);
  assert.equal(z.nr, '102');
  assert.equal(z.label, 'Svetainė/virtuvė');
  assert.equal(z.color, '#f59e0b');                        // valgomasis
});

test('buildRoomZone: eksplikacija area → high confidence, green dot', () => {
  const z = buildRoomZone(roomPolygon, SIZE);
  assert.equal(z.confidence, 'high');                      // single eksplikacija source
  assert.equal(z.confidenceColor, '#16a34a');
  assert.equal(z.areaLabel, '50,5 m²');                    // lt-LT, 1 decimal
});

test('buildRoomZone: synthesized polygon is flagged approximate', () => {
  const z = buildRoomZone(roomPolygon, SIZE);
  assert.equal(z.approximate, true);                       // polygon_source synthesized
});

test('buildRoomZone: real/manual polygon is NOT approximate', () => {
  const z = buildRoomZone({ ...roomPolygon, polygon_source: 'manual' }, SIZE);
  assert.equal(z.approximate, false);
});

test('buildRoomZone: no polygon → bbox rect fallback, always approximate', () => {
  const z = buildRoomZone({
    nr: '101', pavadinimas: 'Tambūras', paskirtis: 'tamburas',
    puslapio_nr: 2, plotas_m2: 11.01, plotas_saltinis: 'eksplikacija',
    bbox_pct: { x: 0.1, y: 0.13, w: 0.4, h: 0.42 },
  }, SIZE);
  assert.equal(z.geometry.type, 'rect');
  assert.equal(z.geometry.left, 100);
  assert.equal(z.geometry.width, 400);
  assert.equal(z.approximate, true);
  assert.equal(z.color, '#64748b');                        // tamburas
});

test('buildRoomZone: vision-sourced area → low confidence (red)', () => {
  const z = buildRoomZone({
    nr: '9', pavadinimas: 'X', paskirtis: 'gyvenamoji', puslapio_nr: 2,
    plotas_m2: 20, plotas_source: 'vision',
    polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
  }, SIZE);
  assert.equal(z.confidence, 'low');
  assert.equal(z.confidenceColor, '#dc2626');
});

test('buildRoomZone: no geometry at all → null', () => {
  const z = buildRoomZone({ nr: '5', plotas_m2: 9, puslapio_nr: 2 }, SIZE);
  assert.equal(z, null);
});

test('buildRoomZone: missing render size → null', () => {
  assert.equal(buildRoomZone(roomPolygon, { renderedWidth: 0, renderedHeight: 0 }), null);
  assert.equal(buildRoomZone(null, SIZE), null);
});

test('buildRoomZone: plotas_m2 null → unknown confidence, empty areaLabel', () => {
  const z = buildRoomZone({
    nr: '7', paskirtis: 'vonia', puslapio_nr: 2,
    polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
  }, SIZE);
  assert.equal(z.confidence, 'unknown');
  assert.equal(z.confidenceColor, '#9ca3af');
  assert.equal(z.areaLabel, '');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/lib/roomZones.test.js`
Expected: FAIL — `buildRoomZone is not a function` (not yet exported).

- [ ] **Step 3: Write the minimal implementation**

Append to `frontend/src/lib/roomZones.js`:

```js
// polygon_source values that mean "we approximated the shape" → dashed border.
const APPROXIMATE_POLYGON_SOURCES = new Set([
  'synthesized_from_bbox', 'bbox_fallback', 'manual_needed',
]);

/**
 * buildRoomZone — one room → a render-ready descriptor, or null if the room
 * has no geometry we can honestly place on the plan.
 *
 * geometry is one of:
 *   { type: 'polygon', points: [[x,y], …] }   // from polygon_pct
 *   { type: 'rect', left, top, width, height } // from bbox_pct fallback
 * `approximate` is true when the shape is synthesized (dashed border in the UI).
 */
export function buildRoomZone(room, { renderedWidth, renderedHeight } = {}) {
  if (!room || !renderedWidth || !renderedHeight) return null;

  let geometry = null;
  let approximate = false;

  const polyPoints = getPolygonPctPoints(room.polygon_pct, { renderedWidth, renderedHeight });
  if (polyPoints) {
    geometry = { type: 'polygon', points: polyPoints };
    approximate = APPROXIMATE_POLYGON_SOURCES.has(room.polygon_source);
  } else {
    const rect = getBboxPctRect(room.bbox_pct, { width: renderedWidth, height: renderedHeight });
    if (rect) {
      geometry = { type: 'rect', ...rect };
      approximate = true; // a bbox rectangle is never an exact room outline
    }
  }

  if (!geometry) return null;

  const { confidence } = computeAreaConfidence(room);
  const area = Number.isFinite(room.plotas_m2) ? room.plotas_m2 : null;

  return {
    nr: room.nr,
    label: room.pavadinimas || `#${room.nr}`,
    areaLabel: area != null
      ? `${area.toLocaleString('lt-LT', { maximumFractionDigits: 1 })} m²`
      : '',
    paskirtis: room.paskirtis || null,
    color: roomZoneColor(room.paskirtis),
    confidence,
    confidenceColor: confidenceHex(confidence),
    approximate,
    geometry,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test src/lib/roomZones.test.js`
Expected: PASS — all Task 1 + Task 2 tests pass.

Note: `'50,5 m²'` uses the comma decimal separator from `toLocaleString('lt-LT', …)`. Node ships full ICU, so this matches. If a stripped-ICU Node build is ever used the separator could differ — if that specific assertion fails, confirm `node -e "console.log((1.5).toLocaleString('lt-LT'))"` prints `1,5` before touching the implementation.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/lib/roomZones.js src/lib/roomZones.test.js
git commit -m "feat(viewer): buildRoomZone (pct/bbox geometry + area confidence + approximate flag)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `roomZones.js` — page selection (`buildPageRoomZones`, `countRoomsMissingGeometry`)

**Files:**
- Modify: `frontend/src/lib/roomZones.js`
- Test: `frontend/src/lib/roomZones.test.js`

- [ ] **Step 1: Write the failing test**

Append to `frontend/src/lib/roomZones.test.js`:

```js
import { buildPageRoomZones, countRoomsMissingGeometry } from './roomZones.js';

const poly = (nr, page) => ({
  nr, pavadinimas: `R${nr}`, paskirtis: 'gyvenamoji',
  puslapio_nr: page, plotas_m2: 10, plotas_saltinis: 'eksplikacija',
  polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
});
const noGeom = (nr, page) => ({ nr, puslapio_nr: page, plotas_m2: 8 });

test('buildPageRoomZones: keeps only current-page drawable rooms', () => {
  const rooms = [poly('1', 2), poly('2', 3), noGeom('3', 2)];
  const zones = buildPageRoomZones(rooms, { renderedWidth: 1000, renderedHeight: 800, page: 2 });
  assert.equal(zones.length, 1);        // room 2 is page 3, room 3 has no geometry
  assert.equal(zones[0].nr, '1');
});

test('buildPageRoomZones: honours page_nr as well as puslapio_nr', () => {
  const rooms = [{ ...poly('4', undefined), page_nr: 5, puslapio_nr: undefined }];
  const zones = buildPageRoomZones(rooms, { renderedWidth: 1000, renderedHeight: 800, page: 5 });
  assert.equal(zones.length, 1);
});

test('buildPageRoomZones: non-array / empty → []', () => {
  assert.deepEqual(buildPageRoomZones(null, { renderedWidth: 1000, renderedHeight: 800, page: 2 }), []);
  assert.deepEqual(buildPageRoomZones([], { renderedWidth: 1000, renderedHeight: 800, page: 2 }), []);
});

test('countRoomsMissingGeometry: counts current-page rooms we cannot place', () => {
  const rooms = [poly('1', 2), noGeom('3', 2), noGeom('4', 3)];
  const n = countRoomsMissingGeometry(rooms, { renderedWidth: 1000, renderedHeight: 800, page: 2 });
  assert.equal(n, 1);                   // only room 3 (page 2, no geometry)
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/lib/roomZones.test.js`
Expected: FAIL — `buildPageRoomZones is not a function`.

- [ ] **Step 3: Write the minimal implementation**

Append to `frontend/src/lib/roomZones.js`:

```js
function roomPage(room) {
  return room?.page_nr ?? room?.puslapio_nr ?? null;
}

/**
 * buildPageRoomZones — all rooms on `page` that CAN be drawn, as descriptors.
 * Rooms without geometry are dropped here (they still surface in the review
 * worklist and in countRoomsMissingGeometry).
 */
export function buildPageRoomZones(rooms, { renderedWidth, renderedHeight, page }) {
  if (!Array.isArray(rooms)) return [];
  return rooms
    .filter((r) => roomPage(r) === page)
    .map((r) => buildRoomZone(r, { renderedWidth, renderedHeight }))
    .filter(Boolean);
}

/**
 * countRoomsMissingGeometry — rooms on `page` we could NOT place on the plan.
 * Surfaced as an honest "N patalpų be vietos plane" chip (spec §9), never hidden.
 */
export function countRoomsMissingGeometry(rooms, { renderedWidth, renderedHeight, page }) {
  if (!Array.isArray(rooms)) return 0;
  return rooms
    .filter((r) => roomPage(r) === page)
    .filter((r) => !buildRoomZone(r, { renderedWidth, renderedHeight }))
    .length;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && node --test src/lib/roomZones.test.js`
Expected: PASS — all Task 1-3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/lib/roomZones.js src/lib/roomZones.test.js
git commit -m "feat(viewer): page-scoped room-zone selection + missing-geometry count

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `RoomZoneLayer.jsx` — SVG overlay component

**Files:**
- Create: `frontend/src/components/project/RoomZoneLayer.jsx`

There is no component-test runner in this repo (see grounding facts), so this task is **verified in the real app** in Task 6, not unit-tested. Keep all logic in `roomZones.js` (already tested); this file is presentation only.

- [ ] **Step 1: Write the component**

Create `frontend/src/components/project/RoomZoneLayer.jsx`:

```jsx
/**
 * RoomZoneLayer — the AI Takeoff Viewer's first visible layer (Phase 1).
 *
 * Draws the app's ALREADY-COMPUTED rooms onto the PDF page as translucent SVG
 * zones: paskirtis-colored fill (identity) + name + area label + a confidence
 * dot (honesty). Synthesized/bbox geometry gets a DASHED border + "apytikslė"
 * so the viewer never fakes a precise outline (design spec §9).
 *
 * A FACE over the engine — no quantity math here. Geometry + confidence come
 * from lib/roomZones (which reuses planOverlayGeometry + areaConfidence).
 *
 * Pattern mirrors FillPolygonOverlay: an absolutely-positioned SVG with
 * pointer-events:none, and pointer-events:auto only on each <g>, so clicks land
 * on zones and pass THROUGH the gaps to the PDF / pan handler underneath.
 */

import { useMemo } from 'react';
import { buildPageRoomZones, countRoomsMissingGeometry } from '@/lib/roomZones';

function centroidOf(geometry) {
  if (geometry.type === 'rect') {
    return {
      cx: geometry.left + geometry.width / 2,
      cy: geometry.top + geometry.height / 2,
    };
  }
  const xs = geometry.points.map((p) => p[0]);
  const ys = geometry.points.map((p) => p[1]);
  return {
    cx: (Math.min(...xs) + Math.max(...xs)) / 2,
    cy: (Math.min(...ys) + Math.max(...ys)) / 2,
  };
}

export default function RoomZoneLayer({
  rooms = [],
  page,
  renderedSize,
  focusedRoomNr = null,
  onRoomClick = null,
}) {
  const width = renderedSize?.width;
  const height = renderedSize?.height;

  const zones = useMemo(() => {
    if (!width || !height) return [];
    return buildPageRoomZones(rooms, { renderedWidth: width, renderedHeight: height, page });
  }, [rooms, page, width, height]);

  const missingCount = useMemo(() => {
    if (!width || !height) return 0;
    return countRoomsMissingGeometry(rooms, { renderedWidth: width, renderedHeight: height, page });
  }, [rooms, page, width, height]);

  if (!width || !height) return null;
  if (zones.length === 0 && missingCount === 0) return null;

  return (
    <svg
      width={width}
      height={height}
      className="absolute left-0 top-0 z-[16]"
      style={{ pointerEvents: 'none' }}
    >
      {zones.map((z) => {
        const isFocused = focusedRoomNr != null && String(z.nr) === String(focusedRoomNr);
        const { cx, cy } = centroidOf(z.geometry);
        const strokeW = isFocused ? 3.5 : 2;
        const fillOpacity = isFocused ? 0.34 : 0.18;
        const dash = z.approximate ? '6 4' : undefined;

        return (
          <g
            key={z.nr}
            style={{ pointerEvents: 'auto', cursor: onRoomClick ? 'pointer' : 'default' }}
            onClick={() => onRoomClick?.(z)}
          >
            {z.geometry.type === 'polygon' ? (
              <polygon
                points={z.geometry.points.map((p) => `${p[0]},${p[1]}`).join(' ')}
                fill={z.color}
                fillOpacity={fillOpacity}
                stroke={z.color}
                strokeWidth={strokeW}
                strokeDasharray={dash}
              />
            ) : (
              <rect
                x={z.geometry.left}
                y={z.geometry.top}
                width={z.geometry.width}
                height={z.geometry.height}
                rx={3}
                fill={z.color}
                fillOpacity={fillOpacity}
                stroke={z.color}
                strokeWidth={strokeW}
                strokeDasharray={dash}
              />
            )}

            {/* Label chip: white bg, confidence dot, name + area */}
            <g transform={`translate(${cx}, ${cy})`}>
              <rect
                x={-58} y={-17} width={116} height={34} rx={4}
                fill="white" stroke={z.color} strokeWidth={1} opacity={0.96}
              />
              <circle cx={-48} cy={-6} r={4} fill={z.confidenceColor}>
                <title>{`Ploto pasitikėjimas: ${z.confidence}`}</title>
              </circle>
              <text
                x={-40} y={-2} fontSize={11} fontWeight="700" fill="#1f2937"
                style={{ pointerEvents: 'none' }}
              >
                {z.label.length > 12 ? `${z.label.slice(0, 11)}…` : z.label}
              </text>
              <text
                x={-40} y={11} fontSize={10} fill={z.color}
                style={{ pointerEvents: 'none' }}
              >
                {z.areaLabel}{z.approximate ? ' · apytikslė vieta' : ''}
              </text>
            </g>
          </g>
        );
      })}

      {/* Honest "we could not place these" chip (spec §9) */}
      {missingCount > 0 && (
        <g transform="translate(12, 12)" style={{ pointerEvents: 'none' }}>
          <rect x={0} y={0} width={250} height={24} rx={5}
            fill="#fef3c7" stroke="#fde68a" strokeWidth={1} />
          <text x={10} y={16} fontSize={11} fill="#b45309">
            {missingCount} patalpų be vietos plane — žr. „Peržiūra“
          </text>
        </g>
      )}
    </svg>
  );
}
```

- [ ] **Step 2: Verify it compiles (no runtime mount yet)**

Run: `cd frontend && npx vite build 2>&1 | tail -5` (or rely on the dev server's HMR having no import/parse error).
Expected: build succeeds; the module imports `@/lib/roomZones` without error. (No visual change yet — the component is not mounted until Task 5.)

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/components/project/RoomZoneLayer.jsx
git commit -m "feat(viewer): RoomZoneLayer SVG overlay (zones + confidence dot + approximate dash)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Mount `RoomZoneLayer` in `PlanViewer`

**Files:**
- Modify: `frontend/src/components/project/PlanViewer.jsx` (props block `:206-216`; page container after `<Document>` `:976`)

- [ ] **Step 1: Import the component**

At the top of `PlanViewer.jsx`, with the other component imports, add:

```jsx
import RoomZoneLayer from './RoomZoneLayer';
```

- [ ] **Step 2: Add the two new props**

In the `PlanViewer` props destructure (currently `PlanViewer.jsx:206-216`), add `rooms` and `onRoomZoneClick`:

```jsx
export default function PlanViewer({
  fileUrl,
  pdfFile = null,
  onSymbolCountResult = null,
  onRoomPolygonFill = null,
  pageMeta = {},
  missingTypes = [],
  focusedPage = null,
  focusedRoom = null,
  eksplikacija_source_page = null,
  rooms = [],
  onRoomZoneClick = null,
}) {
```

- [ ] **Step 3: Mount the layer inside the page container**

In the relative page container, immediately AFTER the closing `</Document>` tag (`PlanViewer.jsx:976`) and BEFORE the `{symbolPickMode && (` block, insert:

```jsx
                {renderedSize && rooms.length > 0 && (
                  <RoomZoneLayer
                    rooms={rooms}
                    page={pageNumber}
                    renderedSize={renderedSize}
                    focusedRoomNr={focusedRoom?.nr ?? null}
                    onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: pageNumber })}
                  />
                )}
```

Placement rationale: DOM order after `<Document>` but before the symbol-pick (`z-30`), symbol overlay (`z-25`), and focused-marker (`z-20`) blocks; the layer's own `z-[16]` keeps zones beneath the blue focused-room number marker so both read together (zone border + number circle). `renderedSize` is already the page-identity-guarded size (`PlanViewer.jsx:310-312`).

- [ ] **Step 4: Verify it compiles**

Run: `cd frontend && npx vite build 2>&1 | tail -5`
Expected: build succeeds. Visual verification happens in Task 6 (rooms are not yet passed in from `InteriorWorkspace`, so nothing renders until then — the `rooms.length > 0` guard keeps it inert).

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/components/project/PlanViewer.jsx
git commit -m "feat(viewer): mount RoomZoneLayer in PlanViewer (rooms + onRoomZoneClick props)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Wire `InteriorWorkspace` — feed rooms + canvas→panel selection

**Files:**
- Modify: `frontend/src/components/project/InteriorWorkspace.jsx` (`<PlanViewer …>` at `:303-348`)

- [ ] **Step 1: Pass `rooms` and `onRoomZoneClick` to `PlanViewer`**

In the `<PlanViewer …>` element (`InteriorWorkspace.jsx:303`), add two props alongside the existing ones (e.g. right after `focusedRoom={effectiveFocusedRoom}`):

```jsx
            rooms={project?.v8_rooms || project?.patalpos || []}
            onRoomZoneClick={(room) => {
              // Canvas → panel: selecting a zone focuses that room. We already
              // are on its page (zones are page-filtered), so puslapio_nr is the
              // current page. effectiveFocusedRoom (line ~114) re-derives the
              // full room from the live patalpos by nr, so {nr, puslapio_nr} is
              // enough to drive both the canvas marker and the panel highlight.
              if (room?.puslapio_nr) setLocalFocusedPage(room.puslapio_nr);
              setLocalFocusedRoom(room);
              onJumpToPage?.(room.puslapio_nr, room);
            }}
```

(`setLocalFocusedPage`, `setLocalFocusedRoom`, and `onJumpToPage` are already in scope — the existing `WorkspacePanel` `onJumpToPage` handler at `InteriorWorkspace.jsx:421-426` uses the same three.)

- [ ] **Step 2: Real-app verification — the core Phase 1 gate**

This is the mandatory real-`InteriorWorkspace` check (spec §10). Use the running dev server and a real logged-in project (the contractor-validated **Objektas A** fixture — memory `project_contractor_pdf_fixture`).

1. Start/confirm the frontend dev server (`cd frontend && npm run dev`) and the backend, and log in.
2. Open the Objektas A interior project → **Brėžinys** tab → `InteriorWorkspace`.
3. Confirm on the floor-plan page:
   - [ ] Rooms appear as translucent colored zones with a white label chip (name + area). Colors differ by paskirtis (e.g. miegamasis blue, vonia cyan, virtuvė amber).
   - [ ] Each chip has a confidence dot: **green** for eksplikacija-sourced areas; amber/red only where the room is medium/low.
   - [ ] Rooms whose polygon is synthesized show a **dashed** border and "· apytikslė vieta".
   - [ ] If any room on the page has no geometry, the amber "N patalpų be vietos plane" chip shows top-left; the count matches how many rooms are listed for that page but not drawn.
   - [ ] Zone positions align to the drawn rooms (not offset/transposed). If a page is `/Rotate 90|270`, confirm alignment still holds (the viewport-based `pageSize` already handles rotation).
4. **Bidirectional sync (canvas → panel):** click a room zone → the panel's matching room row does NOT yet highlight (that's Task 7), but the blue focused-room marker should appear on the clicked room and the page should stay put.
5. **Bidirectional sync (panel → canvas):** click a room row in the panel (and a row in the "Peržiūra"/ReviewQueueSidebar worklist) → the viewer jumps to its page and the zone shows the focused (thicker) border + blue marker.
6. **Pan still works:** drag from empty canvas space to pan; clicking inside a room selects it rather than panning (acceptable Phase 1 behavior — note if it feels wrong).

Record the outcome honestly in the commit message / handoff. If zones are misaligned, STOP and diagnose the coordinate path (`getPolygonPctPoints` expects fractional 0–1 `polygon_pct`; if the data is absolute PDF points the room would have `polygon_pdf` instead — that is out of Phase 1 scope and should be logged, not hacked around).

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/components/project/InteriorWorkspace.jsx
git commit -m "feat(viewer): feed rooms to PlanViewer + canvas→panel room focus

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Reflect focused room in the panel (complete bidirectional sync)

**Files:**
- Modify: `frontend/src/components/project/InteriorWorkspace.jsx` (`<WorkspacePanel …>` at `:420`)
- Modify: `frontend/src/components/project/WorkspacePanel.jsx` (signature `:88`; room row `:280-327`)

- [ ] **Step 1: Pass the focused room nr into `WorkspacePanel`**

In `InteriorWorkspace.jsx`, add a prop to the `<WorkspacePanel …>` element (`:420`):

```jsx
          focusedRoomNr={effectiveFocusedRoom?.nr ?? null}
```

- [ ] **Step 2: Accept the prop and highlight + scroll the matching row**

In `WorkspacePanel.jsx`, extend the signature (`:88`):

```jsx
export default function WorkspacePanel({ project, onJumpToPage, onJumpToProvenance, onProjectChange, focusedRoomNr = null }) {
```

Add a ref for the focused row near the other hooks (after the `useState`/`useMemo` block, before `return`):

```jsx
  const focusedRowRef = useRef(null);
  useEffect(() => {
    if (focusedRoomNr != null && focusedRowRef.current) {
      focusedRowRef.current.scrollIntoView({ block: 'nearest' });
    }
  }, [focusedRoomNr]);
```

Ensure `useRef` and `useEffect` are imported (the file already imports `useState, useMemo, useEffect, useCallback, memo` — add `useRef`):

```jsx
import { useState, useMemo, useEffect, useCallback, memo, useRef } from 'react';
```

In the room-row map (`WorkspacePanel.jsx:280-294`), mark and style the focused row. Replace the `<div key={...} onClick=...>` opening with:

```jsx
        {!collapsed.rooms && filteredRooms.map((r, i) => {
          const targetPage = r.puslapio_nr ?? r.page_nr;
          const canJump = !!(onJumpToPage && targetPage);
          const isWet = WET_PASKIRTYS.has((r.paskirtis || '').toLowerCase());
          const isFocused = focusedRoomNr != null && String(r.nr) === String(focusedRoomNr);
          return (
            <div
              key={`${r.nr}-${i}`}
              ref={isFocused ? focusedRowRef : undefined}
              onClick={canJump ? () => onJumpToPage(targetPage, r) : undefined}
              className="row-hover-halo grid items-center cursor-pointer transition-colors"
              style={{
                gridTemplateColumns: '24px 1fr auto',
                gap: 8, padding: '6px 12px', fontSize: 12,
                borderBottom: '1px solid hsl(var(--border) / 0.5)',
                background: isFocused ? 'hsl(var(--primary) / 0.10)' : undefined,
                boxShadow: isFocused ? 'inset 3px 0 0 hsl(var(--primary))' : undefined,
              }}
              title={canJump ? `Atidaryti psl. ${targetPage}` : undefined}
            >
```

(The rest of the row body — the `nr` span, name, wet badge, `ConfidenceBadge`, area — is unchanged.)

- [ ] **Step 3: Real-app verification**

On the Objektas A project in `InteriorWorkspace`:
- [ ] Click a room zone on the canvas → the matching room row in the panel now highlights (left accent bar + tint) and scrolls into view.
- [ ] Click a panel room row → the canvas focuses that zone (Task 6 behavior) AND the row stays highlighted — selection is consistent in both directions.
- [ ] Press `Esc` (existing behavior) clears the canvas marker; confirm the panel highlight is acceptable to leave until another room is selected (no crash / no stuck state).

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/components/project/WorkspacePanel.jsx src/components/project/InteriorWorkspace.jsx
git commit -m "feat(viewer): highlight focused room row in panel (bidirectional sync)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Full-slice acceptance on the ground-truth fixture

**Files:** none (verification + any small fixes surfaced).

- [ ] **Step 1: Run the whole lib test suite**

Run: `cd frontend && npm run test:units`
Expected: PASS — all `src/lib/*.test.js` including the new `roomZones.test.js`; no regressions in `areaConfidence.test.js` or `planOverlayGeometry`-related tests.

- [ ] **Step 2: Ground-truth visual acceptance (spec §10)**

On Objektas A in the real `InteriorWorkspace`:
- [ ] The displayed room areas match the žiniaraštis / panel values (the viewer shows the SAME numbers the engine already computed — no parallel math). Spot-check a couple of rooms' `m²` chip vs the panel row.
- [ ] Confidence flags are correct: eksplikacija rooms = green dot; any vision-only or disagreeing rooms = amber/red and also present in the "Peržiūra" worklist.
- [ ] Synthesized-polygon rooms are dashed; nothing is presented as a precise polygon that isn't.
- [ ] Navigate pages (`[` / `]`): zones re-render for the correct page only; no ghost zones from the previous page (the `renderedSize` page-identity guard + `page` filter cover this — confirm visually).
- [ ] Zoom in/out (`+` / `-` or Ctrl-wheel): zones scale with the page and stay aligned.

- [ ] **Step 3: Honest disclosure of anything unverified**

If any check could not be run (e.g. no vision-only room exists in this fixture to prove the red path, or a rotated page wasn't available), state that explicitly in the handoff rather than implying full coverage. Note any follow-ups (e.g. consolidating `ReviewQueueSidebar`'s raw `room.confidence` onto `computeAreaConfidence` for a single confidence source of truth — deferred to Phase 2).

- [ ] **Step 4: Update memory**

Add a short memory note (`project_ai_takeoff_viewer_phase1.md` + `MEMORY.md` pointer) recording: Phase 1 shipped (RoomZoneLayer mounted, pct/bbox bridge live, confidence dots + approximate dashing, bidirectional sync), the two-axis honesty encoding (area confidence vs location approximation), and the deferred Phase-2 confidence-source consolidation. Link `[[project_pdf_takeoff_viewer_module]]` and `[[project_contractor_pdf_fixture]]`.

---

## Self-review notes (checked against the spec)

- **Spec §4.1 one-click seed / §7 Phase-1 "colored zones + area labels"** → Tasks 4-6 (RoomZoneLayer renders on project open; no explicit "Analizuoti" click needed since data is already extracted).
- **§4.2 honest confidence on the drawing + "Tikrinti pirmiausia" worklist** → confidence dot (Task 2/4); worklist reused, not rebuilt (ReviewQueueSidebar) with its jump now landing on a visible zone (Task 6 step 2.5).
- **§4.6 / §7 bidirectional sync** → panel→canvas (existing focusedRoom path, Task 6), canvas→panel focus (Task 6) + panel row highlight (Task 7).
- **§5 "reuse coordinate bridge / confidence / no new math"** → `getPolygonPctPoints` + `getBboxPctRect` + `computeAreaConfidence` reused; no new quantities.
- **§9 room-with-no-geometry = bbox+label, never fabricated polygon; missing ones surfaced** → bbox fallback is dashed + "apytikslė"; `countRoomsMissingGeometry` chip (Task 3/4).
- **§10 lib unit tests for the coordinate bridge + confidence + synthesized-flag; mandatory real-app verification** → Tasks 1-3 (node:test) + Tasks 6-8 (real `InteriorWorkspace`, Objektas A).
- **§6 "lead with surfacing, NOT auto-tracing; no new detection"** → confirmed: Phase 1 only renders already-computed data. Detection/correction/counter are Phases 2-4, out of scope here.
- **Method-name consistency:** `buildRoomZone` / `buildPageRoomZones` / `countRoomsMissingGeometry` / `roomZoneColor` / `confidenceHex` used identically across lib, tests, and `RoomZoneLayer`. `onRoomZoneClick` (PlanViewer prop) ↔ `onRoomClick` (RoomZoneLayer prop) mapping is explicit in Task 5 step 3.
- **No placeholders:** every code step shows complete code; every run step shows the command + expected result.

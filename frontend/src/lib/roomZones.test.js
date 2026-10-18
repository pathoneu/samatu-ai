import test from 'node:test';
import assert from 'node:assert/strict';
import {
  roomTypeWord, ROOM_TYPE_WORDS, areaConfidenceText,
} from './roomZones.js';

// v3 overlay vocabulary (founder decision 2026-10-18): zones share one neutral tint — the room type
// is a WORD in the label, never a hue; area confidence is a sentence, never a coloured dot.
test('roomTypeWord: known paskirtis → its word', () => {
  assert.equal(roomTypeWord('miegamoji'), 'miegamasis');
  assert.equal(roomTypeWord('vonia'), 'vonia');
  assert.equal(roomTypeWord('virtuve'), 'virtuvė');
  assert.equal(roomTypeWord('tambūras'), 'tambūras');
});

test('roomTypeWord: unknown / missing paskirtis → null (the label just leaves it out)', () => {
  assert.equal(roomTypeWord('nesamone'), null);
  assert.equal(roomTypeWord(undefined), null);
});

test('no colour is left in the room-type map', () => {
  for (const word of Object.values(ROOM_TYPE_WORDS)) assert.doesNotMatch(word, /^#|rgb|hsl/);
});

test('areaConfidenceText: only an area that needs a look says something', () => {
  assert.equal(areaConfidenceText('high'), null);
  assert.equal(areaConfidenceText('medium'), 'plotą verta patikrinti');
  assert.equal(areaConfidenceText('low'), 'plotą būtina patikrinti');
  assert.equal(areaConfidenceText('unknown'), 'plotas nežinomas');
  assert.equal(areaConfidenceText(undefined), null);
});

import { buildRoomZone } from './roomZones.js';

const SIZE = { renderedWidth: 1000, renderedHeight: 800 };

// A real-shaped eksplikacija room WITH a REAL traced polygon (flood-fill).
// (Only a source NOT in NON_TRACED_SOURCES renders as a solid Tier-1 polygon.)
const roomPolygon = {
  nr: '102', pavadinimas: 'Svetainė/virtuvė', paskirtis: 'valgomasis',
  puslapio_nr: 2, plotas_m2: 50.54, plotas_saltinis: 'eksplikacija',
  polygon_source: 'auto_floodfill',
  polygon_pct: [[0.1, 0.13], [0.5, 0.13], [0.5, 0.55], [0.1, 0.55]],
  bbox_pct: { x: 0.1, y: 0.13, w: 0.4, h: 0.42 },
};

test('buildRoomZone: polygon_pct → scaled polygon geometry', () => {
  const z = buildRoomZone(roomPolygon, SIZE);
  assert.equal(z.geometry.type, 'polygon');
  assert.deepEqual(z.geometry.points[0], [100, 104]);      // 0.1*1000, 0.13*800
  // 0.55*800 is not exact in IEEE-754 (== 440.00000000000006); assert.equal
  // uses SameValueZero (exact numeric compare) same as deepEqual would, so we
  // compare with a tolerance instead of a literal 440.
  assert.equal(z.geometry.points[2][0], 500);               // 0.5*1000
  assert.ok(Math.abs(z.geometry.points[2][1] - 440) < 1e-9); // 0.55*800
  assert.equal(z.nr, '102');
  assert.equal(z.label, 'Svetainė/virtuvė');
  assert.equal(z.typeWord, 'valgomasis');                  // the type is a word, not a hue
  assert.equal(z.color, undefined);
});

test('buildRoomZone: eksplikacija area → high confidence, nothing to say about it', () => {
  const z = buildRoomZone(roomPolygon, SIZE);
  assert.equal(z.confidence, 'high');                      // single eksplikacija source
  assert.equal(z.confidenceText, null);
  assert.equal(z.areaLabel, '50,54 m²');                   // lt-LT, 2 decimals — as the room list prints it
});

test('buildRoomZone: outline kind follows the source — flood fill is an estimate (dashed)', () => {
  assert.equal(buildRoomZone(roomPolygon, SIZE).outline, 'estimated');
  assert.equal(buildRoomZone({ ...roomPolygon, polygon_source: 'vektoriniai_konturai' }, SIZE).outline, 'read');
  assert.equal(buildRoomZone({ ...roomPolygon, polygon_source: 'corrected' }, SIZE).outline, 'confirmed');
});

test('buildRoomZone: traced flood-fill polygon is NOT approximate', () => {
  const z = buildRoomZone(roomPolygon, SIZE);
  assert.equal(z.geometry.type, 'polygon');
  assert.equal(z.approximate, false);                      // real traced outline
});

test('buildRoomZone: real/manual polygon is NOT approximate', () => {
  const z = buildRoomZone({ ...roomPolygon, polygon_source: 'manual' }, SIZE);
  assert.equal(z.approximate, false);
});

test('buildRoomZone: synthesized_from_bbox polygon is a fake rect → not traced', () => {
  // A synthesized polygon is a fabricated coarse rectangle; with no label anchor
  // it is NEVER drawn (no solid zone, no rect) — the room falls to Tier 3 (null).
  const z = buildRoomZone(
    { ...roomPolygon, polygon_source: 'synthesized_from_bbox' }, SIZE);
  assert.equal(z, null);
});

test('buildRoomZone: synthesized_from_bbox WITH marker_pct → null (floating markers dropped, be9221a)', () => {
  // NON_TRACED_SOURCES seeds often matched the eksplikacija number column, not
  // the on-plan label — a marker there floats in empty space. Suppressed since
  // be9221a: these rooms fall to the honest "be vietos" chip instead.
  const z = buildRoomZone(
    { ...roomPolygon, polygon_source: 'synthesized_from_bbox', marker_pct: [0.3, 0.4] }, SIZE);
  assert.equal(z, null);
});

test('buildRoomZone: no polygon, only bbox (no anchor) → null (no rect fallback)', () => {
  const z = buildRoomZone({
    nr: '101', pavadinimas: 'Tambūras', paskirtis: 'tamburas',
    puslapio_nr: 2, plotas_m2: 11.01, plotas_saltinis: 'eksplikacija',
    bbox_pct: { x: 0.1, y: 0.13, w: 0.4, h: 0.42 },
  }, SIZE);
  assert.equal(z, null);                                   // bbox-centroid marker is banned
});

test('buildRoomZone: vision-sourced area → low confidence (red)', () => {
  const z = buildRoomZone({
    nr: '9', pavadinimas: 'X', paskirtis: 'gyvenamoji', puslapio_nr: 2,
    plotas_m2: 20, plotas_source: 'vision',
    polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]],
  }, SIZE);
  assert.equal(z.confidence, 'low');
  assert.equal(z.confidenceText, 'plotą būtina patikrinti');
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
  assert.equal(z.confidenceText, 'plotas nežinomas');
  assert.equal(z.areaLabel, '');
});

// ── Three-tier geometry (Task C1): traced polygon / located marker / null ──
// markerCenter is label-anchored ONLY: marker_pct || label_pct. A bbox WITHOUT
// an anchor never produces a marker (bbox-centroid markers = "marked random
// places" on furnished plans) — that room falls to the Tier-3 "be vietos" chip.

test('C1(a): real auto_floodfill polygon → solid polygon tier, not approximate', () => {
  const z = buildRoomZone(
    { nr: '101', polygon_pct: [[0.1, 0.1], [0.3, 0.1], [0.3, 0.3]], polygon_source: 'auto_floodfill' },
    { renderedWidth: 1000, renderedHeight: 1000 });
  assert.equal(z.geometry.type, 'polygon');
  assert.equal(z.approximate, false);
});

test('C1(b): manual_needed with marker_pct → null (floating markers dropped, be9221a)', () => {
  const z = buildRoomZone(
    { nr: '108', polygon_source: 'manual_needed', marker_pct: [0.55, 0.30] },
    { renderedWidth: 1000, renderedHeight: 2000 });
  assert.equal(z, null);
});

test('C1(c): manual_needed with label_pct → null (floating markers dropped, be9221a)', () => {
  const z = buildRoomZone(
    { nr: '109', polygon_source: 'manual_needed', label_pct: [0.40, 0.25] },
    { renderedWidth: 1000, renderedHeight: 2000 });
  assert.equal(z, null);
});

test('C1(b2): NO polygon_source with marker_pct → tier-2 marker at the printed label', () => {
  // Tier 2 stays reachable when the source is not a known-bad seed.
  const z = buildRoomZone(
    { nr: '108', marker_pct: [0.55, 0.30] },
    { renderedWidth: 1000, renderedHeight: 2000 });
  assert.equal(z.geometry.type, 'marker');
  assert.deepEqual([z.geometry.cx, z.geometry.cy], [550, 600]);  // 0.55*1000, 0.30*2000
  assert.equal(z.approximate, true);
  assert.equal(z.outline, 'marker');                               // only the number — no outline to style
});

test('C1(d): synthesized_from_bbox with only bbox_pct (no anchor) → null (Tier 3)', () => {
  const z = buildRoomZone(
    { nr: '102',
      polygon_pct: [[0.1, 0.13], [0.5, 0.13], [0.5, 0.55], [0.1, 0.55]],
      polygon_source: 'synthesized_from_bbox', bbox_pct: { x: 0.1, y: 0.13, w: 0.4, h: 0.42 } },
    { renderedWidth: 1000, renderedHeight: 1000 });
  assert.equal(z, null);
});

test('C1(e): no geometry, no anchor → null (Tier 3, counted as missing)', () => {
  const z = buildRoomZone({ nr: '900', polygon_source: 'manual_needed' },
    { renderedWidth: 1000, renderedHeight: 1000 });
  assert.equal(z, null);
});

// ── Marker-by-default (founder decision 2026-07-11) ────────────────────────
// Every placeable zone carries a `marker` anchor: traced polygons anchor at
// their area centroid; tier-2 rooms reuse their label anchor. The polygon
// fills default OFF (RoomZoneLayer renders the marker unless toggled on).
import { ROOM_POLYGON_FILLS_DEFAULT_VISIBLE, polygonPointsCentroid } from './roomZones.js';

test('founder default 2026-07-11: polygon fills are OFF by default', () => {
  assert.equal(ROOM_POLYGON_FILLS_DEFAULT_VISIBLE, false);
});

test('buildRoomZone: traced polygon carries a centroid marker anchor', () => {
  const z = buildRoomZone(roomPolygon, SIZE);
  assert.equal(z.geometry.type, 'polygon');
  // Rectangle (0.1..0.5)×1000 × (0.13..0.55)×800 → centroid (300, 272)
  assert.ok(Math.abs(z.marker.cx - 300) < 1e-9);
  assert.ok(Math.abs(z.marker.cy - 272) < 1e-9);
});

test('buildRoomZone: tier-2 marker zone anchors at its label point', () => {
  const z = buildRoomZone(
    { nr: '108', marker_pct: [0.3, 0.4] }, SIZE);
  assert.equal(z.geometry.type, 'marker');
  assert.deepEqual([z.marker.cx, z.marker.cy], [300, 320]);
});

test('polygonPointsCentroid: L-shape centroid is area-weighted, not bbox center', () => {
  // L-shape (0,0)(2,0)(2,1)(1,1)(1,2)(0,2): area 3, centroid (5/6, 5/6) —
  // bbox center would be (1,1), so this pins the area weighting.
  const c = polygonPointsCentroid([[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]]);
  assert.ok(Math.abs(c.cx - 5 / 6) < 1e-9);
  assert.ok(Math.abs(c.cy - 5 / 6) < 1e-9);
});

test('polygonPointsCentroid: degenerate ring falls back to bbox center', () => {
  const c = polygonPointsCentroid([[0, 0], [4, 0], [8, 0]]);
  assert.deepEqual(c, { cx: 4, cy: 0 });
});

import { spreadOverlappingMarkers } from './roomZones.js';

test('spreadOverlappingMarkers: solo markers keep their true anchor', () => {
  const m = spreadOverlappingMarkers([
    { nr: '101', cx: 100, cy: 100 },
    { nr: '102', cx: 400, cy: 100 },
  ], 30);
  assert.deepEqual(m.get('101'), { cx: 100, cy: 100 });
  assert.deepEqual(m.get('102'), { cx: 400, cy: 100 });
});

test('spreadOverlappingMarkers: identical centroids fan out horizontally, nr-ordered', () => {
  // duplicated flood-fill polygons → 3 rooms share one centroid (Objektas A 103/108/109 case)
  const m = spreadOverlappingMarkers([
    { nr: '109', cx: 648, cy: 506 },
    { nr: '103', cx: 648, cy: 506 },
    { nr: '108', cx: 649, cy: 506 },
  ], 30);
  const xs = ['103', '108', '109'].map((nr) => m.get(nr).cx);
  assert.ok(xs[0] < xs[1] && xs[1] < xs[2]);              // fanned left→right by nr
  assert.ok(Math.abs(xs[1] - xs[0] - 30) < 1e-6);         // exactly minGap apart
  assert.ok(['103', '108', '109'].every((nr) => m.get(nr).cy === 506));
});

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

test('countRoomsMissingGeometry: a room merged into another is not „without a place"', () => {
  const merged = { ...noGeom('5', 2), _konturas: { saltinis: 'sujungta', i: '1', page: 2, plotas_m2: 0 } };
  const n = countRoomsMissingGeometry([poly('1', 2), merged, noGeom('3', 2)], { renderedWidth: 1000, renderedHeight: 800, page: 2 });
  assert.equal(n, 1);
});

// ── 2026-07-12: duplicate-polygon disqualification + interior anchors ──────
import {
  duplicatePolygonLosers, interiorMarkerAnchor, pointInPolygonPoints,
} from './roomZones.js';

const SQ = (x0, y0, w, h) => [[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]];

test('duplicatePolygonLosers: identical polygons keep only the m²-matching owner', () => {
  // Unique reference rooms fix the pct-area→m² scale at k = 0.001/m².
  const rooms = [
    { nr: 201, puslapio_nr: 2, plotas_m2: 50, polygon_source: 'auto_floodfill', polygon_pct: SQ(0.1, 0.1, 0.25, 0.2) },   // 0.05 pct²
    { nr: 202, puslapio_nr: 2, plotas_m2: 10, polygon_source: 'auto_floodfill', polygon_pct: SQ(0.6, 0.1, 0.10, 0.1) },   // 0.01
    // Duplicate trio claiming the SAME strip of 0.009 pct² ≈ 9 m² at k=0.001:
    { nr: 103, puslapio_nr: 2, plotas_m2: 9.6,  polygon_source: 'auto_floodfill', polygon_pct: SQ(0.45, 0.4, 0.03, 0.3) },
    { nr: 108, puslapio_nr: 2, plotas_m2: 12.7, polygon_source: 'auto_floodfill', polygon_pct: SQ(0.45, 0.4, 0.03, 0.3) },
    { nr: 109, puslapio_nr: 2, plotas_m2: 12.7, polygon_source: 'auto_floodfill', polygon_pct: SQ(0.45, 0.4, 0.03, 0.3) },
  ];
  const losers = duplicatePolygonLosers(rooms, 2);
  assert.deepEqual([...losers].sort(), ['108', '109']);   // 103 fits the area → keeps it
  const zones = buildPageRoomZones(rooms, { renderedWidth: 1000, renderedHeight: 800, page: 2 });
  assert.deepEqual(zones.map((z) => String(z.nr)).sort(), ['103', '201', '202']);
});

test('interiorMarkerAnchor: L-shape whose centroid falls outside gets an inside anchor', () => {
  // L-shape: thin horizontal + thin vertical arm; centroid lands in the notch.
  const L = [[0, 0], [100, 0], [100, 10], [10, 10], [10, 100], [0, 100]];
  const a = interiorMarkerAnchor(L);
  assert.ok(pointInPolygonPoints(a.cx, a.cy, L), 'anchor must be inside the L');
});

test('spreadOverlappingMarkers: fanned markers stay inside their own polygon', () => {
  // Two markers stacked inside a NARROW vertical strip: a horizontal fan would
  // exit the strip, so the spreader must fall back to the vertical fan.
  const strip = SQ(480, 300, 40, 300);   // x 480..520 — narrower than the fan gap
  const items = [
    { nr: 'A', cx: 500, cy: 450, points: strip },
    { nr: 'B', cx: 500, cy: 452, points: strip },
  ];
  const out = spreadOverlappingMarkers(items, 30);
  for (const [, pos] of out) {
    assert.ok(pointInPolygonPoints(pos.cx, pos.cy, strip), 'marker escaped its polygon');
  }
  const a = out.get('A'), b = out.get('B');
  assert.ok(Math.hypot(a.cx - b.cx, a.cy - b.cy) >= 29, 'markers still overlap');
});

// ── Shared page-field precedence (audit P2, 2026-07-27) ─────────────────────
import { roomPageOf } from './roomZones.js';

test('roomPageOf: puslapio_nr wins — it is the extraction-native field', () => {
  assert.equal(roomPageOf({ puslapio_nr: 2, page_nr: 5 }), 2);
});

test('roomPageOf: falls back to page_nr, then null', () => {
  assert.equal(roomPageOf({ page_nr: 5 }), 5);
  assert.equal(roomPageOf({}), null);
  assert.equal(roomPageOf(null), null);
});

test('roomPageOf: a disagreeing room lands on the SAME page as its zone', () => {
  // Regression guard for the split precedence: buildPageRoomZones used
  // page_nr-first while the viewer's FocusScroller used puslapio_nr-first, so
  // the zone was drawn on one page while the viewer scrolled to another.
  const room = {
    nr: '7', puslapio_nr: 2, page_nr: 5,
    polygon_pct: [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]],
    polygon_source: 'auto_floodfill', plotas_m2: 12,
  };
  const size = { renderedWidth: 100, renderedHeight: 100 };
  assert.equal(buildPageRoomZones([room], { ...size, page: 2 }).length, 1);
  assert.equal(buildPageRoomZones([room], { ...size, page: 5 }).length, 0);
  assert.equal(roomPageOf(room), 2);
});

test('countRoomsMissingGeometry: a room with no polygon and no anchor feeds the chip', () => {
  // The "N patalpų be vietos plane" disclosure now renders in BOTH presentation
  // modes (RoomZoneLayer simple + fills); this is the count it renders.
  const rooms = [
    { nr: '1', puslapio_nr: 2, polygon_pct: [[0, 0], [0.4, 0], [0.4, 0.4], [0, 0.4]],
      polygon_source: 'auto_floodfill', plotas_m2: 10 },
    { nr: '2', puslapio_nr: 2, polygon_source: 'manual_needed', plotas_m2: 8 },  // no anchor
  ];
  const size = { renderedWidth: 100, renderedHeight: 100, page: 2 };
  assert.equal(buildPageRoomZones(rooms, size).length, 1);
  assert.equal(countRoomsMissingGeometry(rooms, size), 1);
});

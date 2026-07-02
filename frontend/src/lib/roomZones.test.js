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
  assert.equal(z.color, '#f59e0b');                        // valgomasis
});

test('buildRoomZone: eksplikacija area → high confidence, green dot', () => {
  const z = buildRoomZone(roomPolygon, SIZE);
  assert.equal(z.confidence, 'high');                      // single eksplikacija source
  assert.equal(z.confidenceColor, '#16a34a');
  assert.equal(z.areaLabel, '50,5 m²');                    // lt-LT, 1 decimal
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

test('buildRoomZone: synthesized_from_bbox WITH marker_pct → located marker, not a polygon', () => {
  const z = buildRoomZone(
    { ...roomPolygon, polygon_source: 'synthesized_from_bbox', marker_pct: [0.3, 0.4] }, SIZE);
  assert.equal(z.geometry.type, 'marker');
  assert.deepEqual([z.geometry.cx, z.geometry.cy], [300, 320]);  // 0.3*1000, 0.4*800
  assert.equal(z.approximate, true);
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

test('C1(b): manual_needed with marker_pct → marker tier at the printed label', () => {
  const z = buildRoomZone(
    { nr: '108', polygon_source: 'manual_needed', marker_pct: [0.55, 0.30] },
    { renderedWidth: 1000, renderedHeight: 2000 });
  assert.equal(z.geometry.type, 'marker');
  assert.deepEqual([z.geometry.cx, z.geometry.cy], [550, 600]);  // 0.55*1000, 0.30*2000
  assert.equal(z.approximate, true);
});

test('C1(c): manual_needed with label_pct (no marker_pct) → marker at label_pct', () => {
  const z = buildRoomZone(
    { nr: '109', polygon_source: 'manual_needed', label_pct: [0.40, 0.25] },
    { renderedWidth: 1000, renderedHeight: 2000 });
  assert.equal(z.geometry.type, 'marker');
  assert.deepEqual([z.geometry.cx, z.geometry.cy], [400, 500]);  // 0.40*1000, 0.25*2000
  assert.equal(z.approximate, true);
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

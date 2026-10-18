import test from 'node:test';
import assert from 'node:assert/strict';
import { roomAtPoint, nextRoomSelection, BADGE_HIT_PX } from './roomHitTest.js';

const SIZE = { renderedWidth: 1000, renderedHeight: 800 };
const square = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];

// Two traced rooms on sheet 1, a corridor wrapping them, a room with only its printed number, and one the
// lane located by its badge but that the layer cannot draw (no outline, no marker).
const ROOMS = [
  { nr: '04', puslapio_nr: 1, plotas_m2: 26.31, polygon_source: 'vektoriniai_konturai', polygon_pct: square(0.1, 0.1, 0.4, 0.4) },
  { nr: '05', puslapio_nr: 1, plotas_m2: 35.5, polygon_source: 'corrected', polygon_pct: square(0.4, 0.1, 0.7, 0.4) },
  { nr: '03', puslapio_nr: 1, plotas_m2: 60, polygon_source: 'vektoriniai_konturai', polygon_pct: square(0.05, 0.05, 0.75, 0.6) },
  { nr: '07', puslapio_nr: 1, marker_pct: [0.85, 0.2], marker_source: 'plan_label', polygon_source: 'manual_needed' },
  { nr: '09', puslapio_nr: 1, _vieta: { page: 1, cx: 0.85, cy: 0.7, W: 0.02, H: 0.01, saltinis: 'zenkliukas' } },
  { nr: '11', puslapio_nr: 2, polygon_source: 'vektoriniai_konturai', polygon_pct: square(0.1, 0.1, 0.4, 0.4) },
];

test('a click inside an outline picks that room; the smaller of two overlapping outlines wins', () => {
  assert.deepEqual(roomAtPoint(ROOMS, { page: 1, x_pct: 0.2, y_pct: 0.2 }, SIZE), { nr: '04', how: 'outline' });
  assert.deepEqual(roomAtPoint(ROOMS, { page: 1, x_pct: 0.55, y_pct: 0.3 }, SIZE), { nr: '05', how: 'outline' });
  // inside the corridor only (outside 04 and 05)
  assert.deepEqual(roomAtPoint(ROOMS, { page: 1, x_pct: 0.3, y_pct: 0.5 }, SIZE), { nr: '03', how: 'outline' });
});

test('a room drawn only as its number is picked within the badge radius, not beyond it', () => {
  const near = 0.85 + (BADGE_HIT_PX - 4) / 1000;
  assert.deepEqual(roomAtPoint(ROOMS, { page: 1, x_pct: near, y_pct: 0.2 }, SIZE), { nr: '07', how: 'number' });
  const far = 0.85 + (BADGE_HIT_PX + 6) / 1000;
  assert.equal(roomAtPoint(ROOMS, { page: 1, x_pct: far, y_pct: 0.2 }, SIZE), null);
});

test('the badge the drawing lane located counts when the layer has nothing else for the room', () => {
  assert.deepEqual(roomAtPoint(ROOMS, { page: 1, x_pct: 0.852, y_pct: 0.7 }, SIZE), { nr: '09', how: 'seat' });
  // a weak seat (a box guessed from the bbox) is not a place to click
  const weak = [{ nr: '09', puslapio_nr: 1, _vieta: { page: 1, cx: 0.85, cy: 0.7, saltinis: 'bbox' } }];
  assert.equal(roomAtPoint(weak, { page: 1, x_pct: 0.85, y_pct: 0.7 }, SIZE), null);
});

test('only the clicked sheet\'s rooms count, and a room hidden with the eye is not clickable', () => {
  assert.deepEqual(roomAtPoint(ROOMS, { page: 2, x_pct: 0.2, y_pct: 0.2 }, SIZE), { nr: '11', how: 'outline' });
  assert.equal(roomAtPoint(ROOMS, { page: 3, x_pct: 0.2, y_pct: 0.2 }, SIZE), null);
  assert.deepEqual(roomAtPoint(ROOMS, { page: 1, x_pct: 0.2, y_pct: 0.2 }, { ...SIZE, hidden: new Set(['04']) }),
    { nr: '03', how: 'outline' });
});

test('empty paper and bad input pick nothing', () => {
  assert.equal(roomAtPoint(ROOMS, { page: 1, x_pct: 0.95, y_pct: 0.95 }, SIZE), null);
  assert.equal(roomAtPoint(null, { page: 1, x_pct: 0.2, y_pct: 0.2 }, SIZE), null);
  assert.equal(roomAtPoint(ROOMS, null, SIZE), null);
  assert.equal(roomAtPoint(ROOMS, { page: 1, x_pct: NaN, y_pct: 0.2 }, SIZE), null);
});

test('a merged room (its outline went to the room it joined) is not on the sheet', () => {
  const rooms = [
    { nr: '04', puslapio_nr: 1, polygon_source: 'corrected', polygon_pct: square(0.1, 0.1, 0.7, 0.4) },
    { nr: '05', puslapio_nr: 1, _konturas: { saltinis: 'sujungta', i: '04' } },
  ];
  assert.deepEqual(roomAtPoint(rooms, { page: 1, x_pct: 0.55, y_pct: 0.3 }, SIZE), { nr: '04', how: 'outline' });
});

test('click selects one room, Shift+click adds and removes, empty paper clears', () => {
  const none = { focused: null, extra: [] };
  assert.deepEqual(nextRoomSelection(none, '04'), { focused: '04', extra: [] });
  assert.deepEqual(nextRoomSelection({ focused: '04', extra: ['05'] }, '06'), { focused: '06', extra: [] });
  assert.deepEqual(nextRoomSelection({ focused: '04', extra: [] }, null), none);
  // Shift adds after the focused room, in click order
  assert.deepEqual(nextRoomSelection({ focused: '04', extra: [] }, '05', { shift: true }), { focused: '04', extra: ['05'] });
  assert.deepEqual(nextRoomSelection({ focused: '04', extra: ['05'] }, '06', { shift: true }), { focused: '04', extra: ['05', '06'] });
  // Shift on a selected room removes it; removing the focused one hands focus to the next
  assert.deepEqual(nextRoomSelection({ focused: '04', extra: ['05', '06'] }, '05', { shift: true }), { focused: '04', extra: ['06'] });
  assert.deepEqual(nextRoomSelection({ focused: '04', extra: ['05', '06'] }, '04', { shift: true }), { focused: '05', extra: ['06'] });
  assert.deepEqual(nextRoomSelection({ focused: '04', extra: [] }, '04', { shift: true }), none);
  // Shift with nothing selected selects; Shift on empty paper keeps the selection
  assert.deepEqual(nextRoomSelection(none, '04', { shift: true }), { focused: '04', extra: [] });
  assert.deepEqual(nextRoomSelection({ focused: '04', extra: ['05'] }, null, { shift: true }), { focused: '04', extra: ['05'] });
  // numbers and strings are the same room; the focused room never sits in `extra` twice
  assert.deepEqual(nextRoomSelection({ focused: 4, extra: ['4', 5] }, 6, { shift: true }), { focused: '4', extra: ['5', '6'] });
});

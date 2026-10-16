import test from 'node:test';
import assert from 'node:assert/strict';
import { scaleCheckReadout } from './scaleCheck.js';
import { METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';

const mpp = 50 * METERS_PER_POINT_AT_1_TO_1;           // 1:50
const scale = { calibrated: true, source: 'plan', metersPerPointX: mpp, metersPerPointY: mpp };
const pageSize = { width: 1000, height: 500 };
// a 4,00 m wall at 1:50 is 4 / mpp ≈ 226,77 pt long; its string's line drawn along y = 0.2
const wallPt = 4 / mpp;
// line_pct is the line's bounds (one stroke long, like PDFium's); ilgis_pt the drawn length the lane used
const strings = [
  { text: '4000', value_m: 4, ilgis_pt: wallPt, line_pct: [[0.1, 0.2], [0.1 + (wallPt + 1) / 1000, 0.2]] },
  { text: '1200', value_m: 1.2, ilgis_pt: 1.2 / mpp, line_pct: [[0.8, 0.9], [0.8, 0.9 + (1.2 / mpp + 1) / 500]] },
];

test('two clicks read the current scale\'s length; the nearest written string comes first, checked', () => {
  const r = scaleCheckReadout({ a: { x: 100, y: 105 }, b: { x: 100 + wallPt, y: 105 }, scale, pageSize, strings });
  assert.ok(Math.abs(r.lengthM - 4) < 1e-9);
  assert.equal(r.nearest[0].text, '4000');
  assert.ok(Math.abs(r.nearest[0].drawnM - 4) < 1e-9, 'the string agrees with the scale');
  assert.ok(Math.abs(r.nearest[0].diffPct) < 1e-6);
  assert.equal(r.nearest[1].text, '1200');
});

test('a wrong scale shows up as a difference against every string', () => {
  const wrong = { ...scale, metersPerPointX: mpp * 1.1, metersPerPointY: mpp * 1.1 };
  const r = scaleCheckReadout({ a: { x: 0, y: 0 }, b: { x: 10, y: 0 }, scale: wrong, pageSize, strings });
  for (const n of r.nearest) assert.ok(Math.abs(n.diffPct - 10) < 1e-6, String(n.diffPct));
});

test('no scale: the length in points only; no strings: the readout alone', () => {
  const r = scaleCheckReadout({ a: { x: 0, y: 0 }, b: { x: 30, y: 40 }, scale: { calibrated: false }, pageSize, strings });
  assert.equal(r.lengthM, null);
  assert.equal(r.lengthPt, 50);
  assert.equal(r.nearest[0].drawnM, null);
  assert.deepEqual(scaleCheckReadout({ a: { x: 0, y: 0 }, b: { x: 1, y: 0 }, scale, pageSize }).nearest, []);
  assert.equal(scaleCheckReadout({ a: null, b: null, scale, pageSize }), null);
});

test('a /Rotate 90 sheet: clicks in mediabox points meet strings in display fractions', () => {
  // mediabox 1000×500, shown rotated 90° → display 500×1000; mediabox (x,y) → display pct (1−y/H, x/W)
  const r = scaleCheckReadout({
    a: { x: 500, y: 250 }, b: { x: 600, y: 250 }, scale, pageSize, rotation: 90,
    strings: [
      { text: 'far', value_m: 1, line_pct: [[0.0, 0.0], [0.1, 0.0]] },
      { text: 'near', value_m: 1, line_pct: [[0.45, 0.55], [0.55, 0.55]] },
    ],
  });
  assert.equal(r.nearest[0].text, 'near');
});

test('the difference compares ilgis_pt × scale with the written value, not the raw span', () => {
  const r = scaleCheckReadout({ a: { x: 100, y: 105 }, b: { x: 110, y: 105 }, scale, pageSize, strings });
  const n = r.nearest.find((x) => x.text === '4000');
  assert.equal(n.available, true);
  assert.ok(Math.abs(n.diffPct) < 1e-6, 'the raw span would read +0,44 %');
});

test('a stored read without ilgis_pt is not checked: no length, no difference', () => {
  const old = strings.map(({ ilgis_pt, ...rest }) => rest);   // eslint-disable-line no-unused-vars
  const r = scaleCheckReadout({ a: { x: 100, y: 105 }, b: { x: 110, y: 105 }, scale, pageSize, strings: old });
  for (const n of r.nearest) {
    assert.equal(n.available, false);
    assert.equal(n.drawnM, null);
    assert.equal(n.diffPct, null);
  }
});

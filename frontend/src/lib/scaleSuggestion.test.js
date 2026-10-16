import test from 'node:test';
import assert from 'node:assert/strict';
import { suggestStandardScale, standardScalePageScale, STANDARD_SNAP_PCT } from './scaleSuggestion.js';
import { METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';

// A 4,00 m wall on a 1:50 sheet is 4 / (50 · m/pt at 1:1) points long.
const pts50 = 4 / (50 * METERS_PER_POINT_AT_1_TO_1);

test('a line that measures 1:49,4 suggests 1:50 within the snap tolerance', () => {
  const s = suggestStandardScale(pts50 * (50 / 49.4), 4, 'm');
  assert.equal(s.nearest, 50);
  assert.ok(Math.abs(s.measured - 49.4) < 0.05);
  assert.ok(s.diffPct > 1 && s.diffPct < 1.5);
  assert.equal(s.within, true);
});

test('1:115 is nobody\'s drawing scale — nearest 1:125, outside the tolerance', () => {
  const s = suggestStandardScale(4 / (115 * METERS_PER_POINT_AT_1_TO_1), 4, 'm');
  assert.equal(s.nearest, 125);
  assert.ok(s.diffPct > STANDARD_SNAP_PCT);
  assert.equal(s.within, false);
});

test('units are honoured and degenerate input gives null', () => {
  const s = suggestStandardScale(pts50, 400, 'cm');
  assert.equal(s.nearest, 50);
  assert.equal(suggestStandardScale(0, 4, 'm'), null);
  assert.equal(suggestStandardScale(pts50, 0, 'm'), null);
});

test('the standard scale becomes a PageScale with its label', () => {
  const ps = standardScalePageScale(50);
  assert.ok(Math.abs(ps.metersPerPointX - 50 * METERS_PER_POINT_AT_1_TO_1) < 1e-12);
  assert.equal(ps.metersPerPointY, ps.metersPerPointX);
  assert.equal(ps.calibrated, true);
  assert.equal(ps.source, 'user');
  assert.equal(ps.label, '1:50');
});

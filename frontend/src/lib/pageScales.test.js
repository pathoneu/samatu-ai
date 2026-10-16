import test from 'node:test';
import assert from 'node:assert/strict';
import { mergePageScales, effectivePageScales, pageScaleIn } from './pageScales.js';
import { METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';

// objektas_h's shape: the geometry lane measured every sheet; nothing calibrated by hand.
const H = { _meta: { geometrija: { masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 }, 3: { m_per_pt: 0.040602, mastelis: 115 } } } } };

test('a sheet whose scale comes from the lane has metres — the Matavimai bug (it said „nekalibruota")', () => {
  const s = effectivePageScales(H);
  assert.equal(pageScaleIn(s, 1).calibrated, true);
  assert.equal(pageScaleIn(s, 1).source, 'plan');
  assert.equal(pageScaleIn(s, '3').label, '1:115');
  assert.equal(pageScaleIn(s, 2), null);
});

test('merge order: auto < lane < his own; an uncalibrated durable entry never hides the lane', () => {
  const auto = { 1: { calibrated: true, source: 'auto', metersPerPointX: 0.01 }, 2: { calibrated: true, source: 'auto', metersPerPointX: 0.01 } };
  const lane = { 1: { calibrated: true, source: 'plan', metersPerPointX: 0.02 } };
  const durable = { 1: { calibrated: false, source: 'none', metersPerPointX: 0 }, 2: { calibrated: true, source: 'user', metersPerPointX: 0.03 } };
  const m = mergePageScales(auto, lane, durable);
  assert.equal(m[1].source, 'plan');
  assert.equal(m[2].source, 'user');
});

test('the viewer\'s live durable map overrides the stored one', () => {
  const live = { 1: { calibrated: true, source: 'user', metersPerPointX: 50 * METERS_PER_POINT_AT_1_TO_1 } };
  const stored = { ...H, pageScalesDurable: {} };
  assert.equal(pageScaleIn(effectivePageScales(stored, live), 1).source, 'user');
  assert.equal(pageScaleIn(effectivePageScales(stored), 1).source, 'plan');
  assert.deepEqual(effectivePageScales(null), {});
});

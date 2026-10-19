import test from 'node:test';
import assert from 'node:assert/strict';
import { isNotNeeded, notNeededEntry, paperLabel, parseRatio, scaleForRatio, standardRatios } from './scaleEntry.js';
import { mergePageScales } from './pageScales.js';
import { scaleState } from './scaleLabel.js';

test('a typed scale is read the ways a drawing writes it', () => {
  for (const t of ['1:50', '1 : 50', '50', 'M 1:50', 'm1:50', '1/50']) assert.equal(parseRatio(t), 50, t);
  assert.equal(parseRatio('1:12,5'), 12.5);
  for (const t of ['', '1:', 'abc', '1:0', '2:50', '1:99999', null]) assert.equal(parseRatio(t), null, String(t));
});

test('a ratio becomes his own, confirmed scale', () => {
  const s = scaleForRatio(50);
  assert.equal(s.calibrated, true);
  assert.equal(s.source, 'user');
  assert.equal(s.label, '1:50');
  assert.ok(Math.abs(s.metersPerPointX - 50 * 0.0254 / 72) < 1e-12);
  assert.equal(scaleState(s), 'patvirtintas');
  assert.equal(scaleForRatio(0), null);
});

test('„nereikia" never hides a scale read from the drawing and never measures', () => {
  const lane = { 3: { metersPerPointX: 0.04, metersPerPointY: 0.04, calibrated: true, source: 'plan', label: '1:115' } };
  const merged = mergePageScales({}, lane, { 3: notNeededEntry(), 4: notNeededEntry() });
  assert.equal(merged[3].source, 'plan');
  assert.equal(merged[4], undefined);
  assert.equal(isNotNeeded(notNeededEntry()), true);
  assert.equal(isNotNeeded(lane[3]), false);
});

test('the standard list and the paper size', () => {
  assert.deepEqual(standardRatios().slice(0, 5), [20, 25, 30, 40, 50]);
  assert.equal(paperLabel({ width: 1190.55, height: 841.89 }), 'A3 · 420 × 297 mm');
  assert.equal(paperLabel({ width: 595.28, height: 841.89 }), 'A4 · 210 × 297 mm');
  assert.equal(paperLabel({ width: 1000, height: 500 }), '353 × 176 mm');
  assert.equal(paperLabel(null), '');
});

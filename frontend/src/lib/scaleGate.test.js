import test from 'node:test';
import assert from 'node:assert/strict';
import { scaleGateFor, scaleGateFromScale, SCALE_UNSET_REASON } from './scaleGate.js';
import { isBannedText } from './userText.js';

const H = { _meta: { geometrija: { masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 } } } } };

test('no scale on the sheet → not ok, with the soft reason', () => {
  const g = scaleGateFor(H, 2);
  assert.equal(g.ok, false);
  assert.equal(g.scale, null);
  assert.equal(g.state, 'nenustatytas');
  assert.equal(g.reason, SCALE_UNSET_REASON);
  assert.equal(isBannedText(g.reason), false);
});

test('a guessed lane scale is in force (ok) and says it is a guess', () => {
  const g = scaleGateFor(H, 1);
  assert.equal(g.ok, true);
  assert.equal(g.state, 'spejamas');
  assert.equal(g.scale.label, '1:115');
  assert.equal(g.reason, null);
});

test('his live calibration on an empty sheet opens the gate', () => {
  const live = { 2: { calibrated: true, source: 'user', metersPerPointX: 0.02 } };
  assert.equal(scaleGateFor(H, 2, live).ok, true);
  assert.equal(scaleGateFor(H, 2, live).state, 'patvirtintas');
  assert.equal(scaleGateFromScale(undefined).ok, false);
  assert.equal(scaleGateFor(null, 1).ok, false);
});

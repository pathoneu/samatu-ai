// frontend/src/lib/gestures/g5-lasso-geometry.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { simplifyLasso, closeIfNeeded, isMinimalLasso } from './g5-lasso-geometry.js';

test('simplifyLasso drops near-duplicate consecutive points', () => {
  const raw = [[0, 0], [0.0001, 0], [0.5, 0.5], [0.5001, 0.5001], [1, 1]];
  const out = simplifyLasso(raw, /* tolerance= */ 0.001);
  assert.equal(out.length, 3);
});

test('closeIfNeeded appends first point when not closed', () => {
  const open = [[0, 0], [1, 0], [1, 1]];
  const closed = closeIfNeeded(open);
  assert.equal(closed.length, 4);
  assert.deepEqual(closed.at(-1), closed[0]);
});

test('closeIfNeeded leaves already-closed polygon alone', () => {
  const closed = [[0, 0], [1, 0], [1, 1], [0, 0]];
  assert.equal(closeIfNeeded(closed).length, 4);
});

test('isMinimalLasso rejects polygons with <3 unique vertices', () => {
  assert.equal(isMinimalLasso([[0, 0], [1, 0]]), false);
  assert.equal(isMinimalLasso([[0, 0], [1, 0], [2, 0]]), true);
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { pickZoomLevel, MIP_LEVELS, tileKey } from './mipPyramid.js';

test('MIP_LEVELS is the canonical 2-level pyramid', () => {
  assert.deepEqual(MIP_LEVELS, [1.5, 3.0]);
});

test('pickZoomLevel: scale 0.3 → 1.5 (canonical floor)', () => {
  assert.equal(pickZoomLevel(0.3), 1.5);
});

test('pickZoomLevel: scale 1.0 → 1.5 (canonical)', () => {
  assert.equal(pickZoomLevel(1.0), 1.5);
});

test('pickZoomLevel: scale 2.5 → 3.0 (deep zoom)', () => {
  assert.equal(pickZoomLevel(2.5), 3.0);
});

test('pickZoomLevel: scale 5.0 → 3.0 (cap at deepest level)', () => {
  assert.equal(pickZoomLevel(5.0), 3.0);
});

test('pickZoomLevel: scale exactly at boundary 1.5 → 1.5', () => {
  assert.equal(pickZoomLevel(1.5), 1.5);
});

test('tileKey: combines page idx and zoom level', () => {
  assert.equal(tileKey(0, 1.5), '0:1.5');
  assert.equal(tileKey(7, 0.5), '7:0.5');
});

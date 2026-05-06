import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  pickZoomLevel,
  MIP_LEVELS,
  tileKey,
  getRenderPixelRatio,
  createRenderTile,
} from './mipPyramid.js';

test('MIP_LEVELS is the canonical 3-level pyramid', () => {
  assert.deepEqual(MIP_LEVELS, [0.5, 1.5, 3.0]);
});

test('pickZoomLevel: scale 0.3 → 0.5 (smallest preview)', () => {
  assert.equal(pickZoomLevel(0.3), 0.5);
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

test('getRenderPixelRatio: caps HiDPI rendering at 2x', () => {
  const original = globalThis.devicePixelRatio;
  try {
    globalThis.devicePixelRatio = 3;
    assert.equal(getRenderPixelRatio(), 2);
    globalThis.devicePixelRatio = 1.5;
    assert.equal(getRenderPixelRatio(), 1.5);
  } finally {
    globalThis.devicePixelRatio = original;
  }
});

test('createRenderTile: closes underlying ImageBitmap when evicted', () => {
  let closed = false;
  const tile = createRenderTile({ width: 10, height: 20, close: () => { closed = true; } }, 5, 10);
  assert.equal(tile.cssWidth, 5);
  assert.equal(tile.cssHeight, 10);
  tile.close();
  assert.equal(closed, true);
});

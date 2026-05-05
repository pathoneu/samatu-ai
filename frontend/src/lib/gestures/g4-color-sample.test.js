// frontend/src/lib/gestures/g4-color-sample.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { rgbAt, isWhitish, buildColorZonePayload } from './g4-color-sample.js';

test('rgbAt reads color from canvas-like pixel buffer', () => {
  // Stub canvas: 2×1 image, pixel 0 = blue, pixel 1 = red.
  // Each pixel is RGBA: 4 bytes.
  const data = new Uint8ClampedArray([0, 0, 255, 255,  255, 0, 0, 255]);
  const ctx = {
    getImageData: (x, y, w, h) => ({ data: data.slice((y*2 + x) * 4, ((y*2 + x) + 1) * 4) }),
  };
  assert.deepEqual(rgbAt(ctx, 0, 0), [0, 0, 255]);
  assert.deepEqual(rgbAt(ctx, 1, 0), [255, 0, 0]);
});

test('isWhitish rejects near-white pixels (background false-positives)', () => {
  assert.equal(isWhitish([255, 255, 255]), true);
  assert.equal(isWhitish([250, 248, 252]), true);
  assert.equal(isWhitish([200, 100, 50]), false);
});

test('buildColorZonePayload assembles backend payload', () => {
  const payload = buildColorZonePayload({
    targetRoomId: 'r1',
    colorRgb: [80, 200, 120],
    polygonsPct: [[[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]],
  });
  assert.equal(payload.targetRoomId, 'r1');
  assert.deepEqual(payload.colorRgb, [80, 200, 120]);
  assert.equal(payload.polygonsPct.length, 1);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { paddedRect, frameForRoom, frameForMeasurements } from './frameSelection.js';

const close = (a, b, eps = 1e-9) => a.every((v, i) => Math.abs(v - b[i]) < eps);

test('a bbox is padded by a quarter on every side and kept on the page', () => {
  assert.ok(close(paddedRect([0.4, 0.6], [0.4, 0.5]), [0.35, 0.375, 0.65, 0.525]));
  assert.deepEqual(paddedRect([0, 1], [0, 1]), [0, 0, 1, 1]);
  assert.equal(paddedRect([], []), null);
});

test('a point still gets a readable window', () => {
  const r = paddedRect([0.5], [0.5]);
  assert.ok(r[2] - r[0] > 0.1 && r[3] - r[1] > 0.1);
});

test('a traced room frames its outline on its page', () => {
  const room = { nr: '04', puslapio_nr: 1, polygon_pct: [[0.4, 0.4], [0.6, 0.4], [0.6, 0.5], [0.4, 0.5]], polygon_source: 'vektoriniai_konturai' };
  const f = frameForRoom(room);
  assert.equal(f.page, 1);
  assert.ok(close(f.rect, [0.35, 0.375, 0.65, 0.525]));
});

test('a marker-only room frames its printed number; a room without a place has no frame', () => {
  const f = frameForRoom({ nr: '07', puslapio_nr: 2, marker_pct: [0.3, 0.7], marker_source: 'plan_label', polygon_source: 'bbox' });
  assert.equal(f.page, 2);
  assert.ok(f.rect[0] < 0.3 && f.rect[2] > 0.3 && f.rect[1] < 0.7 && f.rect[3] > 0.7);
  assert.equal(frameForRoom({ nr: '09', puslapio_nr: 1 }), null);
  assert.equal(frameForRoom(null), null);
});

test('measurements are framed in the displayed page, rotation applied', () => {
  const ms = [{ page: 3, points: [{ x: 100, y: 100 }, { x: 200, y: 150 }] }];
  const size = { width: 1000, height: 500 };
  const flat = frameForMeasurements(ms, { pageSizeOf: () => size, rotationOf: () => 0 });
  assert.equal(flat.page, 3);
  assert.ok(flat.rect[0] < 0.1 && flat.rect[2] > 0.2 && flat.rect[1] < 0.2 && flat.rect[3] > 0.3);
  const turned = frameForMeasurements(ms, { pageSizeOf: () => size, rotationOf: () => 90 });
  // 90° clockwise: x' = 1 − y, y' = x
  assert.ok(turned.rect[0] > 0.6 && turned.rect[1] < 0.1);
  assert.equal(frameForMeasurements([], {}), null);
  assert.equal(frameForMeasurements(ms, { pageSizeOf: () => null }), null);
});

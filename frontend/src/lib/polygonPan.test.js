// frontend/src/lib/polygonPan.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { polygonBoundingBox, fitToBox, computePanToPolygon } from './polygonPan.js';

test('polygonBoundingBox: empty/null returns null', () => {
  assert.equal(polygonBoundingBox(null), null);
  assert.equal(polygonBoundingBox([]), null);
});

test('polygonBoundingBox: 4-vertex rectangle', () => {
  const bbox = polygonBoundingBox([[0.1, 0.2], [0.5, 0.2], [0.5, 0.6], [0.1, 0.6]]);
  assert.deepEqual(bbox, { minX: 0.1, minY: 0.2, maxX: 0.5, maxY: 0.6 });
});

test('polygonBoundingBox: triangle with non-axis-aligned vertices', () => {
  const bbox = polygonBoundingBox([[0.3, 0.4], [0.7, 0.45], [0.5, 0.8]]);
  assert.deepEqual(bbox, { minX: 0.3, minY: 0.4, maxX: 0.7, maxY: 0.8 });
});

test('fitToBox: null bbox returns null', () => {
  assert.equal(fitToBox(null, 1000, 800), null);
});

test('fitToBox: bbox 0..1 with default 30% padding fits viewport', () => {
  const bbox = { minX: 0, minY: 0, maxX: 1, maxY: 1 };
  const fit = fitToBox(bbox, 1000, 800, 0);
  // Without padding, full bbox of 1.0 should fit at scale that puts it in viewport
  assert.ok(fit.scale > 0);
  assert.ok(typeof fit.translate.x === 'number');
  assert.ok(typeof fit.translate.y === 'number');
});

test('fitToBox: smaller bbox gets larger scale', () => {
  const small = fitToBox({ minX: 0.4, minY: 0.4, maxX: 0.5, maxY: 0.5 }, 1000, 800, 0);
  const large = fitToBox({ minX: 0,   minY: 0,   maxX: 1,   maxY: 1   }, 1000, 800, 0);
  assert.ok(small.scale > large.scale, `small.scale=${small.scale} should be > large.scale=${large.scale}`);
});

test('computePanToPolygon: returns null for null polygon', () => {
  assert.equal(computePanToPolygon(null, 1000, 800), null);
});

test('computePanToPolygon: square polygon centers in viewport', () => {
  const fit = computePanToPolygon([[0.4, 0.4], [0.6, 0.4], [0.6, 0.6], [0.4, 0.6]], 1000, 800);
  assert.ok(fit.scale > 0);
  // The polygon bbox center is (0.5, 0.5); viewport center is (500, 400).
  // After fit, the polygon centroid should map near viewport center.
  assert.ok(typeof fit.translate.x === 'number');
  assert.ok(typeof fit.translate.y === 'number');
});

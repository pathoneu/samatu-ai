import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  clampViewerScale,
  nextWheelScale,
  getAnchoredZoomScroll,
} from './viewerViewport.js';

test('clampViewerScale: keeps scale inside viewer bounds and rounds drift', () => {
  assert.equal(clampViewerScale(0.1), 0.3);
  assert.equal(clampViewerScale(4), 3);
  assert.equal(clampViewerScale(1.234), 1.23);
});

test('nextWheelScale: zooms in and out in stable 10% steps', () => {
  assert.equal(nextWheelScale(1, -1), 1.1);
  assert.equal(nextWheelScale(1, 1), 0.9);
  assert.equal(nextWheelScale(2.95, -1), 3);
  assert.equal(nextWheelScale(0.35, 1), 0.3);
});

test('getAnchoredZoomScroll: keeps pointer anchored on the same drawing coordinate', () => {
  const target = getAnchoredZoomScroll({
    scrollLeft: 200,
    scrollTop: 300,
    viewportX: 400,
    viewportY: 250,
    oldScale: 1,
    newScale: 1.5,
  });

  assert.deepEqual(target, {
    scrollLeft: 500,
    scrollTop: 575,
  });
});

test('getAnchoredZoomScroll: supports zooming out without negative scroll jumps', () => {
  const target = getAnchoredZoomScroll({
    scrollLeft: 20,
    scrollTop: 10,
    viewportX: 100,
    viewportY: 80,
    oldScale: 2,
    newScale: 0.5,
  });

  assert.deepEqual(target, {
    scrollLeft: 0,
    scrollTop: 0,
  });
});

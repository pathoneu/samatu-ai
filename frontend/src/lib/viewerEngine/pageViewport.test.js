import test from 'node:test';
import assert from 'node:assert/strict';
import { makeViewport } from './pageViewport.js';

// A /Rotate 90|270 page: unrotated (mediabox) 1000x800, displayed slot 800x1000.
// The viewport MUST use the rotation-applied dims — the same slot size
// EmbedPDF's Scroller lays the page out with (DOM-verified 2026-07-11 on the
// Objektas A /Rotate-270 sheets: host 737x521 = rotatedWidth x rotatedHeight).
const layout = { pageNumber: 2, pageIndex: 1, width: 1000, height: 800, rotatedWidth: 800, rotatedHeight: 1000 };

test('makeViewport: renderedSize = rotation-applied slot dims', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.renderedSize(), { width: 800, height: 1000 });
  assert.equal(vp.pageNumber, 2);
  assert.equal(vp.pageIndex, 1);
});

test('makeViewport: falls back to width/height when rotated dims are absent', () => {
  const vp = makeViewport({ pageNumber: 1, pageIndex: 0, width: 1000, height: 800 });
  assert.deepEqual(vp.renderedSize(), { width: 1000, height: 800 });
});

test('makeViewport: pctToScreen multiplies by rendered (rotated) size', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.pctToScreen({ x: 0.25, y: 0.5 }), { x: 200, y: 500 });
});

test('makeViewport: screenToPct is the inverse', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.screenToPct({ x: 200, y: 500 }), { x: 0.25, y: 0.5 });
});

test('makeViewport: null-safe on bad layout', () => {
  assert.equal(makeViewport(null), null);
  assert.equal(makeViewport({ width: 0, height: 0 }), null);
});

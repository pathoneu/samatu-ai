import test from 'node:test';
import assert from 'node:assert/strict';
import { makeViewport } from './pageViewport.js';

const layout = { pageNumber: 2, pageIndex: 1, width: 1000, height: 800, rotatedWidth: 500, rotatedHeight: 400 };

test('makeViewport: renderedSize = layout width/height', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.renderedSize(), { width: 1000, height: 800 });
  assert.equal(vp.pageNumber, 2);
  assert.equal(vp.pageIndex, 1);
});

test('makeViewport: pctToScreen multiplies by rendered size', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.pctToScreen({ x: 0.25, y: 0.5 }), { x: 250, y: 400 });
});

test('makeViewport: screenToPct is the inverse', () => {
  const vp = makeViewport(layout);
  assert.deepEqual(vp.screenToPct({ x: 250, y: 400 }), { x: 0.25, y: 0.5 });
});

test('makeViewport: null-safe on bad layout', () => {
  assert.equal(makeViewport(null), null);
  assert.equal(makeViewport({ width: 0, height: 0 }), null);
});

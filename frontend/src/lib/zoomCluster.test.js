import test from 'node:test';
import assert from 'node:assert/strict';
import { dragToPageRect, scrollToCentre, visibleShare } from './zoomCluster.js';

const host = { left: 100, top: 50, width: 1000, height: 500 };

test('a dragged box becomes page fractions in the displayed frame, whichever way it was dragged', () => {
  assert.deepEqual(dragToPageRect({ x0: 600, y0: 300, x1: 350, y1: 175 }, host), [0.25, 0.25, 0.5, 0.5]);
});

test('a box partly off the page is cut to the page; a box beside it is nothing', () => {
  assert.deepEqual(dragToPageRect({ x0: 0, y0: 0, x1: 350, y1: 175 }, host), [0, 0, 0.25, 0.25]);
  assert.equal(dragToPageRect({ x0: 1200, y0: 0, x1: 1300, y1: 40 }, host), null);
  assert.equal(dragToPageRect(null, host), null);
});

test('a click (no drag) frames half the canvas around it — two times closer', () => {
  const r = dragToPageRect({ x0: 600, y0: 300, x1: 602, y1: 301 }, host, { canvas: { width: 400, height: 200 } });
  assert.deepEqual(r.map((v) => Math.round(v * 1000) / 1000), [0.402, 0.402, 0.602, 0.602]);
});

test('the minimap frame is the part of the page the canvas shows', () => {
  assert.deepEqual(visibleShare(host, { left: 350, top: 175, width: 500, height: 250 }), [0.25, 0.25, 0.75, 0.75]);
  // the whole page in view
  assert.deepEqual(visibleShare(host, { left: 0, top: 0, width: 2000, height: 2000 }), [0, 0, 1, 1]);
  assert.equal(visibleShare(host, { left: 2000, top: 0, width: 10, height: 10 }), null);
});

test('a minimap click scrolls that place to the canvas centre', () => {
  assert.deepEqual(scrollToCentre(host, { left: 0, top: 0, width: 400, height: 200 }, 0.5, 0.5), { dx: 400, dy: 200 });
});

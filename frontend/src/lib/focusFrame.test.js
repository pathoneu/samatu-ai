import test from 'node:test';
import assert from 'node:assert/strict';
import { focusFrameForRoom, MARKER_WINDOW } from './focusFrame.js';
import { frameForRoom } from './frameSelection.js';

const OUTLINED = {
  nr: '06', puslapio_nr: 1, polygon_source: 'vektoriniai_konturai',
  polygon_pct: [[0.6, 0.3], [0.8, 0.3], [0.8, 0.5], [0.6, 0.5]],
};

test('a room with an outline is framed by its outline (the selection frame)', () => {
  assert.deepEqual(focusFrameForRoom(OUTLINED), frameForRoom(OUTLINED));
  assert.equal(focusFrameForRoom(OUTLINED).page, 1);
});

test('a room known only by its marker gets a readable window around it, kept on the sheet', () => {
  const f = focusFrameForRoom({ nr: '07', puslapio_nr: 2, marker_pct: [0.3, 0.7], marker_source: 'plan_label', polygon_source: 'bbox' });
  assert.equal(f.page, 2);
  const [x0, y0, x1, y1] = f.rect;
  assert.ok(Math.abs((x1 - x0) - MARKER_WINDOW) < 1e-9 && Math.abs((y1 - y0) - MARKER_WINDOW) < 1e-9);
  assert.ok(x0 <= 0.3 && x1 >= 0.3 && y0 <= 0.7 && y1 >= 0.7);
  // a marker at the sheet edge: the window stays inside the sheet
  const edge = focusFrameForRoom({ nr: '08', puslapio_nr: 2, marker_pct: [0.98, 0.02], marker_source: 'plan_label', polygon_source: 'bbox' });
  assert.ok(edge.rect.every((v) => v >= 0 && v <= 1));
});

test('a room with no place on the drawing has no frame — the viewer scrolls to its page as before', () => {
  assert.equal(focusFrameForRoom({ nr: '09', puslapio_nr: 1 }), null);
  assert.equal(focusFrameForRoom(null), null);
  assert.equal(focusFrameForRoom({ nr: '10', polygon_source: 'vektoriniai_konturai', polygon_pct: OUTLINED.polygon_pct }), null);
});

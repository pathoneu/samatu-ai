import test from 'node:test';
import assert from 'node:assert/strict';
import { placeSelectionBar, pickSpot, overlapArea } from './selectionPlacement.js';

const frame = { width: 828, height: 534 };
const bar = { width: 600, height: 40 };
const inset = { left: 88, top: 8, right: 8, bottom: 8 };

test('the bar stands above the selected label and never covers it', () => {
  const label = { left: 300, top: 240, width: 120, height: 38 };
  const p = placeSelectionBar({ anchor: label, frame, bar, inset });
  assert.equal(p.side, 'above');
  assert.equal(p.top, 240 - 10 - 40);
  assert.equal(overlapArea({ ...p, ...bar }, label), 0);
});

test('near the top it goes below the label; off screen it docks at the top centre', () => {
  const high = { left: 300, top: 20, width: 120, height: 38 };
  const p = placeSelectionBar({ anchor: high, frame, bar, inset });
  assert.equal(p.side, 'below');
  assert.equal(p.top, 20 + 38 + 10);
  const off = { left: 300, top: 900, width: 120, height: 38 };
  assert.equal(placeSelectionBar({ anchor: off, frame, bar, inset }).side, 'docked');
  assert.equal(placeSelectionBar({ anchor: null, frame, bar, inset }).side, 'docked');
});

test('the bar stays inside the canvas and right of the tool cards', () => {
  const leftEdge = { left: 60, top: 300, width: 40, height: 30 };
  const p = placeSelectionBar({ anchor: leftEdge, frame, bar, inset });
  assert.ok(p.left >= 88);
  const rightEdge = { left: 800, top: 300, width: 40, height: 30 };
  const q = placeSelectionBar({ anchor: rightEdge, frame, bar, inset });
  assert.ok(q.left + bar.width <= frame.width - 8);
});

test('the bar never lands on the chrome cards: docked below the top row, or the other side of the label', () => {
  const topRow = { left: 300, top: 8, width: 520, height: 42 };
  const docked = placeSelectionBar({ anchor: null, frame, bar: { width: 400, height: 40 }, inset, avoid: [topRow] });
  assert.equal(docked.side, 'docked');
  assert.equal(docked.top, 8 + 42 + 10);
  // a label right under the top row: above would hit the row → below
  const label = { left: 500, top: 70, width: 100, height: 36 };
  const p = placeSelectionBar({ anchor: label, frame, bar: { width: 400, height: 40 }, inset, avoid: [topRow] });
  assert.equal(p.side, 'below');
  assert.equal(overlapArea({ ...p, width: 400, height: 40 }, topRow), 0);
});

test('the legend takes the first corner that covers nothing, else the least covered', () => {
  const size = { width: 260, height: 90 };
  const spots = [{ id: 'bottom-right', left: 560, top: 390 }, { id: 'top-right', left: 560, top: 56 }, { id: 'bottom-left', left: 88, top: 390 }];
  assert.equal(pickSpot({ spots, size, avoid: [] }), 'bottom-right');
  const label = { left: 600, top: 420, width: 100, height: 36 };
  assert.equal(pickSpot({ spots, size, avoid: [label] }), 'top-right');
  const panel = { left: 540, top: 40, width: 280, height: 300 };
  assert.equal(pickSpot({ spots, size, avoid: [label, panel] }), 'bottom-left');
  const everywhere = { left: 0, top: 0, width: 828, height: 534 };
  assert.ok(['bottom-right', 'top-right', 'bottom-left'].includes(pickSpot({ spots, size, avoid: [everywhere] })));
});

test('overlap area', () => {
  assert.equal(overlapArea({ left: 0, top: 0, width: 10, height: 10 }, { left: 5, top: 5, width: 10, height: 10 }), 25);
  assert.equal(overlapArea({ left: 0, top: 0, width: 10, height: 10 }, { left: 20, top: 0, width: 10, height: 10 }), 0);
  assert.equal(overlapArea(null, { left: 0, top: 0, width: 1, height: 1 }), 0);
});

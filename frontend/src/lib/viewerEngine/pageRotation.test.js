import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeRotation, rotatePctPoint, rotateBboxPct, rotateRoomGeometry } from './pageRotation.js';

test('normalizeRotation: quarter-turns and degrees', () => {
  assert.equal(normalizeRotation(3), 270);
  assert.equal(normalizeRotation(270), 270);
  assert.equal(normalizeRotation(0), 0);
  assert.equal(normalizeRotation(undefined), 0);
});

test('rotatePctPoint: 0 is identity', () => {
  assert.deepEqual(rotatePctPoint(0.3, 0.7, 0), [0.3, 0.7]);
});

test('rotatePctPoint: 270 maps (x,y)->(y,1-x)', () => {
  assert.deepEqual(rotatePctPoint(0.25, 0.10, 270), [0.10, 0.75]);
});

test('rotatePctPoint: 90 maps (x,y)->(1-y,x); 180 maps ->(1-x,1-y)', () => {
  assert.deepEqual(rotatePctPoint(0.25, 0.10, 90), [0.90, 0.25]);
  assert.deepEqual(rotatePctPoint(0.25, 0.10, 180), [0.75, 0.90]);
});

test('four 90° rotations return to origin', () => {
  let p = [0.2, 0.6];
  for (let i = 0; i < 4; i++) p = rotatePctPoint(p[0], p[1], 90);
  assert.ok(Math.abs(p[0] - 0.2) < 1e-9 && Math.abs(p[1] - 0.6) < 1e-9);
});

test('rotateBboxPct: 270 swaps w/h and repositions', () => {
  // landscape bbox at (0.08,0.15) size (0.35,0.4) -> corners rotated, axis-aligned
  const b = rotateBboxPct({ x: 0.08, y: 0.15, w: 0.35, h: 0.4 }, 270);
  assert.ok(Math.abs(b.w - 0.4) < 1e-9, 'w<->h swapped');
  assert.ok(Math.abs(b.h - 0.35) < 1e-9);
  assert.ok(Math.abs(b.x - 0.15) < 1e-9);   // new x = old y
  assert.ok(Math.abs(b.y - (1 - 0.08 - 0.35)) < 1e-9); // new y = 1-(x+w)
});

test('rotateRoomGeometry: rotation 0 returns same object', () => {
  const room = { nr: '1', bbox_pct: { x: 0.1, y: 0.1, w: 0.2, h: 0.2 } };
  assert.equal(rotateRoomGeometry(room, 0), room);
});

test('rotateRoomGeometry: rotates bbox_pct + polygon_pct', () => {
  const room = { nr: '1', bbox_pct: { x: 0.08, y: 0.15, w: 0.35, h: 0.4 }, polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]] };
  const r = rotateRoomGeometry(room, 270);
  assert.deepEqual(r.polygon_pct[0], [0.1, 0.9]); // (0.1,0.1)->(0.1,0.9)
  assert.ok(Math.abs(r.bbox_pct.w - 0.4) < 1e-9);
});

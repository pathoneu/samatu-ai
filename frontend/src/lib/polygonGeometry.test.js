import test from 'node:test';
import assert from 'node:assert/strict';
import { selfIntersects } from './polygonGeometry.js';

test('selfIntersects: simple square is not self-intersecting', () => {
  const square = [
    { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(square), false);
});

test('selfIntersects: bowtie is self-intersecting', () => {
  // Classic bowtie — edges (p0→p1) and (p2→p3) cross
  const bowtie = [
    { x: 0, y: 0 }, { x: 10, y: 10 }, { x: 10, y: 0 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(bowtie), true);
});

test('selfIntersects: triangle is not self-intersecting', () => {
  const tri = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 5, y: 10 }];
  assert.equal(selfIntersects(tri), false);
});

test('selfIntersects: shared vertex between adjacent edges is allowed', () => {
  // Adjacent edges share a vertex — that's NOT self-intersection
  const square = [
    { x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 },
  ];
  assert.equal(selfIntersects(square), false);
});

import { orthoSnap } from './polygonGeometry.js';

test('orthoSnap: cursor near horizontal locks to horizontal', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 5 };  // 2.86° from horizontal — within 15° tolerance
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: false, altHeld: false });
  assert.equal(out.y, 0);
  assert.equal(out.x, 100);
});

test('orthoSnap: cursor far from any axis returns cursor unchanged', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 100 };  // 45° — outside tolerance for {0, 90}
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: false, altHeld: false });
  assert.deepEqual(out, cursor);
});

test('orthoSnap: shiftHeld enables 45° increments', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 100 };
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: true, altHeld: false });
  // Should snap to 45° → x ≈ y ≈ 100
  assert.ok(Math.abs(out.x - 100) < 1);
  assert.ok(Math.abs(out.y - 100) < 1);
});

test('orthoSnap: altHeld disables ortho regardless', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 5 };
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: false, altHeld: true });
  assert.deepEqual(out, cursor);
});

test('orthoSnap: orthoEnabled=false passes through', () => {
  const prev = { x: 0, y: 0 };
  const cursor = { x: 100, y: 5 };
  const out = orthoSnap(prev, cursor, { orthoEnabled: false, shiftHeld: false, altHeld: false });
  assert.deepEqual(out, cursor);
});

test('orthoSnap: vertical lock', () => {
  const prev = { x: 50, y: 0 };
  const cursor = { x: 53, y: 100 };  // ~1.7° from vertical
  const out = orthoSnap(prev, cursor, { orthoEnabled: true, shiftHeld: false, altHeld: false });
  assert.equal(out.x, 50);
  assert.equal(out.y, 100);
});

import { pointInPolygon } from './polygonGeometry.js';

test('pointInPolygon: center of square is inside', () => {
  const sq = [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}];
  assert.equal(pointInPolygon({x:5,y:5}, sq), true);
});

test('pointInPolygon: outside is outside', () => {
  const sq = [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}];
  assert.equal(pointInPolygon({x:15,y:5}, sq), false);
});

test('pointInPolygon: on edge is true (consistent with click-to-select)', () => {
  const sq = [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}];
  // On the right edge — hitting an edge during click-to-select must register
  assert.equal(pointInPolygon({x:10,y:5}, sq), true);
});

import { nearestVertex } from './polygonGeometry.js';

test('nearestVertex: snaps to nearest within tolerance', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:5,y:10}] }];
  const result = nearestVertex({x:1,y:1}, polys, 12);
  assert.deepEqual(result.point, {x:0,y:0});
  assert.equal(result.polygonId, 'a');
});

test('nearestVertex: returns null when no vertex within tolerance', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:5,y:10}] }];
  const result = nearestVertex({x:50,y:50}, polys, 12);
  assert.equal(result, null);
});

test('nearestVertex: skips excludePolygonId (so a polygon does not snap to itself)', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:5,y:10}] }];
  const result = nearestVertex({x:1,y:1}, polys, 12, { excludePolygonId: 'a' });
  assert.equal(result, null);
});

test('nearestVertex: returns closest of multiple candidates', () => {
  const polys = [
    { id: 'a', points: [{x:0,y:0},{x:10,y:0}] },
    { id: 'b', points: [{x:5,y:5},{x:15,y:5}] },
  ];
  const result = nearestVertex({x:6,y:5}, polys, 12);
  assert.deepEqual(result.point, {x:5,y:5});
  assert.equal(result.polygonId, 'b');
});

import { nearestEdge } from './polygonGeometry.js';

test('nearestEdge: snaps to perpendicular foot on edge', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}] }];
  // Cursor at (5, 2) — perpendicular foot on the bottom edge is (5, 0)
  const result = nearestEdge({x:5,y:2}, polys, 8);
  assert.deepEqual(result.point, {x:5,y:0});
  assert.equal(result.polygonId, 'a');
  assert.equal(result.edgeIndex, 0);
});

test('nearestEdge: returns null beyond tolerance', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}] }];
  const result = nearestEdge({x:50,y:50}, polys, 8);
  assert.equal(result, null);
});

test('nearestEdge: skips edges of excludePolygonId', () => {
  const polys = [{ id: 'a', points: [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}] }];
  const result = nearestEdge({x:5,y:2}, polys, 8, { excludePolygonId: 'a' });
  assert.equal(result, null);
});

import { polygonCentroid } from './polygonGeometry.js';

test('polygonCentroid: square center is at 5,5', () => {
  const sq = [{x:0,y:0},{x:10,y:0},{x:10,y:10},{x:0,y:10}];
  const c = polygonCentroid(sq);
  assert.ok(Math.abs(c.x - 5) < 0.001);
  assert.ok(Math.abs(c.y - 5) < 0.001);
});

test('polygonCentroid: degenerate polygon (< 3 pts) returns null', () => {
  assert.equal(polygonCentroid([{x:0,y:0},{x:1,y:1}]), null);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { snapPolygonsFromGeometry, pickSnap } from './drawingSnap.js';
import { inverseRotatePctPoint } from './viewerEngine/pageRotation.js';

const geometry = { status: 'ok', walls_pct: [[[0.1, 0.2], [0.5, 0.2], [0.5, 0.3], [0.1, 0.3]]] };

test('rings in display fractions become PDF-point polygons on an unrotated page', () => {
  const polys = snapPolygonsFromGeometry(geometry, { pageWidthPt: 1000, pageHeightPt: 500, pageRotation: 0 });
  assert.equal(polys.length, 1);
  assert.equal(polys[0].open, false);
  assert.deepEqual(polys[0].points[0], { x: 100, y: 100 });
  assert.deepEqual(polys[0].points[2], { x: 500, y: 150 });
});

test('a /Rotate 90 page maps display fractions back to the unrotated mediabox, like the adapter', () => {
  const polys = snapPolygonsFromGeometry({ walls_pct: [[[0.8, 0.1], [0.8, 0.4], [0.7, 0.4]]] },
    { pageWidthPt: 1000, pageHeightPt: 500, pageRotation: 90 });
  const [ux, uy] = inverseRotatePctPoint(0.8, 0.1, 90);
  const p = polys[0].points[0];
  assert.ok(Math.abs(p.x - ux * 1000) < 1e-9 && Math.abs(p.y - uy * 500) < 1e-9, JSON.stringify(p));
  // and it is NOT the unrotated identity
  assert.ok(Math.abs(p.x - 800) > 1 || Math.abs(p.y - 50) > 1);
});

test('empty or missing geometry gives no polygons', () => {
  assert.deepEqual(snapPolygonsFromGeometry(null, { pageWidthPt: 1, pageHeightPt: 1 }), []);
  assert.deepEqual(snapPolygonsFromGeometry({ walls_pct: [[[0, 0], [1, 1]]] }, { pageWidthPt: 1, pageHeightPt: 1 }), []);
  assert.deepEqual(snapPolygonsFromGeometry(geometry, { pageWidthPt: 0, pageHeightPt: 1 }), []);
});

test('pickSnap prefers a drawing corner, then a measurement vertex, then edges', () => {
  const drawing = [{ id: 'wall-0', open: false, points: [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 50 }, { x: 0, y: 50 }] }];
  const measurements = [{ id: 'm1', open: true, points: [{ x: 3, y: 3 }, { x: 60, y: 3 }] }];
  assert.deepEqual(pickSnap({ x: 2, y: 2 }, { drawing, measurements }, 8), { point: { x: 0, y: 0 }, kind: 'drawing-vertex' });
  assert.deepEqual(pickSnap({ x: 61, y: 5 }, { drawing, measurements }, 8), { point: { x: 60, y: 3 }, kind: 'measure-vertex' });
  assert.deepEqual(pickSnap({ x: 50, y: 4 }, { drawing, measurements: [] }, 8), { point: { x: 50, y: 0 }, kind: 'drawing-edge' });
  assert.equal(pickSnap({ x: 50, y: 25 }, { drawing, measurements }, 8), null);
});

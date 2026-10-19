import test from 'node:test';
import assert from 'node:assert/strict';
import {
  pointsToPct, pctToPoints, minPointsOf, moveEdge, verticesInBox, deleteVertices, nudgeVertices, insertVertex, projectT,
  pathPositionM, cutGap, boxMode, marksInBox, roomsInBox, similarRooms, rectanglePoints, arcPoints, pointAtLength,
  typedLength, copyMeasurement, wallFaceAt, shapeTouchesRect,
} from './editGestures.js';

const close = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) <= eps, `${a} ≉ ${b}`);
// 1 pt = 1 cm on paper-ish: an easy scale for the arithmetic
const SCALE = { metersPerPointX: 0.01, metersPerPointY: 0.01, calibrated: true };

test('a measurement goes into the vertex editor and back unchanged, on every rotation', () => {
  const pts = [{ x: 100, y: 50 }, { x: 300, y: 50 }, { x: 300, y: 400 }];
  for (const rotation of [0, 90, 180, 270]) {
    const size = { width: 842, height: 595, rotation };
    const back = pctToPoints(pointsToPct(pts, size), size);
    back.forEach((p, i) => { close(p.x, pts[i].x, 1e-6); close(p.y, pts[i].y, 1e-6); });
  }
  assert.equal(minPointsOf('area'), 3);
  assert.equal(minPointsOf('distance'), 2);
});

test('moving an edge moves both its corners; a snap at either end sets the move', () => {
  const ring = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.1, 0.5]];
  const { points } = moveEdge(ring, 0, 0, 0.05);
  close(points[0][1], 0.15); close(points[1][1], 0.15); close(points[1][0], 0.5);
  assert.deepEqual(points[2], [0.5, 0.5]);
  // the second end snaps to a wall at y = 0.2 → the whole edge goes there
  const snap = (p) => (Math.abs(p[0] - 0.5) < 0.01 ? [0.5, 0.2] : null);
  const res = moveEdge(ring, 0, 0, 0.09, { snap });
  assert.deepEqual(res.snapped, [0.5, 0.2]);
  close(res.points[0][1], 0.2); close(res.points[1][1], 0.2);
  // an open path has no closing edge
  assert.equal(moveEdge(ring, 3, 0, 0.1, { closed: false }).points, ring);
});

test('box picks corners; delete several never goes below the minimum; nudge stays on the sheet', () => {
  const ring = [[0.1, 0.1], [0.5, 0.1], [0.5, 0.5], [0.3, 0.6], [0.1, 0.5]];
  assert.deepEqual(verticesInBox(ring, [0.4, 0], [0.6, 0.55]), [1, 2]);
  assert.deepEqual(deleteVertices(ring, [1, 3]).points, [[0.1, 0.1], [0.5, 0.5], [0.1, 0.5]]);
  assert.equal(deleteVertices(ring, [0, 1, 2]).refused, true);
  assert.equal(deleteVertices([[0, 0], [1, 1]], [0], 2).refused, true);
  assert.deepEqual(nudgeVertices(ring, [0], -0.2, 0)[0], [0, 0.1]);
  assert.deepEqual(insertVertex(ring, 0, [0.3, 0.1])[1], [0.3, 0.1]);
  close(projectT([0.3, 0.2], [0.1, 0.1], [0.5, 0.1]), 0.5);
});

test('„Iškirpti angą" cuts a doorway gap out of a length where he points', () => {
  // a 6 m wall (600 pt), door 0,9 m centred 2 m along it
  const wall = [{ x: 0, y: 0 }, { x: 600, y: 0 }];
  const parts = cutGap(wall, SCALE, 2, 0.9);
  assert.equal(parts.length, 2);
  close(parts[0][1].x, 155); close(parts[1][0].x, 245);
  // centred at a corner of a perimeter: both sides lose half
  const per = [{ x: 0, y: 0 }, { x: 300, y: 0 }, { x: 300, y: 300 }];
  const at = pathPositionM(per, SCALE, { vertex: 1 });
  close(at, 3);
  const cut = cutGap(per, SCALE, at, 1);
  close(cut[0][cut[0].length - 1].x, 250);
  close(cut[1][0].y, 50);
  assert.deepEqual(cut[1][cut[1].length - 1], { x: 300, y: 300 });
  // at the very start, the gap is kept inside the path → one piece
  assert.equal(cutGap(wall, SCALE, 0, 0.9).length, 1);
  // too short or no scale → nothing
  assert.equal(cutGap([{ x: 0, y: 0 }, { x: 50, y: 0 }], SCALE, 0.2, 0.9), null);
  assert.equal(cutGap(wall, { calibrated: false }, 2, 0.9), null);
  close(pathPositionM(per, SCALE, { edge: 1, t: 0.5 }), 4.5);
});

test('box selection: left→right whole shapes, right→left touched ones', () => {
  assert.equal(boxMode({ x: 0 }, { x: 10 }), 'window');
  assert.equal(boxMode({ x: 10 }, { x: 0 }), 'crossing');
  const ms = [
    { id: 'in', page: 1, kind: 'distance', points: [{ x: 10, y: 10 }, { x: 20, y: 10 }] },
    { id: 'half', page: 1, kind: 'distance', points: [{ x: 40, y: 10 }, { x: 200, y: 10 }] },
    { id: 'around', page: 1, kind: 'area', points: [{ x: -100, y: -100 }, { x: 300, y: -100 }, { x: 300, y: 300 }, { x: -100, y: 300 }] },
    { id: 'other', page: 2, kind: 'count', points: [{ x: 15, y: 15 }] },
  ];
  assert.deepEqual(marksInBox(ms, 1, { x: 0, y: 0 }, { x: 50, y: 50 }, 'window'), ['in']);
  assert.deepEqual(marksInBox(ms, 1, { x: 0, y: 0 }, { x: 50, y: 50 }, 'crossing'), ['in', 'half', 'around']);
  assert.equal(shapeTouchesRect([{ x: 0, y: 0 }, { x: 10, y: 0 }], { x0: 20, x1: 30, y0: 20, y1: 30 }, false), false);
});

test('rooms in a box and rooms like this one', () => {
  const rooms = [
    { nr: '01', puslapio_nr: 1, polygon_source: 'corrected', polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]], paskirtis: 'miegamoji', grindu_danga: 'minksta' },
    { nr: '02', puslapio_nr: 1, polygon_source: 'corrected', polygon_pct: [[0.3, 0.1], [0.6, 0.1], [0.6, 0.4], [0.3, 0.4]], paskirtis: 'san', grindu_danga: 'plyteles' },
    { nr: '03', puslapio_nr: 1, polygon_source: 'corrected', polygon_pct: [[0.7, 0.7], [0.8, 0.7], [0.8, 0.8], [0.7, 0.8]], paskirtis: 'miegamoji', grindu_danga: 'plyteles' },
    { nr: '04', puslapio_nr: 1, paskirtis: 'miegamoji', _sujungta_i: '03' },
  ];
  assert.deepEqual(roomsInBox(rooms, 1, [0.05, 0.05], [0.4, 0.3], 'window'), ['01']);
  assert.deepEqual(roomsInBox(rooms, 1, [0.4, 0.3], [0.05, 0.05], 'crossing'), ['01', '02']);
  assert.deepEqual(roomsInBox(rooms, 1, [0.05, 0.05], [0.4, 0.3], 'window', ['01']), []);
  assert.deepEqual(similarRooms(rooms, '01', 'paskirtis'), ['03']);
  assert.deepEqual(similarRooms(rooms, '02', 'grindu_danga'), ['03']);
  assert.deepEqual(similarRooms([{ nr: '9' }], '9', 'paskirtis'), []);
});

test('drawing: rectangle, arc through three points, typed length', () => {
  assert.deepEqual(rectanglePoints({ x: 0, y: 0 }, { x: 10, y: 5 }), [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 5 }, { x: 0, y: 5 }]);
  const arc = arcPoints({ x: -10, y: 0 }, { x: 0, y: -10 }, { x: 10, y: 0 }, 8);
  assert.equal(arc.length, 9);
  for (const p of arc) close(Math.hypot(p.x, p.y), 10, 1e-6);
  assert.ok(arc[4].y < 0, 'passes through the middle point side');
  assert.equal(arcPoints({ x: 0, y: 0 }, { x: 5, y: 0 }, { x: 10, y: 0 }).length, 2);
  const end = pointAtLength({ x: 0, y: 0 }, { x: 30, y: 40 }, 2.5, SCALE);
  close(end.x, 150); close(end.y, 200);
  assert.equal(pointAtLength({ x: 0, y: 0 }, { x: 1, y: 0 }, 2, { calibrated: false }), null);
  assert.equal(typedLength('3,25'), 3.25);
  assert.equal(typedLength('3.'), 3);
  assert.equal(typedLength(''), null);
  assert.equal(typedLength('a1'), null);
});

test('a copy is a new measurement of his: new id, moved, no row link carried', () => {
  const m = { id: 'a', kind: 'area', page: 1, points: [{ x: 1, y: 1 }], holes: [[{ x: 2, y: 2 }]], eilute_id: 'r1', kaip: 'kiekis', color: '#123' };
  const c = copyMeasurement(m, { page: 3, dx: 10, dy: 0, id: 'b' });
  assert.equal(c.id, 'b'); assert.equal(c.page, 3); assert.equal(c.color, '#123');
  assert.deepEqual(c.points, [{ x: 11, y: 1 }]);
  assert.deepEqual(c.holes, [[{ x: 12, y: 2 }]]);
  assert.equal(c.eilute_id, undefined); assert.equal(c.kaip, undefined);
});

test('a wall face under the click is the two ends of a length', () => {
  const rings = [{ points: [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 10 }, { x: 0, y: 10 }] }];
  assert.deepEqual(wallFaceAt(rings, { x: 50, y: 11 }, 3), { a: { x: 100, y: 10 }, b: { x: 0, y: 10 } });
  assert.equal(wallFaceAt(rings, { x: 50, y: 30 }, 3), null);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  displaySizePt, pctRingToPts, ptsRingToPct, ringArea, ringPerimeter, cleanRing, splitRingByLine, ringAt,
  unionTouchingRings, rectRing, holeFit, holesInside, lassoSelect,
} from './outlineTools.js';

const R = (...xy) => xy.map(([x, y]) => ({ x, y }));
const near = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) <= eps, `${a} ≉ ${b}`);
const square = R([0, 0], [10, 0], [10, 10], [0, 10]);

test('frames: a turned sheet swaps its size; pct ↔ points round-trip at 5 decimals', () => {
  assert.deepEqual(displaySizePt({ width: 842, height: 595 }, 90), { width: 595, height: 842 });
  assert.deepEqual(displaySizePt({ width: 842, height: 595 }, 0), { width: 842, height: 595 });
  assert.equal(displaySizePt(null), null);
  const size = { width: 200, height: 100 };
  const pts = pctRingToPts([[0.1, 0.2], [0.5, 0.2], [0.5, 0.9]], size);
  assert.deepEqual(pts, R([20, 20], [100, 20], [100, 90]));
  assert.deepEqual(ptsRingToPct(pts, size), [[0.1, 0.2], [0.5, 0.2], [0.5, 0.9]]);
  assert.deepEqual(ptsRingToPct(R([-5, 0], [250, 50]), size), [[0, 0], [1, 0.5]]);   // clamped to the sheet
});

test('cleanRing drops repeated and collinear corners', () => {
  const r = cleanRing(R([0, 0], [5, 0], [10, 0], [10, 0], [10, 10], [0, 10], [0, 0]));
  assert.deepEqual(r, square);
  near(ringArea(square), 100);
  near(ringPerimeter(square), 40);
});

test('split: a line across a square gives two halves that add up to it', () => {
  const out = splitRingByLine(square, { x: 4, y: -3 }, { x: 4, y: 13 });
  assert.equal(out.status, 'ok');
  const areas = out.rings.map(ringArea).sort((a, b) => a - b);
  near(areas[0], 40);
  near(areas[1], 60);
  assert.deepEqual(out.chord.map((p) => [p.x, p.y]).sort(), [[4, 0], [4, 10]]);
  assert.equal(ringAt({ x: 2, y: 5 }, out.rings), out.rings.findIndex((r) => ringArea(r) === areas[0]));
  assert.equal(ringAt({ x: 50, y: 5 }, out.rings), -1);
});

test('split: the two clicks may lie inside the outline — the line through them is extended to its edges', () => {
  const out = splitRingByLine(square, { x: 2, y: 3 }, { x: 8, y: 3 });
  assert.equal(out.status, 'ok');
  near(ringArea(out.rings[0]) + ringArea(out.rings[1]), 100);
  assert.deepEqual(out.rings.map(ringArea).sort((a, b) => a - b), [30, 70]);
});

test('split: on a U-shaped room the line cuts only the arm the person pointed at', () => {
  // U: two arms (x 0–3 and 7–10) joined at the bottom (y 7–10); a horizontal line at y=2 crosses BOTH arms
  const u = R([0, 0], [3, 0], [3, 7], [7, 7], [7, 0], [10, 0], [10, 10], [0, 10]);
  const left = splitRingByLine(u, { x: 0.5, y: 2 }, { x: 2.5, y: 2 });
  assert.equal(left.status, 'ok');
  assert.deepEqual(left.rings.map(ringArea).sort((a, b) => a - b), [6, 66]);   // the left arm's top 3×2 (the U is 72)
  const right = splitRingByLine(u, { x: 7.5, y: 2 }, { x: 9.5, y: 2 });
  assert.deepEqual(right.rings.map(ringArea).sort((a, b) => a - b), [6, 66]);
  assert.ok(right.rings.some((r) => r.some((p) => p.x === 10 && p.y === 0)));
});

test('split: a line that misses the outline, or only grazes a corner, is refused', () => {
  assert.equal(splitRingByLine(square, { x: 20, y: 0 }, { x: 20, y: 10 }).status, 'miss');
  assert.equal(splitRingByLine(square, { x: 3, y: 3 }, { x: 3, y: 3 }).status, 'miss');
  assert.notEqual(splitRingByLine(square, { x: -1, y: 1 }, { x: 1, y: -1 }).status, 'ok');   // through the corner only
});

test('split: a line through a corner and across the room works', () => {
  const out = splitRingByLine(square, { x: 0, y: 0 }, { x: 10, y: 10 });
  assert.equal(out.status, 'ok');
  assert.deepEqual(out.rings.map(ringArea), [50, 50]);
});

test('union: two rooms sharing a whole wall line become one', () => {
  const b = R([10, 0], [16, 0], [16, 10], [10, 10]);
  const out = unionTouchingRings(square, b, 0.5);
  assert.equal(out.status, 'ok');
  near(ringArea(out.ring), 160);
  assert.equal(out.ring.length, 4);              // the shared line and its corners are gone
  assert.deepEqual(out.holes, []);
});

test('union: a shorter neighbour along part of the edge, drawn a hair off it, still joins', () => {
  const b = R([10.2, 2], [14, 2], [14, 6], [10.2, 6]);    // 0.2 pt gap: within the tolerance
  const out = unionTouchingRings(square, b, 0.5);
  assert.equal(out.status, 'ok');
  near(ringArea(out.ring), 100 + 3.8 * 4 + 0.2 * 4, 1e-6);   // the snapped neighbour reaches the edge
  assert.equal(out.ring.length, 8);
});

test('union: an L meeting a square along two stretches keeps every outer corner', () => {
  const l = R([0, 0], [20, 0], [20, 10], [10, 10], [10, 20], [0, 20]);
  const sq = R([10, 10], [20, 10], [20, 20], [10, 20]);
  const out = unionTouchingRings(l, sq, 0.5);
  assert.equal(out.status, 'ok');
  near(ringArea(out.ring), 400);
  assert.equal(out.ring.length, 4);
});

test('union: rooms a wall keeps apart are refused, not bridged', () => {
  const b = R([12, 0], [20, 0], [20, 10], [12, 10]);      // a 2 pt wall between them
  assert.equal(unionTouchingRings(square, b, 0.5).status, 'apart');
});

test('union: overlapping outlines are refused', () => {
  const b = R([5, 0], [15, 0], [15, 10], [5, 10]);
  assert.equal(unionTouchingRings(square, b, 0.5).status, 'overlap');
});

test('union: a U and the block closing its mouth enclose a courtyard — it comes back as a hole', () => {
  const u = R([0, 0], [3, 0], [3, 7], [7, 7], [7, 0], [10, 0], [10, 10], [0, 10]);
  const lid = R([0, -3], [10, -3], [10, 0], [7, 0], [3, 0], [0, 0]);
  const out = unionTouchingRings(u, lid, 0.5);
  assert.equal(out.status, 'ok');
  near(ringArea(out.ring), 130);
  assert.equal(out.holes.length, 1);
  near(ringArea(out.holes[0]), 28);
});

test('holes: a rectangle inside the outline fits; outside, crossing or overlapping does not', () => {
  const col = rectRing({ x: 2, y: 2 }, { x: 4, y: 4 });
  assert.equal(holeFit(col, square), 'ok');
  assert.equal(holeFit(rectRing({ x: 8, y: 8 }, { x: 12, y: 12 }), square), 'outside');
  assert.equal(holeFit(rectRing({ x: 3, y: 3 }, { x: 5, y: 5 }), square, [col]), 'overlap');
  assert.equal(holeFit(rectRing({ x: 5, y: 5 }, { x: 5.1, y: 5.1 }), square), 'small');
  assert.equal(holeFit(R([2, 2], [6, 6], [6, 2], [2, 6]), square), 'crossing');
  assert.equal(holeFit(rectRing({ x: 6, y: 6 }, { x: 8, y: 8 }), square, [col]), 'ok');
});

test('holes: after a split each half keeps the holes it holds', () => {
  const holes = [rectRing({ x: 1, y: 1 }, { x: 2, y: 2 }), rectRing({ x: 7, y: 7 }, { x: 8, y: 9 })];
  const [a, b] = splitRingByLine(square, { x: 5, y: -1 }, { x: 5, y: 11 }).rings;
  const left = a.some((p) => p.x === 0) ? a : b;
  const right = left === a ? b : a;
  assert.deepEqual(holesInside(left, holes), [holes[0]]);
  assert.deepEqual(holesInside(right, holes), [holes[1]]);
});

test('lasso: takes the marks wholly inside, on its page only', () => {
  const ms = [
    { id: 'c1', page: 1, kind: 'count', points: [{ x: 5, y: 5 }] },
    { id: 'c2', page: 1, kind: 'count', points: [{ x: 50, y: 5 }] },
    { id: 'd1', page: 1, kind: 'distance', points: [{ x: 2, y: 2 }, { x: 8, y: 8 }] },
    { id: 'd2', page: 1, kind: 'distance', points: [{ x: 2, y: 2 }, { x: 18, y: 8 }] },   // half out
    { id: 'c3', page: 2, kind: 'count', points: [{ x: 5, y: 5 }] },
  ];
  assert.deepEqual(lassoSelect(ms, 1, square), ['c1', 'd1']);
  assert.deepEqual(lassoSelect(ms, 2, square), ['c3']);
  assert.deepEqual(lassoSelect(ms, 1, R([0, 0], [1, 1])), []);
});

test('„Kas atimama?": a hole has walls unless he said otherwise, and the answer follows the hole by place', async () => {
  const { holeHasWalls, roomHoleWalls, sameHole } = await import('./outlineTools.js');
  const column = [[0.1, 0.1], [0.12, 0.1], [0.12, 0.12], [0.1, 0.12]];
  const floorHole = [[0.3, 0.3], [0.34, 0.3], [0.34, 0.34], [0.3, 0.34]];
  const room = { polygon_holes_pct: [column, floorHole],
    _konturas: { skyles: [{ perimetras_m: 2, sienos: true }, { perimetras_m: 3, sienos: false }] } };
  const answers = roomHoleWalls(room);
  assert.deepEqual(answers.map((a) => a.sienos), [true, false]);
  assert.equal(holeHasWalls(column, answers), true);
  assert.equal(holeHasWalls(floorHole, answers), false);
  // the same hole re-drawn in another order of points (a split's ring) keeps its answer
  assert.equal(holeHasWalls([...floorHole].reverse(), answers), false);
  assert.equal(sameHole(column, floorHole), false);
  // a new hole, and a room saved before the question existed: walls
  assert.equal(holeHasWalls([[0.5, 0.5], [0.6, 0.5], [0.6, 0.6]], answers), true);
  assert.deepEqual(roomHoleWalls({ polygon_holes_pct: [column], _konturas: { skyles: 1 } }).map((a) => a.sienos), [true]);
});

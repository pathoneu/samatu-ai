/**
 * outlineTools — the geometry behind the viewer's outline tools (2026-10-16, Togal analysis §6):
 * „Padalyti" (one line cuts a room's outline in two), „Sujungti" (two touching outlines become one),
 * „Atimti" (a column, a closet or a shaft cut out of an outline as a hole) and „Laso" (a freehand
 * region selects every measurement and count mark inside it).
 *
 * Pure functions, no React. Rings are arrays of {x, y} in ONE linear frame — the callers use PDF
 * points of the displayed sheet (pctRingToPts), so a tolerance in points means the same thing on
 * every sheet and every zoom. Nothing here knows about rooms, scales or the server.
 */

const EPS = 1e-9;

const sub = (a, b) => ({ x: a.x - b.x, y: a.y - b.y });
const cross = (a, b) => a.x * b.y - a.y * b.x;
const dot = (a, b) => a.x * b.x + a.y * b.y;
const same = (a, b, eps = 1e-6) => Math.abs(a.x - b.x) <= eps && Math.abs(a.y - b.y) <= eps;

/** The displayed sheet's size in PDF points (a 90°/270° page shows its mediabox turned). */
export function displaySizePt(pageSizePt, displayRotation = 0) {
  const w = Number(pageSizePt?.width);
  const h = Number(pageSizePt?.height);
  if (!(w > 0) || !(h > 0)) return null;
  const turned = displayRotation === 90 || displayRotation === 270;
  return turned ? { width: h, height: w } : { width: w, height: h };
}

/** [[fx, fy], …] display fractions → [{x, y}, …] points of a sheet `size` = {width, height}. */
export function pctRingToPts(ring, size) {
  return (ring || []).map(([fx, fy]) => ({ x: Number(fx) * size.width, y: Number(fy) * size.height }));
}

/** …and back, clamped to the sheet and rounded the way the server stores them (5 decimals). */
export function ptsRingToPct(ring, size) {
  const c = (v) => Math.min(1, Math.max(0, v));
  const r = (v) => Math.round(v * 1e5) / 1e5;
  return (ring || []).map((p) => [r(c(p.x / size.width)), r(c(p.y / size.height))]);
}

/** Signed shoelace area (positive = counter-clockwise in a y-up frame). */
export function signedArea(ring) {
  let s = 0;
  for (let i = 0; i < ring.length; i++) {
    const p = ring[i];
    const q = ring[(i + 1) % ring.length];
    s += p.x * q.y - q.x * p.y;
  }
  return s / 2;
}

export function ringArea(ring) {
  return Math.abs(signedArea(ring || []));
}

export function ringPerimeter(ring) {
  let s = 0;
  for (let i = 0; i < (ring || []).length; i++) {
    const p = ring[i];
    const q = ring[(i + 1) % ring.length];
    s += Math.hypot(q.x - p.x, q.y - p.y);
  }
  return s;
}

/** Strictly-inside ray cast (a point ON an edge is decided by the half-open rule — callers add a tolerance). */
export function insideRing(p, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i];
    const b = ring[j];
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

/** Distance from `p` to the segment a–b, and the nearest point on it ({d, point, t}). */
export function segmentDistance(p, a, b) {
  const ab = sub(b, a);
  const len2 = dot(ab, ab);
  const t = len2 > EPS ? Math.min(1, Math.max(0, dot(sub(p, a), ab) / len2)) : 0;
  const point = { x: a.x + ab.x * t, y: a.y + ab.y * t };
  return { d: Math.hypot(p.x - point.x, p.y - point.y), point, t };
}

/** Distance from `p` to the ring's boundary. */
export function boundaryDistance(p, ring) {
  let best = Infinity;
  for (let i = 0; i < ring.length; i++) best = Math.min(best, segmentDistance(p, ring[i], ring[(i + 1) % ring.length]).d);
  return best;
}

function dedupe(ring, eps = 1e-6) {
  const pts = [];
  for (const p of ring || []) if (!pts.length || !same(pts[pts.length - 1], p, eps)) pts.push(p);
  while (pts.length > 1 && same(pts[0], pts[pts.length - 1], eps)) pts.pop();
  return pts;
}

/** Drop repeated points and points that lie on the straight line between their neighbours. */
export function cleanRing(ring, eps = 1e-6) {
  let pts = dedupe(ring, eps);
  let changed = true;
  while (changed && pts.length > 3) {
    changed = false;
    for (let i = 0; i < pts.length; i++) {
      const a = pts[(i - 1 + pts.length) % pts.length];
      const b = pts[i];
      const c = pts[(i + 1) % pts.length];
      const span = Math.hypot(c.x - a.x, c.y - a.y);
      // collinear: b sits on a–c within eps (relative to the span), and between them
      if (span > EPS && Math.abs(cross(sub(b, a), sub(c, a))) / span <= eps * 10 && dot(sub(b, a), sub(c, b)) >= 0) {
        pts = pts.filter((_, k) => k !== i);
        changed = true;
        break;
      }
    }
  }
  return pts;
}

function segmentsCross(a, b, c, d) {
  const d1 = cross(sub(b, a), sub(c, a));
  const d2 = cross(sub(b, a), sub(d, a));
  const d3 = cross(sub(d, c), sub(a, c));
  const d4 = cross(sub(d, c), sub(b, c));
  return ((d1 > EPS && d2 < -EPS) || (d1 < -EPS && d2 > EPS)) && ((d3 > EPS && d4 < -EPS) || (d3 < -EPS && d4 > EPS));
}

/** True when some edge of `a` properly crosses some edge of `b` (touching does not count). */
export function ringsCross(a, b) {
  for (let i = 0; i < a.length; i++) {
    for (let j = 0; j < b.length; j++) {
      if (segmentsCross(a[i], a[(i + 1) % a.length], b[j], b[(j + 1) % b.length])) return true;
    }
  }
  return false;
}

// ── „Padalyti" ────────────────────────────────────────────────────────────────────────────────────

/**
 * Cut `ring` along the line through `a` and `b`. The line may cross a bent outline more than twice;
 * the cut is the ONE chord inside the outline that the person pointed at — the stretch of the line
 * between two consecutive crossings that holds the middle of a–b (or, failing that, comes nearest to
 * it). → {status: 'ok', rings: [r1, r2], chord: [P, Q]} | {status: 'miss'} (the line never enters the
 * outline) | {status: 'degenerate'} (a piece would have no area).
 */
export function splitRingByLine(ring, a, b, { minArea = 1 } = {}) {
  const pts = cleanRing(ring);
  const dir = sub(b, a);
  const len2 = dot(dir, dir);
  if (pts.length < 3 || len2 <= EPS) return { status: 'miss' };
  const side = (p) => (cross(dir, sub(p, a)) >= 0 ? 1 : -1);
  const hits = [];
  for (let i = 0; i < pts.length; i++) {
    const p = pts[i];
    const q = pts[(i + 1) % pts.length];
    if (side(p) === side(q)) continue;
    const sp = cross(dir, sub(p, a));
    const sq = cross(dir, sub(q, a));
    const t = sp / (sp - sq);
    const point = { x: p.x + (q.x - p.x) * t, y: p.y + (q.y - p.y) * t };
    hits.push({ edge: i, t, point, u: dot(sub(point, a), dir) / len2 });
  }
  if (hits.length < 2 || hits.length % 2) return { status: 'miss' };
  hits.sort((h, k) => h.u - k.u);
  let pick = null;
  let bestGap = Infinity;
  for (let k = 0; k + 1 < hits.length; k += 2) {
    const lo = hits[k].u;
    const hi = hits[k + 1].u;
    const gap = lo <= 0.5 && hi >= 0.5 ? 0 : Math.min(Math.abs(lo - 0.5), Math.abs(hi - 0.5));
    if (gap < bestGap) { bestGap = gap; pick = [hits[k], hits[k + 1]]; }
  }
  let [P, Q] = pick;
  if (P.edge === Q.edge) return { status: 'degenerate' };
  // walk the ring from P's edge to Q's edge and back
  if (P.edge > Q.edge) [P, Q] = [Q, P];
  const n = pts.length;
  const one = [P.point];
  for (let i = P.edge + 1; i <= Q.edge; i++) one.push(pts[i]);
  one.push(Q.point);
  const two = [Q.point];
  for (let i = Q.edge + 1; i <= P.edge + n; i++) two.push(pts[i % n]);
  two.push(P.point);
  const rings = [cleanRing(one), cleanRing(two)];
  if (rings.some((r) => r.length < 3 || ringArea(r) < minArea)) return { status: 'degenerate' };
  return { status: 'ok', rings, chord: [P.point, Q.point] };
}

/** Which of `rings` holds `p` (index), or -1. */
export function ringAt(p, rings) {
  return (rings || []).findIndex((r) => insideRing(p, r));
}

// ── „Sujungti" ────────────────────────────────────────────────────────────────────────────────────

const key = (p) => `${p.x.toFixed(6)},${p.y.toFixed(6)}`;

function ccw(ring) {
  return signedArea(ring) < 0 ? ring.slice().reverse() : ring.slice();
}

// Every point of `points` that lies on an edge of `ring` (within `tol`, not at its ends) becomes a vertex there.
function withPointsOnEdges(ring, points, tol) {
  const out = [];
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i];
    const b = ring[(i + 1) % ring.length];
    out.push(a);
    const on = [];
    for (const p of points) {
      if (same(p, a) || same(p, b)) continue;
      const s = segmentDistance(p, a, b);
      if (s.d <= tol && s.t > 1e-9 && s.t < 1 - 1e-9) on.push({ p, t: s.t });
    }
    on.sort((u, v) => u.t - v.t);
    for (const { p } of on) if (!same(out[out.length - 1], p)) out.push(p);
  }
  return out;
}

/**
 * The union of two outlines that TOUCH — share a stretch of boundary within `tol` (a line drawn
 * between two rooms, an outline drawn up to another's edge). Outlines a wall or a gap keeps apart,
 * or that overlap, are refused: the person is told why, nothing is guessed.
 * → {status: 'ok', ring, holes: [ring…]} | {status: 'apart'} | {status: 'overlap'}
 */
export function unionTouchingRings(ringA, ringB, tol) {
  let A = ccw(cleanRing(ringA));
  let B = ccw(cleanRing(ringB));
  if (A.length < 3 || B.length < 3) return { status: 'apart' };
  // a corner of one well inside the other: they overlap, they do not just touch
  const deepIn = (p, r) => insideRing(p, r) && boundaryDistance(p, r) > tol;
  if (B.some((p) => deepIn(p, A)) || A.some((p) => deepIn(p, B)) || ringsCross(A, B) && !touchesWithin(A, B, tol)) {
    return { status: 'overlap' };
  }
  // 1. B's corners land on A: on A's corner when near one, else on A's nearest edge
  B = B.map((p) => {
    let best = null;
    for (const q of A) {
      const d = Math.hypot(p.x - q.x, p.y - q.y);
      if (d <= tol && (!best || d < best.d)) best = { d, point: q };
    }
    if (best) return best.point;
    let edge = null;
    for (let i = 0; i < A.length; i++) {
      const s = segmentDistance(p, A[i], A[(i + 1) % A.length]);
      if (s.d <= tol && (!edge || s.d < edge.d)) edge = s;
    }
    return edge ? edge.point : p;
  });
  // 2. A's corners that sit near B's corners take them exactly
  A = A.map((p) => B.find((q) => Math.hypot(p.x - q.x, p.y - q.y) <= tol) || p);
  // 3. each ring gains the other's corners lying on its edges — shared stretches now have the same ends
  A = dedupe(withPointsOnEdges(A, B, tol), 1e-9);
  B = dedupe(withPointsOnEdges(B, A, tol), 1e-9);
  // 4. an edge both rings walk (in opposite directions — both are counter-clockwise) is inside the union
  const edges = (r) => r.map((p, i) => [p, r[(i + 1) % r.length]]);
  const eA = edges(A);
  const eB = edges(B);
  const setA = new Set(eA.map(([p, q]) => `${key(p)}>${key(q)}`));
  const setB = new Set(eB.map(([p, q]) => `${key(p)}>${key(q)}`));
  const shared = eA.filter(([p, q]) => setB.has(`${key(q)}>${key(p)}`)).length;
  // walked the SAME way by both: their insides lie on the same side of it — they overlap
  if (eA.some(([p, q]) => setB.has(`${key(p)}>${key(q)}`))) return { status: 'overlap' };
  if (!shared) return { status: 'apart' };
  const rest = [
    ...eA.filter(([p, q]) => !setB.has(`${key(q)}>${key(p)}`)),
    ...eB.filter(([p, q]) => !setA.has(`${key(q)}>${key(p)}`)),
  ];
  // 5. chain what is left into rings: the biggest is the outline, any other is a hole the two enclose
  const from = new Map();
  for (const e of rest) {
    const k = key(e[0]);
    if (!from.has(k)) from.set(k, []);
    from.get(k).push(e);
  }
  const used = new Set();
  const rings = [];
  for (const start of rest) {
    if (used.has(start)) continue;
    const ring = [];
    let e = start;
    let guard = rest.length + 1;
    while (e && !used.has(e) && guard-- > 0) {
      used.add(e);
      ring.push(e[0]);
      e = (from.get(key(e[1])) || []).find((x) => !used.has(x)) || null;
    }
    if (ring.length >= 3) rings.push(cleanRing(ring));
  }
  if (!rings.length) return { status: 'overlap' };
  rings.sort((r, s) => ringArea(s) - ringArea(r));
  const [ring, ...holes] = rings;
  const expected = ringArea(A) + ringArea(B);
  const got = ringArea(ring) - holes.reduce((s, h) => s + ringArea(h), 0);
  if (Math.abs(got - expected) > Math.max(1, expected * 0.02)) return { status: 'overlap' };
  return { status: 'ok', ring, holes: holes.filter((h) => ringArea(h) >= 1) };
}

// An edge crossing between rings that only TOUCH happens at a snapped corner; the area check catches the rest.
function touchesWithin(A, B, tol) {
  return B.every((p) => !insideRing(p, A) || boundaryDistance(p, A) <= tol)
    && A.every((p) => !insideRing(p, B) || boundaryDistance(p, B) <= tol);
}

// ── „Atimti" ──────────────────────────────────────────────────────────────────────────────────────

/** The axis-aligned rectangle dragged from `p` to `q`, as a ring. */
export function rectRing(p, q) {
  return [{ x: p.x, y: p.y }, { x: q.x, y: p.y }, { x: q.x, y: q.y }, { x: p.x, y: q.y }];
}

/**
 * Can `hole` be cut out of `outer` (which already has `holes`)? 'ok' | 'small' (no area) | 'crossing'
 * (the hole's edges cross themselves) | 'outside' (not wholly inside the outline) | 'overlap' (it
 * overlaps a hole already cut).
 */
export function holeFit(hole, outer, holes = [], { minArea = 1 } = {}) {
  const h = cleanRing(hole);
  if (h.length < 3) return 'small';
  for (let i = 0; i < h.length; i++) {
    for (let j = i + 2; j < h.length; j++) {
      if (i === 0 && j === h.length - 1) continue;
      if (segmentsCross(h[i], h[(i + 1) % h.length], h[j], h[(j + 1) % h.length])) return 'crossing';
    }
  }
  if (ringArea(h) < minArea) return 'small';
  if (!h.every((p) => insideRing(p, outer)) || ringsCross(h, outer)) return 'outside';
  for (const o of holes || []) {
    if (h.some((p) => insideRing(p, o)) || o.some((p) => insideRing(p, h)) || ringsCross(h, o)) return 'overlap';
  }
  return 'ok';
}

/** Holes that lie wholly inside `ring` (after a split, each half keeps the holes it holds). */
export function holesInside(ring, holes) {
  return (holes || []).filter((h) => h.every((p) => insideRing(p, ring)) && !ringsCross(h, ring));
}

// ── „Laso" ────────────────────────────────────────────────────────────────────────────────────────

/**
 * The ids of the measurements and count marks on `page` whose points ALL lie inside the freehand
 * `lasso` (PDF points, the frame measurements live in). A mark half inside is not taken — the
 * person sees exactly what the loop went round.
 */
export function lassoSelect(measurements, page, lasso) {
  if (!Array.isArray(lasso) || lasso.length < 3 || ringArea(lasso) < EPS) return [];
  return (measurements || [])
    .filter((m) => m && m.page === page && Array.isArray(m.points) && m.points.length
      && m.points.every((p) => insideRing(p, lasso)))
    .map((m) => m.id);
}

/**
 * editGestures — the pure geometry behind the viewer's editing gestures (Pathon v3 W5-A, design 2026-10-18 §5).
 *
 *  - a measurement edited like an outline (A1): its PDF points ⇄ display-frame page fractions, so the one vertex
 *    editor (OutlineEditLayer) serves both;
 *  - vertex editing (A3): move an edge by both its corners, pick corners with a box, delete several (never below
 *    the shape's minimum), nudge them with the arrow keys;
 *  - „Iškirpti angą" on a length (A2): a doorway's gap cut out of a perimeter / distance where he points;
 *  - box selection (A5): left→right takes whole shapes, right→left touched ones — marks and rooms;
 *    „Pažymėti panašias": the rooms of the same purpose or the same floor covering;
 *  - drawing (A11): a rectangle from two corners, an arc through three points, a segment of a typed length;
 *    copy / paste / duplicate of a measurement;
 *  - a wall face under the click (A12) as the two ends of a length.
 *
 * Coordinates: measurements live in UNROTATED mediabox PDF points ({x, y}); outlines and rooms in DISPLAY-frame
 * page fractions ([x, y]). Nothing here invents a quantity: every number is his geometry at his sheet's scale.
 */
import { displayRotationFor, inverseRotatePctPoint, normalizeRotation, rotatePctPoint } from './viewerEngine/pageRotation.js';
import { realDistanceM } from './measureGeometry.js';
import { buildPageRoomZones } from './roomZones.js';

const clamp01 = (v) => Math.min(1, Math.max(0, v));

// ── A measurement in the vertex editor (A1) ─────────────────────────────────────────────────────────

/** PDF points of an unrotated page → display-frame fractions (the frame the vertex editor works in). */
export function pointsToPct(points, { width, height, rotation = 0 }) {
  if (!(width > 0) || !(height > 0)) return [];
  const rot = displayRotationFor(normalizeRotation(rotation));
  return (points || []).map((p) => rotatePctPoint(p.x / width, p.y / height, rot));
}

/** …and back. */
export function pctToPoints(pct, { width, height, rotation = 0 }) {
  const rot = displayRotationFor(normalizeRotation(rotation));
  return (pct || []).map(([fx, fy]) => {
    const [ux, uy] = inverseRotatePctPoint(fx, fy, rot);
    return { x: ux * width, y: uy * height };
  });
}

/** How many corners a shape keeps at least: an area 3, a length 2. */
export function minPointsOf(kind) {
  return kind === 'area' ? 3 : 2;
}

// ── Vertex editing (A3) ──────────────────────────────────────────────────────────────────────────────

/** The two corner indices of edge `i` (from corner i to the next; an open path has no closing edge). */
export function edgeEnds(n, i, closed = true) {
  if (i < 0 || i >= n || (!closed && i >= n - 1)) return null;
  return [i, (i + 1) % n];
}

/**
 * Edge `i` moved by (dx, dy) in fractions — both of its corners go together. `snap(point) → point | null` is
 * asked for each moved end; the first end that snaps sets the move, so the edge keeps its direction and lands
 * on the wall ("wall snap at both ends"). → {points, snapped: point | null}.
 */
export function moveEdge(points, i, dx, dy, { closed = true, snap = null } = {}) {
  const ends = edgeEnds(points.length, i, closed);
  if (!ends) return { points, snapped: null };
  let mx = dx;
  let my = dy;
  let snapped = null;
  if (snap) {
    for (const k of ends) {
      const want = [points[k][0] + dx, points[k][1] + dy];
      const hit = snap(want);
      if (hit) { mx = hit[0] - points[k][0]; my = hit[1] - points[k][1]; snapped = hit; break; }
    }
  }
  const next = points.map((p, k) => (ends.includes(k) ? [clamp01(p[0] + mx), clamp01(p[1] + my)] : p));
  return { points: next, snapped };
}

/** The corners inside a box (fractions, any two opposite corners). */
export function verticesInBox(points, a, b) {
  const x0 = Math.min(a[0], b[0]); const x1 = Math.max(a[0], b[0]);
  const y0 = Math.min(a[1], b[1]); const y1 = Math.max(a[1], b[1]);
  return (points || []).map((p, i) => (p[0] >= x0 && p[0] <= x1 && p[1] >= y0 && p[1] <= y1 ? i : -1)).filter((i) => i >= 0);
}

/** `indices` removed — refused when fewer than `min` corners would stay. → {points, refused}. */
export function deleteVertices(points, indices, min = 3) {
  const gone = new Set(indices || []);
  if (!gone.size) return { points, refused: false };
  const left = points.filter((_, i) => !gone.has(i));
  if (left.length < min) return { points, refused: true };
  return { points: left, refused: false };
}

/** `indices` moved by (dx, dy) fractions, kept on the sheet. */
export function nudgeVertices(points, indices, dx, dy) {
  const set = new Set(indices || []);
  return points.map((p, i) => (set.has(i) ? [clamp01(p[0] + dx), clamp01(p[1] + dy)] : p));
}

/** The point at fraction `t` along edge `i` — where a click on the edge adds a corner. */
export function insertVertex(points, i, at) {
  const next = points.slice();
  next.splice(i + 1, 0, at);
  return next;
}

/** Fraction of the way along the segment a→b of the point nearest p (0…1). */
export function projectT(p, a, b) {
  const dx = b[0] - a[0]; const dy = b[1] - a[1];
  const len2 = dx * dx + dy * dy;
  if (!len2) return 0;
  return Math.min(1, Math.max(0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / len2));
}

// ── „Iškirpti angą" on a length (A2) ─────────────────────────────────────────────────────────────────

/** Metres along an open path (PDF points) up to corner `i`, or to the point at `t` along edge `i`. */
export function pathPositionM(points, scale, { vertex = null, edge = null, t = 0 } = {}) {
  let s = 0;
  const upto = vertex != null ? vertex : edge;
  for (let k = 0; k < upto; k += 1) s += realDistanceM(points[k], points[k + 1], scale);
  if (edge != null && points[edge + 1]) s += t * realDistanceM(points[edge], points[edge + 1], scale);
  return s;
}

function pointAtM(points, scale, s) {
  let acc = 0;
  for (let k = 0; k < points.length - 1; k += 1) {
    const d = realDistanceM(points[k], points[k + 1], scale);
    if (acc + d >= s || k === points.length - 2) {
      const t = d > 0 ? Math.min(1, Math.max(0, (s - acc) / d)) : 0;
      return { k, p: { x: points[k].x + t * (points[k + 1].x - points[k].x), y: points[k].y + t * (points[k + 1].y - points[k].y) } };
    }
    acc += d;
  }
  return { k: 0, p: points[0] };
}

/**
 * The open path with `gapM` metres cut out, centred at `atM` metres along it (a doorway in a wall's length).
 * → [path, path?] — the pieces that keep a length (≥ 2 points, > 1 cm), or null when the gap does not fit
 * (the path is shorter than the gap, or the scale is not set).
 */
export function cutGap(points, scale, atM, gapM) {
  if (!scale?.calibrated || !(gapM > 0) || !Array.isArray(points) || points.length < 2) return null;
  let total = 0;
  for (let k = 0; k < points.length - 1; k += 1) total += realDistanceM(points[k], points[k + 1], scale);
  if (total <= gapM + 0.01) return null;
  const s0 = Math.max(0, Math.min(total - gapM, atM - gapM / 2));
  const s1 = s0 + gapM;
  const a = pointAtM(points, scale, s0);
  const b = pointAtM(points, scale, s1);
  const before = [...points.slice(0, a.k + 1), a.p];
  const after = [b.p, ...points.slice(b.k + 1)];
  const keep = (path) => {
    if (path.length < 2) return false;
    let len = 0;
    for (let k = 0; k < path.length - 1; k += 1) len += realDistanceM(path[k], path[k + 1], scale);
    return len > 0.01;
  };
  return [before, after].filter(keep);
}

// ── Box selection (A5) ───────────────────────────────────────────────────────────────────────────────

/** 'window' when the box was dragged left→right (whole shapes), 'crossing' right→left (touched ones). */
export function boxMode(from, to) {
  return to.x >= from.x ? 'window' : 'crossing';
}

const inRect = (p, r) => p.x >= r.x0 && p.x <= r.x1 && p.y >= r.y0 && p.y <= r.y1;
const rectOf = (a, b) => ({ x0: Math.min(a.x, b.x), x1: Math.max(a.x, b.x), y0: Math.min(a.y, b.y), y1: Math.max(a.y, b.y) });

function segmentsCross(p, q, r, s) {
  const d = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
  const d1 = d(r, s, p); const d2 = d(r, s, q); const d3 = d(p, q, r); const d4 = d(p, q, s);
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0));
}

function insidePoly(p, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i]; const b = poly[j];
    if ((a.y > p.y) !== (b.y > p.y) && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) inside = !inside;
  }
  return inside;
}

/** Whether a shape (points, closed or not) touches the rectangle at all. */
export function shapeTouchesRect(points, r, closed) {
  if (!points.length) return false;
  if (points.some((p) => inRect(p, r))) return true;
  const corners = [{ x: r.x0, y: r.y0 }, { x: r.x1, y: r.y0 }, { x: r.x1, y: r.y1 }, { x: r.x0, y: r.y1 }];
  const n = points.length;
  const last = closed ? n : n - 1;
  for (let i = 0; i < last; i += 1) {
    const p = points[i]; const q = points[(i + 1) % n];
    for (let k = 0; k < 4; k += 1) if (segmentsCross(p, q, corners[k], corners[(k + 1) % 4])) return true;
  }
  return closed && n >= 3 && corners.some((c) => insidePoly(c, points));
}

/** Ids of the marks on `page` a box takes: `a`, `b` = two corners in PDF points. */
export function marksInBox(measurements, page, a, b, mode = 'window') {
  const r = rectOf(a, b);
  return (measurements || [])
    .filter((m) => m && m.page === page && Array.isArray(m.points) && m.points.length)
    .filter((m) => (mode === 'window'
      ? m.points.every((p) => inRect(p, r))
      : shapeTouchesRect(m.points, r, m.kind === 'area')))
    .map((m) => m.id);
}

/**
 * Room numbers a box takes on `page`: `a`, `b` in display-frame fractions. A room is its outline as the room
 * layer draws it, or its number marker when it has none (lib/roomZones — the same zones a click hits).
 */
export function roomsInBox(rooms, page, a, b, mode = 'window', hidden = null) {
  const W = 1000; const H = 1000;
  const r = rectOf({ x: a[0] * W, y: a[1] * H }, { x: b[0] * W, y: b[1] * H });
  const hiddenSet = new Set(Array.from(hidden || []).map(String));
  const out = [];
  for (const z of buildPageRoomZones(rooms || [], { renderedWidth: W, renderedHeight: H, page })) {
    if (hiddenSet.has(String(z.nr))) continue;
    let hit = false;
    if (z.geometry.type === 'polygon') {
      const pts = z.geometry.points.map((p) => (Array.isArray(p) ? { x: p[0], y: p[1] } : p));
      hit = mode === 'window' ? pts.every((p) => inRect(p, r)) : shapeTouchesRect(pts, r, true);
    } else if (z.geometry.type === 'marker') {
      hit = inRect({ x: z.geometry.cx, y: z.geometry.cy }, r);
    }
    if (hit) out.push(String(z.nr));
  }
  return out;
}

/** „Pažymėti panašias": the rooms whose purpose (`paskirtis`) or floor covering (`grindu_danga`) is the room's. */
export function similarRooms(rooms, nr, by) {
  const field = by === 'grindu_danga' ? 'grindu_danga' : 'paskirtis';
  const me = (rooms || []).find((r) => String(r?.nr) === String(nr));
  const value = me?.[field];
  if (value == null || value === '') return [];
  return (rooms || [])
    .filter((r) => r && String(r.nr) !== String(nr) && r[field] === value && !r._sujungta_i)
    .map((r) => String(r.nr));
}

// ── Drawing (A11) ────────────────────────────────────────────────────────────────────────────────────

/** A rectangle from two opposite corners (PDF points): four corners, clockwise from the first click. */
export function rectanglePoints(a, b) {
  return [{ x: a.x, y: a.y }, { x: b.x, y: a.y }, { x: b.x, y: b.y }, { x: a.x, y: b.y }];
}

/**
 * The arc through three points (start, a point on it, end) as a polyline of `steps` segments; a straight
 * line when the three points are in a row (no circle passes through them).
 */
export function arcPoints(a, m, b, steps = 16) {
  const d = 2 * (a.x * (m.y - b.y) + m.x * (b.y - a.y) + b.x * (a.y - m.y));
  if (Math.abs(d) < 1e-9) return [a, b];
  const ux = ((a.x ** 2 + a.y ** 2) * (m.y - b.y) + (m.x ** 2 + m.y ** 2) * (b.y - a.y) + (b.x ** 2 + b.y ** 2) * (a.y - m.y)) / d;
  const uy = ((a.x ** 2 + a.y ** 2) * (b.x - m.x) + (m.x ** 2 + m.y ** 2) * (a.x - b.x) + (b.x ** 2 + b.y ** 2) * (m.x - a.x)) / d;
  const rad = Math.hypot(a.x - ux, a.y - uy);
  const ang = (p) => Math.atan2(p.y - uy, p.x - ux);
  const a0 = ang(a); const am = ang(m); const a1 = ang(b);
  const norm = (x) => ((x % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
  // go the way round that passes through m
  let sweep = norm(a1 - a0);
  if (norm(am - a0) > sweep) sweep -= 2 * Math.PI;
  const out = [];
  for (let i = 0; i <= steps; i += 1) {
    const t = a0 + (sweep * i) / steps;
    out.push({ x: ux + rad * Math.cos(t), y: uy + rad * Math.sin(t) });
  }
  out[0] = { x: a.x, y: a.y };
  out[steps] = { x: b.x, y: b.y };
  return out;
}

/** The end of a segment from `from` toward `toward` that is exactly `lengthM` metres long at the sheet's scale. */
export function pointAtLength(from, toward, lengthM, scale) {
  if (!scale?.calibrated || !(lengthM > 0)) return null;
  const dx = toward.x - from.x; const dy = toward.y - from.y;
  const unitM = Math.hypot(dx * scale.metersPerPointX, dy * scale.metersPerPointY);
  if (!(unitM > 0)) return null;
  const k = lengthM / unitM;
  return { x: from.x + dx * k, y: from.y + dy * k };
}

/** Digits typed while drawing → metres („3,25" / „3.25"), or null while it is not a number yet. */
export function typedLength(text) {
  const t = String(text || '').trim().replace(',', '.');
  if (!/^\d+(\.\d*)?$/.test(t)) return null;
  const v = Number(t);
  return v > 0 ? v : null;
}

/** A copy of a measurement for another sheet or beside itself: fresh id, moved by (dx, dy) PDF points. */
export function copyMeasurement(m, { page = m.page, dx = 0, dy = 0, id }) {
  const move = (pts) => (pts || []).map((p) => ({ x: p.x + dx, y: p.y + dy }));
  const { id: _old, eilute_id: _e, kaip: _k, ...rest } = m;
  return {
    ...rest,
    id,
    page,
    points: move(m.points),
    ...(Array.isArray(m.holes) ? { holes: m.holes.map(move) } : {}),
    source: 'user',
    created_at: new Date().toISOString(),
  };
}

// ── A wall face as a length (A12) ────────────────────────────────────────────────────────────────────

/**
 * The wall face nearest `p` within `tol` (rings of {x, y}, the drawing's wall solid): its two ends.
 * → {a, b} or null.
 */
export function wallFaceAt(rings, p, tol) {
  let best = null;
  for (const ring of rings || []) {
    const pts = ring.points || ring;
    const n = pts.length;
    for (let i = 0; i < n; i += 1) {
      const a = pts[i]; const b = pts[(i + 1) % n];
      const dx = b.x - a.x; const dy = b.y - a.y;
      const len2 = dx * dx + dy * dy;
      if (!len2) continue;
      const t = Math.min(1, Math.max(0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2));
      const d = Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
      if (d <= tol && (!best || d < best.d)) best = { d, a: { x: a.x, y: a.y }, b: { x: b.x, y: b.y } };
    }
  }
  return best ? { a: best.a, b: best.b } : null;
}

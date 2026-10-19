/**
 * drawingSnap — the drawing's own wall geometry as snap targets for the measure overlay.
 *
 * The backend (api/page_geometry.py) answers with the merged wall solid as rings in DISPLAY-frame page
 * fractions — the frame `polygon_pct` lives in. MeasureLayer works in UNROTATED mediabox PDF points
 * (embedPdfAdapter's contract), so each ring is turned back through the page's /Rotate and scaled by
 * the page size. Pure: no React, no fetch.
 */
import { displayRotationFor, inverseRotatePctPoint, normalizeRotation } from './viewerEngine/pageRotation.js';
import { nearestEdge, nearestVertex } from './polygonGeometry.js';

/** `[{id, open: false, points: [{x, y}]}]` in PDF points — the shape polygonGeometry's snap helpers take. */
export function snapPolygonsFromGeometry(geometry, { pageWidthPt, pageHeightPt, pageRotation = 0 }) {
  const rings = Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : [];
  if (!(pageWidthPt > 0) || !(pageHeightPt > 0) || !rings.length) return [];
  const rot = displayRotationFor(normalizeRotation(pageRotation));
  const out = [];
  rings.forEach((ring, i) => {
    if (!Array.isArray(ring) || ring.length < 3) return;
    const points = ring.map(([fx, fy]) => {
      const [ux, uy] = inverseRotatePctPoint(Number(fx), Number(fy), rot);
      return { x: ux * pageWidthPt, y: uy * pageHeightPt };
    });
    out.push({ id: `wall-${i}`, open: false, points });
  });
  return out;
}

/** What the status line says while a snap is under the pointer (Pathon v3 W5-A A6 [#56]: the snap kind is named). */
export const SNAP_KIND_TEXT = {
  'drawing-vertex': 'sienos kampas',
  'measure-vertex': 'matavimo taškas',
  intersection: 'linijų susikirtimas',
  'drawing-midpoint': 'sienos vidurys',
  'measure-midpoint': 'matavimo atkarpos vidurys',
  'drawing-edge': 'siena',
  'measure-edge': 'matavimo linija',
  align: 'lygiuota su tašku',
};

function* segments(polys, near, reach) {
  for (const poly of polys) {
    const pts = poly.points || [];
    const n = pts.length;
    const last = poly.open ? n - 1 : n;
    for (let i = 0; i < last; i += 1) {
      const a = pts[i]; const b = pts[(i + 1) % n];
      // only segments whose box comes within reach of the pointer: a sheet's wall solid has thousands
      if (near && (Math.max(a.x, b.x) < near.x - reach || Math.min(a.x, b.x) > near.x + reach
        || Math.max(a.y, b.y) < near.y - reach || Math.min(a.y, b.y) > near.y + reach)) continue;
      yield [a, b];
    }
  }
}

/** The nearest middle of a segment within `tol`. → {point} | null */
export function nearestMidpoint(raw, polys, tol) {
  let best = null;
  for (const [a, b] of segments(polys, raw, tol * 40)) {
    const m = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    const d = Math.hypot(m.x - raw.x, m.y - raw.y);
    if (d <= tol && (!best || d < best.d)) best = { d, point: m };
  }
  return best ? { point: best.point } : null;
}

function crossing(p, q, r, s) {
  const d = (q.x - p.x) * (s.y - r.y) - (q.y - p.y) * (s.x - r.x);
  if (Math.abs(d) < 1e-9) return null;
  const t = ((r.x - p.x) * (s.y - r.y) - (r.y - p.y) * (s.x - r.x)) / d;
  const u = ((r.x - p.x) * (q.y - p.y) - (r.y - p.y) * (q.x - p.x)) / d;
  if (t < 0 || t > 1 || u < 0 || u > 1) return null;
  return { x: p.x + t * (q.x - p.x), y: p.y + t * (q.y - p.y) };
}

/** The nearest point where a segment of `a` crosses one of `b` (or of `a` itself, other shapes), within `tol`. */
export function nearestIntersection(raw, a, b, tol) {
  const reach = tol * 2;
  const segA = [...segments(a, raw, reach)];
  const segB = [...segments(b, raw, reach)];
  let best = null;
  const consider = (x) => {
    if (!x) return;
    const d = Math.hypot(x.x - raw.x, x.y - raw.y);
    if (d <= tol && (!best || d < best.d)) best = { d, point: x };
  };
  for (const [p, q] of segA) for (const [r, s] of segB) consider(crossing(p, q, r, s));
  for (let i = 0; i < segA.length; i += 1) {
    for (let j = i + 1; j < segA.length; j += 1) {
      const [p, q] = segA[i]; const [r, s] = segA[j];
      if (p === r || p === s || q === r || q === s) continue;      // neighbours share a corner — that is a vertex
      consider(crossing(p, q, r, s));
    }
  }
  return best ? { point: best.point } : null;
}

/**
 * An alignment guide (A6): `raw` lines up with a vertex on x or y within `tol` → that coordinate is taken, and the
 * guide runs from the vertex to the point. → {point, guides: [{from, axis: 'x' | 'y'}]} | null.
 */
export function alignGuide(raw, vertices, tol) {
  let bx = null; let by = null;
  for (const v of vertices || []) {
    const dx = Math.abs(v.x - raw.x); const dy = Math.abs(v.y - raw.y);
    if (dx <= tol && dy > tol && (!bx || dx < bx.d)) bx = { d: dx, v };
    if (dy <= tol && dx > tol && (!by || dy < by.d)) by = { d: dy, v };
  }
  if (!bx && !by) return null;
  const point = { x: bx ? bx.v.x : raw.x, y: by ? by.v.y : raw.y };
  const guides = [];
  if (bx) guides.push({ from: bx.v, axis: 'x' });
  if (by) guides.push({ from: by.v, axis: 'y' });
  return { point, guides };
}

/**
 * The point a click lands on, in this order: a wall corner, a measurement vertex, where two lines cross, the middle
 * of a wall or of a measured segment, a wall face, a measurement edge — all within `tol` PDF points. `null` when
 * nothing is near. Returns `{point, kind}` (kind: a key of SNAP_KIND_TEXT). With Ctrl held the viewer passes a much
 * larger `tol`: the pointer jumps to the nearest target (A6 [#106]).
 */
export function pickSnap(raw, { drawing = [], measurements = [] }, tol) {
  const dv = drawing.length ? nearestVertex(raw, drawing, tol) : null;
  if (dv) return { point: dv.point, kind: 'drawing-vertex' };
  const mv = measurements.length ? nearestVertex(raw, measurements, tol) : null;
  if (mv) return { point: mv.point, kind: 'measure-vertex' };
  const ix = measurements.length ? nearestIntersection(raw, measurements, drawing, tol) : null;
  if (ix) return { point: ix.point, kind: 'intersection' };
  const dm = drawing.length ? nearestMidpoint(raw, drawing, tol) : null;
  if (dm) return { point: dm.point, kind: 'drawing-midpoint' };
  const mm = measurements.length ? nearestMidpoint(raw, measurements, tol) : null;
  if (mm) return { point: mm.point, kind: 'measure-midpoint' };
  const de = drawing.length ? nearestEdge(raw, drawing, tol) : null;
  if (de) return { point: de.point, kind: 'drawing-edge' };
  const me = measurements.length ? nearestEdge(raw, measurements, tol) : null;
  if (me) return { point: me.point, kind: 'measure-edge' };
  return null;
}

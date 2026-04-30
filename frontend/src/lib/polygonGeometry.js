/**
 * polygonGeometry — pure geometry helpers for the Phase C-1 polygon editor.
 *
 * Coordinate convention: all functions take {x, y} objects in canvas pixel
 * space (matching takeoffStore polygon points). Pixels-per-meter is applied
 * upstream by takeoffStore.polygonAreaM2.
 */

/**
 * Returns true if any non-adjacent edges of `points` cross each other.
 * Adjacent edges (sharing a vertex) are NOT considered intersecting.
 *
 * @param points {x,y}[] — closed polygon, first ≠ last
 * @returns boolean
 */
export function selfIntersects(points) {
  if (!points || points.length < 4) return false;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const a1 = points[i];
    const a2 = points[(i + 1) % n];
    for (let j = i + 1; j < n; j++) {
      // Skip the edge starting at j if it's adjacent to edge i
      // (shares a vertex). Adjacent = consecutive in either direction
      // including wraparound (last→first vs first→second).
      if (j === i || j === (i + 1) % n || (i === 0 && j === n - 1)) continue;
      const b1 = points[j];
      const b2 = points[(j + 1) % n];
      if (segmentsCross(a1, a2, b1, b2)) return true;
    }
  }
  return false;
}

function segmentsCross(p1, p2, p3, p4) {
  const d1 = direction(p3, p4, p1);
  const d2 = direction(p3, p4, p2);
  const d3 = direction(p1, p2, p3);
  const d4 = direction(p1, p2, p4);
  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) &&
      ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) {
    return true;
  }
  return false;
}

function direction(a, b, c) {
  return (c.x - a.x) * (b.y - a.y) - (b.x - a.x) * (c.y - a.y);
}

const ORTHO_TOLERANCE_DEG = 15;

/**
 * Snap cursor to the nearest of [0°, 90°, 180°, 270°] (or 45° increments
 * when shiftHeld) measured from the previous vertex direction. Returns
 * a new {x, y}; pass-through when ortho disabled, alt held, or cursor
 * is outside tolerance from any snap angle.
 *
 * @param prev {x,y} — last placed vertex (origin of the rubber band)
 * @param cursor {x,y} — current pointer position
 * @param opts {orthoEnabled, shiftHeld, altHeld}
 * @returns {x,y}
 */
export function orthoSnap(prev, cursor, opts) {
  if (!opts.orthoEnabled || opts.altHeld) return cursor;

  const dx = cursor.x - prev.x;
  const dy = cursor.y - prev.y;
  if (dx === 0 && dy === 0) return cursor;

  const angleDeg = Math.atan2(dy, dx) * 180 / Math.PI;
  const snapAngles = opts.shiftHeld
    ? [-180, -135, -90, -45, 0, 45, 90, 135, 180]
    : [-180, -90, 0, 90, 180];

  let nearest = null;
  let nearestDelta = ORTHO_TOLERANCE_DEG;
  for (const a of snapAngles) {
    const d = Math.abs(angleDeg - a);
    if (d < nearestDelta) {
      nearestDelta = d;
      nearest = a;
    }
  }
  if (nearest === null) return cursor;

  const dist = Math.hypot(dx, dy);
  const rad = nearest * Math.PI / 180;
  return {
    x: Math.round(prev.x + dist * Math.cos(rad)),
    y: Math.round(prev.y + dist * Math.sin(rad)),
  };
}

/**
 * Ray-casting point-in-polygon. Returns true for points strictly inside
 * AND on edges (so click-to-select-by-body works for clicks on the border).
 */
export function pointInPolygon(p, poly) {
  if (!poly || poly.length < 3) return false;
  // Edge-on test first (cheap)
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    if (pointOnSegment(p, poly[j], poly[i])) return true;
  }
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y;
    const xj = poly[j].x, yj = poly[j].y;
    const intersect = ((yi > p.y) !== (yj > p.y))
      && (p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function pointOnSegment(p, a, b, eps = 1) {
  const cross = (p.y - a.y) * (b.x - a.x) - (p.x - a.x) * (b.y - a.y);
  if (Math.abs(cross) > eps) return false;
  const minX = Math.min(a.x, b.x) - eps;
  const maxX = Math.max(a.x, b.x) + eps;
  const minY = Math.min(a.y, b.y) - eps;
  const maxY = Math.max(a.y, b.y) + eps;
  return p.x >= minX && p.x <= maxX && p.y >= minY && p.y <= maxY;
}

/**
 * Find the nearest vertex among polygons within tolerance.
 *
 * @param point {x,y}
 * @param polygons {id, points}[]
 * @param tolerance px
 * @param opts {excludePolygonId?: string} — skip vertices belonging to this polygon
 * @returns {point: {x,y}, polygonId, vertexIndex} | null
 */
export function nearestVertex(point, polygons, tolerance, opts = {}) {
  let best = null;
  let bestDist = tolerance;
  for (const poly of polygons) {
    if (opts.excludePolygonId && poly.id === opts.excludePolygonId) continue;
    for (let i = 0; i < poly.points.length; i++) {
      const v = poly.points[i];
      const d = Math.hypot(v.x - point.x, v.y - point.y);
      if (d < bestDist) {
        bestDist = d;
        best = { point: { x: v.x, y: v.y }, polygonId: poly.id, vertexIndex: i };
      }
    }
  }
  return best;
}

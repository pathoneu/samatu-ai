// frontend/src/lib/gestures/g5-lasso-geometry.js
/**
 * Sprint 2 G5 helpers — clean up the freehand lasso path before sending
 * to backend. Simplifies near-duplicate points (cheap RDP-lite),
 * closes the polygon, and validates minimum vertex count.
 *
 * Coordinates are in pdf-pct (0..1).
 */

function dist([x1, y1], [x2, y2]) {
  const dx = x1 - x2, dy = y1 - y2;
  return Math.sqrt(dx * dx + dy * dy);
}

export function simplifyLasso(points, tolerance = 0.005) {
  if (points.length <= 2) return points.slice();
  const out = [points[0]];
  for (let i = 1; i < points.length; i++) {
    if (dist(points[i], out[out.length - 1]) >= tolerance) {
      out.push(points[i]);
    }
  }
  return out;
}

export function closeIfNeeded(points) {
  if (points.length === 0) return points.slice();
  const first = points[0];
  const last = points[points.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return points.slice();
  return [...points, first];
}

export function isMinimalLasso(points) {
  return points.length >= 3;
}

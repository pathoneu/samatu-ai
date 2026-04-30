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

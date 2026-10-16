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

/**
 * The point a click lands on, in this order: a wall corner, a measurement vertex, a wall face, a
 * measurement edge — all within `tol` PDF points. `null` when nothing is near.
 * Returns `{point, kind}`; `kind` ∈ drawing-vertex | measure-vertex | drawing-edge | measure-edge.
 */
export function pickSnap(raw, { drawing = [], measurements = [] }, tol) {
  const dv = drawing.length ? nearestVertex(raw, drawing, tol) : null;
  if (dv) return { point: dv.point, kind: 'drawing-vertex' };
  const mv = measurements.length ? nearestVertex(raw, measurements, tol) : null;
  if (mv) return { point: mv.point, kind: 'measure-vertex' };
  const de = drawing.length ? nearestEdge(raw, drawing, tol) : null;
  if (de) return { point: de.point, kind: 'drawing-edge' };
  const me = measurements.length ? nearestEdge(raw, measurements, tol) : null;
  if (me) return { point: me.point, kind: 'measure-edge' };
  return null;
}

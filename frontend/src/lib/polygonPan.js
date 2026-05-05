// frontend/src/lib/polygonPan.js
/**
 * Sprint 3-D: KŽ-panel-driven canvas navigation.
 *
 * When user clicks a KŽ row, we compute scale + translate so the room's
 * polygon centers in the canvas viewport with some padding. Drives
 * viewerStore.setTransform.
 *
 * Math is approximate (uses caller-supplied viewport dims rather than
 * actual canvas-ref measurement); good enough for navigation, refinement
 * Sprint 4.
 */

export function polygonBoundingBox(poly) {
  if (!poly || !Array.isArray(poly) || poly.length === 0) return null;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const v of poly) {
    const x = v[0], y = v[1];
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  if (!Number.isFinite(minX)) return null;
  return { minX, minY, maxX, maxY };
}

export function fitToBox(bbox, viewportW, viewportH, paddingPct = 0.25) {
  if (!bbox) return null;
  const bboxW = bbox.maxX - bbox.minX;
  const bboxH = bbox.maxY - bbox.minY;
  if (bboxW <= 0 || bboxH <= 0) return null;
  // Add padding on each side
  const targetWPct = bboxW * (1 + paddingPct * 2);
  const targetHPct = bboxH * (1 + paddingPct * 2);
  // Pick the scale that makes the targetSize fit the viewport in both dims
  const scaleX = 1 / targetWPct;
  const scaleY = 1 / targetHPct;
  const scale = Math.min(scaleX, scaleY);
  // Centroid of bbox
  const cx = (bbox.minX + bbox.maxX) / 2;
  const cy = (bbox.minY + bbox.maxY) / 2;
  // Translate so centroid lands at viewport center.
  // Canvas system: canvas-px = pdf_pct * canvasNaturalSize * scale + translate
  // viewport center in screen px = viewportW/2, viewportH/2
  // We want: cx * viewportW * scale + translate.x = viewportW/2
  const tx = viewportW / 2 - cx * viewportW * scale;
  const ty = viewportH / 2 - cy * viewportH * scale;
  return { scale, translate: { x: tx, y: ty } };
}

export function computePanToPolygon(poly, viewportW, viewportH, paddingPct = 0.25) {
  const bbox = polygonBoundingBox(poly);
  if (!bbox) return null;
  return fitToBox(bbox, viewportW, viewportH, paddingPct);
}

// frontend/src/lib/coordTransform.js
/**
 * Sprint 2: pixel ↔ pdf-pct ↔ canvas conversions for gesture handlers.
 *
 * "pdf-pct" is page-fraction space (0..1 across page width/height) — the
 * same space backend uses for polygon_pct, click_xy_pct, lasso_polygon_pct.
 *
 * Frontend lives in CSS pixel space inside the TakeoffCanvas container.
 * The canvas is shown via CSS transform: translate + scale (Sprint 1
 * mip-pyramid). To go from a pointer event to backend percent we have to
 * undo translate then divide by (scale × canvasNaturalSize).
 */

export function canvasPxToPdfPct({ px, py }, { scale, translate, canvasWidth, canvasHeight }) {
  const localX = (px - translate.x) / scale;
  const localY = (py - translate.y) / scale;
  return { x: localX / canvasWidth, y: localY / canvasHeight };
}

export function pdfPctToCanvasPx({ x, y }, { scale, translate, canvasWidth, canvasHeight }) {
  const localX = x * canvasWidth;
  const localY = y * canvasHeight;
  return {
    px: localX * scale + translate.x,
    py: localY * scale + translate.y,
  };
}

export function pdfPctPolyToCanvasPxPoly(polyPct, transform) {
  return polyPct.map(([x, y]) => {
    const { px, py } = pdfPctToCanvasPx({ x, y }, transform);
    return [px, py];
  });
}

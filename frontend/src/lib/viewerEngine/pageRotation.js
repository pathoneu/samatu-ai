/**
 * pageRotation — mediabox-space ⇄ display-space transforms for /Rotate pages.
 *
 * COORDINATE SPACES (verified 2026-07-11 on the Objektas A /Rotate-270 sheets):
 * - Room polygon_pct / bbox_pct from the extractor are DISPLAY-space: pdf2image
 *   (poppler) APPLIES /Rotate when rastering, so the extraction raster is the
 *   rotation-applied readable sheet. (An earlier note here claimed pdf2image
 *   ignores /Rotate — that was wrong, and it mis-motivated two bad viewer
 *   fixes. Ground truth: the legacy react-pdf viewer plots the pct RAW over a
 *   rotation-applied render and they align.) Zones therefore need NO transform.
 * - Measurements and EmbedPDF interaction-manager click points are UNROTATED
 *   mediabox PDF points. These helpers map that space onto the rotation-applied
 *   display (and back). Rotation 0 pages pass through untouched (safe).
 *
 * Convention: rotate the IMAGE clockwise by /Rotate degrees (PDF /Rotate is CW).
 *   90:  (x,y) -> (1-y, x)
 *   180: (x,y) -> (1-x, 1-y)
 *   270: (x,y) -> (y, 1-x)
 */
export function normalizeRotation(r) {
  const n = Number(r) || 0;
  if (n === 1 || n === 90) return 90;
  if (n === 2 || n === 180) return 180;
  if (n === 3 || n === 270) return 270;
  return 0;
}

export function rotatePctPoint(x, y, rot) {
  switch (normalizeRotation(rot)) {
    case 90: return [1 - y, x];
    case 180: return [1 - x, 1 - y];
    case 270: return [y, 1 - x];
    default: return [x, y];
  }
}

// Exact inverse of rotatePctPoint: undo a CW rotation by rotating CW the rest
// of the way around (inverse of 90 is 270 and vice versa; 180 is self-inverse).
// Use for DISPLAY-space clicks that must map back to the UNROTATED (mediabox)
// raster — e.g. click-to-fill seeds, whose backend ignores /Rotate.
export function inverseRotatePctPoint(x, y, rot) {
  return rotatePctPoint(x, y, (360 - normalizeRotation(rot)) % 360);
}

// The rotation the page is displayed at. PageOverlayHost's content wrapper
// CSS-rotates ALL EmbedPDF page content (base render + tiles + search
// highlights) by the page's TRUE /Rotate, so display rotation == reported
// /Rotate — the identity. (Previously this returned the COMPLEMENT, a
// workaround from the era when the base raster was drawn unrotated.) Shared by
// PageOverlayHost (content wrapper angle), makeEmbedAdapter (measurement
// mediabox⇄display mapping) and TakeoffViewer's handlePagePoint (click-to-fill
// seed mediabox→display) so those sites can never diverge.
export function displayRotationFor(reported) {
  return normalizeRotation(reported);
}

export function rotateBboxPct(bbox, rot) {
  const r = normalizeRotation(rot);
  if (!bbox || r === 0) return bbox;
  const corners = [
    [bbox.x, bbox.y],
    [bbox.x + bbox.w, bbox.y],
    [bbox.x, bbox.y + bbox.h],
    [bbox.x + bbox.w, bbox.y + bbox.h],
  ].map(([x, y]) => rotatePctPoint(x, y, r));
  const xs = corners.map((p) => p[0]);
  const ys = corners.map((p) => p[1]);
  const nx = Math.min(...xs), ny = Math.min(...ys);
  return { x: nx, y: ny, w: Math.max(...xs) - nx, h: Math.max(...ys) - ny };
}

// Return a shallow-cloned room whose polygon_pct / bbox_pct are rotated by rot.
// NOTE: currently UNUSED by the viewer — room pct are already display-space
// (see header), so PageOverlayHost plots them raw. Kept (with tests) for any
// future geometry that genuinely lives in mediabox space.
export function rotateRoomGeometry(room, rot) {
  const r = normalizeRotation(rot);
  if (r === 0 || !room) return room;
  const out = { ...room };
  if (Array.isArray(room.polygon_pct) && room.polygon_pct.length >= 3) {
    out.polygon_pct = room.polygon_pct.map((p) => {
      const x = Array.isArray(p) ? p[0] : p?.x_pct;
      const y = Array.isArray(p) ? p[1] : p?.y_pct;
      return rotatePctPoint(x, y, r);
    });
  }
  if (room.bbox_pct) out.bbox_pct = rotateBboxPct(room.bbox_pct, r);
  return out;
}

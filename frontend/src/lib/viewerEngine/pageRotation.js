/**
 * pageRotation — corrects a known data-pipeline bug: room polygon_pct / bbox_pct
 * are computed by the extractor on the UNROTATED (mediabox) page raster (pdf2image
 * ignores /Rotate), but the viewer DISPLAYS the page with /Rotate applied. So on a
 * rotated page the pct land in the wrong place. These helpers rotate a top-left-
 * origin fractional point/bbox by the page's /Rotate so extraction-space pct map
 * onto the rotated display. Rotation 0 pages pass through untouched (safe).
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

// Return a shallow-cloned room whose polygon_pct / bbox_pct are rotated for display.
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

/**
 * sheetZoom — the arithmetic behind the enlarged evidence viewer.
 *
 * The viewer shows the WHOLE sheet fitted to the dialog and lets the person
 * zoom in themselves. The evidence endpoint caps any returned crop at 1600 px
 * on the long edge (backend/api/evidence.py MAX_CROP_PX), so a zoomed whole
 * sheet is blurry by construction; the viewer therefore asks the endpoint for
 * the region that is on screen once the zoom settles and lays it over the
 * base image. To place that overlay exactly, `paddedRect` replicates the
 * endpoint's padding rule — backend/tests/test_evidence_padding_contract.py
 * pins the server side to the same fixtures as sheetZoom.test.js.
 */

export const ZOOM_MIN = 1;
export const ZOOM_MAX = 8;
export const ZOOM_STEP = 1.6;
/** Sharpest dpi the endpoint accepts (its own page-size ceiling may lower it). */
export const SHARP_DPI = 160;

// Mirror of backend/api/evidence.py — change both or the overlay drifts.
export const PAD_PCT = 0.012;
export const MIN_CROP_W_PCT = 0.10;
export const MIN_CROP_H_PCT = 0.045;

export function clampZoom(z) {
  const n = Number(z);
  if (!Number.isFinite(n)) return ZOOM_MIN;
  return Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, n));
}

export function rectKey(rect) {
  return rect.map((v) => Number(v).toFixed(4)).join(',');
}

/** The same evidence URL asked for another rectangle (and dpi) of the page. */
export function withRect(cropUrl, rect, dpi = SHARP_DPI) {
  if (!cropUrl) return null;
  const r = rectKey(rect);
  let u = /([?&])rect=[^&]*/.test(cropUrl)
    ? cropUrl.replace(/([?&])rect=[^&]*/, `$1rect=${r}`)
    : `${cropUrl}${cropUrl.includes('?') ? '&' : '?'}rect=${r}`;
  u = /([?&])dpi=\d+/.test(u)
    ? u.replace(/([?&])dpi=\d+/, `$1dpi=${dpi}`)
    : `${u}${u.includes('?') ? '&' : '?'}dpi=${dpi}`;
  return u;
}

export function fullSheetUrl(cropUrl, dpi = SHARP_DPI) {
  return withRect(cropUrl, [0, 0, 1, 1], dpi);
}

/** Exactly what the endpoint returns for a requested rect (see `_padded`). */
export function paddedRect(rect) {
  let [x0, y0, x1, y1] = rect.map(Number);
  x0 -= PAD_PCT; y0 -= PAD_PCT; x1 += PAD_PCT; y1 += PAD_PCT;
  if (x1 - x0 < MIN_CROP_W_PCT) {
    const cx = (x0 + x1) / 2;
    x0 = cx - MIN_CROP_W_PCT / 2; x1 = cx + MIN_CROP_W_PCT / 2;
  }
  if (y1 - y0 < MIN_CROP_H_PCT) {
    const cy = (y0 + y1) / 2;
    y0 = cy - MIN_CROP_H_PCT / 2; y1 = cy + MIN_CROP_H_PCT / 2;
  }
  if (x0 < 0) { x1 = Math.min(1, x1 - x0); x0 = 0; }
  if (x1 > 1) { x0 = Math.max(0, x0 - (x1 - 1)); x1 = 1; }
  if (y0 < 0) { y1 = Math.min(1, y1 - y0); y0 = 0; }
  if (y1 > 1) { y0 = Math.max(0, y0 - (y1 - 1)); y1 = 1; }
  return [Math.max(0, x0), Math.max(0, y0), Math.min(1, x1), Math.min(1, y1)];
}

/**
 * The part of the image (page fractions) that is inside the scroll box.
 * `box` and `img` are DOMRect-like {left, top, right, bottom, width, height}.
 * Returns null when the image is entirely visible — nothing to sharpen.
 */
export function visibleRect(box, img) {
  if (!box || !img || !(img.width > 0) || !(img.height > 0)) return null;
  const x0 = Math.max(0, (box.left - img.left) / img.width);
  const y0 = Math.max(0, (box.top - img.top) / img.height);
  const x1 = Math.min(1, (box.right - img.left) / img.width);
  const y1 = Math.min(1, (box.bottom - img.top) / img.height);
  if (x1 <= x0 || y1 <= y0) return null;
  if (x0 === 0 && y0 === 0 && x1 === 1 && y1 === 1) return null;
  return [x0, y0, x1, y1];
}

/**
 * Zoom (relative to the fitted size) at which `rect` fills about `fill` of
 * the box on its tighter axis, so the outlined spot is framed, not clipped.
 */
export function zoomForRect(rect, box, fitted, fill = 0.9) {
  if (!rect || rect.length !== 4 || !fitted?.width || !fitted?.height || !box?.width || !box?.height) return ZOOM_MIN;
  const w = Math.max(1e-4, rect[2] - rect[0]) * fitted.width;
  const h = Math.max(1e-4, rect[3] - rect[1]) * fitted.height;
  return clampZoom(Math.min((box.width * fill) / w, (box.height * fill) / h));
}

/** Centre of a rect, as image fractions — where the viewer scrolls to. */
export function rectCentre(rect) {
  return { x: (rect[0] + rect[2]) / 2, y: (rect[1] + rect[3]) / 2 };
}

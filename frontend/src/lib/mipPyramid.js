/**
 * Sprint 1: 3-level mip-pyramid for PDF page rendering.
 *
 * Render each page at a small set of fixed zoom levels rather than
 * tile-by-tile. For viewport scale S, pick the closest level >= S so
 * blits look crisp on settle. CSS transform handles in-between scales
 * during interactive pan/zoom.
 */

export const MIP_LEVELS = [0.5, 1.5, 3.0];

/**
 * Given the user's current viewport scale (e.g. 1.0 = 100% zoom),
 * return the mip-level we should render against.
 */
export function pickZoomLevel(scale) {
  for (const level of MIP_LEVELS) {
    if (scale <= level) return level;
  }
  return MIP_LEVELS[MIP_LEVELS.length - 1];
}

export function tileKey(pageIdx, zoomLevel) {
  return `${pageIdx}:${zoomLevel}`;
}

/**
 * Render a pdf.js page at the given mip-zoom level into an ImageBitmap.
 *
 * Uses OffscreenCanvas so the heavy bitmap work happens on a background
 * canvas; we transferToImageBitmap() at the end for fast blits.
 *
 * Caller is responsible for caching the returned bitmap and calling
 * .close() when evicting.
 */
export async function renderPageToImageBitmap(page, zoomLevel) {
  const dpr = Math.min(globalThis.devicePixelRatio || 1, 2);
  const viewport = page.getViewport({ scale: zoomLevel * dpr });
  const offscreen = new OffscreenCanvas(viewport.width, viewport.height);
  const ctx = offscreen.getContext('2d');
  await page.render({ canvasContext: ctx, viewport }).promise;
  return offscreen.transferToImageBitmap();
}

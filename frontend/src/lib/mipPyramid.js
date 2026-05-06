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

export function getRenderPixelRatio() {
  return Math.min(globalThis.devicePixelRatio || 1, 2);
}

export function createRenderTile(bitmap, cssWidth, cssHeight) {
  return {
    bitmap,
    cssWidth,
    cssHeight,
    close() {
      if (bitmap && typeof bitmap.close === 'function') {
        bitmap.close();
      }
    },
  };
}

/**
 * Render a pdf.js page at the given mip-zoom level into an ImageBitmap.
 *
 * Uses OffscreenCanvas so the heavy bitmap work happens on a background
 * canvas when supported; falls back to a regular canvas for browsers without
 * OffscreenCanvas. Returned cssWidth/cssHeight keep HiDPI canvases from
 * rendering at 2x visual size on Retina screens.
 *
 * Caller is responsible for caching the returned tile and calling .close()
 * when evicting.
 */
export async function renderPageToImageBitmap(page, zoomLevel) {
  const dpr = getRenderPixelRatio();
  const renderViewport = page.getViewport({ scale: zoomLevel * dpr });
  const cssViewport = page.getViewport({ scale: zoomLevel });

  if (typeof OffscreenCanvas !== 'undefined') {
    const offscreen = new OffscreenCanvas(renderViewport.width, renderViewport.height);
    const ctx = offscreen.getContext('2d');
    await page.render({ canvasContext: ctx, viewport: renderViewport }).promise;
    return createRenderTile(
      offscreen.transferToImageBitmap(),
      cssViewport.width,
      cssViewport.height
    );
  }

  if (typeof document === 'undefined') {
    throw new Error('Canvas rendering is not available in this environment');
  }

  const canvas = document.createElement('canvas');
  canvas.width = renderViewport.width;
  canvas.height = renderViewport.height;
  const ctx = canvas.getContext('2d');
  await page.render({ canvasContext: ctx, viewport: renderViewport }).promise;
  return createRenderTile(canvas, cssViewport.width, cssViewport.height);
}

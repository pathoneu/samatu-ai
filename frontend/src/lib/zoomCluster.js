// zoomCluster — the arithmetic behind the zoom cluster's area zoom and minimap (Pathon v3 W5-B, B5; coverage
// #152, #178). Pure: rectangles in, page fractions out; components/viewer/ZoomCluster.jsx measures the DOM.

const clamp01 = (v) => Math.min(1, Math.max(0, v));

/**
 * A box dragged on the screen → the page fractions it covers on the page box `host` (both in client px):
 * [x0, y0, x1, y1] in the page's DISPLAYED frame (what FocusZoomer frames), or null when the box misses the
 * page. A drag shorter than `minPx` on both sides is a click: it frames a box of `clickShare` of the canvas
 * around the click, so a click with the area zoom zooms in twice at that place.
 */
export function dragToPageRect(drag, host, { canvas = null, minPx = 8, clickShare = 0.5 } = {}) {
  if (!drag || !host || !(host.width > 0) || !(host.height > 0)) return null;
  let x0 = Math.min(drag.x0, drag.x1);
  let x1 = Math.max(drag.x0, drag.x1);
  let y0 = Math.min(drag.y0, drag.y1);
  let y1 = Math.max(drag.y0, drag.y1);
  if (x1 - x0 < minPx && y1 - y0 < minPx) {
    const w = (canvas?.width || host.width) * clickShare;
    const h = (canvas?.height || host.height) * clickShare;
    x0 = drag.x1 - w / 2; x1 = drag.x1 + w / 2;
    y0 = drag.y1 - h / 2; y1 = drag.y1 + h / 2;
  }
  const r = [
    clamp01((x0 - host.left) / host.width), clamp01((y0 - host.top) / host.height),
    clamp01((x1 - host.left) / host.width), clamp01((y1 - host.top) / host.height),
  ];
  if (r[2] - r[0] <= 0.001 || r[3] - r[1] <= 0.001) return null;
  return r;
}

/** The part of the page box `host` the canvas shows, as page fractions [x0, y0, x1, y1] (the minimap's frame). */
export function visibleShare(host, canvas) {
  if (!host || !canvas || !(host.width > 0) || !(host.height > 0)) return null;
  const r = [
    clamp01((canvas.left - host.left) / host.width), clamp01((canvas.top - host.top) / host.height),
    clamp01((canvas.left + canvas.width - host.left) / host.width), clamp01((canvas.top + canvas.height - host.top) / host.height),
  ];
  return r[2] > r[0] && r[3] > r[1] ? r : null;
}

/** How far to scroll so the page fraction (fx, fy) lands in the canvas centre: {dx, dy} in px. */
export function scrollToCentre(host, canvas, fx, fy) {
  if (!host || !canvas) return { dx: 0, dy: 0 };
  return {
    dx: Math.round(host.left + clamp01(fx) * host.width - (canvas.left + canvas.width / 2)),
    dy: Math.round(host.top + clamp01(fy) * host.height - (canvas.top + canvas.height / 2)),
  };
}

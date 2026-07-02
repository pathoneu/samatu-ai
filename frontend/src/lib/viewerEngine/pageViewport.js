/**
 * pageViewport — wraps EmbedPDF's per-page PageLayout into the coordinate
 * contract our overlays already speak: renderedSize + pct⇄screen. width/height
 * from PageLayout are ALREADY scale+rotation-applied CSS px (verified in the
 * Phase 0 spike), so pct→screen is a plain multiply — no scale/rotation math.
 */
export function makeViewport(layout) {
  if (!layout || !layout.width || !layout.height) return null;
  const width = layout.width;
  const height = layout.height;
  return {
    pageNumber: layout.pageNumber,
    pageIndex: layout.pageIndex,
    width,
    height,
    renderedSize: () => ({ width, height }),
    pctToScreen: (p) => ({ x: p.x * width, y: p.y * height }),
    screenToPct: (p) => ({ x: p.x / width, y: p.y / height }),
  };
}

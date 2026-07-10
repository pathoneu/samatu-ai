/**
 * pageViewport — wraps EmbedPDF's per-page PageLayout into the coordinate
 * contract our overlays already speak: renderedSize + pct⇄screen.
 *
 * Use the ROTATION-APPLIED dims (rotatedWidth/rotatedHeight) — the same slot
 * size EmbedPDF's own Scroller uses. layout.width/height are the UNROTATED
 * mediabox CSS px; on a /Rotate 90|270 page they are portrait while the page
 * actually displays landscape, which transposed every overlay. (The old
 * "already rotation-applied" note was only ever true on /Rotate 0 pages, where
 * width == rotatedWidth so the bug was invisible.) pct→screen stays a plain
 * multiply because the host is now sized to the displayed (rotated) box.
 */
export function makeViewport(layout) {
  if (!layout || !layout.width || !layout.height) return null;
  const width = layout.rotatedWidth ?? layout.width;
  const height = layout.rotatedHeight ?? layout.height;
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

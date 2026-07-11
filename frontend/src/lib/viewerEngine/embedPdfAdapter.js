/**
 * embedPdfAdapter — the ONLY screen<->PDF coordinate boundary for measurement
 * overlays on the EmbedPDF viewer. Replicates the backup reactPdfAdapter
 * interface exactly: { width, height, scale, toViewport(pdfPt)→screenPx,
 * toPdf(screenPx)→pdfPt }.
 *
 * PDF points here are TOP-LEFT-origin mediabox points (rotation-independent):
 * measurements stored in this space survive zoom and /Rotate changes. The
 * display transform goes through the shared pageRotation helpers
 * (displayRotationFor = the page's true /Rotate now that PageOverlayHost's
 * content wrapper rotates the whole rendered page) so it can never diverge
 * from the wrapper's angle or TakeoffViewer's click-to-fill seed transform.
 */
import {
  normalizeRotation,
  displayRotationFor,
  rotatePctPoint,
  inverseRotatePctPoint,
} from './pageRotation.js';

export function makeEmbedAdapter({
  renderedWidth,
  renderedHeight,
  pageWidthPt,
  pageHeightPt,
  reportedRotation = 0,
}) {
  const rot = displayRotationFor(normalizeRotation(reportedRotation));
  const swapped = rot === 90 || rot === 270;
  return {
    width: renderedWidth,
    height: renderedHeight,
    // px per PDF point — the snap-tolerance divisor. On quarter-turn pages the
    // rendered width spans the mediabox HEIGHT, so divide by the swapped axis.
    scale: renderedWidth / (swapped ? pageHeightPt : pageWidthPt),
    toViewport(p) {
      const [fx, fy] = rotatePctPoint(p.x / pageWidthPt, p.y / pageHeightPt, rot);
      return { x: fx * renderedWidth, y: fy * renderedHeight };
    },
    toPdf(sp) {
      const [fx, fy] = inverseRotatePctPoint(sp.x / renderedWidth, sp.y / renderedHeight, rot);
      return { x: fx * pageWidthPt, y: fy * pageHeightPt };
    },
  };
}

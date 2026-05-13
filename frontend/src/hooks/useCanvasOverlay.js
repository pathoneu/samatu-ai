import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Resolve PDF↔screen↔CV-image coordinate spaces. PDF.js gives us the
 * viewport in PDF coords; the backend CV layer works in image coords
 * at a chosen DPI. The screen overlay paints in CSS pixels.
 *
 * Returned helpers:
 *   - pdfToScreen(x, y) — placing markers on top of the PDF canvas
 *   - screenToPdf(x, y) — capturing a click for the CV API
 *   - pdfToImage(x, y) — converting a PDF-coord point to image pixel
 *     at the chosen DPI (the /api/cv endpoints expect image-pixel bbox)
 *   - imageToPdf(x, y) — inverse of pdfToImage
 */
export function useCanvasOverlay(pdfPage, dpi = 200) {
  const [viewport, setViewport] = useState(null);
  const containerRef = useRef(null);

  useEffect(() => {
    if (!pdfPage) return;
    setViewport(pdfPage.getViewport({ scale: 1.0 }));
  }, [pdfPage]);

  const pdfToScreen = useCallback((x, y) => {
    if (!viewport) return [x, y];
    const [sx, sy] = viewport.convertToViewportPoint(x, y);
    return [sx, sy];
  }, [viewport]);

  const screenToPdf = useCallback((x, y) => {
    if (!viewport) return [x, y];
    const [px, py] = viewport.convertToPdfPoint(x, y);
    return [px, py];
  }, [viewport]);

  const pdfToImage = useCallback((x, y) => {
    // PDF point → image pixel at the chosen DPI. PDF unit = 1/72 inch.
    const k = dpi / 72;
    return [Math.round(x * k), Math.round(y * k)];
  }, [dpi]);

  const imageToPdf = useCallback((x, y) => {
    const k = 72 / dpi;
    return [x * k, y * k];
  }, [dpi]);

  return {
    viewport,
    pdfToScreen,
    screenToPdf,
    pdfToImage,
    imageToPdf,
    containerRef,
  };
}

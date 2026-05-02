/**
 * EksplikacijaRowFlash — Phase C-2 temporary halo over the eksplikacija
 * table row that justifies a particular room's plotas_m2.
 *
 * Triggered when user clicks an "iš eksplikacijos" provenance chip. Shows
 * a yellow halo for ~2.5 seconds, then fades.
 *
 * Reads room.eksplikacija_row_bbox = [x0, y0, x1, y1] in PDF point space,
 * plus eksplikacija_row_page_width_pdf / page_height_pdf for normalization.
 * (Set by pdfplumber_eksplikacija.py when row_bbox is available.)
 */

import { useEffect, useState } from 'react';

export default function EksplikacijaRowFlash({
  flashRoom,         // {eksplikacija_row_bbox, eksplikacija_row_page_width_pdf, ...} | null
  canvasWidth,
  canvasHeight,
  pdfPageWidth,
  pdfPageHeight,
  onComplete,
}) {
  const [opacity, setOpacity] = useState(0);

  useEffect(() => {
    if (!flashRoom?.eksplikacija_row_bbox) return;
    setOpacity(1);
    const fadeStart = setTimeout(() => setOpacity(0.6), 1200);
    const fadeOut = setTimeout(() => setOpacity(0), 2200);
    const done = setTimeout(() => onComplete?.(), 2500);
    return () => {
      clearTimeout(fadeStart);
      clearTimeout(fadeOut);
      clearTimeout(done);
    };
  }, [flashRoom?.nr, onComplete]);

  if (!flashRoom?.eksplikacija_row_bbox || !pdfPageWidth || !pdfPageHeight) return null;
  const [x0, y0, x1, y1] = flashRoom.eksplikacija_row_bbox;
  // pdfplumber returns top-left origin coords in PDF point space.
  // Convert to canvas px via the rendered page dims.
  const sx = canvasWidth / pdfPageWidth;
  const sy = canvasHeight / pdfPageHeight;
  const left = x0 * sx;
  const top = y0 * sy;
  const w = (x1 - x0) * sx;
  const h = (y1 - y0) * sy;

  return (
    <div
      style={{
        position: 'absolute',
        left, top, width: w, height: h,
        background: 'rgba(250, 204, 21, 0.35)',
        border: '2px solid rgba(250, 204, 21, 0.85)',
        borderRadius: 3,
        pointerEvents: 'none',
        zIndex: 30,
        opacity,
        transition: 'opacity 0.4s ease-out',
      }}
      data-testid="eksplikacija-row-flash"
    />
  );
}

import { useEffect, useRef, useState } from 'react';
import { matchTemplate } from '@/lib/cvToolsApi';

/**
 * Click-to-count: drag a rubber-band around a symbol on the page →
 * backend returns candidates → parent renders them via DrawingOverlay
 * and surfaces the CountReviewPanel.
 *
 * The component sits as an absolute layer over the rendered PDF page
 * (cursor: crosshair). It owns:
 *   - the rubber-band visual while the user drags
 *   - the bbox→/api/cv/match-template request on mouseup
 *   - error/loading text in a small floating chip
 *
 * Coords flow:
 *   screen pixels → divide by `pageScale` → PDF points → pdfToImage
 *   (cv DPI). The /api/cv contract is image pixels.
 */
export default function CountTool({
  projectId,
  pageIdx,
  width,
  height,
  pageScale,
  pdfToImage,
  dpi = 200,
  threshold = 0.80,
  onCandidates,
}) {
  const layerRef = useRef(null);
  const [drag, setDrag] = useState(null); // { sx, sy, ex, ey }
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const onMouseDown = (e) => {
    if (e.button !== 0) return;
    const rect = layerRef.current.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    setDrag({ sx, sy, ex: sx, ey: sy });
  };
  const onMouseMove = (e) => {
    if (!drag) return;
    const rect = layerRef.current.getBoundingClientRect();
    setDrag(d => ({ ...d, ex: e.clientX - rect.left, ey: e.clientY - rect.top }));
  };
  const onMouseUp = async () => {
    if (!drag) return;
    const w = Math.abs(drag.ex - drag.sx);
    const h = Math.abs(drag.ey - drag.sy);
    const x = Math.min(drag.sx, drag.ex);
    const y = Math.min(drag.sy, drag.ey);
    setDrag(null);
    if (w < 8 || h < 8) {
      setError(
        'Per maža sritis. Reikia VILKTI pelę: paspauskite simbolio kairėje viršuje, '
        + 'palaikykite ir patempkite per visą simbolį.',
      );
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // screen px → PDF pt → image px at the cv DPI
      const pdfX = x / pageScale;
      const pdfY = y / pageScale;
      const pdfW = w / pageScale;
      const pdfH = h / pageScale;
      const [ix, iy] = pdfToImage(pdfX, pdfY);
      const [ix2, iy2] = pdfToImage(pdfX + pdfW, pdfY + pdfH);
      const out = await matchTemplate({
        project_id: projectId,
        page_idx: pageIdx,
        bbox: [ix, iy, ix2 - ix, iy2 - iy],
        threshold,
        dpi,
      });
      onCandidates(out.candidates || [], { dpi, bbox: [ix, iy, ix2 - ix, iy2 - iy] });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  // Cancel a half-drawn rubber-band on Escape.
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setDrag(null);
        setError(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div
      ref={layerRef}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={() => setDrag(null)}
      style={{
        position: 'absolute',
        inset: 0,
        width,
        height,
        cursor: 'crosshair',
        zIndex: 30,
      }}
    >
      {drag && (
        <div
          style={{
            position: 'absolute',
            left: Math.min(drag.sx, drag.ex),
            top: Math.min(drag.sy, drag.ey),
            width: Math.abs(drag.ex - drag.sx),
            height: Math.abs(drag.ey - drag.sy),
            border: '2px dashed #2563eb',
            background: 'rgba(37, 99, 235, 0.10)',
            pointerEvents: 'none',
          }}
        />
      )}
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          background: 'rgba(255, 251, 235, 0.97)',
          border: '2px solid #f59e0b',
          borderRadius: 6,
          padding: '8px 12px',
          fontSize: 13,
          color: '#78350f',
          pointerEvents: 'none',
          maxWidth: 360,
          boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
        }}
      >
        {busy ? (
          <span>Ieškoma panašių simbolių visame puslapy…</span>
        ) : (
          <>
            <div style={{ fontWeight: 700, marginBottom: 2 }}>
              ✏️ VILKITE pelę aplink simbolį
            </div>
            <div style={{ fontSize: 11, color: '#92400e' }}>
              Paspauskite kairiajame viršutiniame kampe → palaikykite → patempkite
              per dešinį apatinį. (NE tik paspausti.)
            </div>
          </>
        )}
        {error && (
          <div style={{ color: '#b91c1c', marginTop: 6, fontSize: 11 }}>{error}</div>
        )}
      </div>
    </div>
  );
}

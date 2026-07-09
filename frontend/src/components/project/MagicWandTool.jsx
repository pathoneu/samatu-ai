import { useEffect, useRef, useState } from 'react';
import { magicWand } from '@/lib/cvToolsApi';

/**
 * Magic-wand polygon suggestion. Click inside an empty room area →
 * backend returns a polygon (or null when click hit a wall) →
 * suggested polygon is handed up via onPolygon(pdfPoints) so the
 * existing polygon editor (MarkupCanvas) can render handles for edit.
 *
 * Sensitivity slider exposes the morph close kernel size — wider gaps
 * (architectural drawings often draw doors as a 6–12 px break) need a
 * larger value, but oversized values eat into wall corners. Default 7
 * is the empirically usable middle.
 */
export default function MagicWandTool({
  projectId,
  pageIdx,
  width,
  height,
  pageScale,
  pdfToImage,
  imageToPdf,
  dpi = 200,
  onPolygon,
}) {
  const layerRef = useRef(null);
  const [closeKernel, setCloseKernel] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const onClick = async (e) => {
    if (e.button !== 0) return;
    const rect = layerRef.current.getBoundingClientRect();
    const sx = e.clientX - rect.left;
    const sy = e.clientY - rect.top;
    setBusy(true);
    setError(null);
    try {
      // screen px → PDF pt → image px at the cv DPI
      const pdfX = sx / pageScale;
      const pdfY = sy / pageScale;
      const [ix, iy] = pdfToImage(pdfX, pdfY);
      const out = await magicWand({
        project_id: projectId,
        page_idx: pageIdx,
        click: [ix, iy],
        close_kernel: closeKernel,
        dpi,
      });
      if (!out.polygon) {
        setError('Paspaudėte ant sienos. Pabandykite paspausti tuščioje patalpos vietoje (toliau nuo sienų).');
        return;
      }
      // Sanity check: if polygon covers most of the page, flood fill leaked
      // through a door gap. Tell the user to bump the sensitivity slider
      // instead of showing them a useless full-page rectangle.
      if (out.page_size && out.polygon.length > 0) {
        const [pageW, pageH] = out.page_size;
        const xs = out.polygon.map(p => p[0]);
        const ys = out.polygon.map(p => p[1]);
        const bboxArea = (Math.max(...xs) - Math.min(...xs))
          * (Math.max(...ys) - Math.min(...ys));
        if (bboxArea > pageW * pageH * 0.6) {
          setError(
            'Patalpa "ištekėjo" pro tarpus tarp sienų. Pakelkite jautrumą '
            + '(stumkite šliaužiklį į dešinę) ir bandykite dar kartą.',
          );
          return;
        }
      }
      // image px → PDF pt for the editor
      const pdfPts = out.polygon.map(([x, y]) => {
        const [px, py] = imageToPdf(x, y);
        return { x: px, y: py };
      });
      onPolygon(pdfPts);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') setError(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div
      ref={layerRef}
      onClick={onClick}
      style={{
        position: 'absolute',
        inset: 0,
        width,
        height,
        cursor: busy ? 'wait' : 'crosshair',
        zIndex: 30,
      }}
    >
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          background: 'hsl(var(--popover) / 0.96)',
          border: '1px solid hsl(var(--border-strong))',
          borderRadius: 4,
          padding: '6px 10px',
          fontSize: 12,
          color: 'hsl(var(--foreground))',
          pointerEvents: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          minWidth: 220,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ fontWeight: 600 }}>
          {busy ? 'Ieškoma patalpos sienų…' : '👆 Paspauskite TUŠČIOJE patalpos vietoje'}
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 110 }}>Sienų užpildymas</span>
          <input
            type="range"
            min="3"
            max="21"
            step="2"
            value={closeKernel}
            onChange={e => setCloseKernel(Number(e.target.value))}
            style={{ flex: 1 }}
          />
          <span style={{ width: 20, textAlign: 'right' }}>{closeKernel}</span>
        </label>
        <div style={{ fontSize: 10, color: 'hsl(var(--muted-foreground))' }}>
          Jei patalpa "išteka" už sienų — pakelkite šliaužiklį į dešinę.
        </div>
        {error && <div style={{ color: 'hsl(var(--destructive))', fontSize: 11 }}>{error}</div>}
      </div>
    </div>
  );
}

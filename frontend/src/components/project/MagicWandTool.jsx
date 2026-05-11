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
        setError('Paspaudei ant sienos arba per arti tarpo. Pabandyk kitur arba padidink jautrumą.');
        return;
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
          background: 'rgba(255,255,255,0.92)',
          border: '1px solid #cbd5e1',
          borderRadius: 4,
          padding: '6px 10px',
          fontSize: 12,
          color: '#0f172a',
          pointerEvents: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 4,
          minWidth: 220,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div>{busy ? 'Aptinkama…' : 'Spausk patalpos vidury'}</div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ width: 60 }}>Jautrumas</span>
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
        {error && <div style={{ color: '#b91c1c', fontSize: 11 }}>{error}</div>}
      </div>
    </div>
  );
}

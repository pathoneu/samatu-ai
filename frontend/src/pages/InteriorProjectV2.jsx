// frontend/src/pages/InteriorProjectV2.jsx
/**
 * Sprint 1: new dual-route mount for the takeoff workspace.
 *
 * URL: /project/:id/v2 — opt-in during Sprints 1-3, default at end of
 * Sprint 3, legacy /project/:id removed Sprint 4.
 *
 * For Sprint 1 this page only mounts <TakeoffCanvas>; full chrome
 * (top bar, side panel, verification panel) arrives Sprint 3.
 *
 * Worker note: we import pdfjs from react-pdf (4.8.69) rather than the
 * standalone pdfjs-dist (4.10.38) to avoid version drift.  PdfViewer.jsx
 * already sets GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs' at module
 * load; if PdfViewer is not in the bundle chunk for this route we set it
 * here too — the guard at the top of PdfViewer will still catch a drift.
 */
import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { pdfjs } from 'react-pdf';
import { getPdfBlob } from '../lib/pdfStore';
import { TakeoffCanvas } from '../components/canvas/TakeoffCanvas';
import { MemoryWatchdog } from '../components/canvas/MemoryWatchdog';
import { tileCache } from '../lib/tileCache';

// Set workerSrc here so this route works even when PdfViewer.jsx is
// tree-shaken into a different chunk.  Idempotent: setting the same
// value twice is harmless.
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs';

export default function InteriorProjectV2() {
  const { id } = useParams();
  const [pdfDoc, setPdfDoc] = useState(null);
  const [error, setError] = useState(null);

  const loadPdf = useCallback(async () => {
    try {
      const blob = await getPdfBlob(id);
      if (!blob) {
        setError('Brėžinys nerastas (uždaryk + atidaryk projektą iš naujo).');
        return;
      }
      const buf = await blob.arrayBuffer();
      const doc = await pdfjs.getDocument({ data: buf }).promise;
      setPdfDoc(doc);
    } catch (err) {
      setError(`Nepavyko užkrauti PDF: ${err.message}`);
    }
  }, [id]);

  useEffect(() => { loadPdf(); }, [loadPdf]);

  const handleReset = useCallback(() => {
    pdfDoc?.destroy().catch(() => {});
    tileCache.clear();
    setPdfDoc(null);
    loadPdf();
  }, [pdfDoc, loadPdf]);

  if (error) return <div style={{ padding: 20, color: '#fff' }}>{error}</div>;
  if (!pdfDoc) return <div style={{ padding: 20, color: '#aaa' }}>Kraunamas brėžinys…</div>;

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#0e1216' }}>
      <MemoryWatchdog onReset={handleReset} />
      <TakeoffCanvas pdfDoc={pdfDoc} pageIdx={0} />
    </div>
  );
}

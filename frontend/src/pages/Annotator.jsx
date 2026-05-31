/**
 * /annotator — minimal interactive PDF measurement viewer (MVP).
 *
 * - Loads a project's floor-plan PDF via the existing react-pdf <Page>.
 * - Overlays a plain HTML5 <canvas> for drawing (no fabric.js dep —
 *   small surface area + production-safe).
 * - Two tools:
 *     • Calibrate — click two points + enter mm; sets scale factor.
 *     • Measure   — click two points; renders a line + mm label.
 * - Right pane is a stub KŽ table that can be wired to project samata.
 *
 * Persistence calls the backend endpoint at /api/projects/<id>/annotations
 * (built in this same turn). For the MVP we keep state in React only;
 * adding "Save" is one fetch call away.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Document, Page, pdfjs } from 'react-pdf';

// react-pdf worker — same setup as the existing PdfViewer
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const TOOLS = {
  NONE: 'none',
  CALIBRATE: 'calibrate',
  MEASURE: 'measure',
};

/** Convert client (page) coords to canvas-local coords. */
function clientToCanvas(canvas, e) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  };
}

export default function Annotator() {
  const { id: projectId } = useParams();
  const [searchParams] = useSearchParams();
  const pdfUrl = searchParams.get('pdf') || `/api/projects/${projectId}/pdf`;
  const initialPage = Number(searchParams.get('page') || 1);

  const [numPages, setNumPages] = useState(0);
  const [pageNum, setPageNum] = useState(initialPage);
  const [pageDims, setPageDims] = useState({ width: 0, height: 0 });
  const [tool, setTool] = useState(TOOLS.NONE);

  // mm per CSS pixel; null until first calibration.
  const [scale, setScale] = useState(null);
  const [draftStart, setDraftStart] = useState(null);
  const [measurements, setMeasurements] = useState([]); // {x1,y1,x2,y2,length_mm}
  const [calibrationPoints, setCalibrationPoints] = useState([]);
  const [loadError, setLoadError] = useState(null);
  // Persistence state
  const [saveStatus, setSaveStatus] = useState(null);  // "saving" | "saved" | "error"
  const [lastSavedAt, setLastSavedAt] = useState(null);

  const canvasRef = useRef(null);
  const containerRef = useRef(null);

  // ── Persistence ──────────────────────────────────────────────────────────
  const annotationsUrl = `/api/projects/${projectId}/annotations`;

  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      const body = {
        measurements,
        calibration_scale_mm_per_px: scale,
        page: pageNum,
      };
      const r = await fetch(annotationsUrl, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`HTTP ${r.status}: ${t.slice(0, 200)}`);
      }
      const j = await r.json();
      setSaveStatus('saved');
      setLastSavedAt(j.updated_at || Math.floor(Date.now() / 1000));
    } catch (err) {
      console.error('annotation save failed', err);
      setSaveStatus('error');
    }
  };

  const handleLoad = async () => {
    setSaveStatus('saving');
    try {
      const r = await fetch(annotationsUrl, { credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      if (Array.isArray(j.measurements)) setMeasurements(j.measurements);
      if (typeof j.calibration_scale_mm_per_px === 'number') {
        setScale(j.calibration_scale_mm_per_px);
      }
      if (j.page && Number.isFinite(j.page)) setPageNum(j.page);
      setSaveStatus('saved');
      setLastSavedAt(j.updated_at || null);
    } catch (err) {
      console.error('annotation load failed', err);
      setSaveStatus('error');
    }
  };

  // Redraw all overlay objects whenever they change.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Calibration in-progress line
    if (calibrationPoints.length === 2) {
      const [a, b] = calibrationPoints;
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // Persisted measurements
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#2a6fb5';
    ctx.fillStyle = '#2a6fb5';
    ctx.font = '12px ui-sans-serif, system-ui';
    for (const m of measurements) {
      ctx.beginPath();
      ctx.moveTo(m.x1, m.y1);
      ctx.lineTo(m.x2, m.y2);
      ctx.stroke();
      const midX = (m.x1 + m.x2) / 2;
      const midY = (m.y1 + m.y2) / 2;
      const label = `${m.length_mm.toFixed(0)} mm`;
      const w = ctx.measureText(label).width + 8;
      ctx.fillStyle = 'rgba(255,255,255,0.9)';
      ctx.fillRect(midX - w / 2, midY - 16, w, 16);
      ctx.fillStyle = '#2a6fb5';
      ctx.fillText(label, midX - w / 2 + 4, midY - 4);
    }

    // Draft (active drawing) line
    if (draftStart) {
      ctx.strokeStyle = '#16a34a';
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(draftStart.x, draftStart.y);
      ctx.lineTo(draftStart.x, draftStart.y); // placeholder; mousemove fills
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [measurements, draftStart, calibrationPoints]);

  // Sync canvas size to PDF dims
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    c.width = pageDims.width;
    c.height = pageDims.height;
  }, [pageDims]);

  const onCanvasClick = (e) => {
    if (tool === TOOLS.NONE) return;
    const c = canvasRef.current;
    if (!c) return;
    const p = clientToCanvas(c, e);

    if (tool === TOOLS.CALIBRATE) {
      const next = [...calibrationPoints, p];
      if (next.length === 1) {
        setCalibrationPoints(next);
        return;
      }
      // Second point — ask user for the true mm
      const distPx = Math.hypot(next[1].x - next[0].x, next[1].y - next[0].y);
      const input = window.prompt(
        `Įveskite TIKRĄ atstumą tarp dviejų taškų milimetrais (px=${distPx.toFixed(1)}):`,
        '1000',
      );
      const trueMm = parseFloat(input || '');
      if (Number.isFinite(trueMm) && trueMm > 0 && distPx > 0) {
        setScale(trueMm / distPx); // mm per px
      }
      setCalibrationPoints([]);
      setTool(TOOLS.NONE);
      return;
    }

    if (tool === TOOLS.MEASURE) {
      if (!scale) {
        alert('Pirmiausia kalibruokite mastelį.');
        setTool(TOOLS.CALIBRATE);
        return;
      }
      if (!draftStart) {
        setDraftStart(p);
        return;
      }
      const dx = p.x - draftStart.x;
      const dy = p.y - draftStart.y;
      const lenPx = Math.hypot(dx, dy);
      const lenMm = lenPx * scale;
      setMeasurements((prev) => [
        ...prev,
        { x1: draftStart.x, y1: draftStart.y, x2: p.x, y2: p.y, length_mm: lenMm },
      ]);
      setDraftStart(null);
    }
  };

  const onCanvasMove = (e) => {
    if (!draftStart || tool !== TOOLS.MEASURE) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    // Repaint everything then draw the live line
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    // Triggering the redraw effect is enough — but to render the live cursor
    // we need a quick local draw without state churn:
    const p = clientToCanvas(canvas, e);
    ctx.strokeStyle = '#16a34a';
    ctx.lineWidth = 2;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(draftStart.x, draftStart.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    ctx.setLineDash([]);

    if (scale) {
      const lenPx = Math.hypot(p.x - draftStart.x, p.y - draftStart.y);
      ctx.fillStyle = '#16a34a';
      ctx.font = '12px ui-sans-serif, system-ui';
      ctx.fillText(`${(lenPx * scale).toFixed(0)} mm`, p.x + 6, p.y - 6);
    }
  };

  const onDocLoadSuccess = ({ numPages }) => setNumPages(numPages);
  const onDocLoadError = (err) => setLoadError(err?.message || String(err));

  const undoLast = () => setMeasurements((prev) => prev.slice(0, -1));
  const clearAll = () => setMeasurements([]);

  const toolbar = (
    <div className="flex flex-wrap items-center gap-2 border-b border-neutral-200 bg-white px-4 py-2 text-sm">
      <strong className="mr-3 text-neutral-700">Matavimas</strong>
      <button
        type="button"
        className={`rounded border px-3 py-1 ${
          tool === TOOLS.CALIBRATE ? 'border-amber-500 bg-amber-50' : 'border-neutral-300'
        }`}
        onClick={() => { setTool(TOOLS.CALIBRATE); setCalibrationPoints([]); setDraftStart(null); }}
      >
        Kalibruoti
      </button>
      <button
        type="button"
        className={`rounded border px-3 py-1 ${
          tool === TOOLS.MEASURE ? 'border-blue-500 bg-blue-50' : 'border-neutral-300'
        }`}
        onClick={() => { setTool(TOOLS.MEASURE); setDraftStart(null); }}
        disabled={!scale}
        title={!scale ? 'Pirmiausia kalibruokite' : ''}
      >
        Matuoti
      </button>
      <button
        type="button"
        className="rounded border border-neutral-300 px-3 py-1"
        onClick={() => { setTool(TOOLS.NONE); setDraftStart(null); }}
      >
        Stop
      </button>
      <span className="mx-3 text-neutral-400">|</span>
      <button
        type="button"
        className="rounded border border-neutral-300 px-3 py-1"
        onClick={undoLast}
        disabled={!measurements.length}
      >
        Atšaukti
      </button>
      <button
        type="button"
        className="rounded border border-neutral-300 px-3 py-1"
        onClick={clearAll}
        disabled={!measurements.length}
      >
        Išvalyti
      </button>
      <button
        type="button"
        className="rounded border border-emerald-500 bg-emerald-50 px-3 py-1 text-emerald-700"
        onClick={handleSave}
        disabled={saveStatus === 'saving'}
        title="Įrašyti matavimus į backend"
      >
        Įrašyti
      </button>
      <button
        type="button"
        className="rounded border border-neutral-300 px-3 py-1"
        onClick={handleLoad}
        disabled={saveStatus === 'saving'}
        title="Atkurti paskutinius įrašytus matavimus"
      >
        Atkurti
      </button>
      <span className="ml-2 text-xs text-neutral-500">
        {saveStatus === 'saving' && '⏳ siunčiama…'}
        {saveStatus === 'saved' && lastSavedAt && `✓ įrašyta ${new Date(lastSavedAt * 1000).toLocaleTimeString('lt-LT')}`}
        {saveStatus === 'error' && '⚠ klaida'}
      </span>
      <span className="ml-auto text-neutral-600">
        Mastelis: <strong>{scale ? `${(scale).toFixed(3)} mm/px` : 'nekalibruota'}</strong>
        {' · '}
        Matavimų: <strong>{measurements.length}</strong>
        {' · '}
        Puslapis {pageNum}/{numPages || '?'}
      </span>
    </div>
  );

  const sidePanel = (
    <aside className="flex w-[40%] flex-col border-l border-neutral-200 bg-neutral-50">
      <header className="border-b border-neutral-200 px-4 py-3">
        <h3 className="font-semibold text-neutral-800">Matavimų sąrašas</h3>
        <p className="text-xs text-neutral-500">
          Spauskite „Kalibruoti", brėžkite linija ant žinomo dydžio brėžinyje,
          įveskite tikrą atstumą mm. Po to „Matuoti" – tarp dviejų taškų rodys
          mm pagal jūsų kalibravimą.
        </p>
      </header>
      <ol className="flex-1 overflow-auto text-sm">
        {measurements.length === 0 && (
          <li className="px-4 py-4 text-neutral-400">Dar nėra matavimų.</li>
        )}
        {measurements.map((m, i) => (
          <li key={i} className="flex items-center justify-between border-b border-neutral-100 px-4 py-2">
            <span className="text-neutral-700">#{i + 1}</span>
            <span className="font-mono text-blue-700">{m.length_mm.toFixed(1)} mm</span>
            <span className="text-neutral-400">
              ({m.x1.toFixed(0)},{m.y1.toFixed(0)} → {m.x2.toFixed(0)},{m.y2.toFixed(0)})
            </span>
          </li>
        ))}
      </ol>
      <footer className="border-t border-neutral-200 px-4 py-3 text-xs text-neutral-500">
        Annotation persistence backend endpoint:
        <code className="ml-1">{`PUT /api/projects/${projectId}/annotations`}</code>
        <br />
        Žinomas matavimų išsaugojimas šiame MVP nepalaikomas (planuojama kitame žingsnyje).
      </footer>
    </aside>
  );

  return (
    <div className="flex h-screen flex-col bg-neutral-100">
      {toolbar}
      {loadError && (
        <div className="bg-red-50 border-y border-red-200 px-4 py-2 text-sm text-red-700">
          PDF įkėlimo klaida: {loadError}
        </div>
      )}
      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-1 items-start justify-center overflow-auto p-4">
          <div
            ref={containerRef}
            className="relative inline-block bg-white shadow"
          >
            <Document
              file={pdfUrl}
              onLoadSuccess={onDocLoadSuccess}
              onLoadError={onDocLoadError}
              loading={<div className="p-12 text-neutral-500">Kraunama PDF…</div>}
            >
              <Page
                pageNumber={pageNum}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                onRenderSuccess={(page) => {
                  // page.width/height are CSS pixels at scale=1
                  setPageDims({ width: page.width, height: page.height });
                }}
              />
            </Document>
            <canvas
              ref={canvasRef}
              onClick={onCanvasClick}
              onMouseMove={onCanvasMove}
              className="absolute left-0 top-0 cursor-crosshair"
              style={{
                width: pageDims.width || 0,
                height: pageDims.height || 0,
                pointerEvents: tool === TOOLS.NONE ? 'none' : 'auto',
              }}
            />
          </div>
        </main>
        {sidePanel}
      </div>
    </div>
  );
}

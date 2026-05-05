// frontend/src/pages/InteriorProjectV2.jsx
/**
 * Sprint 3 Task 16: full chrome mount. Sprint 3-B simplification trim.
 *
 * URL: /project/:id/v2 — opt-in during Sprints 1-3, default at end of
 * Sprint 3, legacy /project/:id removed Sprint 4.
 *
 * Mounts:
 *   - TopBar (48px, top)               — page nav, zoom, search, AI
 *   - ToolRail (50px, left)            — gesture tool selection
 *   - TakeoffCanvas (center)           — Sprint 1 mip-pyramid renderer
 *   - GestureSurface + AnnotationLayer — gestures + Konva overlay
 *   - RightPanel (320px, right)        — single Kiekiai panel
 *   - MemoryWatchdog                   — Sprint 1 carryover
 *
 * State plumbing:
 *   - AI Run button calls /extract-interior
 *   - Page nav drives viewerStore.currentPage
 *   - QuantitiesPanel hover → setHoveredRoomId → AnnotationLayer thickens
 *     polygon stroke + glow
 *   - committedPolygons derived from rooms[] with polygon_pct
 *
 * Sprint 3-B notes:
 *   - VerificationWizard + buildQueue removed (confidence model upstream
 *     was unreliable; UI added complexity for no value).
 *   - AiPanel + SuvestinePanel files retained but no longer mounted; the
 *     RightPanel now renders QuantitiesPanel directly.
 *
 * Worker note: import pdfjs from react-pdf (4.8.69) rather than
 * standalone pdfjs-dist to avoid version drift. PdfViewer.jsx already
 * sets GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs' at module load;
 * we set it here too in case PdfViewer is tree-shaken into a different
 * chunk for this route.
 */
import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { pdfjs } from 'react-pdf';
import { useStore } from 'zustand';
import { getPdfBlob } from '../lib/pdfStore';
import { getProject, updateProject } from '../lib/projectStore';
import { TakeoffCanvas } from '../components/canvas/TakeoffCanvas';
import { MemoryWatchdog } from '../components/canvas/MemoryWatchdog';
import { AnnotationLayer } from '../components/canvas/AnnotationLayer';
import { PageNavigator } from '../components/canvas/PageNavigator';
import { TopBar } from '../components/workspace/TopBar';
import { ToolRail } from '../components/workspace/ToolRail';
import { RightPanel } from '../components/workspace/RightPanel';
import { tileCache } from '../lib/tileCache';
import { createSession } from '../lib/telemetry';
import { attachShortcuts } from '../lib/keyboardShortcuts';
import { categoryAccent } from '../lib/categoryColor';
import { useG1Handler } from '../components/canvas/gestures/G1VisionFill';
import { useG2Handler } from '../components/canvas/gestures/G2AddCount';
import { useG3Handler } from '../components/canvas/gestures/G3RemoveCount';
import { useG4Handler } from '../components/canvas/gestures/G4ColorSample';
import { useG5Handlers } from '../components/canvas/gestures/G5Lasso';
import { viewerStore } from '../lib/viewerStore';

// Set workerSrc here so this route works even when PdfViewer.jsx is
// tree-shaken into a different chunk. Idempotent: setting the same
// value twice is harmless.
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs';

export default function InteriorProjectV2() {
  const { id } = useParams();
  const [pdfDoc, setPdfDoc] = useState(null);
  const [error, setError] = useState(null);
  const [project, setProject] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [pozicijos, setPozicijos] = useState([]);
  const [assumptions, setAssumptions] = useState({});
  const [committedPoints, setCommittedPoints] = useState([]);
  const [preview, setPreview] = useState(null);
  const [aiRunning, setAiRunning] = useState(false);
  const [pageNavOpen, setPageNavOpen] = useState(false);
  const [pages, setPages] = useState([]);
  const sessionRef = useRef(null);

  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);
  const currentPage = useStore(viewerStore, (s) => s.currentPage);
  const setCurrentPage = useStore(viewerStore, (s) => s.setCurrentPage);
  const scale = useStore(viewerStore, (s) => s.scale);
  const setScale = useStore(viewerStore, (s) => s.setScale);

  // ─── PDF loading ──────────────────────────────────────────────────
  const loadPdf = useCallback(async () => {
    try {
      const blob = await getPdfBlob(id);
      if (!blob) { setError('Brėžinys nerastas.'); return; }
      const buf = await blob.arrayBuffer();
      const doc = await pdfjs.getDocument({ data: buf }).promise;
      setPdfDoc(doc);
      // Build pages list for PageNavigator (titles deferred to Sprint 4).
      const total = doc.numPages || 1;
      setPages(Array.from({ length: total }, (_, i) => ({ kind: `Puslapis ${i + 1}` })));
    } catch (err) { setError(`Nepavyko užkrauti PDF: ${err.message}`); }
  }, [id]);

  useEffect(() => { loadPdf(); }, [loadPdf]);

  // ─── Project load ─────────────────────────────────────────────────
  useEffect(() => {
    const proj = getProject(id);
    if (!proj) return;
    setProject(proj);
    if (Array.isArray(proj.darbu_sarasas)) {
      setPozicijos(proj.darbu_sarasas.map((p, i) => ({
        ...p, id: p.id || (p.eil_nr != null ? `poz-${p.eil_nr}` : `poz-${i}`),
      })));
    }
    const projectRooms = proj.raw_calc_data?.patalpos || proj.v8_rooms || proj.patalpos;
    if (Array.isArray(projectRooms)) {
      setRooms(projectRooms.map((r, i) => ({
        ...r, id: r.id || (r.nr ? `room-${r.nr}` : `room-${i}`),
      })));
    }
    if (proj.prielaidos) setAssumptions(proj.prielaidos);
  }, [id]);

  // ─── Telemetry session + keyboard shortcuts ───────────────────────
  useEffect(() => {
    sessionRef.current = createSession({ projectId: id });
    const onUnload = () => sessionRef.current?.finish({ exported: false });
    window.addEventListener('beforeunload', onUnload);
    const detachKb = attachShortcuts({ setCurrentTool });
    return () => {
      window.removeEventListener('beforeunload', onUnload);
      sessionRef.current?.finish({ exported: false });
      detachKb();
    };
  }, [id, setCurrentTool]);

  const recordGesture = useCallback((g) => sessionRef.current?.recordGesture(g), []);

  // ─── Recompute pipeline (G1..G7 callback) ─────────────────────────
  const onRecomputed = useCallback((result) => {
    if (result.rooms) setRooms(result.rooms);
    if (result.pozicijos) setPozicijos(result.pozicijos);
    if (result.assumptions) setAssumptions(result.assumptions);
  }, []);

  // ─── Derived: committedPolygons from rooms[] ─────────────────────
  const committedPolygons = useMemo(() => {
    return rooms
      .filter((r) => Array.isArray(r.polygon_pct) && r.polygon_pct.length >= 3)
      .map((r) => ({
        id: r.id,
        points: r.polygon_pct,
        color: categoryAccent(r.skyrius_enum),
        fillAlpha: 0.18,
      }));
  }, [rooms]);

  // ─── Memory reset ─────────────────────────────────────────────────
  const handleReset = useCallback(() => {
    pdfDoc?.destroy().catch(() => {});
    tileCache.clear();
    setPdfDoc(null);
    loadPdf();
  }, [pdfDoc, loadPdf]);

  // ─── AI Run handler ───────────────────────────────────────────────
  const handleAiRun = useCallback(async () => {
    if (aiRunning || !project) return;
    setAiRunning(true);
    try {
      const blob = await getPdfBlob(id);
      if (!blob) throw new Error('PDF nerastas');
      const fd = new FormData();
      fd.append('files', blob, (project.name || 'projektas') + '.pdf');
      if (project._overrides) fd.append('rules_override', JSON.stringify(project._overrides));
      const res = await fetch('/extract-interior', {
        method: 'POST',
        credentials: 'include',
        body: fd,
        signal: AbortSignal.timeout(600_000),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      const result = await res.json();
      if (result?.status === 'error') throw new Error(result._error || 'Pipeline klaida');
      if (!result.patalpos) throw new Error('AI grąžino netinkamą formatą');
      const merged = {
        ...project,
        ...result,
        name: project.name,
        company_name: project.company_name,
        vat_rate: project.vat_rate,
        _reextracted_at: new Date().toISOString(),
      };
      updateProject(project.id, merged);
      setProject(merged);
      // Refresh local rooms / pozicijos / prielaidos
      if (Array.isArray(merged.darbu_sarasas)) {
        setPozicijos(merged.darbu_sarasas.map((p, i) => ({
          ...p, id: p.id || (p.eil_nr != null ? `poz-${p.eil_nr}` : `poz-${i}`),
        })));
      }
      const rs = merged.raw_calc_data?.patalpos || merged.v8_rooms || merged.patalpos;
      if (Array.isArray(rs)) {
        setRooms(rs.map((r, i) => ({
          ...r, id: r.id || (r.nr ? `room-${r.nr}` : `room-${i}`),
        })));
      }
      if (merged.prielaidos) setAssumptions(merged.prielaidos);
    } catch (err) {
      console.error('[AI run] failed:', err);
      alert(`AI klaida: ${err.message}`);
    } finally {
      setAiRunning(false);
    }
  }, [aiRunning, project, id]);

  // ─── TopBar handlers ──────────────────────────────────────────────
  const onPrevPage = useCallback(() => {
    setCurrentPage(Math.max(0, currentPage - 1));
  }, [currentPage, setCurrentPage]);
  const onNextPage = useCallback(() => {
    setCurrentPage(Math.min(pages.length - 1, currentPage + 1));
  }, [currentPage, pages.length, setCurrentPage]);
  const onZoomIn = useCallback(() => setScale(Math.min(scale * 1.1, 6)), [scale, setScale]);
  const onZoomOut = useCallback(() => setScale(Math.max(scale / 1.1, 0.25)), [scale, setScale]);
  const onPagePicker = useCallback(() => setPageNavOpen((v) => !v), []);

  if (error) return <div style={{ padding: 20, color: '#fff' }}>{error}</div>;
  if (!pdfDoc) return <div style={{ padding: 20, color: '#aaa' }}>Kraunamas brėžinys…</div>;

  return (
    <div style={{
      width: '100vw', height: '100vh', background: '#0e1216',
      display: 'flex', flexDirection: 'column',
    }}>
      <MemoryWatchdog onReset={handleReset} />

      {/* TopBar */}
      <TopBar
        projectName={project?.name || 'Projektas'}
        subtitle={project?.company_name}
        pageTitle={pages[currentPage]?.title || pages[currentPage]?.kind}
        totalPages={pages.length || 1}
        onPrevPage={onPrevPage}
        onNextPage={onNextPage}
        onPagePicker={onPagePicker}
        onZoomIn={onZoomIn}
        onZoomOut={onZoomOut}
        onSearch={() => { /* Sprint 4 */ }}
        onAiRun={handleAiRun}
        onMore={() => { /* Sprint 4 */ }}
      />

      {pageNavOpen && (
        <PageNavigator
          pages={pages}
          currentPage={currentPage}
          onSelect={setCurrentPage}
          onClose={() => setPageNavOpen(false)}
        />
      )}

      {/* Center row: ToolRail | Canvas | RightPanel */}
      <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
        <ToolRail />

        {/* Canvas area */}
        <div style={{ flex: 1, position: 'relative', minWidth: 0 }}>
          <TakeoffCanvas
            pdfDoc={pdfDoc}
            renderOverlay={({ canvasWidth, canvasHeight, canvasRef, containerRef }) => (
              <GestureSurface
                {...{
                  projectId: id, pageIdx: currentPage,
                  canvasWidth, canvasHeight, canvasRef, containerRef,
                  rooms, pozicijos, currentAssumptions: assumptions,
                  committedPolygons, committedPoints, preview,
                  onPolygonAdded: (poly) => {
                    // Polygons committed by G1 should also persist on rooms[]
                    // (Sprint 4 will properly thread through projectStore).
                    // For Sprint 3 we keep them in a dedicated overlay list:
                    setRooms((rs) => [...rs, {
                      id: poly.id,
                      polygon_pct: poly.points,
                      _ephemeral: true,
                    }]);
                  },
                  onLassoResult: (result) => {
                    const newPoints = (result.symbols || []).map((s, i) => ({
                      id: `g5-${Date.now()}-${i}`, xy: s.xy_pct, color: '#22c55e', kind: s.type,
                    }));
                    setCommittedPoints((ps) => [...ps, ...newPoints]);
                  },
                  onRecomputed,
                  onGestureEvent: recordGesture,
                  onPreviewChange: setPreview,
                }}
              />
            )}
          />
        </div>

        {/* RightPanel */}
        <RightPanel
          rooms={rooms}
          pozicijos={pozicijos}
          currentAssumptions={assumptions}
          onRecomputed={onRecomputed}
          onGestureEvent={recordGesture}
        />
      </div>
    </div>
  );
}

function GestureSurface({
  projectId, pageIdx, canvasWidth, canvasHeight, canvasRef, containerRef,
  rooms, pozicijos, currentAssumptions,
  committedPolygons, committedPoints, preview,
  onPolygonAdded, onLassoResult, onRecomputed, onGestureEvent, onPreviewChange,
}) {
  const onG1 = useG1Handler({ projectId, pageIdx, canvasWidth, canvasHeight,
                              containerRef, onPolygonAdded, onGestureEvent });
  const onG2 = useG2Handler({ rooms, pozicijos, currentAssumptions,
                              canvasWidth, canvasHeight, containerRef,
                              onRecomputed, onGestureEvent });
  const onG3 = useG3Handler({ rooms, pozicijos, currentAssumptions,
                              onRecomputed, onGestureEvent });
  const onG4 = useG4Handler({ rooms, pozicijos, currentAssumptions,
                              canvasRef, canvasWidth, canvasHeight,
                              containerRef, onRecomputed, onGestureEvent });
  const g5 = useG5Handlers({ projectId, pageIdx, canvasWidth, canvasHeight,
                             containerRef, onLassoResult, onGestureEvent,
                             onPreviewChange });

  const onClick = (e) => { onG1(e) || onG2(e) || onG3(e) || onG4(e); };
  return (
    <>
      <div
        onClick={onClick}
        onPointerDown={g5.onPointerDown}
        onPointerMove={g5.onPointerMove}
        onPointerUp={g5.onPointerUp}
        style={{ position: 'absolute', inset: 0, zIndex: 2 }}
      />
      <div style={{ position: 'absolute', inset: 0, zIndex: 3, pointerEvents: 'none' }}>
        <AnnotationLayer
          width={canvasWidth || 1}
          height={canvasHeight || 1}
          canvasWidth={canvasWidth || 1}
          canvasHeight={canvasHeight || 1}
          committedPolygons={committedPolygons}
          committedPoints={committedPoints}
          preview={preview}
        />
      </div>
    </>
  );
}

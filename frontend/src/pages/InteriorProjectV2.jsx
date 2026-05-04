// frontend/src/pages/InteriorProjectV2.jsx
/**
 * Sprint 2: full takeoff workspace mount.
 *
 * URL: /project/:id/v2 — opt-in during Sprints 1-3, default at end of
 * Sprint 3, legacy /project/:id removed Sprint 4.
 *
 * Mounts:
 *   - TakeoffCanvas (Sprint 1 mip-pyramid renderer) with renderOverlay
 *   - GestureSurface — dispatches click + pointer events through
 *     G1..G5 hooks, all sharing the same z-index-2 surface
 *   - AnnotationLayer (z-index 3, pointer-events: none) — paints
 *     committed polygons / points / live preview
 *   - MiniKZPanel — Sprint 3 chrome stand-in; hosts G7 inline override
 *   - MemoryWatchdog (Sprint 1 carryover)
 *
 * Worker note: import pdfjs from react-pdf (4.8.69) rather than
 * standalone pdfjs-dist to avoid version drift. PdfViewer.jsx already
 * sets GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs' at module load;
 * we set it here too in case PdfViewer is tree-shaken into a different
 * chunk for this route.
 */
import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { pdfjs } from 'react-pdf';
import { useStore } from 'zustand';
import { getPdfBlob } from '../lib/pdfStore';
import { getProject } from '../lib/projectStore';
import { TakeoffCanvas } from '../components/canvas/TakeoffCanvas';
import { MemoryWatchdog } from '../components/canvas/MemoryWatchdog';
import { AnnotationLayer } from '../components/canvas/AnnotationLayer';
import { MiniKZPanel } from '../components/panels/MiniKZPanel';
import { tileCache } from '../lib/tileCache';
import { createSession } from '../lib/telemetry';
import { attachShortcuts } from '../lib/keyboardShortcuts';
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
  const [rooms, setRooms] = useState([]);
  const [pozicijos, setPozicijos] = useState([]);
  const [assumptions, setAssumptions] = useState({});
  const [committedPolygons, setCommittedPolygons] = useState([]);
  const [committedPoints, setCommittedPoints] = useState([]);
  const [preview, setPreview] = useState(null);
  const sessionRef = useRef(null);

  const setCurrentTool = useStore(viewerStore, (s) => s.setCurrentTool);

  const loadPdf = useCallback(async () => {
    try {
      const blob = await getPdfBlob(id);
      if (!blob) { setError('Brėžinys nerastas.'); return; }
      const buf = await blob.arrayBuffer();
      const doc = await pdfjs.getDocument({ data: buf }).promise;
      setPdfDoc(doc);
    } catch (err) { setError(`Nepavyko užkrauti PDF: ${err.message}`); }
  }, [id]);

  useEffect(() => { loadPdf(); }, [loadPdf]);

  // Load existing project state (rooms / pozicijos / assumptions) so MiniKZPanel
  // and gesture hooks have something to work with. Without this, KŽ panel shows
  // 0 pozicijos and G2/G3/G7 can't run (they need a selection target).
  useEffect(() => {
    const project = getProject(id);
    if (!project) return;
    if (Array.isArray(project.darbu_sarasas)) setPozicijos(project.darbu_sarasas);
    const projectRooms = project.raw_calc_data?.patalpos || project.v8_rooms || project.patalpos;
    if (Array.isArray(projectRooms)) setRooms(projectRooms);
    if (project.prielaidos) setAssumptions(project.prielaidos);
  }, [id]);

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

  const onRecomputed = useCallback((result) => {
    if (result.rooms) setRooms(result.rooms);
    if (result.pozicijos) setPozicijos(result.pozicijos);
    if (result.assumptions) setAssumptions(result.assumptions);
  }, []);

  const handleReset = useCallback(() => {
    pdfDoc?.destroy().catch(() => {});
    tileCache.clear();
    setPdfDoc(null);
    loadPdf();
  }, [pdfDoc, loadPdf]);

  if (error) return <div style={{ padding: 20, color: '#fff' }}>{error}</div>;
  if (!pdfDoc) return <div style={{ padding: 20, color: '#aaa' }}>Kraunamas brėžinys…</div>;

  return (
    <div style={{ width: '100vw', height: '100vh', background: '#0e1216', display: 'flex' }}>
      <MemoryWatchdog onReset={handleReset} />

      <div style={{ flex: 1, position: 'relative' }}>
        <TakeoffCanvas
          pdfDoc={pdfDoc}
          pageIdx={0}
          renderOverlay={({ canvasWidth, canvasHeight, canvasRef, containerRef }) => (
            <GestureSurface
              {...{
                projectId: id, pageIdx: 0,
                canvasWidth, canvasHeight, canvasRef, containerRef,
                rooms, pozicijos, currentAssumptions: assumptions,
                committedPolygons, committedPoints, preview,
                onPolygonAdded: (poly) => setCommittedPolygons((ps) => [...ps, poly]),
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

      <MiniKZPanel
        rooms={rooms}
        pozicijos={pozicijos}
        currentAssumptions={assumptions}
        onRecomputed={onRecomputed}
        onGestureEvent={recordGesture}
      />
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

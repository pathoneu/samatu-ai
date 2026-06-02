/**
 * /project/:id/annotator — orchestrator for the interactive PDF measurement
 * viewer. Owns app state (rooms, tool, scale, measurements, symbols,
 * calibration, verification, walkthrough). Delegates display to two
 * isolated components:
 *
 *   <PdfPage>            — react-pdf rendering only.
 *   <AnnotationCanvas>   — vanilla-canvas overlay with imperative ref API.
 *
 * The split honours docs/viewer-api.md: a future Fabric.js implementation
 * replaces AnnotationCanvas in place and the orchestrator is unchanged.
 */

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';

import PdfMultiPage from '@/components/annotator/PdfMultiPage';
import AnnotationCanvas, { SYMBOL_ICONS, TOOLS } from '@/components/annotator/AnnotationCanvas';
import ViewerToolbar from '@/components/annotator/ViewerToolbar';
import RoomDetailCard from '@/components/annotator/RoomDetailCard';
import MeasurementsList from '@/components/annotator/MeasurementsList';
import SymbolPalette from '@/components/annotator/SymbolPalette';
import VerifyWalkthrough from '@/components/annotator/VerifyWalkthrough';
import ScaleCalibrationWizard from '@/components/annotator/ScaleCalibrationWizard';
import useCommandStack from '@/hooks/useCommandStack';


export default function Annotator() {
  const { id: projectId } = useParams();
  const [searchParams] = useSearchParams();
  const fixture = searchParams.get('fixture');
  const pdfUrl = searchParams.get('pdf')
    || (fixture
        ? `/api/projects/${projectId}/pdf?fixture=${fixture}`
        : `/api/projects/${projectId}/pdf`);
  const initialPage = Number(searchParams.get('page') || 2);

  // ── PDF render state ─────────────────────────────────────────────────────
  const [numPages, setNumPages] = useState(0);
  const [pageNum, setPageNum] = useState(initialPage);   // legacy, used for scroll-to-page nav
  // Multi-page layout reported by PdfMultiPage:
  //   {pages: [{pageNum,width,height,offsetY}], totalWidth, totalHeight}
  const [pagesLayout, setPagesLayout] = useState({ pages: [], totalWidth: 0, totalHeight: 0 });
  const [loadError, setLoadError] = useState(null);
  // Backward-compat alias: a synthetic single-page dims for the wizard's
  // page-rendered gate. Use the first page's dims when available.
  const pageDims = pagesLayout.pages[0]
    ? { width: pagesLayout.pages[0].width, height: pagesLayout.pages[0].height }
    : { width: 0, height: 0 };

  // ── Tool + interaction ──────────────────────────────────────────────────
  const [tool, setTool] = useState(TOOLS.NONE);
  const [placeSymbolType, setPlaceSymbolType] = useState(null);

  // ── Scale ───────────────────────────────────────────────────────────────
  const [scale, setScale] = useState(null);

  // ── Drawing data ────────────────────────────────────────────────────────
  const [measurements, setMeasurements] = useState([]);
  const [symbols, setSymbols] = useState([]);

  // ── Zoom (synced PDF + canvas viewport) ─────────────────────────────────
  const [zoom, setZoom] = useState(1.0);
  const ZOOM_MIN = 0.25;
  const ZOOM_MAX = 4.0;

  // ── Undo/redo for measurements + symbols ─────────────────────────────────
  const cmdStack = useCommandStack({ bindKeys: true });

  // ── Bidirectional linking: selected measurement ──────────────────────────
  // When the user clicks a measurement row in the sidebar, this is set;
  // the canvas pulses the matching line. When the user clicks a
  // measurement directly on the canvas, the same state highlights the
  // sidebar row and scrolls it into view.
  const [selectedMeasurementId, setSelectedMeasurementId] = useState(null);

  // ── First-time scale calibration wizard ──────────────────────────────────
  // Shown on first project open with no saved scale. Once dismissed
  // (accept / draw / skip), never reopens until the user manually
  // clicks the toolbar Calibrate tool. localStorage gates re-opens
  // across reloads so the wizard isn't repetitive.
  const [scaleWizardOpen, setScaleWizardOpen] = useState(false);
  useEffect(() => {
    const key = `scale-wizard-dismissed:${projectId}`;
    const dismissed = localStorage.getItem(key);
    if (!dismissed && scale === null && pageDims.width > 0) {
      setScaleWizardOpen(true);
    }
  }, [projectId, scale, pageDims.width]);

  // ── Rooms (from /room-graph) + selection ────────────────────────────────
  const [rooms, setRooms] = useState([]);
  const [hoveredRoomNr, setHoveredRoomNr] = useState(null);
  const [selectedRoomNr, setSelectedRoomNr] = useState(null);
  const [pageScaleMmPerPct, setPageScaleMmPerPct] = useState(null);

  // ── Per-wall edit + verify walkthrough ──────────────────────────────────
  const [roomOverrides, setRoomOverrides] = useState({});
  const [verificationState, setVerificationState] = useState({});
  const [editingWall, setEditingWall] = useState(null);
  const [recalcedSantrauka, setRecalcedSantrauka] = useState(null);
  const [walkthroughActive, setWalkthroughActive] = useState(false);
  const [walkthroughIdx, setWalkthroughIdx] = useState(0);
  const roomsWithPolygons = useMemo(
    () => rooms.filter((r) => r.polygon_pct),
    [rooms],
  );

  // ── Persistence ─────────────────────────────────────────────────────────
  const [saveStatus, setSaveStatus] = useState(null);
  const [lastSavedAt, setLastSavedAt] = useState(null);

  // ── Calibration (contractor overrides) ──────────────────────────────────
  const [calibrationModalOpen, setCalibrationModalOpen] = useState(false);
  const [calibrationFactors, setCalibrationFactors] = useState({});
  const [calibrationOverrides, setCalibrationOverrides] = useState({});
  const [calibrationFetching, setCalibrationFetching] = useState(false);

  const canvasRef = useRef(null);

  // KŽ totals (rooms aggregation) for the calibration dialog
  const kzTotals = useMemo(() => {
    const sum = (field) => rooms.reduce((acc, r) => acc + (Number(r[field]) || 0), 0);
    return {
      dazymo_plotas_m2: Number(sum('dazymo_plotas_m2').toFixed(2)),
      walls_paintable_m2: Number(sum('walls_paintable_m2').toFixed(2)),
      ceiling_paintable_m2: Number(sum('ceiling_paintable_m2').toFixed(2)),
      floor_total_m2: Number(sum('area_m2').toFixed(2)),
    };
  }, [rooms]);

  // ── Effects: load rooms + calibration on mount ──────────────────────────
  useEffect(() => {
    const url = fixture
      ? `/api/projects/${projectId}/room-graph?fixture=${fixture}`
      : `/api/projects/${projectId}/room-graph`;
    fetch(url, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : Promise.reject(r.status))
      .then((j) => {
        setRooms(j.rooms || []);
        setPageScaleMmPerPct(j.page_scale_mm_per_pct);
      })
      .catch((e) => console.warn('room-graph fetch failed', e));
  }, [projectId, fixture]);

  useEffect(() => {
    if (scale !== null) return;
    if (pageScaleMmPerPct && pageDims.width > 0) {
      setScale(pageScaleMmPerPct / pageDims.width);
    }
  }, [pageScaleMmPerPct, pageDims, scale]);

  useEffect(() => {
    const url = `/api/projects/${projectId}/calibrate`;
    fetch(url, { credentials: 'include' })
      .then((r) => r.ok ? r.json() : null)
      .then((j) => {
        if (j && j.factors) {
          setCalibrationFactors(j.factors);
          setCalibrationOverrides(j.overrides || {});
        }
      })
      .catch(() => undefined);
  }, [projectId]);

  // ── Per-wall editing ───────────────────────────────────────────────────
  const recalcRoom = async (room_nr, walls) => {
    try {
      const url = fixture
        ? `/api/projects/${projectId}/rooms/${room_nr}/recalc?fixture=${fixture}`
        : `/api/projects/${projectId}/rooms/${room_nr}/recalc`;
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ walls }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setRooms((prev) => prev.map((rm) => rm.nr === room_nr ? {
        ...rm,
        perimeter_mm: j.room.perimetras_m * 1000,
        walls_paintable_m2: j.room.walls_paintable_m2,
        ceiling_paintable_m2: j.room.ceiling_paintable_m2,
        dazymo_plotas_m2: j.room.dazymo_plotas_m2,
      } : rm));
      setRecalcedSantrauka(j.new_santrauka);
    } catch (err) {
      console.error('room recalc failed', err);
    }
  };

  const startWallEdit = (room_nr, wall_id) => {
    const room = rooms.find((r) => r.nr === room_nr);
    if (!room || !room.polygon_pct) return;
    const poly = room.polygon_pct;
    const idx = parseInt(wall_id.replace(/[^0-9]/g, ''), 10) || 0;
    const p1 = poly[idx % poly.length];
    const p2 = poly[(idx + 1) % poly.length];
    setEditingWall({ room_nr, wall_id, p1_pct: p1, p2_pct: p2 });
    setTool(TOOLS.EDIT_WALL);
    setSelectedRoomNr(room_nr);
  };

  const commitWallEdit = async (room_nr, wall_id, length_mm) => {
    setRoomOverrides((prev) => {
      const next = { ...prev };
      const block = { walls: { ...(prev[room_nr]?.walls || {}) } };
      block.walls[wall_id] = length_mm;
      next[room_nr] = block;
      return next;
    });
    const room = rooms.find((r) => r.nr === room_nr);
    const overrides = { ...(roomOverrides[room_nr]?.walls || {}), [wall_id]: length_mm };
    const polyLen = room?.polygon_pct?.length || 4;
    const oldPerimMm = room?.perimeter_mm || 0;
    const avgWallMm = oldPerimMm / polyLen;
    const walls = [];
    for (let i = 0; i < polyLen; i++) {
      const wid = `w${i + 1}`;
      walls.push({ wall_id: wid, length_mm: overrides[wid] ?? avgWallMm });
    }
    setEditingWall(null);
    setTool(TOOLS.NONE);
    await recalcRoom(room_nr, walls);
  };

  const confirmRoom = (nr) => setVerificationState((p) => ({ ...p, [nr]: 'confirmed' }));
  const markCorrected = (nr) => setVerificationState((p) => ({ ...p, [nr]: 'corrected' }));

  // ── Symbol auto-detection ────────────────────────────────────────────────
  const [detecting, setDetecting] = useState(false);
  const handleDetectSymbols = async () => {
    setDetecting(true);
    try {
      const url = fixture
        ? `/api/projects/${projectId}/detect-symbols?fixture=${fixture}&page=5`
        : `/api/projects/${projectId}/detect-symbols?page=5`;
      const r = await fetch(url, { method: 'POST', credentials: 'include' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      const newSyms = (j.symbols || []).map((s) => ({
        id: `det-${s.id || Math.random().toString(36).slice(2, 7)}`,
        type: SYMBOL_ICONS[s.type] ? s.type : 'socket',
        pos_pct: { x_pct: s.x_pct, y_pct: s.y_pct },
      }));
      setSymbols((prev) => [...prev, ...newSyms]);
    } catch (err) {
      console.error(err);
      alert('Simbolių aptikimas nepavyko');
    } finally {
      setDetecting(false);
    }
  };

  // ── Persistence ──────────────────────────────────────────────────────────
  const annotationsUrl = `/api/projects/${projectId}/annotations`;
  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      const body = {
        measurements, symbols,
        scale_mm_per_px: scale,
        selected_room_nr: selectedRoomNr,
        page: pageNum,
        room_overrides: roomOverrides,
        verification_state: verificationState,
      };
      const r = await fetch(annotationsUrl, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setSaveStatus('saved');
      setLastSavedAt(j.updated_at);
    } catch (err) {
      console.error(err);
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
      if (Array.isArray(j.symbols)) setSymbols(j.symbols);
      if (typeof j.scale_mm_per_px === 'number') setScale(j.scale_mm_per_px);
      if (j.page) setPageNum(j.page);
      if (j.selected_room_nr) setSelectedRoomNr(j.selected_room_nr);
      if (j.room_overrides) setRoomOverrides(j.room_overrides);
      if (j.verification_state) setVerificationState(j.verification_state);
      setSaveStatus('saved');
      setLastSavedAt(j.updated_at);
    } catch (err) {
      console.error(err);
      setSaveStatus('error');
    }
  };

  // ── Calibration submit ───────────────────────────────────────────────────
  const submitCalibration = async (overrides) => {
    setCalibrationFetching(true);
    try {
      const url = fixture
        ? `/api/projects/${projectId}/calibrate?fixture=${fixture}`
        : `/api/projects/${projectId}/calibrate`;
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ overrides }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setCalibrationFactors(j.factors || {});
      setCalibrationOverrides(overrides);
      setCalibrationModalOpen(false);
    } catch (err) {
      console.error('calibration failed', err);
      alert('Kalibravimas nepavyko');
    } finally {
      setCalibrationFetching(false);
    }
  };

  // ── Selected room data ───────────────────────────────────────────────────
  const selectedRoom = useMemo(
    () => rooms.find((r) => r.nr === selectedRoomNr),
    [rooms, selectedRoomNr],
  );

  // ── Tool button helper ───────────────────────────────────────────────────
  const toolBtn = (id, label, glyph) => (
    <button
      type="button"
      key={id}
      onClick={() => {
        setTool(id);
        if (id !== TOOLS.PLACE_SYMBOL) setPlaceSymbolType(null);
        if (canvasRef.current) canvasRef.current.cancelDraft();
      }}
      className={`flex items-center gap-1.5 rounded border px-3 py-1.5 text-sm transition ${
        tool === id
          ? 'border-blue-500 bg-blue-50 text-blue-700'
          : 'border-neutral-300 bg-white text-neutral-700 hover:border-neutral-400'
      }`}
    >
      <span>{glyph}</span><span>{label}</span>
    </button>
  );

  // Excel export handler
  const handleExport = async () => {
    const url = fixture
      ? `/api/projects/${projectId}/export-excel?fixture=${fixture}`
      : `/api/projects/${projectId}/export-excel`;
    const r = await fetch(url, { method: 'POST', credentials: 'include' });
    if (!r.ok) {
      setSaveStatus('error');
      return;
    }
    const blob = await r.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `samata-${projectId}.xlsx`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  // Tool change wrapper (cancels in-progress draft)
  const setToolSafe = (id) => {
    setTool(id);
    if (id !== TOOLS.PLACE_SYMBOL) setPlaceSymbolType(null);
    if (canvasRef.current) canvasRef.current.cancelDraft();
  };

  const startVerifyAll = () => {
    setWalkthroughActive(true);
    setWalkthroughIdx(0);
    if (roomsWithPolygons[0]) setSelectedRoomNr(roomsWithPolygons[0].nr);
  };

  return (
    <div className="flex h-screen flex-col bg-neutral-100">
      {/* Professional toolbar */}
      <ViewerToolbar
        tool={tool}
        setTool={setToolSafe}
        onUndo={cmdStack.undo}
        onRedo={cmdStack.redo}
        canUndo={cmdStack.canUndo}
        canRedo={cmdStack.canRedo}
        onSave={handleSave}
        onLoad={handleLoad}
        onExport={handleExport}
        onCalibrateModal={() => setCalibrationModalOpen(true)}
        onDetectSymbols={handleDetectSymbols}
        detectingSymbols={detecting}
        onVerifyAll={startVerifyAll}
        walkthroughActive={walkthroughActive}
        saveStatus={saveStatus}
        scale={scale}
        zoom={zoom}
        onZoom={(action) => {
          if (action === 'in') setZoom((z) => Math.min(ZOOM_MAX, z * 1.25));
          else if (action === 'out') setZoom((z) => Math.max(ZOOM_MIN, z / 1.25));
          else setZoom(1);
        }}
        pageNum={pageNum}
        numPages={numPages}
        onPageChange={(n) => {
          setPageNum(n);
          // Scroll the corresponding page into the viewport
          const el = document.querySelector(`[data-testid="pdf-page-${n}"]`);
          if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }}
        measurementsCount={measurements.length}
        symbolsCount={symbols.length}
      />

      {/* Symbol palette — visible during NONE and PLACE_SYMBOL tools */}
      {(tool === TOOLS.NONE || tool === TOOLS.PLACE_SYMBOL) && (
        <SymbolPalette
          symbols={symbols}
          activeType={placeSymbolType}
          onSelectType={(type) => {
            setTool(TOOLS.PLACE_SYMBOL);
            setPlaceSymbolType(type);
          }}
        />
      )}

      {loadError && (
        <div className="bg-red-50 border-y border-red-200 px-4 py-2 text-sm text-red-700">
          PDF įkėlimo klaida: {loadError}
        </div>
      )}

      {/* Body — main is the scrollable infinite-canvas viewport */}
      <div className="flex flex-1 overflow-hidden">
        <main
          data-testid="viewer-scroll-container"
          className="flex flex-1 items-start justify-center overflow-auto p-4"
        >
          <div className="relative inline-block">
            <PdfMultiPage
              file={pdfUrl}
              zoom={zoom}
              onNumPages={setNumPages}
              onPagesLayout={setPagesLayout}
              onLoadError={(err) => setLoadError(err?.message || String(err))}
            />
            <AnnotationCanvas
              ref={canvasRef}
              pagesLayout={pagesLayout}
              tool={tool}
              scale={scale}
              rooms={rooms}
              measurements={measurements}
              symbols={symbols}
              placeSymbolType={placeSymbolType}
              selectedRoomNr={selectedRoomNr}
              hoveredRoomNr={hoveredRoomNr}
              editingWall={editingWall}
              selectedMeasurementId={selectedMeasurementId}
              zoom={zoom}
              onWheel={(e) => {
                // Ctrl/Cmd + wheel zooms; bare wheel scrolls (default).
                if (!(e.ctrlKey || e.metaKey)) return;
                e.preventDefault();
                const delta = e.deltaY < 0 ? 1.1 : 1 / 1.1;
                setZoom((z) => Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, z * delta)));
              }}
              onCalibrationComplete={setScale}
              onMeasurementComplete={(m) => {
                const id = `m-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
                const next = { id, ...m };
                setMeasurements((prev) => [...prev, next]);
                cmdStack.push({
                  label: `Pridėtas matavimas ${next.length_mm.toFixed(0)} mm`,
                  do:   () => setMeasurements((prev) => [...prev, next]),
                  undo: () => setMeasurements((prev) => prev.filter((x) => x.id !== id)),
                });
              }}
              onSymbolPlaced={(s) => {
                const id = `sym-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
                const next = { id, ...s };
                setSymbols((prev) => [...prev, next]);
                cmdStack.push({
                  label: `Pridėtas simbolis ${s.type}`,
                  do:   () => setSymbols((prev) => [...prev, next]),
                  undo: () => setSymbols((prev) => prev.filter((x) => x.id !== id)),
                });
              }}
              onSymbolDeleted={(id) => {
                const removed = symbols.find((s) => s.id === id);
                setSymbols((prev) => prev.filter((s) => s.id !== id));
                if (removed) {
                  cmdStack.push({
                    label: `Ištrintas simbolis`,
                    do:   () => setSymbols((prev) => prev.filter((s) => s.id !== id)),
                    undo: () => setSymbols((prev) => [...prev, removed]),
                  });
                }
              }}
              onSymbolMoved={(id, pos_pct) =>
                setSymbols((prev) => prev.map((s) => s.id === id ? { ...s, pos_pct } : s))}
              onRoomClick={(nr) => {
                setSelectedRoomNr(nr);
                if (nr) {
                  const el = document.getElementById(`room-row-${nr}`);
                  el && el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
              }}
              onRoomHover={setHoveredRoomNr}
              onWallEditComplete={commitWallEdit}
              onMeasurementClick={(id) => setSelectedMeasurementId(id)}
            />
          </div>
        </main>

        {/* Walkthrough overlay */}
        {walkthroughActive && (
          <VerifyWalkthrough
            rooms={roomsWithPolygons}
            currentIdx={walkthroughIdx}
            verificationState={verificationState}
            onConfirm={(nr) => {
              confirmRoom(nr);
              // Advance: same logic as the inline version
              const total = roomsWithPolygons.length;
              if (walkthroughIdx + 1 >= total) {
                setWalkthroughActive(false);
                return;
              }
              const nextIdx = walkthroughIdx + 1;
              setWalkthroughIdx(nextIdx);
              setSelectedRoomNr(roomsWithPolygons[nextIdx].nr);
            }}
            onCorrect={(nr) => markCorrected(nr)}
            onAdvance={() => {
              const total = roomsWithPolygons.length;
              if (walkthroughIdx + 1 >= total) {
                setWalkthroughActive(false);
                return;
              }
              const nextIdx = walkthroughIdx + 1;
              setWalkthroughIdx(nextIdx);
              setSelectedRoomNr(roomsWithPolygons[nextIdx].nr);
            }}
            onStop={() => setWalkthroughActive(false)}
          />
        )}

        {/* Calibration modal (per-category override) */}
        {calibrationModalOpen && (
          <CalibrationModal
            initialAi={kzTotals}
            initialOverrides={calibrationOverrides}
            onCancel={() => setCalibrationModalOpen(false)}
            onSubmit={submitCalibration}
            busy={calibrationFetching}
          />
        )}

        {/* First-time scale calibration wizard */}
        {scaleWizardOpen && (
          <ScaleCalibrationWizard
            aiScale={pageScaleMmPerPct && pageDims.width
              ? pageScaleMmPerPct / pageDims.width
              : null}
            onAccept={(s) => {
              setScale(s);
              setScaleWizardOpen(false);
              localStorage.setItem(`scale-wizard-dismissed:${projectId}`, '1');
            }}
            onDrawLine={() => {
              setTool(TOOLS.CALIBRATE);
              setScaleWizardOpen(false);
              localStorage.setItem(`scale-wizard-dismissed:${projectId}`, '1');
            }}
            onSkip={() => {
              setScaleWizardOpen(false);
              localStorage.setItem(`scale-wizard-dismissed:${projectId}`, '1');
            }}
          />
        )}

        {/* Sidebar */}
        <aside className="flex w-[36%] min-w-[320px] flex-col border-l border-neutral-200 bg-neutral-50">
          {/* KŽ summary */}
          <section className="border-b border-neutral-200 bg-white px-4 py-3">
            <div className="mb-1 flex items-center justify-between">
              <div className="text-xs font-medium uppercase text-neutral-500">KŽ santrauka</div>
              {Object.keys(calibrationFactors).length > 0 && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">⚖ Kalibruota</span>
              )}
            </div>
            <table className="w-full text-sm">
              <thead><tr className="text-xs text-neutral-500">
                <th className="text-left">Kategorija</th>
                <th className="text-right">AI</th>
                <th className="text-right">Jūsų</th>
              </tr></thead>
              <tbody>
                {[
                  ['dazymo_plotas_m2',     'Dažymo plotas', kzTotals.dazymo_plotas_m2,     'm²'],
                  ['walls_paintable_m2',   'Sienos',         kzTotals.walls_paintable_m2,   'm²'],
                  ['ceiling_paintable_m2', 'Lubos',          kzTotals.ceiling_paintable_m2, 'm²'],
                  ['floor_total_m2',       'Plotas',         kzTotals.floor_total_m2,       'm²'],
                ].map(([key, label, ai, unit]) => {
                  const override = calibrationOverrides[key];
                  const factor = calibrationFactors[key]?.factor;
                  const calibrated = (override !== undefined)
                    ? override
                    : (factor ? ai * factor : null);
                  return (
                    <tr key={key} className="border-t border-neutral-100">
                      <td className="py-1 text-neutral-700">{label}</td>
                      <td className="py-1 text-right font-mono text-neutral-600">{ai.toFixed(2)} {unit}</td>
                      <td className="py-1 text-right font-mono font-semibold text-amber-700">
                        {calibrated !== null && calibrated !== undefined ? `${calibrated.toFixed(2)} ${unit}` : '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <button
              type="button"
              onClick={() => setCalibrationModalOpen(true)}
              className="mt-2 w-full rounded border border-amber-300 bg-amber-50 py-1.5 text-sm text-amber-700 hover:bg-amber-100"
            >⚖ Kalibruoti pagal mano sumas</button>
          </section>

          {/* Selected room card + per-wall edit */}
          <RoomDetailCard
            room={selectedRoom}
            verificationState={verificationState}
            roomOverrides={roomOverrides}
            scale={scale}
            onConfirm={confirmRoom}
            onMarkCorrected={markCorrected}
            onStartWallEdit={startWallEdit}
          />

          {/* Rooms list */}
          <section className="border-b border-neutral-200">
            <header className="px-4 py-2 text-xs font-medium uppercase text-neutral-500">
              Patalpos ({rooms.length})
            </header>
            <ul className="max-h-72 overflow-auto text-sm">
              {rooms.map((r) => (
                <li
                  key={r.nr}
                  id={`room-row-${r.nr}`}
                  onClick={() => setSelectedRoomNr(r.nr)}
                  onMouseEnter={() => setHoveredRoomNr(r.nr)}
                  onMouseLeave={() => setHoveredRoomNr(null)}
                  className={`flex cursor-pointer items-center justify-between gap-2 border-b border-neutral-100 px-4 py-1.5 ${
                    r.nr === selectedRoomNr ? 'bg-blue-100' : 'hover:bg-neutral-100'
                  }`}
                >
                  <span className="font-mono text-xs text-neutral-500">{r.nr}</span>
                  <span className="flex-1 truncate text-neutral-800">{r.name}</span>
                  <span className="text-xs text-neutral-500">{r.area_m2.toFixed(1)} m²</span>
                  {!r.polygon_pct && (
                    <span title="No polygon — sidebar-only room" className="text-xs text-amber-600">⚠</span>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {/* Measurements list (with bidirectional canvas linking) */}
          <MeasurementsList
            measurements={measurements}
            selectedId={selectedMeasurementId}
            onSelect={setSelectedMeasurementId}
            onDelete={(id) => {
              setMeasurements((prev) => prev.filter((x) => x.id !== id));
              if (selectedMeasurementId === id) setSelectedMeasurementId(null);
            }}
            onClearAll={() => {
              setMeasurements([]);
              setSelectedMeasurementId(null);
            }}
          />
        </aside>
      </div>

      {/* Status bar */}
      <footer className="border-t border-neutral-200 bg-white px-4 py-1.5 text-xs text-neutral-500">
        Įrankis: <strong>{tool}</strong>
        {' · '}Snap: 20px
        {' · '}Patalpos su poligonais: <strong>{rooms.filter((r) => r.polygon_pct).length}/{rooms.length}</strong>
        {pageScaleMmPerPct && <> {' · '}Aptiktas mastelis: {pageScaleMmPerPct.toFixed(0)} mm/pct</>}
      </footer>
    </div>
  );
}


// ─── Calibration modal ─────────────────────────────────────────────────────
const CALIBRATION_FIELDS = [
  { key: 'dazymo_plotas_m2',     label: 'Dažymo plotas',       unit: 'm²' },
  { key: 'plyteles_sienose_m2',  label: 'Plytelės sienose',    unit: 'm²' },
  { key: 'plyteles_grindyse_m2', label: 'Plytelės grindyse',   unit: 'm²' },
  { key: 'angokrasciai_m',       label: 'Angokraščiai',        unit: 'm'  },
  { key: 'kampu_metrai_m',       label: 'Dažymo kampai',       unit: 'm'  },
  { key: 'led_nisos_m',          label: 'LED nišų ilgis',      unit: 'm'  },
  { key: 'gkp_lubu_iki_3m_m2',   label: 'GKP lubos iki 3m',    unit: 'm²' },
];

function CalibrationModal({ initialAi, initialOverrides, onCancel, onSubmit, busy }) {
  const [values, setValues] = React.useState(() => {
    const out = {};
    for (const f of CALIBRATION_FIELDS) {
      out[f.key] = initialOverrides[f.key] ?? '';
    }
    return out;
  });
  const handleSubmit = (e) => {
    e.preventDefault();
    const overrides = {};
    for (const [k, v] of Object.entries(values)) {
      const n = parseFloat(v);
      if (Number.isFinite(n) && n > 0) overrides[k] = n;
    }
    if (Object.keys(overrides).length === 0) {
      alert('Įveskite bent vieną kategoriją.');
      return;
    }
    onSubmit(overrides);
  };
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onCancel}
    >
      <div
        className="w-[520px] max-w-[90vw] rounded-lg bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-1 text-lg font-semibold text-neutral-800">Kalibruoti pagal jūsų sumas</h2>
        <p className="mb-4 text-sm text-neutral-500">
          Įveskite jums žinomas sumas kategorijoms, kurias norite pakoreguoti.
          Sistema saugos koregavimo koeficientus tik šiam projektui — bendra
          AI formulė lieka nepakitusi.
        </p>
        <form onSubmit={handleSubmit} className="space-y-2">
          {CALIBRATION_FIELDS.map((f) => (
            <div key={f.key} className="flex items-center gap-3">
              <label className="flex-1 text-sm text-neutral-700">
                {f.label}
                <span className="ml-2 text-xs text-neutral-400">
                  {f.key in initialAi && `AI: ${initialAi[f.key].toFixed(2)} ${f.unit}`}
                </span>
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                value={values[f.key]}
                onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                placeholder={`mano ${f.unit}`}
                className="w-28 rounded border border-neutral-300 px-2 py-1 text-right font-mono text-sm"
              />
              <span className="w-8 text-xs text-neutral-400">{f.unit}</span>
            </div>
          ))}
          <div className="mt-4 flex justify-end gap-2">
            <button type="button" onClick={onCancel}
              className="rounded border border-neutral-300 px-4 py-1.5 text-sm">Atšaukti</button>
            <button type="submit" disabled={busy}
              className="rounded border border-amber-500 bg-amber-500 px-4 py-1.5 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50">
              {busy ? 'Saugoma…' : 'Kalibruoti'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

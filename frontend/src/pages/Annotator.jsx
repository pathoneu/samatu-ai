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
import { toast } from 'sonner';
import { useParams, useSearchParams } from 'react-router';

import PdfPage from '@/components/annotator/PdfPage';
import AnnotationCanvas, { SYMBOL_ICONS, TOOLS } from '@/components/annotator/AnnotationCanvas';


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
  const [pageNum, setPageNum] = useState(initialPage);
  const [pageDims, setPageDims] = useState({ width: 0, height: 0 });
  const [loadError, setLoadError] = useState(null);

  // ── Tool + interaction ──────────────────────────────────────────────────
  const [tool, setTool] = useState(TOOLS.NONE);
  const [placeSymbolType, setPlaceSymbolType] = useState(null);

  // ── Scale ───────────────────────────────────────────────────────────────
  const [scale, setScale] = useState(null);

  // ── Drawing data ────────────────────────────────────────────────────────
  const [measurements, setMeasurements] = useState([]);
  const [symbols, setSymbols] = useState([]);

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

  // (Vision symbol auto-detection — POST …/detect-symbols — is gone, v4 3b 2026-10-25.)

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
      toast.error('Kalibravimas nepavyko');
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
          ? 'border-blue-500 bg-blue-500/10 text-blue-300'
          : 'border-border bg-card text-foreground hover:border-primary/40'
      }`}
    >
      <span>{glyph}</span><span>{label}</span>
    </button>
  );

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-card px-4 py-2 text-sm">
        <strong className="mr-3 text-foreground">Matavimas</strong>
        {toolBtn(TOOLS.NONE,      'Pasirinkti', '🖱')}
        {toolBtn(TOOLS.CALIBRATE, 'Kalibruoti', '🔍')}
        {toolBtn(TOOLS.MEASURE,   'Matuoti',    '📏')}
        <span className="mx-2 text-muted-foreground/70">|</span>
        <button
          type="button"
          onClick={() => {
            setWalkthroughActive(true);
            setWalkthroughIdx(0);
            if (roomsWithPolygons[0]) setSelectedRoomNr(roomsWithPolygons[0].nr);
          }}
          disabled={roomsWithPolygons.length === 0}
          className="rounded border border-sky-500 bg-sky-500/10 px-3 py-1.5 text-sky-300"
          title="Praeiti per visus kambarius ir patvirtinti / pakoreguoti"
        >🚶 Tikrinti kambarius</button>
        <button
          type="button"
          onClick={() => setCalibrationModalOpen(true)}
          className="rounded border border-amber-500 bg-amber-500/10 px-3 py-1.5 text-amber-300"
          title="Kalibruoti AI sumas pagal jūsų žinomus skaičius"
        >⚖ Kalibruoti</button>
        <button
          type="button"
          onClick={async () => {
            const url = fixture
              ? `/api/projects/${projectId}/export-excel?fixture=${fixture}`
              : `/api/projects/${projectId}/export-excel`;
            const r = await fetch(url, { method: 'POST', credentials: 'include' });
            if (!r.ok) return toast.error('Eksportavimas nepavyko');
            const blob = await r.blob();
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `samata-${projectId}.xlsx`;
            a.click();
            URL.revokeObjectURL(a.href);
          }}
          className="rounded border border-green-600 bg-green-500/10 px-3 py-1.5 text-emerald-300"
          title="Eksportuoti KŽ į Excel"
        >📊 Eksportuoti</button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saveStatus === 'saving'}
          className="rounded border border-emerald-500 bg-emerald-500/10 px-3 py-1.5 text-emerald-300"
        >💾 Įrašyti</button>
        <button
          type="button"
          onClick={handleLoad}
          disabled={saveStatus === 'saving'}
          className="rounded border border-border bg-card px-3 py-1.5 text-foreground"
        >↺ Atkurti</button>
        <span className="text-xs text-muted-foreground">
          {saveStatus === 'saving' && '⏳'}
          {saveStatus === 'saved' && lastSavedAt && `✓ ${new Date(lastSavedAt * 1000).toLocaleTimeString('lt-LT')}`}
          {saveStatus === 'error' && '⚠ klaida'}
        </span>
        <span className="ml-auto text-muted-foreground">
          Mastelis: <strong>{scale ? `1 mm = ${(1 / scale).toFixed(2)} px` : 'nekalibruota'}</strong>
          {' · '}
          Matavimai: <strong>{measurements.length}</strong>
          {' · '}
          Simboliai: <strong>{symbols.length}</strong>
          {' · '}
          Puslapis {pageNum}/{numPages || '?'}
        </span>
      </div>

      {/* Symbol palette — when no other tool active */}
      {(tool === TOOLS.NONE || tool === TOOLS.PLACE_SYMBOL) && (
        <div className="flex items-center gap-2 border-b border-border bg-card px-4 py-1.5 text-xs">
          <span className="text-muted-foreground">Simboliai:</span>
          {Object.entries(SYMBOL_ICONS).map(([type, meta]) => (
            <button
              key={type}
              type="button"
              onClick={() => {
                setTool(TOOLS.PLACE_SYMBOL);
                setPlaceSymbolType(type);
              }}
              className={`flex items-center gap-1.5 rounded border px-2 py-1 ${
                placeSymbolType === type
                  ? 'border-purple-500 bg-purple-500/10 text-purple-300'
                  : 'border-border bg-card text-foreground hover:border-primary/40'
              }`}
              style={{ borderLeftWidth: 4, borderLeftColor: meta.color }}
            >
              <span>{meta.glyph}</span>{meta.label}
            </button>
          ))}
          <span className="ml-2 text-muted-foreground/70">
            Dešinysis pelės klavišas = ištrinti.  Vilkti = perkelti.
          </span>
        </div>
      )}

      {loadError && (
        <div className="bg-red-500/10 border-y border-red-300 px-4 py-2 text-sm text-red-300">
          PDF įkėlimo klaida: {loadError}
        </div>
      )}

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-1 items-start justify-center overflow-auto p-4">
          <div className="relative inline-block bg-white shadow">
            <PdfPage
              file={pdfUrl}
              pageNumber={pageNum}
              onNumPages={setNumPages}
              onPageDims={setPageDims}
              onLoadError={(err) => setLoadError(err?.message || String(err))}
            />
            <AnnotationCanvas
              ref={canvasRef}
              pageDims={pageDims}
              tool={tool}
              scale={scale}
              rooms={rooms}
              measurements={measurements}
              symbols={symbols}
              placeSymbolType={placeSymbolType}
              selectedRoomNr={selectedRoomNr}
              hoveredRoomNr={hoveredRoomNr}
              editingWall={editingWall}
              onCalibrationComplete={setScale}
              onMeasurementComplete={(m) =>
                setMeasurements((prev) => [...prev, {
                  id: `m-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
                  ...m,
                }])}
              onSymbolPlaced={(s) =>
                setSymbols((prev) => [...prev, {
                  id: `sym-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
                  ...s,
                }])}
              onSymbolDeleted={(id) =>
                setSymbols((prev) => prev.filter((s) => s.id !== id))}
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
            />
          </div>
        </main>

        {/* Walkthrough overlay */}
        {walkthroughActive && roomsWithPolygons[walkthroughIdx] && (() => {
          const current = roomsWithPolygons[walkthroughIdx];
          const total = roomsWithPolygons.length;
          const confirmed = Object.values(verificationState).filter((v) => v === 'confirmed').length;
          const corrected = Object.values(verificationState).filter((v) => v === 'corrected').length;
          const advance = () => {
            if (walkthroughIdx + 1 >= total) {
              setWalkthroughActive(false);
              toast(`Patvirtinta: ${confirmed}, Pakoreguota: ${corrected}, Iš viso: ${total}`);
              return;
            }
            const nextIdx = walkthroughIdx + 1;
            setWalkthroughIdx(nextIdx);
            setSelectedRoomNr(roomsWithPolygons[nextIdx].nr);
          };
          return (
            <div className="absolute right-4 top-32 z-40 w-80 rounded-lg border border-sky-300 bg-card p-4 shadow-2xl">
              <div className="mb-1 text-xs uppercase text-sky-300">
                Tikrinimas {walkthroughIdx + 1} / {total}
              </div>
              <div className="text-base font-semibold text-foreground">
                {current.nr} {current.name}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div>Plotas: <strong>{current.area_m2.toFixed(2)} m²</strong></div>
                <div>Perim.: <strong>{(current.perimeter_mm / 1000).toFixed(2)} m</strong></div>
                <div>H: <strong>{current.ceiling_height_m.toFixed(2)} m</strong></div>
                <div>Dažym.: <strong>{current.dazymo_plotas_m2.toFixed(1)} m²</strong></div>
              </div>
              <p className="mt-3 text-sm font-medium text-foreground">
                Ar AI matmenys teisingi?
              </p>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => { confirmRoom(current.nr); advance(); }}
                  className="flex-1 rounded border border-emerald-500 bg-emerald-500/10 px-2 py-1.5 text-sm text-emerald-300"
                >✓ Taip</button>
                <button
                  type="button"
                  onClick={() => markCorrected(current.nr)}
                  className="flex-1 rounded border border-amber-500 bg-amber-500/10 px-2 py-1.5 text-sm text-amber-300"
                  title="Pakoreguokite sienas dešinėje, tada Toliau"
                >✎ Koreguoti</button>
              </div>
              <div className="mt-2 flex gap-2 text-xs">
                <button
                  type="button"
                  onClick={advance}
                  className="flex-1 rounded border border-border px-2 py-1 text-muted-foreground"
                >→ Toliau</button>
                <button
                  type="button"
                  onClick={() => setWalkthroughActive(false)}
                  className="rounded border border-border px-2 py-1 text-muted-foreground"
                >Nutraukti</button>
              </div>
              <div className="mt-2 text-xs text-muted-foreground/70">
                ✓ {confirmed}  ·  ✎ {corrected}  ·  liko {total - walkthroughIdx - 1}
              </div>
            </div>
          );
        })()}

        {/* Calibration modal */}
        {calibrationModalOpen && (
          <CalibrationModal
            initialAi={kzTotals}
            initialOverrides={calibrationOverrides}
            onCancel={() => setCalibrationModalOpen(false)}
            onSubmit={submitCalibration}
            busy={calibrationFetching}
          />
        )}

        {/* Sidebar */}
        <aside className="flex w-[36%] min-w-[320px] flex-col border-l border-border bg-card">
          {/* KŽ summary */}
          <section className="border-b border-border bg-card px-4 py-3">
            <div className="mb-1 flex items-center justify-between">
              <div className="text-xs font-medium uppercase text-muted-foreground">KŽ santrauka</div>
              {Object.keys(calibrationFactors).length > 0 && (
                <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">⚖ Kalibruota</span>
              )}
            </div>
            <table className="w-full text-sm">
              <thead><tr className="text-xs text-muted-foreground">
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
                    <tr key={key} className="border-t border-border">
                      <td className="py-1 text-foreground">{label}</td>
                      <td className="py-1 text-right font-mono text-muted-foreground">{ai.toFixed(2)} {unit}</td>
                      <td className="py-1 text-right font-mono font-semibold text-amber-300">
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
              className="mt-2 w-full rounded border border-amber-300 bg-amber-500/10 py-1.5 text-sm text-amber-300 hover:bg-amber-500/20"
            >⚖ Kalibruoti pagal mano sumas</button>
          </section>

          {/* Selected room card + per-wall edit */}
          {selectedRoom && (
            <section className="border-b border-border bg-blue-500/10 px-4 py-3">
              <div className="mb-1 flex items-center justify-between">
                <div className="text-xs font-medium uppercase text-muted-foreground">Pasirinkta patalpa</div>
                {verificationState[selectedRoom.nr] === 'confirmed' && (
                  <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-300">✓ Patvirtinta</span>
                )}
                {verificationState[selectedRoom.nr] === 'corrected' && (
                  <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-300">✎ Pakoreguota</span>
                )}
              </div>
              <div className="text-base font-semibold text-foreground">
                {selectedRoom.nr} {selectedRoom.name}
              </div>
              <div className="mt-1 grid grid-cols-3 gap-2 text-xs">
                <div><span className="text-muted-foreground">Plotas: </span><strong>{selectedRoom.area_m2.toFixed(2)} m²</strong></div>
                <div><span className="text-muted-foreground">Perimetras: </span><strong>{(selectedRoom.perimeter_mm / 1000).toFixed(2)} m</strong></div>
                <div><span className="text-muted-foreground">H: </span><strong>{selectedRoom.ceiling_height_m.toFixed(2)} m</strong></div>
                <div><span className="text-muted-foreground">Sienos dažomos: </span><strong>{selectedRoom.walls_paintable_m2.toFixed(1)} m²</strong></div>
                <div><span className="text-muted-foreground">Lubos: </span><strong>{selectedRoom.ceiling_paintable_m2.toFixed(1)} m²</strong></div>
                <div><span className="text-muted-foreground">Σ dažymas: </span><strong>{selectedRoom.dazymo_plotas_m2.toFixed(1)} m²</strong></div>
              </div>
              {selectedRoom.polygon_pct && (
                <div className="mt-3">
                  <div className="mb-1 text-xs font-medium text-muted-foreground">Sienos</div>
                  <ul className="space-y-1">
                    {selectedRoom.polygon_pct.map((_, idx) => {
                      const wallId = `w${idx + 1}`;
                      const override = roomOverrides[selectedRoom.nr]?.walls?.[wallId];
                      const aiLen = (selectedRoom.perimeter_mm / selectedRoom.polygon_pct.length / 1000).toFixed(2);
                      return (
                        <li key={wallId} className="flex items-center gap-2 text-xs">
                          <span className="w-8 font-mono text-muted-foreground">{wallId}</span>
                          <span className="flex-1">
                            AI: {aiLen} m
                            {override !== undefined && (
                              <span className="ml-2 font-mono font-semibold text-amber-300">
                                → {(override / 1000).toFixed(2)} m
                              </span>
                            )}
                          </span>
                          <button
                            type="button"
                            onClick={() => startWallEdit(selectedRoom.nr, wallId)}
                            disabled={!scale}
                            title={scale ? 'Pertaškyti sieną' : 'Pirmiausia kalibruokite'}
                            className="rounded border border-blue-300 bg-card px-2 py-0.5 text-blue-300 hover:border-blue-500"
                          >✎ Pertaškyti</button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => confirmRoom(selectedRoom.nr)}
                  className="flex-1 rounded border border-emerald-500 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300"
                >✓ Patvirtinti</button>
                <button
                  type="button"
                  onClick={() => markCorrected(selectedRoom.nr)}
                  className="flex-1 rounded border border-amber-500 bg-amber-500/10 px-2 py-1 text-xs text-amber-300"
                >✎ Pakoregavau</button>
              </div>
            </section>
          )}

          {/* Rooms list */}
          <section className="border-b border-border">
            <header className="px-4 py-2 text-xs font-medium uppercase text-muted-foreground">
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
                  className={`flex cursor-pointer items-center justify-between gap-2 border-b border-border px-4 py-1.5 ${
                    r.nr === selectedRoomNr ? 'bg-blue-500/20' : 'hover:bg-muted'
                  }`}
                >
                  <span className="font-mono text-xs text-muted-foreground">{r.nr}</span>
                  <span className="flex-1 truncate text-foreground">{r.name}</span>
                  <span className="text-xs text-muted-foreground">{r.area_m2.toFixed(1)} m²</span>
                  {!r.polygon_pct && (
                    <span title="No polygon — sidebar-only room" className="text-xs text-amber-600">⚠</span>
                  )}
                </li>
              ))}
            </ul>
          </section>

          {/* Measurements */}
          <section className="flex-1 overflow-auto">
            <header className="flex items-center justify-between px-4 py-2 text-xs font-medium uppercase text-muted-foreground">
              <span>Matavimai ({measurements.length})</span>
              {measurements.length > 0 && (
                <button
                  onClick={() => setMeasurements([])}
                  className="rounded border border-border px-2 py-0.5 text-xs"
                >Išvalyti</button>
              )}
            </header>
            <ul className="text-sm">
              {measurements.map((m, i) => (
                <li key={m.id} className="flex items-center justify-between gap-2 border-b border-border px-4 py-1.5">
                  <span className="text-muted-foreground">#{i + 1}</span>
                  <span className="font-mono text-blue-300">{m.length_mm.toFixed(1)} mm</span>
                  <button
                    onClick={() => setMeasurements((prev) => prev.filter((x) => x.id !== m.id))}
                    className="rounded border border-border px-2 py-0.5 text-xs text-muted-foreground"
                  >Trinti</button>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      {/* Status bar */}
      <footer className="border-t border-border bg-card px-4 py-1.5 text-xs text-muted-foreground">
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
      toast.error('Įveskite bent vieną kategoriją.');
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
        className="w-[520px] max-w-[90vw] rounded-lg bg-card p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-1 text-lg font-semibold text-foreground">Kalibruoti pagal jūsų sumas</h2>
        <p className="mb-4 text-sm text-muted-foreground">
          Įveskite jums žinomas sumas kategorijoms, kurias norite pakoreguoti.
          Sistema saugos koregavimo koeficientus tik šiam projektui — bendra
          AI formulė lieka nepakitusi.
        </p>
        <form onSubmit={handleSubmit} className="space-y-2">
          {CALIBRATION_FIELDS.map((f) => (
            <div key={f.key} className="flex items-center gap-3">
              <label className="flex-1 text-sm text-foreground">
                {f.label}
                <span className="ml-2 text-xs text-muted-foreground/70">
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
                className="w-28 rounded border border-border bg-card px-2 py-1 text-right font-mono text-sm text-foreground"
              />
              <span className="w-8 text-xs text-muted-foreground/70">{f.unit}</span>
            </div>
          ))}
          <div className="mt-4 flex justify-end gap-2">
            <button type="button" onClick={onCancel}
              className="rounded border border-border px-4 py-1.5 text-sm text-foreground">Atšaukti</button>
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

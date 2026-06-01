/**
 * /project/:id/annotator — interactive PDF measurement viewer (Togal-style MVP).
 *
 * Features (all in LT):
 *   • Calibration (manual + detected scale from backend; instant recalibrate).
 *   • Snapping measurement tool — snaps endpoints to room corners within
 *     SNAP_PX of the cursor. Shows snap circle + live mm label.
 *   • Magic-wand polygons — semi-transparent fills over each room; hover
 *     highlights; click selects + scrolls sidebar; sidebar row click selects
 *     the room.
 *   • Symbol layer — palette with 6 LT-construction icons (rozetė, jungtukas,
 *     šviestuvas, difūzorius, vandens taškas, internetas); click palette →
 *     placement mode; click canvas to drop; drag to move; right-click to
 *     delete.
 *   • Persistence — Save / Load via /api/projects/:id/annotations. Payload
 *     keeps coords in PCT (fractions of page) so they survive resize.
 *
 * No fabric.js / pixi dep — vanilla canvas overlay. Clean redraw from React
 * state on every change keeps the implementation simple and predictable.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Document, Page, pdfjs } from 'react-pdf';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

const TOOLS = {
  NONE: 'none',
  CALIBRATE: 'calibrate',
  MEASURE: 'measure',
  PLACE_SYMBOL: 'place_symbol',
  EDIT_WALL: 'edit_wall',           // wall-edit mode: redraw a specific wall's length
};

const SNAP_PX = 20;

// LT construction icon set — simple SVG paths, all 24×24, currentColor stroke.
const SYMBOL_ICONS = {
  socket:        { label: 'Rozetė',      glyph: '⊙',  color: '#2a6fb5' },
  switch:        { label: 'Jungtukas',   glyph: '⊟',  color: '#7c3aed' },
  light_ceiling: { label: 'Šviestuvas',  glyph: '☀',  color: '#f59e0b' },
  vent_supply:   { label: 'Difūzorius',  glyph: '◈',  color: '#0ea5e9' },
  water_cold:    { label: 'Vanduo',      glyph: '◐',  color: '#0891b2' },
  data_outlet:   { label: 'Internetas',  glyph: '⌬',  color: '#16a34a' },
};

function clientToCanvas(canvas, e) {
  const rect = canvas.getBoundingClientRect();
  return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }

function pctToPx(pt, dims) {
  return { x: pt.x_pct * dims.width, y: pt.y_pct * dims.height };
}

function pxToPct(pt, dims) {
  return {
    x_pct: dims.width  > 0 ? pt.x / dims.width  : 0,
    y_pct: dims.height > 0 ? pt.y / dims.height : 0,
  };
}

/** Returns the polygon corner nearest to ``cursor`` (within ``thresholdPx``)
 *  or null. ``rooms`` is the API rooms list; ``dims`` are canvas dimensions.*/
function snapToCorner(cursor, rooms, dims, thresholdPx) {
  let best = null;
  let bestD = thresholdPx;
  for (const room of rooms) {
    if (!room.polygon_pct) continue;
    for (const v of room.polygon_pct) {
      const px = pctToPx(v, dims);
      const d = dist(cursor, px);
      if (d < bestD) {
        bestD = d;
        best = { ...px, room_nr: room.nr, room_name: room.name };
      }
    }
  }
  return best;
}

/** Even-odd point-in-polygon test in canvas px space. */
function pointInPolygonPx(pt, polygonPx) {
  let inside = false;
  const n = polygonPx.length;
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = polygonPx[i].x, yi = polygonPx[i].y;
    const xj = polygonPx[j].x, yj = polygonPx[j].y;
    const intersect =
      (yi > pt.y) !== (yj > pt.y) &&
      pt.x < ((xj - xi) * (pt.y - yi)) / (yj - yi + 1e-9) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

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

  // ── Tool / interaction state ─────────────────────────────────────────────
  const [tool, setTool] = useState(TOOLS.NONE);
  const [placeSymbolType, setPlaceSymbolType] = useState(null);

  // ── Scale (mm per CANVAS pixel) ──────────────────────────────────────────
  // Initialised from backend's page-scale (when available); user can
  // recalibrate at any time. Persisted via annotations endpoint.
  const [scale, setScale] = useState(null);
  const [calibrationPoints, setCalibrationPoints] = useState([]);

  // ── Drawing state ────────────────────────────────────────────────────────
  // Measurements and symbols are stored in PCT (page fractions) so they
  // survive page resize / different rendered scales.
  const [measurements, setMeasurements] = useState([]); // {id, p1_pct, p2_pct, length_mm}
  const [symbols, setSymbols]           = useState([]); // {id, type, pos_pct}
  const [draftStart, setDraftStart]     = useState(null); // px (live during measure)
  const [cursorPx, setCursorPx]         = useState(null); // px
  const [snapTarget, setSnapTarget]     = useState(null); // {x, y, room_nr, room_name}
  const [draggingSymbolId, setDraggingSymbolId] = useState(null);

  // ── Backend data ─────────────────────────────────────────────────────────
  const [rooms, setRooms]   = useState([]);
  const [hoveredRoomNr, setHoveredRoomNr] = useState(null);
  const [selectedRoomNr, setSelectedRoomNr] = useState(null);
  const [pageScaleMmPerPct, setPageScaleMmPerPct] = useState(null);

  // ── Persistence ──────────────────────────────────────────────────────────
  const [saveStatus, setSaveStatus] = useState(null);
  const [lastSavedAt, setLastSavedAt] = useState(null);

  const canvasRef = useRef(null);

  // ── Fetch room-graph on mount ────────────────────────────────────────────
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

  // ── Derived: mm-per-px from backend scale when present ───────────────────
  useEffect(() => {
    if (scale !== null) return;
    if (pageScaleMmPerPct && pageDims.width > 0) {
      // scale_mm_per_px = scale_mm_per_pct × (1 / page_width_in_px)
      setScale(pageScaleMmPerPct / pageDims.width);
    }
  }, [pageScaleMmPerPct, pageDims, scale]);

  // ── Resize canvas to PDF ────────────────────────────────────────────────
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    c.width = pageDims.width;
    c.height = pageDims.height;
  }, [pageDims]);

  // ── Redraw on any state change ──────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Room polygons (magic-wand layer)
    for (const room of rooms) {
      if (!room.polygon_pct) continue;
      const polyPx = room.polygon_pct.map((v) => pctToPx(v, pageDims));
      ctx.beginPath();
      polyPx.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
      ctx.closePath();
      const isHover = room.nr === hoveredRoomNr;
      const isSelected = room.nr === selectedRoomNr;
      ctx.fillStyle = isSelected
        ? 'rgba(42, 111, 181, 0.30)'
        : isHover
          ? 'rgba(42, 111, 181, 0.18)'
          : 'rgba(42, 111, 181, 0.08)';
      ctx.strokeStyle = isSelected ? '#2a6fb5' : 'rgba(255,255,255,0.9)';
      ctx.lineWidth = isSelected ? 2.5 : 1.5;
      ctx.fill();
      ctx.stroke();
    }

    // 2. Measurements (persisted lines)
    ctx.font = '12px ui-sans-serif, system-ui';
    for (const m of measurements) {
      const p1 = pctToPx(m.p1_pct, pageDims);
      const p2 = pctToPx(m.p2_pct, pageDims);
      ctx.strokeStyle = '#2a6fb5';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(p1.x, p1.y);
      ctx.lineTo(p2.x, p2.y);
      ctx.stroke();
      // Endpoint dots
      [p1, p2].forEach((p) => {
        ctx.fillStyle = '#2a6fb5';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        ctx.fill();
      });
      // Label
      const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
      const label = `${m.length_mm.toFixed(0)} mm`;
      const w = ctx.measureText(label).width + 8;
      ctx.fillStyle = 'rgba(255,255,255,0.94)';
      ctx.fillRect(mid.x - w / 2, mid.y - 16, w, 16);
      ctx.fillStyle = '#2a6fb5';
      ctx.fillText(label, mid.x - w / 2 + 4, mid.y - 4);
    }

    // 3. Calibration in-progress overlay
    if (calibrationPoints.length === 1 && cursorPx) {
      const a = calibrationPoints[0];
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(cursorPx.x, cursorPx.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // 4. Draft measurement (live drag preview)
    if (draftStart && cursorPx && tool === TOOLS.MEASURE) {
      const end = snapTarget || cursorPx;
      ctx.strokeStyle = '#16a34a';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.moveTo(draftStart.x, draftStart.y);
      ctx.lineTo(end.x, end.y);
      ctx.stroke();
      ctx.setLineDash([]);
      if (scale) {
        const lenPx = dist(draftStart, end);
        const label = `${(lenPx * scale).toFixed(0)} mm`;
        ctx.fillStyle = '#16a34a';
        ctx.fillText(label, end.x + 8, end.y - 6);
      }
    }

    // 5. Snap-target indicator
    if (snapTarget && (tool === TOOLS.MEASURE || tool === TOOLS.CALIBRATE)) {
      ctx.strokeStyle = '#16a34a';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(snapTarget.x, snapTarget.y, 8, 0, Math.PI * 2);
      ctx.stroke();
    }

    // 6. Symbols
    for (const s of symbols) {
      const pos = pctToPx(s.pos_pct, pageDims);
      const meta = SYMBOL_ICONS[s.type] || SYMBOL_ICONS.socket;
      ctx.fillStyle = meta.color;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 10, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = 'white';
      ctx.font = '14px ui-sans-serif, system-ui';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(meta.glyph, pos.x, pos.y + 1);
      ctx.textAlign = 'start';
      ctx.textBaseline = 'alphabetic';
      ctx.font = '12px ui-sans-serif, system-ui';
    }
  }, [rooms, pageDims, measurements, symbols, calibrationPoints, draftStart,
      cursorPx, snapTarget, hoveredRoomNr, selectedRoomNr, tool, scale]);

  // ── Mouse handlers ───────────────────────────────────────────────────────
  const onCanvasMove = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const p = clientToCanvas(canvas, e);
    setCursorPx(p);

    // Symbol drag
    if (draggingSymbolId) {
      setSymbols((prev) => prev.map((s) =>
        s.id === draggingSymbolId
          ? { ...s, pos_pct: pxToPct(p, pageDims) }
          : s));
      return;
    }

    // Hover detection (magic-wand)
    if (tool === TOOLS.NONE) {
      let hit = null;
      for (const room of rooms) {
        if (!room.polygon_pct) continue;
        const polyPx = room.polygon_pct.map((v) => pctToPx(v, pageDims));
        if (pointInPolygonPx(p, polyPx)) { hit = room.nr; break; }
      }
      setHoveredRoomNr(hit);
      setSnapTarget(null);
      return;
    }

    // Snap preview while measuring or calibrating
    if (tool === TOOLS.MEASURE || tool === TOOLS.CALIBRATE) {
      setSnapTarget(snapToCorner(p, rooms, pageDims, SNAP_PX));
    }
  };

  const onCanvasClick = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const raw = clientToCanvas(canvas, e);
    const p = snapTarget || raw;

    // Symbol placement
    if (tool === TOOLS.PLACE_SYMBOL && placeSymbolType) {
      setSymbols((prev) => [
        ...prev,
        {
          id: `sym-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          type: placeSymbolType,
          pos_pct: pxToPct(raw, pageDims),
        },
      ]);
      return;
    }

    // Magic-wand select
    if (tool === TOOLS.NONE) {
      let hit = null;
      for (const room of rooms) {
        if (!room.polygon_pct) continue;
        const polyPx = room.polygon_pct.map((v) => pctToPx(v, pageDims));
        if (pointInPolygonPx(raw, polyPx)) { hit = room.nr; break; }
      }
      setSelectedRoomNr(hit);
      // Scroll the sidebar to the selected row
      if (hit) {
        const el = document.getElementById(`room-row-${hit}`);
        el && el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
      return;
    }

    // Calibration
    if (tool === TOOLS.CALIBRATE) {
      const next = [...calibrationPoints, p];
      if (next.length === 1) { setCalibrationPoints(next); return; }
      const distPx = dist(next[0], next[1]);
      const trueMm = parseFloat(window.prompt(
        `Įveskite TIKRĄ atstumą tarp dviejų taškų milimetrais (px=${distPx.toFixed(1)}):`,
        '1000',
      ) || '');
      if (Number.isFinite(trueMm) && trueMm > 0 && distPx > 0) {
        setScale(trueMm / distPx);
      }
      setCalibrationPoints([]);
      setTool(TOOLS.NONE);
      return;
    }

    // Wall-edit (two clicks → length update → recalc)
    if (tool === TOOLS.EDIT_WALL) {
      if (!scale) {
        alert('Pirmiausia kalibruokite mastelį.');
        setTool(TOOLS.CALIBRATE);
        return;
      }
      if (!draftStart) { setDraftStart(p); return; }
      const lenMm = dist(draftStart, p) * scale;
      setDraftStart(null);
      commitWallEdit(lenMm);
      return;
    }

    // Measure
    if (tool === TOOLS.MEASURE) {
      if (!scale) {
        alert('Pirmiausia kalibruokite mastelį.');
        setTool(TOOLS.CALIBRATE);
        return;
      }
      if (!draftStart) { setDraftStart(p); return; }
      const lenPx = dist(draftStart, p);
      const lenMm = lenPx * scale;
      setMeasurements((prev) => [
        ...prev,
        {
          id: `m-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
          p1_pct: pxToPct(draftStart, pageDims),
          p2_pct: pxToPct(p, pageDims),
          length_mm: lenMm,
        },
      ]);
      setDraftStart(null);
    }
  };

  const onCanvasMouseDown = (e) => {
    if (tool !== TOOLS.NONE) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const p = clientToCanvas(canvas, e);
    // Symbol hit-test (radius 10)
    for (const s of symbols) {
      const sp = pctToPx(s.pos_pct, pageDims);
      if (dist(p, sp) <= 12) { setDraggingSymbolId(s.id); return; }
    }
  };

  const onCanvasMouseUp = () => setDraggingSymbolId(null);

  const onCanvasContextMenu = (e) => {
    if (tool !== TOOLS.NONE) return;
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const p = clientToCanvas(canvas, e);
    // Delete symbol under cursor
    const idx = symbols.findIndex(
      (s) => dist(p, pctToPx(s.pos_pct, pageDims)) <= 12,
    );
    if (idx >= 0) setSymbols((prev) => prev.filter((_, i) => i !== idx));
  };

  // ── Persistence ──────────────────────────────────────────────────────────
  const annotationsUrl = `/api/projects/${projectId}/annotations`;
  const handleSave = async () => {
    setSaveStatus('saving');
    try {
      const body = {
        measurements,
        symbols,
        scale_mm_per_px: scale,
        selected_room_nr: selectedRoomNr,
        page: pageNum,
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
      setSaveStatus('saved');
      setLastSavedAt(j.updated_at);
    } catch (err) {
      console.error(err);
      setSaveStatus('error');
    }
  };

  // ── Per-wall editing + verify-all-rooms walkthrough ─────────────────────
  // roomOverrides: { [room_nr]: { walls: { wall_id: length_mm } } }
  // verificationState: { [room_nr]: 'confirmed' | 'corrected' }
  const [roomOverrides, setRoomOverrides] = useState({});
  const [verificationState, setVerificationState] = useState({});
  const [editingWall, setEditingWall] = useState(null); // { room_nr, wall_id, p1_pct, p2_pct }
  // recalc'd totals come back from the backend after each wall edit
  const [recalcedSantrauka, setRecalcedSantrauka] = useState(null);
  // verify-all-rooms walkthrough
  const [walkthroughActive, setWalkthroughActive] = useState(false);
  const [walkthroughIdx, setWalkthroughIdx] = useState(0);

  const roomsWithPolygons = useMemo(
    () => rooms.filter((r) => r.polygon_pct),
    [rooms],
  );

  /** Recalc a single room via /rooms/{nr}/recalc and patch local state. */
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
      // Patch the room's local fields with the backend's recalculated values
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

  /** Begin editing a specific wall. The next click-pair on the canvas
   *  becomes the new wall length; we redraw and recalc instantly. */
  const startWallEdit = (room_nr, wall_id) => {
    // For rooms whose polygon_pct comes from bbox, walls 0..3 are
    // {bottom, right, top, left}. We seed editingWall with the wall's
    // pct endpoints so the measure tool snaps to them.
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

  /** Commit a measured wall edit: store override, recalc room, update KŽ. */
  const commitWallEdit = async (length_mm) => {
    if (!editingWall) return;
    const { room_nr, wall_id } = editingWall;
    // Merge into roomOverrides
    setRoomOverrides((prev) => {
      const next = { ...prev };
      const block = { walls: { ...(prev[room_nr]?.walls || {}) } };
      block.walls[wall_id] = length_mm;
      next[room_nr] = block;
      return next;
    });
    // Build the full walls list for this room (mix override + existing perim).
    // For Annotator MVP, we approximate: if the user has overridden ALL 4 walls,
    // the new perim = sum(overrides). Otherwise we scale the original perim
    // proportionally to the edited wall's old vs new length so the recalc has
    // a reasonable single-wall response. The backend accepts a list either
    // way; production refinement is left for the next iteration once room
    // graphs carry full per-wall data.
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
    setDraftStart(null);
    await recalcRoom(room_nr, walls);
  };

  /** Mark a room confirmed in the verify walkthrough. */
  const confirmRoom = (room_nr) => {
    setVerificationState((prev) => ({ ...prev, [room_nr]: 'confirmed' }));
  };
  const markCorrected = (room_nr) => {
    setVerificationState((prev) => ({ ...prev, [room_nr]: 'corrected' }));
  };

  // ── Calibration (contractor enters known totals) ─────────────────────────
  const [calibrationModalOpen, setCalibrationModalOpen] = useState(false);
  const [calibrationFactors, setCalibrationFactors] = useState({});
  const [calibrationOverrides, setCalibrationOverrides] = useState({});
  const [calibrationFetching, setCalibrationFetching] = useState(false);

  // KŽ totals derived from rooms (the magic-wand sidebar already exposes
  // per-room values; here we aggregate for the calibration dialog).
  const kzTotals = useMemo(() => {
    const sum = (field) =>
      rooms.reduce((acc, r) => acc + (Number(r[field]) || 0), 0);
    return {
      dazymo_plotas_m2: Number(sum("dazymo_plotas_m2").toFixed(2)),
      walls_paintable_m2: Number(sum("walls_paintable_m2").toFixed(2)),
      ceiling_paintable_m2: Number(sum("ceiling_paintable_m2").toFixed(2)),
      floor_total_m2: Number(sum("area_m2").toFixed(2)),
    };
  }, [rooms]);

  // Fetch any stored calibration on mount
  useEffect(() => {
    const url = `/api/projects/${projectId}/calibrate`;
    fetch(url, { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((j) => {
        if (j && j.factors) {
          setCalibrationFactors(j.factors);
          setCalibrationOverrides(j.overrides || {});
        }
      })
      .catch(() => undefined);
  }, [projectId]);

  const submitCalibration = async (overrides) => {
    setCalibrationFetching(true);
    try {
      const url = fixture
        ? `/api/projects/${projectId}/calibrate?fixture=${fixture}`
        : `/api/projects/${projectId}/calibrate`;
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ overrides }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = await r.json();
      setCalibrationFactors(j.factors || {});
      setCalibrationOverrides(overrides);
      setCalibrationModalOpen(false);
    } catch (err) {
      console.error("calibration failed", err);
      alert("Kalibravimas nepavyko");
    } finally {
      setCalibrationFetching(false);
    }
  };

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
      alert('Symbolių aptikimas nepavyko');
    } finally {
      setDetecting(false);
    }
  };

  // ── Computed ─────────────────────────────────────────────────────────────
  const selectedRoom = useMemo(
    () => rooms.find((r) => r.nr === selectedRoomNr),
    [rooms, selectedRoomNr],
  );

  // ── JSX ──────────────────────────────────────────────────────────────────
  const toolBtn = (id, label, glyph) => (
    <button
      type="button"
      key={id}
      onClick={() => {
        setTool(id);
        if (id !== TOOLS.MEASURE) setDraftStart(null);
        if (id !== TOOLS.CALIBRATE) setCalibrationPoints([]);
        if (id !== TOOLS.PLACE_SYMBOL) setPlaceSymbolType(null);
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

  return (
    <div className="flex h-screen flex-col bg-neutral-100">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2 border-b border-neutral-200 bg-white px-4 py-2 text-sm">
        <strong className="mr-3 text-neutral-700">Matavimas</strong>
        {toolBtn(TOOLS.NONE,      'Pasirinkti', '🖱')}
        {toolBtn(TOOLS.CALIBRATE, 'Kalibruoti', '🔍')}
        {toolBtn(TOOLS.MEASURE,   'Matuoti',    '📏')}
        <button
          type="button"
          onClick={handleDetectSymbols}
          disabled={detecting}
          className="flex items-center gap-1.5 rounded border border-purple-300 bg-white px-3 py-1.5 text-sm text-purple-700 hover:border-purple-500"
        >
          <span>💡</span><span>{detecting ? 'Aptinkama…' : 'Aptikti simbolius'}</span>
        </button>
        <span className="mx-2 text-neutral-300">|</span>
        <button
          type="button"
          onClick={() => {
            setWalkthroughActive(true);
            setWalkthroughIdx(0);
            if (roomsWithPolygons[0]) setSelectedRoomNr(roomsWithPolygons[0].nr);
          }}
          disabled={roomsWithPolygons.length === 0}
          className="rounded border border-sky-500 bg-sky-50 px-3 py-1.5 text-sky-700"
          title="Praeiti per visus kambarius ir patvirtinti / pakoreguoti"
        >🚶 Tikrinti kambarius</button>
        <button
          type="button"
          onClick={() => setCalibrationModalOpen(true)}
          className="rounded border border-amber-500 bg-amber-50 px-3 py-1.5 text-amber-700"
          title="Kalibruoti AI sumas pagal jūsų žinomus skaičius"
        >⚖ Kalibruoti</button>
        <button
          type="button"
          onClick={async () => {
            const url = fixture
              ? `/api/projects/${projectId}/export-excel?fixture=${fixture}`
              : `/api/projects/${projectId}/export-excel`;
            const r = await fetch(url, { method: 'POST', credentials: 'include' });
            if (!r.ok) return alert('Eksportavimas nepavyko');
            const blob = await r.blob();
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = `samata-${projectId}.xlsx`;
            a.click();
            URL.revokeObjectURL(a.href);
          }}
          className="rounded border border-green-600 bg-green-50 px-3 py-1.5 text-green-700"
          title="Eksportuoti KŽ į Excel"
        >📊 Eksportuoti</button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saveStatus === 'saving'}
          className="rounded border border-emerald-500 bg-emerald-50 px-3 py-1.5 text-emerald-700"
        >💾 Įrašyti</button>
        <button
          type="button"
          onClick={handleLoad}
          disabled={saveStatus === 'saving'}
          className="rounded border border-neutral-300 bg-white px-3 py-1.5 text-neutral-700"
        >↺ Atkurti</button>
        <span className="text-xs text-neutral-500">
          {saveStatus === 'saving' && '⏳'}
          {saveStatus === 'saved' && lastSavedAt && `✓ ${new Date(lastSavedAt * 1000).toLocaleTimeString('lt-LT')}`}
          {saveStatus === 'error' && '⚠ klaida'}
        </span>
        <span className="ml-auto text-neutral-600">
          Mastelis: <strong>{scale ? `1 mm = ${(1 / scale).toFixed(2)} px` : 'nekalibruota'}</strong>
          {' · '}
          Matavimai: <strong>{measurements.length}</strong>
          {' · '}
          Simboliai: <strong>{symbols.length}</strong>
          {' · '}
          Puslapis {pageNum}/{numPages || '?'}
        </span>
      </div>

      {/* Symbol palette — only shown when no other tool active */}
      {tool === TOOLS.NONE || tool === TOOLS.PLACE_SYMBOL ? (
        <div className="flex items-center gap-2 border-b border-neutral-200 bg-neutral-50 px-4 py-1.5 text-xs">
          <span className="text-neutral-500">Simboliai:</span>
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
                  ? 'border-purple-500 bg-purple-50 text-purple-700'
                  : 'border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300'
              }`}
              style={{ borderLeftWidth: 4, borderLeftColor: meta.color }}
            >
              <span>{meta.glyph}</span>{meta.label}
            </button>
          ))}
          <span className="ml-2 text-neutral-400">
            Dešinysis pelės klavišas = ištrinti.  Vilkti = perkelti.
          </span>
        </div>
      ) : null}

      {loadError && (
        <div className="bg-red-50 border-y border-red-200 px-4 py-2 text-sm text-red-700">
          PDF įkėlimo klaida: {loadError}
        </div>
      )}

      {/* Body — PDF + canvas left, sidebar right */}
      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-1 items-start justify-center overflow-auto p-4">
          <div className="relative inline-block bg-white shadow">
            <Document
              file={pdfUrl}
              onLoadSuccess={({ numPages }) => setNumPages(numPages)}
              onLoadError={(err) => setLoadError(err?.message || String(err))}
              loading={<div className="p-12 text-neutral-500">Kraunama PDF…</div>}
            >
              <Page
                pageNumber={pageNum}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                onRenderSuccess={(page) => setPageDims({ width: page.width, height: page.height })}
              />
            </Document>
            <canvas
              ref={canvasRef}
              onClick={onCanvasClick}
              onMouseMove={onCanvasMove}
              onMouseDown={onCanvasMouseDown}
              onMouseUp={onCanvasMouseUp}
              onMouseLeave={() => { setCursorPx(null); setSnapTarget(null); setHoveredRoomNr(null); }}
              onContextMenu={onCanvasContextMenu}
              className={`absolute left-0 top-0 ${
                tool === TOOLS.NONE ? 'cursor-pointer' : 'cursor-crosshair'
              }`}
              style={{
                width: pageDims.width || 0,
                height: pageDims.height || 0,
              }}
            />
            {/* Hover tooltip */}
            {hoveredRoomNr && cursorPx && (
              <div
                className="pointer-events-none absolute rounded bg-neutral-900 px-2 py-1 text-xs text-white shadow"
                style={{ left: cursorPx.x + 14, top: cursorPx.y + 14 }}
              >
                {rooms.find((r) => r.nr === hoveredRoomNr)?.name}
              </div>
            )}
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
              alert(`Patvirtinta: ${confirmed + 1}, Pakoreguota: ${corrected}, Iš viso: ${total}`);
              return;
            }
            const nextIdx = walkthroughIdx + 1;
            setWalkthroughIdx(nextIdx);
            setSelectedRoomNr(roomsWithPolygons[nextIdx].nr);
          };
          return (
            <div className="pointer-events-none absolute right-4 top-4 z-40 w-80 pointer-events-auto rounded-lg border border-sky-300 bg-white p-4 shadow-2xl">
              <div className="mb-1 text-xs uppercase text-sky-600">
                Tikrinimas {walkthroughIdx + 1} / {total}
              </div>
              <div className="text-base font-semibold text-neutral-800">
                {current.nr} {current.name}
              </div>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-neutral-600">
                <div>Plotas: <strong>{current.area_m2.toFixed(2)} m²</strong></div>
                <div>Perim.: <strong>{(current.perimeter_mm / 1000).toFixed(2)} m</strong></div>
                <div>H: <strong>{current.ceiling_height_m.toFixed(2)} m</strong></div>
                <div>Dažym.: <strong>{current.dazymo_plotas_m2.toFixed(1)} m²</strong></div>
              </div>
              <p className="mt-3 text-sm font-medium text-neutral-700">
                Ar AI matmenys teisingi?
              </p>
              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => { confirmRoom(current.nr); advance(); }}
                  className="flex-1 rounded border border-emerald-500 bg-emerald-50 px-2 py-1.5 text-sm text-emerald-700"
                >✓ Taip</button>
                <button
                  type="button"
                  onClick={() => markCorrected(current.nr)}
                  className="flex-1 rounded border border-amber-500 bg-amber-50 px-2 py-1.5 text-sm text-amber-700"
                  title="Pakoreguokite sienas dešinėje, tada Toliau"
                >✎ Koreguoti</button>
              </div>
              <div className="mt-2 flex gap-2 text-xs">
                <button
                  type="button"
                  onClick={advance}
                  className="flex-1 rounded border border-neutral-300 px-2 py-1 text-neutral-600"
                >→ Toliau</button>
                <button
                  type="button"
                  onClick={() => setWalkthroughActive(false)}
                  className="rounded border border-neutral-300 px-2 py-1 text-neutral-500"
                >Nutraukti</button>
              </div>
              <div className="mt-2 text-xs text-neutral-400">
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
        <aside className="flex w-[36%] min-w-[320px] flex-col border-l border-neutral-200 bg-neutral-50">
          {/* KŽ summary — AI vs Calibrated (when contractor overrides exist) */}
          <section className="border-b border-neutral-200 bg-white px-4 py-3">
            <div className="mb-1 flex items-center justify-between">
              <div className="text-xs font-medium uppercase text-neutral-500">
                KŽ santrauka
              </div>
              {Object.keys(calibrationFactors).length > 0 && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
                  ⚖ Kalibruota
                </span>
              )}
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-neutral-500">
                  <th className="text-left">Kategorija</th>
                  <th className="text-right">AI</th>
                  <th className="text-right">Jūsų</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["dazymo_plotas_m2", "Dažymo plotas", kzTotals.dazymo_plotas_m2, "m²"],
                  ["walls_paintable_m2", "Sienos", kzTotals.walls_paintable_m2, "m²"],
                  ["ceiling_paintable_m2", "Lubos", kzTotals.ceiling_paintable_m2, "m²"],
                  ["floor_total_m2", "Plotas", kzTotals.floor_total_m2, "m²"],
                ].map(([key, label, ai, unit]) => {
                  const override = calibrationOverrides[key];
                  const factor = calibrationFactors[key]?.factor;
                  const calibrated = (override !== undefined)
                    ? override
                    : (factor ? ai * factor : null);
                  return (
                    <tr key={key} className="border-t border-neutral-100">
                      <td className="py-1 text-neutral-700">{label}</td>
                      <td className="py-1 text-right font-mono text-neutral-600">
                        {ai.toFixed(2)} {unit}
                      </td>
                      <td className="py-1 text-right font-mono font-semibold text-amber-700">
                        {calibrated !== null && calibrated !== undefined
                          ? `${calibrated.toFixed(2)} ${unit}`
                          : "—"}
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
            >
              ⚖ Kalibruoti pagal mano sumas
            </button>
          </section>

          {/* Selected room card + per-wall edit list */}
          {selectedRoom && (
            <section className="border-b border-neutral-200 bg-blue-50/40 px-4 py-3">
              <div className="mb-1 flex items-center justify-between">
                <div className="text-xs font-medium uppercase text-neutral-500">
                  Pasirinkta patalpa
                </div>
                {verificationState[selectedRoom.nr] === 'confirmed' && (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">✓ Patvirtinta</span>
                )}
                {verificationState[selectedRoom.nr] === 'corrected' && (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">✎ Pakoreguota</span>
                )}
              </div>
              <div className="text-base font-semibold text-neutral-800">
                {selectedRoom.nr} {selectedRoom.name}
              </div>
              <div className="mt-1 grid grid-cols-3 gap-2 text-xs">
                <div><span className="text-neutral-500">Plotas: </span><strong>{selectedRoom.area_m2.toFixed(2)} m²</strong></div>
                <div><span className="text-neutral-500">Perimetras: </span><strong>{(selectedRoom.perimeter_mm / 1000).toFixed(2)} m</strong></div>
                <div><span className="text-neutral-500">H: </span><strong>{selectedRoom.ceiling_height_m.toFixed(2)} m</strong></div>
                <div><span className="text-neutral-500">Sienos dažomos: </span><strong>{selectedRoom.walls_paintable_m2.toFixed(1)} m²</strong></div>
                <div><span className="text-neutral-500">Lubos: </span><strong>{selectedRoom.ceiling_paintable_m2.toFixed(1)} m²</strong></div>
                <div><span className="text-neutral-500">Σ dažymas: </span><strong>{selectedRoom.dazymo_plotas_m2.toFixed(1)} m²</strong></div>
              </div>

              {/* Per-wall edit list (only when polygon known) */}
              {selectedRoom.polygon_pct && (
                <div className="mt-3">
                  <div className="mb-1 text-xs font-medium text-neutral-500">Sienos</div>
                  <ul className="space-y-1">
                    {selectedRoom.polygon_pct.map((_, idx) => {
                      const wallId = `w${idx + 1}`;
                      const override = roomOverrides[selectedRoom.nr]?.walls?.[wallId];
                      const aiLen = (selectedRoom.perimeter_mm / selectedRoom.polygon_pct.length / 1000).toFixed(2);
                      return (
                        <li key={wallId} className="flex items-center gap-2 text-xs">
                          <span className="w-8 font-mono text-neutral-500">{wallId}</span>
                          <span className="flex-1">
                            AI: {aiLen} m
                            {override !== undefined && (
                              <span className="ml-2 font-mono font-semibold text-amber-700">
                                → {(override / 1000).toFixed(2)} m
                              </span>
                            )}
                          </span>
                          <button
                            type="button"
                            onClick={() => startWallEdit(selectedRoom.nr, wallId)}
                            disabled={!scale}
                            title={scale ? 'Pertaškyti sieną' : 'Pirmiausia kalibruokite'}
                            className="rounded border border-blue-300 bg-white px-2 py-0.5 text-blue-700 hover:border-blue-500"
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
                  className="flex-1 rounded border border-emerald-500 bg-emerald-50 px-2 py-1 text-xs text-emerald-700"
                >✓ Patvirtinti</button>
                <button
                  type="button"
                  onClick={() => markCorrected(selectedRoom.nr)}
                  className="flex-1 rounded border border-amber-500 bg-amber-50 px-2 py-1 text-xs text-amber-700"
                >✎ Pakoregavau</button>
              </div>
            </section>
          )}

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

          {/* Measurements */}
          <section className="flex-1 overflow-auto">
            <header className="flex items-center justify-between px-4 py-2 text-xs font-medium uppercase text-neutral-500">
              <span>Matavimai ({measurements.length})</span>
              {measurements.length > 0 && (
                <button
                  onClick={() => setMeasurements([])}
                  className="rounded border border-neutral-300 px-2 py-0.5 text-xs"
                >Išvalyti</button>
              )}
            </header>
            <ul className="text-sm">
              {measurements.map((m, i) => (
                <li key={m.id} className="flex items-center justify-between gap-2 border-b border-neutral-100 px-4 py-1.5">
                  <span className="text-neutral-500">#{i + 1}</span>
                  <span className="font-mono text-blue-700">{m.length_mm.toFixed(1)} mm</span>
                  <button
                    onClick={() => setMeasurements((prev) => prev.filter((x) => x.id !== m.id))}
                    className="rounded border border-neutral-300 px-2 py-0.5 text-xs text-neutral-600"
                  >Trinti</button>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </div>

      {/* Status bar */}
      <footer className="border-t border-neutral-200 bg-white px-4 py-1.5 text-xs text-neutral-500">
        Įrankis: <strong>{tool}</strong>
        {' · '}Snap: {SNAP_PX}px
        {' · '}Patalpos su poligonais: <strong>{rooms.filter((r) => r.polygon_pct).length}/{rooms.length}</strong>
        {pageScaleMmPerPct && <> {' · '}Aptiktas mastelis: {pageScaleMmPerPct.toFixed(0)} mm/pct</>}
      </footer>
    </div>
  );
}


// ─── Calibration modal ─────────────────────────────────────────────────────
const CALIBRATION_FIELDS = [
  { key: "dazymo_plotas_m2",     label: "Dažymo plotas",       unit: "m²" },
  { key: "plyteles_sienose_m2",  label: "Plytelės sienose",    unit: "m²" },
  { key: "plyteles_grindyse_m2", label: "Plytelės grindyse",   unit: "m²" },
  { key: "angokrasciai_m",       label: "Angokraščiai",        unit: "m"  },
  { key: "kampu_metrai_m",       label: "Dažymo kampai",       unit: "m"  },
  { key: "led_nisos_m",          label: "LED nišų ilgis",      unit: "m"  },
  { key: "gkp_lubu_iki_3m_m2",   label: "GKP lubos iki 3m",    unit: "m²" },
];

function CalibrationModal({ initialAi, initialOverrides, onCancel, onSubmit, busy }) {
  const [values, setValues] = React.useState(() => {
    const out = {};
    for (const f of CALIBRATION_FIELDS) {
      out[f.key] = initialOverrides[f.key] ?? "";
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
      alert("Įveskite bent vieną kategoriją.");
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
        <h2 className="mb-1 text-lg font-semibold text-neutral-800">
          Kalibruoti pagal jūsų sumas
        </h2>
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
            <button
              type="button"
              onClick={onCancel}
              className="rounded border border-neutral-300 px-4 py-1.5 text-sm"
            >Atšaukti</button>
            <button
              type="submit"
              disabled={busy}
              className="rounded border border-amber-500 bg-amber-500 px-4 py-1.5 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
            >{busy ? "Saugoma…" : "Kalibruoti"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

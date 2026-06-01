/**
 * AnnotationCanvas — vanilla-canvas overlay for the Annotator.
 *
 * Receives all persistent state as props (measurements, symbols, rooms,
 * tool, scale, …); owns ONLY transient drawing state (cursor position,
 * draft start, calibration points, snap target). Emits user actions via
 * the on* callbacks. Exposes an imperative ref API for snap/hit-test
 * lookups + cancelDraft.
 *
 * Drop-in Fabric.js replacement target — see docs/viewer-api.md for the
 * full contract this file implements.
 */
import React, {
  forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState,
} from 'react';

const SNAP_PX = 20;

// LT construction icon set — small SVG glyphs, all 24×24, currentColor stroke.
export const SYMBOL_ICONS = {
  socket:        { label: 'Rozetė',      glyph: '⊙',  color: '#2a6fb5' },
  switch:        { label: 'Jungtukas',   glyph: '⊟',  color: '#7c3aed' },
  light_ceiling: { label: 'Šviestuvas',  glyph: '☀',  color: '#f59e0b' },
  vent_supply:   { label: 'Difūzorius',  glyph: '◈',  color: '#0ea5e9' },
  water_cold:    { label: 'Vanduo',      glyph: '◐',  color: '#0891b2' },
  data_outlet:   { label: 'Internetas',  glyph: '⌬',  color: '#16a34a' },
};

export const TOOLS = {
  NONE: 'none',
  CALIBRATE: 'calibrate',
  MEASURE: 'measure',
  PLACE_SYMBOL: 'place_symbol',
  EDIT_WALL: 'edit_wall',
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

const AnnotationCanvas = forwardRef(function AnnotationCanvas(
  {
    pageDims,
    tool,
    scale,
    rooms,
    measurements,
    symbols,
    placeSymbolType,
    selectedRoomNr,
    hoveredRoomNr,
    editingWall,                     // {room_nr, wall_id, p1_pct, p2_pct} | null
    onMeasurementComplete,
    onSymbolPlaced,
    onSymbolDeleted,
    onSymbolMoved,
    onCalibrationComplete,
    onRoomClick,
    onRoomHover,
    onWallEditComplete,
  },
  ref,
) {
  const canvasRef = useRef(null);
  const [cursorPx, setCursorPx] = useState(null);
  const [draftStart, setDraftStart] = useState(null);
  const [snapTarget, setSnapTarget] = useState(null);
  const [calibrationPoints, setCalibrationPoints] = useState([]);
  const [draggingSymbolId, setDraggingSymbolId] = useState(null);

  // ── Imperative API ────────────────────────────────────────────────────────
  useImperativeHandle(ref, () => ({
    snapPxToCorner: (point) =>
      snapToCorner(point, rooms, pageDims, SNAP_PX),
    getCanvasDims: () => ({ width: pageDims.width, height: pageDims.height }),
    cancelDraft: () => {
      setDraftStart(null);
      setCalibrationPoints([]);
      setSnapTarget(null);
    },
    hitTestRoomAtPx: (point) => {
      for (const room of rooms) {
        if (!room.polygon_pct) continue;
        const polyPx = room.polygon_pct.map((v) => pctToPx(v, pageDims));
        if (pointInPolygonPx(point, polyPx)) return room.nr;
      }
      return null;
    },
    hitTestSymbolAtPx: (point) => {
      for (const s of symbols) {
        const sp = pctToPx(s.pos_pct, pageDims);
        if (dist(point, sp) <= 12) return s.id;
      }
      return null;
    },
  }), [rooms, symbols, pageDims]);

  // Cancel transient drafts whenever the tool switches.
  useEffect(() => {
    setDraftStart(null);
    setCalibrationPoints([]);
    setSnapTarget(null);
  }, [tool]);

  // Resize canvas backing store to page dims
  useEffect(() => {
    const c = canvasRef.current;
    if (!c) return;
    c.width = pageDims.width;
    c.height = pageDims.height;
  }, [pageDims]);

  // ── Redraw on any state change ───────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Room polygons
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

    // 2. Measurements
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
      [p1, p2].forEach((p) => {
        ctx.fillStyle = '#2a6fb5';
        ctx.beginPath();
        ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
        ctx.fill();
      });
      const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
      const label = `${m.length_mm.toFixed(0)} mm`;
      const w = ctx.measureText(label).width + 8;
      ctx.fillStyle = 'rgba(255,255,255,0.94)';
      ctx.fillRect(mid.x - w / 2, mid.y - 16, w, 16);
      ctx.fillStyle = '#2a6fb5';
      ctx.fillText(label, mid.x - w / 2 + 4, mid.y - 4);
    }

    // 3. Calibration in-progress
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

    // 4. Draft measurement (MEASURE / EDIT_WALL)
    if (draftStart && cursorPx && (tool === TOOLS.MEASURE || tool === TOOLS.EDIT_WALL)) {
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

    // 5. Snap indicator
    if (snapTarget && (tool === TOOLS.MEASURE || tool === TOOLS.CALIBRATE || tool === TOOLS.EDIT_WALL)) {
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
  }, [
    rooms, pageDims, measurements, symbols, calibrationPoints,
    draftStart, cursorPx, snapTarget, hoveredRoomNr, selectedRoomNr,
    tool, scale,
  ]);

  // ── Mouse handlers ───────────────────────────────────────────────────────
  const onMove = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const p = clientToCanvas(canvas, e);
    setCursorPx(p);

    if (draggingSymbolId) {
      onSymbolMoved && onSymbolMoved(draggingSymbolId, pxToPct(p, pageDims));
      return;
    }
    if (tool === TOOLS.NONE) {
      let hit = null;
      for (const room of rooms) {
        if (!room.polygon_pct) continue;
        const polyPx = room.polygon_pct.map((v) => pctToPx(v, pageDims));
        if (pointInPolygonPx(p, polyPx)) { hit = room.nr; break; }
      }
      onRoomHover && onRoomHover(hit);
      setSnapTarget(null);
      return;
    }
    if (tool === TOOLS.MEASURE || tool === TOOLS.CALIBRATE || tool === TOOLS.EDIT_WALL) {
      setSnapTarget(snapToCorner(p, rooms, pageDims, SNAP_PX));
    }
  };

  const onClick = (e) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const raw = clientToCanvas(canvas, e);
    const p = snapTarget || raw;

    if (tool === TOOLS.PLACE_SYMBOL && placeSymbolType) {
      onSymbolPlaced && onSymbolPlaced({
        type: placeSymbolType,
        pos_pct: pxToPct(raw, pageDims),
      });
      return;
    }

    if (tool === TOOLS.NONE) {
      const hit = (() => {
        for (const room of rooms) {
          if (!room.polygon_pct) continue;
          const polyPx = room.polygon_pct.map((v) => pctToPx(v, pageDims));
          if (pointInPolygonPx(raw, polyPx)) return room.nr;
        }
        return null;
      })();
      onRoomClick && onRoomClick(hit);
      return;
    }

    if (tool === TOOLS.CALIBRATE) {
      const next = [...calibrationPoints, p];
      if (next.length === 1) { setCalibrationPoints(next); return; }
      const distPx = dist(next[0], next[1]);
      const trueMm = parseFloat(window.prompt(
        `Įveskite TIKRĄ atstumą tarp dviejų taškų milimetrais (px=${distPx.toFixed(1)}):`,
        '1000',
      ) || '');
      setCalibrationPoints([]);
      if (Number.isFinite(trueMm) && trueMm > 0 && distPx > 0) {
        onCalibrationComplete && onCalibrationComplete(trueMm / distPx);
      }
      return;
    }

    if (tool === TOOLS.EDIT_WALL) {
      if (!scale) return;
      if (!draftStart) { setDraftStart(p); return; }
      const lenMm = dist(draftStart, p) * scale;
      setDraftStart(null);
      onWallEditComplete && onWallEditComplete(
        editingWall?.room_nr, editingWall?.wall_id, lenMm,
      );
      return;
    }

    if (tool === TOOLS.MEASURE) {
      if (!scale) {
        alert('Pirmiausia kalibruokite mastelį.');
        return;
      }
      if (!draftStart) { setDraftStart(p); return; }
      const lenPx = dist(draftStart, p);
      const lenMm = lenPx * scale;
      setDraftStart(null);
      onMeasurementComplete && onMeasurementComplete({
        p1_pct: pxToPct(draftStart, pageDims),
        p2_pct: pxToPct(p, pageDims),
        length_mm: lenMm,
      });
    }
  };

  const onMouseDown = (e) => {
    if (tool !== TOOLS.NONE) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const p = clientToCanvas(canvas, e);
    for (const s of symbols) {
      const sp = pctToPx(s.pos_pct, pageDims);
      if (dist(p, sp) <= 12) { setDraggingSymbolId(s.id); return; }
    }
  };
  const onMouseUp = () => setDraggingSymbolId(null);

  const onContextMenu = (e) => {
    if (tool !== TOOLS.NONE) return;
    e.preventDefault();
    const canvas = canvasRef.current;
    if (!canvas) return;
    const p = clientToCanvas(canvas, e);
    for (const s of symbols) {
      const sp = pctToPx(s.pos_pct, pageDims);
      if (dist(p, sp) <= 12) {
        onSymbolDeleted && onSymbolDeleted(s.id);
        return;
      }
    }
  };

  return (
    <canvas
      ref={canvasRef}
      onClick={onClick}
      onMouseMove={onMove}
      onMouseDown={onMouseDown}
      onMouseUp={onMouseUp}
      onMouseLeave={() => {
        setCursorPx(null);
        setSnapTarget(null);
        onRoomHover && onRoomHover(null);
      }}
      onContextMenu={onContextMenu}
      className={`absolute left-0 top-0 ${tool === TOOLS.NONE ? 'cursor-pointer' : 'cursor-crosshair'}`}
      style={{ width: pageDims.width || 0, height: pageDims.height || 0 }}
    />
  );
});

export default AnnotationCanvas;

/**
 * AnnotationCanvas — Fabric.js-backed overlay for the Annotator viewer.
 *
 * Contract: see docs/viewer-api.md. Same forwardRef + useImperativeHandle
 * surface as the legacy vanilla-canvas implementation; the swap is a
 * single-file change. All caller-visible behaviour is preserved:
 *
 *   - draws room polygons, measurements, symbols, draft cursor, snap ring
 *   - the imperative API (snapPxToCorner / cancelDraft / hitTest…) is identical
 *   - all coordinate state stored in pct (page-fraction), pixel conversions
 *     happen at draw time
 *
 * What changed:
 *
 *   - render path uses fabric.Canvas → fabric.Polygon/Line/Circle/Text/Group
 *     instead of imperative ctx.draw calls. Same per-state-change clear+
 *     redraw cycle (the React state model is the source of truth; Fabric
 *     is the rendering primitive).
 *   - the canvas now supports zoom via the `zoom` prop. The DOM canvas
 *     element stays sized to pageDims (page-pixel coords); fabric's
 *     viewport transform scales the rendered output. Pointer events are
 *     unwrapped back to page-pixel coords so hit-test logic is unchanged.
 *   - wheel events bubble to the parent so the parent can drive a shared
 *     pan/zoom across the PDF + canvas.
 */
import React, {
  forwardRef, useEffect, useImperativeHandle, useMemo, useRef, useState,
} from 'react';
import * as fabric from 'fabric';

// ── Constants ──────────────────────────────────────────────────────────────
const SNAP_PX = 20;

export const SYMBOL_ICONS = {
  socket:        { glyph: '⚡', color: '#dc2626', label: 'Rozetė' },
  switch:        { glyph: '⌧', color: '#2563eb', label: 'Jungiklis' },
  light_ceiling: { glyph: '☀', color: '#f59e0b', label: 'Šviestuvas' },
  vent_supply:   { glyph: '⤒', color: '#0891b2', label: 'Vėdinimas' },
  water_cold:    { glyph: '💧', color: '#0284c7', label: 'Vanduo' },
  data_outlet:   { glyph: '⚙', color: '#7c3aed', label: 'Internetas' },
};

export const TOOLS = {
  NONE:        'none',
  CALIBRATE:   'calibrate',
  MEASURE:     'measure',
  PLACE_SYMBOL: 'place_symbol',
  EDIT_WALL:   'edit_wall',
};

// ── Geometry helpers ───────────────────────────────────────────────────────
function clientToPagePx(canvasEl, e, zoom) {
  // Convert client-space click → page-pixel space.
  // Canvas CSS is sized to pageDims × zoom, so dividing the in-rect
  // offset by `zoom` lands us back in pageDims coords (the same space
  // polygon_pct × pageDims produces). DO NOT use canvasEl.width — that's
  // the DPI-scaled intrinsic store (Fabric multiplies it for HiDPI) and
  // would put coords in a different space than the polygon hit-test.
  const rect = canvasEl.getBoundingClientRect();
  return {
    x: (e.clientX - rect.left) / zoom,
    y: (e.clientY - rect.top) / zoom,
  };
}

function dist(a, b) { return Math.hypot(a.x - b.x, a.y - b.y); }

function pctToPx(pt, dims) {
  return { x: pt.x_pct * dims.width, y: pt.y_pct * dims.height };
}

function pxToPct(pt, dims) {
  return {
    x_pct: dims.width ? pt.x / dims.width : 0,
    y_pct: dims.height ? pt.y / dims.height : 0,
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
        best = { x: px.x, y: px.y, room_nr: room.nr, room_name: room.name };
      }
    }
  }
  return best;
}

function pointInPolygonPx(pt, polygonPx) {
  let inside = false;
  for (let i = 0, j = polygonPx.length - 1; i < polygonPx.length; j = i++) {
    const xi = polygonPx[i].x, yi = polygonPx[i].y;
    const xj = polygonPx[j].x, yj = polygonPx[j].y;
    const intersect = ((yi > pt.y) !== (yj > pt.y))
      && (pt.x < ((xj - xi) * (pt.y - yi)) / (yj - yi + 1e-9) + xi);
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
    editingWall,
    selectedMeasurementId = null,
    zoom = 1,
    onMeasurementComplete,
    onSymbolPlaced,
    onSymbolDeleted,
    onSymbolMoved,
    onCalibrationComplete,
    onRoomClick,
    onRoomHover,
    onWallEditComplete,
    onMeasurementClick,
    onWheel,
  },
  ref,
) {
  const canvasElRef = useRef(null);
  const fabricRef = useRef(null);                  // fabric.Canvas instance
  const [cursorPx, setCursorPx] = useState(null);
  const [draftStart, setDraftStart] = useState(null);
  const [snapTarget, setSnapTarget] = useState(null);
  const [calibrationPoints, setCalibrationPoints] = useState([]);
  const [draggingSymbolId, setDraggingSymbolId] = useState(null);

  // ── Initialize fabric.Canvas once ───────────────────────────────────────
  useEffect(() => {
    const el = canvasElRef.current;
    if (!el || fabricRef.current) return undefined;
    const fc = new fabric.Canvas(el, {
      selection: false,           // we manage selection through React state
      renderOnAddRemove: false,   // we batch via requestRenderAll
      skipTargetFind: true,       // we run our own hit-tests
      preserveObjectStacking: true,
      stopContextMenu: false,
      backgroundColor: undefined,
    });
    // Fabric wraps the <canvas> in a `.canvas-container` div whose CSS
    // doesn't inherit our `absolute left-0 top-0`. Force it manually so
    // the annotation layer overlays the PDF (without this, the wrapper
    // div participates in normal flow and sits BELOW the PDF page).
    const wrapper = fc.wrapperEl;
    if (wrapper) {
      wrapper.style.position = 'absolute';
      wrapper.style.left = '0';
      wrapper.style.top = '0';
      wrapper.style.pointerEvents = 'auto';
    }
    // Fabric installs an `upper-canvas` SIBLING that intercepts ALL
    // pointer events for Fabric's own selection logic. Since we set
    // skipTargetFind+selection=false (React owns interaction), the
    // upper-canvas is interaction-dead AND blocks React's onClick from
    // reaching the lower-canvas (the React-controlled <canvas>). Force
    // pointer-events:none on upper so events fall through to lower.
    if (fc.upperCanvasEl) {
      fc.upperCanvasEl.style.pointerEvents = 'none';
    }
    fabricRef.current = fc;
    return () => { fc.dispose(); fabricRef.current = null; };
  }, []);

  // ── Resize + zoom application ───────────────────────────────────────────
  useEffect(() => {
    const fc = fabricRef.current;
    if (!fc) return;
    fc.setDimensions({ width: pageDims.width, height: pageDims.height });
    fc.setZoom(zoom);
    fc.requestRenderAll();
  }, [pageDims.width, pageDims.height, zoom]);

  // ── Imperative API (unchanged from vanilla impl) ────────────────────────
  useImperativeHandle(ref, () => ({
    snapPxToCorner: (point) => snapToCorner(point, rooms, pageDims, SNAP_PX),
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
    // Hit-test a measurement line — used for canvas → list highlight.
    // Returns the closest measurement id whose line passes within
    // `thresholdPx` of the click point.
    hitTestMeasurementAtPx: (point, thresholdPx = 6) => {
      const distPointToSeg = (p, a, b) => {
        const dx = b.x - a.x, dy = b.y - a.y;
        const t = dx === 0 && dy === 0 ? 0
          : Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx*dx + dy*dy)));
        const px = a.x + t * dx, py = a.y + t * dy;
        return Math.hypot(p.x - px, p.y - py);
      };
      let best = null, bestD = thresholdPx;
      for (const m of measurements) {
        const a = pctToPx(m.p1_pct, pageDims);
        const b = pctToPx(m.p2_pct, pageDims);
        const d = distPointToSeg(point, a, b);
        if (d < bestD) { bestD = d; best = m.id; }
      }
      return best;
    },
    setMeasurements: () => {},    // controlled by parent; no-op preserved for API parity
    setSymbols: () => {},
  }), [rooms, symbols, pageDims, measurements]);

  // Cancel transient drafts whenever the tool switches.
  useEffect(() => {
    setDraftStart(null);
    setCalibrationPoints([]);
    setSnapTarget(null);
  }, [tool]);

  // ── Redraw via Fabric on any state change ───────────────────────────────
  useEffect(() => {
    const fc = fabricRef.current;
    if (!fc) return;
    // Clear & rebuild. Object pooling would be faster but is overkill for
    // typical 5-20 rooms + ~100 measurements/symbols per page.
    fc.remove(...fc.getObjects());

    // 1. Room polygons
    for (const room of rooms) {
      if (!room.polygon_pct) continue;
      const polyPx = room.polygon_pct.map((v) => pctToPx(v, pageDims));
      const isHover = room.nr === hoveredRoomNr;
      const isSelected = room.nr === selectedRoomNr;
      const fill = isSelected ? 'rgba(42, 111, 181, 0.30)'
                 : isHover    ? 'rgba(42, 111, 181, 0.18)'
                              : 'rgba(42, 111, 181, 0.08)';
      const stroke = isSelected ? '#2a6fb5' : 'rgba(255,255,255,0.9)';
      fc.add(new fabric.Polygon(polyPx, {
        fill, stroke,
        strokeWidth: isSelected ? 2.5 : 1.5,
        selectable: false,
        evented: false,
        objectCaching: false,
      }));
    }

    // 2. Measurements
    for (const m of measurements) {
      const p1 = pctToPx(m.p1_pct, pageDims);
      const p2 = pctToPx(m.p2_pct, pageDims);
      const isSelected = m.id && m.id === selectedMeasurementId;
      // Selected measurement gets a yellow halo (thicker, brighter)
      // so the bidirectional canvas↔list highlight is visible.
      if (isSelected) {
        fc.add(new fabric.Line([p1.x, p1.y, p2.x, p2.y], {
          stroke: '#facc15', strokeWidth: 8, opacity: 0.6,
          selectable: false, evented: false, objectCaching: false,
        }));
      }
      fc.add(new fabric.Line([p1.x, p1.y, p2.x, p2.y], {
        stroke: isSelected ? '#1d4ed8' : '#2a6fb5',
        strokeWidth: isSelected ? 3 : 2,
        selectable: false, evented: false, objectCaching: false,
      }));
      for (const p of [p1, p2]) {
        fc.add(new fabric.Circle({
          left: p.x - 3, top: p.y - 3, radius: 3,
          fill: '#2a6fb5', stroke: 'transparent',
          selectable: false, evented: false, objectCaching: false,
        }));
      }
      const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
      const label = `${m.length_mm.toFixed(0)} mm`;
      fc.add(new fabric.Textbox(label, {
        left: mid.x - 30, top: mid.y - 18,
        fontSize: 12, fontFamily: 'ui-sans-serif, system-ui',
        backgroundColor: 'rgba(255,255,255,0.94)',
        fill: '#2a6fb5', textAlign: 'center', width: 60,
        selectable: false, evented: false, objectCaching: false,
      }));
    }

    // 3. Calibration in-progress
    if (calibrationPoints.length === 1 && cursorPx) {
      const a = calibrationPoints[0];
      const ln = new fabric.Line([a.x, a.y, cursorPx.x, cursorPx.y], {
        stroke: '#f59e0b', strokeWidth: 2, strokeDashArray: [6, 4],
        selectable: false, evented: false, objectCaching: false,
      });
      fc.add(ln);
    }

    // 4. Draft measurement (MEASURE / EDIT_WALL)
    if (draftStart && cursorPx && (tool === TOOLS.MEASURE || tool === TOOLS.EDIT_WALL)) {
      const end = snapTarget || cursorPx;
      fc.add(new fabric.Line([draftStart.x, draftStart.y, end.x, end.y], {
        stroke: '#16a34a', strokeWidth: 2, strokeDashArray: [5, 4],
        selectable: false, evented: false, objectCaching: false,
      }));
      if (scale) {
        const lenPx = dist(draftStart, end);
        const label = `${(lenPx * scale).toFixed(0)} mm`;
        fc.add(new fabric.Textbox(label, {
          left: end.x + 8, top: end.y - 14,
          fontSize: 12, fontFamily: 'ui-sans-serif, system-ui',
          fill: '#16a34a', selectable: false, evented: false, objectCaching: false,
          width: 80,
        }));
      }
    }

    // 5. Snap indicator
    if (snapTarget && (tool === TOOLS.MEASURE || tool === TOOLS.CALIBRATE || tool === TOOLS.EDIT_WALL)) {
      fc.add(new fabric.Circle({
        left: snapTarget.x - 8, top: snapTarget.y - 8, radius: 8,
        fill: 'transparent', stroke: '#16a34a', strokeWidth: 2,
        selectable: false, evented: false, objectCaching: false,
      }));
    }

    // 6. Symbols
    for (const s of symbols) {
      const pos = pctToPx(s.pos_pct, pageDims);
      const meta = SYMBOL_ICONS[s.type] || SYMBOL_ICONS.socket;
      const circle = new fabric.Circle({
        left: -10, top: -10, radius: 10,
        fill: meta.color, originX: 'left', originY: 'top',
        selectable: false, evented: false,
      });
      const glyph = new fabric.Text(meta.glyph, {
        left: 0, top: 0,
        originX: 'center', originY: 'center',
        fontSize: 14, fontFamily: 'ui-sans-serif, system-ui',
        fill: 'white', selectable: false, evented: false,
      });
      fc.add(new fabric.Group([circle, glyph], {
        left: pos.x, top: pos.y, originX: 'center', originY: 'center',
        selectable: false, evented: false, objectCaching: false,
      }));
    }

    fc.requestRenderAll();
  }, [
    rooms, pageDims, measurements, symbols, calibrationPoints,
    draftStart, cursorPx, snapTarget, hoveredRoomNr, selectedRoomNr,
    selectedMeasurementId, tool, scale,
  ]);

  // ── Mouse handlers (unchanged event model from vanilla impl) ────────────
  const onMove = (e) => {
    const el = canvasElRef.current;
    if (!el) return;
    const p = clientToPagePx(el, e, zoom);
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
    const el = canvasElRef.current;
    if (!el) return;
    const raw = clientToPagePx(el, e, zoom);
    const p = snapTarget || raw;

    if (tool === TOOLS.PLACE_SYMBOL && placeSymbolType) {
      onSymbolPlaced && onSymbolPlaced({
        type: placeSymbolType,
        pos_pct: pxToPct(raw, pageDims),
      });
      return;
    }

    if (tool === TOOLS.NONE) {
      // 1. Prefer measurement-line click (canvas → list highlight)
      const measHit = (() => {
        // Inline the hit-test (the imperative API method is for outside callers)
        const distPointToSeg = (p, a, b) => {
          const dx = b.x - a.x, dy = b.y - a.y;
          const t = dx === 0 && dy === 0 ? 0
            : Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx*dx + dy*dy)));
          const px = a.x + t * dx, py = a.y + t * dy;
          return Math.hypot(p.x - px, p.y - py);
        };
        let best = null, bestD = 8;
        for (const m of measurements) {
          const a = pctToPx(m.p1_pct, pageDims);
          const b = pctToPx(m.p2_pct, pageDims);
          const d = distPointToSeg(raw, a, b);
          if (d < bestD) { bestD = d; best = m.id; }
        }
        return best;
      })();
      if (measHit && onMeasurementClick) {
        onMeasurementClick(measHit);
        return;
      }
      // 2. Otherwise: room polygon click → select room
      const hit = (() => {
        for (const room of rooms) {
          if (!room.polygon_pct) continue;
          const polyPx = room.polygon_pct.map((v) => pctToPx(v, pageDims));
          if (pointInPolygonPx(raw, polyPx)) return room.nr;
        }
        return null;
      })();
      // eslint-disable-next-line no-console
      if (window.__DEBUG_CANVAS) console.log('[AnnotationCanvas] click', { raw, hit, n_rooms: rooms.length, pageDims });
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
        // Non-blocking inline notice instead of a modal alert. The
        // calibration wizard (when shipped) will trigger the calibrate
        // flow automatically on first project open.
        // eslint-disable-next-line no-console
        console.warn('[AnnotationCanvas] measure attempted without scale; calibrate first');
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
    const el = canvasElRef.current;
    if (!el) return;
    const p = clientToPagePx(el, e, zoom);
    for (const s of symbols) {
      const sp = pctToPx(s.pos_pct, pageDims);
      if (dist(p, sp) <= 12) { setDraggingSymbolId(s.id); return; }
    }
  };
  const onMouseUp = () => setDraggingSymbolId(null);

  const onContextMenu = (e) => {
    if (tool !== TOOLS.NONE) return;
    e.preventDefault();
    const el = canvasElRef.current;
    if (!el) return;
    const p = clientToPagePx(el, e, zoom);
    for (const s of symbols) {
      const sp = pctToPx(s.pos_pct, pageDims);
      if (dist(p, sp) <= 12) {
        onSymbolDeleted && onSymbolDeleted(s.id);
        return;
      }
    }
  };

  // ── Keyboard: Escape cancels current draft ─────────────────────────────
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setDraftStart(null);
        setCalibrationPoints([]);
        setSnapTarget(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Avoid setting className on the <canvas> via React: Fabric installs
  // its own `lower-canvas` class for hit-testing + style hooks, and any
  // React-set className on re-render wipes Fabric's class. Style is
  // applied via inline cursor + dimensions instead.
  return (
    <canvas
      ref={canvasElRef}
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
      onWheel={onWheel}
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        cursor: tool === TOOLS.NONE ? 'pointer' : 'crosshair',
        width: (pageDims.width || 0) * zoom,
        height: (pageDims.height || 0) * zoom,
      }}
    />
  );
});

export default AnnotationCanvas;

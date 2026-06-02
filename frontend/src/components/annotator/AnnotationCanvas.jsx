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
function clientToCanvasPx(canvasEl, e, zoom) {
  // Convert client-space click → canvas-pixel space (full multi-page
  // height). Canvas CSS is sized to layout.totalSize × zoom; dividing
  // the in-rect offset by `zoom` lands us back in layout coords.
  const rect = canvasEl.getBoundingClientRect();
  return {
    x: (e.clientX - rect.left) / zoom,
    y: (e.clientY - rect.top) / zoom,
  };
}

function pageOfY(layoutPages, canvasY) {
  // Which page contains this canvas-y? Returns the page entry or null.
  for (const p of layoutPages || []) {
    if (canvasY >= p.offsetY && canvasY < p.offsetY + p.height) return p;
  }
  return null;
}

function canvasPxToPagePct(canvasPt, layoutPages) {
  // Returns {pageNum, x_pct, y_pct} or null if outside any page.
  const p = pageOfY(layoutPages, canvasPt.y);
  if (!p) return null;
  return {
    pageNum: p.pageNum,
    x_pct: p.width > 0 ? canvasPt.x / p.width : 0,
    y_pct: p.height > 0 ? (canvasPt.y - p.offsetY) / p.height : 0,
  };
}

function pagePctToCanvasPx(pageNum, pt_pct, layoutPages) {
  const p = (layoutPages || []).find((q) => q.pageNum === pageNum);
  if (!p) return null;
  return {
    x: pt_pct.x_pct * p.width,
    y: p.offsetY + pt_pct.y_pct * p.height,
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

function snapToCorner(cursor, rooms, layoutPages, thresholdPx) {
  // Multi-page: each room's polygon is in pct of its own page; convert to
  // canvas-y coords by offsetting with the room's page.
  let best = null;
  let bestD = thresholdPx;
  for (const room of rooms) {
    if (!room.polygon_pct) continue;
    const pageNum = parseInt(room.puslapio_nr ?? 1, 10);
    const page = (layoutPages || []).find((p) => p.pageNum === pageNum)
      || (layoutPages || [])[0];
    if (!page) continue;
    for (const v of room.polygon_pct) {
      const px = {
        x: v.x_pct * page.width,
        y: page.offsetY + v.y_pct * page.height,
      };
      const d = dist(cursor, px);
      if (d < bestD) {
        bestD = d;
        best = { x: px.x, y: px.y, room_nr: room.nr, room_name: room.name };
      }
    }
  }
  return best;
}

function snapToWallLine(cursor, rooms, layoutPages, thresholdPx) {
  // Perpendicular snap: for every wall segment in every room's polygon,
  // find the foot of perpendicular from cursor. If within threshold,
  // snap there. Returns {x, y, line: [{x,y},{x,y}]} or null.
  let best = null;
  let bestD = thresholdPx;
  for (const room of rooms) {
    if (!room.polygon_pct || room.polygon_pct.length < 2) continue;
    const pageNum = parseInt(room.puslapio_nr ?? 1, 10);
    const page = (layoutPages || []).find((p) => p.pageNum === pageNum)
      || (layoutPages || [])[0];
    if (!page) continue;
    const poly = room.polygon_pct.map((v) => ({
      x: v.x_pct * page.width,
      y: page.offsetY + v.y_pct * page.height,
    }));
    for (let i = 0; i < poly.length; i++) {
      const a = poly[i];
      const b = poly[(i + 1) % poly.length];
      const dx = b.x - a.x, dy = b.y - a.y;
      const len2 = dx*dx + dy*dy;
      if (len2 < 1) continue;
      const t = ((cursor.x - a.x) * dx + (cursor.y - a.y) * dy) / len2;
      if (t < 0 || t > 1) continue;  // foot outside segment — corner snap handles
      const fx = a.x + t * dx, fy = a.y + t * dy;
      const d = Math.hypot(cursor.x - fx, cursor.y - fy);
      if (d < bestD) {
        bestD = d;
        best = { x: fx, y: fy, line: [a, b] };
      }
    }
  }
  return best;
}

function snapToOrthogonal(cursor, anchor, thresholdDeg = 15) {
  // When drawing from anchor → cursor, snap to 0/90/180/270 when the
  // current angle is within thresholdDeg of one. Returns possibly
  // adjusted endpoint, plus a flag for whether a snap happened.
  const dx = cursor.x - anchor.x, dy = cursor.y - anchor.y;
  const angle = (Math.atan2(dy, dx) * 180 / Math.PI + 360) % 360;
  const candidates = [0, 90, 180, 270];
  let chosen = null;
  for (const c of candidates) {
    const diff = Math.min(
      Math.abs(angle - c),
      Math.abs(angle - c - 360),
      Math.abs(angle - c + 360),
    );
    if (diff < thresholdDeg) { chosen = c; break; }
  }
  if (chosen === null) return { x: cursor.x, y: cursor.y, snapped: false };
  const r = Math.hypot(dx, dy);
  const rad = chosen * Math.PI / 180;
  return {
    x: anchor.x + r * Math.cos(rad),
    y: anchor.y + r * Math.sin(rad),
    snapped: true,
    angle: chosen,
  };
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
    // Single-page legacy: pageDims = {width, height}
    // Multi-page: pagesLayout = {pages:[{pageNum,width,height,offsetY}],
    //                            totalWidth, totalHeight}
    pageDims,
    pagesLayout,
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
  // Normalize: caller may supply either pagesLayout (multi-page) or
  // pageDims (legacy single-page). Internally we always use layoutPages
  // as the source-of-truth list of {pageNum,width,height,offsetY}.
  const layoutPages = pagesLayout?.pages || (pageDims && pageDims.width > 0
    ? [{ pageNum: 1, width: pageDims.width, height: pageDims.height, offsetY: 0 }]
    : []);
  const canvasSize = pagesLayout
    ? { width: pagesLayout.totalWidth || 0, height: pagesLayout.totalHeight || 0 }
    : { width: pageDims?.width || 0, height: pageDims?.height || 0 };
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
      // CRITICAL: disable retina scaling on multi-page canvases. With 45+ PDF
      // pages stacked vertically, CSS height × devicePixelRatio quickly
      // exceeds Chrome's 32767-pixel GPU canvas limit; over that limit the
      // canvas is created without error but every draw is silently discarded
      // (polygons / measurements / symbols become invisible). Trading some
      // crispness on retina displays for "polygons actually render" is the
      // right call. See diagnosis 2026-06-02.
      enableRetinaScaling: false,
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
    fc.setDimensions({ width: canvasSize.width, height: canvasSize.height });
    fc.setZoom(zoom);
    fc.requestRenderAll();
  }, [canvasSize.width, canvasSize.height, zoom]);

  // Helper: convert a stored point (with optional pageNum) to canvas px
  const storedPointToCanvasPx = (pt) => {
    const pageNum = pt.pageNum != null ? pt.pageNum : 1;
    const r = pagePctToCanvasPx(pageNum, pt, layoutPages);
    return r || { x: 0, y: 0 };
  };

  // ── Imperative API (unchanged from vanilla impl) ────────────────────────
  useImperativeHandle(ref, () => ({
    snapPxToCorner: (point) => snapToCorner(point, rooms, layoutPages, SNAP_PX),
    snapPxToWallLine: (point) => snapToWallLine(point, rooms, layoutPages, SNAP_PX),
    getCanvasDims: () => canvasSize,
    cancelDraft: () => {
      setDraftStart(null);
      setCalibrationPoints([]);
      setSnapTarget(null);
    },
    hitTestRoomAtPx: (point) => {
      // Click in canvas coords → find which page → check that page's polygons
      const pageEntry = pageOfY(layoutPages, point.y);
      if (!pageEntry) return null;
      for (const room of rooms) {
        const roomPageNum = parseInt(room.puslapio_nr ?? 1, 10);
        if (roomPageNum !== pageEntry.pageNum) continue;
        if (!room.polygon_pct) continue;
        const polyPx = room.polygon_pct.map((v) => ({
          x: v.x_pct * pageEntry.width,
          y: pageEntry.offsetY + v.y_pct * pageEntry.height,
        }));
        if (pointInPolygonPx(point, polyPx)) return room.nr;
      }
      return null;
    },
    hitTestSymbolAtPx: (point) => {
      for (const s of symbols) {
        const sp = storedPointToCanvasPx(s.pos_pct);
        if (dist(point, sp) <= 12) return s.id;
      }
      return null;
    },
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
        const a = storedPointToCanvasPx(m.p1_pct);
        const b = storedPointToCanvasPx(m.p2_pct);
        const d = distPointToSeg(point, a, b);
        if (d < bestD) { bestD = d; best = m.id; }
      }
      return best;
    },
    setMeasurements: () => {},    // controlled by parent; no-op preserved for API parity
    setSymbols: () => {},
  }), [rooms, symbols, layoutPages, canvasSize, measurements]);

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

    // 1. Room polygons (per-page offset)
    for (const room of rooms) {
      if (!room.polygon_pct) continue;
      const pageNum = parseInt(room.puslapio_nr ?? 1, 10);
      const page = layoutPages.find((p) => p.pageNum === pageNum) || layoutPages[0];
      if (!page) continue;
      const polyPx = room.polygon_pct.map((v) => ({
        x: v.x_pct * page.width,
        y: page.offsetY + v.y_pct * page.height,
      }));
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
        objectCaching: true,
      }));
    }

    // 2. Measurements
    for (const m of measurements) {
      const p1 = storedPointToCanvasPx(m.p1_pct);
      const p2 = storedPointToCanvasPx(m.p2_pct);
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

    // 6. Symbols (with optional rotation)
    for (const s of symbols) {
      const pos = storedPointToCanvasPx(s.pos_pct);
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
        angle: s.rotation_deg || 0,
        selectable: false, evented: false, objectCaching: false,
      }));
      // Rotation handle when this symbol is selected
      if (s.id && s.id === window.__selectedSymbolId) {
        fc.add(new fabric.Circle({
          left: pos.x, top: pos.y - 26,
          radius: 6, fill: '#fff', stroke: meta.color, strokeWidth: 2,
          originX: 'center', originY: 'center',
          selectable: false, evented: false, objectCaching: false,
        }));
      }
    }

    fc.requestRenderAll();
  }, [
    rooms, layoutPages, measurements, symbols, calibrationPoints,
    draftStart, cursorPx, snapTarget, hoveredRoomNr, selectedRoomNr,
    selectedMeasurementId, tool, scale,
  ]);

  // ── Mouse handlers (multi-page aware) ───────────────────────────────────
  const onMove = (e) => {
    const el = canvasElRef.current;
    if (!el) return;
    const p = clientToCanvasPx(el, e, zoom);
    setCursorPx(p);

    if (draggingSymbolId) {
      const pageMeta = canvasPxToPagePct(p, layoutPages);
      if (pageMeta) onSymbolMoved && onSymbolMoved(draggingSymbolId, pageMeta);
      return;
    }
    if (tool === TOOLS.NONE) {
      // Multi-page hit-test by page-of-y
      const pageEntry = pageOfY(layoutPages, p.y);
      let hit = null;
      if (pageEntry) {
        for (const room of rooms) {
          const rPage = parseInt(room.puslapio_nr ?? 1, 10);
          if (rPage !== pageEntry.pageNum) continue;
          if (!room.polygon_pct) continue;
          const polyPx = room.polygon_pct.map((v) => ({
            x: v.x_pct * pageEntry.width,
            y: pageEntry.offsetY + v.y_pct * pageEntry.height,
          }));
          if (pointInPolygonPx(p, polyPx)) { hit = room.nr; break; }
        }
      }
      onRoomHover && onRoomHover(hit);
      setSnapTarget(null);
      return;
    }
    if (tool === TOOLS.MEASURE || tool === TOOLS.CALIBRATE || tool === TOOLS.EDIT_WALL) {
      // Snap priority: corner > wall-line > orthogonal-from-draft
      let snap = snapToCorner(p, rooms, layoutPages, SNAP_PX);
      if (!snap) snap = snapToWallLine(p, rooms, layoutPages, 15);
      if (!snap && draftStart && tool === TOOLS.MEASURE) {
        const ortho = snapToOrthogonal(p, draftStart, 8);
        if (ortho.snapped) snap = { x: ortho.x, y: ortho.y, ortho: true };
      }
      setSnapTarget(snap);
    }
  };

  const onClick = (e) => {
    const el = canvasElRef.current;
    if (!el) return;
    const raw = clientToCanvasPx(el, e, zoom);
    const p = snapTarget || raw;

    if (tool === TOOLS.PLACE_SYMBOL && placeSymbolType) {
      const pageMeta = canvasPxToPagePct(raw, layoutPages);
      if (pageMeta) {
        onSymbolPlaced && onSymbolPlaced({
          type: placeSymbolType,
          pos_pct: pageMeta,
        });
      }
      return;
    }

    if (tool === TOOLS.NONE) {
      // 1. Prefer measurement-line click (canvas → list highlight)
      const distPointToSeg = (q, a, b) => {
        const dx = b.x - a.x, dy = b.y - a.y;
        const t = dx === 0 && dy === 0 ? 0
          : Math.max(0, Math.min(1, ((q.x - a.x) * dx + (q.y - a.y) * dy) / (dx*dx + dy*dy)));
        const px = a.x + t * dx, py = a.y + t * dy;
        return Math.hypot(q.x - px, q.y - py);
      };
      let measHit = null, bestD = 8;
      for (const m of measurements) {
        const a = storedPointToCanvasPx(m.p1_pct);
        const b = storedPointToCanvasPx(m.p2_pct);
        const d = distPointToSeg(raw, a, b);
        if (d < bestD) { bestD = d; measHit = m.id; }
      }
      if (measHit && onMeasurementClick) {
        onMeasurementClick(measHit);
        return;
      }
      // 2. Otherwise: room polygon click → select room (multi-page hit-test)
      const pageEntry = pageOfY(layoutPages, raw.y);
      let hit = null;
      if (pageEntry) {
        for (const room of rooms) {
          const rPage = parseInt(room.puslapio_nr ?? 1, 10);
          if (rPage !== pageEntry.pageNum) continue;
          if (!room.polygon_pct) continue;
          const polyPx = room.polygon_pct.map((v) => ({
            x: v.x_pct * pageEntry.width,
            y: pageEntry.offsetY + v.y_pct * pageEntry.height,
          }));
          if (pointInPolygonPx(raw, polyPx)) { hit = room.nr; break; }
        }
      }
      // eslint-disable-next-line no-console
      if (window.__DEBUG_CANVAS) console.log('[AnnotationCanvas] click', { raw, hit, page: pageEntry?.pageNum });
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
        // eslint-disable-next-line no-console
        console.warn('[AnnotationCanvas] measure attempted without scale; calibrate first');
        return;
      }
      if (!draftStart) { setDraftStart(p); return; }
      const lenPx = dist(draftStart, p);
      const lenMm = lenPx * scale;
      const p1Stored = canvasPxToPagePct(draftStart, layoutPages);
      const p2Stored = canvasPxToPagePct(p, layoutPages);
      setDraftStart(null);
      if (p1Stored && p2Stored) {
        onMeasurementComplete && onMeasurementComplete({
          p1_pct: p1Stored,
          p2_pct: p2Stored,
          length_mm: lenMm,
        });
      }
    }
  };

  const onMouseDown = (e) => {
    if (tool !== TOOLS.NONE) return;
    const el = canvasElRef.current;
    if (!el) return;
    const p = clientToCanvasPx(el, e, zoom);
    for (const s of symbols) {
      const sp = storedPointToCanvasPx(s.pos_pct);
      if (dist(p, sp) <= 12) {
        setDraggingSymbolId(s.id);
        // Alt-drag = duplicate
        if (e.altKey && onSymbolPlaced) {
          onSymbolPlaced({
            type: s.type,
            pos_pct: { ...s.pos_pct },
            rotation_deg: s.rotation_deg || 0,
          });
        }
        return;
      }
    }
  };
  const onMouseUp = () => setDraggingSymbolId(null);

  const onContextMenu = (e) => {
    if (tool !== TOOLS.NONE) return;
    e.preventDefault();
    const el = canvasElRef.current;
    if (!el) return;
    const p = clientToCanvasPx(el, e, zoom);
    for (const s of symbols) {
      const sp = storedPointToCanvasPx(s.pos_pct);
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
        width: canvasSize.width * zoom,
        height: canvasSize.height * zoom,
      }}
    />
  );
});

export default AnnotationCanvas;

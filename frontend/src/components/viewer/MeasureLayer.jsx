import { useReducer, useRef, useState, useEffect, useCallback, useMemo } from 'react';
import { toast } from 'sonner';
import { draftReducer } from '@/lib/measureOverlayReducer.js';
import { makeMeasurement, measurementValue } from '@/lib/measurements.js';
import {
  realPathLengthM, shoelaceAreaM2, formatNumberLT, uncalibratedScale, draftCommitPoints,
} from '@/lib/measureGeometry.js';
import {
  nearestEdge,
  orthoSnap,
  pointInPolygon,
  polygonCentroid,
} from '@/lib/polygonGeometry.js';
import { pickSnap } from '@/lib/drawingSnap.js';
import { lassoSelect } from '@/lib/outlineTools.js';
import { flashCursorHint } from '@/lib/cursorHints.js';
import {
  DASH, LABEL_FONT_PX, LABEL_STYLE, SELECTED_STROKE_PX, STROKE_PX, labelWidth, ov, paint,
} from '@/lib/overlayTokens.js';

// v3 overlay vocabulary (lib/overlayTokens): his own measurement keeps the colour he chose (default
// --ov-user); the selection is the heavy neutral ink; a draft's not-yet-placed segment is the one
// dash (proposed); the calibration line and every snap mark are the tool-at-work orange — red is
// left for errors; readouts are white label pills in the app's sans.
const USER = ov('user');
const INK = ov('selected');
const EDITING = ov('editing');

// Tools that build a multi-vertex draft (polyline for line tools, polygon for area).
const POLY_TOOLS = new Set(['distance', 'perimeter', 'area']);

// Pixel tolerance (screen px) for vertex/edge snap, poly-close, and select hit-testing.
const SNAP_TOL_PX = 8;

const EMPTY_DRAFT = { points: [], committed: false };

/**
 * MeasureLayer (ported verbatim from backup MeasureOverlay) — standalone, fully props-driven SVG overlay for the measurement
 * tools (distance / perimeter / area / count). Committed measurements live
 * upstream and arrive via props. All geometry is in PDF-point space — the
 * adapter is the single screen<->PDF boundary.
 *
 * DRAFT OWNERSHIP (audit P1): this component is mounted PER PAGE and unmounts
 * as soon as the page leaves the scroll virtualization buffer (±2 pages) — an
 * in-progress draft (and the first calibration click) used to die with it. Both
 * are therefore CONTROLLED by TakeoffViewer when it passes `onDraftAction` /
 * `onCalibAChange`; without those props the component keeps its own state so it
 * stays usable standalone (test harness).
 *
 * It does NOT import PlanViewer so it can be mounted in a test harness.
 */
export default function MeasureLayer({
  adapter,
  pageNr,
  tool,
  scale = uncalibratedScale(),
  measurements = [],
  countTypes = [],
  activeCountTypeId = null,
  snapEnabled = false,
  orthoEnabled = false,
  // The drawing's wall solid as snap polygons in PDF points (lib/drawingSnap) — [] when the sheet has
  // no vector walls or the geometry has not arrived yet. Snapped BEFORE the user's own measurements.
  drawingSnapPolygons = [],
  onCommit,
  onCalibrate,
  onSelect,
  onDelete,
  selectedId = null,
  // Lasso (2026-10-16): the selection can hold several marks — `selectedIds` wins over `selectedId`.
  selectedIds = null,
  display = { decimals: 2 },
  // Controlled draft / calibration-A (lifted to TakeoffViewer, see above).
  draft: draftProp = null,
  onDraftAction = null,
  calibA: calibAProp = null,
  onCalibAChange = null,
}) {
  const svgRef = useRef(null);
  const decimals = display?.decimals ?? 2;

  const [localDraft, localDispatch] = useReducer(draftReducer, EMPTY_DRAFT);
  const [localCalibA, setLocalCalibA] = useState(null);
  const controlled = typeof onDraftAction === 'function';
  const draft = controlled ? (draftProp || EMPTY_DRAFT) : localDraft;
  const dispatch = controlled ? onDraftAction : localDispatch;
  const calibA = onCalibAChange ? calibAProp : localCalibA;   // first calibration point (PDF space)
  const setCalibA = onCalibAChange || setLocalCalibA;
  const [cursor, setCursor] = useState(null);   // snapped PDF point under the pointer
  const [snapPt, setSnapPt] = useState(null);    // PDF point where a snap fired (for the indicator dot)
  const [snapKind, setSnapKind] = useState(null); // drawing-vertex | drawing-edge | measure-vertex | measure-edge
  const [lasso, setLasso] = useState(null);       // {px: [{x, y}], add} while a lasso is being drawn
  // Right-click while drawing (v3 W1-B B5, Kreo „Create / Reset"): „Baigti" / „Atšaukti" at the pointer.
  const [finishMenu, setFinishMenu] = useState(null);   // {x, y} in SVG px, or null
  const selectedSet = useMemo(
    () => new Set(Array.isArray(selectedIds) ? selectedIds : (selectedId != null ? [selectedId] : [])),
    [selectedIds, selectedId],
  );

  // Reset the draft whenever the active tool changes. In controlled mode the
  // OWNER resets (this component re-mounts on every scroll-back, and resetting
  // here would wipe the very draft the lift is meant to preserve).
  useEffect(() => {
    if (!controlled) {
      localDispatch({ type: 'reset' });
      setLocalCalibA(null);
    }
    setCursor(null);
    setSnapPt(null); setSnapKind(null);
  }, [tool]);

  // ---- coordinate + snapping helpers -------------------------------------

  // Committed line/area measurements on THIS page, in the {id, points} shape the
  // polygonGeometry snap helpers expect. `open` marks polylines so their
  // non-existent closing edge never attracts a snap (audit P2).
  const snapPolygons = useMemo(
    () => measurements
      .filter((m) => m.page === pageNr && (m.kind === 'distance' || m.kind === 'perimeter' || m.kind === 'area'))
      .map((m) => ({ id: m.id, points: m.points, open: m.kind !== 'area' })),
    [measurements, pageNr],
  );

  const eventToPdf = useCallback((e) => {
    const svg = svgRef.current;
    if (!svg) return { x: 0, y: 0 };
    const rect = svg.getBoundingClientRect();
    return adapter.toPdf({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }, [adapter]);

  // Apply vertex/edge snapping then ortho snapping. Returns { point, snapped, snapKind }.
  // Order (lib/drawingSnap.pickSnap): a wall corner of the drawing, a measurement vertex, a wall face,
  // a measurement edge — the drawing wins because it is what the person is measuring.
  const applySnap = useCallback((raw, e) => {
    const tol = SNAP_TOL_PX / (adapter?.scale || 1);
    let point = raw;
    let snapped = false;
    let snapKind = null;

    if (snapEnabled && (drawingSnapPolygons.length || snapPolygons.length)) {
      const hit = pickSnap(raw, { drawing: drawingSnapPolygons, measurements: snapPolygons }, tol);
      if (hit) {
        point = hit.point;
        snapped = true;
        snapKind = hit.kind;
      }
    }

    const shiftHeld = !!(e && e.shiftKey);
    const altHeld = !!(e && e.altKey);
    if ((orthoEnabled || shiftHeld) && POLY_TOOLS.has(tool) && draft.points.length > 0) {
      const prev = draft.points[draft.points.length - 1];
      // orthoSnap (from polygonGeometry) passes through when orthoEnabled is false,
      // so OR in shiftHeld. It rounds to integers — acceptable: in PDF-point space the
      // sub-point rounding is well below drawing precision.
      point = orthoSnap(prev, point, { orthoEnabled: orthoEnabled || shiftHeld, shiftHeld, altHeld });
    }
    return { point, snapped, snapKind };
  }, [adapter?.scale, snapEnabled, snapPolygons, drawingSnapPolygons, orthoEnabled, tool, draft.points]);

  // ---- pointer handlers ---------------------------------------------------

  const commitDraft = useCallback((points) => {
    if (!onCommit) return;
    // Dedupe coincident vertices, then enforce the PER-KIND minimum: a 2-click
    // 'area' must not commit as a degenerate 0,00 m² polygon (audit P2).
    const pts = draftCommitPoints(points, tool);
    if (pts) onCommit(makeMeasurement(tool, pageNr, pts));
    dispatch({ type: 'reset' });
    setCursor(null);
    setSnapPt(null); setSnapKind(null);
  }, [onCommit, tool, pageNr, dispatch]);

  const localPx = useCallback((e) => {
    const rect = svgRef.current.getBoundingClientRect();
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  const handlePointerMove = useCallback((e) => {
    if (tool === 'lasso') {
      if (!lasso) return;
      const p = localPx(e);
      const last = lasso.px[lasso.px.length - 1];
      if (Math.hypot(p.x - last.x, p.y - last.y) >= 3) setLasso((cur) => (cur ? { ...cur, px: [...cur.px, p] } : cur));
      return;
    }
    if (tool === 'pan' || tool === 'select') {
      setCursor(null);
      return;
    }
    const { point, snapped, snapKind: kind } = applySnap(eventToPdf(e), e);
    setCursor(point);
    setSnapPt(snapped ? point : null);
    setSnapKind(snapped ? kind : null);
  }, [tool, applySnap, eventToPdf, lasso, localPx]);

  const handlePointerDown = useCallback((e) => {
    if (tool === 'pan') return;

    if (tool === 'lasso') {
      if (e.button !== 0) return;     // a right-click opens the menu for the selection, it starts no loop
      // Freehand loop: everything wholly inside it is selected (Shift adds to the selection). A click
      // without a drag picks the one mark under it, like „Žymėti".
      try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* pointer already gone */ }
      setLasso({ px: [localPx(e)], add: e.shiftKey });
      return;
    }

    if (tool === 'select') {
      const raw = eventToPdf(e);
      const hitId = hitTest(raw, measurements, pageNr, SNAP_TOL_PX / adapter.scale);
      onSelect?.(hitId);
      return;
    }

    // Only the main button draws (a right-click used to drop a vertex or a mark under the menu).
    if (e.button !== 0) return;
    // The right-click pop-up is open: a click beside it closes it and adds nothing.
    if (finishMenu) { setFinishMenu(null); return; }

    const { point } = applySnap(eventToPdf(e), e);

    if (tool === 'calibrate') {
      if (!calibA) {
        setCalibA(point);
      } else if (Math.hypot(point.x - calibA.x, point.y - calibA.y) <= SNAP_TOL_PX / (adapter?.scale || 1)) {
        // Second click landed ON the first one (audit P1: a double-click armed
        // the dialog with a zero-length line, whose Patvirtinti then threw and
        // did nothing). Ignore it and keep waiting for a real B point — and say so at the pointer.
        flashCursorHint('Taškai sutampa — spustelėkite kitą atkarpos galą');
        return;
      } else {
        onCalibrate?.(pageNr, calibA, point);
        setCalibA(null);
        setCursor(null);
        setSnapPt(null); setSnapKind(null);
      }
      return;
    }

    if (tool === 'count') {
      if (!activeCountTypeId) { flashCursorHint('Nieko nepažymėta: pirmiausia pasirinkite arba sukurkite tipą kairėje'); return; }
      // Place/remove toggle (founder 2026-07-12: "no way to delete them"):
      // clicking ON an existing count dot removes THAT dot instead of stacking
      // a new one next to it — no separate eraser or select-tool detour needed.
      // Hit-test against the RAW (unsnapped) click, like the select tool.
      // ONLY marks of the ACTIVE type are eligible: deleting a neighbouring
      // rozetė while counting jungikliai was silent data loss (audit P1).
      const hitId = hitTest(
        eventToPdf(e),
        measurements.filter((m) => m.kind === 'count' && m.typeId === activeCountTypeId),
        pageNr,
        SNAP_TOL_PX / adapter.scale,
      );
      if (hitId) { onDelete?.(hitId); toast.info('Žymė pašalinta'); return; }
      const type = countTypes.find((t) => t.id === activeCountTypeId) || {};
      onCommit?.(makeMeasurement('count', pageNr, [point], {
        typeId: activeCountTypeId,
        color: type.color,
        confidence: 'green',
      }));
      return;
    }

    if (POLY_TOOLS.has(tool)) {
      // Distance ends on its second click (v3 W1-B B5); Shift + click keeps the chain going instead, and the
      // next plain click ends it there.
      if (tool === 'distance' && draft.points.length >= 1 && !e.shiftKey) {
        commitDraft([...draft.points, point]);
        return;
      }
      const closeTolerance = SNAP_TOL_PX / adapter.scale;
      const next = draftReducer(draft, { type: 'click', tool, point, closeTolerance });
      if (next.committed) {
        commitDraft(next.points);
      } else {
        dispatch({ type: 'click', tool, point, closeTolerance });
      }
    }
  }, [tool, eventToPdf, applySnap, measurements, pageNr, adapter?.scale, onSelect, onDelete, activeCountTypeId, countTypes, onCommit, onCalibrate, calibA, setCalibA, draft, dispatch, commitDraft, localPx, finishMenu]);

  const handlePointerUp = useCallback((e) => {
    if (tool !== 'lasso' || !lasso) return;
    const loop = lasso.px;
    const prev = [...selectedSet];
    setLasso(null);
    let ids;
    if (loop.length < 3) {
      const hit = hitTest(eventToPdf(e), measurements, pageNr, SNAP_TOL_PX / adapter.scale);
      ids = hit ? [hit] : [];
    } else {
      ids = lassoSelect(measurements, pageNr, loop.map((p) => adapter.toPdf(p)));
    }
    onSelect?.(lasso.add ? [...new Set([...prev, ...ids])] : ids);
  }, [tool, lasso, selectedSet, eventToPdf, measurements, pageNr, adapter, onSelect]);

  const handleDoubleClick = useCallback((e) => {
    if (!POLY_TOOLS.has(tool)) return;
    e.preventDefault();
    const finished = draftReducer(draft, { type: 'finish', tool });
    if (finished.committed) commitDraft(finished.points);
    else if (draft.points.length) flashCursorHint(tool === 'area' ? 'Plotui reikia bent 3 taškų' : 'Reikia bent 2 taškų');
  }, [tool, draft, commitDraft]);

  // Explicit on-canvas Baigti/Atšaukti (founder 2026-07-25: "no buttons on how
  // to stop" — double-click and Esc were the only exits, and neither is
  // discoverable). Same code paths as dblclick / Escape.
  const finishDraft = useCallback(() => {
    const finished = draftReducer(draft, { type: 'finish', tool });
    if (finished.committed) commitDraft(finished.points);
  }, [tool, draft, commitDraft]);
  const cancelDraft = useCallback(() => {
    dispatch({ type: 'reset' });
    setCursor(null);
    setSnapPt(null); setSnapKind(null);
  }, [dispatch]);
  const draftMinPoints = tool === 'area' ? 3 : 2;
  const draftFinishable = POLY_TOOLS.has(tool) && draft.points.length >= draftMinPoints;
  const drafting = POLY_TOOLS.has(tool) && draft.points.length > 0;
  // Right-click while drawing → „Baigti" / „Atšaukti" at the pointer. Off a draft the right-click stays the
  // measurement menu (PageOverlayHost) — this handler lets it through.
  const handleContextMenu = useCallback((e) => {
    if (!drafting) return;
    e.preventDefault();
    e.stopPropagation();
    setFinishMenu(localPx(e));
  }, [drafting, localPx]);
  // The pop-up closes with the draft (finished, cancelled, stepped back to nothing, tool changed).
  useEffect(() => { if (!drafting) setFinishMenu(null); }, [drafting]);
  // Esc closes the pop-up only — the draft keeps its points (the viewer's Esc step never sees this press).
  useEffect(() => {
    if (!finishMenu) return undefined;
    const onKey = (e) => {
      if (e.key !== 'Escape') return;
      e.preventDefault();
      e.stopPropagation();
      setFinishMenu(null);
    };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [finishMenu]);

  // Keyboard: Enter = finish, z / Backspace = undo a point. Bound to window while a
  // poly tool is active so the user need not focus the SVG. Esc is NOT here (v3 W1-B B4): the viewer's
  // one Esc step (lib/escOrder) removes the last point, and leaves the tool only when none is left.
  // Bound ONLY on the page that owns a non-empty draft: this component is
  // mounted once per virtualized page, and with the draft lifted upstream every
  // mounted copy would otherwise apply the same undo/finish (5 pages = 5 undos).
  useEffect(() => {
    if (!POLY_TOOLS.has(tool) || draft.points.length === 0) return undefined;
    const onKey = (e) => {
      if (e.target?.closest?.('input, textarea, select, [contenteditable]')) return;
      if (e.key === 'Enter') {
        const finished = draftReducer(draft, { type: 'finish', tool });
        if (finished.committed) commitDraft(finished.points);
      } else if (e.key === 'z' && !e.metaKey && !e.ctrlKey && !e.altKey) {
        dispatch({ type: 'undo' });
      } else if (e.key === 'Backspace') {
        e.preventDefault();
        dispatch({ type: 'undo' });
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tool, draft, dispatch, commitDraft]);

  // ---- render -------------------------------------------------------------

  const pageMeasurements = useMemo(
    () => measurements.filter((m) => m.page === pageNr),
    [measurements, pageNr],
  );

  if (!adapter) return null;

  return (
    <svg
      ref={svgRef}
      width={adapter.width}
      height={adapter.height}
      role="application"
      aria-label="Matavimo sluoksnis"
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: tool === 'pan' ? 'none' : 'auto',
        cursor: tool === 'select' ? 'default' : 'crosshair',
      }}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={() => setLasso(null)}
      onPointerLeave={() => setCursor(null)}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleContextMenu}
    >
      {pageMeasurements.map((m) => (
        <CommittedMeasurement
          key={m.id}
          m={m}
          adapter={adapter}
          scale={scale}
          countTypes={countTypes}
          selected={selectedSet.has(m.id)}
          decimals={decimals}
        />
      ))}

      <DraftLayer
        tool={tool}
        draft={draft}
        cursor={cursor}
        adapter={adapter}
        scale={scale}
        snapPt={snapPt}
        snapKind={snapKind}
        decimals={decimals}
      />

      {/* „Baigti" / „Atšaukti" live in the mode pill at the bottom of the drawing (v3 W1-B B2), always visible
          there; a right-click while drawing brings the same two to the pointer (B5). */}
      {finishMenu && drafting && (
        <DraftActions
          lastPt={finishMenu}
          width={adapter.width}
          height={adapter.height}
          finishable={draftFinishable}
          onFinish={() => { setFinishMenu(null); finishDraft(); }}
          onCancel={() => { setFinishMenu(null); cancelDraft(); }}
        />
      )}

      {lasso && lasso.px.length > 1 && (
        <polygon
          points={lasso.px.map((p) => `${p.x},${p.y}`).join(' ')}
          style={paint({ fill: INK, stroke: INK })} fillOpacity={0.06} strokeOpacity={0.7} strokeWidth={1.5}
          pointerEvents="none" data-lasso
        />
      )}

      {tool === 'calibrate' && (
        <CalibrationLayer
          calibA={calibA}
          cursor={cursor}
          adapter={adapter}
          snapPt={snapPt}
          snapKind={snapKind}
        />
      )}
    </svg>
  );
}

// The right-click pop-up while drawing: Baigti / Atšaukti beside the pointer (v3 W1-B B5). SVG-native
// (this layer is an <svg>), stopPropagation on pointerdown+click so pressing a
// button never adds a draft vertex underneath it. Clamped inside the page.
function DraftActions({ lastPt, width, height, finishable, onFinish, onCancel }) {
  const W = 168, H = 32;
  const x = Math.min(Math.max(lastPt.x + 14, 4), Math.max(4, width - W - 4));
  const y = Math.min(Math.max(lastPt.y - H - 12, 4), Math.max(4, height - H - 4));
  const stop = (e) => { e.stopPropagation(); };
  const btn = (bx, bw, label, enabled, onClick, primary, hint) => (
    <g
      transform={`translate(${bx}, 0)`}
      style={{ cursor: enabled ? 'pointer' : 'not-allowed', pointerEvents: 'auto' }}
      onPointerDown={stop}
      onDoubleClick={stop}
      onClick={(e) => { stop(e); if (enabled) onClick(); }}
      role="menuitem"
      aria-label={label}
      aria-disabled={!enabled}
    >
      {/* SVG <title> is the native tooltip inside an <svg>. "Baigti" greys out
          until the shape has enough points and said nothing about why —
          the hint now names the missing step. (2026-07-28.) */}
      <title>{hint}</title>
      <rect width={bw} height={H} rx={2}
        style={primary
          ? { fill: 'hsl(var(--primary))', opacity: enabled ? 1 : 0.45 }
          : paint({ fill: ov('label-bg'), stroke: 'hsl(var(--border-strong))' })}
        strokeWidth={primary ? 0 : 1} />
      <text x={bw / 2} y={H / 2 + 1} textAnchor="middle" dominantBaseline="central"
        fontSize={14} fontWeight={600}
        style={{ ...LABEL_STYLE, fill: primary ? 'hsl(var(--primary-foreground))' : ov('label-fg'), pointerEvents: 'none', userSelect: 'none' }}>{label}</text>
    </g>
  );
  return (
    <g transform={`translate(${x}, ${y})`} style={{ pointerEvents: 'none' }} data-draft-menu role="menu" aria-label="Braižomas matavimas">
      <rect x={-4} y={-4} width={W + 8} height={H + 8} rx={4}
        style={paint({ fill: ov('label-bg'), stroke: 'hsl(var(--border))' })} fillOpacity={0.96} strokeWidth={1} />
      {btn(0, 84, 'Baigti', finishable, onFinish, true,
        finishable
          ? 'Užbaigti matavimą ir įrašyti rezultatą (arba dukart spustelėkite)'
          : 'Pažymėkite dar bent vieną tašką, tada galėsite baigti')}
      {btn(92, 76, 'Atšaukti', true, onCancel, false,
        'Atsisakyti šio matavimo — nubrėžti taškai bus ištrinti (Esc)')}
    </g>
  );
}

// Hit-test committed measurements (this page) for select mode. Area → point in
// polygon; line → nearest edge within tolerance. Returns id or null.
// Exported for the right-click menu (PageOverlayHost), which hit-tests while no tool is armed.
export const MEASURE_HIT_TOL_PX = SNAP_TOL_PX;
export function hitTest(raw, measurements, pageNr, tol) {
  const page = measurements.filter((m) => m.page === pageNr);
  // Count markers: hit within tol of the point.
  for (const m of page) {
    if (m.kind === 'count' && m.points[0]) {
      if (Math.hypot(m.points[0].x - raw.x, m.points[0].y - raw.y) <= tol) return m.id;
    }
  }
  // Area bodies.
  for (const m of page) {
    if (m.kind === 'area' && pointInPolygon(raw, m.points)) return m.id;
  }
  // Lines: nearest edge. `open` — a polyline has no closing segment, so a click
  // in the empty span between its last and first vertex must not select it.
  const lines = page
    .filter((m) => m.kind === 'distance' || m.kind === 'perimeter')
    .map((m) => ({ id: m.id, points: m.points, open: true }));
  const edge = nearestEdge(raw, lines, tol);
  if (edge) return edge.polygonId;
  return null;
}

// ---- pure SVG sub-renderers ----------------------------------------------

function CommittedMeasurement({ m, adapter, scale, countTypes, selected, decimals }) {
  if (m.kind === 'count') {
    return <CountMarker m={m} adapter={adapter} countTypes={countTypes} selected={selected} />;
  }

  const sp = m.points.map((p) => adapter.toViewport(p));
  if (sp.length === 0) return null;
  const closed = m.kind === 'area';
  const d = pathD(sp, closed);

  const { value } = measurementValue(m, scale);
  // An uncalibrated page has no real meters — say so instead of lying "0,00 m"
  // (audit P1). The draft chip already does this; committed labels now match.
  const label = !scale?.calibrated
    ? 'nekalibruota'
    : closed
      ? `${formatNumberLT(value, decimals)} m²`
      : `${formatNumberLT(value, decimals)} m`;

  const labelAt = closed
    ? (() => { const c = polygonCentroid(m.points); return c ? adapter.toViewport(c) : sp[0]; })()
    : midOf(sp);

  // his colour stays his; the selection lays the heavy neutral ink under it (a casing), so both read
  const stroke = m.color || USER;

  return (
    <g pointerEvents="none" data-measurement={m.id}>
      {selected && (
        <path d={d} fill="none" style={paint({ stroke: INK })} strokeWidth={SELECTED_STROKE_PX + 3} strokeLinejoin="round" strokeLinecap="round" />
      )}
      <path
        d={d}
        style={paint({ fill: closed ? stroke : null, stroke })}
        fill={closed ? undefined : 'none'}
        fillOpacity={closed ? 0.12 : 0}
        strokeWidth={STROKE_PX}
        strokeLinejoin="round"
      />
      {sp.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={selected ? 4 : 3} style={paint({ fill: stroke, stroke: selected ? INK : null })} strokeWidth={selected ? 1.5 : 0} />
      ))}
      <ReadoutChip x={labelAt.x} y={labelAt.y} text={label} selected={selected} />
    </g>
  );
}

function CountMarker({ m, adapter, countTypes, selected }) {
  const p0 = m.points[0];
  if (!p0) return null;
  const { x, y } = adapter.toViewport(p0);
  const type = countTypes.find((t) => t.id === m.typeId) || {};
  const color = m.color || type.color || USER;
  const shape = type.shape || 'circle';
  const r = selected ? 8 : 6;
  const stroke = selected ? INK : color;
  // „Rasti panašius" marks are found by shape, not checked: same type colour, drawn
  // hollow (white fill, thick outline) so they never pass for hand-placed ones.
  if (m.source === 'symbol_search') {
    const w = selected ? 2.5 : 2;
    const hollow = shape === 'square'
      ? <rect x={x - r} y={y - r} width={r * 2} height={r * 2} style={paint({ fill: ov('label-bg'), stroke })} fillOpacity={0.85} strokeWidth={w} />
      : shape === 'diamond'
        ? <path d={`M ${x} ${y - r} L ${x + r} ${y} L ${x} ${y + r} L ${x - r} ${y} Z`} style={paint({ fill: ov('label-bg'), stroke })} fillOpacity={0.85} strokeWidth={w} />
        : <circle cx={x} cy={y} r={r} style={paint({ fill: ov('label-bg'), stroke })} fillOpacity={0.85} strokeWidth={w} />;
    return <g pointerEvents="none" data-ai-mark>{hollow}</g>;
  }

  let mark;
  if (shape === 'square') {
    mark = <rect x={x - r} y={y - r} width={r * 2} height={r * 2} style={paint({ fill: color, stroke })} strokeWidth={selected ? 2 : 1} />;
  } else if (shape === 'diamond') {
    mark = <path d={`M ${x} ${y - r} L ${x + r} ${y} L ${x} ${y + r} L ${x - r} ${y} Z`} style={paint({ fill: color, stroke })} strokeWidth={selected ? 2 : 1} />;
  } else if (shape === 'check') {
    mark = (
      <g>
        <circle cx={x} cy={y} r={r} fill="none" style={paint({ stroke: selected ? INK : color })} strokeWidth={selected ? 2 : 1.5} />
        <path d={`M ${x - r * 0.5} ${y} L ${x - r * 0.1} ${y + r * 0.45} L ${x + r * 0.6} ${y - r * 0.5}`} fill="none" style={paint({ stroke: color })} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </g>
    );
  } else {
    mark = <circle cx={x} cy={y} r={r} style={paint({ fill: color, stroke })} strokeWidth={selected ? 2 : 1} />;
  }
  return <g pointerEvents="none">{mark}</g>;
}

function DraftLayer({ tool, draft, cursor, adapter, scale, snapPt, snapKind = null, decimals }) {
  if (!POLY_TOOLS.has(tool)) {
    // Still show the snap indicator for non-poly tools that snap (the count tool on a wall corner).
    return snapPt ? <SnapDot p={adapter.toViewport(snapPt)} kind={snapKind} /> : null;
  }
  const sp = draft.points.map((p) => adapter.toViewport(p));
  const liveScreen = sp.length ? [...sp, ...(cursor ? [adapter.toViewport(cursor)] : [])] : [];
  const closed = tool === 'area';

  // Live readout uses PDF points + cursor.
  const livePts = cursor ? [...draft.points, cursor] : draft.points;
  let chip = null;
  if (livePts.length >= 1 && cursor) {
    const len = realPathLengthM(livePts, scale, false);
    if (!scale.calibrated) {
      // Dead-end message → tell them the fix. The Mastelis tool is one click
      // away in the same palette. (2026-07-28 explainability pass.)
      chip = 'Mastelis nenustatytas — pasirinkite įrankį „Mastelis"';
    } else if (closed) {
      const area = shoelaceAreaM2(livePts, scale);
      chip = `Plotas: ${formatNumberLT(area, decimals)} m² · Perimetras: ${formatNumberLT(len, decimals)} m`;
    } else {
      chip = `Ilgis: ${formatNumberLT(len, decimals)} m`;
    }
  }

  const cur = cursor ? adapter.toViewport(cursor) : null;

  return (
    <g>
      {sp.length > 0 && (
        <polyline
          points={sp.map((p) => `${p.x},${p.y}`).join(' ')}
          fill="none"
          style={paint({ stroke: USER })}
          strokeWidth={STROKE_PX}
        />
      )}
      {/* rubber-band from last vertex to cursor */}
      {liveScreen.length >= 2 && (
        <line
          x1={liveScreen[liveScreen.length - 2].x}
          y1={liveScreen[liveScreen.length - 2].y}
          x2={liveScreen[liveScreen.length - 1].x}
          y2={liveScreen[liveScreen.length - 1].y}
          style={paint({ stroke: USER })}
          strokeWidth={1.5}
          strokeDasharray={DASH}
        />
      )}
      {/* faint closing segment back to the first vertex (area only) */}
      {closed && sp.length >= 2 && cur && (
        <line
          x1={cur.x}
          y1={cur.y}
          x2={sp[0].x}
          y2={sp[0].y}
          style={paint({ stroke: USER })}
          strokeWidth={1}
          strokeDasharray={DASH}
          strokeOpacity={0.5}
        />
      )}
      {sp.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} style={paint({ fill: USER })} />
      ))}
      {snapPt && <SnapDot p={adapter.toViewport(snapPt)} kind={snapKind} />}
      {chip && cur && <ReadoutChip x={cur.x + 12} y={cur.y - 12} text={chip} anchor="start" />}
    </g>
  );
}

// Calibration draft: a distinct 2-point line in the tool-at-work orange (visually separate from the
// measurement drafts; red is for errors only). First point A is fixed; a rubber-band follows the
// cursor until the second click, which is handled upstream via onCalibrate.
function CalibrationLayer({ calibA, cursor, adapter, snapPt, snapKind = null }) {
  const a = calibA ? adapter.toViewport(calibA) : null;
  const c = cursor ? adapter.toViewport(cursor) : null;
  return (
    <g pointerEvents="none">
      {a && c && (
        <line
          x1={a.x}
          y1={a.y}
          x2={c.x}
          y2={c.y}
          style={paint({ stroke: EDITING })}
          strokeWidth={STROKE_PX}
        />
      )}
      {a && <circle cx={a.x} cy={a.y} r={4} style={paint({ fill: EDITING })} />}
      {c && <circle cx={c.x} cy={c.y} r={3} style={paint({ fill: EDITING })} fillOpacity={0.7} />}
      {snapPt && <SnapDot p={adapter.toViewport(snapPt)} kind={snapKind} />}
    </g>
  );
}

function SnapDot({ p, kind = null }) {
  // One colour for every snap mark (the tool-at-work orange) — the SHAPE says what the click will land
  // on: a wall corner of the DRAWING is a square, a wall face a diamond, his own measurement a circle.
  if (kind === 'drawing-vertex' || kind === 'drawing-edge') {
    const r = kind === 'drawing-vertex' ? 6 : 5;
    return (
      <rect
        x={p.x - r} y={p.y - r} width={r * 2} height={r * 2}
        fill="none" style={paint({ stroke: EDITING })} strokeWidth={STROKE_PX} pointerEvents="none"
        transform={kind === 'drawing-edge' ? `rotate(45 ${p.x} ${p.y})` : undefined}
      />
    );
  }
  return (
    <circle cx={p.x} cy={p.y} r={5} fill="none" style={paint({ stroke: EDITING })} strokeWidth={STROKE_PX} pointerEvents="none" />
  );
}

function ReadoutChip({ x, y, text, anchor = 'middle', selected = false }) {
  // A neutral label pill (white, slate ink, the app's sans, tabular numbers) — the overlay vocabulary's
  // one label; a selected measurement's pill takes the selection's ink border.
  const w = labelWidth(text);
  const h = 20;
  const rx = anchor === 'start' ? x - 6 : x - w / 2;
  return (
    <g pointerEvents="none">
      <rect x={rx} y={y - h + 5} width={w} height={h} rx={2}
        style={paint({ fill: ov('label-bg'), stroke: selected ? INK : ov('selected', 0.35) })}
        fillOpacity={0.96} strokeWidth={selected ? 1.5 : 1} />
      <text
        x={anchor === 'start' ? x + 1 : x}
        y={y - 1}
        textAnchor={anchor}
        fontSize={LABEL_FONT_PX}
        fontWeight={500}
        style={{ ...LABEL_STYLE, ...paint({ fill: ov('label-fg') }) }}
      >
        {text}
      </text>
    </g>
  );
}

// SVG path string from screen points.
function pathD(sp, closed) {
  if (!sp.length) return '';
  const d = sp.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  return closed ? `${d} Z` : d;
}

function midOf(sp) {
  if (!sp.length) return { x: 0, y: 0 };
  const mid = sp[Math.floor(sp.length / 2)];
  return mid;
}

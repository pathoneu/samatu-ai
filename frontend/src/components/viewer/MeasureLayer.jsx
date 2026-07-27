import { useReducer, useRef, useState, useEffect, useCallback, useMemo } from 'react';
import { toast } from 'sonner';
import { draftReducer } from '@/lib/measureOverlayReducer.js';
import { makeMeasurement, measurementValue } from '@/lib/measurements.js';
import {
  realPathLengthM, shoelaceAreaM2, formatNumberLT, uncalibratedScale, draftCommitPoints,
} from '@/lib/measureGeometry.js';
import {
  nearestVertex,
  nearestEdge,
  orthoSnap,
  pointInPolygon,
  polygonCentroid,
} from '@/lib/polygonGeometry.js';

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
  onCommit,
  onCalibrate,
  onSelect,
  onDelete,
  selectedId = null,
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

  // Reset the draft whenever the active tool changes. In controlled mode the
  // OWNER resets (this component re-mounts on every scroll-back, and resetting
  // here would wipe the very draft the lift is meant to preserve).
  useEffect(() => {
    if (!controlled) {
      localDispatch({ type: 'reset' });
      setLocalCalibA(null);
    }
    setCursor(null);
    setSnapPt(null);
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

  // Apply vertex/edge snapping then ortho snapping. Returns { point, snapped }.
  const applySnap = useCallback((raw, e) => {
    const tol = SNAP_TOL_PX / (adapter?.scale || 1);
    let point = raw;
    let snapped = false;

    if (snapEnabled && snapPolygons.length) {
      const v = nearestVertex(raw, snapPolygons, tol);
      const edge = v ? null : nearestEdge(raw, snapPolygons, tol);
      const hit = v || edge;
      if (hit) {
        point = hit.point;
        snapped = true;
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
    return { point, snapped };
  }, [adapter?.scale, snapEnabled, snapPolygons, orthoEnabled, tool, draft.points]);

  // ---- pointer handlers ---------------------------------------------------

  const commitDraft = useCallback((points) => {
    if (!onCommit) return;
    // Dedupe coincident vertices, then enforce the PER-KIND minimum: a 2-click
    // 'area' must not commit as a degenerate 0,00 m² polygon (audit P2).
    const pts = draftCommitPoints(points, tool);
    if (pts) onCommit(makeMeasurement(tool, pageNr, pts));
    dispatch({ type: 'reset' });
    setCursor(null);
    setSnapPt(null);
  }, [onCommit, tool, pageNr, dispatch]);

  const handlePointerMove = useCallback((e) => {
    if (tool === 'pan' || tool === 'select') {
      setCursor(null);
      return;
    }
    const { point, snapped } = applySnap(eventToPdf(e), e);
    setCursor(point);
    setSnapPt(snapped ? point : null);
  }, [tool, applySnap, eventToPdf]);

  const handlePointerDown = useCallback((e) => {
    if (tool === 'pan') return;

    if (tool === 'select') {
      const raw = eventToPdf(e);
      const hitId = hitTest(raw, measurements, pageNr, SNAP_TOL_PX / adapter.scale);
      onSelect?.(hitId);
      return;
    }

    const { point } = applySnap(eventToPdf(e), e);

    if (tool === 'calibrate') {
      if (!calibA) {
        setCalibA(point);
      } else if (Math.hypot(point.x - calibA.x, point.y - calibA.y) <= SNAP_TOL_PX / (adapter?.scale || 1)) {
        // Second click landed ON the first one (audit P1: a double-click armed
        // the dialog with a zero-length line, whose Patvirtinti then threw and
        // did nothing). Ignore it and keep waiting for a real B point.
        return;
      } else {
        onCalibrate?.(pageNr, calibA, point);
        setCalibA(null);
        setCursor(null);
        setSnapPt(null);
      }
      return;
    }

    if (tool === 'count') {
      if (!activeCountTypeId) return;
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
      const closeTolerance = SNAP_TOL_PX / adapter.scale;
      const next = draftReducer(draft, { type: 'click', tool, point, closeTolerance });
      if (next.committed) {
        commitDraft(next.points);
      } else {
        dispatch({ type: 'click', tool, point, closeTolerance });
      }
    }
  }, [tool, eventToPdf, applySnap, measurements, pageNr, adapter?.scale, onSelect, onDelete, activeCountTypeId, countTypes, onCommit, onCalibrate, calibA, setCalibA, draft, dispatch, commitDraft]);

  const handleDoubleClick = useCallback((e) => {
    if (!POLY_TOOLS.has(tool)) return;
    e.preventDefault();
    const finished = draftReducer(draft, { type: 'finish', tool });
    if (finished.committed) commitDraft(finished.points);
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
    setSnapPt(null);
  }, [dispatch]);
  const draftMinPoints = tool === 'area' ? 3 : 2;
  const draftFinishable = POLY_TOOLS.has(tool) && draft.points.length >= draftMinPoints;

  // Keyboard: Enter = finish, Escape = reset, z = undo. Bound to window while a
  // poly tool is active so the user need not focus the SVG.
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
      } else if (e.key === 'Escape') {
        dispatch({ type: 'reset' });
        setCursor(null);
        setSnapPt(null);
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

  // Keyboard for the calibrate tool: Escape cancels an in-progress calibration.
  // Same one-owner rule as the draft listener above.
  useEffect(() => {
    if (tool !== 'calibrate' || !calibA) return undefined;
    const onKey = (e) => {
      if (e.target?.closest?.('input, textarea, select, [contenteditable]')) return;
      if (e.key === 'Escape') {
        setCalibA(null);
        setCursor(null);
        setSnapPt(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tool, calibA, setCalibA]);

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
      onPointerLeave={() => setCursor(null)}
      onDoubleClick={handleDoubleClick}
    >
      {pageMeasurements.map((m) => (
        <CommittedMeasurement
          key={m.id}
          m={m}
          adapter={adapter}
          scale={scale}
          countTypes={countTypes}
          selected={m.id === selectedId}
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
        decimals={decimals}
      />

      {POLY_TOOLS.has(tool) && draft.points.length > 0 && (
        <DraftActions
          lastPt={adapter.toViewport(draft.points[draft.points.length - 1])}
          width={adapter.width}
          height={adapter.height}
          finishable={draftFinishable}
          onFinish={finishDraft}
          onCancel={cancelDraft}
        />
      )}

      {tool === 'calibrate' && (
        <CalibrationLayer
          calibA={calibA}
          cursor={cursor}
          adapter={adapter}
          snapPt={snapPt}
        />
      )}
    </svg>
  );
}

// Floating Baigti / Atšaukti buttons beside the draft's last vertex. SVG-native
// (this layer is an <svg>), stopPropagation on pointerdown+click so pressing a
// button never adds a draft vertex underneath it. Clamped inside the page.
function DraftActions({ lastPt, width, height, finishable, onFinish, onCancel }) {
  const W = 168, H = 30;
  const x = Math.min(Math.max(lastPt.x + 14, 4), Math.max(4, width - W - 4));
  const y = Math.min(Math.max(lastPt.y - H - 12, 4), Math.max(4, height - H - 4));
  const stop = (e) => { e.stopPropagation(); };
  const btn = (bx, bw, label, enabled, onClick, primary) => (
    <g
      transform={`translate(${bx}, 0)`}
      style={{ cursor: enabled ? 'pointer' : 'not-allowed', pointerEvents: 'auto' }}
      onPointerDown={stop}
      onDoubleClick={stop}
      onClick={(e) => { stop(e); if (enabled) onClick(); }}
    >
      <rect width={bw} height={H} rx={6}
        fill={primary ? (enabled ? '#1d4ed8' : '#93a8e8') : '#ffffff'}
        stroke={primary ? 'none' : '#cbd5e1'} strokeWidth={1} />
      <text x={bw / 2} y={H / 2 + 1} textAnchor="middle" dominantBaseline="central"
        fontSize={12} fontWeight={600}
        fill={primary ? '#ffffff' : '#334155'}
        style={{ pointerEvents: 'none', userSelect: 'none' }}>{label}</text>
    </g>
  );
  return (
    <g transform={`translate(${x}, ${y})`} style={{ pointerEvents: 'none' }}>
      <rect x={-4} y={-4} width={W + 8} height={H + 8} rx={8}
        fill="#ffffff" fillOpacity={0.92} stroke="#e2e8f0" strokeWidth={1} />
      {btn(0, 84, 'Baigti', finishable, onFinish, true)}
      {btn(92, 76, 'Atšaukti', true, onCancel, false)}
    </g>
  );
}

// Hit-test committed measurements (this page) for select mode. Area → point in
// polygon; line → nearest edge within tolerance. Returns id or null.
function hitTest(raw, measurements, pageNr, tol) {
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

  const stroke = selected ? '#1d4ed8' : (m.color || '#2a6fb5');
  const strokeWidth = selected ? 3 : 2;

  return (
    <g pointerEvents="none">
      <path
        d={d}
        fill={closed ? stroke : 'none'}
        fillOpacity={closed ? 0.12 : 0}
        stroke={stroke}
        strokeWidth={strokeWidth}
      />
      {sp.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={selected ? 4 : 3} fill={stroke} />
      ))}
      <ReadoutChip x={labelAt.x} y={labelAt.y} text={label} />
    </g>
  );
}

function CountMarker({ m, adapter, countTypes, selected }) {
  const p0 = m.points[0];
  if (!p0) return null;
  const { x, y } = adapter.toViewport(p0);
  const type = countTypes.find((t) => t.id === m.typeId) || {};
  const color = m.color || type.color || '#2a6fb5';
  const shape = type.shape || 'circle';
  const r = selected ? 8 : 6;
  const stroke = selected ? '#1d4ed8' : color;

  let mark;
  if (shape === 'square') {
    mark = <rect x={x - r} y={y - r} width={r * 2} height={r * 2} fill={color} stroke={stroke} strokeWidth={selected ? 2 : 1} />;
  } else if (shape === 'diamond') {
    mark = <path d={`M ${x} ${y - r} L ${x + r} ${y} L ${x} ${y + r} L ${x - r} ${y} Z`} fill={color} stroke={stroke} strokeWidth={selected ? 2 : 1} />;
  } else if (shape === 'check') {
    mark = (
      <g>
        <circle cx={x} cy={y} r={r} fill="none" stroke={color} strokeWidth={selected ? 2 : 1.5} />
        <path d={`M ${x - r * 0.5} ${y} L ${x - r * 0.1} ${y + r * 0.45} L ${x + r * 0.6} ${y - r * 0.5}`} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </g>
    );
  } else {
    mark = <circle cx={x} cy={y} r={r} fill={color} stroke={stroke} strokeWidth={selected ? 2 : 1} />;
  }
  return <g pointerEvents="none">{mark}</g>;
}

function DraftLayer({ tool, draft, cursor, adapter, scale, snapPt, decimals }) {
  if (!POLY_TOOLS.has(tool)) {
    // Still show the snap indicator for non-poly tools that snap (none today), no-op.
    return snapPt ? <SnapDot p={adapter.toViewport(snapPt)} /> : null;
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
      chip = 'Mastelis nekalibruotas';
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
          stroke="#2a6fb5"
          strokeWidth={2}
        />
      )}
      {/* rubber-band from last vertex to cursor */}
      {liveScreen.length >= 2 && (
        <line
          x1={liveScreen[liveScreen.length - 2].x}
          y1={liveScreen[liveScreen.length - 2].y}
          x2={liveScreen[liveScreen.length - 1].x}
          y2={liveScreen[liveScreen.length - 1].y}
          stroke="#2a6fb5"
          strokeWidth={1.5}
          strokeDasharray="5 4"
        />
      )}
      {/* faint closing segment back to the first vertex (area only) */}
      {closed && sp.length >= 2 && cur && (
        <line
          x1={cur.x}
          y1={cur.y}
          x2={sp[0].x}
          y2={sp[0].y}
          stroke="#2a6fb5"
          strokeWidth={1}
          strokeDasharray="3 4"
          strokeOpacity={0.4}
        />
      )}
      {sp.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#2a6fb5" />
      ))}
      {snapPt && <SnapDot p={adapter.toViewport(snapPt)} />}
      {chip && cur && <ReadoutChip x={cur.x + 12} y={cur.y - 12} text={chip} anchor="start" />}
    </g>
  );
}

// Calibration draft: a distinct RED 2-point line (visually separate from the
// blue measurement drafts). First point A is fixed; a rubber-band follows the
// cursor until the second click, which is handled upstream via onCalibrate.
function CalibrationLayer({ calibA, cursor, adapter, snapPt }) {
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
          stroke="#dc2626"
          strokeWidth={2}
          strokeDasharray="5 4"
        />
      )}
      {a && <circle cx={a.x} cy={a.y} r={4} fill="#dc2626" />}
      {c && <circle cx={c.x} cy={c.y} r={3} fill="#dc2626" fillOpacity={0.7} />}
      {snapPt && <SnapDot p={adapter.toViewport(snapPt)} />}
    </g>
  );
}

function SnapDot({ p }) {
  return (
    <circle cx={p.x} cy={p.y} r={5} fill="none" stroke="#16a34a" strokeWidth={2} pointerEvents="none" />
  );
}

function ReadoutChip({ x, y, text, anchor = 'middle' }) {
  // Approximate width so the background rect frames the text. Monospace-ish guess.
  const w = text.length * 6.2 + 12;
  const h = 18;
  const rx = anchor === 'start' ? x - 6 : x - w / 2;
  return (
    <g pointerEvents="none">
      <rect x={rx} y={y - h + 4} width={w} height={h} rx={3} fill="#1f2937" fillOpacity={0.92} />
      <text
        x={anchor === 'start' ? x : x}
        y={y - 3}
        textAnchor={anchor}
        fontSize={11}
        fontFamily="system-ui, sans-serif"
        fill="#ffffff"
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

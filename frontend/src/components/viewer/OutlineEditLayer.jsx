/**
 * OutlineEditLayer — one room's outline (or one of his measurements, Pathon v3 W5-A A1), vertex by vertex:
 *   drag a corner; drag an EDGE — both its corners move together, a wall snaps at either end (A3 #92);
 *   click an edge (or its middle dot) — a corner is added there; double-click a corner — it goes (never below
 *   the shape's minimum);
 *   click a corner — it is selected and its pop-up opens beside it („Ištrinti" · „Iškirpti angą", A2 #91);
 *   right-click a corner or an edge — the same pop-up; Ctrl / Shift + click — add the corner to the selection;
 *   drag on empty paper — a box selects the corners in it (A3 #93); Delete / the arrow keys act on the selected
 *   corners (TakeoffViewer owns the keys).
 * Snaps to the drawing's wall corners and faces (the page geometry's rings) within SNAP_PX. Works in
 * DISPLAY-frame page fractions — the frame `polygon_pct` lives in — so nothing is rotated here; a measurement
 * is turned into this frame and back by lib/editGestures. Controlled: `points` and `selected` come from
 * TakeoffViewer, every change goes back through `onChange(points)` / `onSelect(indices)`; `onGestureStart()`
 * fires once per drag / insert / delete so the owner keeps an undo history.
 *
 * A live chip shows what the ring measures at the page's scale next to the table's area, so the person sees
 * the consequence of a move before saving; a self-crossing ring turns red (the owner refuses to save it).
 *
 * v3 overlay vocabulary (lib/overlayTokens): the ring being edited and its handles are the tool-at-work orange,
 * solid; a selected corner is filled; red only when the ring crosses itself (an error); snap mark orange square;
 * the box being dragged the neutral selection ink; the readout a neutral label pill.
 */
import { useMemo, useRef, useState } from 'react';
import { nearestEdge, nearestVertex, polygonCentroid, selfIntersects } from '@/lib/polygonGeometry';
import { formatNumberLT, realPathLengthM, shoelaceAreaM2 } from '@/lib/measureGeometry';
import { displayRotationFor, normalizeRotation } from '@/lib/viewerEngine/pageRotation';
import { moveEdge, projectT, verticesInBox } from '@/lib/editGestures';
import { cursorOf } from '@/lib/cursors';
import { LABEL_FONT_PX, LABEL_STYLE, STROKE_PX, labelWidth, ov, paint } from '@/lib/overlayTokens';

const SNAP_PX = 8;
const VERTEX_R = 6;
const HIT_R = 12;
const EDGE_HIT_PX = 10;
const GHOST_R = 4;
const MOVE_PX = 3;              // a press that moves less than this is a click
const STROKE = ov('editing');  // an edit in progress — the tool-at-work colour, distinct from a read outline
const INVALID = ov('error');   // the ring crosses itself — an error

export default function OutlineEditLayer({
  points, onChange, onGestureStart = null, geometry, renderedSize,
  scale = null, pageSizePt = null, pageRotation = 0, tableAreaM2 = null,
  // „Atimti" cut-outs (2026-10-16): shown through the fill (even-odd), off the readout's area, kept on save.
  holes = [],
  // A measurement (W5-A A1): a distance / perimeter is an OPEN path (no closing edge, 2 corners at least).
  closed = true,
  minPoints = 3,
  // Selected corners (indices) and the pop-up (A2): `onMenu({kind: 'vertex' | 'edge', index, t, x, y})`, x/y in
  // screen px — the owner places VertexPopover there.
  selected = [],
  onSelect = null,
  onMenu = null,
}) {
  const { width, height } = renderedSize || {};
  const svgRef = useRef(null);
  // {kind: 'vertex' | 'edge' | 'box', index, from: px, moved, start: points}
  const [press, setPress] = useState(null);
  const [boxTo, setBoxTo] = useState(null);
  const [snapPx, setSnapPx] = useState(null);
  const selectedSet = useMemo(() => new Set(selected || []), [selected]);
  const snapRings = useMemo(() => (Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : [])
    .map((ring, i) => ({ id: `wall-${i}`, open: false, points: ring.map(([fx, fy]) => ({ x: fx * width, y: fy * height })) })),
  [geometry, width, height]);
  // The ring in PDF points of the DISPLAYED sheet (area and length do not care which way the page is turned).
  const readout = useMemo(() => {
    if (!Array.isArray(points) || points.length < (closed ? 3 : 2) || !pageSizePt?.width || !pageSizePt?.height) return null;
    const rot = displayRotationFor(normalizeRotation(pageRotation));
    const swapped = rot === 90 || rot === 270;
    const W = swapped ? pageSizePt.height : pageSizePt.width;
    const H = swapped ? pageSizePt.width : pageSizePt.height;
    const pts = points.map(([fx, fy]) => ({ x: fx * W, y: fy * H }));
    const crossing = closed && selfIntersects(pts);
    if (!scale?.calibrated) return { crossing, text: crossing ? 'Kontūras kertasi' : 'Mastelis nenustatytas' };
    if (!closed) return { crossing: false, text: `${formatNumberLT(realPathLengthM(pts, scale, false), 2)} m` };
    const toPts = (ring) => ring.map(([fx, fy]) => ({ x: fx * W, y: fy * H }));
    const area = Math.max(0, shoelaceAreaM2(pts, scale) - (holes || []).reduce((s, h) => s + shoelaceAreaM2(toPts(h), scale), 0));
    const perim = realPathLengthM(pts, scale, true);
    const table = Number(tableAreaM2);
    const vs = table > 0 ? ` · lentelėje ${formatNumberLT(table, 2)} m²` : '';
    return { crossing, text: crossing ? 'Kontūras kertasi pats su savimi' : `${formatNumberLT(area, 2)} m² · ${formatNumberLT(perim, 2)} m${vs}` };
  }, [points, holes, pageSizePt, pageRotation, scale, tableAreaM2, closed]);
  if (!width || !height || !Array.isArray(points)) return null;

  const toPx = (p) => ({ x: p[0] * width, y: p[1] * height });
  const eventPx = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const snapped = (px) => {
    const v = snapRings.length ? nearestVertex(px, snapRings, SNAP_PX) : null;
    const hit = v || (snapRings.length ? nearestEdge(px, snapRings, SNAP_PX) : null);
    return hit ? { px: hit.point, kind: v ? 'vertex' : 'edge' } : { px, kind: null };
  };
  const snapPct = ([fx, fy]) => {
    const s = snapped({ x: fx * width, y: fy * height });
    return s.kind ? [s.px.x / width, s.px.y / height] : null;
  };
  const clamp01 = (v) => Math.min(1, Math.max(0, v));
  const edgeCount = closed ? points.length : points.length - 1;
  const menuAt = (e) => ({ x: e.clientX, y: e.clientY });

  const onVertexDown = (i) => (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (e.button === 2) return;                          // the right-click opens the pop-up (onContextMenu)
    if (e.ctrlKey || e.metaKey || e.shiftKey) {
      const next = selectedSet.has(i) ? [...selectedSet].filter((k) => k !== i) : [...selectedSet, i];
      onSelect?.(next.sort((a, b) => a - b));
      return;
    }
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setPress({ kind: 'vertex', index: i, from: eventPx(e), moved: false, start: points, menu: menuAt(e) });
  };
  const onEdgeDown = (i) => (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (e.button === 2) return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setPress({ kind: 'edge', index: i, from: eventPx(e), moved: false, start: points });
  };
  const onBackgroundDown = (e) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture?.(e.pointerId);
    const p = eventPx(e);
    setPress({ kind: 'box', from: p, moved: false, add: e.shiftKey || e.ctrlKey || e.metaKey });
    setBoxTo(p);
  };
  const onPointerMove = (e) => {
    if (!press) return;
    const here = eventPx(e);
    const moved = press.moved || Math.hypot(here.x - press.from.x, here.y - press.from.y) >= MOVE_PX;
    if (!moved) return;
    if (!press.moved) {
      if (press.kind !== 'box') onGestureStart?.();
      setPress({ ...press, moved: true });
    }
    if (press.kind === 'box') { setBoxTo(here); return; }
    if (press.kind === 'vertex') {
      const { px, kind } = snapped(here);
      setSnapPx(kind ? px : null);
      const next = points.slice();
      next[press.index] = [clamp01(px.x / width), clamp01(px.y / height)];
      onChange(next);
      return;
    }
    if (press.kind === 'edge') {
      const dx = (here.x - press.from.x) / width;
      const dy = (here.y - press.from.y) / height;
      const res = moveEdge(press.start, press.index, dx, dy, { closed, snap: snapPct });
      setSnapPx(res.snapped ? toPx(res.snapped) : null);
      onChange(res.points);
    }
  };
  const onPointerUp = (e) => {
    const p = press;
    setPress(null);
    setSnapPx(null);
    if (!p) return;
    if (p.kind === 'box') {
      const to = boxTo || p.from;
      setBoxTo(null);
      if (!p.moved) { if (selectedSet.size) onSelect?.([]); return; }
      const hits = verticesInBox(points, [p.from.x / width, p.from.y / height], [to.x / width, to.y / height]);
      onSelect?.(p.add ? [...new Set([...selectedSet, ...hits])].sort((a, b) => a - b) : hits);
      return;
    }
    if (p.moved) return;
    if (p.kind === 'vertex') {
      // a click on a corner: it is the selection, and its pop-up opens beside it (never hover-only)
      onSelect?.([p.index]);
      onMenu?.({ kind: 'vertex', index: p.index, x: p.menu.x, y: p.menu.y });
      return;
    }
    if (p.kind === 'edge') {
      // a click on an edge adds a corner where he clicked
      const a = points[p.index];
      const b = points[(p.index + 1) % points.length];
      const at = [clamp01(eventPx(e).x / width), clamp01(eventPx(e).y / height)];
      const t = projectT(at, a, b);
      const next = points.slice();
      next.splice(p.index + 1, 0, [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
      onGestureStart?.();
      onChange(next);
      onSelect?.([p.index + 1]);
    }
  };
  const insertAt = (i) => (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (e.button === 2) return;
    const a = points[i];
    const b = points[(i + 1) % points.length];
    const next = points.slice();
    next.splice(i + 1, 0, [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
    onGestureStart?.();
    onChange(next);
  };
  const removeAt = (i) => (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (points.length <= minPoints) return;
    onGestureStart?.();
    onChange(points.filter((_, k) => k !== i));
    onSelect?.([]);
  };
  const vertexMenu = (i) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    onSelect?.([i]);
    onMenu?.({ kind: 'vertex', index: i, x: e.clientX, y: e.clientY });
  };
  const edgeMenu = (i) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    const a = points[i];
    const b = points[(i + 1) % points.length];
    const at = eventPx(e);
    onMenu?.({ kind: 'edge', index: i, t: projectT([at.x / width, at.y / height], a, b), x: e.clientX, y: e.clientY });
  };

  const px = points.map(toPx);
  const stroke = readout?.crossing ? INVALID : STROKE;
  const centre = (closed ? polygonCentroid(px) : px[Math.floor(px.length / 2)]) || px[0];
  const ringPath = (r, close) => `M ${r.map((p) => `${p.x} ${p.y}`).join(' L ')}${close ? ' Z' : ''}`;
  const dragging = press?.moved && press.kind !== 'box';
  const box = press?.kind === 'box' && press.moved && boxTo
    ? { x: Math.min(press.from.x, boxTo.x), y: Math.min(press.from.y, boxTo.y), w: Math.abs(boxTo.x - press.from.x), h: Math.abs(boxTo.y - press.from.y) }
    : null;
  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      data-outline-edit-layer
      data-closed={closed ? 'true' : 'false'}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'auto', overflow: 'visible', cursor: cursorOf(dragging ? 'dragging' : 'rest') }}
      onPointerDown={onBackgroundDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => { setPress(null); setBoxTo(null); setSnapPx(null); }}
      onContextMenu={(e) => e.preventDefault()}
    >
      {closed ? (
        <path
          d={[px, ...(holes || []).map((h) => h.map(toPx))].filter((r) => r.length >= 3).map((r) => ringPath(r, true)).join(' ')}
          style={paint({ fill: stroke, stroke })} fillOpacity={0.08} fillRule="evenodd" strokeWidth={STROKE_PX} strokeLinejoin="round" pointerEvents="none"
        />
      ) : (
        <path d={ringPath(px, false)} fill="none" style={paint({ stroke })} strokeWidth={STROKE_PX} strokeLinejoin="round" pointerEvents="none" />
      )}
      {/* edges: a wide invisible target — drag moves the edge, a click adds a corner, right-click the pop-up */}
      {px.slice(0, edgeCount).map((p, i) => {
        const q = px[(i + 1) % px.length];
        return (
          <line
            key={`e${i}`} x1={p.x} y1={p.y} x2={q.x} y2={q.y} data-outline-edge={i}
            stroke="transparent" strokeWidth={EDGE_HIT_PX} style={{ cursor: cursorOf('edge') }}
            onPointerDown={onEdgeDown(i)} onContextMenu={edgeMenu(i)}
          >
            <title>Tempkite kraštinę · spustelėkite — pridėti kampą · dešinysis klavišas — iškirpti angą</title>
          </line>
        );
      })}
      {px.slice(0, edgeCount).map((p, i) => {
        const q = px[(i + 1) % px.length];
        return (
          <circle
            key={`g${i}`} cx={(p.x + q.x) / 2} cy={(p.y + q.y) / 2} r={GHOST_R}
            style={{ ...paint({ fill: ov('label-bg'), stroke }), cursor: cursorOf('insert') }} strokeWidth={1.5} opacity={0.85}
            onPointerDown={insertAt(i)} onContextMenu={edgeMenu(i)}
          >
            <title>Pridėti viršūnę</title>
          </circle>
        );
      })}
      {px.map((p, i) => (
        <g key={`v${i}`} data-outline-vertex={i} data-selected={selectedSet.has(i) ? 'true' : undefined}>
          <circle cx={p.x} cy={p.y} r={selectedSet.has(i) ? VERTEX_R + 1 : VERTEX_R} style={paint({ fill: selectedSet.has(i) ? stroke : ov('label-bg'), stroke })} strokeWidth={STROKE_PX} pointerEvents="none" />
          {/* a wider invisible target: a 6 px handle at 79 % zoom is too small to grab reliably */}
          <circle
            cx={p.x} cy={p.y} r={HIT_R} fill="transparent" stroke="none"
            style={{ cursor: cursorOf(dragging ? 'dragging' : 'vertex') }} onPointerDown={onVertexDown(i)} onDoubleClick={removeAt(i)}
            onContextMenu={vertexMenu(i)}
          >
            <title>Tempkite · spustelėkite — veiksmai · dukart spustelėkite — pašalinti</title>
          </circle>
        </g>
      ))}
      {box && <rect x={box.x} y={box.y} width={box.w} height={box.h} style={paint({ fill: ov('selected'), stroke: ov('selected') })} fillOpacity={0.06} strokeWidth={1.5} pointerEvents="none" data-vertex-box />}
      {snapPx && <rect x={snapPx.x - 6} y={snapPx.y - 6} width={12} height={12} fill="none" style={paint({ stroke: ov('editing') })} strokeWidth={STROKE_PX} pointerEvents="none" />}
      {readout && centre && (
        <g pointerEvents="none" data-outline-readout>
          <rect x={centre.x - labelWidth(readout.text) / 2} y={centre.y - 10} width={labelWidth(readout.text)} height={20} rx={2}
            style={paint({ fill: ov('label-bg'), stroke: readout.crossing ? INVALID : STROKE })} fillOpacity={0.96} strokeWidth={1.5} />
          <text x={centre.x} y={centre.y + 4} textAnchor="middle" fontSize={LABEL_FONT_PX} fontWeight={readout.crossing ? 600 : 500}
            style={{ ...LABEL_STYLE, ...paint({ fill: readout.crossing ? INVALID : ov('label-fg') }) }}>
            {readout.text}
          </text>
        </g>
      )}
    </svg>
  );
}

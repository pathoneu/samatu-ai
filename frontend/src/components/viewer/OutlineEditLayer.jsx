/**
 * OutlineEditLayer — one room's outline, vertex by vertex: drag a corner, click a midpoint to add one,
 * double-click a corner to remove it (never below 3). Snaps to the drawing's wall corners and faces
 * (the page geometry's rings) within SNAP_PX. Works in DISPLAY-frame page fractions — the frame
 * `polygon_pct` lives in — so nothing is rotated here. Controlled: `points` come from TakeoffViewer,
 * every change goes back through `onChange(points)`; `onGestureStart()` fires once per drag / insert /
 * delete so the owner can keep an undo history. Save/Cancel/Undo live in the viewer's toolbar.
 * (2026-10-16, Togal analysis §6: drag vertex / hover edge to add / double-click to delete.)
 *
 * A live chip shows what the ring measures at the page's scale next to the table's area, so the person
 * sees the consequence of a move before saving; a self-crossing ring turns red (the owner refuses to
 * save it).
 *
 * v3 overlay vocabulary (lib/overlayTokens): the ring being edited and its handles are the
 * tool-at-work orange, solid; red only when the ring crosses itself (an error); snap mark orange square;
 * the readout a neutral label pill.
 */
import { useMemo, useRef, useState } from 'react';
import { nearestEdge, nearestVertex, polygonCentroid, selfIntersects } from '@/lib/polygonGeometry';
import { formatNumberLT, realPathLengthM, shoelaceAreaM2 } from '@/lib/measureGeometry';
import { displayRotationFor, normalizeRotation } from '@/lib/viewerEngine/pageRotation';
import { LABEL_FONT_PX, LABEL_STYLE, STROKE_PX, labelWidth, ov, paint } from '@/lib/overlayTokens';

const SNAP_PX = 8;
const VERTEX_R = 6;
const HIT_R = 12;
const GHOST_R = 4;
const STROKE = ov('editing');  // an edit in progress — the tool-at-work colour, distinct from a read outline
const INVALID = ov('error');   // the ring crosses itself — an error

export default function OutlineEditLayer({
  points, onChange, onGestureStart = null, geometry, renderedSize,
  scale = null, pageSizePt = null, pageRotation = 0, tableAreaM2 = null,
  // „Atimti" cut-outs (2026-10-16): shown through the fill (even-odd), off the readout's area, kept on save.
  holes = [],
}) {
  const { width, height } = renderedSize || {};
  const svgRef = useRef(null);
  const [drag, setDrag] = useState(null);           // index of the vertex being dragged
  const [snapPx, setSnapPx] = useState(null);
  const snapRings = useMemo(() => (Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : [])
    .map((ring, i) => ({ id: `wall-${i}`, open: false, points: ring.map(([fx, fy]) => ({ x: fx * width, y: fy * height })) })),
  [geometry, width, height]);
  // The ring in PDF points of the DISPLAYED sheet (area and length do not care which way the page is turned).
  const readout = useMemo(() => {
    if (!Array.isArray(points) || points.length < 3 || !pageSizePt?.width || !pageSizePt?.height) return null;
    const rot = displayRotationFor(normalizeRotation(pageRotation));
    const swapped = rot === 90 || rot === 270;
    const W = swapped ? pageSizePt.height : pageSizePt.width;
    const H = swapped ? pageSizePt.width : pageSizePt.height;
    const pts = points.map(([fx, fy]) => ({ x: fx * W, y: fy * H }));
    const crossing = selfIntersects(pts);
    if (!scale?.calibrated) return { crossing, text: crossing ? 'Kontūras kertasi' : 'Mastelis nenustatytas' };
    const toPts = (ring) => ring.map(([fx, fy]) => ({ x: fx * W, y: fy * H }));
    const area = Math.max(0, shoelaceAreaM2(pts, scale) - (holes || []).reduce((s, h) => s + shoelaceAreaM2(toPts(h), scale), 0));
    const perim = realPathLengthM(pts, scale, true);
    const table = Number(tableAreaM2);
    const vs = table > 0 ? ` · lentelėje ${formatNumberLT(table, 2)} m²` : '';
    return { crossing, text: crossing ? 'Kontūras kertasi pats su savimi' : `${formatNumberLT(area, 2)} m² · ${formatNumberLT(perim, 2)} m${vs}` };
  }, [points, holes, pageSizePt, pageRotation, scale, tableAreaM2]);
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
  const clamp01 = (v) => Math.min(1, Math.max(0, v));

  const onVertexDown = (i) => (e) => {
    e.stopPropagation();
    e.preventDefault();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    onGestureStart?.();
    setDrag(i);
  };
  const onPointerMove = (e) => {
    if (drag == null) return;
    const { px, kind } = snapped(eventPx(e));
    setSnapPx(kind ? px : null);
    const next = points.slice();
    next[drag] = [clamp01(px.x / width), clamp01(px.y / height)];
    onChange(next);
  };
  const onPointerUp = () => { setDrag(null); setSnapPx(null); };
  const insertAt = (i) => (e) => {
    e.stopPropagation();
    e.preventDefault();
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
    if (points.length <= 3) return;
    onGestureStart?.();
    onChange(points.filter((_, k) => k !== i));
  };

  const px = points.map(toPx);
  const stroke = readout?.crossing ? INVALID : STROKE;
  const centre = polygonCentroid(px) || px[0];
  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      data-outline-edit-layer
      style={{ position: 'absolute', inset: 0, pointerEvents: 'auto', overflow: 'visible', cursor: drag != null ? 'grabbing' : 'default' }}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <path
        d={[px, ...(holes || []).map((h) => h.map(toPx))].filter((r) => r.length >= 3)
          .map((r) => `M ${r.map((p) => `${p.x} ${p.y}`).join(' L ')} Z`).join(' ')}
        style={paint({ fill: stroke, stroke })} fillOpacity={0.08} fillRule="evenodd" strokeWidth={STROKE_PX} strokeLinejoin="round" pointerEvents="none"
      />
      {px.map((p, i) => {
        const q = px[(i + 1) % px.length];
        return (
          <circle
            key={`g${i}`} cx={(p.x + q.x) / 2} cy={(p.y + q.y) / 2} r={GHOST_R}
            style={{ ...paint({ fill: ov('label-bg'), stroke }), cursor: 'copy' }} strokeWidth={1.5} opacity={0.85}
            onPointerDown={insertAt(i)}
          >
            <title>Pridėti viršūnę</title>
          </circle>
        );
      })}
      {px.map((p, i) => (
        <g key={`v${i}`} data-outline-vertex={i}>
          <circle cx={p.x} cy={p.y} r={VERTEX_R} style={paint({ fill: ov('label-bg'), stroke })} strokeWidth={STROKE_PX} pointerEvents="none" />
          {/* a wider invisible target: a 6 px handle at 79 % zoom is too small to grab reliably */}
          <circle
            cx={p.x} cy={p.y} r={HIT_R} fill="transparent" stroke="none"
            style={{ cursor: 'grab' }} onPointerDown={onVertexDown(i)} onDoubleClick={removeAt(i)}
          >
            <title>Tempkite · dukart spustelėkite — pašalinti</title>
          </circle>
        </g>
      ))}
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

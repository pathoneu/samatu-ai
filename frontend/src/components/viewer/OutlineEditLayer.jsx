/**
 * OutlineEditLayer — one room's outline, vertex by vertex: drag a corner, click a midpoint to add one,
 * double-click a corner to remove it (never below 3). Snaps to the drawing's wall corners and faces
 * (the page geometry's rings) within SNAP_PX. Works in DISPLAY-frame page fractions — the frame
 * `polygon_pct` lives in — so nothing is rotated here. Controlled: `points` come from TakeoffViewer,
 * every change goes back through `onChange(points)`; Save/Cancel live in the viewer's toolbar.
 * (2026-10-16, Togal analysis §6: drag vertex / hover edge to add / double-click to delete.)
 */
import { useMemo, useRef, useState } from 'react';
import { nearestEdge, nearestVertex } from '@/lib/polygonGeometry';

const SNAP_PX = 8;
const VERTEX_R = 6;
const HIT_R = 12;
const GHOST_R = 4;
const STROKE = '#b45309';   // amber — an edit in progress, distinct from the evergreen committed outline

export default function OutlineEditLayer({ points, onChange, geometry, renderedSize }) {
  const { width, height } = renderedSize || {};
  const svgRef = useRef(null);
  const [drag, setDrag] = useState(null);           // index of the vertex being dragged
  const [snapPx, setSnapPx] = useState(null);
  const snapRings = useMemo(() => (Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : [])
    .map((ring, i) => ({ id: `wall-${i}`, open: false, points: ring.map(([fx, fy]) => ({ x: fx * width, y: fy * height })) })),
  [geometry, width, height]);
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
    onChange(next);
  };
  const removeAt = (i) => (e) => {
    e.stopPropagation();
    e.preventDefault();
    if (points.length <= 3) return;
    onChange(points.filter((_, k) => k !== i));
  };

  const px = points.map(toPx);
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
      <polygon
        points={px.map((p) => `${p.x},${p.y}`).join(' ')}
        fill={STROKE} fillOpacity={0.08} stroke={STROKE} strokeWidth={2} strokeLinejoin="round" pointerEvents="none"
      />
      {px.map((p, i) => {
        const q = px[(i + 1) % px.length];
        return (
          <circle
            key={`g${i}`} cx={(p.x + q.x) / 2} cy={(p.y + q.y) / 2} r={GHOST_R}
            fill="#ffffff" stroke={STROKE} strokeWidth={1.5} opacity={0.8}
            style={{ cursor: 'copy' }} onPointerDown={insertAt(i)}
          >
            <title>Pridėti viršūnę</title>
          </circle>
        );
      })}
      {px.map((p, i) => (
        <g key={`v${i}`} data-outline-vertex={i}>
          <circle cx={p.x} cy={p.y} r={VERTEX_R} fill="#ffffff" stroke={STROKE} strokeWidth={2} pointerEvents="none" />
          {/* a wider invisible target: a 6 px handle at 79 % zoom is too small to grab reliably */}
          <circle
            cx={p.x} cy={p.y} r={HIT_R} fill="transparent" stroke="none"
            style={{ cursor: 'grab' }} onPointerDown={onVertexDown(i)} onDoubleClick={removeAt(i)}
          >
            <title>Tempkite · dukart spustelėkite — pašalinti</title>
          </circle>
        </g>
      ))}
      {snapPx && <rect x={snapPx.x - 6} y={snapPx.y - 6} width={12} height={12} fill="none" stroke="#ea580c" strokeWidth={2} pointerEvents="none" />}
    </svg>
  );
}

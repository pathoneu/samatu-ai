/**
 * OutlineToolLayer — the page half of the outline tools (2026-10-16, Togal analysis §6), on the page
 * that holds the focused room's outline:
 *   „Padalyti": two clicks give a line; the outline is cut along it (lib/outlineTools.splitRingByLine);
 *               hover a half to see it, click the half that stays this room.
 *   „Sujungti": hover a neighbour's outline on this sheet, click it — the union of the two (refused,
 *               with the reason, when a wall or a gap keeps them apart or they overlap).
 *   „Atimti":   drag a rectangle (or click a polygon) inside the outline — it becomes a hole.
 * Every step shows what it measures BEFORE anything is saved (chips in m², like the vertex editor's).
 *
 * Works in DISPLAY-frame page fractions (the frame `polygon_pct` lives in); geometry is computed in
 * PDF points of the displayed sheet, so a tolerance means the same at every zoom. Controlled: the state
 * lives in useOutlineTool, every change goes back through `onChange`.
 */
import { useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import { nearestEdge, nearestVertex, polygonCentroid } from '@/lib/polygonGeometry';
import { formatNumberLT, shoelaceAreaM2 } from '@/lib/measureGeometry';
import { displayRotationFor, normalizeRotation } from '@/lib/viewerEngine/pageRotation';
import { roomPageOf } from '@/lib/roomZones';
import {
  displaySizePt, holeFit, holesInside, pctRingToPts, ptsRingToPct, rectRing, ringAt, splitRingByLine, unionTouchingRings,
} from '@/lib/outlineTools';
import { roomHoles } from './useOutlineTool';

const SNAP_PX = 8;
const EDIT = '#b45309';       // amber — the outline being worked on (same as the vertex editor)
const KEEP = '#2f6b4f';       // the theme's evergreen — what stays / what the result will be
const OTHER = '#64748b';      // slate — the half that leaves, a neighbour to pick
const HOLE = '#7c3aed';       // violet — a hole being drawn
const MERGE_TOL_M = 0.05;     // outlines this close (5 cm on the sheet) touch

const SPLIT_REFUSED = {
  miss: 'Linija nekerta šio kontūro — spustelėkite abiejose patalpos pusėse',
  degenerate: 'Linija nukerta tik kampą — viena dalis būtų be ploto',
};
export const MERGE_REFUSED = {
  apart: 'Kontūrai nesiliečia — tarp jų siena ar tarpas. Sujungti galima tik besiliečiančius kontūrus (pvz., per menamą ribą tarp virtuvės ir svetainės).',
  overlap: 'Kontūrai persidengia — pirmiausia pataisykite vieną jų („Redaguoti kontūrą"), tada sujunkite.',
};
const HOLE_REFUSED = {
  small: 'Išpjova per maža',
  crossing: 'Išpjovos kraštinės kertasi',
  outside: 'Išpjova turi būti visa kontūro viduje',
  overlap: 'Išpjova persidengia su kita išpjova',
};

function pathOf(rings, toPx) {
  return rings.filter((r) => r && r.length >= 3)
    .map((r) => `M ${r.map((p) => { const q = toPx(p); return `${q.x.toFixed(1)} ${q.y.toFixed(1)}`; }).join(' L ')} Z`)
    .join(' ');
}

function Chip({ at, text, tone = 'dark' }) {
  if (!at || !text) return null;
  const w = text.length * 6.2 + 12;
  return (
    <g pointerEvents="none" data-outline-tool-chip>
      <rect x={at.x - w / 2} y={at.y - 10} width={w} height={20} rx={3} fill={tone === 'dark' ? '#1f2937' : KEEP} fillOpacity={0.92} />
      <text x={at.x} y={at.y + 4} textAnchor="middle" fontSize={11} fontFamily="system-ui, sans-serif" fill="#ffffff">{text}</text>
    </g>
  );
}

export default function OutlineToolLayer({
  tool, onChange, rooms = [], geometry = null, renderedSize, scale = null, pageSizePt = null, pageRotation = 0,
}) {
  const { width, height } = renderedSize || {};
  const svgRef = useRef(null);
  const [cursor, setCursor] = useState(null);      // pct
  const [hoverPart, setHoverPart] = useState(-1);
  const [hoverNr, setHoverNr] = useState(null);
  const [dragFrom, setDragFrom] = useState(null);  // pct — a rectangle hole being dragged
  const size = useMemo(
    () => displaySizePt(pageSizePt, displayRotationFor(normalizeRotation(pageRotation))),
    [pageSizePt, pageRotation],
  );
  const calibrated = !!scale?.calibrated;
  const pts = (ring) => pctRingToPts(ring, size);
  const m2 = (ring, holes = []) => (calibrated && size
    ? Math.max(0, shoelaceAreaM2(pts(ring), scale) - holes.reduce((s, h) => s + shoelaceAreaM2(pts(h), scale), 0))
    : null);
  const fmt = (v) => (v == null ? 'mastelis nenustatytas' : `${formatNumberLT(v, 2)} m²`);
  const neighbours = useMemo(() => (tool?.mode === 'merge'
    ? (rooms || []).filter((r) => String(r?.nr) !== tool.nr && roomPageOf(r) === tool.page
      && Array.isArray(r.polygon_pct) && r.polygon_pct.length >= 3)
    : []), [rooms, tool?.mode, tool?.nr, tool?.page]);
  if (!width || !height || !tool || !size) return null;

  const toPx = ([fx, fy]) => ({ x: fx * width, y: fy * height });
  const eventPct = (e) => {
    const r = svgRef.current.getBoundingClientRect();
    return [Math.min(1, Math.max(0, (e.clientX - r.left) / width)), Math.min(1, Math.max(0, (e.clientY - r.top) / height))];
  };
  // Clicks for a line snap to the outline's own corners and edges and to the drawing's walls.
  const snapped = (pct) => {
    const px = toPx(pct);
    const rings = [
      { id: 'ring', open: false, points: tool.ring.map(toPx) },
      ...(Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : []).map((w, i) => ({ id: `w${i}`, open: false, points: w.map(toPx) })),
    ];
    const hit = nearestVertex(px, rings, SNAP_PX) || nearestEdge(px, rings, SNAP_PX);
    return hit ? [hit.point.x / width, hit.point.y / height] : pct;
  };
  const toPt = ([fx, fy]) => ({ x: fx * size.width, y: fy * size.height });

  // ── „Padalyti" ──────────────────────────────────────────────────────────────────────────────────
  const trySplit = (a, b) => {
    const res = splitRingByLine(pts(tool.ring), toPt(a), toPt(b));
    if (res.status !== 'ok') return { refused: SPLIT_REFUSED[res.status] || SPLIT_REFUSED.miss };
    const holesPt = (tool.holes || []).map(pts);
    const parts = res.rings.map((r) => ({ ring: r, holes: holesInside(r, holesPt) }));
    if (parts[0].holes.length + parts[1].holes.length !== holesPt.length) {
      return { refused: 'Linija kerta išpjovą — veskite ją pro šalį arba pirmiausia pašalinkite išpjovą („Atimti")' };
    }
    return {
      parts: parts.map((p) => ({ ring: ptsRingToPct(p.ring, size), holes: p.holes.map((h) => ptsRingToPct(h, size)) })),
      chord: res.chord.map((p) => [p.x / size.width, p.y / size.height]),
    };
  };
  const preview = tool.mode === 'split' && tool.a && !tool.parts && cursor ? trySplit(tool.a, cursor) : null;

  // ── „Sujungti" ──────────────────────────────────────────────────────────────────────────────────
  const tryMerge = (room) => {
    const mpp = calibrated ? (Number(scale.metersPerPointX) + Number(scale.metersPerPointY)) / 2 : 0;
    const tol = mpp > 0 ? MERGE_TOL_M / mpp : 2;
    const res = unionTouchingRings(pts(tool.ring), pts(room.polygon_pct.map(([x, y]) => [Number(x), Number(y)])), tol);
    if (res.status !== 'ok') return { refused: res.status };
    const holes = [...res.holes, ...(tool.holes || []).map(pts), ...roomHoles(room).map(pts)];
    return { union: { ring: ptsRingToPct(res.ring, size), holes: holes.map((h) => ptsRingToPct(h, size)) } };
  };
  const hovered = tool.mode === 'merge' && hoverNr && hoverNr !== tool.targetNr
    ? neighbours.find((r) => String(r.nr) === hoverNr) : null;
  const hoverMerge = hovered ? tryMerge(hovered) : null;

  // ── „Atimti" ────────────────────────────────────────────────────────────────────────────────────
  const addHole = (ring) => {
    const fit = holeFit(pts(ring), pts(tool.ring), (tool.holes || []).map(pts));
    if (fit !== 'ok') { toast.error(HOLE_REFUSED[fit] || HOLE_REFUSED.outside); return false; }
    onChange((cur) => ({ ...cur, holes: [...(cur.holes || []), ring], draft: [], dirty: true }));
    return true;
  };
  const dragRect = tool.mode === 'subtract' && dragFrom && cursor
    ? ptsRingToPct(rectRing(toPt(dragFrom), toPt(cursor)), size) : null;

  // ── pointer ─────────────────────────────────────────────────────────────────────────────────────
  const onPointerMove = (e) => {
    const p = eventPct(e);
    setCursor(tool.mode === 'split' && !tool.parts ? snapped(p) : p);
    if (tool.mode === 'split' && tool.parts) setHoverPart(ringAt(toPt(p), tool.parts.map((x) => pts(x.ring))));
  };
  const onPointerDown = (e) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const p = eventPct(e);
    if (tool.mode === 'split') {
      if (tool.parts) {
        const i = ringAt(toPt(p), tool.parts.map((x) => pts(x.ring)));
        if (i >= 0 && i !== tool.keep) onChange((cur) => ({ ...cur, keep: i }));
        return;
      }
      const s = snapped(p);
      if (!tool.a) { onChange((cur) => ({ ...cur, a: s })); return; }
      const res = trySplit(tool.a, s);
      if (res.refused) { toast.error(res.refused); return; }
      onChange((cur) => ({ ...cur, b: s, parts: res.parts, chord: res.chord, keep: null, otherNr: '' }));
      return;
    }
    if (tool.mode === 'merge') {
      const room = hovered;
      if (!room) return;
      const res = tryMerge(room);
      if (res.refused) {
        onChange((cur) => ({ ...cur, targetNr: null, union: null, refused: { nr: String(room.nr), status: res.refused } }));
        toast.error(`${room.nr}: ${MERGE_REFUSED[res.refused]}`);
        return;
      }
      onChange((cur) => ({ ...cur, targetNr: String(room.nr), union: res.union, refused: null }));
      return;
    }
    if (tool.mode === 'subtract') {
      if (tool.shape === 'rect') {
        try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* pointer already gone */ }
        setDragFrom(p);
        setCursor(p);
        return;
      }
      const draft = tool.draft || [];
      if (draft.length >= 3) {
        const first = toPx(draft[0]);
        const here = toPx(p);
        if (Math.hypot(first.x - here.x, first.y - here.y) <= SNAP_PX) { addHole(draft); return; }
      }
      onChange((cur) => ({ ...cur, draft: [...(cur.draft || []), p] }));
    }
  };
  const onPointerUp = () => {
    if (tool.mode === 'subtract' && dragFrom && cursor) {
      const a = toPx(dragFrom);
      const b = toPx(cursor);
      if (Math.abs(a.x - b.x) > 4 && Math.abs(a.y - b.y) > 4) addHole(dragRect);
      setDragFrom(null);
    }
  };
  const onDoubleClick = (e) => {
    if (tool.mode === 'subtract' && tool.shape === 'poly' && (tool.draft || []).length >= 3) {
      e.preventDefault();
      addHole(tool.draft);
    }
  };

  // ── what the person sees ────────────────────────────────────────────────────────────────────────
  const centreOf = (ring) => polygonCentroid(ring.map(toPx)) || toPx(ring[0]);
  const showSplitParts = tool.mode === 'split' && (tool.parts || (preview && preview.parts));
  const parts = tool.parts || preview?.parts || null;
  const net = m2(tool.ring, tool.holes || []);
  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      data-outline-tool-layer={tool.mode}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'auto', overflow: 'visible', cursor: tool.mode === 'merge' ? (hovered ? 'pointer' : 'default') : 'crosshair' }}
      onPointerMove={onPointerMove}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
      onPointerCancel={() => setDragFrom(null)}
      onPointerLeave={() => { setCursor(null); setHoverPart(-1); setHoverNr(null); }}
      onDoubleClick={onDoubleClick}
    >
      {/* the room's outline as it stands, holes cut out (even-odd) */}
      {!(tool.mode === 'merge' && tool.union) && !showSplitParts && (
        <path d={pathOf([tool.ring, ...(tool.holes || [])], toPx)} fill={EDIT} fillOpacity={0.1} fillRule="evenodd" stroke={EDIT} strokeWidth={2} strokeLinejoin="round" pointerEvents="none" />
      )}

      {tool.mode === 'split' && parts && parts.map((p, i) => {
        const kept = tool.keep === i;
        const lit = tool.parts ? (hoverPart === i || kept) : false;
        const col = tool.keep == null ? (lit ? KEEP : EDIT) : (kept ? KEEP : OTHER);
        const area = m2(p.ring, p.holes);
        const label = tool.parts
          ? (tool.keep == null ? `${fmt(area)} — spustelėkite, jei lieka ${tool.nr}` : (kept ? `Lieka ${tool.nr}: ${fmt(area)}` : `Kita dalis: ${fmt(area)}`))
          : fmt(area);
        return (
          <g key={`part${i}`} data-split-part={i}>
            <path d={pathOf([p.ring, ...p.holes], toPx)} fill={col} fillOpacity={lit ? 0.22 : 0.1} fillRule="evenodd"
              stroke={col} strokeWidth={2} strokeDasharray={tool.keep != null && !kept ? '6 4' : undefined} pointerEvents="none" />
            <Chip at={centreOf(p.ring)} text={label} tone={kept ? 'keep' : 'dark'} />
          </g>
        );
      })}
      {tool.mode === 'split' && !tool.parts && tool.a && (
        <g pointerEvents="none">
          {cursor && <line x1={toPx(tool.a).x} y1={toPx(tool.a).y} x2={toPx(cursor).x} y2={toPx(cursor).y} stroke={EDIT} strokeWidth={1.5} strokeDasharray="5 4" />}
          {preview?.chord && (
            <line x1={toPx(preview.chord[0]).x} y1={toPx(preview.chord[0]).y} x2={toPx(preview.chord[1]).x} y2={toPx(preview.chord[1]).y} stroke={EDIT} strokeWidth={2.5} />
          )}
          <circle cx={toPx(tool.a).x} cy={toPx(tool.a).y} r={5} fill="#ffffff" stroke={EDIT} strokeWidth={2} />
        </g>
      )}
      {tool.mode === 'split' && tool.parts && tool.chord && (
        <line pointerEvents="none" x1={toPx(tool.chord[0]).x} y1={toPx(tool.chord[0]).y} x2={toPx(tool.chord[1]).x} y2={toPx(tool.chord[1]).y} stroke={EDIT} strokeWidth={2.5} />
      )}
      {tool.mode === 'split' && !tool.parts && cursor && <circle cx={toPx(cursor).x} cy={toPx(cursor).y} r={4} fill={EDIT} pointerEvents="none" />}

      {tool.mode === 'merge' && neighbours.map((r) => {
        const ring = r.polygon_pct.map(([x, y]) => [Number(x), Number(y)]);
        const nr = String(r.nr);
        const picked = nr === tool.targetNr;
        const refused = tool.refused?.nr === nr;
        const lit = nr === hoverNr;
        return (
          <g key={`n${nr}`} data-merge-target={nr}
            onPointerEnter={() => setHoverNr(nr)} onPointerLeave={() => setHoverNr((cur) => (cur === nr ? null : cur))}>
            <path d={pathOf([ring, ...roomHoles(r)], toPx)} fill={refused ? '#dc2626' : OTHER} fillOpacity={lit ? 0.2 : 0.06} fillRule="evenodd"
              stroke={refused ? '#dc2626' : OTHER} strokeWidth={lit || picked ? 2 : 1.25} strokeDasharray={picked ? undefined : '6 4'} />
            {(lit || picked) && <Chip at={centreOf(ring)} text={`${nr} · ${r.pavadinimas || ''}`.trim()} />}
          </g>
        );
      })}
      {tool.mode === 'merge' && (hoverMerge?.union || tool.union) && (() => {
        const u = hoverMerge?.union || tool.union;
        return (
          <g pointerEvents="none">
            <path d={pathOf([u.ring, ...u.holes], toPx)} fill={KEEP} fillOpacity={0.14} fillRule="evenodd" stroke={KEEP} strokeWidth={2.5} />
            <Chip at={centreOf(u.ring)} tone="keep" text={`${tool.nr} + ${hoverMerge ? hovered.nr : tool.targetNr} = ${fmt(m2(u.ring, u.holes))}`} />
          </g>
        );
      })()}
      {tool.mode === 'merge' && hoverMerge?.refused && hovered && (
        <Chip at={centreOf(hovered.polygon_pct.map(([x, y]) => [Number(x), Number(y)]))} text={hoverMerge.refused === 'apart' ? 'nesiliečia — sujungti negalima' : 'persidengia — sujungti negalima'} />
      )}
      {tool.mode === 'merge' && !hoverMerge && !tool.union && <Chip at={centreOf(tool.ring)} text={`${tool.nr}: ${fmt(net)}`} />}

      {tool.mode === 'subtract' && (
        <g pointerEvents="none">
          {dragRect && <path d={pathOf([dragRect], toPx)} fill={HOLE} fillOpacity={0.18} stroke={HOLE} strokeWidth={1.5} strokeDasharray="4 3" />}
          {(tool.draft || []).length > 0 && (
            <polyline points={[...tool.draft, ...(cursor ? [cursor] : [])].map((p) => { const q = toPx(p); return `${q.x},${q.y}`; }).join(' ')}
              fill="none" stroke={HOLE} strokeWidth={1.5} strokeDasharray="4 3" />
          )}
          {(tool.draft || []).map((p, i) => <circle key={i} cx={toPx(p).x} cy={toPx(p).y} r={i === 0 ? 5 : 3} fill="#ffffff" stroke={HOLE} strokeWidth={1.5} />)}
          <Chip
            at={centreOf(tool.ring)}
            text={dragRect
              ? `${fmt(net)} − ${fmt(m2(dragRect))}`
              : `${tool.nr}: ${fmt(net)}${(tool.holes || []).length ? ` (be ${tool.holes.length} išpjov.)` : ''}`}
          />
        </g>
      )}
    </svg>
  );
}

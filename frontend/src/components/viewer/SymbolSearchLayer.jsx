import { useRef, useState } from 'react';
import { boxFromDrag, formatScore } from '@/lib/symbolSearch';

/**
 * SymbolSearchLayer — one page's part of „Rasti panašius": drag a box around a
 * symbol, see the candidates the backend found on this sheet as numbered hollow
 * markers with their score, click a wrong one to remove it.
 *
 * Mounted per page by PageOverlayHost while the search is open. All geometry is
 * in top-left mediabox PDF points; `adapter` (embedPdfAdapter) is the only
 * screen⇄PDF boundary, so the box is right on /Rotate pages and at any zoom.
 * State lives in useSymbolSearch (TakeoffViewer) — this page host unmounts when
 * it scrolls out of the virtualization buffer.
 */
export default function SymbolSearchLayer({
  adapter,
  pageNr,
  canDraw = true,
  candidates = [],          // visible on this page: [{id, box, score, isSource}]
  numbers = {},             // id → the number the review list shows
  templateBox = null,       // [x0, y0, x1, y1] when this page holds the example
  hoveredId = null,
  onBox,
  onRemove,
  onHover,
}) {
  const svgRef = useRef(null);
  const [drag, setDrag] = useState(null);   // {a, b} in PDF points

  const toPdf = (e) => {
    const r = svgRef.current?.getBoundingClientRect();
    if (!r) return null;
    return adapter.toPdf({ x: e.clientX - r.left, y: e.clientY - r.top });
  };
  const rectOf = (box) => {
    const a = adapter.toViewport({ x: box[0], y: box[1] });
    const b = adapter.toViewport({ x: box[2], y: box[3] });
    return { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), w: Math.abs(b.x - a.x), h: Math.abs(b.y - a.y) };
  };

  const onPointerDown = (e) => {
    if (!canDraw || e.button !== 0) return;
    const p = toPdf(e);
    if (!p) return;
    e.preventDefault();
    e.stopPropagation();
    svgRef.current?.setPointerCapture?.(e.pointerId);
    setDrag({ a: p, b: p });
  };
  const onPointerMove = (e) => {
    if (!drag) return;
    const p = toPdf(e);
    if (p) setDrag((d) => (d ? { ...d, b: p } : d));
  };
  const onPointerUp = (e) => {
    if (!drag) return;
    e.stopPropagation();
    svgRef.current?.releasePointerCapture?.(e.pointerId);
    const p = toPdf(e) || drag.b;
    const box = boxFromDrag(drag.a, p);
    setDrag(null);
    onBox?.(pageNr, box);   // null = too small; the owner says so
  };

  const dragBox = drag ? boxFromDrag(drag.a, drag.b, 0) : null;
  const AI = 'hsl(var(--conf-med))';
  const SOURCE = 'hsl(var(--viewer-chrome-active))';

  return (
    <svg
      ref={svgRef}
      width={adapter.width}
      height={adapter.height}
      style={{ position: 'absolute', inset: 0, cursor: canDraw ? 'crosshair' : 'default', touchAction: 'none' }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={() => setDrag(null)}
      data-testid={`symbol-search-layer-${pageNr}`}
    >
      {templateBox && (() => {
        const r = rectOf(templateBox);
        return <rect x={r.x - 2} y={r.y - 2} width={r.w + 4} height={r.h + 4} fill="none" stroke={SOURCE} strokeWidth={1.5} strokeDasharray="4 3" pointerEvents="none" />;
      })()}
      {candidates.map((c) => {
        const r = rectOf(c.box);
        const hot = c.id === hoveredId;
        const colour = c.isSource ? SOURCE : AI;
        const n = numbers[c.id];
        const tag = `${n ?? ''} · ${formatScore(c.score)}`;
        const tagW = 8 + tag.length * 5.6;
        return (
          <g
            key={c.id}
            style={{ cursor: 'pointer' }}
            onPointerDown={(e) => { e.stopPropagation(); }}
            onClick={(e) => { e.stopPropagation(); onRemove?.(c.id); }}
            onPointerEnter={() => onHover?.(c.id)}
            onPointerLeave={() => onHover?.(null)}
            data-testid="symbol-candidate"
          >
            <title>{c.isSource
              ? `Jūsų pavyzdys · panašumas ${formatScore(c.score)} · spustelėkite — pašalinti`
              : `Nr. ${n} · panašumas ${formatScore(c.score)} · spustelėkite, jei tai ne tas simbolis — pašalinti`}</title>
            <rect x={r.x} y={r.y} width={r.w} height={r.h} fill={colour} fillOpacity={hot ? 0.22 : 0.04}
              stroke={colour} strokeWidth={hot ? 2.5 : 1.5} />
            <rect x={r.x} y={r.y - 13} width={tagW} height={12} rx={2} fill={colour} />
            <text x={r.x + 4} y={r.y - 4} fontSize={9.5} fontFamily="IBM Plex Mono, monospace" fill="#fff">{tag}</text>
          </g>
        );
      })}
      {dragBox && (() => {
        const r = rectOf(dragBox);
        return <rect x={r.x} y={r.y} width={r.w} height={r.h} fill={SOURCE} fillOpacity={0.08} stroke={SOURCE} strokeWidth={1.5} strokeDasharray="5 3" pointerEvents="none" />;
      })()}
    </svg>
  );
}

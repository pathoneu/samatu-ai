import { useRef, useState } from 'react';
import { boxFromDrag, formatScore } from '@/lib/symbolSearch';
import { DASH, LABEL_FONT_PX, LABEL_STYLE, STROKE_PX, labelWidth, ov, paint } from '@/lib/overlayTokens';

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
 *
 * v3 overlay vocabulary (lib/overlayTokens): a candidate is a PROPOSAL until he reviews it — the one
 * dash in the proposal slate blue, its number and score on a neutral label pill; his own example is
 * solid (he drew it); the box being dragged is the tool-at-work orange.
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
  const FOUND = ov('proposed');
  const SOURCE = ov('read');

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
        return <rect x={r.x - 2} y={r.y - 2} width={r.w + 4} height={r.h + 4} fill="none" style={paint({ stroke: SOURCE })} strokeWidth={STROKE_PX} pointerEvents="none" />;
      })()}
      {candidates.map((c) => {
        const r = rectOf(c.box);
        const hot = c.id === hoveredId;
        const colour = c.isSource ? SOURCE : FOUND;
        const n = numbers[c.id];
        const tag = `${n ?? ''} · ${formatScore(c.score)}`;
        const tagW = labelWidth(tag);
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
            <rect x={r.x} y={r.y} width={r.w} height={r.h} style={paint({ fill: colour, stroke: colour })} fillOpacity={hot ? 0.22 : 0.06}
              strokeWidth={hot ? 2.5 : STROKE_PX} strokeDasharray={c.isSource ? undefined : DASH} />
            <rect x={r.x} y={r.y - 19} width={tagW} height={17} rx={2}
              style={paint({ fill: ov('label-bg'), stroke: colour })} fillOpacity={0.96} strokeWidth={hot ? 1.5 : 1} />
            <text x={r.x + 7} y={r.y - 6} fontSize={LABEL_FONT_PX} fontWeight={500}
              style={{ ...LABEL_STYLE, ...paint({ fill: ov('label-fg') }) }}>{tag}</text>
          </g>
        );
      })}
      {dragBox && (() => {
        const r = rectOf(dragBox);
        return <rect x={r.x} y={r.y} width={r.w} height={r.h} style={paint({ fill: ov('editing'), stroke: ov('editing') })} fillOpacity={0.08} strokeWidth={1.5} pointerEvents="none" />;
      })()}
    </svg>
  );
}

/**
 * SheetZoneLayer — the sheet's zones on the drawing (Pathon v3 W5-B, B2; coverage #11). Hovering a legend, a
 * table, the title block or a notes block outlines it and names it; „Rodyti sritis" (view settings) draws them
 * all, the plan included. The zones are what the program READ off the sheet, so the line is solid, in the
 * neutral wall slate (lib/overlayTokens), with the name in the one label pill.
 *
 * The zones of a sheet are asked for once it is hovered or the switch is on (lib/sheetZonesApi caches them per
 * project and page — a heavy sheet takes seconds to read, so nothing is asked for sheets nobody looks at).
 * Pointer-transparent: the hover is read from the page's own pointer moves, never by taking a click.
 */
import { useEffect, useRef, useState } from 'react';
import { fetchSheetZones } from '@/lib/sheetZonesApi';
import { hoverZoneAt, zoneLabel, zonesToDraw } from '@/lib/sheetZonesView';
import { ov, paint, STROKE_PX } from '@/lib/overlayTokens';
import OverlayLabel from './OverlayLabel';

export default function SheetZoneLayer({ projectId, page, renderedSize, shown = false, hoverable = true }) {
  const ref = useRef(null);
  const [zones, setZones] = useState(null);
  const [wanted, setWanted] = useState(shown);
  const [hovered, setHovered] = useState(null);
  const zonesRef = useRef(null);
  zonesRef.current = zones;
  const lastRef = useRef(null);          // the last pointer position over this sheet (client px)
  const hoverAt = (pt) => {
    const host = ref.current?.parentElement;
    const r = host?.getBoundingClientRect();
    if (!pt || !r || !(r.width > 0)) return null;
    return hoverZoneAt(zonesRef.current, (pt.x - r.left) / r.width, (pt.y - r.top) / r.height);
  };
  // the zones arrive after the first move: name what the pointer is already over, without waiting for it to move
  useEffect(() => { if (zones && lastRef.current) setHovered(hoverAt(lastRef.current)); }, [zones]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (shown) setWanted(true); }, [shown]);
  useEffect(() => {
    if (!wanted || !projectId || zones) return undefined;
    let alive = true;
    fetchSheetZones(projectId, page).then((a) => { if (alive) setZones(Array.isArray(a?.zones) ? a.zones : []); }).catch(() => {});
    return () => { alive = false; };
  }, [wanted, projectId, page, zones]);
  // Hover: the page host's own pointer moves (passive) — the layer itself never takes the pointer.
  useEffect(() => {
    const host = ref.current?.parentElement;
    if (!host || !hoverable) return undefined;
    let raf = 0;
    const look = () => {
      raf = 0;
      if (!lastRef.current) return;
      const z = hoverAt(lastRef.current);
      setHovered((cur) => (cur === z ? cur : z));
    };
    const move = (e) => {
      setWanted(true);
      lastRef.current = { x: e.clientX, y: e.clientY };
      if (!raf) raf = requestAnimationFrame(look);
    };
    const leave = () => { lastRef.current = null; setHovered(null); };
    host.addEventListener('pointermove', move, { passive: true });
    host.addEventListener('pointerleave', leave, { passive: true });
    return () => {
      host.removeEventListener('pointermove', move);
      host.removeEventListener('pointerleave', leave);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [hoverable]); // eslint-disable-line react-hooks/exhaustive-deps
  const W = renderedSize?.width || 0;
  const H = renderedSize?.height || 0;
  const draw = W > 0 && H > 0 ? zonesToDraw(zones, { shown, hovered: hoverable ? hovered : null }) : [];
  return (
    <div ref={ref} style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }} data-sheet-zone-layer={page}>
      {draw.length > 0 && (
        <svg width={W} height={H} style={{ position: 'absolute', inset: 0, overflow: 'visible' }} aria-hidden="true">
          {draw.map((z, i) => {
            const [x0, y0, x1, y1] = z.bbox_pct;
            const box = { x: x0 * W, y: y0 * H, w: (x1 - x0) * W, h: (y1 - y0) * H };
            return (
              <g key={`${z.kind}-${i}`} data-sheet-zone={z.kind}>
                <rect
                  x={box.x} y={box.y} width={box.w} height={box.h}
                  style={paint({ stroke: ov('wall'), fill: z.kind === 'planas' ? 'none' : ov('wall', 0.06) })}
                  strokeWidth={STROKE_PX}
                />
                <OverlayLabel x={box.x + 4} y={Math.max(12, box.y - 12)} anchor="start" text={zoneLabel(z)} border={ov('wall', 0.6)} />
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

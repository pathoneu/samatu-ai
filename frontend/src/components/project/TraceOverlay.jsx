/**
 * TraceOverlay — pagal active/hovered row trace_type/trace_links piešia
 * brėžinyje atitinkamus elementus: dot'us (counted), polygons (area),
 * linijas (linear).
 *
 * Style guide:
 *  - active row → solid raudonas (#ef4444), 100% opacity, 16px markeris
 *  - hovered row → pulsing fade (50%/100% opacity, 1.5s cycle)
 *  - jei active.page_nr != activePage → markeris invisibleas, bet sheets
 *    sidebar'e atitinkamas puslapis pulses (handled by parent)
 */

import { useEffect, useState } from 'react';
import { Stage, Layer, Circle, Line, Group, Rect } from 'react-konva';

const COUNTED_COLOR = '#ef4444';   // red — clicked symbols
const AREA_COLOR    = '#10b981';   // emerald — clicked rooms
const LINEAR_COLOR  = '#3b82f6';   // blue — clicked perimeter
const HOVER_COLOR   = '#f59e0b';   // amber — hover state

export default function TraceOverlay({
  width, height, page,
  activeRow, hoveredRow,    // {trace_type, trace_links, ...}
  pageWidthPdf, pageHeightPdf,  // iš PdfViewer Page onLoadSuccess
}) {
  // Pulse animation state for hovered row
  const [pulseT, setPulseT] = useState(0);
  useEffect(() => {
    if (!hoveredRow) return;
    const start = Date.now();
    const id = setInterval(() => {
      const elapsed = (Date.now() - start) / 1500;  // 1.5s cycle
      setPulseT(0.5 + 0.5 * Math.sin(elapsed * Math.PI * 2));
    }, 50);
    return () => clearInterval(id);
  }, [hoveredRow?._id]);   

  const renderLinks = (row, color, opacity = 1) => {
    if (!row || !row.trace_links) return null;
    const links = row.trace_links.filter(l => (l.page_nr || 1) === page);
    if (!links.length) return null;
    const tt = row.trace_type;

    return links.map((link, i) => {
      const key = `${row._id}-${i}`;

      // ─ Counted: raudonas dot'as koordinatėje ──────────────────────────────
      if (tt === 'counted' && link.x_pct != null && link.y_pct != null) {
        const x = link.x_pct * width;
        const y = link.y_pct * height;
        return (
          <Group key={key}>
            <Circle x={x} y={y} radius={12} stroke={color} strokeWidth={2}
                    fill={`${color}33`} opacity={opacity} />
            <Circle x={x} y={y} radius={3} fill={color} opacity={opacity} />
          </Group>
        );
      }

      // ─ Area: polygon spalvotai užpildytas ─────────────────────────────────
      if (tt === 'area') {
        // Bandom polygon_pdf (V9 — tikslus polygon)
        const pdfW = link.page_width_pdf || pageWidthPdf;
        const pdfH = link.page_height_pdf || pageHeightPdf;
        if (link.polygon_pdf && link.polygon_pdf.length >= 3 && pdfW && pdfH) {
          const pts = link.polygon_pdf.flatMap(p => [
            (p[0] / pdfW) * width,
            (p[1] / pdfH) * height,
          ]);
          return (
            <Line key={key} points={pts} closed
                  fill={`${color}55`} stroke={color} strokeWidth={2}
                  opacity={opacity} listening={false} />
          );
        }
        // Fallback į bbox_pct (V8 endpoint — Vision tik bbox)
        if (link.bbox_pct) {
          const bb = link.bbox_pct;
          if (bb.w > 0 && bb.h > 0) {
            return (
              <Rect key={key}
                    x={bb.x * width} y={bb.y * height}
                    width={bb.w * width} height={bb.h * height}
                    fill={`${color}40`} stroke={color} strokeWidth={2}
                    cornerRadius={2} opacity={opacity} listening={false} />
            );
          }
        }
        return null;
      }

      // ─ Linear: polygon perimeter (be fill) ────────────────────────────────
      if (tt === 'linear') {
        const pdfW = link.page_width_pdf || pageWidthPdf;
        const pdfH = link.page_height_pdf || pageHeightPdf;
        if (link.polygon_pdf && link.polygon_pdf.length >= 3 && pdfW && pdfH) {
          const pts = link.polygon_pdf.flatMap(p => [
            (p[0] / pdfW) * width,
            (p[1] / pdfH) * height,
          ]);
          return (
            <Line key={key} points={pts} closed={false}
                  stroke={color} strokeWidth={3} opacity={opacity}
                  lineJoin="round" listening={false} />
          );
        }
        // Fallback: bbox borders (rectangle outline, no fill)
        if (link.bbox_pct) {
          const bb = link.bbox_pct;
          if (bb.w > 0 && bb.h > 0) {
            return (
              <Rect key={key}
                    x={bb.x * width} y={bb.y * height}
                    width={bb.w * width} height={bb.h * height}
                    fill="transparent" stroke={color} strokeWidth={3}
                    cornerRadius={2} opacity={opacity} listening={false} />
            );
          }
        }
        return null;
      }

      return null;
    });
  };

  if (!activeRow && !hoveredRow) return null;

  return (
    <Stage
      width={width}
      height={height}
      style={{
        position: 'absolute', top: 0, left: 0,
        pointerEvents: 'none', zIndex: 20,
      }}
      listening={false}
    >
      <Layer listening={false}>
        {/* Hovered row (background, pulsing) */}
        {hoveredRow && hoveredRow._id !== activeRow?._id &&
          renderLinks(hoveredRow, HOVER_COLOR, pulseT)}

        {/* Active row (foreground, solid) */}
        {activeRow && renderLinks(
          activeRow,
          activeRow.trace_type === 'area' ? AREA_COLOR
            : activeRow.trace_type === 'linear' ? LINEAR_COLOR
            : COUNTED_COLOR,
          1.0,
        )}
      </Layer>
    </Stage>
  );
}

/**
 * AiRoomOverlay — Togal-style AI auto-detect overlay.
 *
 * AI grąžina patalpas su `bbox_pct: {x, y, w, h}` (procentais nuo puslapio).
 * Šis komponentas perdengia PDF su žaliomis transparentinėmis zonomis,
 * kiekviena su patalpos pavadinimu + plotu.
 *
 * Vartotojas mato VISUS AI atpažintus kambarius automatiškai (Togal Button stilius).
 */

import { Stage, Layer, Rect, Text as KonvaText, Group, Line } from 'react-konva';

const COLORS_BY_PASKIRTIS = {
  gyvenamoji:  '#10b981',  // green
  miegamoji:   '#3b82f6',  // blue
  virtuve:     '#f59e0b',  // amber
  vonia:       '#06b6d4',  // cyan
  wc:          '#06b6d4',
  san:         '#06b6d4',
  koridorius:  '#a78bfa',  // violet
  holas:       '#a78bfa',
  drabuzine:   '#ec4899',  // pink
  sandeliukas: '#94a3b8',  // slate
  garazas:     '#64748b',  // gray
  tambūras:    '#64748b',
  katiline:    '#94a3b8',
};

function colorFor(paskirtis) {
  return COLORS_BY_PASKIRTIS[paskirtis] || '#10b981';
}

export default function AiRoomOverlay({
  width, height, page, rooms,
  onRoomClick,
}) {
  if (!rooms || rooms.length === 0) return null;

  // Filtruojam patalpas tik šiam puslapiui (palaikom V9 polygon_pdf + V8 bbox_pct)
  const pageRooms = rooms.filter(r => {
    const pageNr = r.page_nr || r.puslapio_nr || r.page || 1;
    return pageNr === page && (r.polygon_pdf || r.bbox_pct);
  });

  if (pageRooms.length === 0) return null;

  return (
    <Stage
      width={width}
      height={height}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        pointerEvents: 'none',  // PDF lieka klikuojamas, mes tik overlay
      }}
    >
      <Layer listening={true}>
        {pageRooms.map((room, idx) => {
          const color = colorFor(room.paskirtis);
          let cx, cy, shape;

          // V9: polygon_pdf (vector poligonai — TIKSLU)
          if (room.polygon_pdf && Array.isArray(room.polygon_pdf) && room.polygon_pdf.length >= 3) {
            // polygon_pdf yra PDF coordinates — turim convertuoti į pikseliais
            // Reikia žinoti PDF page width/height. Naudojam centroid_pct + bounds estimate.
            // Jei centroid_pct yra — naudojam jį, kitaip apskaičiuojam iš polygono.
            const pdfW = room.page_width_pdf || room.pdf_page_width;
            const pdfH = room.page_height_pdf || room.pdf_page_height;

            // Jei žinome PDF dimensijas — naudojam exact mapping
            if (pdfW && pdfH) {
              const pts = room.polygon_pdf.flatMap(p => [
                (p[0] / pdfW) * width,
                (p[1] / pdfH) * height,
              ]);
              shape = (
                <Line
                  points={pts}
                  fill={`${color}22`}
                  stroke={color}
                  strokeWidth={2}
                  closed={true}
                  listening={true}
                />
              );
              const cp = room.centroid_pct;
              if (cp && Array.isArray(cp)) {
                cx = cp[0] * width;
                cy = cp[1] * height;
              } else {
                // Aproks centroidą iš polygon vidurio
                const xs = room.polygon_pdf.map(p => (p[0] / pdfW) * width);
                const ys = room.polygon_pdf.map(p => (p[1] / pdfH) * height);
                cx = (Math.min(...xs) + Math.max(...xs)) / 2;
                cy = (Math.min(...ys) + Math.max(...ys)) / 2;
              }
            } else if (room.centroid_pct) {
              // Be PDF dim — naudojam centroid_pct + bbox_pct (jei yra)
              const cp = room.centroid_pct;
              cx = cp[0] * width;
              cy = cp[1] * height;
              if (room.bbox_pct) {
                const bb = room.bbox_pct;
                shape = (
                  <Rect
                    x={bb.x * width} y={bb.y * height}
                    width={bb.w * width} height={bb.h * height}
                    fill={`${color}22`}
                    stroke={color}
                    strokeWidth={2}
                    cornerRadius={2}
                  />
                );
              }
            }
          }

          // V8 fallback: bbox_pct (rectangle)
          if (!shape && room.bbox_pct) {
            const bb = room.bbox_pct;
            if (!bb || bb.w <= 0 || bb.h <= 0) return null;
            const x = bb.x * width;
            const y = bb.y * height;
            const w = bb.w * width;
            const h = bb.h * height;
            cx = x + w / 2;
            cy = y + h / 2;
            shape = (
              <Rect
                x={x} y={y} width={w} height={h}
                fill={`${color}22`}
                stroke={color}
                strokeWidth={1.5}
                cornerRadius={2}
                listening={true}
              />
            );
          }

          if (!shape) return null;

          const labelText = room.pavadinimas || `#${room.nr}`;
          const areaText = room.plotas_m2 ? `${room.plotas_m2.toFixed(1)} m²` : '';

          return (
            <Group
              key={`${room.nr}-${idx}`}
              listening={true}
              onClick={() => onRoomClick?.(room)}
              onTap={() => onRoomClick?.(room)}
              style={{ pointerEvents: 'auto' }}
            >
              {shape}
              {/* Label fone */}
              <Rect
                x={cx - 50} y={cy - 16}
                width={100} height={32}
                fill="white"
                stroke={color}
                strokeWidth={1}
                cornerRadius={3}
                opacity={0.95}
              />
              {/* Label tekstas */}
              <KonvaText
                x={cx - 48} y={cy - 12}
                text={labelText}
                fontSize={11}
                fontStyle="bold"
                fill="#1f2937"
                width={96}
                align="center"
                ellipsis
              />
              <KonvaText
                x={cx - 48} y={cy + 1}
                text={areaText}
                fontSize={10}
                fill={color}
                width={96}
                align="center"
              />
            </Group>
          );
        })}
      </Layer>
    </Stage>
  );
}

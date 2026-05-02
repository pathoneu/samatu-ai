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

// Phase C-4-bis: per-category colors per Kreo competitor research. Each room
// paskirtis gets its own hue so a glance at the polygon overlay reveals the
// floor plan's functional zones without reading labels.
const COLORS_BY_PASKIRTIS = {
  gyvenamoji:  '#10b981',  // green — svetainė / gyvenamasis
  svetaine:    '#10b981',
  miegamoji:   '#3b82f6',  // blue — miegamasis
  miegamasis:  '#3b82f6',
  vaikui:      '#3b82f6',
  virtuve:     '#f59e0b',  // amber — virtuvė
  valgomasis:  '#f59e0b',
  vonia:       '#06b6d4',  // cyan — vonia / sanitarinės patalpos
  vonios:      '#06b6d4',
  wc:          '#06b6d4',
  san:         '#06b6d4',
  sanitarine:  '#06b6d4',
  koridorius:  '#a78bfa',  // violet — bendro naudojimo praeigos
  holas:       '#a78bfa',
  prieskambaris:'#a78bfa',
  drabuzine:   '#ec4899',  // pink — uždaras dėvėjimas
  rūbinė:      '#ec4899',
  sandeliukas: '#94a3b8',  // slate — sandėliavimas
  saugykla:    '#94a3b8',
  garazas:     '#64748b',  // gray — techninės / ūkinės
  tambūras:    '#64748b',
  tamburas:    '#64748b',
  katiline:    '#94a3b8',
  ukio:        '#94a3b8',
  balkonas:    '#22c55e',  // bright green — atviros zonos
  terasa:      '#22c55e',
};

function colorFor(paskirtis) {
  return COLORS_BY_PASKIRTIS[paskirtis] || '#10b981';
}

// SM01-debug: A/B Y-flip toggle. Default OFF after visual diagnosis
// (2026-04-27 P1 sample): Vision is already emitting top-left origin for
// bbox_pct, so no flip needed. The flag remains for future investigation
// if a project shows rooms inverted — try
// `localStorage.setItem('samatu_bbox_flip_y', 'true')` and refresh.
function shouldFlipY() {
  try {
    return localStorage.getItem('samatu_bbox_flip_y') === 'true';
  } catch {
    return false;
  }
}

export default function AiRoomOverlay({
  width, height, page, rooms,
  onRoomClick,
  onRoomHover,
  highlightRoomNrs = null, // Set<roomNr> | null — Phase 14 / QW05
}) {
  if (!rooms || rooms.length === 0) return null;

  // Filtruojam patalpas tik šiam puslapiui.
  const pageRooms = rooms.filter(r => {
    const pageNr = r.page_nr || r.puslapio_nr || r.page || 1;
    // Phase C-2 (2026-05-02): only render rooms with a real polygon. The
    // legacy bbox_pct rectangles flashed in wrong locations and have been
    // dropped from the overlay. Eksplikacija numbers printed on the drawing
    // handle the visual "where" question for free.
    return pageNr === page && Array.isArray(r.polygon_pdf) && r.polygon_pdf.length >= 3;
  });

  if (pageRooms.length === 0) return null;

  const flipY = shouldFlipY();

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
          const isHighlight = highlightRoomNrs?.has?.(room.nr) === true;
          // Phase C-4-bis: thicker stroke + brighter fill so polygons read
          // clearly on the dark blueprint frame. Highlight (room-from-panel
          // jump) bumps the stroke + fill further.
          const strokeW = isHighlight ? 4 : 2.5;
          const fillAlpha = isHighlight ? '55' : '33';
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
                  fill={`${color}${fillAlpha}`}
                  stroke={color}
                  strokeWidth={strokeW}
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
              cy = (flipY ? (1 - cp[1]) : cp[1]) * height;
              if (room.bbox_pct) {
                const bb = room.bbox_pct;
                const by = flipY ? (1 - bb.y - bb.h) * height : bb.y * height;
                shape = (
                  <Rect
                    x={bb.x * width} y={by}
                    width={bb.w * width} height={bb.h * height}
                    fill={`${color}${fillAlpha}`}
                    stroke={color}
                    strokeWidth={strokeW}
                    cornerRadius={2}
                  />
                );
              }
            }
          }

          // Phase C-2 (2026-05-02): bbox_pct rendering removed. Only polygon_pdf
          // rooms reach this point per the filter above.

          if (!shape) return null;

          const labelText = room.pavadinimas || `#${room.nr}`;
          const areaText = room.plotas_m2 ? `${room.plotas_m2.toFixed(1)} m²` : '';

          return (
            <Group
              key={`${room.nr}-${idx}`}
              listening={true}
              onClick={() => onRoomClick?.(room)}
              onTap={() => onRoomClick?.(room)}
              onMouseEnter={() => onRoomHover?.(room)}
              onMouseLeave={() => onRoomHover?.(null)}
              style={{ pointerEvents: 'auto', cursor: onRoomHover ? 'pointer' : 'default' }}
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

/**
 * DrawingGeometryLayer — what the program READ on this sheet, all rooms at once: the wall solid
 * (api/page_geometry), every room's outline (`polygon_pct`) and the openings the wall solid shows in
 * their walls (`_angos_sienose`). Togal's „Layers" view (2026-10-16 analysis §5), here as a QA layer
 * the wall-icon toolbar button turns on — at rest the drawing stays clean (founder decision 2026-07-14).
 *
 * v3 overlay vocabulary (lib/overlayTokens, legend in OverlayLegend): an outline traced off the walls
 * or confirmed by him is SOLID, an estimated one (flood fill, a box) DASHED; walls slate, openings
 * violet with their width written beside them in the app's sans on a white halo.
 *
 * Every coordinate is a DISPLAY-frame page fraction; PageOverlayHost's wrapper rotates the whole page,
 * so nothing is rotated here. Pointer-transparent: clicks go through to zones and measure tools.
 */
import { useMemo } from 'react';
import { roomPageOf } from '@/lib/roomZones';
import { formatNumberLT } from '@/lib/measureGeometry';
import { LABEL_FONT_PX, LABEL_STYLE, STROKE_PX, lineStyle, outlineKindOf, ov, paint } from '@/lib/overlayTokens';

export default function DrawingGeometryLayer({ geometry, rooms = [], page, renderedSize }) {
  const { width, height } = renderedSize || {};
  const onPage = useMemo(() => (rooms || []).filter((r) => roomPageOf(r) === page), [rooms, page]);
  if (!width || !height) return null;
  const X = (p) => p[0] * width;
  const Y = (p) => p[1] * height;
  const poly = (pts) => pts.map((p) => `${X(p).toFixed(1)},${Y(p).toFixed(1)}`).join(' ');
  const rings = Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : [];
  return (
    <svg
      width={width}
      height={height}
      style={{ position: 'absolute', inset: 0, pointerEvents: 'none', overflow: 'visible' }}
      data-drawing-geometry-layer
    >
      {rings.map((ring, i) => (
        <polygon key={`w${i}`} points={poly(ring)} style={paint({ fill: ov('wall'), stroke: ov('wall') })} fillOpacity={0.22} strokeOpacity={0.8} strokeWidth={1} />
      ))}
      {onPage.map((r) => {
        const pts = Array.isArray(r.polygon_pct) && r.polygon_pct.length >= 3 ? r.polygon_pct : null;
        const gaps = Number(r?._angos_sienose?.page) === page && Array.isArray(r?._angos_sienose?.angos)
          ? r._angos_sienose.angos : [];
        const kind = outlineKindOf(r);
        const line = lineStyle(kind);
        // „Atimti" cut-outs (2026-10-16): a column or a shaft shows through the outline's fill (even-odd)
        const holes = pts && Array.isArray(r.polygon_holes_pct) ? r.polygon_holes_pct.filter((h) => Array.isArray(h) && h.length >= 3) : [];
        return (
          <g key={`r${r.nr}`} data-room-nr={r.nr} data-outline={kind}>
            {pts && (
              <path
                d={[pts, ...holes].map((ring) => `M ${poly(ring).replace(/ /g, ' L ')} Z`).join(' ')}
                style={paint({ fill: line.stroke, stroke: line.stroke })} fillOpacity={0.04} fillRule="evenodd"
                strokeWidth={STROKE_PX} strokeLinejoin="round"
                strokeDasharray={line.dash || undefined}
                data-holes={holes.length || undefined}
              />
            )}
            {gaps.filter((g) => Array.isArray(g.line_pct) && g.line_pct.length === 2).map((g, i) => {
              const [a, b] = g.line_pct;
              const prefix = g.nupiesta === 'durys' ? 'D ' : g.nupiesta === 'langas' ? 'L ' : '';
              return (
                <g key={`o${i}`}>
                  <line x1={X(a)} y1={Y(a)} x2={X(b)} y2={Y(b)} style={paint({ stroke: ov('opening') })} strokeWidth={5} strokeLinecap="butt" strokeOpacity={0.9} />
                  <text
                    x={(X(a) + X(b)) / 2} y={(Y(a) + Y(b)) / 2 - 6}
                    fontSize={LABEL_FONT_PX} fontWeight={600} textAnchor="middle"
                    paintOrder="stroke" strokeWidth={3} strokeLinejoin="round"
                    style={{ ...LABEL_STYLE, ...paint({ fill: ov('opening'), stroke: ov('label-bg') }) }}
                  >
                    {prefix}{formatNumberLT(Number(g.plotis_m) || 0, 2)} m
                  </text>
                </g>
              );
            })}
          </g>
        );
      })}
    </svg>
  );
}

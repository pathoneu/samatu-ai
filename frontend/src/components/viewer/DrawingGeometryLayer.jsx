/**
 * DrawingGeometryLayer — what the program READ on this sheet, all rooms at once: the wall solid
 * (api/page_geometry), every room's outline (`polygon_pct`) and the openings the wall solid shows in
 * their walls (`_angos_sienose`). Togal's „Layers" view (2026-10-16 analysis §5), here as a QA layer
 * the wall-icon toolbar button turns on — at rest the drawing stays clean (founder decision 2026-07-14).
 *
 * Every coordinate is a DISPLAY-frame page fraction; PageOverlayHost's wrapper rotates the whole page,
 * so nothing is rotated here. Pointer-transparent: clicks go through to zones and measure tools.
 */
import { useMemo } from 'react';
import { roomPageOf } from '@/lib/roomZones';
import { formatNumberLT } from '@/lib/measureGeometry';

const WALL = '#475569';          // slate — the solid the lane read
const OUTLINE = '#2f6b4f';       // the theme's evergreen — a room's outline
const OPENING = '#7c3aed';       // violet, as CheckLayer draws a room's openings

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
        <polygon key={`w${i}`} points={poly(ring)} fill={WALL} fillOpacity={0.22} stroke={WALL} strokeOpacity={0.7} strokeWidth={1} />
      ))}
      {onPage.map((r) => {
        const pts = Array.isArray(r.polygon_pct) && r.polygon_pct.length >= 3 ? r.polygon_pct : null;
        const gaps = Number(r?._angos_sienose?.page) === page && Array.isArray(r?._angos_sienose?.angos)
          ? r._angos_sienose.angos : [];
        const confirmed = r.polygon_source === 'corrected' || r.polygon_source === 'manual';
        // „Atimti" cut-outs (2026-10-16): a column or a shaft shows through the outline's fill (even-odd)
        const holes = pts && Array.isArray(r.polygon_holes_pct) ? r.polygon_holes_pct.filter((h) => Array.isArray(h) && h.length >= 3) : [];
        return (
          <g key={`r${r.nr}`} data-room-nr={r.nr}>
            {pts && (
              <path
                d={[pts, ...holes].map((ring) => `M ${poly(ring).replace(/ /g, ' L ')} Z`).join(' ')}
                fill={OUTLINE} fillOpacity={0.04} fillRule="evenodd"
                stroke={OUTLINE} strokeWidth={1.5} strokeLinejoin="round"
                strokeDasharray={confirmed ? undefined : '6 4'}
                data-holes={holes.length || undefined}
              />
            )}
            {gaps.filter((g) => Array.isArray(g.line_pct) && g.line_pct.length === 2).map((g, i) => {
              const [a, b] = g.line_pct;
              const prefix = g.nupiesta === 'durys' ? 'D ' : g.nupiesta === 'langas' ? 'L ' : '';
              return (
                <g key={`o${i}`}>
                  <line x1={X(a)} y1={Y(a)} x2={X(b)} y2={Y(b)} stroke={OPENING} strokeWidth={5} strokeLinecap="butt" strokeOpacity={0.85} />
                  <text
                    x={(X(a) + X(b)) / 2} y={(Y(a) + Y(b)) / 2 - 6}
                    fontSize={10} fontFamily="system-ui, sans-serif" fill={OPENING} textAnchor="middle"
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

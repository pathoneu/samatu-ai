/**
 * RoomZoneLayer — the AI Takeoff Viewer's first visible layer (Phase 1).
 *
 * Draws the app's ALREADY-COMPUTED rooms onto the PDF page as translucent SVG
 * zones: paskirtis-colored fill (identity) + name + area label + a confidence
 * dot (honesty). Synthesized/bbox geometry gets a DASHED border + "apytikslė"
 * so the viewer never fakes a precise outline (design spec §9).
 *
 * A FACE over the engine — no quantity math here. Geometry + confidence come
 * from lib/roomZones (which reuses planOverlayGeometry + areaConfidence).
 *
 * Pattern mirrors FillPolygonOverlay: an absolutely-positioned SVG with
 * pointer-events:none, and pointer-events:auto only on each <g>, so clicks land
 * on zones and pass THROUGH the gaps to the PDF / pan handler underneath.
 */

import { useMemo } from 'react';
import { buildPageRoomZones, countRoomsMissingGeometry } from '@/lib/roomZones';

function centroidOf(geometry) {
  if (geometry.type === 'marker') return { cx: geometry.cx, cy: geometry.cy };
  if (geometry.type === 'rect') {
    return {
      cx: geometry.left + geometry.width / 2,
      cy: geometry.top + geometry.height / 2,
    };
  }
  const xs = geometry.points.map((p) => p[0]);
  const ys = geometry.points.map((p) => p[1]);
  return {
    cx: (Math.min(...xs) + Math.max(...xs)) / 2,
    cy: (Math.min(...ys) + Math.max(...ys)) / 2,
  };
}

export default function RoomZoneLayer({
  rooms = [],
  page,
  renderedSize,
  focusedRoomNr = null,
  onRoomClick = null,
}) {
  const width = renderedSize?.width;
  const height = renderedSize?.height;

  const zones = useMemo(() => {
    if (!width || !height) return [];
    return buildPageRoomZones(rooms, { renderedWidth: width, renderedHeight: height, page });
  }, [rooms, page, width, height]);

  const missingCount = useMemo(() => {
    if (!width || !height) return 0;
    return countRoomsMissingGeometry(rooms, { renderedWidth: width, renderedHeight: height, page });
  }, [rooms, page, width, height]);

  if (!width || !height) return null;
  if (zones.length === 0 && missingCount === 0) return null;

  return (
    <svg
      width={width}
      height={height}
      className="absolute left-0 top-0 z-[16]"
      style={{ pointerEvents: 'none' }}
    >
      {zones.map((z) => {
        const isFocused = focusedRoomNr != null && String(z.nr) === String(focusedRoomNr);
        const { cx, cy } = centroidOf(z.geometry);
        const strokeW = isFocused ? 3.5 : 2;
        const fillOpacity = isFocused ? 0.34 : 0.18;
        const dash = z.approximate ? '6 4' : undefined;

        return (
          <g
            key={z.nr}
            style={{ pointerEvents: 'auto', cursor: onRoomClick ? 'pointer' : 'default' }}
            onClick={() => onRoomClick?.(z)}
          >
            {z.geometry.type === 'marker' ? (
              <g transform={`translate(${z.geometry.cx}, ${z.geometry.cy})`}>
                <circle r={15} fill="white" fillOpacity={0.9} stroke={z.color}
                  strokeWidth={2} strokeDasharray="4 3" />
                <text x={0} y={0} textAnchor="middle" dominantBaseline="central"
                  fontSize={12} fontWeight="700" fill={z.color}
                  style={{ pointerEvents: 'none' }}>
                  {z.nr}
                </text>
              </g>
            ) : z.geometry.type === 'polygon' ? (
              <polygon
                points={z.geometry.points.map((p) => `${p[0]},${p[1]}`).join(' ')}
                fill={z.color}
                fillOpacity={fillOpacity}
                stroke={z.color}
                strokeWidth={strokeW}
                strokeDasharray={dash}
              />
            ) : (
              <rect
                x={z.geometry.left}
                y={z.geometry.top}
                width={z.geometry.width}
                height={z.geometry.height}
                rx={3}
                fill={z.color}
                fillOpacity={fillOpacity}
                stroke={z.color}
                strokeWidth={strokeW}
                strokeDasharray={dash}
              />
            )}

            {/* Label chip: white bg, confidence dot, name + area.
                Suppressed for markers — a marker already shows its number. */}
            {z.geometry.type !== 'marker' && (
              <g transform={`translate(${cx}, ${cy})`}>
                <rect
                  x={-58} y={-17} width={116} height={34} rx={4}
                  fill="white" stroke={z.color} strokeWidth={1} opacity={0.96}
                />
                <circle cx={-48} cy={-6} r={4} fill={z.confidenceColor}>
                  <title>{`Ploto pasitikėjimas: ${z.confidence}`}</title>
                </circle>
                <text
                  x={-40} y={-2} fontSize={11} fontWeight="700" fill="#1f2937"
                  style={{ pointerEvents: 'none' }}
                >
                  {z.label.length > 12 ? `${z.label.slice(0, 11)}…` : z.label}
                </text>
                <text
                  x={-40} y={11} fontSize={10} fill={z.color}
                  style={{ pointerEvents: 'none' }}
                >
                  {z.areaLabel}{z.approximate ? ' · apytikslė vieta' : ''}
                </text>
              </g>
            )}
          </g>
        );
      })}

      {/* Honest "we could not place these" chip (spec §9) */}
      {missingCount > 0 && (
        <g transform="translate(12, 12)" style={{ pointerEvents: 'none' }}>
          <rect x={0} y={0} width={250} height={24} rx={5}
            fill="#fef3c7" stroke="#fde68a" strokeWidth={1} />
          <text x={10} y={16} fontSize={11} fill="#b45309">
            {missingCount} patalpų be vietos plane — žr. „Peržiūra“
          </text>
        </g>
      )}
    </svg>
  );
}

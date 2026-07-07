/**
 * RoomZoneLayer — the AI Takeoff Viewer's first visible layer (Phase 1).
 *
 * Draws the app's ALREADY-COMPUTED rooms onto the PDF page as translucent SVG
 * zones. Declutter contract (declutter pattern, 2026-07-02): at rest a zone is a
 * quiet fill-only polygon — NO label chip. The chip (name + area + confidence
 * dot) appears only on hover, and stays pinned while the room is focused.
 * Synthesized/bbox geometry gets a DASHED border + "apytikslė" so the viewer
 * never fakes a precise outline (design spec §9).
 *
 * A FACE over the engine — no quantity math here. Geometry + confidence come
 * from lib/roomZones (which reuses planOverlayGeometry + areaConfidence).
 *
 * Pattern mirrors FillPolygonOverlay: an absolutely-positioned SVG with
 * pointer-events:none, and pointer-events:auto only on each <g>, so clicks land
 * on zones and pass THROUGH the gaps to the PDF / pan handler underneath.
 */

import { useMemo, useState } from 'react';
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

// Chip sizing: dynamic width so room names no longer truncate at 12 chars.
// 14px left pad-with-dot + 8px gap + ~6.4px/char at fontSize 11.
const CHIP_MAX_W = 200;
function chipWidthFor(label) {
  return Math.min(CHIP_MAX_W, Math.max(90, 14 + 8 + label.length * 6.4));
}
function chipLabelFor(label) {
  // Only ellipsize when the name exceeds even the clamped max width.
  const maxChars = Math.floor((CHIP_MAX_W - 22) / 6.4);
  return label.length > maxChars ? `${label.slice(0, maxChars - 1)}…` : label;
}

export default function RoomZoneLayer({
  rooms = [],
  page,
  renderedSize,
  focusedRoomNr = null,
  hiddenRoomNrs = null,
  hoveredRoomNrExternal = null,
  onRoomClick = null,
  // false while a measurement tool is armed: zones stay visible but must not
  // swallow the measure clicks (their <g> normally re-enable pointer events).
  interactive = true,
}) {
  const width = renderedSize?.width;
  const height = renderedSize?.height;

  // Internal hover — a zone brightens + shows its chip while the cursor is on it.
  const [hoverNr, setHoverNr] = useState(null);

  const zones = useMemo(() => {
    if (!width || !height) return [];
    return buildPageRoomZones(rooms, { renderedWidth: width, renderedHeight: height, page });
  }, [rooms, page, width, height]);

  const missingCount = useMemo(() => {
    if (!width || !height) return 0;
    return countRoomsMissingGeometry(rooms, { renderedWidth: width, renderedHeight: height, page });
  }, [rooms, page, width, height]);

  // Per-room visibility (panel eye toggles). Accepts a Set or an array; nrs may
  // be numbers or strings in data, so always compare as String.
  const hiddenSet = useMemo(
    () => new Set(Array.from(hiddenRoomNrs || []).map(String)),
    [hiddenRoomNrs],
  );
  const visibleZones = useMemo(
    () => zones.filter((z) => !hiddenSet.has(String(z.nr))),
    [zones, hiddenSet],
  );

  if (!width || !height) return null;
  if (zones.length === 0 && missingCount === 0) return null;

  const isFocusedZone = (z) => focusedRoomNr != null && String(z.nr) === String(focusedRoomNr);
  // Hover = internal (cursor on the zone) OR external (cursor on the panel row) —
  // the panel→canvas half of the cheap bidirectional hover sync.
  const isHoveredZone = (z) =>
    (hoverNr != null && String(z.nr) === hoverNr)
    || (hoveredRoomNrExternal != null && String(z.nr) === String(hoveredRoomNrExternal));

  return (
    <svg
      width={width}
      height={height}
      className="absolute left-0 top-0 z-[16]"
      style={{ pointerEvents: 'none' }}
    >
      {/* Pass 1: shapes only — fill-quiet at rest, brighter on hover/focus. */}
      {visibleZones.map((z) => {
        const isFocused = isFocusedZone(z);
        const isHovered = isHoveredZone(z);
        const strokeW = isFocused ? 3.5 : isHovered ? 2.5 : 1.5;
        const fillOpacity = isFocused ? 0.34 : isHovered ? 0.30 : 0.16;
        const dash = z.approximate ? '6 4' : undefined;

        return (
          <g
            key={z.nr}
            style={{
              pointerEvents: interactive ? 'auto' : 'none',
              cursor: interactive && onRoomClick ? 'pointer' : 'default',
            }}
            onClick={() => onRoomClick?.(z)}
            onMouseEnter={() => setHoverNr(String(z.nr))}
            onMouseLeave={() => setHoverNr((cur) => (cur === String(z.nr) ? null : cur))}
          >
            {z.geometry.type === 'marker' ? (
              <g transform={`translate(${z.geometry.cx}, ${z.geometry.cy})`}>
                <circle r={15} fill="white" fillOpacity={0.9} stroke={z.color}
                  strokeWidth={isHovered || isFocused ? 3 : 2} strokeDasharray="4 3" />
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
          </g>
        );
      })}

      {/* Pass 2: label chips — hovered/focused zones only, drawn AFTER every
          polygon so a chip is never buried under a neighbor zone's fill.
          Suppressed for markers — a marker already shows its number. */}
      {visibleZones.map((z) => {
        if (z.geometry.type === 'marker') return null;
        const isFocused = isFocusedZone(z);
        const isHovered = isHoveredZone(z);
        if (!isFocused && !isHovered) return null;
        const { cx, cy } = centroidOf(z.geometry);
        const w = chipWidthFor(z.label);
        const half = w / 2;
        return (
          <g
            key={`chip-${z.nr}`}
            transform={`translate(${cx}, ${cy})`}
            style={{ pointerEvents: 'none' }}
          >
            <rect
              x={-half} y={-17} width={w} height={34} rx={4}
              fill="white" stroke={z.color} strokeWidth={1} opacity={0.96}
            />
            <circle cx={-half + 10} cy={-6} r={4} fill={z.confidenceColor}>
              <title>{`Ploto pasitikėjimas: ${z.confidence}`}</title>
            </circle>
            <text x={-half + 18} y={-2} fontSize={11} fontWeight="700" fill="#1f2937">
              {chipLabelFor(z.label)}
            </text>
            <text x={-half + 18} y={11} fontSize={10} fill={z.color}>
              {z.areaLabel}{z.approximate ? ' · apytikslė vieta' : ''}
            </text>
          </g>
        );
      })}

      {/* Honest "we could not place these" chip (spec §9) — unaffected by
          per-room visibility. */}
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

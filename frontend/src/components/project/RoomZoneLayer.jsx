/**
 * RoomZoneLayer — the AI Takeoff Viewer's first visible layer (Phase 1).
 *
 * FOUNDER DECISION (2026-07-14): the DEFAULT is a CLEAN drawing — nothing is
 * drawn at rest. Selecting a room in the panel draws ONE red ring around that
 * room's own printed number (labelAnchor = the verified plan-label position),
 * checked-drawing style. One ring at a time → no de-overlap fanning → the
 * ring always lands exactly on the printed number. This replaced the
 * always-on numbered markers (2026-07-11), whose overlap-fanning pushed
 * circles onto walls and read as "numbers marked wrong".
 * The filled polygon zones stay implemented and render when `zoneFillsVisible`
 * is true (viewer toolbar Layers toggle) — the QA/verification view.
 *
 * Declutter contract (2026-07-02): at rest a shape is quiet — NO label chip.
 * The chip (name + area + confidence dot) appears on hover, and stays pinned
 * while the room is focused; a focused marker also gets a pulsing halo (the
 * "Rodyti brėžinyje" flash). Synthesized/bbox geometry stays DASHED +
 * "apytikslė" so the viewer never fakes a precise outline (design spec §9).
 *
 * A FACE over the engine — no quantity math here. Geometry + confidence come
 * from lib/roomZones (which reuses planOverlayGeometry + areaConfidence).
 *
 * Pattern mirrors FillPolygonOverlay: an absolutely-positioned SVG with
 * pointer-events:none, and pointer-events:auto only on each <g>, so clicks land
 * on zones and pass THROUGH the gaps to the PDF / pan handler underneath.
 */

import { useMemo, useState } from 'react';
import {
  buildPageRoomZones, countRoomsMissingGeometry, spreadOverlappingMarkers, missingRoomsText,
  ROOM_POLYGON_FILLS_DEFAULT_VISIBLE,
} from '@/lib/roomZones';

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

// Marker aesthetics: professional "clean number marker" — white/paper fill,
// ink stroke + ink number, constant screen size at every zoom (map-pin style).
const MARKER_R = 13;
const MARKER_INK = '#1f2937';

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
  // Founder decision 2026-07-11: polygon fills are OFF by default — every
  // placeable room renders as a numbered marker until this is toggled on.
  zoneFillsVisible = ROOM_POLYGON_FILLS_DEFAULT_VISIBLE,
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

  // De-overlapped marker anchors: rooms with duplicated polygons share a
  // centroid, which would stack their circled numbers unreadably — fan those
  // clusters out (nr → {cx, cy}); solo markers keep their true anchor.
  const markerAt = useMemo(() => spreadOverlappingMarkers(
    visibleZones.map((z) => ({
      nr: z.nr,
      cx: z.marker.cx,
      cy: z.marker.cy,
      // Own polygon (screen px) lets the spreader keep fanned numbers INSIDE
      // their room instead of drifting into empty plan space.
      points: z.geometry?.type === 'polygon' ? z.geometry.points : null,
    })),
    MARKER_R * 2 + 4,
  ), [visibleZones]);

  if (!width || !height) return null;
  if (zones.length === 0 && missingCount === 0) return null;

  const isFocusedZone = (z) => focusedRoomNr != null && String(z.nr) === String(focusedRoomNr);
  // Hover = internal (cursor on the zone) OR external (cursor on the panel row) —
  // the panel→canvas half of the cheap bidirectional hover sync.
  const isHoveredZone = (z) =>
    (hoverNr != null && String(z.nr) === hoverNr)
    || (hoveredRoomNrExternal != null && String(z.nr) === String(hoveredRoomNrExternal));

  // ── SIMPLE MODE (default): clean drawing; focused/hovered room → red ring
  // around its printed number. Entirely pointer-transparent, so it can never
  // swallow measure or fill clicks.
  if (!zoneFillsVisible) {
    // visibleZones, not zones: a room hidden with the panel's eye must not draw
    // its focus/hover ring either (audit P2).
    const active = visibleZones.filter((z) => isFocusedZone(z) || isHoveredZone(z));
    if (active.length === 0 && missingCount === 0) return null;
    // Ring sized to enclose the printed label plate; scales with the render.
    const ringR = Math.min(44, Math.max(16, width * 0.02));
    const RED = '#dc2626';
    return (
      <svg
        width={width}
        height={height}
        className="absolute left-0 top-0 z-[16]"
        style={{ pointerEvents: 'none' }}
      >
        <style>{`
          @keyframes rz-ring-pulse {
            0% { transform: scale(1); opacity: 0.65; }
            100% { transform: scale(1.9); opacity: 0; }
          }
          .rz-ring-pulse {
            animation: rz-ring-pulse 1.6s ease-out infinite;
            transform-box: fill-box;
            transform-origin: center;
          }
        `}</style>
        {active.map((z) => {
          const isFocused = isFocusedZone(z);
          const a = z.labelAnchor || z.marker;
          const w = chipWidthFor(z.label);
          const half = w / 2;
          return (
            <g key={z.nr} transform={`translate(${a.cx}, ${a.cy})`}>
              {isFocused && (
                <circle className="rz-ring-pulse" r={ringR} fill="none"
                  stroke={RED} strokeWidth={2} />
              )}
              <circle r={ringR} fill="none" stroke={RED}
                strokeWidth={isFocused ? 2.5 : 1.75}
                opacity={isFocused ? 1 : 0.65} />
              {isFocused && (
                <g transform={`translate(0, ${-ringR - 21})`}>
                  <rect x={-half} y={-17} width={w} height={34} rx={4}
                    fill="white" stroke={RED} strokeWidth={1} opacity={0.96} />
                  <circle cx={-half + 10} cy={-6} r={4} fill={z.confidenceColor}>
                    <title>{`Ploto pasitikėjimas: ${z.confidence}`}</title>
                  </circle>
                  <text x={-half + 18} y={-2} fontSize={11} fontWeight="700" fill="#1f2937">
                    {chipLabelFor(z.label)}
                  </text>
                  <text x={-half + 18} y={11} fontSize={10} fill="#4b5563">
                    {z.areaLabel}
                  </text>
                </g>
              )}
            </g>
          );
        })}
        {/* Same honest "we could not place these" chip as fills mode — the
            simple branch used to return before it, so the default view hid the
            disclosure entirely (audit P2). */}
        {missingCount > 0 && <MissingRoomsChip count={missingCount} />}
      </svg>
    );
  }
  // ── FILLS MODE (Layers toggle): traced rooms as filled zones; tier-2
  // (label-anchored, no traced outline) rooms as numbered markers.
  const rendersAsMarker = (z) => z.geometry.type === 'marker';

  return (
    <svg
      width={width}
      height={height}
      className="absolute left-0 top-0 z-[16]"
      style={{ pointerEvents: 'none' }}
    >
      {/* Focus pulse for markers ("Rodyti brėžinyje" flash). r is a CSS
          geometry property — animatable in all evergreen browsers. */}
      <style>{`
        @keyframes rz-marker-pulse {
          0% { r: ${MARKER_R}px; opacity: 0.75; }
          100% { r: ${MARKER_R * 2.2}px; opacity: 0; }
        }
        .rz-marker-pulse { animation: rz-marker-pulse 1.5s ease-out infinite; }
      `}</style>
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
            onClick={(e) => { e.stopPropagation(); onRoomClick?.(z); }}
            onMouseEnter={() => setHoverNr(String(z.nr))}
            onMouseLeave={() => setHoverNr((cur) => (cur === String(z.nr) ? null : cur))}
          >
            {rendersAsMarker(z) ? (
              <g transform={`translate(${(markerAt.get(String(z.nr)) || z.marker).cx}, ${(markerAt.get(String(z.nr)) || z.marker).cy})`}>
                {isFocused && (
                  <circle className="rz-marker-pulse" r={MARKER_R} fill="none"
                    stroke={MARKER_INK} strokeWidth={2} style={{ pointerEvents: 'none' }} />
                )}
                <circle r={MARKER_R} fill="#ffffff" fillOpacity={0.95}
                  stroke={MARKER_INK}
                  strokeWidth={isFocused ? 2.5 : isHovered ? 2 : 1.25}
                  strokeDasharray={z.approximate ? '4 3' : undefined} />
                <text x={0} y={0} textAnchor="middle" dominantBaseline="central"
                  fontSize={11} fontWeight="700" fill={MARKER_INK}
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
          shape so a chip is never buried under a neighbor zone's fill. Markers
          get the chip ABOVE the circle so it never covers the number. */}
      {visibleZones.map((z) => {
        const isFocused = isFocusedZone(z);
        const isHovered = isHoveredZone(z);
        if (!isFocused && !isHovered) return null;
        const asMarker = rendersAsMarker(z);
        const anchor = asMarker ? (markerAt.get(String(z.nr)) || z.marker) : null;
        const { cx, cy } = asMarker
          ? { cx: anchor.cx, cy: anchor.cy - MARKER_R - 21 }
          : centroidOf(z.geometry);
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
              fill="white" stroke={asMarker ? MARKER_INK : z.color} strokeWidth={1} opacity={0.96}
            />
            <circle cx={-half + 10} cy={-6} r={4} fill={z.confidenceColor}>
              <title>{`Ploto pasitikėjimas: ${z.confidence}`}</title>
            </circle>
            <text x={-half + 18} y={-2} fontSize={11} fontWeight="700" fill="#1f2937">
              {chipLabelFor(z.label)}
            </text>
            <text x={-half + 18} y={11} fontSize={10} fill={asMarker ? '#4b5563' : z.color}>
              {z.areaLabel}{z.approximate ? ' · apytikslė vieta' : ''}
            </text>
          </g>
        );
      })}

      {/* Honest "we could not place these" chip (spec §9) — unaffected by
          per-room visibility. */}
      {missingCount > 0 && <MissingRoomsChip count={missingCount} />}
    </svg>
  );
}

// Honest disclosure chip, identical in both presentation modes. Its width follows the sentence
// (~6,2 px a character at 11 px) — the old fixed 250 px only fitted the old, shorter text.
function MissingRoomsChip({ count }) {
  const text = missingRoomsText(count);
  return (
    <g transform="translate(12, 12)" style={{ pointerEvents: 'none' }} data-testid="missing-rooms-chip">
      <rect x={0} y={0} width={Math.ceil(20 + text.length * 6.2)} height={24} rx={5}
        fill="#fef3c7" stroke="#fde68a" strokeWidth={1} />
      <text x={10} y={16} fontSize={11} fill="#b45309">
        {text}
      </text>
    </g>
  );
}

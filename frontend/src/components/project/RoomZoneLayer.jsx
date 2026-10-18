/**
 * RoomZoneLayer — the AI Takeoff Viewer's first visible layer (Phase 1).
 *
 * FOUNDER DECISION (2026-07-14): the DEFAULT is a CLEAN drawing — nothing is
 * drawn at rest. Selecting a room in the panel draws ONE ring around that
 * room's own printed number (labelAnchor = the verified plan-label position),
 * checked-drawing style. One ring at a time → no de-overlap fanning → the
 * ring always lands exactly on the printed number. This replaced the
 * always-on numbered markers (2026-07-11), whose overlap-fanning pushed
 * circles onto walls and read as "numbers marked wrong".
 * The filled polygon zones stay implemented and render when `zoneFillsVisible`
 * is true (viewer toolbar Layers toggle) — the QA/verification view.
 *
 * Declutter contract (2026-07-02): at rest a shape is quiet — NO label chip.
 * The chip (name, then area · room type · how the outline was found) appears on
 * hover, and stays pinned while the room is focused; a focused room pulses twice
 * (the "Rodyti brėžinyje" flash), then holds still.
 *
 * v3 overlay vocabulary (2026-10-18, founder decision 2; lib/overlayTokens):
 * the selection is a heavy NEUTRAL ring/outline plus the label — never red (red
 * means an error); every zone shares ONE neutral tint and the room type is a word
 * in the label; an outline read off the walls or confirmed by him is SOLID, an
 * estimated one (flood fill, a box) DASHED. Every zone carries a hover sentence.
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
  buildPageRoomZones, countRoomsMissingGeometry, spreadOverlappingMarkers,
  ROOM_POLYGON_FILLS_DEFAULT_VISIBLE,
} from '@/lib/roomZones';
import { ltCount } from '@/lib/ltPlural';
import {
  FILL_ALPHA, FILL_ALPHA_HOVER, LABEL_FONT_PX, LABEL_STYLE, OUTLINE_SENTENCE, SELECTED_STROKE_PX, STROKE_PX,
  labelWidth, lineStyle, ov, paint,
} from '@/lib/overlayTokens';
import OverlayLabel from '@/components/viewer/OverlayLabel';

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

// Chip text: line 1 the name (ellipsized past CHIP_MAX_CHARS), line 2 what the drawing says about it.
const CHIP_MAX_CHARS = 30;
function chipLabelFor(label) {
  return label.length > CHIP_MAX_CHARS ? `${label.slice(0, CHIP_MAX_CHARS - 1)}…` : label;
}
function chipSubFor(z) {
  return [z.areaLabel, z.typeWord, z.confidenceText].filter(Boolean).join(' · ');
}
// The outline's kind in a few words, for the chip of an outline that is NOT read off the walls.
function outlineNote(z) {
  if (z.outline === 'estimated') return 'kontūras apytikslis';
  if (z.outline === 'marker') return 'tik numeris, be kontūro';
  return null;
}
// The whole sentence — the hover title of an interactive zone.
function zoneSentence(z) {
  return [`${z.nr} ${z.label}`, chipSubFor(z), OUTLINE_SENTENCE[z.outline]].filter(Boolean).join(' · ');
}

// Marker aesthetics: professional "clean number marker" — white/paper fill,
// ink stroke + ink number, constant screen size at every zoom (map-pin style).
const MARKER_R = 13;
const INK = ov('selected');
// A focused room pulses twice, then holds still (the endless 1.6 s pulse read as an alarm).
const PULSE_TIMES = 2;

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
    return (
      <svg
        width={width}
        height={height}
        className="absolute left-0 top-0 z-[16]"
        style={{ pointerEvents: 'none' }}
        data-room-zone-layer="simple"
      >
        <style>{`
          @keyframes rz-ring-pulse {
            0% { transform: scale(1); opacity: 0.6; }
            100% { transform: scale(1.8); opacity: 0; }
          }
          .rz-ring-pulse {
            animation: rz-ring-pulse 1.4s ease-out ${PULSE_TIMES} forwards;
            transform-box: fill-box;
            transform-origin: center;
          }
          @media (prefers-reduced-motion: reduce) { .rz-ring-pulse { animation: none; opacity: 0; } }
        `}</style>
        {active.map((z) => {
          const isFocused = isFocusedZone(z);
          const a = z.labelAnchor || z.marker;
          return (
            <g key={z.nr} transform={`translate(${a.cx}, ${a.cy})`} data-room-ring={z.nr}>
              {isFocused && (
                <circle className="rz-ring-pulse" r={ringR} fill="none"
                  style={paint({ stroke: INK })} strokeWidth={STROKE_PX} />
              )}
              {/* the selection: a heavy neutral ring on a white casing, so it reads on any sheet */}
              {isFocused && (
                <circle r={ringR} fill="none" style={paint({ stroke: ov('label-bg') })}
                  strokeWidth={SELECTED_STROKE_PX + 3} opacity={0.9} />
              )}
              <circle r={ringR} fill="none" style={paint({ stroke: INK })}
                strokeWidth={isFocused ? SELECTED_STROKE_PX : 1.5}
                opacity={isFocused ? 1 : 0.6} />
              {isFocused && (
                <OverlayLabel x={0} y={-ringR - 24} text={chipLabelFor(z.label)} sub={chipSubFor(z)} border={INK} />
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
      data-room-zone-layer="fills"
    >
      {/* Focus pulse for markers ("Rodyti brėžinyje" flash), twice. r is a CSS
          geometry property — animatable in all evergreen browsers. */}
      <style>{`
        @keyframes rz-marker-pulse {
          0% { r: ${MARKER_R}px; opacity: 0.7; }
          100% { r: ${MARKER_R * 2.2}px; opacity: 0; }
        }
        .rz-marker-pulse { animation: rz-marker-pulse 1.4s ease-out ${PULSE_TIMES} forwards; }
        @media (prefers-reduced-motion: reduce) { .rz-marker-pulse { animation: none; opacity: 0; } }
      `}</style>
      {/* Pass 1: shapes only — one neutral tint, quiet at rest, a little denser on hover/focus;
          the line says how the outline was found (solid read/confirmed, dashed estimated). */}
      {visibleZones.map((z) => {
        const isFocused = isFocusedZone(z);
        const isHovered = isHoveredZone(z);
        const line = lineStyle(z.outline === 'marker' ? 'read' : z.outline);
        const stroke = isFocused ? INK : line.stroke;
        const strokeW = isFocused ? SELECTED_STROKE_PX : STROKE_PX;
        const fillOpacity = isFocused || isHovered ? FILL_ALPHA_HOVER : FILL_ALPHA;
        const dash = line.dash || undefined;

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
            data-room-zone={z.nr}
            data-outline={z.outline}
          >
            <title>{zoneSentence(z)}</title>
            {rendersAsMarker(z) ? (
              <g transform={`translate(${(markerAt.get(String(z.nr)) || z.marker).cx}, ${(markerAt.get(String(z.nr)) || z.marker).cy})`}>
                {isFocused && (
                  <circle className="rz-marker-pulse" r={MARKER_R} fill="none"
                    style={{ ...paint({ stroke: INK }), pointerEvents: 'none' }} strokeWidth={STROKE_PX} />
                )}
                <circle r={MARKER_R} fillOpacity={0.95}
                  style={paint({ fill: ov('label-bg'), stroke: INK })}
                  strokeWidth={isFocused ? SELECTED_STROKE_PX : isHovered ? STROKE_PX : 1.5} />
                <text x={0} y={0} textAnchor="middle" dominantBaseline="central"
                  fontSize={LABEL_FONT_PX} fontWeight="600"
                  style={{ ...LABEL_STYLE, ...paint({ fill: INK }), pointerEvents: 'none' }}>
                  {z.nr}
                </text>
              </g>
            ) : z.geometry.type === 'polygon' ? (
              <polygon
                points={z.geometry.points.map((p) => `${p[0]},${p[1]}`).join(' ')}
                style={paint({ fill: ov('zone-fill'), stroke })}
                fillOpacity={fillOpacity}
                strokeWidth={strokeW}
                strokeDasharray={dash}
                strokeLinejoin="round"
              />
            ) : (
              <rect
                x={z.geometry.left}
                y={z.geometry.top}
                width={z.geometry.width}
                height={z.geometry.height}
                rx={2}
                style={paint({ fill: ov('zone-fill'), stroke })}
                fillOpacity={fillOpacity}
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
          ? { cx: anchor.cx, cy: anchor.cy - MARKER_R - 24 }
          : centroidOf(z.geometry);
        return (
          <OverlayLabel
            key={`chip-${z.nr}`}
            x={cx} y={cy}
            text={chipLabelFor(z.label)}
            sub={[chipSubFor(z), outlineNote(z)].filter(Boolean).join(' · ')}
            border={isFocused ? INK : undefined}
          />
        );
      })}

      {/* Honest "we could not place these" chip (spec §9) — unaffected by
          per-room visibility. */}
      {missingCount > 0 && <MissingRoomsChip count={missingCount} />}
    </svg>
  );
}

// Honest disclosure chip, identical in both presentation modes.
function MissingRoomsChip({ count }) {
  const text = `${ltCount(count, 'patalpa', 'patalpos', 'patalpų')} be vietos plane — žr. „Peržiūra“`;
  return (
    <g transform="translate(12, 12)" style={{ pointerEvents: 'none' }} data-missing-rooms-chip>
      <rect x={0} y={0} width={labelWidth(text)} height={24} rx={2}
        style={paint({ fill: ov('label-bg'), stroke: ov('estimated') })} strokeWidth={1} />
      <text x={7} y={16} fontSize={LABEL_FONT_PX} style={{ ...LABEL_STYLE, ...paint({ fill: ov('label-fg') }) }}>
        {text}
      </text>
    </g>
  );
}

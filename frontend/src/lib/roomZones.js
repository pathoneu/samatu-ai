/**
 * roomZones.js — pure helpers that turn extracted patalpos[] rooms into
 * render-ready zone descriptors for the AI Takeoff Viewer's RoomZoneLayer.
 *
 * The viewer is a FACE over the existing engine (design spec 2026-07-01 §3):
 * these functions add NO new quantity math. They only
 *   1. map a room's paskirtis → a stable fill color (identity),
 *   2. bridge polygon_pct / bbox_pct → screen pixels (reusing
 *      planOverlayGeometry — the coordinate bridge that was never wired into a
 *      visible overlay),
 *   3. attach the room's AREA confidence (reusing computeAreaConfidence — the
 *      audited provenance→🟢🟡🔴 logic; spec §5 "do not invent a new one"),
 *   4. flag geometry that is only APPROXIMATE (synthesized from bbox), so the
 *      viewer never draws a fabricated-precise polygon (spec §9).
 */

import { computeAreaConfidence } from './areaConfidence.js';
import { getPolygonPctPoints, getBboxPctRect } from './planOverlayGeometry.js';

// paskirtis → hex. Moved verbatim from AiRoomOverlay (Kreo per-category hues)
// so a glance reveals functional zones without reading labels.
export const ROOM_ZONE_COLORS = {
  gyvenamoji: '#10b981', svetaine: '#10b981',
  miegamoji: '#3b82f6', miegamasis: '#3b82f6', vaikui: '#3b82f6',
  virtuve: '#f59e0b', valgomasis: '#f59e0b',
  vonia: '#06b6d4', vonios: '#06b6d4', wc: '#06b6d4', san: '#06b6d4', sanitarine: '#06b6d4',
  koridorius: '#a78bfa', holas: '#a78bfa', prieskambaris: '#a78bfa',
  drabuzine: '#ec4899', 'rūbinė': '#ec4899',
  sandeliukas: '#94a3b8', saugykla: '#94a3b8', katiline: '#94a3b8', ukio: '#94a3b8',
  garazas: '#64748b', 'tambūras': '#64748b', tamburas: '#64748b',
  balkonas: '#22c55e', terasa: '#22c55e',
};

const DEFAULT_ZONE_COLOR = '#10b981';

export function roomZoneColor(paskirtis) {
  return ROOM_ZONE_COLORS[paskirtis] || DEFAULT_ZONE_COLOR;
}

// confidence → hex for the on-canvas dot + stroke. Matches the app's 🟢🟡🔴
// language and the count-tool prototype's green/amber/red.
export const CONFIDENCE_HEX = {
  high: '#16a34a',
  medium: '#d97706',
  low: '#dc2626',
  unknown: '#9ca3af',
};

export function confidenceHex(confidence) {
  return CONFIDENCE_HEX[confidence] || CONFIDENCE_HEX.unknown;
}

// polygon_source values that mean "we approximated the shape" → dashed border.
const APPROXIMATE_POLYGON_SOURCES = new Set([
  'synthesized_from_bbox', 'bbox_fallback', 'manual_needed',
]);

/**
 * buildRoomZone — one room → a render-ready descriptor, or null if the room
 * has no geometry we can honestly place on the plan.
 *
 * geometry is one of:
 *   { type: 'polygon', points: [[x,y], …] }   // from polygon_pct
 *   { type: 'rect', left, top, width, height } // from bbox_pct fallback
 * `approximate` is true when the shape is synthesized (dashed border in the UI).
 */
export function buildRoomZone(room, { renderedWidth, renderedHeight } = {}) {
  if (!room || !renderedWidth || !renderedHeight) return null;

  let geometry = null;
  let approximate = false;

  const polyPoints = getPolygonPctPoints(room.polygon_pct, { renderedWidth, renderedHeight });
  if (polyPoints) {
    geometry = { type: 'polygon', points: polyPoints };
    approximate = APPROXIMATE_POLYGON_SOURCES.has(room.polygon_source);
  } else {
    const rect = getBboxPctRect(room.bbox_pct, { width: renderedWidth, height: renderedHeight });
    if (rect) {
      geometry = { type: 'rect', ...rect };
      approximate = true; // a bbox rectangle is never an exact room outline
    }
  }

  if (!geometry) return null;

  const { confidence } = computeAreaConfidence(room);
  const area = Number.isFinite(room.plotas_m2) ? room.plotas_m2 : null;

  return {
    nr: room.nr,
    label: room.pavadinimas || `#${room.nr}`,
    areaLabel: area != null
      ? `${area.toLocaleString('lt-LT', { maximumFractionDigits: 1 })} m²`
      : '',
    paskirtis: room.paskirtis || null,
    color: roomZoneColor(room.paskirtis),
    confidence,
    confidenceColor: confidenceHex(confidence),
    approximate,
    geometry,
  };
}

function roomPage(room) {
  return room?.page_nr ?? room?.puslapio_nr ?? null;
}

/**
 * buildPageRoomZones — all rooms on `page` that CAN be drawn, as descriptors.
 * Rooms without geometry are dropped here (they still surface in the review
 * worklist and in countRoomsMissingGeometry).
 */
export function buildPageRoomZones(rooms, { renderedWidth, renderedHeight, page }) {
  if (!Array.isArray(rooms)) return [];
  return rooms
    .filter((r) => roomPage(r) === page)
    .map((r) => buildRoomZone(r, { renderedWidth, renderedHeight }))
    .filter(Boolean);
}

/**
 * countRoomsMissingGeometry — rooms on `page` we could NOT place on the plan.
 * Surfaced as an honest "N patalpų be vietos plane" chip (spec §9), never hidden.
 */
export function countRoomsMissingGeometry(rooms, { renderedWidth, renderedHeight, page }) {
  if (!Array.isArray(rooms)) return 0;
  return rooms
    .filter((r) => roomPage(r) === page)
    .filter((r) => !buildRoomZone(r, { renderedWidth, renderedHeight }))
    .length;
}

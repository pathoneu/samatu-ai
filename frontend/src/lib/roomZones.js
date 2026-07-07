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
import { getPolygonPctPoints } from './planOverlayGeometry.js';

// paskirtis → hex. Moved verbatim from AiRoomOverlay (industry takeoff tools per-category hues)
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

// A polygon whose source is in this set is NOT a real traced outline — the
// polygon it may carry is a fabricated coarse rectangle, so the room becomes a
// Tier-2 marker (circled number), never a solid zone.
const NON_TRACED_SOURCES = new Set(['synthesized_from_bbox', 'bbox_fallback', 'manual_needed']);

function markerCenter(room, { renderedWidth, renderedHeight }) {
  // ONLY a reliable printed-number anchor (marker_pct = the backend's label seed,
  // or label_pct) may place a marker. Do NOT fall back to the bbox centroid — on
  // furnished/rotated plans Vision bboxes are garbage and a bbox-centroid marker
  // is the "marked random places" failure. No anchor → null → the room falls to
  // the honest "N patalpų be vietos" chip.
  const mp = room.marker_pct || room.label_pct;
  if (Array.isArray(mp) && mp.length === 2) {
    return { cx: mp[0] * renderedWidth, cy: mp[1] * renderedHeight };
  }
  return null;
}

/**
 * buildRoomZone — one room → a render-ready descriptor, or null if the room
 * has no geometry we can honestly place on the plan.
 *
 * Three honest tiers:
 *   Tier 1 (traced)  { type: 'polygon', points: [[x,y], …] }  — real flood-fill
 *     outline (polygon_source NOT in NON_TRACED_SOURCES). approximate = false.
 *   Tier 2 (located) { type: 'marker', cx, cy }               — no traced shape
 *     but a label-anchored marker_pct/label_pct exists. approximate = true.
 *   Tier 3 (no place) → null                                  — no polygon and
 *     no anchor; surfaced by countRoomsMissingGeometry as the "be vietos" chip.
 * A coarse bbox rectangle is NEVER drawn.
 */
export function buildRoomZone(room, { renderedWidth, renderedHeight } = {}) {
  if (!room || !renderedWidth || !renderedHeight) return null;

  const traced = room.polygon_pct && !NON_TRACED_SOURCES.has(room.polygon_source);
  let geometry = null;
  let approximate = false;

  if (traced) {
    const polyPoints = getPolygonPctPoints(room.polygon_pct, { renderedWidth, renderedHeight });
    if (polyPoints) {
      geometry = { type: 'polygon', points: polyPoints };
      approximate = false;
    }
  }
  if (!geometry) {
    // Tier 2: circled-number marker at the printed label (label-anchored only).
    const c = markerCenter(room, { renderedWidth, renderedHeight });
    if (c) {
      geometry = { type: 'marker', cx: c.cx, cy: c.cy };
      approximate = true;
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

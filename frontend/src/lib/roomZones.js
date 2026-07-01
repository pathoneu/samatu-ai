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

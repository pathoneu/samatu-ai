/**
 * pageScales — the ONE per-sheet scale every surface uses (Togal-v2 W6, 2026-10-16).
 *
 * The viewer measured with `{auto, lane, durable}` merged, while the Matavimai list and its export merged only
 * `{auto, durable}` — so a sheet whose scale the lane read (objektas_h: every sheet 1:115) showed metres in the
 * viewer and „nekalibruota" in the list. Merge order, weakest first:
 *   auto    — derived from the traced rooms' areas (approximate, durableScale.autoPageScalesFromRooms);
 *   lane    — the drawing's own dimension strings (durableScale.laneScalesOf);
 *   durable — what the user set or confirmed (project.pageScalesDurable / the viewer's live state).
 * A durable entry that is not calibrated never hides a lane scale. Pure.
 */
import { autoPageScalesFromRooms, laneScalesOf } from './durableScale.js';

/** `{page: PageScale}` — auto, then lane, then the user's own (only calibrated entries). */
export function mergePageScales(auto = {}, lane = {}, durable = {}) {
  const out = { ...(auto || {}), ...(lane || {}) };
  for (const [page, s] of Object.entries(durable || {})) {
    if (s?.calibrated) out[page] = s;
  }
  return out;
}

const roomsOf = (project) => project?.v8_rooms || project?.patalpos || [];

/**
 * The project's effective scales. `durable` defaults to the stored map; the viewer passes its live state
 * (it owns the scales between saves).
 */
export function effectivePageScales(project, durable = project?.pageScalesDurable, lane = laneScalesOf(project)) {
  return mergePageScales(autoPageScalesFromRooms(roomsOf(project)), lane, durable || {});
}

/**
 * The map a viewer with no scale state of its own shows — Patikra's room sheet (2026-10-18 audit, side finding
 * A). It is handed in as that viewer's lane input: with no rooms and no durable map of its own, the viewer then
 * measures with exactly the main viewer's map, so a confirmed sheet reads „Patvirtintas" in both (before, the
 * room sheet got the lane alone and called the same sheet „Spėjamas").
 */
export function checkViewerScales(project) {
  return effectivePageScales(project);
}

/** One page's entry of a merged map, number or string key; null when none. */
export function pageScaleIn(scales, page) {
  if (!scales || page == null) return null;
  return scales[page] ?? scales[String(page)] ?? null;
}

/**
 * roomSheetApi.js — every network call the room check sheet makes.
 *
 * The sheet writes through the SAME two paths the rest of the app already
 * uses; it invents no third one:
 *
 *   • aukštis / sienų apdaila  → POST /api/recompute-quantities (the
 *     Prielaidos path). Both fields are per-room dicts in `_ASSUMPTION_FIELDS`,
 *     so the edit is `{field, new_value: {...all, [nr]: value}}`, exactly the
 *     shape AssumptionsPanel sends.
 *   • plotas / perimetras / angos / paskirtis → POST /recompute-interior (the
 *     room-edit path), because those live ON the room, not in the assumptions.
 *     Replicates `InteriorProject.handleRoomsChange` — including the merge that
 *     is the only thing standing between a room edit and 15 deleted priced rows.
 *
 * Both carry `buildRecomputeContext`, so neither can quietly ship a shorter
 * sąmata (the 2026-06-17 door/fixture loss, the 2026-09-02 un-anchored Lubų).
 *
 * STUBBED, deliberately: `overrideRoomQuantity` writes a WHOLE-ROW manual
 * override through the existing `quantityOverride` mechanics, and only when
 * this room is the row's sole contributor (`canOverrideWholeRow`). A per-room
 * share override has no backend write path yet; the UI says so rather than
 * pretending, and this module never fabricates one.
 */

import { API_BASE } from './apiBase.js';
import { recompute } from './recomputeApi.js';
import { buildRecomputeContext } from './recomputeContext.js';
import { updatePositionQuantity } from './quantityOverride.js';
import {
  canOverrideWholeRow, findRowForQuantity, legacyKeyIsUnique, legacyRowKey,
} from './roomSheet.js';

function roomsOf(project) {
  return project?.v8_rooms?.length ? project.v8_rooms : (project?.patalpos || []);
}

/** GET the room's facts + the quantities it feeds. */
export async function fetchRoomFacts(projectId, roomNr, { signal } = {}) {
  const url = `${API_BASE}/api/projects/${encodeURIComponent(projectId)}`
    + `/rooms/${encodeURIComponent(roomNr)}/facts`;
  const res = await fetch(url, { credentials: 'include', signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

/**
 * The crop URL the backend handed us, made absolute. `crop_url` arrives as a
 * path so the same payload works behind the dev proxy and on api.pathon.eu —
 * we only ever prefix, never rebuild it (the rect is the server's decision).
 */
export function evidenceUrl(cropUrl) {
  if (!cropUrl) return null;
  if (/^https?:\/\//i.test(cropUrl)) return cropUrl;
  return `${API_BASE}${cropUrl}`;
}

/**
 * Assumption-class edit (aukštis, sienų apdaila): one per-room dict field.
 * Returns the raw recompute result — the caller merges it, because the merge
 * needs the project it is holding.
 */
export function saveAssumptionEdit(project, field, nextDict) {
  return recompute({
    rooms: roomsOf(project),
    pozicijos: project?.pozicijos || [],
    // The user's PRICES live here, not in pozicijos — without them the backend
    // merge cannot tell a priced row from a throwaway one.
    darbu_sarasas: project?.darbu_sarasas || [],
    edits: [{ field, new_value: nextDict }],
    current_assumptions: project?._overrides || {},
    context: buildRecomputeContext(project),
  });
}

/**
 * Room-class edit (plotas, perimetras, angos, paskirtis): the whole rooms array
 * goes back with one room changed. Mirrors handleRoomsChange's body exactly.
 */
export async function saveRoomEdit(project, nextRooms) {
  const res = await fetch(`${API_BASE}/recompute-interior`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      patalpos: nextRooms,
      rules_override: project?._overrides || {},
      per_room_overrides: project?._per_room_overrides || {},
      archetipas: project?.archetipas,
      bendras_plotas_m2: nextRooms.reduce((s, r) => s + (Number(r?.plotas_m2) || 0), 0),
      _ceiling_anchor: project?._ceiling_anchor,
      context: buildRecomputeContext(project),
    }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  const result = await res.json();
  if (result.status !== 'ok') throw new Error(result._error || `HTTP ${res.status}`);
  return result;
}

/** A no-op recompute — the button behind „Kiekiai dar neparuošti". */
export function recomputeUntouched(project) {
  return recompute({
    rooms: roomsOf(project),
    pozicijos: project?.pozicijos || [],
    darbu_sarasas: project?.darbu_sarasas || [],
    edits: [],
    current_assumptions: project?._overrides || {},
    context: buildRecomputeContext(project),
  });
}

/** One room in the array replaced by `patch`, everything else untouched. */
export function patchRoom(project, roomNr, patch) {
  return roomsOf(project).map((r) => (
    String(r?.nr) === String(roomNr) ? { ...r, ...patch } : r
  ));
}

/**
 * A per-room quantity correction, as far as it can honestly go today.
 *
 * When this room is the row's ONLY contributor the room's share IS the row, so
 * we write a normal whole-row manual override — the same `manual_override`
 * flag `quantityOverride.js` sets everywhere else, which a recompute will not
 * overwrite. When the row has other rooms in it, there is nothing truthful to
 * write: returning `{ ok: false }` is what makes the UI say so instead.
 */
export function overrideRoomQuantity(project, quantity, roomNr, value) {
  const rows = project?.darbu_sarasas || [];
  if (!canOverrideWholeRow(quantity, rows, roomNr)) {
    return { ok: false, reason: 'shared_row', darbu_sarasas: rows };
  }
  const row = findRowForQuantity(rows, quantity);
  // `updatePositionQuantity` keys on the legacy id, and rewrites EVERY row that
  // matches it. If the key is not unique, one click would move two lines.
  if (!legacyKeyIsUnique(rows, row)) {
    return { ok: false, reason: 'ambiguous_row', darbu_sarasas: rows };
  }
  return {
    ok: true,
    reason: 'whole_row',
    darbu_sarasas: updatePositionQuantity(rows, legacyRowKey(row), value),
  };
}

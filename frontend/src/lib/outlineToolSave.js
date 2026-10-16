/**
 * outlineToolSave — what the viewer's outline tools („Padalyti", „Sujungti", „Atimti") send to the
 * server and how the answer lands on the project (2026-10-16).
 *
 * The server saves nothing (api/room_outline.py): it measures each ring at the sheet's scale, reads
 * the walls again and answers with GEOMETRY keys. This module turns one tool operation into those
 * requests and the answers into ONE project patch, so the sheet recomputes once:
 *
 *   {kind: 'set',   nr, page, polygon, holes}                       — „Atimti", or a split with the
 *                                                                     other half left out
 *   {kind: 'split', nr, page, polygon, holes, other: {nr, polygon, holes}}
 *   {kind: 'merge', keptNr, goneNr, page, polygon, holes}
 *
 * A merge bills BOTH table rows in the kept room (`plotas_m2 = a + b`, its openings carried over) and
 * marks the absorbed room structurally (`_sujungta_i`): the answer's `sujungimas` names exactly those
 * room keys, and they land here beside the geometry ones. Nothing goes through the scope — a merged room
 * is not a room he chose not to count.
 */
import { roomsWithOutline, roomsWithSplit } from './roomOutline.js';

/** The room keys a merge writes besides the geometry (mirror of backend MERGE_ROOM_KEYS). */
export const MERGE_ROOM_KEYS = [
  'plotas_m2', 'plotas_saltinis', '_plotas_pries_sujungima', '_sujungimas', 'elementai',
  '_sujungta_i', '_elementai_pries_sujungima', '_perimetras_pries_sujungima',
];

function withMergeKeys(rooms, sujungimas) {
  if (!sujungimas || typeof sujungimas !== 'object') return rooms;
  return rooms.map((r) => {
    const keys = sujungimas[String(r?.nr ?? '')];
    if (!keys || typeof keys !== 'object') return r;
    const next = { ...r };
    for (const k of MERGE_ROOM_KEYS) {
      if (!(k in keys)) continue;
      if (keys[k] == null) delete next[k];
      else next[k] = keys[k];
    }
    return next;
  });
}

function failure(answer) {
  return new Error(typeof answer?.detail === 'string' ? answer.detail : 'Kontūras nepriimtas');
}

/** v8_rooms (older blobs carry both lists) follow the rooms that changed. */
function withV8(project, rooms) {
  const patch = { patalpos: rooms };
  if (Array.isArray(project?.v8_rooms)) {
    const byNr = new Map(rooms.map((r) => [String(r?.nr), r]));
    patch.v8_rooms = project.v8_rooms.map((r) => byNr.get(String(r?.nr)) || r);
  }
  return patch;
}

/**
 * Run `op` against the server (`api` = {outlineSet, outlineMerge}, the roomOutlineApi calls bound to the
 * project) and build the patch from `getFresh()` — the project as stored AFTER the answers came back,
 * so an edit that landed meanwhile is not reverted. → the patch ({patalpos, v8_rooms?, _apimtis?}).
 */
export async function saveOutlineTool(op, { api, getFresh }) {
  if (op?.kind === 'set') {
    const answer = await api.outlineSet(op.nr, { page: op.page, polygon_pct: op.polygon, holes: op.holes });
    const fresh = getFresh();
    const rooms = roomsWithOutline(fresh, op.nr, answer);
    if (!rooms) throw failure(answer);
    return withV8(fresh, rooms);
  }
  if (op?.kind === 'split') {
    const mine = await api.outlineSet(op.nr, { page: op.page, polygon_pct: op.polygon, holes: op.holes });
    if (mine?.status !== 'ok') throw failure(mine);
    const theirs = await api.outlineSet(op.other.nr, { page: op.page, polygon_pct: op.other.polygon, holes: op.other.holes });
    if (theirs?.status !== 'ok') throw failure(theirs);
    // Each answer read the walls against the STORED outlines: a neighbour's openings from either answer are
    // fine, but neither may speak for the two rooms that just changed.
    const changed = new Set([String(op.nr), String(op.other.nr)]);
    const kitu = {};
    for (const [nr, v] of Object.entries({ ...(mine.kitu_angos || {}), ...(theirs.kitu_angos || {}) })) {
      if (!changed.has(String(nr))) kitu[nr] = v;
    }
    const fresh = getFresh();
    const rooms = roomsWithSplit(fresh, {
      status: 'ok', rooms: { [String(op.nr)]: mine.room, [String(op.other.nr)]: theirs.room }, kitu_angos: kitu,
    });
    return withV8(fresh, rooms);
  }
  if (op?.kind === 'merge') {
    const answer = await api.outlineMerge(op.goneNr, {
      page: op.page, kept_nr: String(op.keptNr), polygon_pct: op.polygon, holes: op.holes,
    });
    const fresh = getFresh();
    const rooms = roomsWithSplit(fresh, answer);
    if (!rooms) throw failure(answer);
    return withV8(fresh, withMergeKeys(rooms, answer.sujungimas));
  }
  throw new Error(`Nežinomas kontūro veiksmas: ${op?.kind}`);
}

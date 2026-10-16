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
 * A merged-away room must stop billing its own area: it is taken out the way every excluded room is
 * (`_apimtis.patalpos_ne`, enforced server side by extractor/scope.py on every compute path) — kept on
 * the sheet, named in the settings, put back with one switch.
 */
import { roomsWithOutline, roomsWithSplit } from './roomOutline.js';
import { withRoomIncluded } from './scope.js';

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
    let scope = fresh?._apimtis;
    for (const nr of answer.neskaiciuoti || [op.goneNr]) scope = withRoomIncluded(scope, nr, false);
    return { ...withV8(fresh, rooms), _apimtis: scope };
  }
  throw new Error(`Nežinomas kontūro veiksmas: ${op?.kind}`);
}

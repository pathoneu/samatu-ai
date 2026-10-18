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

/** „Kas atimama?" per hole (`holes_walls`), sent only when the operation says — the server's default is walls. */
function wallsOf(op) {
  return Array.isArray(op?.holesWalls) && op.holesWalls.length ? { holes_walls: op.holesWalls } : {};
}

/** The room keys a merge writes besides the geometry (mirror of backend MERGE_ROOM_KEYS). */
export const MERGE_ROOM_KEYS = [
  'plotas_m2', 'plotas_saltinis', '_plotas_pries_sujungima', '_sujungimas', 'elementai',
  '_sujungta_i', '_elementai_pries_sujungima', '_perimetras_pries_sujungima', 'n_partition_walls',
];

export function withMergeKeys(rooms, sujungimas) {
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

/**
 * One `previous` from several answers' (a split saves two rooms with two requests): per room, per key, the
 * FIRST answer's value wins — every answer read the same stored project, so they agree where they overlap.
 */
export function mergePrevious(...previous) {
  const out = {};
  for (const prev of previous) {
    if (!prev || typeof prev !== 'object') continue;
    for (const [nr, keys] of Object.entries(prev)) {
      if (!keys || typeof keys !== 'object') continue;
      out[nr] = { ...keys, ...(out[nr] || {}) };
    }
  }
  return out;
}

function failure(answer) {
  return new Error(typeof answer?.detail === 'string' ? answer.detail : 'Kontūras nepriimtas');
}

/** v8_rooms (older blobs carry both lists) follow the rooms that changed. */
export function withV8(project, rooms) {
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
export async function saveOutlineTool(op, { api, getFresh, onPrevious = null }) {
  // „Atšaukti" (Pathon v3 W1-D): every answer carries `previous`; `onPrevious({action, nr, previous})` hands the
  // host what to PUT back through the same route to undo this operation.
  const undoable = (action, nr, ...answers) => {
    const previous = mergePrevious(...answers.map((a) => a?.previous));
    if (onPrevious && Object.keys(previous).length) onPrevious({ action, nr: String(nr), previous });
  };
  if (op?.kind === 'set') {
    const answer = await api.outlineSet(op.nr, { page: op.page, polygon_pct: op.polygon, holes: op.holes, ...wallsOf(op) });
    const fresh = getFresh();
    const rooms = roomsWithOutline(fresh, op.nr, answer);
    if (!rooms) throw failure(answer);
    undoable('outline-set', op.nr, answer);
    return withV8(fresh, rooms);
  }
  if (op?.kind === 'split') {
    const mine = await api.outlineSet(op.nr, { page: op.page, polygon_pct: op.polygon, holes: op.holes, ...wallsOf(op) });
    if (mine?.status !== 'ok') throw failure(mine);
    const theirs = await api.outlineSet(op.other.nr, { page: op.page, polygon_pct: op.other.polygon, holes: op.other.holes, ...wallsOf(op.other) });
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
    undoable('outline-set', op.nr, mine, theirs);
    return withV8(fresh, rooms);
  }
  if (op?.kind === 'merge') {
    const answer = await api.outlineMerge(op.goneNr, {
      page: op.page, kept_nr: String(op.keptNr), polygon_pct: op.polygon, holes: op.holes, ...wallsOf(op),
    });
    const fresh = getFresh();
    const rooms = roomsWithSplit(fresh, answer);
    if (!rooms) throw failure(answer);
    undoable('outline-merge', op.goneNr, answer);
    return withV8(fresh, withMergeKeys(rooms, answer.sujungimas));
  }
  throw new Error(`Nežinomas kontūro veiksmas: ${op?.kind}`);
}

// `grindu_danga` → [nominative, genitive, accusative] (mirror of backend api/room_outline.py _FLOOR_WORDS)
const FLOOR_WORDS = {
  plyteles: ['plytelės', 'plytelių', 'plyteles'],
  minksta: ['parketas arba laminatas', 'parketo arba laminato', 'parketą arba laminatą'],
  be_dangos: ['betonas be dangos', 'betono be dangos', 'betoną be dangos'],
};
const lt2 = (v) => Number(v).toFixed(2).replace('.', ',');
const pos = (v) => typeof v === 'number' && v > 0;

function floorKind(r) {
  if (r && FLOOR_WORDS[r.grindu_danga]) return r.grindu_danga;
  if (pos(r?.plyteles_grindys_m2)) return 'plyteles';
  return pos(r?.pvc_grindys_m2) ? 'minksta' : null;
}

/**
 * „Sujungti" applies the kept room's finishes to the whole area. When the two rooms' floor coverings or
 * wall tiles differ that moves billed quantities between lines — the dialog says so BEFORE the merge
 * (mirror of backend `merge_finish_warning`, same words). Null when nothing moves.
 */
export function mergeFinishWarning(kept, gone, keptNr, goneNr) {
  const a = pos(kept?.plotas_m2) ? kept.plotas_m2 : 0;
  const b = pos(gone?.plotas_m2) ? gone.plotas_m2 : 0;
  const both = Math.round((a + b) * 100) / 100;
  const fk = floorKind(kept);
  const fg = floorKind(gone);
  const floorDiffers = Boolean(fk && fg && fk !== fg);
  const wallTiles = pos(gone?.plyteles_sienos_m2) ? gone.plyteles_sienos_m2 : 0;
  const lostTiles = wallTiles > 0 && !pos(kept?.plyteles_sienos_m2);
  if (!floorDiffers && !lostTiles) return null;
  let text = 'Patalpų apdaila skiriasi: ' + (floorDiffers
    ? `${goneNr} grindys ${FLOOR_WORDS[fg][0]}, ${keptNr} ${FLOOR_WORDS[fk][0]}`
    : `${goneNr} sienose plytelės, ${keptNr} — ne`);
  text += ` — sujungus visam plotui (${lt2(both)} m²) bus taikoma ${keptNr} apdaila`;
  const tail = [];
  if (floorDiffers && b > 0) tail.push(`${lt2(b)} m² pereis iš ${FLOOR_WORDS[fg][1]} į ${FLOOR_WORDS[fk][2]}`);
  if (lostTiles) tail.push(`${goneNr} sienų plytelių (${lt2(wallTiles)} m²) sąmatoje nebeliks`);
  return text + (tail.length ? '; ' + tail.join('; ') : '') + '.';
}

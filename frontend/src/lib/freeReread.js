/**
 * freeReread — what a FREE re-read of the drawing does to a stored project.
 *
 * The geometry lane (vector outlines, perimeters added from the written strings,
 * floor coverings off the floor plan) runs inside a full, paid extraction; a
 * project read before the lane existed has none of it. `POST
 * /api/projects/{id}/free-reread` runs the lane on the stored PDF and rooms —
 * no Vision call — and answers with its rooms and meta; the server saves
 * nothing. This module decides what of that answer lands on the project.
 *
 * The rules are the re-read's rules (lib/mergeReextract.js): a room he verified
 * keeps its facts, a number he typed or an outline he corrected stays, and what
 * changed is recorded in `_reread_diff` for the banner. Only the rooms and the
 * lane's own record (`_meta.geometrija`) change here — rows, prices,
 * assumptions and scope are not this module's to touch; the caller rebuilds the
 * rows on the merged rooms through the usual /recompute-interior path. Pure.
 */

import { mergeReextractRooms } from './mergeReextract.js';

/** Project-level reads the free re-read returns beside the rooms (api/free_reread.py). */
export const PROJECT_READ_KEYS = Object.freeze(['_duru_ziniarastis', '_vector_symbols']);

const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);

/**
 * `{ project, diff }` — the stored project with the lane's read merged in, or
 * `{ project: null }` when there is nothing to land (the lane failed, or it
 * answered without rooms).
 */
export function mergeFreeReread(base, result, now = new Date().toISOString()) {
  if (!isObj(base) || !isObj(result) || result.lane === 'failed') return { project: null, diff: null };
  const fresh = Array.isArray(result.patalpos) ? result.patalpos.filter(isObj) : [];
  if (!fresh.length) return { project: null, diff: null };
  const stored = Array.isArray(base.v8_rooms) && base.v8_rooms.length ? base.v8_rooms : base.patalpos;
  const { rooms, diff } = mergeReextractRooms(stored, fresh, now);
  const geometrija = isObj(result._meta) ? result._meta.geometrija : undefined;
  const project = {
    ...base,
    patalpos: rooms,
    v8_rooms: rooms,
    _meta: { ...(isObj(base._meta) ? base._meta : {}), ...(geometrija !== undefined ? { geometrija } : {}) },
    _reread_diff: diff,
    _geometrija_perskaityta_at: now,
  };
  // the drawing's project-level reads the lane brings along (the door schedule, the symbols counted from
  // the paths): a project read before they existed gets them with the same click — never overwritten by
  // their absence
  for (const key of PROJECT_READ_KEYS) {
    if (isObj(result[key])) project[key] = result[key];
  }
  return { project, diff };
}

/** The four counts the banner reports afterwards. */
export function freeRereadSummary(santrauka) {
  const n = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);
  return {
    konturai: n(santrauka?.konturai),
    perimetrai: n(santrauka?.perimetrai_sudeti),
    tusti: n(santrauka?.perimetrai_tusti),
    dangos: n(santrauka?.grindu_dangos),
  };
}

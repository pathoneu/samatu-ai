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

// Outlines that follow the walls — the lane's, the raster lane's, or his own (backend dimension_sum.WALL_OUTLINES).
const WALL_OUTLINES = new Set(['vektoriniai_konturai', 'sienu_konturas', 'corrected', 'manual']);
// Wall lengths read off the plan's dimension strings — added up wall by wall (dimension_sum), or the two sides of
// a rectangle the strings close (plan_dimensions).
const FROM_DIMENSIONS = new Set(['matmenu_eilutes', 'plano_matmenys']);
// A wall length that is his — typed, or a proposal he confirmed in Patikra (both are stored as his): never re-read,
// so never counted as the drawing's.
const TYPED_BY_HIM = new Set(['user_override', 'manual']);

/**
 * What the banner reports afterwards: the project AS IT STANDS after the read, whichever read did it.
 *
 * 2026-10-06 (contractor walkthrough on objektas_h): it used to print the lane's counts of THIS run, and a
 * room whose walls an earlier read had already added up keeps its figure and is not added up again — so the
 * notice said „sienų ilgiai sudėti iš matmenų: 0" on a project where six rooms' walls came from the drawing's
 * dimensions. Counted on the merged rooms, it says what he now has.
 */
export function freeRereadState(project) {
  const stored = Array.isArray(project?.v8_rooms) && project.v8_rooms.length ? project.v8_rooms : project?.patalpos;
  const rooms = (Array.isArray(stored) ? stored : []).filter(isObj);
  const count = (pick) => rooms.filter(pick).length;
  return {
    count: rooms.length,
    konturai: count((r) => WALL_OUTLINES.has(String(r.polygon_source || ''))),
    perimetrai: count((r) => FROM_DIMENSIONS.has(String(r.perimetras_saltinis || ''))),
    jusu: count((r) => TYPED_BY_HIM.has(String(r.perimetras_saltinis || ''))),
    dangos: count((r) => r.grindu_danga_saltinis === 'grindu_planas'),
  };
}

/**
 * The banner's sentence for that state (`t` = i18next's). Only what the drawing gave is listed: a contractor reads
 * „sienų ilgiai iš plano matmenų — 0" as a failure (2026-10-06 review). His own wall lengths ride with the plan's,
 * or stand alone when the plan gave none; a read that gave none of the three says so in one plain sentence.
 */
export function freeRereadDoneText(state, t) {
  const n = (k) => Math.max(0, Number(state?.[k]) || 0);
  const [konturai, perimetrai, jusu, dangos] = [n('konturai'), n('perimetrai'), n('jusu'), n('dangos')];
  if (!konturai && !perimetrai && !dangos) return t('project.freeReread.doneNothing');
  const walls = perimetrai
    ? t('project.freeReread.donePart.perimetrai', { n: perimetrai })
      + (jusu ? t('project.freeReread.doneTyped', { n: jusu }) : '')
    : (jusu ? t('project.freeReread.donePart.jusu', { n: jusu }) : '');
  const parts = [
    konturai ? t('project.freeReread.donePart.konturai', { n: konturai }) : '',
    walls,
    dangos ? t('project.freeReread.donePart.dangos', { n: dangos }) : '',
  ].filter(Boolean);
  return t('project.freeReread.done', { count: n('count'), parts: parts.join(', ') });
}

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
 * changed is recorded in `_reread_diff` for the banner. Only the rooms, the
 * lane's own records (`_meta.geometrija`, the tables stage's `_meta.lenteles`,
 * the sheet zones `_meta.zonos`) and the drawing's project-level reads
 * (PROJECT_READ_KEYS) change here — rows, prices,
 * assumptions and scope are not this module's to touch; the caller rebuilds the
 * rows on the merged rooms through the usual /recompute-interior path. Pure.
 */

import { mergeReextractRooms } from './mergeReextract.js';
import { carryIdentity, renumberMap, renumberProject } from './roomRenumber.js';

/**
 * Project-level reads the free re-read returns beside the rooms (api/free_reread.py): the door schedule, the
 * symbols counted from the paths, and the window and finish schedules of the „lentelės" stage (Pathon v3 W3-A).
 */
export const PROJECT_READ_KEYS = Object.freeze(['_duru_ziniarastis', '_vector_symbols', '_langu_ziniarastis', '_apdailos_lentele',
  // Pathon v3 W5-D D6 — sent only with the server's SAMATU_REREAD_FIGURES on: the designer's figures and the anchors
  // billed from them
  '_autoriaus_kiekiai', '_walls_anchor', '_floor_anchors']);

const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);

// A zone he drew or corrected himself — kept on its sheet whatever the read finds there (the re-read's rule for
// everything he set: lib/mergeReextract.js).
const USER_ZONE_SOURCES = new Set(['naudotojas', 'manual', 'corrected']);
const isUserZone = (z) => USER_ZONE_SOURCES.has(String(z?.evidence?.source || ''));

/**
 * `_meta.zonos` = {page: [zone]} (extractor/sheet_zones.py) for the sheets the read looked at. Sheet by sheet:
 * a sheet the read covered takes its zones (plus the ones he drew there), a sheet it did not keeps the stored ones.
 * Undefined when the read brought no zones — the stored map stays as it is.
 */
export function mergeZones(stored, read) {
  if (!isObj(read)) return undefined;
  const out = { ...(isObj(stored) ? stored : {}) };
  for (const [page, zones] of Object.entries(read)) {
    const his = (Array.isArray(out[page]) ? out[page] : []).filter(isUserZone);
    out[page] = [...(Array.isArray(zones) ? zones : []).filter((z) => !isUserZone(z)), ...his];
  }
  return out;
}

/**
 * The lane's records under `_meta` that land with the re-read: its own (`geometrija`), the tables stage's
 * (`lenteles`, a record of the whole document — taken whole) and the sheet zones (`zonos`, sheet by sheet).
 * Only what the read brought; nothing is overwritten by its absence.
 */
export function mergeReadMeta(storedMeta, readMeta) {
  const base = isObj(storedMeta) ? storedMeta : {};
  if (!isObj(readMeta)) return { ...base };
  const out = { ...base };
  if (readMeta.geometrija !== undefined) out.geometrija = readMeta.geometrija;
  if (isObj(readMeta.lenteles)) out.lenteles = readMeta.lenteles;
  // the floor sheet's key lines (Pathon v3 W5-D, D1) — a record of the floor sheet, taken whole
  if (Array.isArray(readMeta.grindu_legenda)) out.grindu_legenda = readMeta.grindu_legenda;
  // the wall / partition types the legends name (W5-D D9) — a record of the drawing, taken whole
  if (isObj(readMeta.sienu_tipai)) out.sienu_tipai = readMeta.sienu_tipai;
  // where the room numbers come from (v4 Phase 3a, api/free_reread.renumber_rooms) — kept, so the drawing's table
  // is not opened again on the next re-read
  if (isObj(readMeta.kambariu_tapatybe)) out.kambariu_tapatybe = readMeta.kambariu_tapatybe;
  const zonos = mergeZones(base.zonos, readMeta.zonos);
  if (zonos !== undefined) out.zonos = zonos;
  return out;
}

/**
 * `{ project, diff }` — the stored project with the lane's read merged in, or
 * `{ project: null }` when there is nothing to land (the lane failed, or it
 * answered without rooms).
 */
export function mergeFreeReread(rawBase, result, now = new Date().toISOString()) {
  if (!isObj(rawBase) || !isObj(result) || result.lane === 'failed') return { project: null, diff: null };
  const fresh = Array.isArray(result.patalpos) ? result.patalpos.filter(isObj) : [];
  if (!fresh.length) return { project: null, diff: null };
  // rooms the read gave the drawing's numbers (K2 → 1-2, v4 Phase 3a): the stored project is renumbered first, so
  // each room meets its fresh read under one key and keeps what he set on it (lib/roomRenumber.js)
  const renumber = renumberMap(result._perkeisti_numeriai);
  const base = renumberProject(rawBase, renumber);
  const stored = Array.isArray(base.v8_rooms) && base.v8_rooms.length ? base.v8_rooms : base.patalpos;
  const merged = mergeReextractRooms(stored, fresh, now);
  const rooms = carryIdentity(merged.rooms, fresh, renumber);
  const { diff } = merged;
  const project = {
    ...base,
    patalpos: rooms,
    v8_rooms: rooms,
    _meta: mergeReadMeta(base._meta, result._meta),
    _reread_diff: diff,
    _geometrija_perskaityta_at: now,
  };
  // the drawing's project-level reads the lane brings along (the door schedule, the symbols counted from
  // the paths): a project read before they existed gets them with the same click — never overwritten by
  // their absence
  for (const key of PROJECT_READ_KEYS) {
    if (isObj(result[key]) || Array.isArray(result[key])) project[key] = result[key];
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

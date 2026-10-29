/**
 * freeReread — the merge path for a fresh read of the drawing that costs €0 (the geometry lane: vector outlines,
 * perimeters added from the written strings, floor coverings off the floor plan).
 *
 * The product no longer offers a whole-project free re-read (2026-10-29 founder decision: a sąmata is a dated
 * document — the drawing is read once at upload, the result stands). What remains is per-sheet reading from
 * the viewer: „Perskaityti lapą" (api/detect_run.py) and other viewer features that call the lane for one
 * sheet (outline edits, scale line, legend counts, „Parodyti patalpą"). Those /detect-run results land here
 * through `mergeFreeReread`.
 *
 * The rules are the re-read's rules (lib/mergeReextract.js): a room he verified keeps its facts, a number he
 * typed or an outline he corrected stays, and what changed is recorded in `_reread_diff` for the Kas pasikeitė
 * notice. Only the rooms, the lane's own records (`_meta.geometrija`, the tables stage's `_meta.lenteles`,
 * the sheet zones `_meta.zonos`) and the drawing's project-level reads (PROJECT_READ_KEYS) change here —
 * rows, prices, assumptions and scope are not this module's to touch; the caller rebuilds the rows on the
 * merged rooms through the usual /recompute-interior path. Pure.
 */

import { mergeReextractRooms } from './mergeReextract.js';
import { carryIdentity, renumberedCount, renumberMap, renumberProject } from './roomRenumber.js';

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
  // v4 Phase 3c-2: the legend count proposals and the sheet kinds read from the text — records of the whole
  // drawing, taken whole, so a stored project keeps the counts the server just computed
  if (isObj(readMeta.legendos_siulymai)) out.legendos_siulymai = readMeta.legendos_siulymai;
  if (isObj(readMeta.lapu_rusys_is_teksto)) out.lapu_rusys_is_teksto = readMeta.lapu_rusys_is_teksto;
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
  // „Kas pasikeitė" counts the rooms that took the drawing's numbers („17 patalpų gavo brėžinio numerius")
  const renumbered = renumberedCount(renumber);
  const diff = renumbered
    ? { ...(merged.diff || { changed: [], kept: [], added: [], removed: [] }), perkeisti_numeriai: renumbered }
    : merged.diff;
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


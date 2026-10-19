// settingsSections — how „Nustatymai" (AssumptionsPanel) is grouped (Pathon v3 B1-E, 2026-10-19).
//
// Founder: „Nustatymai all messed up" — one long form, a wall of buttons. Now five sections, collapsed
// except the one a caller asked for; each setting is one line; per-room settings show the value for all
// rooms first and a row only for the rooms that differ. Pure: which section holds which engine input
// (names unchanged — these are the `_overrides` keys the backend reads) and the per-room split.

import { BAG_KEY, BUCKET_KEY } from './packaging.js';

export const SETTINGS_SECTIONS = Object.freeze(['bendra', 'patalpos', 'angos', 'medziagos', 'pasirinkimai']);

/** Engine input → its section. Every input the panel edits is here (a test holds the list). */
export const SECTION_OF_FIELD = Object.freeze({
  glaistimo_lygis: 'bendra',
  lubu_auksciai: 'patalpos',
  lubu_aukstis_m: 'patalpos',
  walls_paint_override: 'patalpos',
  stretch_ceiling_override: 'patalpos',
  vidaus_durys_beapvadines: 'angos',
  angokrasciai_apimtis: 'angos',
  sienos_storis_m: 'angos',
  custom_windows: 'angos',
  custom_doors: 'angos',
  [BAG_KEY]: 'medziagos',
  [BUCKET_KEY]: 'medziagos',
  santechnika_potinkinis: 'pasirinkimai',
  led_nisu_ivertinimas: 'pasirinkimai',
});

/** The section a jump („Atidaryti nustatymus", an engine message) should open, or null. */
export function sectionForField(field) {
  if (!field) return null;
  return Object.prototype.hasOwnProperty.call(SECTION_OF_FIELD, field) ? SECTION_OF_FIELD[field] : null;
}

/**
 * Per-room split: the value most rooms share (ties → the first room's) and the rooms that differ from it.
 * `valueOf(room)` gives the room's current value; `same(a, b)` compares (numbers to the centimetre).
 * → { common, differing: [room], allSame }
 */
export function perRoomSplit(rooms, valueOf, same = defaultSame) {
  const list = Array.isArray(rooms) ? rooms : [];
  if (!list.length) return { common: null, differing: [], allSame: true };
  const groups = [];
  for (const r of list) {
    const v = valueOf(r);
    const g = groups.find((x) => same(x.value, v));
    if (g) g.n += 1; else groups.push({ value: v, n: 1 });
  }
  const top = groups.reduce((best, g) => (g.n > best.n ? g : best), groups[0]);
  const differing = list.filter((r) => !same(top.value, valueOf(r)));
  return { common: top.value, differing, allSame: differing.length === 0 };
}

function defaultSame(a, b) {
  if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) < 0.005;
  return a === b;
}

/** The rooms whose row is shown: the differing ones, plus rooms a jump named or he just edited (`also`), or all. */
export function visibleRoomRows(rooms, differing, { showAll = false, also = [] } = {}) {
  const list = Array.isArray(rooms) ? rooms : [];
  if (showAll) return list;
  const keep = new Set((differing || []).map((r) => String(r.nr)));
  for (const nr of also || []) if (nr != null) keep.add(String(nr));
  return list.filter((r) => keep.has(String(r.nr)));
}

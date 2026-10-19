/**
 * changeSummary — „Kas pasikeitė" after a fresh read of the drawing (Pathon v3 W4-A M3).
 *
 * The re-read already records what it did to the ROOMS (`_reread_diff`, lib/mergeReextract.js). What the
 * contractor bills is the ROWS, and the reads that came along (a schedule, the tables, the sheet areas)
 * change what the rows rest on — so the landing paths (lib/rereadApply.projectAfterReread,
 * lib/freeRereadApi.landFreeRereadResult) add both to the same diff with `withChanges`:
 *
 *   _reread_diff.eilutes     = {changed: [{id, aprasymas, skyrius, unit, from, to}], added: [...], removed: [...]}
 *   _reread_diff.perskaityta = ['_langu_ziniarastis', 'lenteles', …] — reads that appeared or changed
 *
 * and the banner (components/project/RereadDiffBanner.jsx) says it on one line — „Kas pasikeitė — 12 eilučių
 * · Peržiūrėti · Atšaukti". „Atšaukti" puts back the project as it was before the read through the saved
 * versions (`rereadUndoTarget` picks it). Pure.
 */

import { PROJECT_READ_KEYS } from './freeReread.js';

const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
const num = (v) => (v != null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : null);
const keyOf = (r) => (r?.id != null ? `id:${r.id}` : `l:${String(r?.aprasymas || '')}|${String(r?.skyrius || '')}`);
const unitOf = (r) => String(r?.mato_vnt || r?.vnt || '');

/** The rows whose quantity moved, appeared or went, by row id (label + section for a row without one). */
export function rowChanges(beforeRows, afterRows) {
  const before = new Map();
  for (const r of Array.isArray(beforeRows) ? beforeRows : []) if (isObj(r) && !before.has(keyOf(r))) before.set(keyOf(r), r);
  const seen = new Set();
  const changed = [];
  const added = [];
  for (const r of Array.isArray(afterRows) ? afterRows : []) {
    if (!isObj(r)) continue;
    const k = keyOf(r);
    if (seen.has(k)) continue;
    seen.add(k);
    const old = before.get(k);
    const entry = { id: r.id ?? null, aprasymas: r.aprasymas || '', skyrius: r.skyrius || '', unit: unitOf(r) };
    if (!old) { added.push({ ...entry, to: num(r.kiekis) }); continue; }
    const from = num(old.kiekis);
    const to = num(r.kiekis);
    if ((from == null) !== (to == null) || (from != null && Math.abs(from - to) > 0.005)) {
      changed.push({ ...entry, from, to });
    }
  }
  const removed = [];
  for (const [k, r] of before) {
    if (!seen.has(k)) removed.push({ id: r.id ?? null, aprasymas: r.aprasymas || '', skyrius: r.skyrius || '', unit: unitOf(r), from: num(r.kiekis) });
  }
  return { changed, added, removed };
}

/** The drawing's reads the banner names, and where each lives on the project. */
export const READ_KEYS = Object.freeze([
  ...PROJECT_READ_KEYS.map((k) => ({ key: k, get: (p) => p?.[k] })),
  { key: 'lenteles', get: (p) => (isObj(p?._meta) ? p._meta.lenteles : undefined) },
  { key: 'zonos', get: (p) => (isObj(p?._meta) ? p._meta.zonos : undefined) },
]);

const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/** Reads that appeared, or came back different, with this read. */
export function readChanges(before, after) {
  return READ_KEYS
    .filter(({ get }) => get(after) != null && !same(get(before), get(after)))
    .map(({ key }) => key);
}

/** The re-read's diff with the rows and the reads added (the diff itself may be null — rooms unchanged). */
export function withChanges(diff, before, after) {
  return {
    ...(isObj(diff) ? diff : { changed: [], kept: [], added: [], removed: [] }),
    eilutes: rowChanges(before?.darbu_sarasas, after?.darbu_sarasas),
    perskaityta: readChanges(before, after),
  };
}

/** How many rows the read moved (changed + new + gone). */
export function rowChangeCount(diff) {
  const e = isObj(diff?.eilutes) ? diff.eilutes : null;
  if (!e) return 0;
  return (e.changed?.length || 0) + (e.added?.length || 0) + (e.removed?.length || 0);
}

// The saves a fresh read is stored under (lib/projectStore versionSource; backend db.VERSION_SOURCES).
const READ_SOURCES = new Set(['perskaityta', 'lapas']);

/**
 * Which saved version „Atšaukti" puts back: the one just before the newest read. `versions` newest first
 * (GET …/versions). `{target, read, later}` — `later` = how many saves came after the read (they go too, and are
 * kept as „Prieš grąžinant"); null when no read or nothing before it is saved.
 */
export function rereadUndoTarget(versions) {
  const list = Array.isArray(versions) ? versions : [];
  const at = list.findIndex((v) => READ_SOURCES.has(v?.saltinis));
  if (at < 0 || !list[at + 1]) return null;
  return { target: list[at + 1], read: list[at], later: at };
}

/**
 * scope — „Ką skaičiuoti?" as the contractor wants it (apimtis, item 4).
 *
 * The project carries `_apimtis`:
 *   { patalpos_ne: ['07'],            rooms he does not do — kept on the sheet, out of every row
 *     darbai_ne: ['plyteles'],        work families he does not do
 *     lubos: 'dazomos'|'ne_musu'|'itempiamos',   ceilings, project-wide default
 *     sienos_angos: 'atimti'|'neatimti' }        wall area with / without openings
 *
 * It travels to the backend as `rules_override.apimtis` on every recompute and
 * is ENFORCED there (extractor/scope.py) — the sheet, the exports and the
 * template all see the same numbers. Nothing here changes a quantity; these are
 * pure helpers over the object. Absent = as the drawing says.
 *
 * Pure: no React, no DOM, no i18n. Covered by scope.test.js.
 */

export const WORK_FAMILIES = ['apdaila', 'grindys', 'plyteles', 'santechnika', 'elektra'];
export const LUBOS_CHOICES = ['dazomos', 'ne_musu', 'itempiamos'];
export const SIENOS_ANGOS_CHOICES = ['atimti', 'neatimti'];

const nr = (v) => String(v ?? '').trim();

/** A complete scope object from whatever the project carries. */
export function normalizeScope(raw) {
  const r = raw && typeof raw === 'object' ? raw : {};
  return {
    patalpos_ne: Array.isArray(r.patalpos_ne) ? [...new Set(r.patalpos_ne.map(nr).filter(Boolean))].sort() : [],
    darbai_ne: WORK_FAMILIES.filter((f) => Array.isArray(r.darbai_ne) && r.darbai_ne.includes(f)),
    lubos: LUBOS_CHOICES.includes(r.lubos) ? r.lubos : 'dazomos',
    sienos_angos: SIENOS_ANGOS_CHOICES.includes(r.sienos_angos) ? r.sienos_angos : 'atimti',
  };
}

/** True when the scope says nothing beyond „as the drawing says". */
export function isDefaultScope(raw) {
  const s = normalizeScope(raw);
  return s.patalpos_ne.length === 0 && s.darbai_ne.length === 0
    && s.lubos === 'dazomos' && s.sienos_angos === 'atimti';
}

/** What goes into `rules_override.apimtis` — null when there is nothing to say. */
export function scopeForBackend(raw) {
  return isDefaultScope(raw) ? null : normalizeScope(raw);
}

export function isRoomIncluded(raw, roomNr) {
  return !normalizeScope(raw).patalpos_ne.includes(nr(roomNr));
}

export function isFamilyOn(raw, family) {
  return !normalizeScope(raw).darbai_ne.includes(family);
}

export function withRoomIncluded(raw, roomNr, included) {
  const s = normalizeScope(raw);
  const set = new Set(s.patalpos_ne);
  if (included) set.delete(nr(roomNr)); else if (nr(roomNr)) set.add(nr(roomNr));
  return { ...s, patalpos_ne: [...set].sort() };
}

export function withFamily(raw, family, on) {
  const s = normalizeScope(raw);
  if (!WORK_FAMILIES.includes(family)) return s;
  const set = new Set(s.darbai_ne);
  if (on) set.delete(family); else set.add(family);
  return { ...s, darbai_ne: WORK_FAMILIES.filter((f) => set.has(f)) };
}

export function withLubos(raw, lubos) {
  const s = normalizeScope(raw);
  return { ...s, lubos: LUBOS_CHOICES.includes(lubos) ? lubos : s.lubos };
}

export function withSienosAngos(raw, choice) {
  const s = normalizeScope(raw);
  return { ...s, sienos_angos: SIENOS_ANGOS_CHOICES.includes(choice) ? choice : s.sienos_angos };
}

/** `rules_override` with the scope folded in (or without the key when default). */
export function rulesWithScope(overrides, scopeRaw) {
  const base = { ...(overrides || {}) };
  delete base.apimtis;
  const s = scopeForBackend(scopeRaw);
  return s ? { ...base, apimtis: s } : base;
}

// ── remembered choices ──────────────────────────────────────────────────────
// The upload screen pre-selects a project-level choice once the contractor has
// made the same one on his last three projects — and says so. Kept as a plain
// history list so nothing is inferred from a single project.

export const REMEMBER_AFTER = 3;
const PROJECT_LEVEL_KEYS = ['lubos', 'sienos_angos', 'darbai_ne'];

function sameValue(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** History with this project's project-level choices appended (newest last, capped). */
export function rememberScope(history, scopeRaw, cap = 10) {
  const s = normalizeScope(scopeRaw);
  const entry = Object.fromEntries(PROJECT_LEVEL_KEYS.map((k) => [k, s[k]]));
  const list = Array.isArray(history) ? history.slice() : [];
  list.push(entry);
  return list.slice(-cap);
}

/**
 * The project-level choices repeated on the last REMEMBER_AFTER projects, or {}.
 * Only a value that is NOT the default is worth pre-selecting.
 */
export function learnedDefaults(history) {
  const list = Array.isArray(history) ? history.filter((h) => h && typeof h === 'object') : [];
  if (list.length < REMEMBER_AFTER) return {};
  const last = list.slice(-REMEMBER_AFTER);
  const out = {};
  for (const key of PROJECT_LEVEL_KEYS) {
    const v = last[0][key];
    const defaultValue = normalizeScope({})[key];
    if (last.every((h) => sameValue(h[key], v)) && !sameValue(v, defaultValue)) out[key] = v;
  }
  return out;
}

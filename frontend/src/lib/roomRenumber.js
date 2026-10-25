/**
 * roomRenumber — a stored project's rooms given the drawing's numbers (Pathon v4 Phase 3a, 2026-10-25).
 *
 * A project read before the room identity came from the drawing can carry the reading model's invented keys
 * (objektas_i: K1…K8 / D1…D9 where the drawing numbers 1–8 and 1–9 in two units). The free re-read
 * (api/free_reread.renumber_rooms) answers with its rooms already under the drawing's numbers and a map
 * `_perkeisti_numeriai` = { old: new }. The re-read merges rooms BY NUMBER (lib/mergeReextract.js), so the stored
 * project is renumbered with that map FIRST — then every room meets its fresh read under one key, and what he set
 * on it (a verified room, a typed perimeter, a corrected outline, prices on the rows) stays attached by the
 * re-read's usual rules.
 *
 * Renumbered here: the rooms of both lists (`patalpos`, `v8_rooms`; the old key kept as `_modelio_nr`), his per-room
 * overrides (`_per_room_overrides`, keyed by room), the scope's rooms (`_apimtis.patalpos_ne`, `patalpu_sritys_ne`
 * — and the copy under `_overrides.apimtis`), and the rows' room references (`contributions[].room_nr`). The map
 * itself is kept on the project (composed with an earlier one) so Patikra can say „K2 → 1-2". Pure.
 */

const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
const key = (v) => (v == null ? '' : String(v).trim());

/** The map as {old: new} strings; {} when there is nothing usable. */
export function renumberMap(raw) {
  if (!isObj(raw)) return {};
  const out = {};
  for (const [from, to] of Object.entries(raw)) {
    const a = key(from);
    const b = key(to);
    if (a && b && a !== b) out[a] = b;
  }
  return out;
}

const rename = (map, nr) => (Object.prototype.hasOwnProperty.call(map, key(nr)) ? map[key(nr)] : nr);

function renumberRooms(rooms, map) {
  if (!Array.isArray(rooms)) return rooms;
  return rooms.map((r) => {
    if (!isObj(r)) return r;
    const was = key(r.nr);
    if (!Object.prototype.hasOwnProperty.call(map, was)) return r;
    return { ...r, nr: map[was], _modelio_nr: r._modelio_nr ?? was };
  });
}

function renumberKeys(obj, map) {
  if (!isObj(obj)) return obj;
  const out = {};
  for (const [k, v] of Object.entries(obj)) out[rename(map, k)] = v;
  return out;
}

function renumberScope(scope, map) {
  if (!isObj(scope)) return scope;
  const out = { ...scope };
  if (Array.isArray(scope.patalpos_ne)) out.patalpos_ne = scope.patalpos_ne.map((nr) => rename(map, nr));
  if (isObj(scope.patalpu_sritys_ne)) out.patalpu_sritys_ne = renumberKeys(scope.patalpu_sritys_ne, map);
  return out;
}

function renumberRows(rows, map) {
  if (!Array.isArray(rows)) return rows;
  return rows.map((row) => {
    if (!isObj(row) || !Array.isArray(row.contributions)) return row;
    let touched = false;
    const contributions = row.contributions.map((c) => {
      if (!isObj(c) || !Object.prototype.hasOwnProperty.call(map, key(c.room_nr))) return c;
      touched = true;
      return { ...c, room_nr: map[key(c.room_nr)] };
    });
    return touched ? { ...row, contributions } : row;
  });
}

/** The project with every room key the map names replaced; the same object when the map is empty. */
export function renumberProject(project, rawMap) {
  const map = renumberMap(rawMap);
  if (!isObj(project) || !Object.keys(map).length) return project;
  const out = { ...project };
  if (Array.isArray(project.patalpos)) out.patalpos = renumberRooms(project.patalpos, map);
  if (Array.isArray(project.v8_rooms)) out.v8_rooms = renumberRooms(project.v8_rooms, map);
  if (isObj(project._per_room_overrides)) out._per_room_overrides = renumberKeys(project._per_room_overrides, map);
  if (isObj(project._apimtis)) out._apimtis = renumberScope(project._apimtis, map);
  if (isObj(project._overrides) && isObj(project._overrides.apimtis)) {
    out._overrides = { ...project._overrides, apimtis: renumberScope(project._overrides.apimtis, map) };
  }
  if (Array.isArray(project.darbu_sarasas)) out.darbu_sarasas = renumberRows(project.darbu_sarasas, map);
  const earlier = renumberMap(project._perkeisti_numeriai);
  const composed = {};
  for (const [from, to] of Object.entries(earlier)) composed[from] = rename(map, to);
  out._perkeisti_numeriai = { ...composed, ...map };
  return out;
}

/** The drawing's identity keys on the merged rooms the map renamed: a room he verified is kept whole by the
 * re-read, so it would miss the unit the fresh read gives it. Only `_vienetas` / `_nr_brezinyje`, only when absent. */
export function carryIdentity(rooms, fresh, rawMap) {
  const renamed = new Set(Object.values(renumberMap(rawMap)));
  if (!renamed.size || !Array.isArray(rooms)) return rooms;
  const byNr = new Map((Array.isArray(fresh) ? fresh : []).filter(isObj).map((r) => [key(r.nr), r]));
  return rooms.map((r) => {
    if (!isObj(r) || !renamed.has(key(r.nr))) return r;
    const f = byNr.get(key(r.nr));
    if (!f) return r;
    const add = {};
    for (const k of ['_vienetas', '_nr_brezinyje']) if (r[k] == null && f[k] != null) add[k] = f[k];
    return Object.keys(add).length ? { ...r, ...add } : r;
  });
}

/**
 * The key a room wore before the re-read gave it the drawing's number („K2" for 1-2) — said once in Patikra
 * („buvo K2") until he checks the room; null when the project carries no map, the room was not renumbered, or he
 * has checked it. `_modelio_nr` (the oldest key — renumberRooms keeps the first) when the map knows it, else a key
 * the map sends to the room.
 */
export function formerRoomKey(project, room) {
  if (!isObj(room) || room.user_verified_at) return null;
  const map = renumberMap(project?._perkeisti_numeriai);
  const nr = key(room.nr);
  if (!nr || !Object.keys(map).length) return null;
  const model = key(room._modelio_nr);
  if (model && model !== nr && map[model] === nr) return model;
  return Object.keys(map).find((k) => map[k] === nr) || null;
}

/** How many rooms the map gave the drawing's numbers (distinct new keys). */
export function renumberedCount(rawMap) {
  return new Set(Object.values(renumberMap(rawMap))).size;
}

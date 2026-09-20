/**
 * mergeReextract.js — what a re-read of the drawing may and may not replace.
 *
 * `ReextractButton` used to spread the fresh extraction over the stored
 * project: every room, every row. That threw away the contractor's own work —
 * the perimeter he typed, the polygon he corrected, the door he added on the
 * check sheet, the rooms he stamped „Viskas teisinga" — and told him nothing
 * about what the second read had changed. Two reads of one PDF are not
 * identical (openings and perimeters move between runs), so a re-read is an
 * EVENT he has to see, not a silent refresh (council verdict 2, 2026-09-13).
 *
 * Rules (pure, no I/O):
 *   • a room he verified keeps its old facts entirely — he confirmed them; the
 *     diff says what the new read would have made of it;
 *   • an unverified room takes the new read, except the facts he set himself
 *     (`plotas_saltinis` / `perimetras_saltinis` / `lubu_aukstis_saltinis` =
 *     user_override or manual, `plotas_source` = manual_polygon, `polygon_source`
 *     = corrected or manual, `_angos_user_at`, `_paskirtis_user_at`);
 *   • a room the new read did not return stays when he touched it, else it is
 *     dropped and listed;
 *   • rows go through `mergeDarbuSarasasEdits` (prices, manual quantities,
 *     symbol-count lines);
 *   • `_reread_diff` records, per room, what changed, what was kept and what
 *     the new read said — the banner reads it, „Supratau" clears it.
 *
 * The caller still has to REBUILD the rows on the merged rooms (the fresh
 * extraction built its rows on its own rooms, without the carried facts and
 * without the project's scope) — `ReextractButton` does that through the same
 * `/recompute-interior` path a room edit on the sheet uses.
 */

import { mergeDarbuSarasasEdits } from './mergeDarbuSarasas.js';
import { isRoomVerified } from './roomSheet.js';

/** `*_saltinis` values that mean „he typed it". */
export const USER_SOURCES = Object.freeze(['user_override', 'manual']);
/** `polygon_source` values that mean „he drew or accepted it". */
export const USER_POLYGON_SOURCES = Object.freeze(['corrected', 'manual']);
/** `plotas_source` values that mean the area follows his own polygon. */
export const USER_AREA_SOURCES = Object.freeze(['manual', 'manual_polygon']);

const POLYGON_KEYS = [
  'polygon_pct', 'polygon_pdf', 'page_width_pdf', 'page_height_pdf', 'page_nr',
  'polygon_source', 'polygon_confidence', 'polygon_traced_at',
];
const DOOR_KINDS = new Set(['duris', 'pasleptos_duris']);
const NUMERIC_FACTS = ['plotas_m2', 'perimetras_m', 'lubu_aukstis_m'];

const isObj = (r) => !!r && typeof r === 'object';
const nrKey = (r) => (r?.nr == null ? '' : String(r.nr).trim());
const src = (v) => String(v ?? '').trim().toLowerCase();
const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const same = (a, b) => (a == null && b == null) || (a != null && b != null && Math.abs(a - b) < 0.005);
const roomName = (r) => String(r?.pavadinimas || '').trim();

/** Door and window counts a room's `elementai` add up to. */
export function openingCounts(elementai) {
  let durys = 0;
  let langai = 0;
  for (const el of Array.isArray(elementai) ? elementai : []) {
    const kind = src(el?.tipas);
    const n = Number(el?.kiekis);
    const k = Number.isFinite(n) ? n : 1;
    if (DOOR_KINDS.has(kind)) durys += k;
    else if (kind === 'langas') langai += k;
  }
  return { durys, langai };
}

/** True when the contractor did anything to this room that a re-read must not undo. */
export function roomTouched(room) {
  if (!isObj(room)) return false;
  return isRoomVerified(room)
    || USER_SOURCES.includes(src(room.plotas_saltinis))
    || USER_SOURCES.includes(src(room.perimetras_saltinis))
    || USER_SOURCES.includes(src(room.lubu_aukstis_saltinis))
    || USER_AREA_SOURCES.includes(src(room.plotas_source))
    || USER_POLYGON_SOURCES.includes(src(room.polygon_source))
    || !!room._angos_user_at
    || !!room._paskirtis_user_at
    || (USER_SOURCES.includes(src(room.grindu_danga_saltinis)) && !!room.grindu_danga)
    || !!room._prideta_is_plano;
}

/** The facts that differ between two versions of one room: [{key, from, to}]. */
export function factDiff(before, after) {
  const out = [];
  for (const key of NUMERIC_FACTS) {
    const a = num(before?.[key]);
    const b = num(after?.[key]);
    if (!same(a, b)) out.push({ key, from: a, to: b });
  }
  const oa = openingCounts(before?.elementai);
  const ob = openingCounts(after?.elementai);
  if (oa.durys !== ob.durys) out.push({ key: 'durys', from: oa.durys, to: ob.durys });
  if (oa.langai !== ob.langai) out.push({ key: 'langai', from: oa.langai, to: ob.langai });
  const pa = src(before?.paskirtis);
  const pb = src(after?.paskirtis);
  if (pa !== pb) out.push({ key: 'paskirtis', from: before?.paskirtis ?? null, to: after?.paskirtis ?? null });
  return out;
}

/**
 * The fresh read of a room with the facts he set himself put back on it.
 * Returns the room and the list of facts kept against a different new read.
 */
export function carryUserFacts(oldRoom, freshRoom) {
  const room = { ...freshRoom };
  const carried = [];
  const keep = (key, kept, read) => {
    if (!same(num(kept), num(read))) carried.push({ key, kept: num(kept), read: num(read) });
  };

  const areaIsHis = USER_SOURCES.includes(src(oldRoom.plotas_saltinis))
    || USER_AREA_SOURCES.includes(src(oldRoom.plotas_source));
  if (areaIsHis && oldRoom.plotas_m2 != null) {
    keep('plotas_m2', oldRoom.plotas_m2, freshRoom.plotas_m2);
    room.plotas_m2 = oldRoom.plotas_m2;
    if (oldRoom.plotas_saltinis != null) room.plotas_saltinis = oldRoom.plotas_saltinis;
    if (oldRoom.plotas_source != null) room.plotas_source = oldRoom.plotas_source;
  }
  if (USER_SOURCES.includes(src(oldRoom.perimetras_saltinis)) && oldRoom.perimetras_m != null) {
    keep('perimetras_m', oldRoom.perimetras_m, freshRoom.perimetras_m);
    room.perimetras_m = oldRoom.perimetras_m;
    room.perimetras_saltinis = oldRoom.perimetras_saltinis;
  }
  if (USER_SOURCES.includes(src(oldRoom.lubu_aukstis_saltinis)) && oldRoom.lubu_aukstis_m != null) {
    keep('lubu_aukstis_m', oldRoom.lubu_aukstis_m, freshRoom.lubu_aukstis_m);
    room.lubu_aukstis_m = oldRoom.lubu_aukstis_m;
    room.lubu_aukstis_saltinis = oldRoom.lubu_aukstis_saltinis;
  }
  if (USER_POLYGON_SOURCES.includes(src(oldRoom.polygon_source))) {
    for (const k of POLYGON_KEYS) {
      if (oldRoom[k] !== undefined) room[k] = oldRoom[k];
      else delete room[k];
    }
    if (freshRoom.polygon_pct || freshRoom.polygon_pdf) {
      carried.push({ key: 'polygon', kept: src(oldRoom.polygon_source), read: src(freshRoom.polygon_source) || null });
    }
  }
  if (oldRoom._angos_user_at && Array.isArray(oldRoom.elementai)) {
    const was = openingCounts(oldRoom.elementai);
    const now = openingCounts(freshRoom.elementai);
    if (was.durys !== now.durys) carried.push({ key: 'durys', kept: was.durys, read: now.durys });
    if (was.langai !== now.langai) carried.push({ key: 'langai', kept: was.langai, read: now.langai });
    room.elementai = oldRoom.elementai;
    room._angos_user_at = oldRoom._angos_user_at;
  }
  if (oldRoom._paskirtis_user_at && oldRoom.paskirtis != null) {
    if (src(oldRoom.paskirtis) !== src(freshRoom.paskirtis)) {
      carried.push({ key: 'paskirtis', kept: oldRoom.paskirtis, read: freshRoom.paskirtis ?? null });
    }
    room.paskirtis = oldRoom.paskirtis;
    room._paskirtis_user_at = oldRoom._paskirtis_user_at;
  }
  if (USER_SOURCES.includes(src(oldRoom.grindu_danga_saltinis)) && oldRoom.grindu_danga) {
    if (src(oldRoom.grindu_danga) !== src(freshRoom.grindu_danga) && freshRoom.grindu_danga != null) {
      carried.push({ key: 'grindu_danga', kept: oldRoom.grindu_danga, read: freshRoom.grindu_danga });
    }
    room.grindu_danga = oldRoom.grindu_danga;
    room.grindu_danga_saltinis = oldRoom.grindu_danga_saltinis;
    // `_grindu_danga` (what the floor plan draws there) stays as the fresh read gave it:
    // the check sheet shows his choice AND says when the drawing differs.
  }
  if (oldRoom._prideta_is_plano) room._prideta_is_plano = true;
  return { room, carried };
}

const summary = (r) => ({ nr: nrKey(r), pavadinimas: roomName(r), plotas_m2: num(r?.plotas_m2) });

/**
 * Merge the rooms of a fresh read into the stored ones.
 * Returns `{ rooms, diff }` where diff = `{ at, changed, kept, added, removed }`.
 */
export function mergeReextractRooms(oldRooms, newRooms, now = new Date().toISOString()) {
  const olds = (Array.isArray(oldRooms) ? oldRooms : []).filter(isObj);
  const news = (Array.isArray(newRooms) ? newRooms : []).filter(isObj);
  const oldByNr = new Map();
  for (const r of olds) {
    const k = nrKey(r);
    if (k && !oldByNr.has(k)) oldByNr.set(k, r);
  }
  const seen = new Set();
  const rooms = [];
  const changed = [];
  const kept = [];
  const added = [];
  for (const fresh of news) {
    const key = nrKey(fresh);
    const old = key ? oldByNr.get(key) : undefined;
    if (!old || seen.has(key)) {
      rooms.push(fresh);
      added.push(summary(fresh));
      continue;
    }
    seen.add(key);
    if (isRoomVerified(old)) {
      // He confirmed these facts; the new read does not get to move them.
      const wouldChange = factDiff(old, fresh);
      rooms.push({ ...old, _reread_seen_at: now });
      if (wouldChange.length) {
        kept.push({
          nr: key, pavadinimas: roomName(old), why: 'verified',
          fields: wouldChange.map((d) => ({ key: d.key, kept: d.from, read: d.to })),
        });
      }
      continue;
    }
    const { room, carried } = carryUserFacts(old, fresh);
    rooms.push(room);
    if (carried.length) kept.push({ nr: key, pavadinimas: roomName(old), why: 'user', fields: carried });
    const diffs = factDiff(old, room);
    if (diffs.length) changed.push({ nr: key, pavadinimas: roomName(room) || roomName(old), fields: diffs });
  }
  const removed = [];
  for (const old of olds) {
    const key = nrKey(old);
    if (key && seen.has(key)) continue;
    if (roomTouched(old)) {
      rooms.push({ ...old, _reread_missing_at: now });
      kept.push({ nr: key, pavadinimas: roomName(old), why: 'missing', fields: [] });
    } else {
      removed.push(summary(old));
    }
  }
  return { rooms, diff: { at: now, changed, kept, added, removed } };
}

/**
 * What the last re-read did to ONE room — for the check sheet's header.
 * Returns `{ changed: [{key, from, to}], kept: {why, fields} | null }` or
 * null when the diff does not mention the room.
 */
export function rereadEntriesFor(diff, roomNr) {
  if (!isObj(diff)) return null;
  const key = roomNr == null ? '' : String(roomNr).trim();
  if (!key) return null;
  const changed = (diff.changed || []).find((c) => String(c?.nr) === key)?.fields || [];
  const kept = (diff.kept || []).find((k) => String(k?.nr) === key) || null;
  if (!changed.length && !kept) return null;
  return { changed, kept: kept ? { why: kept.why, fields: kept.fields || [] } : null };
}

/** True when the diff has anything a person should look at. */
export function rereadDiffIsEmpty(diff) {
  if (!isObj(diff)) return true;
  return !(diff.changed?.length || diff.kept?.length || diff.added?.length || diff.removed?.length);
}

/**
 * The stored project after a fresh read: rooms merged by the rules above,
 * rows merged for prices and manual quantities, the contractor's project-level
 * choices kept, and the diff recorded on the project. Pure.
 */
export function mergeReextract(base, result, now = new Date().toISOString()) {
  const prev = isObj(base) ? base : {};
  const fresh = isObj(result) ? result : {};
  const { rooms, diff } = mergeReextractRooms(prev.patalpos, fresh.patalpos, now);
  const notes = [];
  const project = {
    ...prev,
    ...fresh,
    name: prev.name,
    company_name: prev.company_name,
    vat_rate: prev.vat_rate,
    patalpos: rooms,
    v8_rooms: rooms,
    _overrides: prev._overrides ?? fresh._overrides,
    _apimtis: prev._apimtis ?? fresh._apimtis,
    _per_room_overrides: prev._per_room_overrides ?? fresh._per_room_overrides,
    darbu_sarasas: mergeDarbuSarasasEdits(fresh.darbu_sarasas, prev.darbu_sarasas, notes),
    _reextracted_at: now,
    _reread_diff: diff,
  };
  return { project, diff, notes };
}

export default mergeReextract;

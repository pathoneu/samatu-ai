/**
 * openingCounts — a room's doors and windows set to a NUMBER he typed on the question card (2026-10-19).
 *
 * Founder, on the first v3 walk: „Čia kur patikra, negaliu iškart vietoje pataisyti to, ką reikia. Negerai." The
 * question „Durys ir langai: patikrinkite 2 patalpas" sent him to the room sheet. Now each room on the card has
 * the list's number and the walls' number (backend/extractor/project_questions `_opening_numbers`) and a field per
 * kind pre-filled with the walls' number; this file turns the number into the room's `elementai` — the same list
 * the room sheet's stepper edits (lib/roomSheet adjustOpeningCount / addOpening), saved down the same path.
 *
 * The walls pass's own marks decide which units go first (universal_rules.reconcile_openings_with_walls):
 *   • a unit an opening backs is kept first (a door without `_be_angos`; a window's units up to its `_anga_ks`);
 *   • then the openings the walls show free of that kind (`laisvos` — the ones held back from the one-click list,
 *     most likely the listed units at another width) get a unit each, at the drawn width (to the nearest 10 cm,
 *     as the one-click offers) and the height of the listed unit it replaces;
 *   • then the listed units no opening backs, in list order;
 *   • then standard sizes (the room sheet's „+ Durys" / „+ Langas").
 * Fewer than the openings back: the last units go first. A removed unit an opening backed stays on its element
 * at a lower `kiekis` (the engine then keeps that opening empty — `_hold_removed_openings`); a removed unit no
 * opening backed simply goes. Nothing here invents a size: a width is the drawn one, the listed one or the
 * standard one the engine assumes. Pure.
 */
import { STANDARD_OPENINGS, addOpening } from './roomSheet.js';
import { ltNumber } from './ledger.js';

const DOOR_TIPAI = new Set(['duris', 'pasleptos_duris']);

/** A missing count is one unit (as the engine reads it), an explicit 0 stays 0. */
function units(el) {
  const k = el?.kiekis;
  if (typeof k === 'number' && k === 0) return 0;
  const n = Math.round(Number(k));
  return Number.isFinite(n) && n > 0 ? n : 1;
}

const ofKind = (kind) => (el) => (kind === 'durys'
  ? DOOR_TIPAI.has(String(el?.tipas ?? '')) && !el?._praejimas
  : String(el?.tipas ?? '') === 'langas');

/** Did the walls pass stand this room's units (any of its marks on an element)? */
function wallsStood(list) {
  return list.some((el) => Boolean(el && ((Array.isArray(el._anga_ks) && el._anga_ks.length > 0) || el._be_angos || el._praejimas)));
}

/** How many of an element's units an opening backs. */
function backedUnits(el, kind, stood) {
  const n = units(el);
  if (!stood) return n;
  if (kind === 'durys') return el?._be_angos ? 0 : n;
  return Math.min(n, Array.isArray(el?._anga_ks) ? el._anga_ks.length : 0);
}

/**
 * `elementai` with `kind` ('durys' | 'langai') set to `target` units. `free` — the walls' free openings of that
 * kind ({plotis_m, i}). → {elementai, removed: [{plotis_mm}], added: [{plotis_mm, from: 'walls' | 'standard'}],
 * changed}; `changed` false when the list stays as it was.
 */
export function setOpeningCount(elementai, kind, target, free = []) {
  const list = Array.isArray(elementai) ? elementai : [];
  const want = Math.max(0, Math.round(Number(target)));
  if (!Number.isFinite(want)) return { elementai: list, removed: [], added: [], changed: false };
  const stood = wallsStood(list);
  const mine = ofKind(kind);
  const idx = list.map((el, i) => (el && mine(el) ? i : -1)).filter((i) => i >= 0);
  const backed = Object.fromEntries(idx.map((i) => [i, backedUnits(list[i], kind, stood)]));
  const loose = Object.fromEntries(idx.map((i) => [i, units(list[i]) - backed[i]]));
  const keep = { ...backed };
  const totalBacked = idx.reduce((s, i) => s + backed[i], 0);
  const freeList = (Array.isArray(free) ? free : []).filter((o) => Number(o?.plotis_m) > 0);

  let left = want - totalBacked;
  // fewer than the openings back: the last units go first
  for (let n = idx.length - 1; n >= 0 && left < 0; n -= 1) {
    const i = idx[n];
    const off = Math.min(keep[i], -left);
    keep[i] -= off;
    left += off;
  }
  // the free openings, each taking the height of a listed unit no opening backs (the same unit, another width)
  const looseHeights = idx.flatMap((i) => Array(Math.max(0, loose[i])).fill(Number(list[i]?.aukstis_mm) || null));
  const fromWalls = [];
  for (const o of freeList) {
    if (left <= 0) break;
    const std = kind === 'durys' ? STANDARD_OPENINGS.duris : STANDARD_OPENINGS.langas;
    const h = looseHeights.shift() || std.aukstis_mm;
    fromWalls.push({
      tipas: kind === 'durys' ? 'duris' : 'langas', kiekis: 1, plotis_mm: Math.round(Number(o.plotis_m) * 10) * 100,
      aukstis_mm: h, _dydis_user: true, ...(o.i ? { _is_sienu_angos: String(o.i) } : {}),
    });
    left -= 1;
  }
  // then the listed units no opening backs, in list order
  for (const i of idx) {
    if (left <= 0) break;
    const back = Math.min(loose[i], left);
    keep[i] += back;
    left -= back;
  }

  const removed = [];
  let next = [];
  list.forEach((el, i) => {
    if (!(i in keep)) { next.push(el); return; }
    const was = units(el);
    const now = keep[i];
    for (let k = now; k < was; k += 1) removed.push({ plotis_mm: Number(el.plotis_mm) || null, backed: k < backed[i] });
    if (now === was) { next.push(el); return; }
    // a unit an opening backed stays on its element at the lower count (the engine keeps that opening empty);
    // an element left with no backed unit and nothing kept goes
    if (now === 0 && backed[i] === 0) return;
    next.push({ ...el, kiekis: now });
  });
  next = [...next, ...fromWalls];
  const added = fromWalls.map((el) => ({ plotis_mm: el.plotis_mm, from: 'walls' }));
  const std = kind === 'durys' ? STANDARD_OPENINGS.duris : STANDARD_OPENINGS.langas;
  for (; left > 0; left -= 1) {
    next = addOpening(next, std);
    added.push({ plotis_mm: std.plotis_mm, from: 'standard' });
  }
  return { elementai: next, removed, added, changed: removed.length > 0 || added.length > 0 };
}

/** Both kinds at once: `target` {durys, langai}, `row` the question's room row (its `durys` / `langai`). */
export function setRoomOpeningCounts(elementai, target, row = {}) {
  let list = Array.isArray(elementai) ? elementai : [];
  const out = { durys: null, langai: null };
  for (const kind of ['durys', 'langai']) {
    const n = target?.[kind];
    if (n === undefined || n === null || n === '') continue;
    const r = setOpeningCount(list, kind, n, row?.[kind]?.laisvos || []);
    list = r.elementai;
    out[kind] = r;
  }
  return { elementai: list, ...out, changed: Boolean(out.durys?.changed || out.langai?.changed) };
}

const m = (mm) => ltNumber(Number(mm) / 1000, 2);
const doorWord = (n) => (n % 10 === 0 || (n % 100 >= 11 && n % 100 <= 19) ? 'durų' : 'duris');
const windowWord = (n) => (n % 10 === 1 && n % 100 !== 11 ? 'langą' : n % 10 >= 2 && n % 10 <= 9 && !(n % 100 >= 12 && n % 100 <= 19) ? 'langus' : 'langų');

/**
 * What „Tinka" will do to one kind, in one plain line for under the field — „Išimsiu 3 duris (1,00, 0,90 ir 0,90 m)
 * — jų angų sienose nėra." / „Pridėsiu 1 duris 0,90 m — standartinio dydžio." / „Sąrašas nesikeis." (`r` from
 * setOpeningCount, `kind` 'durys' | 'langai'.)
 */
export function countChangeText(r, kind) {
  if (!r || !r.changed) return 'Sąrašas nesikeis.';
  const word = kind === 'durys' ? doorWord : windowWord;
  const widths = (xs) => {
    const ws = xs.map((x) => (x.plotis_mm ? `${m(x.plotis_mm)}` : null)).filter(Boolean);
    if (!ws.length) return '';
    return ` (${ws.length > 1 ? `${ws.slice(0, -1).join(', ')} ir ${ws[ws.length - 1]}` : ws[0]} m)`;
  };
  const parts = [];
  const walls = r.added.filter((a) => a.from === 'walls');
  const std = r.added.filter((a) => a.from === 'standard');
  if (r.removed.length && walls.length) {
    parts.push(kind === 'durys'
      ? `Durys${widths(r.removed)} bus pakeistos nubraižytomis${widths(walls)}.`
      : `Langai${widths(r.removed)} bus pakeisti nubraižytais${widths(walls)}.`);
  } else {
    if (r.removed.length) {
      const why = r.removed.every((x) => !x.backed) ? ' — jų angų sienose nėra' : '';
      parts.push(`Išimsiu ${r.removed.length} ${word(r.removed.length)}${widths(r.removed)}${why}.`);
    }
    if (walls.length) parts.push(`Pridėsiu ${walls.length} ${word(walls.length)}${widths(walls)} — pagal angas sienose.`);
  }
  if (std.length) parts.push(`Pridėsiu ${std.length} ${word(std.length)}${widths(std)} — standartinio dydžio.`);
  return parts.join(' ');
}

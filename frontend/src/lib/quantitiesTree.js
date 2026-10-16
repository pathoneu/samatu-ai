/**
 * quantitiesTree — the Kiekiai panel's tree (Togal's Quantities Panel on Pathon's data, capability B
 * of docs/superpowers/plans/2026-10-16-togal-v2-program.md).
 *
 *   SECTION (row.skyrius, server order)
 *     └ FAMILY (one darbu_sarasas row: its kiekis, unit, confidence)
 *         └ ROOM (one entry of row.contributions[], the server's own per-room share)
 *
 * A Togal "classification" is one quantity with one unit, so the family here is the sąmata LINE, not the
 * skyrius: „Sienų glaistymas dažymas" holds m² of paint, m of corners and m of baseboards, and no total
 * of the section would mean anything. The skyrius is the folder the lines sit in.
 *
 * Rules (lib/ledger.js says why): every number shown is the server's. The family total is `kiekis`,
 * never Σ contributions; when the ledger says the contributions do not add up to it (an anchor, a cap)
 * the family carries the roll_up line that explains the difference. The only additions in this module
 * are the footer's per-unit Σ over the DISPLAYED lines' `kiekis` — a sum of server numbers, labelled as
 * such in the UI — and never a sum of contributions.
 *
 * Pure: rows + rooms + view options in, plain objects out. Covered by quantitiesTree.test.js.
 */

import {
  anchorNote, contributionsOf, excludedOf, hasLedger, isManualRow, rollUpHeadline,
  rollUpIsAuthoritative, sourceLabel, unitLabel,
} from './ledger.js';
import { normalizeConfidence } from './confidence.js';

export const SORT_ORDER = 'order';      // the server's line order, rooms in plan order
export const SORT_ALPHA = 'alpha';      // A–Ž by name
export const SORT_QUANTITY = 'quantity'; // biggest first
export const SORT_MODES = [SORT_ORDER, SORT_ALPHA, SORT_QUANTITY];

const OTHER_SECTION = 'Kiti darbai';

// Outline sources a person drew or fixed (lib/mergeReextract.js USER_POLYGON_SOURCES) and the ones the
// geometry lane traced from the wall lines of a vector PDF. Anything else that still has a polygon
// (browser flood-fill, a bbox) is approximate.
const USER_SOURCES = new Set(['corrected', 'manual']);
const WALL_SOURCES = new Set(['vektoriniai_konturai', 'sienu_konturas']);

/** Where a room's outline came from, in the contractor's words. */
export function geometrySource(room, contribution = null) {
  const src = String(room?.polygon_source || '');
  const hasPolygon = Array.isArray(room?.polygon_pct) && room.polygon_pct.length >= 3;
  if (USER_SOURCES.has(src) && hasPolygon) return { kind: 'user', label: 'pataisytas jūsų' };
  if (WALL_SOURCES.has(src) && hasPolygon) return { kind: 'walls', label: 'kontūras iš sienų' };
  if (hasPolygon) return { kind: 'approx', label: 'apytikslis' };
  const geometry = contribution?.geometry;
  if (geometry === 'marker' || room?.marker_pct) return { kind: 'marker', label: 'tik numeris brėžinyje' };
  return { kind: 'none', label: 'be kontūro' };
}

/** Lower-case, no Lithuanian diacritics: „dazymas" finds „Dažymas". */
export function foldText(value) {
  return String(value ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
}

function rowKey(row, index) {
  const id = row?.id || row?._id;
  return id ? `${id}#${index}` : `row-${index}-${row?.eil_nr ?? ''}`;
}

function numberOr(value, fallback) {
  const n = Number(value);
  return value != null && value !== '' && Number.isFinite(n) ? n : fallback;
}

function compareText(a, b) {
  return String(a || '').localeCompare(String(b || ''), 'lt', { numeric: true, sensitivity: 'base' });
}

function roomEntry(contribution, roomsByNr, roomOrder, familyUnit, hidden) {
  const nr = contribution?.room_nr != null ? String(contribution.room_nr) : '';
  const room = roomsByNr.get(nr) || null;
  return {
    key: `room-${nr}`,
    nr,
    name: contribution?.room_name || room?.pavadinimas || '',
    value: numberOr(contribution?.value, null),
    unit: unitLabel(contribution?.unit) || familyUnit,
    page: contribution?.page ?? room?.puslapio_nr ?? null,
    includedBecause: contribution?.included_because || null,
    source: geometrySource(room, contribution),
    hidden: hidden.has(nr),
    order: roomOrder.has(nr) ? roomOrder.get(nr) : Number.MAX_SAFE_INTEGER,
    room,
  };
}

function familyEntry(row, index, roomsByNr, roomOrder, hidden) {
  const unit = unitLabel(row?.mato_vnt || row?.vnt);
  const rollUp = Array.isArray(row?.roll_up) ? row.roll_up : [];
  const contributions = contributionsOf(row);
  const authoritative = contributions.length > 0 && rollUpIsAuthoritative(rollUp, row);
  return {
    key: rowKey(row, index),
    id: row?.id || null,
    index,
    label: row?.aprasymas || row?.pavadinimas || '',
    section: row?.skyrius || row?.kategorija || OTHER_SECTION,
    total: numberOr(row?.kiekis, null),
    unit,
    confidence: normalizeConfidence(row?.confidence),
    confidenceReason: row?._confidence_reason || null,
    manual: isManualRow(row),
    // The user typed this line's quantity over the program's (lib/quantityOverride.js): the rooms below
    // are what the program computed, not a split of the typed number.
    overridden: row?.manual_override === true,
    programTotal: row?.manual_override === true ? numberOr(row?.ai_kiekis_original, null) : null,
    hasLedger: hasLedger(row),
    // The chain is the number: the rooms below are supporting detail, not an addition to check.
    rollUpAuthoritative: authoritative,
    rollUpLine: authoritative ? rollUpHeadline(rollUp, unit) : null,
    rollUpNote: authoritative ? (anchorNote(rollUp) || rollUp.find((s) => s?.note)?.note || null) : null,
    sourceLabel: sourceLabel(row?.saltinis),
    rooms: contributions.map((c) => roomEntry(c, roomsByNr, roomOrder, unit, hidden)),
    excluded: excludedOf(row).map((e) => ({
      nr: e?.room_nr != null ? String(e.room_nr) : '',
      name: e?.room_name || '',
      because: e?.excluded_because || null,
    })),
    row,
  };
}

function sortRooms(rooms, sort) {
  const list = [...rooms];
  if (sort === SORT_ALPHA) list.sort((a, b) => compareText(a.name, b.name) || compareText(a.nr, b.nr));
  else if (sort === SORT_QUANTITY) list.sort((a, b) => (b.value ?? -Infinity) - (a.value ?? -Infinity));
  else list.sort((a, b) => (a.order - b.order) || compareText(a.nr, b.nr));
  return list;
}

function sortFamilies(families, sort) {
  const list = [...families];
  if (sort === SORT_ALPHA) list.sort((a, b) => compareText(a.label, b.label));
  else if (sort === SORT_QUANTITY) list.sort((a, b) => (b.total ?? -Infinity) - (a.total ?? -Infinity));
  else list.sort((a, b) => a.index - b.index);
  return list;
}

/**
 * Keep a family when the query names its line or its section (all its rooms stay), or when it names one
 * of its rooms by number or name (only those rooms stay). `matchedBy` tells the UI which happened.
 */
function filterFamily(family, query) {
  if (!query) return { ...family, matchedBy: null };
  if (foldText(family.label).includes(query) || foldText(family.section).includes(query)) {
    return { ...family, matchedBy: 'family' };
  }
  const rooms = family.rooms.filter((r) => foldText(r.nr) === query
    || foldText(r.name).includes(query) || foldText(`${r.nr} ${r.name}`).includes(query));
  return rooms.length > 0 ? { ...family, rooms, matchedBy: 'room' } : null;
}

/**
 * Σ of the displayed lines' `kiekis`, per unit, in first-seen order. Lines without a quantity are
 * counted separately so the footer can say „N eilučių be kiekio" instead of silently treating them as 0.
 */
export function totalsByUnit(families) {
  const byUnit = new Map();
  let missing = 0;
  for (const f of families) {
    if (f.total == null) { missing += 1; continue; }
    const unit = f.unit || '—';
    const cur = byUnit.get(unit) || { unit, value: 0, lines: 0 };
    cur.value += f.total;
    cur.lines += 1;
    byUnit.set(unit, cur);
  }
  const units = [...byUnit.values()].map((u) => ({ ...u, value: Math.round(u.value * 100) / 100 }));
  return { units, missing };
}

/**
 * @param {Array<object>} rows   project.darbu_sarasas
 * @param {Array<object>} rooms  project.v8_rooms || project.patalpos (plan order)
 * @param {{filter?: string, sort?: string, hiddenRoomNrs?: Iterable}} options
 * @returns {{sections: Array, families: Array, totals: object, familyCount: number}}
 */
export function buildQuantitiesTree(rows, rooms, options = {}) {
  const { filter = '', sort = SORT_ORDER, hiddenRoomNrs = null } = options;
  const hidden = new Set(Array.from(hiddenRoomNrs || []).map(String));
  const roomList = Array.isArray(rooms) ? rooms.filter(Boolean) : [];
  const roomsByNr = new Map(roomList.map((r) => [String(r.nr), r]));
  const roomOrder = new Map(roomList.map((r, i) => [String(r.nr), i]));
  const query = foldText(filter);

  const all = (Array.isArray(rows) ? rows : [])
    .map((row, i) => (row ? familyEntry(row, i, roomsByNr, roomOrder, hidden) : null))
    .filter(Boolean);

  const sectionOrder = [];
  const bySection = new Map();
  for (const fam of all) {
    const kept = filterFamily(fam, query);
    if (!kept) continue;
    if (!bySection.has(kept.section)) { bySection.set(kept.section, []); sectionOrder.push(kept.section); }
    bySection.get(kept.section).push({ ...kept, rooms: sortRooms(kept.rooms, sort) });
  }

  const sections = sectionOrder.map((label) => {
    const families = sortFamilies(bySection.get(label), sort);
    return { key: `section-${label}`, label, families };
  });
  const families = sections.flatMap((s) => s.families);
  return { sections, families, totals: totalsByUnit(families), familyCount: all.length };
}

/**
 * The rows the keyboard walks, top to bottom, honouring which sections and families are open.
 * Each item is {key, kind: 'section'|'family'|'room', familyKey?, room?}.
 */
export function visibleRowKeys(tree, { collapsedSections = new Set(), expandedFamilies = new Set() } = {}) {
  const out = [];
  for (const section of tree?.sections || []) {
    out.push({ key: section.key, kind: 'section' });
    if (collapsedSections.has(section.key)) continue;
    for (const fam of section.families) {
      out.push({ key: fam.key, kind: 'family' });
      if (!expandedFamilies.has(fam.key)) continue;
      for (const room of fam.rooms) {
        out.push({ key: `${fam.key}/${room.key}`, kind: 'room', familyKey: fam.key, nr: room.nr });
      }
    }
  }
  return out;
}

/** The families a room contributes to — the panel's half of the sheet → panel highlight. */
export function familiesWithRoom(tree, roomNr) {
  if (roomNr == null) return [];
  const nr = String(roomNr);
  return (tree?.families || []).filter((f) => f.rooms.some((r) => r.nr === nr)).map((f) => f.key);
}

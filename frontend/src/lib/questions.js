/**
 * Patikra as a short list of QUESTIONS for the whole project (2026-09-21) — the pure half.
 *
 * Founder, after walking a real project on the room sheet: „viskas pasižymi labai gerai ir tiksliai… bet per
 * daug veiksmų visokių būtų rangovui". The server groups everything that still waits for a person into a few
 * questions, each with the program's own proposal (backend/extractor/project_questions.py). This file is what
 * the screen needs around that list: which question is open next, and what an ANSWER turns into on the project.
 *
 * „Programa siūlo — jūs patvirtinate": with nothing typed, an answer is the proposal of every item. Answers go
 * down the very write paths the room sheet uses (lib/roomSheetApi: `saveAssumptionEdit` for the per-room tables,
 * `saveRoomEdit` for the rooms) — these functions only build what is sent, and never mutate the project.
 */

import { addOpening, alreadyInUse, heightsForRooms, openingsPatch, userEditPatch } from './roomSheet.js';
import { setRoomOpeningCounts } from './openingCounts.js';
import { ltNumber } from './ledger.js';

const nrOf = (item) => String(item?.room_nr ?? '');
const roomsOf = (project) => (project?.v8_rooms?.length ? project.v8_rooms : (project?.patalpos || []));
const validAmount = (v) => Number.isFinite(Number(v)) && Number(v) > 0;

/**
 * The question to open next: the first that is not skipped — looking AFTER `afterId` first (he moves down the
 * list), then from the top. An answered question is simply gone from `questions` (the list is rebuilt after
 * every answer). `null` when nothing is open.
 */
export function nextOpenQuestion(questions, skipped, afterId = null) {
  const list = Array.isArray(questions) ? questions : [];
  const open = (q) => !skipped?.has?.(q.id);
  const at = afterId == null ? -1 : list.findIndex((q) => q.id === afterId);
  return list.slice(at + 1).find(open) || list.slice(0, Math.max(at, 0) + 1).find(open) || null;
}

/**
 * Where to stand after an answer. The list was rebuilt: the answered question is usually GONE — then the one that
 * slid into its place is next (he moves down the list), else the first still open. A question that is still
 * there (more rooms to point at) stays in front of him.
 */
export function questionAfterAnswer(questions, skipped, answeredId, answeredIndex = 0) {
  const list = Array.isArray(questions) ? questions : [];
  const open = (q) => !skipped?.has?.(q.id);
  const same = list.find((q) => q.id === answeredId);
  if (same && open(same)) return same;
  return list.slice(Math.max(0, answeredIndex)).find(open) || list.find(open) || null;
}

/** Counts for the header: still open, skipped (and still there), answered in this sitting. */
export function progressOf(questions, skipped, answeredCount = 0) {
  const list = Array.isArray(questions) ? questions : [];
  const skippedHere = list.filter((q) => skipped?.has?.(q.id)).length;
  const answered = Number(answeredCount) || 0;
  return { open: list.length - skippedHere, skipped: skippedHere, answered, total: list.length + answered };
}

/**
 * One height for every room that asked (`perRoom`: the rooms he typed separately). → the `lubu_auksciai` table
 * for `saveAssumptionEdit`, or null when there is no number to send.
 */
export function heightAnswer(project, items, value, perRoom = null) {
  const list = (Array.isArray(items) ? items : []).filter((i) => nrOf(i));
  if (!list.length || !validAmount(value)) return null;
  const own = perRoom && typeof perRoom === 'object' ? perRoom : {};
  const valueFor = (nr) => (validAmount(own[nr]) ? Number(own[nr]) : Number(value));
  let table = heightsForRooms(project, [], value);
  for (const item of list) table = { ...table, [nrOf(item)]: valueFor(nrOf(item)) };
  return {
    table,
    touched: list.map(nrOf),
    value: Number(value),
    sameValue: list.every((i) => alreadyInUse(project, [nrOf(i)], 'lubu_auksciai', valueFor(nrOf(i)))),
  };
}

function patchedRooms(project, patches) {
  return roomsOf(project).map((r) => (patches[String(r?.nr)] ? { ...r, ...patches[String(r.nr)] } : r));
}

/**
 * Numbers per room (perimeters, areas): each item's proposal, or what he typed for it (`values[nr]`). An item
 * with neither is left alone. → `{rooms, touched, sameValue}` for `saveRoomEdit`, or null when nothing is sent.
 */
export function numbersAnswer(project, items, values = {}) {
  const patches = {};
  let same = true;
  for (const item of Array.isArray(items) ? items : []) {
    const nr = nrOf(item);
    const typed = values?.[nr];
    const value = typed !== undefined && typed !== null && typed !== '' ? Number(typed) : Number(item?.proposed);
    if (!nr || !item?.field || !validAmount(value)) continue;
    patches[nr] = userEditPatch(item.field, value);
    same = same && alreadyInUse(project, [nr], item.field, value);
  }
  const touched = Object.keys(patches);
  if (!touched.length) return null;
  return { rooms: patchedRooms(project, patches), touched, sameValue: same };
}

/** Floor coverings per room: the proposal or his own choice, written as his (`grindu_danga`). */
export function floorAnswer(project, items, values = {}) {
  const patches = {};
  for (const item of Array.isArray(items) ? items : []) {
    const nr = nrOf(item);
    const value = values?.[nr] ?? item?.proposed;
    if (!nr || value == null || value === '') continue;
    patches[nr] = userEditPatch('grindu_danga', value);
  }
  const touched = Object.keys(patches);
  return touched.length ? { rooms: patchedRooms(project, patches), touched } : null;
}

/** Painted or not, per room → the `walls_paint_override` table for `saveAssumptionEdit`. */
export function wallsAnswer(project, items, values = {}) {
  const table = { ...((project?._overrides || {}).walls_paint_override || {}) };
  const touched = [];
  for (const item of Array.isArray(items) ? items : []) {
    const nr = nrOf(item);
    const value = values?.[nr] ?? item?.proposed;
    if (!nr || value == null || value === '') continue;
    table[nr] = Number(value);
    touched.push(nr);
  }
  return touched.length ? { table, touched } : null;
}

/** The room key that says he answered its door and window count on the question card (project_questions.py). */
export const CHECKED_OPENINGS_KEY = '_angos_patikrinta_at';

/**
 * The openings he left ticked (`picked[i]` — all of them when nothing was unticked), added to their rooms the
 * way „+ Durys" adds one on the room sheet. `edits[i]` (2026-09-23, the founder: „durys 1,40 pločio nebus
 * tikrai") — the width, height or kind he corrected on that opening, in mm and 'duris' | 'langas'; anything
 * else in it is ignored.
 *
 * `manual` + `counts` (2026-10-19, „negaliu iškart vietoje pataisyti"): the rooms the card asks to check, each
 * with the number of doors and windows he left in its fields (`counts[nr] = {durys, langai}`, the proposal when
 * untouched) — set on the room first (lib/openingCounts), the ticked openings added on top; every such room is
 * marked as checked (`_angos_patikrinta_at`) and its openings as his. → `{rooms, touched, added, edited,
 * counted, sameValue}` for `saveRoomEdit`, or null when nothing is sent.
 */
export function openingsAnswer(project, items, picked, edits = {}, { manual = [], counts = {}, now = new Date().toISOString() } = {}) {
  let edited = 0;
  const list = (Array.isArray(items) ? items : []).map((item, i) => {
    const e = edits && typeof edits === 'object' ? edits[i] : null;
    if (!e || typeof e !== 'object') return item;
    const next = { ...item };
    if (validAmount(e.plotis_mm)) next.plotis_mm = Math.round(Number(e.plotis_mm));
    if (validAmount(e.aukstis_mm)) next.aukstis_mm = Math.round(Number(e.aukstis_mm));
    if (e.tipas === 'duris' || e.tipas === 'langas') next.tipas = e.tipas;
    if (next.plotis_mm !== item.plotis_mm || next.aukstis_mm !== item.aukstis_mm || next.tipas !== item.tipas) edited += 1;
    return next;
  });
  const byRoom = {};
  let added = 0;
  list.forEach((item, i) => {
    if (Array.isArray(picked) && picked[i] === false) return;
    const nr = nrOf(item);
    if (!nr || !item?.tipas) return;
    (byRoom[nr] = byRoom[nr] || []).push(item);
    added += 1;
  });
  const rows = Object.fromEntries((Array.isArray(manual) ? manual : []).filter((m) => nrOf(m)).map((m) => [nrOf(m), m]));
  if (!added && !Object.keys(rows).length) return null;
  const patches = {};
  let changed = false;
  for (const room of roomsOf(project)) {
    const nr = String(room?.nr);
    const mine = byRoom[nr];
    const row = rows[nr];
    if (!mine && !row) continue;
    let elementai = room.elementai || [];
    if (row) {
      const want = { durys: row.proposed?.durys, langai: row.proposed?.langai, ...(counts?.[nr] || {}) };
      const set = setRoomOpeningCounts(elementai, want, row);
      elementai = set.elementai;
      changed = changed || set.changed;
    }
    if (mine) elementai = mine.reduce((acc, opening) => addOpening(acc, opening), elementai);
    patches[nr] = { ...openingsPatch(elementai, now), ...(row ? { [CHECKED_OPENINGS_KEY]: now } : {}) };
  }
  const touched = Object.keys(patches);
  if (!touched.length) return null;
  return {
    rooms: patchedRooms(project, patches), touched, added, edited,
    counted: touched.filter((nr) => rows[nr]), sameValue: !added && !changed,
  };
}

/**
 * Frameless or with casings — ONE choice for every interior door of the project (2026-09-23): the proposal
 * (what the estimate computes with today) or what he picked, → `{value, label, touched: []}` for
 * `saveAssumptionEdit(project, 'vidaus_durys_beapvadines', value)`, or null when the question has no item.
 */
export function doorsAnswer(project, items, values = {}) {
  const item = (Array.isArray(items) ? items : [])[0];
  if (!item) return null;
  const nr = nrOf(item);
  const raw = values?.[nr] ?? item?.proposed;
  if (raw == null || raw === '') return null;
  const value = Number(raw) === 1;
  const label = (item.choices || []).find((c) => Number(c.value) === Number(value))?.label || (value ? 'beapvadinės' : 'su apvadais');
  return { value, label, touched: [], sameValue: Boolean((project?._overrides || {}).vidaus_durys_beapvadines === value) };
}

/**
 * A schedule question (Pathon v3 W3-A kinds, answered since W2-B): `reconcile` (the schedule's count against the
 * openings drawn in the walls) records which one he holds right — `value` 'brezinys' | 'ziniarastis', the estimate
 * itself is not changed by it; `info` (a table's sum against the rooms') records that he saw it ('matyta'). Both
 * land in `_lenteliu_sprendimai[question.id]`, the record the server reads to stop asking. → `{decisions, previous,
 * value, label, touched: [], sameValue}`, or null.
 */
export function tableDecisionAnswer(project, question, value) {
  if (!question?.id || value == null || value === '') return null;
  const own = project?._lenteliu_sprendimai;
  const previous = own && typeof own === 'object' && !Array.isArray(own) ? own : {};
  const label = (question.choices || []).find((c) => String(c.value) === String(value))?.label
    || (question.answer === 'info' ? 'pažymėta, kad matėte' : String(value));
  return {
    decisions: { ...previous, [question.id]: value }, previous, value, label, touched: [],
    sameValue: previous[question.id] === value,
  };
}

const SUMMARY_KEY = {
  aukstis: 'answeredHeight', konturas: 'answeredOutline', erdve: 'answeredSplit', perimetras: 'answeredNumbers',
  plotas: 'answeredNumbers', angos: 'answeredOpenings', durys: 'answeredDoors', grindys: 'answeredChoices',
  apdaila: 'answeredChoices',
  lentele_durys: 'answeredTable', lentele_langai: 'answeredTable', lentele_zymos: 'answeredTable', lentele_apdaila: 'answeredChoices', lentele_suma: 'answeredInfo',
};

/** What was just answered, in one plain sentence for the strip above the next question. */
export function answerSummary(question, answer, t) {
  let key = SUMMARY_KEY[question?.kind] || 'answeredNumbers';
  // the outline question has two more ways to be answered (2026-09-23): „Tinka" on the outline the program
  // proposed, and a wall length typed by hand instead of any click
  if (question?.kind === 'konturas' && answer?.accepted) key = 'answeredOutlineAccepted';
  if (question?.kind === 'konturas' && answer?.typed) key = 'answeredPerimeterTyped';
  if (question?.kind === 'konturas' && answer?.joined) key = 'answeredJoin';
  // the door and window count answered on the card (2026-10-19) — with or without openings added beside it
  if (question?.kind === 'angos' && answer?.counted?.length) key = answer?.added ? 'answeredOpeningsCounted' : 'answeredCounts';
  if (question?.kind === 'angos' && answer?.placed) key = 'answeredOpeningPlaced';
  // `touched` — room NUMBERS; an answer's `rooms` is the rooms array that is sent, never text
  const rooms = (answer?.touched || []).map(String).sort((a, b) => a.localeCompare(b, 'lt', { numeric: true }));
  // the door question answers with a LABEL („beapvadinės" / „su apvadais"), not a number
  const value = question?.kind === 'durys' || question?.kind === 'lentele_durys' || question?.kind === 'lentele_langai' ? (answer?.label || '')
    : Number.isFinite(Number(answer?.value)) && answer?.value !== '' && answer?.value != null
      ? ltNumber(Number(answer.value), 2) : answer?.value;
  return t(`project.questions.${key}`, {
    count: question?.kind === 'angos' ? Number(answer?.added) || 0 : rooms.length,
    rooms: rooms.join(', '),
    value,
  });
}

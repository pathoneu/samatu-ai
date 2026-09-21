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

/**
 * The openings he left ticked (`picked[i]` — all of them when nothing was unticked), added to their rooms the
 * way „+ Durys" adds one on the room sheet. → `{rooms, touched, added}` for `saveRoomEdit`, or null.
 */
export function openingsAnswer(project, items, picked) {
  const list = Array.isArray(items) ? items : [];
  const byRoom = {};
  let added = 0;
  list.forEach((item, i) => {
    if (Array.isArray(picked) && picked[i] === false) return;
    const nr = nrOf(item);
    if (!nr || !item?.tipas) return;
    (byRoom[nr] = byRoom[nr] || []).push(item);
    added += 1;
  });
  if (!added) return null;
  const patches = {};
  for (const room of roomsOf(project)) {
    const mine = byRoom[String(room?.nr)];
    if (!mine) continue;
    const elementai = mine.reduce((acc, opening) => addOpening(acc, opening), room.elementai || []);
    patches[String(room.nr)] = openingsPatch(elementai);
  }
  const touched = Object.keys(patches);
  return touched.length ? { rooms: patchedRooms(project, patches), touched, added } : null;
}

const SUMMARY_KEY = {
  aukstis: 'answeredHeight', konturas: 'answeredOutline', erdve: 'answeredSplit', perimetras: 'answeredNumbers',
  plotas: 'answeredNumbers', angos: 'answeredOpenings', grindys: 'answeredChoices', apdaila: 'answeredChoices',
};

/** What was just answered, in one plain sentence for the strip above the next question. */
export function answerSummary(question, answer, t) {
  const key = SUMMARY_KEY[question?.kind] || 'answeredNumbers';
  // `touched` — room NUMBERS; an answer's `rooms` is the rooms array that is sent, never text
  const rooms = (answer?.touched || []).map(String).sort((a, b) => a.localeCompare(b, 'lt', { numeric: true }));
  return t(`project.questions.${key}`, {
    count: question?.kind === 'angos' ? Number(answer?.added) || 0 : rooms.length,
    rooms: rooms.join(', '),
    value: answer?.value,
  });
}

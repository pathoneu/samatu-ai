/**
 * The „Pokalbis" panel's selection and request (togal-v2 W11, Togal capability J) — pure.
 *
 * What the estimator points at becomes PILLS: the room in focus on the drawing, more rooms clicked from the
 * room chips, and sąmata lines added from the Kiekiai panel. The pills are exactly what the request's
 * `selection: {rooms: [nr], rows: [row id]}` carries, and the server answers with `given` — what the model was
 * really handed — so an answer can show its own pills. Same caps as the server (api/chat_selection.py).
 */

import { rowIdOf } from './learningEvents.js';

export const MAX_ROOMS = 12;
export const MAX_ROWS = 30;
export const MAX_TURNS = 12;
const MAX_CHARS = 4000;

export const EMPTY_SELECTION = Object.freeze({ rooms: [], rows: [], droppedFocus: null });

const str = (v) => (v == null ? '' : String(v));
const roomsOf = (project) => (project?.v8_rooms?.length ? project.v8_rooms : (project?.patalpos || []));

/** Add a room (by nr) — a room already there, or the focused one, is not added twice. */
export function addRoom(sel, nr) {
  const key = str(nr);
  if (!key) return sel;
  const s = sel || EMPTY_SELECTION;
  if (s.rooms.includes(key)) return s;
  return { ...s, rooms: [...s.rooms, key], droppedFocus: s.droppedFocus === key ? null : s.droppedFocus };
}

/** Add a sąmata line by its row (or its id). */
export function addRow(sel, rowOrId) {
  const key = typeof rowOrId === 'object' ? rowIdOf(rowOrId) : str(rowOrId);
  const s = sel || EMPTY_SELECTION;
  if (!key || s.rows.includes(key)) return s;
  return { ...s, rows: [...s.rows, key] };
}

/** Remove a pill. Removing the focused room keeps it out until another room is focused. */
export function removePill(sel, pill, focusedNr = null) {
  const s = sel || EMPTY_SELECTION;
  if (pill?.kind === 'row') return { ...s, rows: s.rows.filter((r) => r !== pill.id) };
  if (pill?.kind === 'room') {
    const rooms = s.rooms.filter((r) => r !== pill.nr);
    return { ...s, rooms, droppedFocus: str(focusedNr) === pill.nr ? pill.nr : s.droppedFocus };
  }
  return s;
}

/** Toggle a room chip. */
export function toggleRoom(sel, nr, focusedNr = null) {
  const s = sel || EMPTY_SELECTION;
  const key = str(nr);
  const inFocus = key && key === str(focusedNr) && s.droppedFocus !== key;
  return s.rooms.includes(key) || inFocus ? removePill(s, { kind: 'room', nr: key }, focusedNr) : addRoom(s, key);
}

/** The room numbers in the selection, the focused room first (unless he removed it). */
export function selectedRoomNrs(sel, focusedNr = null) {
  const s = sel || EMPTY_SELECTION;
  const focus = str(focusedNr);
  const out = focus && s.droppedFocus !== focus ? [focus] : [];
  for (const nr of s.rooms) if (!out.includes(nr)) out.push(nr);
  return out;
}

export function roomLabel(room, nr) {
  const name = str(room?.pavadinimas || room?.name).trim();
  return `Patalpa ${str(room?.nr ?? nr)}${name ? ` · ${name}` : ''}`;
}

export function rowLabel(row) {
  return `Eilutė: ${str(row?.aprasymas || row?.label || '—').trim()}`;
}

/** The pills, in order: rooms (focused first), then lines. `focus: true` on the room in focus. */
export function selectionPills(sel, project, focusedNr = null) {
  const s = sel || EMPTY_SELECTION;
  const rooms = new Map(roomsOf(project).map((r) => [str(r?.nr), r]));
  const rows = new Map((project?.darbu_sarasas || []).map((r) => [rowIdOf(r), r]));
  const focus = str(focusedNr);
  return [
    ...selectedRoomNrs(s, focusedNr).map((nr) => ({
      kind: 'room', key: `room-${nr}`, nr, label: roomLabel(rooms.get(nr), nr), focus: nr === focus,
    })),
    ...s.rows.map((id) => ({ kind: 'row', key: `row-${id}`, id, label: rowLabel(rows.get(id) || { aprasymas: id }) })),
  ];
}

/** `selection` for the request — capped like the server, so the pills never promise more than is sent. */
export function selectionPayload(sel, focusedNr = null) {
  const s = sel || EMPTY_SELECTION;
  return { rooms: selectedRoomNrs(s, focusedNr).slice(0, MAX_ROOMS), rows: s.rows.slice(0, MAX_ROWS) };
}

/**
 * The request body: the last turns (errors left out — the model never saw them) plus the new question,
 * each cut to 4 000 characters like the server does.
 */
export function chatRequest(projectId, history, question, selection) {
  const turns = (Array.isArray(history) ? history : [])
    .filter((m) => !m?.isError && (m?.role === 'user' || m?.role === 'assistant') && str(m?.text).trim())
    .map((m) => ({ role: m.role, content: str(m.text).slice(0, MAX_CHARS) }));
  turns.push({ role: 'user', content: str(question).trim().slice(0, MAX_CHARS) });
  return { project_id: projectId, messages: turns.slice(-MAX_TURNS), selection };
}

/**
 * The pills of what the model was GIVEN (`given` from the server), in the panel's words, and the sentences
 * for what it was not given.
 */
export function givenPills(given) {
  const g = given && typeof given === 'object' ? given : {};
  const pills = [
    ...(g.rooms || []).map((r) => ({ kind: 'room', key: `room-${r.nr}`, label: roomLabel(r, r.nr) })),
    ...(g.rows || []).map((r) => ({ kind: 'row', key: `row-${r.id}`, label: rowLabel(r) })),
  ];
  const notes = [];
  const leftRooms = g.left_out?.rooms || [];
  const leftRows = g.left_out?.rows || [];
  if (leftRooms.length) notes.push(`Neperduota (daugiau nei ${MAX_ROOMS} patalpų): ${leftRooms.join(', ')}`);
  if (leftRows.length) notes.push(`Neperduota eilučių (daugiau nei ${MAX_ROWS}): ${leftRows.length}`);
  const missing = [...(g.not_found?.rooms || []), ...(g.not_found?.rows || [])];
  if (missing.length) notes.push(`Projekte nerasta: ${missing.join(', ')}`);
  return { pills, notes };
}

/**
 * An answer's text as plain and bold parts: the model marks key numbers with `**…**`; shown as bold, never
 * as asterisks and never as HTML. Unpaired markers stay as they are.
 */
export function answerParts(text) {
  const s = String(text ?? '');
  const pieces = s.split('**');
  if (pieces.length < 3) return [{ text: s, bold: false }];
  // an even count of pieces means the last marker has no partner
  const paired = pieces.length % 2 === 1 ? pieces.length : pieces.length - 1;
  const out = [];
  pieces.forEach((piece, i) => {
    if (i % 2 === 1 && i < paired) out.push({ text: piece, bold: true });
    else if (i % 2 === 1) out.push({ text: `**${piece}`, bold: false });
    else if (piece) out.push({ text: piece, bold: false });
  });
  return out;
}

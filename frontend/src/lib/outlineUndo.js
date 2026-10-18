/**
 * outlineUndo — „Atšaukti" after every outline save (Pathon v3 wave 1, W1-D, D3; audit F5, Rimo principle 5).
 *
 * Outline save, merge, split and subtract used to toast success with no way back except a whole-project
 * version restore. Every saving answer of api/room_outline.py now carries `previous` — each changed room's
 * keys AS STORED before the save (null = absent), the merge keys for „Sujungti", the neighbours' openings.
 * The toast's „Atšaukti" (10 s) PUTs that `previous` back through the same route (restoreOutline); the
 * answer comes back in the forward answer's shape, so `restorePatch` lands it with the very functions the
 * save was landed with, and the sheet recomputes on the usual path.
 *
 * `newerSaves` guards the one way an undo could do harm: undoing an OLDER save of a room after a newer one
 * would throw the newer one away silently. Each save takes a ticket for its rooms; an undo whose rooms were
 * saved again since is refused with a sentence. Pure (the registry is a plain object the host keeps).
 */
import { roomsWithSplit } from './roomOutline.js';
import { mergePrevious, withMergeKeys, withV8 } from './outlineToolSave.js';

export { mergePrevious };

/** The project patch an undo answer lands as (`{patalpos, v8_rooms?}`), or null when it is not an undo. */
export function restorePatch(project, answer) {
  const rooms = roomsWithSplit(project, answer);
  if (!rooms) return null;
  return withV8(project, answer?.sujungimas ? withMergeKeys(rooms, answer.sujungimas) : rooms);
}

/** The rooms an undo changes back (the ones with keys besides a neighbour's openings), for its sentence. */
export function undoneRooms(previous) {
  return Object.entries(previous || {})
    .filter(([, keys]) => keys && typeof keys === 'object' && Object.keys(keys).some((k) => k !== '_angos_sienose'))
    .map(([nr]) => nr)
    .sort((a, b) => a.localeCompare(b, 'lt', { numeric: true }));
}

/** What the undo toast says once it is done. */
export function undoneSentence(action, previous) {
  const rooms = undoneRooms(previous);
  const list = rooms.join(' ir ');
  if (action === 'outline-merge') return `Atšaukta: patalpos ${list} vėl atskiros`;
  if (rooms.length > 1) return `Atšaukta: patalpų ${list} kontūrai grąžinti`;
  return `Atšaukta: patalpos ${list} kontūras grąžintas`;
}

export const UNDO_SUPERSEDED = 'Šią patalpą jau pakeitėte vėliau — pirmiausia atšaukite naujesnį pakeitimą.';

/** A fresh registry of the newest save per room. */
export function newerSaves() {
  return { seq: 0, latest: {} };
}

/** A save of `rooms` happened → its ticket. */
export function ticketFor(registry, rooms) {
  registry.seq += 1;
  const ticket = { seq: registry.seq, rooms: (rooms || []).map(String) };
  for (const nr of ticket.rooms) registry.latest[nr] = ticket.seq;
  return ticket;
}

/** Whether `ticket`'s save is still the newest one of every room it changed. */
export function isNewest(registry, ticket) {
  return Boolean(ticket) && ticket.rooms.every((nr) => registry.latest[nr] === ticket.seq);
}

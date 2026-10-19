// drawingNotes — „Pastaba" pins on the drawing (Pathon v3 W5-C, C11 / coverage #179, #180): a point on a sheet
// with his text, kept with the measurements (kind `note`, the same save path and history), listed in Matavimai,
// printed in „PDF su žymėjimais". No sticker or redline toolset — one pin, one sentence.
//
// The pin tool is armed from Matavimai („+ Pastaba brėžinyje") through the tiny store below, so the viewer's
// own tool routing is not touched; DrawingNoteLayer (mounted per page) owns the click while it is armed.

export const NOTE_KIND = 'note';
export const NOTE_MAX = 500;

let seq = 0;
const newId = () => `note-${Date.now().toString(36)}-${(seq += 1).toString(36)}`;

/** A new note at PDF point (x, y) of sheet `page` (1-based) — the measurement shape, kind `note`. */
export function makeNote({ page, x, y, text, id = null, now = new Date().toISOString() }) {
  return {
    id: id || newId(),
    kind: NOTE_KIND,
    page: Number(page),
    points: [{ x: Number(x), y: Number(y) }],
    text: String(text || '').trim().slice(0, NOTE_MAX),
    source: 'user',
    created_at: now,
  };
}

/** The notes (all, or of one sheet), in the order they were made. */
export function notesOf(measurements, page = null) {
  return (Array.isArray(measurements) ? measurements : [])
    .filter((m) => m?.kind === NOTE_KIND && Array.isArray(m.points) && m.points[0] && (page == null || m.page === page));
}

/** Short text for a label beside the pin; the whole text is in the pop-up, the list and the PDF. */
export function noteLabel(text, max = 40) {
  const s = String(text || '').replace(/\s+/g, ' ').trim();
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/** A note's number on its sheet („P1", „P2") — the same on the drawing, in the list and in the PDF. */
export function noteNumbers(measurements) {
  const out = new Map();
  const perPage = new Map();
  for (const n of notesOf(measurements)) {
    const k = (perPage.get(n.page) || 0) + 1;
    perPage.set(n.page, k);
    out.set(n.id, `P${k}`);
  }
  return out;
}

// ── the arming store (one per window) ─────────────────────────────────────────────────────────────
const listeners = new Set();
let armed = false;

export function noteToolArmed() { return armed; }

export function setNoteToolArmed(on) {
  const next = Boolean(on);
  if (next === armed) return;
  armed = next;
  for (const fn of [...listeners]) fn(armed);
}

export function subscribeNoteTool(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

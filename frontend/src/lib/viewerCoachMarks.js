// First-run walkthrough for the viewer (2026-10-16, Togal analysis §11; v3 B1-E 2026-10-19): ten SHORT
// cards, one at a time, in the order a person meets the screen — the sheet strip, the tool cards, a room
// by click, the room tool R, the scale chip, a measurement, the legend G, then the steps Patikra, Sąmata,
// Siųsti. Each card: a title, ONE sentence (≤ 12 words) that says what to do, at most one key.
// The words live in i18n (`project.coach.<id>.title|body`); this file holds the order and the anchors.
// Shown once per browser and resumable: the card he stopped on is remembered until he finishes or skips.

export const COACH_STORAGE_KEY = 'samatu_viewer_onboarded';
/** The card he reached, so a reload brings him back to the same card. */
export const COACH_STEP_KEY = 'samatu_viewer_onboarded_step';

/**
 * anchor  CSS selector, looked up inside the viewer first, then in the whole page (the four steps sit in
 *         the project frame above the viewer).
 * place   'below' | 'above' | 'right' (beside a column) | 'over' (the drawing itself: the card sits inside
 *         its top edge and the drawing gets no ring).
 * key     a shortcut id from viewerShortcuts (its key is shown under the sentence), or a literal key name.
 */
export const COACH_STEPS = [
  { id: 'sheets', anchor: '[data-testid="sheet-rail"]', place: 'right' },
  { id: 'tools', anchor: '[data-tool-rail]', place: 'right', key: 'openGuide' },
  { id: 'roomClick', anchor: '[data-testid="viewer-canvas"]', place: 'over' },
  { id: 'roomTool', anchor: '[data-coach="room"]', place: 'right', key: 'toolRoom' },
  { id: 'scale', anchor: '[data-testid="scale-chip"]', place: 'above', key: 'toolCalibrate' },
  { id: 'measure', anchor: '[data-coach="distance"]', place: 'right', key: 'toolDistance' },
  { id: 'legend', anchor: '[data-coach="legend"]', place: 'right', key: 'toolLegend' },
  { id: 'patikra', anchor: '[data-testid="step-patikra"]', place: 'below', key: 'Enter' },
  { id: 'samata', anchor: '[data-testid="step-samata"]', place: 'below' },
  { id: 'siusti', anchor: '[data-testid="step-siusti"]', place: 'below' },
];

/** At most this many words in a card's sentence (founder 2026-10-19: more cards, less writing in each). */
export const COACH_MAX_WORDS = 12;

/** Words in a sentence: dashes, dots and quotes are not words. */
export function wordCount(text) {
  return String(text || '').split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;
}

function store(storage) {
  if (storage) return storage;
  try { return typeof localStorage !== 'undefined' ? localStorage : null; } catch { return null; }
}

/** True when the walkthrough was finished or skipped in this browser (or storage is unavailable). */
export function coachMarksDone(storage) {
  try {
    const s = store(storage);
    if (!s) return true;                 // private mode / no storage: never nag on every open
    return s.getItem(COACH_STORAGE_KEY) === '1';
  } catch { return true; }
}

export function markCoachMarksDone(storage) {
  try {
    const s = store(storage);
    s?.setItem(COACH_STORAGE_KEY, '1');
    s?.removeItem?.(COACH_STEP_KEY);
  } catch { /* private mode */ }
}

/** The card to open on: where he stopped last time, else the first. Clamped into the list. */
export function coachStartStep(storage, steps = COACH_STEPS) {
  try {
    const n = Number.parseInt(store(storage)?.getItem(COACH_STEP_KEY), 10);
    return Number.isFinite(n) && n > 0 ? Math.min(n, steps.length - 1) : 0;
  } catch { return 0; }
}

export function saveCoachStep(step, storage) {
  try { store(storage)?.setItem(COACH_STEP_KEY, String(Math.max(0, Math.trunc(Number(step) || 0)))); } catch { /* private mode */ }
}

/**
 * Where the card goes for an anchor rect (viewport px), clamped into the viewport:
 *   'below'  under it, arrow up at its centre      'above'  over it, arrow down at its centre
 *   'right'  beside it (a column of tool cards — a card below would cover the next tools)
 *   'over'   inside its top edge (the drawing: pointing at it from outside would leave the screen)
 * No anchor → centred near the top. Returns { left, top, arrowLeft|null, arrowTop|null, arrowDown }.
 */
export function coachCardPosition(rect, { vw, vh, cardW = 320, cardH = 220, gap = 10, margin = 12, side = 'below' } = {}) {
  const none = { arrowLeft: null, arrowTop: null, arrowDown: false };
  if (!rect) return { ...none, left: Math.max(margin, (vw - cardW) / 2), top: Math.min(96, vh / 4) };
  const clampLeft = (x) => Math.min(Math.max(margin, x), Math.max(margin, vw - cardW - margin));
  const clampTop = (y) => Math.min(Math.max(margin, y), Math.max(margin, vh - cardH - margin));
  if (side === 'right') {
    const right = rect.left + rect.width;
    const left = Math.min(right + gap, Math.max(margin, vw - cardW - margin));
    const top = clampTop(rect.top - 12);
    const mid = rect.top + Math.min(rect.height || 0, 120) / 2;
    return { ...none, left, top, arrowTop: Math.min(Math.max(14, mid - top), cardH - 14) };
  }
  if (side === 'over') {
    const left = clampLeft(rect.left + (rect.width - cardW) / 2);
    return { ...none, left, top: clampTop(rect.top + 24) };
  }
  const centre = rect.left + rect.width / 2;
  const left = clampLeft(centre - cardW / 2);
  const arrowLeft = Math.min(Math.max(14, centre - left), cardW - 14);
  if (side === 'above') {
    return { ...none, left, top: clampTop(rect.top - gap - cardH), arrowLeft, arrowDown: true };
  }
  return { ...none, left, top: clampTop((rect.bottom ?? rect.top + rect.height) + gap), arrowLeft };
}

/** „Rodyti įvadą dar kartą" (Pagalba): the next opened drawing shows the walkthrough again, from card 1. */
export function resetCoachMarks(storage) {
  try {
    const s = store(storage);
    s?.removeItem(COACH_STORAGE_KEY);
    s?.removeItem(COACH_STEP_KEY);
  } catch { /* private mode */ }
}

/**
 * A dialog, drawer or full-screen overlay is open (v3 W7-A M6). The walkthrough
 * sits on the coach layer (z-coach 60, above the modal layer 50) so it can point
 * at toolbar buttons — which means it would cover a dialog. While one is open the
 * card and its ring step aside (same step afterwards) and Esc belongs to the
 * dialog. Radix dialogs / sheets / alert dialogs announce themselves; the app's
 * hand-made overlays are `fixed inset-0` on the modal layer.
 */
export const MODAL_SELECTOR = [
  '[role="dialog"][data-state="open"]',
  '[role="alertdialog"]',
  '[aria-modal="true"]',
  '.fixed.inset-0.z-50',
  '.fixed.inset-0.z-modal',
].join(', ');

export function modalOpen(doc = (typeof document !== 'undefined' ? document : null)) {
  try {
    return !!doc?.querySelector?.(MODAL_SELECTOR);
  } catch {
    return false;
  }
}

/**
 * Headers a walkthrough card must never cover — Patikra's room header (`data-coach-avoid`, 2026-10-24: opened
 * from the viewer at 1440×900 the „Lapai" card, whose sheet rail is not on that screen, sat centred near the
 * top, right over the room's name and its „Kitas" button).
 */
export const COACH_AVOID_SELECTOR = '[data-coach-avoid]';

const overlaps = (a, b) => a.left < b.left + b.width && b.left < a.left + a.width
  && a.top < b.top + b.height && b.top < a.top + a.height;
const usable = (r) => r && r.width > 0 && r.height > 0;

/**
 * The card's place (`pos` from coachCardPosition, size `cardW`×`cardH`) with every `avoid` rect kept clear:
 *   · it covers none → `pos` unchanged;
 *   · it points at an anchor and fits under the lowest header it covers → moved there (arrows dropped — they
 *     would point at nothing);
 *   · otherwise (no anchor on this screen, or no room under the header) → null: the card waits and the same
 *     step comes back when the header is gone. One card at a time either way.
 */
export function coachAvoid(pos, { cardW, cardH, vh, avoid = [], anchored = true, gap = 10, margin = 12 } = {}) {
  if (!pos) return pos;
  const rects = (avoid || []).filter(usable);
  const at = (top) => ({ left: pos.left, top, width: cardW, height: cardH });
  const hit = rects.filter((r) => overlaps(at(pos.top), r));
  if (!hit.length) return pos;
  if (!anchored) return null;
  const top = Math.max(...hit.map((r) => r.top + r.height)) + gap;
  if (top + cardH > vh - margin || rects.some((r) => overlaps(at(top), r))) return null;
  return { ...pos, top, arrowLeft: null, arrowTop: null, arrowDown: false };
}

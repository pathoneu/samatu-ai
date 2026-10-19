// firstUseHints — one sentence the FIRST time a tool or a panel is used (Pathon v3 B1-E, 2026-10-19).
//
// Founder: „more help boxes, less writing in each — explain stuff one by one". Besides the walkthrough,
// each of these says one thing once: beside the pointer for a tool (CursorHint shows it above the mode's
// own sentence), as a small pill at the panel for a panel. Never a banner. It goes away by being USED:
// the first click with that tool, or inside that panel, marks it seen for good in this browser.
// The words live in i18n (`project.firstUse.<id>`); this file holds which ones exist and the memory.

export const FIRST_USE_KEY = 'samatu_first_use_seen';

/** Tool modes with a first-use sentence (CursorHint's `mode`): G, R, X, Kiekis. */
export const FIRST_USE_TOOLS = Object.freeze({ legend: 'legend', room: 'room', subtract: 'subtract', count: 'count' });

/**
 * Panels with a first-use pill: the element it stands at, and where it goes. „Nustatymai" renders its own
 * pill inside the drawer (AssumptionsPanel) with the same memory.
 */
export const FIRST_USE_PANELS = Object.freeze([
  { id: 'matavimai', anchor: '[data-testid="meas-groups"]' },
  { id: 'patikra', anchor: '[data-testid^="question-card-"]' },
]);

export const FIRST_USE_IDS = Object.freeze([...Object.values(FIRST_USE_TOOLS), ...FIRST_USE_PANELS.map((p) => p.id), 'nustatymai']);

function store(storage) {
  if (storage) return storage;
  try { return typeof localStorage !== 'undefined' ? localStorage : null; } catch { return null; }
}

function readSeen(storage) {
  try {
    const raw = store(storage)?.getItem(FIRST_USE_KEY);
    const list = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(list) ? list.map(String) : []);
  } catch { return null; }   // unreadable storage: treat everything as seen — never nag
}

/** True when this hint has been used up (or storage cannot remember it — then it never shows). */
export function firstUseSeen(id, storage) {
  const seen = readSeen(storage);
  return seen == null || !store(storage) || seen.has(String(id));
}

export function markFirstUseSeen(id, storage) {
  try {
    const seen = readSeen(storage) || new Set();
    if (seen.has(String(id))) return;
    seen.add(String(id));
    store(storage)?.setItem(FIRST_USE_KEY, JSON.stringify([...seen]));
  } catch { /* private mode */ }
}

/** The tool hint's id for a CursorHint mode, or null when that mode has none. */
export function firstUseToolFor(mode) {
  return Object.prototype.hasOwnProperty.call(FIRST_USE_TOOLS, mode) ? FIRST_USE_TOOLS[mode] : null;
}

/** „Rodyti įvadą dar kartą" also brings these back. */
export function resetFirstUse(storage) {
  try { store(storage)?.removeItem(FIRST_USE_KEY); } catch { /* private mode */ }
}

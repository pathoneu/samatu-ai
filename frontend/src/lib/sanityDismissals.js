/**
 * Shared store for dismissed sanity warnings.
 *
 * Lives outside SanityWarningsBanner because two surfaces now read it: the
 * banner itself (Kiekiai tab) and the severity pill in the project top bar
 * (visible on every tab, including the Brėžinys landing tab). If only the
 * banner honoured dismissals, the pill would keep shouting "7 įspėjimai"
 * after the user had judged all seven — and a badge you cannot ever clear is
 * a badge people stop reading.
 *
 * Backed by localStorage, capped at the 200 most recent keys. Changes publish
 * a window event so both surfaces re-render together without a shared store.
 */

export const DISMISSED_KEY = 'samatu_sanity_dismissed';
export const DISMISSED_EVENT = 'samatu:sanity-dismissed';
const MAX_KEYS = 200;

export function loadDismissed() {
  try {
    const raw = localStorage.getItem(DISMISSED_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

export function saveDismissed(set) {
  try {
    localStorage.setItem(
      DISMISSED_KEY,
      JSON.stringify(Array.from(set).slice(-MAX_KEYS)),
    );
  } catch { /* quota / private mode — dismissals just don't persist */ }
  try {
    window.dispatchEvent(new CustomEvent(DISMISSED_EVENT));
  } catch { /* no window (tests) */ }
}

/** Subscribe to dismissal changes. Returns an unsubscribe function. */
export function subscribeDismissals(handler) {
  if (typeof window === 'undefined') return () => {};
  window.addEventListener(DISMISSED_EVENT, handler);
  // `storage` fires for the OTHER tabs — keeps two open projects in sync.
  window.addEventListener('storage', handler);
  return () => {
    window.removeEventListener(DISMISSED_EVENT, handler);
    window.removeEventListener('storage', handler);
  };
}

/** Drop the warnings the user has already judged. Pure. */
export function withoutDismissed(warnings, dismissed, keyOf) {
  if (!Array.isArray(warnings)) return [];
  if (!dismissed || dismissed.size === 0) return warnings;
  return warnings.filter((w) => !dismissed.has(keyOf(w)));
}

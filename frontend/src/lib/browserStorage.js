/**
 * window.localStorage, or null when the browser refuses it. Safari with „Block all cookies" THROWS a
 * SecurityError on the mere property read — `readPanelWidth(window.localStorage)` crashed the whole
 * workspace into the error screen (2026-10-19, B1-A). Callers pass the result to helpers that already
 * accept a null storage.
 */
export function browserStorage() {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null;
  }
}

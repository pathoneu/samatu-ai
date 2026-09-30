/**
 * "Someone is signing in" — a one-shot note that survives the Google redirect
 * (2026-09-30).
 *
 * Login and register purge the previous account's cached data themselves. A
 * Google sign-in finishes through a server redirect, so the app only learns of
 * the new session when it restores it on the next page load. The button leaves
 * this note in the tab's sessionStorage before leaving; the restore takes it, and
 * then a cache that carries no owner marker is treated as another account's
 * (see `claimLocalCache` in projectStore). Without the note a restore is a plain
 * reload of the same session.
 *
 * No dependencies on purpose: the sign-in button and the auth layer import it.
 */
const SIGN_IN_HINT_KEY = 'samatu_signin_started';

export function noteSignInStarted() {
  try { sessionStorage.setItem(SIGN_IN_HINT_KEY, '1'); } catch { /* storage blocked */ }
}

/** True once after `noteSignInStarted()`; the note is removed as it is read. */
export function takeSignInHint() {
  try {
    const v = sessionStorage.getItem(SIGN_IN_HINT_KEY);
    sessionStorage.removeItem(SIGN_IN_HINT_KEY);
    return v === '1';
  } catch {
    return false;
  }
}

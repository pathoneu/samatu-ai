/**
 * Where sign-in sends the user back to (2026-10-05).
 *
 * ProtectedRoute (App.jsx) sends a signed-out visitor to /login with the page
 * they asked for in router state — `state.from`, a location. After signing in
 * they return to the WHOLE address: path, query (`?step=samata`,
 * `?kambarys=02`) and hash. Login used to take `from.pathname` alone, so a
 * link to a project step or a Patikra room opened on the project's first
 * screen instead. The Google button sends the same string as `next`, and the
 * backend checks it again (main._safe_next_path).
 *
 * Only an address on this site comes back; anything else is '/'. Pure — no
 * React — so node:test pins it.
 */

// One leading slash, then neither a second slash nor a backslash (a browser
// reads `//host` and `/\host` as another site); printable ASCII only — the
// browser's own address is already percent-encoded, and a tab or newline
// would be dropped by its URL parser.
const SAME_SITE_PATH = /^\/(?![/\\])[\x21-\x7e]*$/;

export function isSameSitePath(path) {
  return typeof path === 'string' && SAME_SITE_PATH.test(path);
}

/** The address to return to after sign-in, read from Login's router state. */
export function returnPathFrom(state) {
  const from = state && typeof state === 'object' ? state.from : null;
  let path = '';
  if (typeof from === 'string') {
    path = from;
  } else if (from && typeof from === 'object') {
    const part = (v) => (typeof v === 'string' ? v : '');
    path = part(from.pathname) + part(from.search) + part(from.hash);
  }
  return isSameSitePath(path) ? path : '/';
}

/** The backend route that starts a Google sign-in and comes back to `next`. */
export function googleSignInPath(next) {
  const target = isSameSitePath(next) ? next : '/';
  return `/api/auth/google?next=${encodeURIComponent(target)}`;
}

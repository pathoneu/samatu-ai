/**
 * userStorage.js — which browser-storage keys belong to the signed-in person
 * and leave with them on logout or a user switch (audit backend-security-15,
 * 2026-10-18). UI preferences (panel widths, the language, the cookie choice,
 * the viewer's eye toggles) stay: they say nothing about anyone's projects.
 *
 * Pure — the caller passes the keys and does the removing.
 */

/** Whole-account caches and their owner markers. */
export const USER_SCOPED_KEYS = Object.freeze([
  'samatu_projects', 'samatu_settings', 'samatu_price_lists',
  'samatu_settings_owner', 'samatu_cache_owner',
  'samatu_server_versions', 'samatu_apimtis_history', 'samatu_error_log',
  'samatu_takeoff_p1',
]);

/** Per-project keys: measurements, export section picks, runs, pending price lists. */
export const USER_SCOPED_PREFIXES = Object.freeze([
  'samatu_takeoff_', 'samatu_export_skyriai_', 'samatu_reread_run:',
  'samatu_kainynas_pending:', 'pathon_free_reread_later_',
]);

export function isUserScopedKey(key) {
  if (typeof key !== 'string') return false;
  return USER_SCOPED_KEYS.includes(key) || USER_SCOPED_PREFIXES.some((p) => key.startsWith(p));
}

/** The keys of `storage` (a Storage-like object) that must go. */
export function userScopedKeysIn(storage) {
  const out = [];
  try {
    for (let i = 0; i < storage.length; i += 1) {
      const k = storage.key(i);
      if (isUserScopedKey(k)) out.push(k);
    }
  } catch { /* storage blocked: nothing to list */ }
  return out;
}

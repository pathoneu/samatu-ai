/**
 * accountApi — deleting the signed-in account (2026-10-05).
 *
 * POST /api/account/delete with the account's email as the confirmation. The
 * server removes every project with its drawing, the company details, price
 * lists and sąmata templates, keeps issued invoices, ends every session and
 * clears this browser's session cookie.
 *
 * What this browser still holds of the account is cleared by the caller:
 * the cached projects, company details, price lists and owner markers through
 * the auth layer's logout (it owns those keys — nothing new is invented here),
 * and the drawings cached in IndexedDB through `forgetCachedDrawings`.
 */

// Explicit .js extension so this module also resolves under plain `node --test`.
import { API_BASE } from './apiBase.js';

/** The confirmation the server accepts: the account's email, in any case,
 *  surrounding spaces ignored. */
export function confirmMatches(typed, email) {
  const want = String(email || '').trim().toLowerCase();
  return want !== '' && String(typed || '').trim().toLowerCase() === want;
}

/**
 * Resolves `{ deleted_projects }`. Throws an Error carrying `status` and, when
 * the server said why in words, `detail` — plain Lithuanian, shown as is. A
 * network failure throws with status 0 and no detail.
 */
export async function deleteAccount(confirm, { fetchImpl } = {}) {
  const doFetch = fetchImpl || ((...args) => globalThis.fetch(...args));
  let res;
  try {
    res = await doFetch(`${API_BASE}/api/account/delete`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: String(confirm || '').trim() }),
    });
  } catch {
    const err = new Error('network');
    err.status = 0;
    err.detail = null;
    throw err;
  }
  let body = null;
  try { body = await res.json(); } catch { body = null; }
  if (!res.ok) {
    const detail = typeof body?.detail === 'string' ? body.detail : null;
    const err = new Error(detail || `HTTP ${res.status}`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return { deleted_projects: Number(body?.deleted_projects) || 0 };
}

/**
 * Drop the drawings this browser cached (IndexedDB) for the given projects.
 * Best-effort: the account is already gone on the server, so a browser
 * without IndexedDB, or one that refuses, changes nothing about that.
 * Returns how many were dropped.
 */
export async function forgetCachedDrawings(projectIds, { deletePdfImpl } = {}) {
  let del = deletePdfImpl;
  if (!del) {
    try {
      ({ deletePdf: del } = await import('./pdfStore.js'));
    } catch {
      return 0;
    }
  }
  let dropped = 0;
  for (const id of new Set(projectIds || [])) {
    if (!id) continue;
    try {
      await del(id);
      dropped += 1;
    } catch { /* one refused drawing must not keep the others */ }
  }
  return dropped;
}

/**
 * assembliesApi — his „rinkiniai" and a row's „sudėtis" (togal-v2 W9).
 *
 * GET/POST/PUT/DELETE /api/assemblies (owner-scoped; the „numatyta" set comes
 * with every list and is read-only) and GET …/rows/{id}/sudetis. Errors carry
 * the server's Lithuanian `detail` when it gave one.
 */

// Explicit .js extension so this module also resolves under plain `node --test`.
import { API_BASE } from './apiBase.js';

async function call(path, { method = 'GET', body, fetchImpl } = {}) {
  const doFetch = fetchImpl || ((...args) => globalThis.fetch(...args));
  const res = await doFetch(`${API_BASE}${path}`, {
    method,
    credentials: 'include',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { data = null; }
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : null;
    const err = new Error(detail || `HTTP ${res.status}`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

let _cache = null;

/** `{ assemblies, kodai }`. Cached for the session; `force` refetches. */
export async function listAssemblies({ force = false, fetchImpl } = {}) {
  if (_cache && !force) return _cache;
  const data = await call('/api/assemblies', { fetchImpl });
  _cache = { assemblies: Array.isArray(data?.assemblies) ? data.assemblies : [], kodai: data?.kodai || {} };
  return _cache;
}

/** The last list fetched, or null — for synchronous readers (export, WorkRow). */
export function cachedAssemblies() {
  return _cache;
}

export async function createAssembly(body, opts = {}) {
  const out = await call('/api/assemblies', { method: 'POST', body, ...opts });
  _cache = null;
  return out;
}

export async function updateAssembly(id, body, opts = {}) {
  const out = await call(`/api/assemblies/${encodeURIComponent(id)}`, { method: 'PUT', body, ...opts });
  _cache = null;
  return out;
}

export async function deleteAssembly(id, opts = {}) {
  const out = await call(`/api/assemblies/${encodeURIComponent(id)}`, { method: 'DELETE', ...opts });
  _cache = null;
  return out;
}

export function getSudetis(projectId, rowId, opts = {}) {
  return call(`/api/projects/${encodeURIComponent(projectId)}/rows/${encodeURIComponent(rowId)}/sudetis`, opts);
}

/** A default copied into his own, editable set: same components, his name. */
export function copyOfDefault(a) {
  return {
    name: `${a?.name || 'Rinkinys'} (mano)`,
    skyrius: a?.skyrius || null,
    taikoma: { aprasymas: a?.taikoma?.aprasymas || '', vnt: a?.taikoma?.vnt || a?.vnt || '', eilutes_id: [] },
    vnt: a?.vnt || null,
    kodas: a?.kodas || null,
    komponentai: (a?.komponentai || []).map((c) => ({
      rusis: c.rusis, pavadinimas: c.pavadinimas, norma: c.norma, vnt: c.vnt,
      atliekos_proc: c.atliekos_proc || 0, kaina: c.kaina ?? null,
      apvalinimas: c.apvalinimas ?? null, minimumas: c.minimumas ?? null,
    })),
  };
}

/**
 * pageGeometryApi — GET /api/projects/{id}/pages/{page}/geometry (api/page_geometry.py): the sheet's wall
 * solid as rings in display-frame page fractions. One request per (project, page) per session: pages are
 * mounted and unmounted by the scroll virtualization, and the geometry of a sheet does not change.
 */
import { API_BASE } from './apiBase';

const cache = new Map();   // `${projectId}:${page}` → Promise<geometry>

export function fetchPageGeometry(projectId, page) {
  const key = `${projectId}:${page}`;
  if (!cache.has(key)) {
    const p = fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/pages/${Number(page)}/geometry`,
      { credentials: 'include', signal: AbortSignal.timeout(60_000) },
    ).then(async (res) => {
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
        err.status = res.status;
        throw err;
      }
      return body;
    }).catch((e) => { cache.delete(key); throw e; });   // a failure is retried on the next ask
    cache.set(key, p);
  }
  return cache.get(key);
}

/** Forget a project's sheets (a re-uploaded PDF). */
export function clearPageGeometryCache(projectId) {
  const prefix = `${projectId}:`;
  for (const key of [...cache.keys()]) if (key.startsWith(prefix)) cache.delete(key);
}

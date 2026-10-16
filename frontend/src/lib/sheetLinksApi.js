/**
 * sheetLinksApi — GET /api/projects/{id}/pages/{page}/callouts (api/sheet_links.py): the spans on a
 * sheet that refer to other sheets, with page-fraction boxes and the target page. One request per
 * (project, page, overrides version) per session: pages mount and unmount with the scroll
 * virtualization, and the links only change when the user renames or retypes a sheet.
 */
import { API_BASE } from './apiBase';

const cache = new Map();   // `${projectId}:${version}:${page}` → Promise<{page, callouts}>

export function fetchPageCallouts(projectId, page, version = '') {
  const key = `${projectId}:${version}:${page}`;
  if (!cache.has(key)) {
    const p = fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/pages/${Number(page)}/callouts`,
      { credentials: 'include', signal: AbortSignal.timeout(60_000) },
    ).then(async (res) => {
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const err = new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
        err.status = res.status;
        throw err;
      }
      return body;
    }).catch((e) => { cache.delete(key); throw e; });   // a failure (429, offline) is retried on the next ask
    cache.set(key, p);
  }
  return cache.get(key);
}

/** Forget a project's links (a re-uploaded PDF). */
export function clearPageCalloutsCache(projectId) {
  const prefix = `${projectId}:`;
  for (const key of [...cache.keys()]) if (key.startsWith(prefix)) cache.delete(key);
}

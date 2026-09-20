/**
 * roomOutlineApi — the network half of „Parodyti patalpą" (see lib/roomOutline.js).
 * The server reads the drawing and saves nothing; a click that may not become an
 * outline comes back as a normal answer with its `status`, not as an error.
 */

import { API_BASE } from '@/lib/apiBase';

/** `{status: 'ok', room, kitu_angos}` | `{status: 'taken'|'open'|'outside'|'no_walls', …}` */
export async function fetchOutlineAt(projectId, roomNr, point, { signal } = {}) {
  const res = await fetch(
    `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/rooms/${encodeURIComponent(roomNr)}/outline-at`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ page: point.page, x_pct: point.x_pct, y_pct: point.y_pct }),
      signal: signal || AbortSignal.timeout(120_000),
    },
  );
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
    err.status = res.status;
    err.userMessage = typeof body.detail === 'string' ? body.detail : null;
    throw err;
  }
  return body;
}

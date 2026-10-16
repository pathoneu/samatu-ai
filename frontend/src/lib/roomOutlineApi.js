/**
 * roomOutlineApi — the network half of „Parodyti patalpą" (see lib/roomOutline.js).
 * The server reads the drawing and saves nothing; a click that may not become an
 * outline comes back as a normal answer with its `status`, not as an error.
 */

import { API_BASE } from '@/lib/apiBase';

async function post(projectId, roomNr, action, payload, signal) {
  const res = await fetch(
    `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/rooms/${encodeURIComponent(roomNr)}/${action}`,
    {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
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

/** `{status: 'ok', room, kitu_angos}` | `{status: 'taken'|'open'|'outside'|'no_walls', …}` */
export async function fetchOutlineAt(projectId, roomNr, point, { signal, pritarta = false, klausimas = null } = {}) {
  // `pritarta`: the point is inside the outline the program PROPOSED and he said „Tinka" (2026-09-23)
  // `klausimas`: the Patikra question this click answers — the server's journal row carries it (togal-v2 W11)
  return post(projectId, roomNr, 'outline-at',
    { page: point.page, x_pct: point.x_pct, y_pct: point.y_pct, ...(pritarta ? { pritarta: true } : {}),
      ...(klausimas ? { klausimas: String(klausimas) } : {}) }, signal);
}

/** `{status: 'ok', rooms: {nr: geometry}, kitu_angos}` | `{status: 'bad_line'|'not_shared'|'too_many'|'no_walls'}` */
export async function fetchSplitSpace(projectId, roomNr, request, { signal, klausimas = null } = {}) {
  return post(projectId, roomNr, 'split-space', { ...request, ...(klausimas ? { klausimas: String(klausimas) } : {}) }, signal);
}

/**
 * The boundary the PROGRAM proposes for the space this room shares (2026-09-21) — the very answer a drawn
 * line gives, plus `line_pct` / `page` / `pagal`: `{status: 'ok', rooms, kitu_angos, line_pct, page, pagal}`
 * | `{status: 'no_proposal'|'not_shared'|'too_many'|'no_walls'}`.
 */
export async function fetchSplitProposal(projectId, roomNr, { signal } = {}) {
  return post(projectId, roomNr, 'split-proposal', {}, signal);
}

/**
 * `{status: 'ok', room, kitu_angos}` — the ring the person drew becomes the room's corrected outline (2026-10-16).
 * `holes`: rings cut out of it („Atimti"); absent or empty clears the ones it had.
 */
export async function fetchOutlineSet(projectId, roomNr, { page, polygon_pct, holes = null }, { signal } = {}) {
  return post(projectId, roomNr, 'outline-set', { page, polygon_pct, ...(holes?.length ? { holes } : {}) }, signal);
}

/**
 * „Sujungti" (2026-10-16): room `goneNr` merged INTO `keptNr`, whose outline becomes the drawn union.
 * `{status: 'ok', rooms: {kept, gone}, kitu_angos, neskaiciuoti: [goneNr]}`.
 */
export async function fetchOutlineMerge(projectId, goneNr, { page, kept_nr, polygon_pct, holes = null }, { signal } = {}) {
  return post(projectId, goneNr, 'outline-merge', { page, kept_nr, polygon_pct, ...(holes?.length ? { holes } : {}) }, signal);
}

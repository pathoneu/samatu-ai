/**
 * sheetZonesApi — GET /api/projects/{id}/pages/{page}/zones (api/sheet_zones.py, Pathon v3 W1-E): where on one
 * sheet the plan, the legend, the tables, the title block and the notes are. Boxes are display-frame page
 * fractions (top-left origin) — the frame clicks and `polygon_pct` live in.
 *
 * The room tool asks once per (project, page) per session: a click inside the title block, a legend or a
 * table is never a room (design §5), so it says so instead of reading walls there. A failed or empty answer
 * means „no zones known" — the click goes on as before, never blocked by this.
 */
import { API_BASE } from './apiBase.js';

const cache = new Map();   // `${projectId}:${page}` → Promise<{status, zones}>

export function fetchSheetZones(projectId, page) {
  const key = `${projectId}:${page}`;
  if (!cache.has(key)) {
    const p = fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/pages/${Number(page)}/zones`,
      { credentials: 'include', signal: AbortSignal.timeout(60_000) },
    ).then(async (res) => {
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
      return body;
    }).catch((e) => { cache.delete(key); throw e; });   // a failure is retried on the next ask
    cache.set(key, p);
  }
  return cache.get(key);
}

/** Zone kinds a room never stands in, with the sentence the tool says there. */
export const NO_ROOM_ZONES = Object.freeze({
  antspaudas: 'Čia antspaudas — patalpos čia nėra. Spustelėkite plane, patalpos viduje.',
  legenda: 'Čia legenda — patalpos čia nėra. Spustelėkite plane, patalpos viduje.',
  lentele: 'Čia lentelė — patalpos čia nėra. Spustelėkite plane, patalpos viduje.',
});

/**
 * The no-room zone under a click → `{kind, sentence}` or null. A point inside a `planas` box as well is the
 * plan's (a legend drawn inside the plan viewport does not shadow the rooms around it).
 */
export function noRoomZoneAt(answer, x, y) {
  const zones = Array.isArray(answer?.zones) ? answer.zones : [];
  const inBox = (z) => {
    const b = z?.bbox_pct;
    return Array.isArray(b) && b.length === 4 && x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3];
  };
  const hit = zones.find((z) => NO_ROOM_ZONES[z?.kind] && inBox(z));
  if (!hit) return null;
  const smallerPlan = zones.some((z) => z?.kind === 'planas' && inBox(z) && area(z.bbox_pct) < area(hit.bbox_pct));
  return smallerPlan ? null : { kind: hit.kind, sentence: NO_ROOM_ZONES[hit.kind] };
}

function area(b) {
  return Math.max(0, b[2] - b[0]) * Math.max(0, b[3] - b[1]);
}

/**
 * roomOutline — „Parodyti patalpą": one click inside a room on the check sheet's
 * drawing gives it the wall-exact outline, and its walls are read again
 * (backend api/room_outline.py → extractor/vector_rooms.outline_at).
 *
 * Founder, after the first real Patikra run (2026-09-17): „labai sunku suprasti,
 * kur ką pataisyti galima". A room without an outline showed why, and a blank
 * perimeter — and nothing on the sheet could fix it.
 *
 * Pure functions. The server saves nothing and answers with GEOMETRY keys only;
 * `roomsWithOutline` applies them and nothing else, so a click can never touch a
 * name, an area or a quantity. The rows are rebuilt on the path every other room
 * edit takes (roomSheetApi.saveRoomEdit).
 */

import { ltNumber } from './ledger.js';
import { displayRotationFor, rotatePctPoint } from './viewerEngine/pageRotation.js';

/** Mirror of backend `GEOMETRY_ROOM_KEYS` — what a room's geometry is made of. */
export const GEOMETRY_ROOM_KEYS = [
  'polygon_pct', 'polygon_source', 'polygon_corrected_at', '_konturas', '_konturo_priezastis', '_konturo_siulymas', '_atvira_erdve',
  'perimetras_m', 'perimetras_saltinis', '_sienos', '_perimetras_suma', '_perimetras_priezastis',
  '_perimetras_ivertis_m', '_perimetras_ivertis_saltinis', '_perimetras_pries_geometrija',
  '_angos_sienose', 'grindu_danga', 'grindu_danga_saltinis', '_grindu_danga', '_grindu_dangos_dvi',
  'polygon_holes_pct',
];

/**
 * The viewer hands a click over in UNROTATED page points (PageOverlayHost's
 * coordinate contract); the drawing readers work in the DISPLAYED sheet's
 * fractions — the space `polygon_pct` lives in.
 */
export function displayPointOf(pt) {
  const w = Number(pt?.pageWidth);
  const h = Number(pt?.pageHeight);
  const x = Number(pt?.x);
  const y = Number(pt?.y);
  if (!(w > 0) || !(h > 0) || !Number.isFinite(x) || !Number.isFinite(y)) return null;
  if (x < 0 || y < 0 || x > w || y > h) return null;
  const [dx, dy] = rotatePctPoint(x / w, y / h, displayRotationFor(pt.pageRotation ?? 0));
  return { page: Number(pt.pageIndex) + 1, x_pct: dx, y_pct: dy };
}

/** A room with the server's geometry keys applied — and nothing else of it touched. */
function withGeometry(room, geometry) {
  const next = { ...room };
  for (const key of GEOMETRY_ROOM_KEYS) {
    if (!(key in geometry)) continue;
    if (geometry[key] == null) delete next[key];
    else next[key] = geometry[key];
  }
  return next;
}

function applyGeometry(project, byRoom, answer) {
  const others = answer.kitu_angos && typeof answer.kitu_angos === 'object' ? answer.kitu_angos : {};
  return (Array.isArray(project?.patalpos) ? project.patalpos : []).map((r) => {
    const nr = String(r?.nr ?? '');
    if (byRoom[nr] && typeof byRoom[nr] === 'object') return withGeometry(r, byRoom[nr]);
    return others[nr] ? { ...r, _angos_sienose: others[nr] } : r;
  });
}

/** The project's rooms with the answer applied, or null when the answer is not an outline. */
export function roomsWithOutline(project, roomNr, answer) {
  if (answer?.status !== 'ok' || !answer.room || typeof answer.room !== 'object') return null;
  return applyGeometry(project, { [String(roomNr)]: answer.room }, answer);
}

/** …the same for a divided space: BOTH rooms of `answer.rooms` get their geometry. */
export function roomsWithSplit(project, answer) {
  if (answer?.status !== 'ok' || !answer.rooms || typeof answer.rooms !== 'object') return null;
  return applyGeometry(project, answer.rooms, answer);
}

/**
 * „Padalinti erdvę" takes two clicks on ONE sheet: where the boundary starts and where it ends.
 * `{first, request}` — the point to remember, or the request to send once both are there.
 */
export function nextSplitClick(first, point) {
  if (!point) return { first: first || null, request: null };
  if (!first || Number(first.page) !== Number(point.page)) return { first: point, request: null };
  if (Math.hypot(point.x_pct - first.x_pct, point.y_pct - first.y_pct) < 0.002) return { first, request: null };
  return {
    first: null,
    request: { page: Number(first.page), a: { x_pct: first.x_pct, y_pct: first.y_pct }, b: { x_pct: point.x_pct, y_pct: point.y_pct } },
  };
}

/** Which sentence says why the click gave no outline (i18n key under `project.roomSheet`). */
export function outlineFailureKey(answer) {
  const area = Number.isFinite(Number(answer?.plotas_m2)) ? ltNumber(Number(answer.plotas_m2), 2) : '';
  switch (answer?.status) {
    case 'taken': return { key: 'outlineTaken', params: { room: String(answer.nr ?? '') } };
    case 'open': {
      const su = Array.isArray(answer.su) ? answer.su.map(String).filter(Boolean) : [];
      return su.length
        ? { key: 'outlineOpenWith', params: { rooms: su.join(', '), area } }
        : { key: 'outlineOpen', params: { area } };
    }
    case 'shared': return { key: 'outlineShared', params: { rooms: String(answer.su ?? '') } };
    case 'outside': return { key: 'outlineOutside', params: {} };
    case 'no_walls': return { key: 'outlineNoWalls', params: {} };
    default: return { key: 'outlineFailed', params: {} };
  }
}

/** …and why a line did not divide the space. */
export function splitFailureKey(answer) {
  switch (answer?.status) {
    case 'bad_line': return { key: 'splitBadLine', params: {} };
    case 'not_shared': return { key: 'splitNotShared', params: {} };
    case 'too_many': return { key: 'splitTooMany', params: {} };
    case 'no_walls': return { key: 'outlineNoWalls', params: {} };
    default: return { key: 'outlineFailed', params: {} };
  }
}

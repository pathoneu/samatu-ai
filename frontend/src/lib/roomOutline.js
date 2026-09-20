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
  'polygon_pct', 'polygon_source', 'polygon_corrected_at', '_konturas', '_konturo_priezastis', '_atvira_erdve',
  'perimetras_m', 'perimetras_saltinis', '_sienos', '_perimetras_suma', '_perimetras_priezastis',
  '_perimetras_ivertis_m', '_perimetras_ivertis_saltinis', '_perimetras_pries_geometrija',
  '_angos_sienose', 'grindu_danga', 'grindu_danga_saltinis', '_grindu_danga', '_grindu_dangos_dvi',
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

/** The project's rooms with the answer applied, or null when the answer is not an outline. */
export function roomsWithOutline(project, roomNr, answer) {
  if (answer?.status !== 'ok' || !answer.room || typeof answer.room !== 'object') return null;
  const others = answer.kitu_angos && typeof answer.kitu_angos === 'object' ? answer.kitu_angos : {};
  return (Array.isArray(project?.patalpos) ? project.patalpos : []).map((r) => {
    const nr = String(r?.nr ?? '');
    if (nr === String(roomNr)) {
      const next = { ...r };
      for (const key of GEOMETRY_ROOM_KEYS) {
        if (!(key in answer.room)) continue;
        if (answer.room[key] == null) delete next[key];
        else next[key] = answer.room[key];
      }
      return next;
    }
    return others[nr] ? { ...r, _angos_sienose: others[nr] } : r;
  });
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
    case 'outside': return { key: 'outlineOutside', params: {} };
    case 'no_walls': return { key: 'outlineNoWalls', params: {} };
    default: return { key: 'outlineFailed', params: {} };
  }
}

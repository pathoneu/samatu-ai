/**
 * roomHitTest — which room a click on the drawing lands on, and what that click does to the selection
 * (Pathon v3 wave 1, track W1-D, D1; viewer audit 2026-10-18 §5 F1).
 *
 * Until now the room layer was pointer-transparent at rest and a plain click on the sheet CLEARED the focused
 * room: a room could be selected only from the list. The viewer now hit-tests the click itself (in
 * TakeoffViewer.handlePagePoint, so the measure tools keep their clicks) against exactly what the room layer
 * draws on that sheet — `roomZones.buildPageRoomZones`, the same zones, the same hidden-room filter — so what
 * he sees is what he can click:
 *   1. inside a drawn outline (the smallest one when outlines overlap);
 *   2. else on a room's number marker (a room with no outline, only its printed number);
 *   3. else on the number badge the drawing lane located (`_vieta`, a strong seat on this sheet).
 * Coordinates: display-space page fractions (the space `polygon_pct` lives in); the badge radius is in
 * screen pixels so it feels the same at every zoom.
 *
 * `nextRoomSelection` is the selection grammar of Togal and Kreo: a click selects one room, Shift+click adds
 * or removes one, a click on empty paper clears. The first selected room stays the FOCUSED one (the panel's
 * room, the one „Sujungti" keeps). Pure.
 */
import { buildPageRoomZones, pointInPolygonPoints, roomPageOf } from './roomZones.js';

/** How far from a number marker's centre a click still picks it, in screen pixels. */
export const BADGE_HIT_PX = 22;

/** Lane seats a click may pick a room by (backend vector_rooms.STRONG). */
const STRONG_SEATS = new Set(['zenkliukas', 'plotas_uzrasas']);

function shoelace(points) {
  let a = 0;
  for (let i = 0; i < points.length; i += 1) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % points.length];
    a += x1 * y2 - x2 * y1;
  }
  return Math.abs(a / 2);
}

/**
 * The room under a click → `{nr, how}` (`how`: 'outline' | 'number' | 'seat') or null.
 * `point` = {page, x_pct, y_pct}; `renderedWidth/Height` = the sheet's size on screen (for the badge radius);
 * `hidden` = room numbers the panel's eye hides (a hidden room is not on the sheet, so it is not clickable).
 */
export function roomAtPoint(rooms, point, { renderedWidth = 1000, renderedHeight = 1000, badgePx = BADGE_HIT_PX, hidden = null } = {}) {
  const page = Number(point?.page);
  const fx = Number(point?.x_pct);
  const fy = Number(point?.y_pct);
  if (!Array.isArray(rooms) || !(page > 0) || !Number.isFinite(fx) || !Number.isFinite(fy)) return null;
  const W = Number(renderedWidth) > 0 ? Number(renderedWidth) : 1000;
  const H = Number(renderedHeight) > 0 ? Number(renderedHeight) : 1000;
  const hiddenSet = new Set(Array.from(hidden || []).map(String));
  const x = fx * W;
  const y = fy * H;
  const zones = buildPageRoomZones(rooms, { renderedWidth: W, renderedHeight: H, page })
    .filter((z) => !hiddenSet.has(String(z.nr)));

  const inside = zones
    .filter((z) => z.geometry.type === 'polygon' && pointInPolygonPoints(x, y, z.geometry.points))
    .map((z) => ({ nr: String(z.nr), area: shoelace(z.geometry.points) }))
    .sort((a, b) => a.area - b.area);
  if (inside.length) return { nr: inside[0].nr, how: 'outline' };

  const near = (cx, cy, r) => Math.hypot(cx - x, cy - y) <= r;
  const markers = zones
    .filter((z) => z.geometry.type === 'marker')
    .map((z) => ({ nr: String(z.nr), d: Math.hypot(z.geometry.cx - x, z.geometry.cy - y) }))
    .filter((m) => m.d <= badgePx)
    .sort((a, b) => a.d - b.d);
  if (markers.length) return { nr: markers[0].nr, how: 'number' };

  const seats = rooms
    .filter((r) => r && !hiddenSet.has(String(r.nr)) && roomPageOf(r) === page)
    .map((r) => ({ r, v: r._vieta }))
    .filter(({ v }) => v && Number(v.page) === page && STRONG_SEATS.has(v.saltinis)
      && Number.isFinite(Number(v.cx)) && Number.isFinite(Number(v.cy)))
    .map(({ r, v }) => {
      const reach = Math.max(badgePx, (Number(v.W) > 0 ? Number(v.W) * W : 0) / 2);
      const cx = Number(v.cx) * W;
      const cy = Number(v.cy) * H;
      return { nr: String(r.nr), d: Math.hypot(cx - x, cy - y), ok: near(cx, cy, reach) };
    })
    .filter((s) => s.ok)
    .sort((a, b) => a.d - b.d);
  if (seats.length) return { nr: seats[0].nr, how: 'seat' };
  return null;
}

/**
 * The selection after one click. `sel` = {focused: nr | null, extra: [nr…]}; `nr` = the room under the click
 * (null on empty paper); `shift` = Shift held. → {focused, extra}.
 *   click a room           → that room alone;
 *   click empty paper      → nothing selected;
 *   Shift+click a room     → added (or, if it is selected, removed — the next one becomes the focused room);
 *   Shift+click empty      → unchanged.
 */
export function nextRoomSelection(sel, nr, { shift = false } = {}) {
  const focused = sel?.focused == null ? null : String(sel.focused);
  const extra = (Array.isArray(sel?.extra) ? sel.extra : []).map(String).filter((n) => n !== focused);
  const hit = nr == null ? null : String(nr);
  if (!shift) return hit == null ? { focused: null, extra: [] } : { focused: hit, extra: [] };
  if (hit == null) return { focused, extra };
  if (focused == null) return { focused: hit, extra: [] };
  if (hit === focused) return { focused: extra[0] ?? null, extra: extra.slice(1) };
  if (extra.includes(hit)) return { focused, extra: extra.filter((n) => n !== hit) };
  return { focused, extra: [...extra, hit] };
}

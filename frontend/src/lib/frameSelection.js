// frameSelection — „show the selection in the whole window" (Pathon v3 click model, W1-B task B4;
// Togal §2b „F = centre / frame the selection", Kreo „Focus F"). The key is Shift+F or „." — plain F is
// „Rasti panašius" (plan B4).
//
// Returns a rectangle in DISPLAY-frame page fractions [x0, y0, x1, y1] — the frame TakeoffViewer's
// FocusZoomer fits — padded so the selection does not touch the window edge.

import { buildRoomZone, roomPageOf } from './roomZones.js';
import { rotatePctPoint } from './viewerEngine/pageRotation.js';

const PAD = 0.25;          // a quarter of the selection's size on every side
const MIN_SIZE = 0.08;     // a point (a count mark, a marker-only room) still gets a readable window

function clamp01(v) { return Math.max(0, Math.min(1, v)); }

/** Pad a bbox of fractions and keep it on the page. */
export function paddedRect(xs, ys) {
  if (!xs.length || !ys.length) return null;
  let x0 = Math.min(...xs); let x1 = Math.max(...xs);
  let y0 = Math.min(...ys); let y1 = Math.max(...ys);
  if (![x0, x1, y0, y1].every(Number.isFinite)) return null;
  const w = Math.max(x1 - x0, MIN_SIZE);
  const h = Math.max(y1 - y0, MIN_SIZE);
  const cx = (x0 + x1) / 2; const cy = (y0 + y1) / 2;
  x0 = cx - (w / 2) * (1 + 2 * PAD); x1 = cx + (w / 2) * (1 + 2 * PAD);
  y0 = cy - (h / 2) * (1 + 2 * PAD); y1 = cy + (h / 2) * (1 + 2 * PAD);
  return [clamp01(x0), clamp01(y0), clamp01(x1), clamp01(y1)];
}

/** A room's frame: its outline, else its printed-number marker. { page, rect } or null. */
export function frameForRoom(room) {
  const page = roomPageOf(room);
  if (!room || !page) return null;
  const zone = buildRoomZone(room, { renderedWidth: 1, renderedHeight: 1 });
  if (!zone) return null;
  const g = zone.geometry;
  const rect = g.type === 'polygon'
    ? paddedRect(g.points.map((p) => p[0]), g.points.map((p) => p[1]))
    : paddedRect([g.cx], [g.cy]);
  return rect ? { page: Number(page), rect } : null;
}

/**
 * Measurements' frame (all on one page — the first mark's): their points are unrotated mediabox PDF
 * points; the frame is the displayed page. { page, rect } or null.
 */
export function frameForMeasurements(measurements, { pageSizeOf, rotationOf } = {}) {
  const list = (measurements || []).filter((m) => Array.isArray(m?.points) && m.points.length);
  if (!list.length) return null;
  const page = list[0].page;
  const size = pageSizeOf?.(page);
  if (!size?.width || !size?.height) return null;
  const rot = rotationOf?.(page) ?? 0;
  const xs = []; const ys = [];
  for (const m of list.filter((x) => x.page === page)) {
    for (const p of m.points) {
      const [x, y] = rotatePctPoint(p.x / size.width, p.y / size.height, rot);
      xs.push(x); ys.push(y);
    }
  }
  const rect = paddedRect(xs, ys);
  return rect ? { page: Number(page), rect } : null;
}

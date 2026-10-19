// focusFrame — where the viewer goes when a room is focused from outside the drawing (a list row, Patikra's
// „Rodyti brėžinyje", a search hit): the ROOM, not the top of its sheet (Pathon v3 W5-B B7, coverage #132).
//
// A room with an outline is framed by it (lib/frameSelection.frameForRoom, padded); a room known only by its
// number marker gets a window of MARKER_WINDOW of the sheet around the marker — close enough to read, wide
// enough to see where it is. A room with neither has no frame: the viewer scrolls to its page as before. Pure.

import { frameForRoom } from './frameSelection.js';
import { buildRoomZone, roomPageOf } from './roomZones.js';

export const MARKER_WINDOW = 0.35;

export function focusFrameForRoom(room) {
  const page = roomPageOf(room);
  if (!room || !page) return null;
  const zone = buildRoomZone(room, { renderedWidth: 1, renderedHeight: 1 });
  if (!zone) return null;
  if (zone.geometry?.type === 'polygon') return frameForRoom(room);
  const cx = Number(zone.geometry?.cx);
  const cy = Number(zone.geometry?.cy);
  if (!Number.isFinite(cx) || !Number.isFinite(cy)) return null;
  const h = MARKER_WINDOW / 2;
  const x0 = Math.max(0, Math.min(1 - MARKER_WINDOW, cx - h));
  const y0 = Math.max(0, Math.min(1 - MARKER_WINDOW, cy - h));
  return { page: Number(page), rect: [x0, y0, x0 + MARKER_WINDOW, y0 + MARKER_WINDOW] };
}

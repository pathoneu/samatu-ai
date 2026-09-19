/**
 * checkOverlay — what the check sheet draws ON the drawing for one room.
 *
 * Patikra v2 (2026-09-19): the left side of the sheet is the real viewer, and
 * on it the things the program READ about this room — the traced outline, every
 * wall coloured by where its length came from, the dimension strings that were
 * added (marked on the sheet they are written on), and the place each other
 * fact was read from. Pure functions: no React, no math about quantities —
 * lengths, sources and sums all arrive from the backend (room_facts.py
 * `_perimeter_drawing`, dimension_sum.py).
 *
 * Coordinates are DISPLAY-space page fractions, the same space `polygon_pct`
 * lives in; the viewer's rotation wrapper turns them with the page.
 *
 * Sheets of one plan lie over each other (`_meta.geometrija.sutapdinimas`:
 * base = k·sheet + d, in page fractions), so the room traced on the layout
 * sheet is also drawn on the wall-painting sheet, where its numbers are.
 */

import { ltNumber } from './ledger.js';

const MIN_FOCUS = 0.08;          // a focus box never shrinks below this share of the page
const ROOM_MARGIN = 0.035;
const MARKER_NEIGHBOURHOOD = 0.07;

const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : null);
const round5 = (v) => Number(Number(v).toFixed(5));

function entry(sut, page) {
  const e = sut && (sut[page] ?? sut[String(page)]);
  if (!e) return null;
  const kx = num(e.kx ?? e.k);
  const ky = num(e.ky ?? e.k);
  if (!(kx > 0) || !(ky > 0)) return null;
  return { base: Number(e.base), kx, ky, dx: num(e.dx_pct) ?? 0, dy: num(e.dy_pct) ?? 0 };
}

/** A page-fraction point on `fromPage`, laid onto `toPage` of the same plan. */
export function mapPct(pt, fromPage, toPage, sutapdinimas) {
  if (!Array.isArray(pt) || Number(fromPage) === Number(toPage)) return pt;
  const from = entry(sutapdinimas, fromPage);
  const to = entry(sutapdinimas, toPage);
  if (!from || !to || from.base !== to.base) return pt;      // not the same plan: nothing to lay over
  const bx = from.kx * pt[0] + from.dx;
  const by = from.ky * pt[1] + from.dy;
  return [(bx - to.dx) / to.kx, (by - to.dy) / to.ky];
}

/** Where a wall's length came from — the four things the legend names. */
export function wallState(wall) {
  const s = wall?.saltinis;
  if (s === 'eilute') return 'read';
  if (s === 'priesinga_siena') return 'borrowed';
  if (s === 'konturas') return 'outline';
  return 'missing';
}

/** The number(s) written along the wall, exactly as the drawing writes them. */
export function wallLabel(wall) {
  const state = wallState(wall);
  if (state === 'missing') return '—';
  const texts = (wall?.eilutes || []).map((e) => String(e?.text ?? '')).filter(Boolean);
  if (texts.length && state !== 'outline') return texts.join(' + ');
  return num(wall?.ilgis_m) != null ? ltNumber(Number(wall.ilgis_m), 2) : '—';
}

/** A padded, clamped focus box around points `[[x, y], …]` or a rect `[x0, y0, x1, y1]`. */
export function focusRectFor(shape, margin = ROOM_MARGIN) {
  if (!Array.isArray(shape) || !shape.length) return null;
  const pts = Array.isArray(shape[0]) ? shape : [[shape[0], shape[1]], [shape[2], shape[3]]];
  const xs = pts.map((p) => num(p?.[0])).filter((v) => v != null);
  const ys = pts.map((p) => num(p?.[1])).filter((v) => v != null);
  if (!xs.length || !ys.length) return null;
  let x0 = Math.min(...xs) - margin; let x1 = Math.max(...xs) + margin;
  let y0 = Math.min(...ys) - margin; let y1 = Math.max(...ys) + margin;
  if (x1 - x0 < MIN_FOCUS) { const c = (x0 + x1) / 2; x0 = c - MIN_FOCUS / 2; x1 = c + MIN_FOCUS / 2; }
  if (y1 - y0 < MIN_FOCUS) { const c = (y0 + y1) / 2; y0 = c - MIN_FOCUS / 2; y1 = c + MIN_FOCUS / 2; }
  if (x0 < 0) { x1 -= x0; x0 = 0; }
  if (y0 < 0) { y1 -= y0; y0 = 0; }
  return [round5(Math.max(0, x0)), round5(Math.max(0, y0)), round5(Math.min(1, x1)), round5(Math.min(1, y1))];
}

function sameRect(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== 4 || b.length !== 4) return false;
  return a.every((v, i) => Math.abs(Number(v) - Number(b[i])) < 1e-3);
}

function boxOf(points) {
  if (!Array.isArray(points) || !points.length) return null;
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

function validPolygon(poly) {
  return Array.isArray(poly) && poly.length >= 3
    && poly.every((p) => Array.isArray(p) && num(p[0]) != null && num(p[1]) != null);
}

/**
 * Everything the viewer draws for this room, per page, plus where to look.
 *   pages[p] = { outline, openSpace, walls, strings, marks, marker }
 *   roomFocus = { page, rect }   — „Į patalpą"
 *   factFocus = { page, rect } | null   — the active fact's own place
 */
export function buildCheckOverlay({ room, facts, sutapdinimas = null, activeFactKey = null } = {}) {
  const out = { pages: {}, roomFocus: null, factFocus: null, outlineReason: null };
  if (!room) return out;
  const list = Array.isArray(facts) ? facts : [];
  const pageOf = (p) => {
    const key = Number(p);
    if (!out.pages[key]) out.pages[key] = { outline: null, openSpace: null, walls: [], strings: [], marks: [], marker: null };
    return out.pages[key];
  };

  const perim = list.find((f) => f?.key === 'perimetras') || null;
  const outlinePage = num(perim?.outline?.page) ?? num(room.page);
  const outline = validPolygon(perim?.outline?.polygon_pct) ? perim.outline.polygon_pct : null;
  const space = perim?.outline?.open_space;
  const shared = validPolygon(space?.polygon_pct) ? space.polygon_pct : null;
  const walls = outline && Array.isArray(perim?.walls) ? perim.walls : [];
  out.outlineReason = !outline && perim?.outline_reason ? String(perim.outline_reason) : null;

  if (outlinePage != null) {
    // the sheets this room is drawn on: its own, and every sheet one of its numbers is written on
    const sheets = new Set([outlinePage]);
    for (const w of walls) for (const e of w.eilutes || []) if (num(e?.page) != null) sheets.add(Number(e.page));
    for (const sheet of sheets) {
      const page = pageOf(sheet);
      const lay = (pt) => mapPct(pt, outlinePage, sheet, sutapdinimas);
      if (outline) page.outline = outline.map(lay);
      page.walls = walls.map((w) => ({
        a: lay(w.edge_pct[0]), b: lay(w.edge_pct[1]), state: wallState(w), label: wallLabel(w),
      }));
      for (const w of walls) {
        for (const e of w.eilutes || []) {
          if (Number(e?.page) !== sheet || !Array.isArray(e.line_pct) || e.line_pct.length !== 2) continue;
          page.strings.push({ a: e.line_pct[0], b: e.line_pct[1], text: String(e.text ?? '') });
        }
      }
    }
    if (shared) {
      const sp = num(space.page) ?? outlinePage;
      pageOf(sp).openSpace = {
        points: shared, nariai: (space.nariai || []).map(String), perimetras_m: num(space.perimetras_m),
      };
    }
  }

  // the room's printed number: the only mark a room without its own outline has
  const marker = Array.isArray(room.marker_pct) && num(room.marker_pct[0]) != null && num(room.marker_pct[1]) != null
    ? { x: Number(room.marker_pct[0]), y: Number(room.marker_pct[1]), nr: String(room.nr ?? '') } : null;
  if (marker && !outline && num(room.page) != null) pageOf(room.page).marker = marker;

  // where each fact was read — only a place the fact really has (not the room's own box)
  const roomBox = outline ? boxOf(outline) : null;
  for (const f of list) {
    const src = f?.source;
    const rect = Array.isArray(src?.rect_pct) && src.rect_pct.length === 4 ? src.rect_pct.map(Number) : null;
    if (!rect || num(src?.page) == null) continue;
    const whole = rect[0] <= 0.001 && rect[1] <= 0.001 && rect[2] >= 0.999 && rect[3] >= 0.999;
    const onlyTheRoom = sameRect(rect, room.region_pct)
      || (roomBox && rect[0] <= roomBox[0] && rect[1] <= roomBox[1] && rect[2] >= roomBox[2] && rect[3] >= roomBox[3]
        && (rect[2] - rect[0]) < (roomBox[2] - roomBox[0]) + 0.08)
      || (f.key === 'perimetras');
    if (!whole && !onlyTheRoom) {
      pageOf(src.page).marks.push({ key: f.key, rect, active: f.key === activeFactKey });
    }
    if (f.key === activeFactKey && !whole) out.factFocus = { page: Number(src.page), rect: focusRectFor(rect, 0.02) };
  }

  const focusShape = outline || shared
    || (marker ? [[marker.x - MARKER_NEIGHBOURHOOD, marker.y - MARKER_NEIGHBOURHOOD], [marker.x + MARKER_NEIGHBOURHOOD, marker.y + MARKER_NEIGHBOURHOOD]] : null)
    || (Array.isArray(room.region_pct) ? room.region_pct : null);
  const focusPage = outline ? outlinePage : (shared ? (num(space.page) ?? outlinePage) : num(room.page));
  if (focusShape && focusPage != null) out.roomFocus = { page: Number(focusPage), rect: focusRectFor(focusShape) };
  return out;
}

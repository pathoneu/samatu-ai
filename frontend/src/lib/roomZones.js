/**
 * roomZones.js — pure helpers that turn extracted patalpos[] rooms into
 * render-ready zone descriptors for the AI Takeoff Viewer's RoomZoneLayer.
 *
 * The viewer is a FACE over the existing engine (design spec 2026-07-01 §3):
 * these functions add NO new quantity math. They only
 *   1. name a room's paskirtis in words (the room type goes into the label —
 *      zones share ONE neutral tint, v3 overlay vocabulary, founder decision
 *      2026-10-18),
 *   2. bridge polygon_pct / bbox_pct → screen pixels (reusing
 *      planOverlayGeometry — the coordinate bridge that was never wired into a
 *      visible overlay),
 *   3. attach the room's AREA confidence (reusing computeAreaConfidence — the
 *      audited provenance→🟢🟡🔴 logic; spec §5 "do not invent a new one"),
 *   4. flag geometry that is only APPROXIMATE (synthesized from bbox), so the
 *      viewer never draws a fabricated-precise polygon (spec §9).
 */

import { computeAreaConfidence } from './areaConfidence.js';
import { getPolygonPctPoints } from './planOverlayGeometry.js';
import { outlineKindOf } from './overlayTokens.js';
import { ltCount, ltPlural } from './ltPlural.js';

// paskirtis → the word the label shows. v3 overlay vocabulary (2026-10-18, founder decision 2):
// zones no longer carry a hue per room type (9 Tailwind hues, 6 of them under 3:1 on the white
// sheet, no legend) — they share one neutral tint and the type is WRITTEN in the label.
export const ROOM_TYPE_WORDS = {
  gyvenamoji: 'gyvenamoji', svetaine: 'svetainė',
  miegamoji: 'miegamasis', miegamasis: 'miegamasis', vaikui: 'vaiko kambarys',
  virtuve: 'virtuvė', valgomasis: 'valgomasis', kabinetas: 'darbo kambarys',
  vonia: 'vonia', vonios: 'vonia', wc: 'WC', san: 'san. mazgas', sanitarine: 'san. mazgas',
  san_mazgas: 'san. mazgas', skalbykla: 'skalbykla', pirtis: 'pirtis',
  koridorius: 'koridorius', holas: 'holas', prieskambaris: 'prieškambaris', laiptine: 'laiptinė',
  drabuzine: 'drabužinė', 'rūbinė': 'rūbinė', rubine: 'rūbinė',
  sandeliukas: 'sandėliukas', saugykla: 'sandėliukas', katiline: 'katilinė', ukio: 'ūkio patalpa',
  techpatalpa: 'techninė patalpa',
  garazas: 'garažas', 'tambūras': 'tambūras', tamburas: 'tambūras',
  balkonas: 'balkonas', terasa: 'terasa',
};

/** The room type in words for the label, or null when the type is unknown. */
export function roomTypeWord(paskirtis) {
  if (!paskirtis) return null;
  return ROOM_TYPE_WORDS[paskirtis] || ROOM_TYPE_WORDS[String(paskirtis).toLowerCase()] || null;
}

// FOUNDER DECISION (2026-07-11): the default room presentation is a numbered
// MARKER at the polygon centroid, NOT the filled polygon — on real plans the
// flood-fill outlines bleed over walls / notch around annotations and read as
// "polygons don't match the rooms". The polygon fills stay in the codebase and
// are reachable via the viewer toolbar's zone-fill toggle; flip this to true
// once the traced polygons are trusted again.
export const ROOM_POLYGON_FILLS_DEFAULT_VISIBLE = false;

// Area confidence in words (the old coloured dot had only an English <title>): said only when the
// area needs a look — a trusted area adds nothing to the label.
const AREA_CHECK_TEXT = {
  medium: 'plotą verta patikrinti',
  low: 'plotą būtina patikrinti',
  unknown: 'plotas nežinomas',
};

export function areaConfidenceText(confidence) {
  return AREA_CHECK_TEXT[confidence] || null;
}

// A polygon whose source is in this set is NOT a real traced outline — the
// polygon it may carry is a fabricated coarse rectangle, so the room becomes a
// Tier-2 marker (circled number), never a solid zone.
const NON_TRACED_SOURCES = new Set(['synthesized_from_bbox', 'bbox_fallback', 'manual_needed']);

// Area-weighted centroid of a scaled polygon ([[x,y], …] screen px). Falls back
// to the bbox center for degenerate (zero-area) rings. Used to anchor the
// default numbered marker of a TRACED room — the centroid is reliable even when
// the traced outline itself is sloppy at the edges.
export function polygonPointsCentroid(points) {
  if (!Array.isArray(points) || points.length < 3) return null;
  let cx = 0, cy = 0, areaSum = 0;
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = points[i];
    const [x2, y2] = points[(i + 1) % n];
    const f = x1 * y2 - x2 * y1;
    cx += (x1 + x2) * f;
    cy += (y1 + y2) * f;
    areaSum += f;
  }
  if (areaSum !== 0) {
    const a = areaSum / 2;
    return { cx: cx / (6 * a), cy: cy / (6 * a) };
  }
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return {
    cx: (Math.min(...xs) + Math.max(...xs)) / 2,
    cy: (Math.min(...ys) + Math.max(...ys)) / 2,
  };
}

function markerCenter(room, { renderedWidth, renderedHeight }) {
  // ONLY a reliable printed-number anchor (marker_pct = the backend's label seed,
  // or label_pct) may place a marker. Do NOT fall back to the bbox centroid — on
  // furnished/rotated plans Vision bboxes are garbage and a bbox-centroid marker
  // is the "marked random places" failure. No anchor → null → the room falls to
  // the honest "N patalpų be vietos" chip.
  const mp = room.marker_pct || room.label_pct;
  if (Array.isArray(mp) && mp.length === 2) {
    return { cx: mp[0] * renderedWidth, cy: mp[1] * renderedHeight };
  }
  return null;
}

/**
 * buildRoomZone — one room → a render-ready descriptor, or null if the room
 * has no geometry we can honestly place on the plan.
 *
 * Three honest tiers:
 *   Tier 1 (traced)  { type: 'polygon', points: [[x,y], …] }  — real flood-fill
 *     outline (polygon_source NOT in NON_TRACED_SOURCES). approximate = false.
 *   Tier 2 (located) { type: 'marker', cx, cy }               — no traced shape
 *     but a label-anchored marker_pct/label_pct exists. approximate = true.
 *   Tier 3 (no place) → null                                  — no polygon and
 *     no anchor; surfaced by countRoomsMissingGeometry as the "be vietos" chip.
 * A coarse bbox rectangle is NEVER drawn.
 */
export function buildRoomZone(room, { renderedWidth, renderedHeight } = {}) {
  if (!room || !renderedWidth || !renderedHeight) return null;

  const traced = room.polygon_pct && !NON_TRACED_SOURCES.has(room.polygon_source);
  let geometry = null;
  let approximate = false;

  if (traced) {
    const polyPoints = getPolygonPctPoints(room.polygon_pct, { renderedWidth, renderedHeight });
    if (polyPoints) {
      geometry = { type: 'polygon', points: polyPoints };
      approximate = false;
    }
  }
  // Tier 2 markers are ONLY honest when the room has a real label anchor.
  // Historically, NON_TRACED rooms' seeds often matched the eksplikacija
  // number column (markers floating in empty space), so they were suppressed
  // wholesale. Since 2026-07-12 the backend column-filters the seed locator
  // and stamps trustworthy anchors with marker_source: 'plan_label' — those
  // may render a Tier-2 circled number even without a polygon. Legacy rooms
  // without the stamp keep the conservative suppression and fall to the
  // honest "N patalpų be vietos plane" chip.
  const labelVerified = room.marker_source === 'plan_label';
  if (!geometry && (labelVerified || !NON_TRACED_SOURCES.has(room.polygon_source))) {
    // Tier 2: circled-number marker at the printed label (label-anchored only).
    const c = markerCenter(room, { renderedWidth, renderedHeight });
    if (c) {
      geometry = { type: 'marker', cx: c.cx, cy: c.cy };
      approximate = true;
    }
  }

  if (!geometry) return null;

  // Marker anchor for the default numbered-marker presentation (founder
  // decision 2026-07-11): traced polygons anchor at an INTERIOR point —
  // centroid when it lands inside, otherwise the deepest inside sample
  // (L-shaped rooms have exterior centroids). Tier-2 rooms reuse their
  // label anchor.
  const marker = geometry.type === 'polygon'
    ? interiorMarkerAnchor(geometry.points)
    : { cx: geometry.cx, cy: geometry.cy };

  // Exact printed-label anchor (verified plan_label seeds only) — the simple
  // "red ring around the room's own number" presentation targets THIS, not the
  // polygon interior anchor.
  const labelAnchor = room.marker_source === 'plan_label'
    ? markerCenter(room, { renderedWidth, renderedHeight })
    : null;

  const { confidence } = computeAreaConfidence(room);
  const area = Number.isFinite(room.plotas_m2) ? room.plotas_m2 : null;

  return {
    nr: room.nr,
    label: room.pavadinimas || `#${room.nr}`,
    areaLabel: area != null ? `${roomAreaText(area)} m²` : '',
    paskirtis: room.paskirtis || null,
    typeWord: roomTypeWord(room.paskirtis),
    confidence,
    confidenceText: areaConfidenceText(confidence),
    // how the outline is drawn (lib/overlayTokens): solid = read / confirmed, dashed = estimated;
    // a Tier-2 room has no outline — only its printed number
    outline: geometry.type === 'marker' ? 'marker' : outlineKindOf(room),
    approximate,
    geometry,
    marker,
    labelAnchor,
  };
}

/**
 * spreadOverlappingMarkers — de-overlap marker anchors so every circled room
 * number stays readable and clickable. On real plans several rooms can carry
 * near-identical polygons (duplicated flood-fills → identical centroids), which
 * stacks their markers exactly on top of each other. Groups anchors within
 * `minGap` of each other (transitively), then fans each group out horizontally
 * around the group's center, ordered by nr for determinism.
 *
 * @param items [{ nr, cx, cy }] — original anchors
 * @param minGap px — minimum center-to-center distance (default 2R + 4)
 * @returns Map nr(String) → { cx, cy } adjusted anchors
 */
export function spreadOverlappingMarkers(items, minGap = 30) {
  const out = new Map();
  if (!Array.isArray(items) || items.length === 0) return out;
  // Union-find style greedy clustering on the ORIGINAL positions.
  const groups = [];
  for (const it of items) {
    const hit = groups.find((g) => g.some(
      (m) => Math.hypot(m.cx - it.cx, m.cy - it.cy) < minGap));
    if (hit) hit.push(it); else groups.push([it]);
  }
  for (const g of groups) {
    if (g.length === 1) {
      out.set(String(g[0].nr), { cx: g[0].cx, cy: g[0].cy });
      continue;
    }
    const midX = g.reduce((s, m) => s + m.cx, 0) / g.length;
    const midY = g.reduce((s, m) => s + m.cy, 0) / g.length;
    const sorted = [...g].sort((a, b) => String(a.nr).localeCompare(String(b.nr), 'lt', { numeric: true }));
    sorted.forEach((m, i) => {
      const off = (i - (sorted.length - 1) / 2) * minGap;
      // Try horizontal fan, then vertical; a fanned marker must stay INSIDE
      // its own polygon (when known) — a number floating in empty space is
      // worse than two slightly overlapping numbers, so the last resort is
      // the marker's own (unfanned) interior anchor.
      const candidates = [
        { cx: midX + off, cy: midY },
        { cx: midX, cy: midY + off },
      ];
      const ok = !m.points
        ? candidates[0]
        : candidates.find((c) => pointInPolygonPoints(c.cx, c.cy, m.points));
      out.set(String(m.nr), ok || { cx: m.cx, cy: m.cy });
    });
  }
  return out;
}

/**
 * roomPageOf — THE page-field precedence for a room, shared by every consumer.
 *
 * AUDIT P2: this file used `page_nr ?? puslapio_nr` while FocusScroller and
 * durableScale used `puslapio_nr ?? page_nr`. A room carrying BOTH (they
 * disagree on re-extracted projects) drew its zone on one page while the viewer
 * scrolled to another. `puslapio_nr` wins — it is the extraction-native field
 * and the majority reading.
 */
export function roomPageOf(room) {
  return room?.puslapio_nr ?? room?.page_nr ?? null;
}

// ── Geometry helpers (screen-space [[x,y], …] rings) ────────────────────────

export function pointInPolygonPoints(x, y, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const [xi, yi] = points[i];
    const [xj, yj] = points[j];
    if (((yi > y) !== (yj > y)) && (x < ((xj - xi) * (y - yi)) / (yj - yi) + xi)) {
      inside = !inside;
    }
  }
  return inside;
}

function distToSegment(px, py, ax, ay, bx, by) {
  const dx = bx - ax, dy = by - ay;
  const len2 = dx * dx + dy * dy;
  const t = len2 === 0 ? 0 : Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

function minEdgeDistance(x, y, points) {
  let d = Infinity;
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    d = Math.min(d, distToSegment(x, y, points[j][0], points[j][1], points[i][0], points[i][1]));
  }
  return d;
}

/**
 * interiorMarkerAnchor — a point guaranteed INSIDE the polygon. The centroid
 * when it lands inside (usual case); otherwise (L/U-shaped rooms) the best of
 * a coarse grid sample — the inside candidate farthest from any edge (a cheap
 * pole-of-inaccessibility). A marker floating outside its own room is the
 * "marked random places" failure the founder rejected — never allow it.
 */
export function interiorMarkerAnchor(points) {
  const c = polygonPointsCentroid(points);
  if (c && pointInPolygonPoints(c.cx, c.cy, points)) return c;
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  const candidates = [];
  const N = 15;
  for (let i = 1; i < N; i++) {
    for (let j = 1; j < N; j++) {
      candidates.push([x0 + ((x1 - x0) * i) / N, y0 + ((y1 - y0) * j) / N]);
    }
  }
  // Arms thinner than bbox/N slip through the grid — also probe just inside
  // each edge midpoint (both normals; the inside one survives the test).
  const eps = Math.max(2, Math.hypot(x1 - x0, y1 - y0) * 0.02);
  for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
    const mx = (points[j][0] + points[i][0]) / 2;
    const my = (points[j][1] + points[i][1]) / 2;
    const dx = points[i][0] - points[j][0];
    const dy = points[i][1] - points[j][1];
    const len = Math.hypot(dx, dy) || 1;
    candidates.push([mx - (dy / len) * eps, my + (dx / len) * eps]);
    candidates.push([mx + (dy / len) * eps, my - (dx / len) * eps]);
  }
  let best = null;
  for (const [x, y] of candidates) {
    if (!pointInPolygonPoints(x, y, points)) continue;
    const d = minEdgeDistance(x, y, points);
    if (!best || d > best.d) best = { cx: x, cy: y, d };
  }
  return best ? { cx: best.cx, cy: best.cy } : c;
}

// ── Duplicate-polygon disqualification ──────────────────────────────────────
// Real failure on the Objektas A demo: flood-fill returned the IDENTICAL corridor
// polygon for rooms 103/108/109 (and near-identical for 101/104). Only one
// claimant can be right; drawing all of them stacks zones and forces markers
// into empty space. We keep the claimant whose known plotas_m2 best matches
// the polygon's area (scale k estimated from the page's UNIQUE polygons) and
// disqualify the rest — they fall to the honest "be vietos plane" chip.

function pctPoints(room) {
  const poly = room?.polygon_pct;
  if (!Array.isArray(poly) || poly.length < 3) return null;
  const pts = poly.map((p) => (Array.isArray(p) ? p : [p?.x_pct, p?.y_pct]));
  return pts.every((p) => Number.isFinite(p[0]) && Number.isFinite(p[1])) ? pts : null;
}

function shoelaceArea(pts) {
  let a = 0;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    a += pts[j][0] * pts[i][1] - pts[i][0] * pts[j][1];
  }
  return Math.abs(a / 2);
}

function bboxOf(pts) {
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

function bboxIoU(a, b) {
  const ix = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const iy = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const inter = ix * iy;
  const ua = (a[2] - a[0]) * (a[3] - a[1]);
  const ub = (b[2] - b[0]) * (b[3] - b[1]);
  const union = ua + ub - inter;
  return union > 0 ? inter / union : 0;
}

const DUP_IOU = 0.85;

/** Set of String(nr) whose polygon is a duplicate claimed by a better owner. */
export function duplicatePolygonLosers(rooms, page) {
  const losers = new Set();
  const traced = (Array.isArray(rooms) ? rooms : [])
    .filter((r) => roomPageOf(r) === page)
    .filter((r) => r.polygon_pct && !NON_TRACED_SOURCES.has(r.polygon_source))
    .map((r) => {
      const pts = pctPoints(r);
      return pts ? { nr: String(r.nr), pts, area: shoelaceArea(pts), bbox: bboxOf(pts), m2: Number(r.plotas_m2) || null } : null;
    })
    .filter(Boolean);
  if (traced.length < 2) return losers;

  // Transitive grouping on bbox IoU.
  const groups = [];
  for (const t of traced) {
    const g = groups.find((grp) => grp.some((m) => bboxIoU(m.bbox, t.bbox) >= DUP_IOU));
    if (g) g.push(t); else groups.push([t]);
  }
  const dupGroups = groups.filter((g) => g.length > 1);
  if (dupGroups.length === 0) return losers;

  // Scale estimate: pct-area per m² from rooms OUTSIDE duplicate groups.
  const inDup = new Set(dupGroups.flat().map((t) => t.nr));
  const ratios = traced
    .filter((t) => !inDup.has(t.nr) && t.m2 > 0)
    .map((t) => t.area / t.m2)
    .sort((a, b) => a - b);
  const k = ratios.length ? ratios[Math.floor(ratios.length / 2)] : null;

  for (const g of dupGroups) {
    let winner;
    if (k) {
      winner = g.reduce((best, t) => {
        const err = t.m2 ? Math.abs(t.area / k - t.m2) : Infinity;
        return !best || err < best.err ? { t, err } : best;
      }, null).t;
    } else {
      // No reference scale — deterministic: lowest nr keeps the polygon.
      winner = [...g].sort((a, b) => a.nr.localeCompare(b.nr, 'lt', { numeric: true }))[0];
    }
    g.forEach((t) => { if (t !== winner) losers.add(t.nr); });
  }
  return losers;
}

/**
 * buildPageRoomZones — all rooms on `page` that CAN be drawn, as descriptors.
 * Rooms without geometry are dropped here (they still surface in the review
 * worklist and in countRoomsMissingGeometry).
 */
export function buildPageRoomZones(rooms, { renderedWidth, renderedHeight, page }) {
  if (!Array.isArray(rooms)) return [];
  const losers = duplicatePolygonLosers(rooms, page);
  return rooms
    .filter((r) => roomPageOf(r) === page)
    .filter((r) => !losers.has(String(r.nr)))
    .map((r) => buildRoomZone(r, { renderedWidth, renderedHeight }))
    .filter(Boolean);
}

/**
 * A room's area as every room surface prints it — the drawing's chip and the panel's room list — with two
 * decimals, the way the eksplikacija writes it („4,48", „6,90"). 2026-10-18 audit side finding F: the chip
 * rounded to one decimal („4,5 m²") while the list said „4,48" for the same room. '—' when there is none.
 */
export function roomAreaText(m2) {
  const v = Number(m2);
  if (m2 == null || m2 === '' || !Number.isFinite(v)) return '—';
  return v.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/**
 * The "rooms we could not place" chip's sentence. It names the real place to fix it: the step „Patikra",
 * where the question list asks for a room the walls gave no outline and every room's sheet has
 * „Parodyti patalpą" (2026-10-18 audit side finding D — it sent him to „Peržiūra", a screen that is gone).
 */
export function missingRoomsText(count) {
  return `${ltCount(count, 'patalpa', 'patalpos', 'patalpų')} be vietos plane — `
    + `parodykite ${ltPlural(count, 'ją', 'jas', 'jas')} žingsnyje „Patikra“`;
}

/**
 * countRoomsMissingGeometry — rooms on `page` we could NOT place on the plan.
 * Surfaced as an honest "N patalpų be vietos plane" chip (spec §9), never hidden.
 */
export function countRoomsMissingGeometry(rooms, { renderedWidth, renderedHeight, page }) {
  if (!Array.isArray(rooms)) return 0;
  const losers = duplicatePolygonLosers(rooms, page);
  return rooms
    .filter((r) => roomPageOf(r) === page)
    // a room merged into another („Sujungti", 2026-10-16) has its place: inside the room that took it
    .filter((r) => r?._konturas?.saltinis !== 'sujungta')
    .filter((r) => losers.has(String(r.nr)) || !buildRoomZone(r, { renderedWidth, renderedHeight }))
    .length;
}

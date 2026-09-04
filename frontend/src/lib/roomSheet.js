/**
 * roomSheet.js — the pure logic behind „Kambario tikrinimo lapas".
 *
 * The screen itself (pages/RoomSheet.jsx + components/roomsheet/) only renders
 * what the two read-only endpoints already say. Everything here is a decision
 * ABOUT that payload — ordering, styling, the walk's arithmetic, the corner
 * derivation and the ripple sentence — kept out of the components so it can be
 * tested without a DOM and so the contract rules stay in one readable place.
 *
 * Contract this module must not blur (docs/ARCHITECTURE.md § "Room facts +
 * evidence"):
 *  - `source.kind` says where the VALUE came from; `source.page`/`rect_pct` say
 *    where to LOOK. They differ on purpose (openings: sizes from the žiniaraštis,
 *    crop framing the room), so nothing here derives one from the other.
 *  - A rectangle is only ever offered on the page it was measured on. No rect
 *    ⇒ the crop is the whole sheet, and we SAY so rather than implying a
 *    pinpoint (`isWholeSheet`).
 *  - `quantities[]` come from the ledger. We never re-sum them client-side and
 *    never invent a per-room decomposition the builder did not emit.
 *  - Openings have no coordinates — ever. `cornersFromPolygon` is the only
 *    geometry we derive, and only from a polygon that actually exists.
 */

import { ltNumber } from './ledger.js';
import { ltPlural } from './ltPlural.js';

/** Drawing-order of the six facts, as the founder's sheet lists them. */
export const FACT_ORDER = Object.freeze([
  'plotas', 'perimetras', 'aukstis', 'apdaila', 'angos', 'grindys',
]);

/** Seconds a contractor is assumed to spend on one unchecked room. */
export const SECONDS_PER_ROOM = 15;

/**
 * Facts in the sheet's order. Unknown keys keep their payload order and go
 * last — a new fact key from the backend must show up, not vanish.
 */
export function orderFacts(facts) {
  const list = Array.isArray(facts) ? facts.filter(Boolean) : [];
  const rank = (fact) => {
    const i = FACT_ORDER.indexOf(fact?.key);
    return i === -1 ? FACT_ORDER.length : i;
  };
  return list
    .map((fact, i) => ({ fact, i }))
    .sort((a, b) => (rank(a.fact) - rank(b.fact)) || (a.i - b.i))
    .map((x) => x.fact);
}

/**
 * The row's visual tone. Deliberately NOT a confidence scale: `read` is the
 * quiet default, and both `assumed` and `missing` render the same amber
 * "there is a blank here for you" treatment — the difference between them is
 * whether the field arrives prefilled, which the renderer reads off `status`.
 */
export function factTone(status) {
  return status === 'assumed' || status === 'missing' ? 'attention' : 'plain';
}

/** An `assumed`/`missing` fact opens with its editor already showing. */
export function factNeedsInput(fact) {
  return factTone(fact?.status) === 'attention';
}

/** `missing` has no value to prefill; `assumed` carries the default we chose. */
export function prefillValue(fact) {
  if (!fact || fact.status === 'missing') return '';
  return fact.value == null ? '' : String(fact.value);
}

/**
 * No rect ⇒ the evidence is the whole sheet. The caption must say so: the
 * 2026-05 browser-side highlight is the post-mortem for implying a pinpoint
 * the data cannot support.
 */
export function isWholeSheet(fact) {
  const rect = fact?.source?.rect_pct;
  if (!Array.isArray(rect) || rect.length !== 4) return true;
  // A full-page rect is a whole sheet too, however it was spelled.
  const [x0, y0, x1, y1] = rect.map(Number);
  return (x1 - x0) >= 0.999 && (y1 - y0) >= 0.999;
}

// ── The walk ────────────────────────────────────────────────────────────────

function numericPrefix(value) {
  const m = String(value ?? '').match(/^\s*(\d+)/);
  return m ? Number(m[1]) : Number.POSITIVE_INFINITY;
}

function compareRooms(a, b) {
  const pa = Number(a?.puslapio_nr);
  const pb = Number(b?.puslapio_nr);
  const na = Number.isFinite(pa) ? pa : Number.POSITIVE_INFINITY;
  const nb = Number.isFinite(pb) ? pb : Number.POSITIVE_INFINITY;
  if (na !== nb) return na - nb;
  const ia = numericPrefix(a?.nr);
  const ib = numericPrefix(b?.nr);
  if (ia !== ib) return ia - ib;
  return String(a?.nr ?? '').localeCompare(String(b?.nr ?? ''), 'lt');
}

/**
 * The rooms to walk, in drawing order: `v8_rooms` when the blob has them,
 * else `patalpos` (older blobs), ordered by page then room number.
 */
export function roomsInDrawingOrder(project) {
  const v8 = project?.v8_rooms;
  const raw = Array.isArray(v8) && v8.length ? v8 : (project?.patalpos || []);
  return (Array.isArray(raw) ? raw : [])
    .filter((r) => r && r.nr != null && String(r.nr) !== '')
    .slice()
    .sort(compareRooms);
}

export function roomName(room) {
  return room?.pavadinimas || room?.name || '';
}

/** „110 Miegamasis" — the room as the drawing prints it. */
export function roomTitle(room) {
  const nr = room?.nr == null ? '' : String(room.nr);
  const name = roomName(room);
  return [nr, name].filter(Boolean).join(' ');
}

export function isRoomVerified(room) {
  return Boolean(room?.user_verified_at);
}

export function roomIndex(rooms, roomNr) {
  return (rooms || []).findIndex((r) => String(r?.nr) === String(roomNr));
}

/** Minutes left at SECONDS_PER_ROOM per unchecked room; never says "0 min". */
export function estimateMinutes(uncheckedCount, secondsPerRoom = SECONDS_PER_ROOM) {
  const n = Math.max(0, Math.floor(Number(uncheckedCount) || 0));
  if (n === 0) return 0;
  return Math.max(1, Math.ceil((n * secondsPerRoom) / 60));
}

/** Everything the top strip needs, from the rooms' own verification stamps. */
export function progressSummary(rooms) {
  const list = Array.isArray(rooms) ? rooms : [];
  const total = list.length;
  const verified = list.filter(isRoomVerified).length;
  const unchecked = Math.max(0, total - verified);
  return {
    total,
    verified,
    unchecked,
    minutes: estimateMinutes(unchecked),
    percent: total ? Math.round((verified / total) * 100) : 0,
  };
}

// ── Corners from the outline ────────────────────────────────────────────────

function dedupe(points, minGap) {
  const out = [];
  points.forEach((p) => {
    const last = out[out.length - 1];
    if (last && Math.hypot(p[0] - last[0], p[1] - last[1]) < minGap) return;
    out.push(p);
  });
  // Closing vertex repeats the first on most emitters.
  while (out.length > 1) {
    const first = out[0];
    const last = out[out.length - 1];
    if (Math.hypot(first[0] - last[0], first[1] - last[1]) < minGap) out.pop();
    else break;
  }
  return out;
}

/**
 * K1…Kn from the room outline — the vertices where the wall actually changes
 * direction, not every point the tracer emitted. A flood-filled polygon is a
 * staircase of near-collinear points; labelling all of them would put twenty
 * „kampai" on a rectangular room and make the marks worthless.
 *
 * Returns [] when there is no polygon: the sheet then draws no corner dots at
 * all rather than inventing them from a bounding box.
 */
export function cornersFromPolygon(polygon, { minGap = 0.004, minAngleDeg = 12 } = {}) {
  const pts = (Array.isArray(polygon) ? polygon : [])
    .map((p) => (Array.isArray(p) ? [Number(p[0]), Number(p[1])] : null))
    .filter((p) => p && Number.isFinite(p[0]) && Number.isFinite(p[1]));
  const ring = dedupe(pts, minGap);
  if (ring.length < 3) return [];

  const sinTol = Math.sin((minAngleDeg * Math.PI) / 180);
  const kept = [];
  for (let i = 0; i < ring.length; i += 1) {
    const prev = ring[(i - 1 + ring.length) % ring.length];
    const here = ring[i];
    const next = ring[(i + 1) % ring.length];
    const ax = here[0] - prev[0];
    const ay = here[1] - prev[1];
    const bx = next[0] - here[0];
    const by = next[1] - here[1];
    const la = Math.hypot(ax, ay);
    const lb = Math.hypot(bx, by);
    if (la === 0 || lb === 0) continue;
    const sin = Math.abs((ax * by - ay * bx) / (la * lb));
    if (sin < sinTol) continue;   // walks straight through — not a corner
    kept.push(here);
  }
  return kept.map((p, i) => ({ label: `K${i + 1}`, x: p[0], y: p[1] }));
}

/** Does this quantity's own arithmetic count corners? (kampai emit terms.) */
export function hasCornerTerms(terms) {
  if (!terms || typeof terms !== 'object') return false;
  return Object.keys(terms).some((k) => String(k).toLowerCase().includes('kamp'));
}

/** `terms` as ordered [label, value] pairs for the expanded quantity line. */
export function termRows(terms) {
  if (!terms || typeof terms !== 'object') return [];
  return Object.entries(terms)
    .filter(([, v]) => v != null && Number.isFinite(Number(v)))
    .map(([label, value]) => ({ label, value: Number(value) }));
}

// ── Editing a quantity: what is honestly possible ───────────────────────────

/**
 * A per-room quantity override does not exist in the backend. What DOES exist
 * is a whole-row manual override (`lib/quantityOverride.js`). So the honest
 * rule: offer the edit only when this room is the row's ONLY contributor —
 * then "this room's share" and "the row" are the same number. Otherwise say
 * plainly that the room's slice cannot be corrected yet, and point at the two
 * things that can (the fact above, or the whole row in the sąmata).
 *
 * `contributions_sum_to_total: false` (a capped or anchored line) also blocks
 * it: the room may be the only contributor and STILL not be what the line
 * bills, so writing its value onto the row would change a number the user did
 * not touch.
 */
export function canOverrideWholeRow(quantity, rows, roomNr) {
  const row = findRowForQuantity(rows, quantity);
  if (!row) return false;
  if (row.contributions_sum_to_total === false) return false;
  const contributions = Array.isArray(row.contributions) ? row.contributions : [];
  if (contributions.length !== 1) return false;
  return String(contributions[0]?.room_nr ?? '') === String(roomNr ?? '');
}

/** The row behind a quantity line, matched by the ledger's stable id. */
export function findRowForQuantity(rows, quantity) {
  const id = quantity?.row_id;
  if (!id) return null;
  return (rows || []).find((r) => r && (r.id || r._id) === id) || null;
}

/**
 * The id `lib/quantityOverride.js` matches on — which is NOT the ledger id.
 * That module predates stable row ids and still keys on `_id` else
 * `eil_nr-aprasymas`; real blobs carry `id` and no `_id`, so handing it a
 * `row_id` matches nothing and returns the rows unchanged — a silent no-op
 * that looks exactly like a saved edit. Translate deliberately instead.
 */
export function legacyRowKey(row) {
  if (!row) return null;
  return row._id || `${row.eil_nr}-${row.aprasymas}`;
}

/**
 * `updatePositionQuantity` rewrites EVERY row whose legacy key matches, so an
 * override is only safe when the key picks out one row. Two rows sharing an
 * eilės nr and a label would both be overwritten from one click.
 */
export function legacyKeyIsUnique(rows, row) {
  const key = legacyRowKey(row);
  if (key == null) return false;
  return (rows || []).filter((r) => legacyRowKey(r) === key).length === 1;
}

// ── The ripple ──────────────────────────────────────────────────────────────

function qtyOf(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Reduce a `diffDarbuSarasas` result to the one sentence the room sheet shows:
 * how many rows moved, and the biggest single move in its own unit. Prices are
 * not the headline here — the contractor is checking quantities, and most rows
 * carry no price yet during Patikra.
 */
export function summarizeRipple(diff) {
  const changed = Array.isArray(diff?.changed) ? diff.changed : [];
  let top = null;
  changed.forEach((c) => {
    const delta = qtyOf(c?.after) - qtyOf(c?.before);
    if (!Number.isFinite(delta) || Math.abs(delta) < 0.005) return;
    if (!top || Math.abs(delta) > Math.abs(top.delta)) {
      top = {
        aprasymas: c?.row?.aprasymas || '',
        unit: c?.row?.mato_vnt || c?.row?.unit || '',
        delta,
      };
    }
  });
  return {
    count: Number(diff?.count) || 0,
    deltaEur: Number(diff?.deltaEur) || 0,
    usePrices: Boolean(diff?.usePrices),
    top,
  };
}

/**
 * „Persiskaičiavo 3 eilutes · Sienų dažymas +12,4 m²" — built through `t` so
 * the strings live in lt.json/en.json, but assembled here so the pluralisation
 * and the sign are testable without a DOM.
 */
export function rippleText(diff, t) {
  const s = summarizeRipple(diff);
  if (!s.count) return t('project.roomSheet.rippleNone');
  const rowsWord = ltPlural(s.count, 'eilutė', 'eilutės', 'eilučių');
  if (!s.top) return t('project.roomSheet.rippleRows', { count: s.count, rowsWord });
  const sign = s.top.delta >= 0 ? '+' : '−';
  const delta = `${sign}${ltNumber(Math.abs(s.top.delta), 2)}${s.top.unit ? ` ${s.top.unit}` : ''}`;
  return t('project.roomSheet.rippleTop', {
    count: s.count, rowsWord, label: s.top.aprasymas, delta,
  });
}

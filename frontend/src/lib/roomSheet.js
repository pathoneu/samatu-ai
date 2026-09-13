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

/** i18n key of each fact's title — the row's heading and the plan's mark share it. */
export const FACT_LABEL_KEY = Object.freeze({
  plotas: 'factPlotas',
  perimetras: 'factPerimetras',
  aukstis: 'factAukstis',
  apdaila: 'factApdaila',
  angos: 'factAngos',
  grindys: 'factGrindys',
});

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

/**
 * `missing` has no value to prefill; `assumed` carries the default we chose.
 * A number comes back with an LT decimal COMMA — `parseLtNumber` accepts either,
 * but a field that opens showing "2.8" in an app that writes "2,8" everywhere
 * else reads as someone else's number.
 */
export function prefillValue(fact) {
  if (!fact || fact.status === 'missing') return '';
  if (fact.value == null) return '';
  return typeof fact.value === 'number'
    ? String(fact.value).replace('.', ',')
    : String(fact.value);
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

/**
 * The same `user_verified_at` stamp on the room in a second list.
 *
 * `projectStore.markRoomVerified` writes onto `patalpos` only, but a v8 blob
 * carries BOTH lists and this walk reads `v8_rooms` first — so the canonical
 * write alone left the counter reading „Patikrinta 0 iš 11" after a room was
 * verified (seen in the browser). Mirroring here keeps the two lists agreeing
 * without touching the store. If `markRoomVerified` ever stamps both, this
 * becomes a harmless no-op rather than a conflict.
 */
export function stampVerified(rooms, roomNr, at) {
  return (Array.isArray(rooms) ? rooms : []).map((r) => (
    String(r?.nr) === String(roomNr) ? { ...r, user_verified_at: at } : r
  ));
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

// ── Placing an overlay on a crop ────────────────────────────────────────────

/**
 * The evidence endpoint does NOT render the rectangle you ask for — it grows it
 * by PAD_PCT, then up to a legibility floor, then slides it back inside the
 * sheet. Overlay coordinates arrive in PAGE percent, so drawing them on the
 * returned image without reproducing that growth puts every mark in the wrong
 * place. These mirror `backend/api/evidence.py::_padded` exactly.
 *
 * ⚠️ The three constants below are a copy. If they move in evidence.py they
 * must move here in the same commit, or the outline slides off its room.
 * Verified against the live endpoint 2026-09-04: for five rects (including
 * both floors firing) the returned pixel size divided by the predicted padded
 * size is the same page constant to within integer rounding.
 */
export const CROP_PAD_PCT = 0.012;
export const CROP_MIN_W_PCT = 0.10;
export const CROP_MIN_H_PCT = 0.045;

export function paddedCropRect(rect) {
  if (!Array.isArray(rect) || rect.length !== 4) return [0, 0, 1, 1];
  let [x0, y0, x1, y1] = rect.map(Number);
  if (![x0, y0, x1, y1].every(Number.isFinite)) return [0, 0, 1, 1];
  if (x1 < x0) [x0, x1] = [x1, x0];
  if (y1 < y0) [y0, y1] = [y1, y0];
  x0 -= CROP_PAD_PCT; y0 -= CROP_PAD_PCT;
  x1 += CROP_PAD_PCT; y1 += CROP_PAD_PCT;
  if (x1 - x0 < CROP_MIN_W_PCT) {
    const cx = (x0 + x1) / 2;
    x0 = cx - CROP_MIN_W_PCT / 2; x1 = cx + CROP_MIN_W_PCT / 2;
  }
  if (y1 - y0 < CROP_MIN_H_PCT) {
    const cy = (y0 + y1) / 2;
    y0 = cy - CROP_MIN_H_PCT / 2; y1 = cy + CROP_MIN_H_PCT / 2;
  }
  // Slide, don't squash — the requested region must stay inside the crop.
  if (x0 < 0) { x1 = Math.min(1, x1 - x0); x0 = 0; }
  if (x1 > 1) { x0 = Math.max(0, x0 - (x1 - 1)); x1 = 1; }
  if (y0 < 0) { y1 = Math.min(1, y1 - y0); y0 = 0; }
  if (y1 > 1) { y0 = Math.max(0, y0 - (y1 - 1)); y1 = 1; }
  return [Math.max(0, x0), Math.max(0, y0), Math.min(1, x1), Math.min(1, y1)];
}

/**
 * A page-percent point as a percentage of the rendered crop. `inside` is false
 * when the point falls outside the image — the renderer then draws nothing
 * rather than a mark clamped to the edge, which would point at the wrong place.
 */
export function pageToCropPct(point, cropRect) {
  const [x0, y0, x1, y1] = cropRect;
  const w = x1 - x0;
  const h = y1 - y0;
  if (!(w > 0) || !(h > 0) || !Array.isArray(point)) {
    return { x: 0, y: 0, inside: false };
  }
  const x = (Number(point[0]) - x0) / w;
  const y = (Number(point[1]) - y0) / h;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return { x: 0, y: 0, inside: false };
  return { x, y, inside: x >= 0 && x <= 1 && y >= 0 && y <= 1 };
}

/** A whole polygon mapped onto the crop; null when nothing lands inside it. */
/**
 * Where each fact was read on the sheet, in the crop's own fractions — the
 * marks the plan pane draws on the WHOLE page so the reader keeps their
 * bearings instead of being dropped into a zoomed corner (founder,
 * 2026-09-13). Facts on another page, whole-sheet facts and rectangles that
 * fall outside the crop are left out.
 */
export function factMarks(facts, page, cropRect, roomRegion = null) {
  if (!Array.isArray(facts) || page == null) return [];
  const out = [];
  for (const f of facts) {
    const src = f?.source;
    if (!src || Number(src.page) !== Number(page) || isWholeSheet(f)) continue;
    // A fact with no place of its own (doors and windows the drawing does not
    // position, a finish read from a table) is cropped on the ROOM's region as
    // a fallback. Drawing that as „where the number was read" says the
    // opposite of the truth (founder, 2026-09-13: „perimetras taip ir
    // suskaičiuotas kaip apibrėžta čia?"), so only a place the fact really has
    // becomes a mark.
    if (sameRect(src.rect_pct, roomRegion)) continue;
    const [x0, y0, x1, y1] = src.rect_pct.map(Number);
    const a = pageToCropPct([Math.min(x0, x1), Math.min(y0, y1)], cropRect);
    const b = pageToCropPct([Math.max(x0, x1), Math.max(y0, y1)], cropRect);
    const left = Math.max(0, a.x);
    const top = Math.max(0, a.y);
    const right = Math.min(1, b.x);
    const bottom = Math.min(1, b.y);
    if (right - left <= 0 || bottom - top <= 0) continue;   // entirely outside the crop
    out.push({ key: f.key, x: left, y: top, w: right - left, h: bottom - top });
  }
  return out;
}

function sameRect(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== 4 || b.length !== 4) return false;
  return a.every((v, i) => Math.abs(Number(v) - Number(b[i])) < 1e-4);
}

export function polygonToCropPct(polygon, cropRect) {
  const pts = (Array.isArray(polygon) ? polygon : [])
    .map((p) => pageToCropPct(p, cropRect));
  if (!pts.length || !pts.some((p) => p.inside)) return null;
  return pts;
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

// ── Opening counts ──────────────────────────────────────────────────────────

/**
 * The `angos` fact's `details[]` are a VIEW of the room's `elementai`; the count
 * is edited on `elementai`, so the two must be joined. There is no id to join
 * on, so the key is what both carry: tipas + the two mm sizes.
 *
 * `elementai` also holds entries the fact never shows — LED niches among them.
 * Matching on the size triple keeps those untouched; matching on `tipas` alone
 * would eventually decrement a niche.
 */
function sameOpening(el, detail) {
  return String(el?.tipas ?? '') === String(detail?.tipas ?? '')
    && Number(el?.plotis_mm ?? NaN) === Number(detail?.plotis_mm ?? NaN)
    && Number(el?.aukstis_mm ?? NaN) === Number(detail?.aukstis_mm ?? NaN);
}

/**
 * `elementai` with one opening's count moved by `delta`, clamped at zero.
 * Only the FIRST match moves — two identical entries are two separate rows in
 * the fact list, and the stepper the user pressed belongs to one of them.
 */
export function adjustOpeningCount(elementai, detail, delta) {
  const list = Array.isArray(elementai) ? elementai : [];
  const step = Number(delta) || 0;
  let done = false;
  return list.map((el) => {
    if (done || !sameOpening(el, detail)) return el;
    done = true;
    const next = Math.max(0, (Number(el.kiekis) || 0) + step);
    return { ...el, kiekis: next };
  });
}

/**
 * The room patch for a fact he typed on the sheet, WITH the marker that says
 * so. Without the marker a typed perimeter read „pagal sienų kontūrą" on the
 * sheet, and a re-read of the drawing (lib/mergeReextract.js) had no way to
 * tell his number from the reader's and overwrote it (2026-09-13).
 */
export function userEditPatch(field, value, now = new Date().toISOString()) {
  if (field === 'plotas_m2' || field === 'perimetras_m') {
    return { [field]: value, [`${field.replace(/_m2?$/, '')}_saltinis`]: 'user_override' };
  }
  if (field === 'paskirtis') return { paskirtis: value, _paskirtis_user_at: now };
  return { [field]: value };
}

/** The room patch for openings he corrected on the sheet, marked as his. */
export function openingsPatch(elementai, now = new Date().toISOString()) {
  return { elementai, _angos_user_at: now };
}

/** Total openings after an adjustment — what the fact's value will become. */
export function countOpenings(elementai, kinds = ['langas', 'duris']) {
  return (Array.isArray(elementai) ? elementai : [])
    .filter((el) => kinds.includes(String(el?.tipas ?? '')))
    .reduce((sum, el) => sum + (Number(el.kiekis) || 0), 0);
}

// ── Shared facts (the „Bendri dalykai" step) ────────────────────────────────

/**
 * Which drawing a symbol family was counted on, most specific first. The count
 * itself lives in `detected_symbols_summary` with no page on it, so this is the
 * mapping that lets the panel show the right sheet — and the reason a fallback
 * chain exists rather than one guess: a project may have no ceiling plan, and a
 * crop of the wrong sheet is worse than a crop of a plausible one.
 */
const SYMBOL_PAGES = {
  rozetes: ['electrical'],
  jungikliai: ['electrical'],
  sviestuvai: ['ceiling_plan', 'electrical'],
  pakabinami_sviestuvai: ['ceiling_plan', 'electrical'],
  led_juostos: ['ceiling_plan', 'electrical'],
  difuzoriai: ['ceiling_plan', 'plumbing'],
  kondicionieriai: ['ceiling_plan', 'electrical'],
  klozetai: ['plumbing'],
  praustuves: ['plumbing'],
  vonios: ['plumbing'],
  trapai: ['plumbing'],
  wc_remai: ['plumbing'],
  gyvatukai: ['plumbing'],
  radiatoriai: ['plumbing'],
};

export function symbolPageTypes(key) {
  return SYMBOL_PAGES[key] || ['floor_plan'];
}

/** The first page of any of `types`, in the order given. */
export function firstPageOfType(pages, types) {
  const list = Array.isArray(pages) ? pages : [];
  for (const tipas of types || []) {
    const hit = list.find((p) => p && p.tipas === tipas);
    if (hit) return Number(hit.nr) || null;
  }
  return null;
}

/**
 * The shared facts worth a check, as rows. A zero count is dropped: „Radiatoriai
 * 0" is not a fact he can check against a drawing, it is the absence of one.
 */
export function symbolRows(project) {
  const summary = project?.detected_symbols_summary;
  if (!summary || typeof summary !== 'object') return [];
  const pages = project?.puslapiai || project?.v8_pages || [];
  return Object.entries(summary)
    .filter(([, v]) => Number(v) > 0)
    .map(([key, value]) => ({
      key,
      value: Number(value),
      page: firstPageOfType(pages, symbolPageTypes(key)),
    }));
}

// ── The author's own figures (2026-09-06) ───────────────────────────────────
// Designers total their own drawing in a legend („Glaistoma dažoma 202 m²",
// „Sienų dažai 320 m²", „Parketlentės 135 m²"). The backend reads them from the
// PDF text (`_autoriaus_kiekiai`); the sheet shows each one with OUR number for
// the same family beside it. A reference to compare against — never a value we
// take: the engine computes from the drawing, other people's numbers only check.

const AUTHOR_FAMILY_OURS = {
  grindu_danga: { unit: 'm2', match: /parketo \/ laminato klojimas|grindų dangos klojimas/i },
  grindjuostes: { unit: 'm', match: /^grindjuosčių sumontavimas/i },
  // „Grindjuostės (iš plytelių)" is the tile skirting — our cut-and-glue row, not the wooden one
  grindjuostes_plyteliu: { unit: 'm', match: /plytelių grindjuosčių/i },
  sienu_dazymas: { unit: 'm2', match: /^sienų glaistymas\/dažymas/i },
  lubu_dazymas: { unit: 'm2', match: /^lubų glaistymas\/dažymas/i },
  // tiles only when the label says which surface — a bare tile zone („Plytelių
  // klojimo 3,95 m²") against every tiled wall and floor of the flat would mislead
  plyteles_sienos: { unit: 'm2', match: /sienų plytelių klijavimas|atatvaro plytelių klijavimas/i },
  plyteles_grindys: { unit: 'm2', match: /grindų plytelių klijavimas/i },
  karnizai: { unit: 'm', match: /^lubų karnizo sumontavimas/i },
  gkp: { unit: 'm2', match: /^gkp lubų montavimas/i },
};

/** The pairing key of a figure: its family, refined by the surface its label names. */
function pairingFamily(f) {
  const l = String(f.label || '').toLowerCase();
  if (f.family === 'grindjuostes') return /plytel/.test(l) ? 'grindjuostes_plyteliu' : 'grindjuostes';
  if (f.family !== 'plyteles') return f.family;
  if (/sien/.test(l)) return 'plyteles_sienos';
  if (/grind/.test(l)) return 'plyteles_grindys';
  return null;
}

const UNIT_ALIASES = { 'm²': 'm2', m2: 'm2', m: 'm', 'vnt.': 'vnt', vnt: 'vnt', kompl: 'kompl', 'kompl.': 'kompl' };

function sameUnit(a, b) {
  const na = UNIT_ALIASES[String(a || '').trim().toLowerCase()] || String(a || '').trim().toLowerCase();
  const nb = UNIT_ALIASES[String(b || '').trim().toLowerCase()] || String(b || '').trim().toLowerCase();
  return na !== '' && na === nb;
}

/** Page-percent rectangle of a text-layer bbox (PDF points from the page top). */
export function bboxToRectPct(bbox, pageWidth, pageHeight, margin = 0.02) {
  if (!Array.isArray(bbox) || bbox.length !== 4) return null;
  const W = Number(pageWidth); const H = Number(pageHeight);
  if (!(W > 0) || !(H > 0)) return null;
  const [x0, top, x1, bottom] = bbox.map(Number);
  if ([x0, top, x1, bottom].some((v) => !Number.isFinite(v))) return null;
  const clamp = (v) => Math.round(Math.min(1, Math.max(0, v)) * 1e4) / 1e4;
  return [clamp(x0 / W - margin), clamp(top / H - margin), clamp(x1 / W + margin), clamp(bottom / H + margin)];
}

/**
 * The designer's figures with our counterpart beside each:
 *   { key, label, value, unit, family, page, rect,
 *     ours: { value, unit, rows } | null,          — our family total, same unit
 *     group: { size, designerTotal } | null }      — when the designer split the
 *                                                     family over several figures
 * A designer often states one family in parts („Glaistoma dažoma (baltai)
 * 202 m²" + „(akcentinė spalva) 18 m²"): each part is listed, and OUR number is
 * compared with the parts' SUM, once, on the group — a part against our whole
 * would read as a wrong number. `ours` sums every row of the family in the
 * same unit (walls iki + virš 3 m); null when we emit nothing comparable — the
 * sheet then says so rather than inventing a pairing.
 */
export function authorFigureRows(project) {
  const figs = Array.isArray(project?._autoriaus_kiekiai) ? project._autoriaus_kiekiai : [];
  const rows = Array.isArray(project?.darbu_sarasas) ? project.darbu_sarasas : [];
  const clean = figs.filter((f) => f && Number.isFinite(Number(f.value)) && Number(f.value) > 0);
  const oursFor = (pairKey, unit) => {
    const fam = AUTHOR_FAMILY_OURS[pairKey];
    if (!fam || !sameUnit(unit, fam.unit)) return null;
    const hits = rows.filter((r) => fam.match.test(String(r?.aprasymas || ''))
      && sameUnit(r?.mato_vnt, fam.unit) && Number.isFinite(Number(r?.kiekis)));
    if (!hits.length) return null;
    return {
      value: Math.round(hits.reduce((n, r) => n + Number(r.kiekis), 0) * 100) / 100,
      unit: fam.unit,
      rows: hits.map((r) => r.aprasymas),
    };
  };
  // group the designer's parts: same pairing family + unit
  const groups = new Map();
  clean.forEach((f) => {
    const pk = pairingFamily(f);
    const unit = UNIT_ALIASES[String(f.unit || '').toLowerCase()] || String(f.unit || '');
    const gk = pk ? `${pk}|${unit}` : null;
    if (gk) {
      const g = groups.get(gk) || { size: 0, designerTotal: 0 };
      g.size += 1; g.designerTotal = Math.round((g.designerTotal + Number(f.value)) * 100) / 100;
      groups.set(gk, g);
    }
  });
  const out = clean.map((f, i) => {
    const pk = pairingFamily(f);
    const unit = UNIT_ALIASES[String(f.unit || '').toLowerCase()] || String(f.unit || '');
    const ours = pk ? oursFor(pk, unit) : null;
    const g = pk ? groups.get(`${pk}|${unit}`) : null;
    return {
      key: `${f.page}-${i}`,
      label: String(f.label || '').trim(),
      value: Number(f.value),
      unit,
      family: f.family || null,
      pairKey: pk,
      page: f.page ?? null,
      rect: bboxToRectPct(f.bbox, f.page_width, f.page_height),
      ours,
      group: g && g.size > 1 ? { size: g.size, designerTotal: g.designerTotal } : null,
    };
  });
  // paired families first, their parts kept together; page order otherwise
  const firstIndex = new Map();
  out.forEach((r, i) => { const k = r.pairKey ? `${r.pairKey}|${r.unit}` : `solo-${i}`; if (!firstIndex.has(k)) firstIndex.set(k, i); });
  return out.map((r, i) => [r, i]).sort((a, b) => {
    const pa = Number(!!a[0].ours); const pb = Number(!!b[0].ours);
    if (pa !== pb) return pb - pa;
    const ka = a[0].pairKey ? `${a[0].pairKey}|${a[0].unit}` : `solo-${a[1]}`;
    const kb = b[0].pairKey ? `${b[0].pairKey}|${b[0].unit}` : `solo-${b[1]}`;
    return (firstIndex.get(ka) - firstIndex.get(kb)) || (a[1] - b[1]);
  }).map(([r]) => r);
}

/** `detected_symbols_summary` with one family's count changed, clamped at 0. */
export function setSymbolCount(summary, key, value) {
  const n = Math.max(0, Math.round(Number(value) || 0));
  return { ...(summary || {}), [key]: n };
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

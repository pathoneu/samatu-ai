/**
 * Reading the contribution ledger — formatting only, never arithmetic.
 *
 * The backend (`extractor/ledger.py`) emits, per sąmata line, WHICH rooms
 * produced the number (`contributions[]`), which rooms it deliberately left out
 * (`excluded[]`) and the chain that turns the rooms into the billed quantity
 * (`roll_up[]`). Every `roll_up[].value` is the RUNNING RESULT after that step,
 * so the last one equals `kiekis` — a delta only ever appears in `note`.
 *
 * The rule this module exists to enforce: **the frontend renders the server's
 * numbers and never re-derives them.** §1.4 of the 2026-09-02 transparency
 * research measured old project blobs already failing a client-side Σ check, so
 * a panel that "helpfully" re-added the contributions would print a
 * contradiction next to a correct total. Nothing here sums a contribution list
 * into a headline; the only additions are inside `termShare`, which compares
 * sub-terms with each other to decide which input a line leans on, and never
 * produces a displayed quantity.
 */

// Contribution units arrive in the builder's ASCII spelling; the app writes
// the typographic one everywhere else (`mato_vnt` is already "m²").
const UNIT_LABELS = { m2: 'm²', m3: 'm³' };

// A hand-added row's id (lib/darbuRows.js `manualRowId`). It never has a ledger
// and must not be shown the "detalizacija dar neprieinama" apology — nobody
// computed it, the user typed it.
const MANUAL_ROW_PREFIX = 'rnk-';

/**
 * Which room input a sub-term leans on.
 *
 * This is a display-layer dictionary over the CLOSED set of `terms` keys the
 * builder writes (`vision_call.py`: kampai, grindjuostės), not a second copy of
 * the builder's predicates — an unknown key yields no opinion instead of a
 * guess, which is the whole difference from the 2026-04-26 `_build_trace_links`
 * that this architecture rejects. Keep in sync when a family gains terms.
 */
const TERM_DRIVERS = {
  'vidiniai kampai': 'height',
  'pusiniai kampai': 'height',
  'angų atbrailos': 'openings',
  'perimetras': 'perimeter',
  'perimetras be durų': 'perimeter',   // legacy blobs (pre 2026-09-02 evening)
  'durys': 'openings',
  'atliekos 10 %': 'perimeter',
};

// Height sources that were READ off the drawing. Everything else — a section
// average spread over every room, a fallback, a clamp — is an assumption, and
// that is the difference the „Jautriausia vieta" line reports.
const HEIGHT_READ_SOURCES = new Set([
  'per_room', 'section_pjuvis', 'ceiling_plan_marker', 'ceiling_plan_annotation',
]);

// Areas taken from a structured table are the strongest number in the project.
const AREA_READ_SOURCES = new Set(['eksplikacija', 'specifikacija', 'isklotines']);

// `saltinis` in the contractor's words — used when a line has no per-room
// decomposition and all we can honestly say is where its number came from.
const SOURCE_LABELS = {
  eksplikacija: 'patalpų eksplikacija brėžinyje',
  specifikacija: 'specifikacijos lentelė',
  isklotines: 'sienų išklotinės',
  lubu_planas: 'lubų planas',
  simboliai_brezinyje: 'brėžinyje suskaičiuoti simboliai',
  skaiciuota_is_brezinio: 'skaičiavimas iš brėžinio matmenų',
  paskirtis_default: 'numatytoji reikšmė pagal patalpos paskirtį',
  'lubu_aukstis>3m': 'patalpos, aukštesnės nei 3 m',
  checklist: 'darbų sąrašo šablonas',
  baseline: 'bazinė prielaida',
};

export function unitLabel(unit) {
  const raw = String(unit ?? '').trim();
  return UNIT_LABELS[raw] || raw;
}

/** "501,3" → "501,30" — LT decimal comma, fixed digits, no thousands hair. */
export function ltNumber(value, digits = 2) {
  if (value == null || value === '' || !Number.isFinite(Number(value))) return '—';
  return Number(value).toLocaleString('lt-LT', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
}

export function ltQuantity(value, unit, digits = 2) {
  const num = ltNumber(value, digits);
  const suffix = unitLabel(unit);
  return suffix ? `${num} ${suffix}` : num;
}

export function ltEur(value, digits = 0) {
  if (value == null || !Number.isFinite(Number(value))) return '—';
  return `${Number(value).toLocaleString('lt-LT', {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  })} €`;
}

export function isManualRow(row) {
  return String(row?.id || '').startsWith(MANUAL_ROW_PREFIX);
}

export function hasLedger(row) {
  return Array.isArray(row?.roll_up) && row.roll_up.length > 0;
}

export function contributionsOf(row) {
  return Array.isArray(row?.contributions) ? row.contributions : [];
}

export function excludedOf(row) {
  return Array.isArray(row?.excluded) ? row.excluded : [];
}

/**
 * The roll-up as one line: „Σ 9 patalpų 437,70 → riba 0,65 m/m² 107,67".
 * Values come from the server verbatim; the arrow is punctuation, not maths.
 */
export function rollUpHeadline(rollUp, unit) {
  if (!Array.isArray(rollUp) || rollUp.length === 0) return null;
  return rollUp
    .map(step => `${step.label} ${ltQuantity(step.value, unit)}`)
    .join(' → ');
}

// Ops that state an external fact rather than derive one from the rooms. When
// any of them is in the chain, `Σ contributions` is NOT the billed quantity.
const NON_ADDITIVE_OPS = new Set(['anchor', 'cap', 'share', 'coefficient', 'constant']);

/**
 * True when the chain — not the contributions — is the number.
 *
 * The anchored ceiling bills the eksplikacija's own „Iš viso" minus the rooms
 * nobody paints, so its `contributions[]` are the drawing's per-room figures and
 * their Σ is deliberately NOT `kiekis`; a capped grindjuostės line bills less
 * than its rooms add up to. In both cases the UI must present the contributions
 * as supporting detail, never as an addition the reader can check in their head.
 */
export function rollUpIsAuthoritative(rollUp, row) {
  // The builder measures this directly (`contributions_sum_to_total`, since
  // 2026-09-02 evening): Σ contributions reproduces `kiekis` to ±0,01 or it
  // doesn't. Prefer the measurement over the op heuristic when it is present.
  if (row && typeof row.contributions_sum_to_total === 'boolean') {
    return !row.contributions_sum_to_total;
  }
  if (!Array.isArray(rollUp) || rollUp.length === 0) return false;
  if (rollUp[0]?.op !== 'sum') return true;
  return rollUp.some(step => NON_ADDITIVE_OPS.has(step?.op));
}

/** True when the quantity is a stated total, not one assembled from the rooms. */
export function hasAnchorStep(rollUp) {
  return (rollUp || []).some(s => s?.op === 'anchor');
}

/** The `anchor` step's own explanation, when the builder wrote one. */
export function anchorNote(rollUp) {
  const step = (rollUp || []).find(s => s?.op === 'anchor');
  return step?.note || null;
}

/**
 * The live row behind a captured one — but ONLY when the match is unambiguous.
 *
 * A merge can carry an orphaned prior row that keeps an id the rebuilt row also
 * has, so a duplicated id must never be allowed to resolve to "some row with
 * that id": it would silently show one line's ledger under another line's name.
 * A duplicate falls back to the label pair, exactly like an old blob with no id
 * at all, and an unresolvable row keeps the captured copy.
 */
export function findRowById(rows, row) {
  if (!row) return null;
  const list = rows || [];
  const key = row.id || row._id;
  if (key) {
    const hits = list.filter(r => (r.id || r._id) === key);
    if (hits.length === 1) return hits[0];
  }
  const byLabel = list.filter(r =>
    r.aprasymas === row.aprasymas && (r.skyrius || '') === (row.skyrius || ''));
  return byLabel.length === 1 ? byLabel[0] : null;
}

/** Contributions biggest-first — the order a contractor audits in. */
export function sortedContributions(contributions) {
  return [...(contributions || [])].sort(
    (a, b) => (Number(b?.value) || 0) - (Number(a?.value) || 0));
}

/**
 * Top `limit` contributions plus how many stay behind „rodyti visas (N)".
 * `hiddenCount` is 0 when the list already fits — the toggle should not appear.
 */
export function splitContributions(contributions, limit = 5) {
  const all = sortedContributions(contributions);
  if (all.length <= limit) return { shown: all, hiddenCount: 0, total: all.length };
  return { shown: all.slice(0, limit), hiddenCount: all.length - limit, total: all.length };
}

/** `terms` as ordered label/value pairs, dropping empty ones. */
export function termEntries(terms) {
  if (!terms || typeof terms !== 'object') return [];
  return Object.entries(terms)
    .filter(([, v]) => v != null && Number.isFinite(Number(v)))
    .map(([label, value]) => ({ label, value: Number(value) }));
}

/**
 * How much of a contribution a given driver accounts for, 0…1.
 *
 * With no terms the caller gets `null` — "no opinion" — which the sensitivity
 * pick reads as "this family has no sub-terms, so its headline input drives it".
 */
/** Which room input a single sub-term leans on, or null when we have no map. */
export function termDriver(label) {
  return TERM_DRIVERS[String(label ?? '')] || null;
}

export function termShare(terms, driver) {
  const entries = termEntries(terms);
  if (entries.length === 0) return null;
  const total = entries.reduce((s, e) => s + Math.abs(e.value), 0);
  if (!(total > 0)) return null;
  const matched = entries
    .filter(e => TERM_DRIVERS[e.label] === driver)
    .reduce((s, e) => s + Math.abs(e.value), 0);
  return matched / total;
}

export function isHeightRead(source) {
  return HEIGHT_READ_SOURCES.has(String(source || ''));
}

export function isAreaRead(source) {
  return AREA_READ_SOURCES.has(String(source || ''));
}

/** „patalpų eksplikacija brėžinyje" — or the raw key when it is a new one. */
export function sourceLabel(saltinis) {
  const raw = String(saltinis || '').trim();
  if (!raw) return null;
  return SOURCE_LABELS[raw] || raw;
}

/**
 * What the panel says instead of a tree, and why. Never a blank panel:
 * a hand-added row says so, a computed row without a ledger names its source.
 */
export function ledgerFallback(row) {
  if (isManualRow(row)) return { kind: 'manual' };
  return { kind: 'unwired', source: sourceLabel(row?.saltinis) };
}

/** The room object behind a contribution, so a jump carries its geometry. */
export function findRoom(rooms, roomNr) {
  if (roomNr == null) return null;
  return (rooms || []).find(r => String(r?.nr) === String(roomNr)) || null;
}

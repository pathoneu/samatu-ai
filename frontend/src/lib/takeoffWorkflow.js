import { CONF_RAUDONA, confidenceNeedsReview, confidenceRank, normalizeConfidence } from './confidence.js';
import { tierBaseLabel, tierKey } from './mergeDarbuSarasas.js';
import {
  contributionsOf, isAreaRead, isHeightRead, sortedContributions, termShare,
} from './ledger.js';

export const TAKEOFF_FILTER_MODES = {
  all: 'all',
  review: 'review',
  manual: 'manual',
  missing_price: 'missing_price',
};

export function isManualQuantity(row) {
  return row?.manual_override === true || row?.quantity_source === 'manual_override';
}

export function getQuantitySourceKind(row) {
  const source = String(row?.quantity_source || row?.saltinis || '').toLowerCase();
  if (isManualQuantity(row)) return 'manual';
  if (row?.user_verified_at) return 'verified';
  if (source === 'ai_symbol_candidate' || source === 'simboliai_brezinyje') return 'ai_symbol';
  if (source === 'room_type_assumption' || source === 'paskirtis_default') return 'assumption';
  if (source === 'project_assumption' || source === 'baseline' || source === 'lubu_aukstis>3m') return 'assumption';
  if (source === 'formula_estimate') return 'formula_estimate';
  return 'formula';
}

export function getQuantitySourceLabel(row) {
  const kind = getQuantitySourceKind(row);
  return {
    manual: 'Rankinis',
    verified: 'Patvirtinta',
    ai_symbol: 'AI ženklas',
    assumption: 'Prielaida',
    formula_estimate: 'Formulė',
    formula: 'Formulė',
  }[kind] || 'Formulė';
}

export function needsTakeoffReview(row) {
  if (isManualQuantity(row) || row?.user_verified_at) return false;
  if (row?._review_status === 'accepted' || row?._review_status === 'rejected') return false;
  if (row?.review_required === true) return true;
  return confidenceNeedsReview(row?.confidence);
}

export function isMissingPrice(row) {
  return !(Number(row?.kaina) > 0);
}

// € impact of a row: kiekis × kaina once prices exist, kiekis alone before —
// the review queue is ranked by what a wrong line costs, not by confidence.
export function getRowImpact(row, usePrices) {
  const kiekis = Number(row?.kiekis) || 0;
  if (!usePrices) return kiekis;
  return kiekis * (Number(row?.kaina) || 0);
}

function hasAnyPrice(rows = []) {
  return rows.some(row => Number(row?.kaina) > 0);
}

/**
 * A checklist row is the honest TODO the builder emits when it cannot compute a
 * quantity ("— m · suveskite ilgį"): kiekis is null (or the source says so).
 * There is nothing to VERIFY on it — „Teisinga" would be meaningless — so it
 * never becomes a Patikra card; it is offered separately as „Suveskite patys".
 * (2026-09-04: 60 of them sat on top of a 67-row queue and hid the real risk.)
 */
export function isChecklistRow(row) {
  if (!row) return false;
  if (row.saltinis === 'checklist') return true;
  return row.kiekis == null;
}

export function rankReviewRows(rows = []) {
  const usePrices = hasAnyPrice(rows);
  return rows
    .filter(row => needsTakeoffReview(row) && !isChecklistRow(row))
    .map(row => ({ row, impact: getRowImpact(row, usePrices) }))
    .sort((a, b) =>
      (b.impact - a.impact)
      || (confidenceRank(b.row?.confidence) - confidenceRank(a.row?.confidence))
      || ((a.row?.eil_nr || 0) - (b.row?.eil_nr || 0)))
    .map(entry => entry.row);
}

/**
 * Default review view: every raudona row plus the maxGeltona biggest geltona
 * rows by € impact; the rest stays collapsed. shareOfTotal is the fraction of
 * the whole estimate sum the primary rows represent (null before prices exist).
 */
export function selectReviewQueue(rows = [], { maxGeltona = 5, exclude = null } = {}) {
  const usePrices = hasAnyPrice(rows);
  const ranked = rankReviewRows(exclude ? rows.filter(row => !exclude(row)) : rows);

  const geltonaShown = new Set(
    ranked.filter(row => normalizeConfidence(row?.confidence) !== CONF_RAUDONA).slice(0, maxGeltona),
  );
  const primary = ranked.filter(row =>
    normalizeConfidence(row?.confidence) === CONF_RAUDONA || geltonaShown.has(row));
  const rest = ranked.filter(row => !primary.includes(row));

  const totalSum = rows.reduce((sum, row) => sum + getRowImpact(row, true), 0);
  const primarySum = primary.reduce((sum, row) => sum + getRowImpact(row, true), 0);
  const shareOfTotal = usePrices && totalSum > 0 ? primarySum / totalSum : null;

  // Rows the builder could not quantify — listed apart, never as claims.
  const pool = exclude ? rows.filter(row => !exclude(row)) : rows;
  const checklist = pool.filter(row => isChecklistRow(row) && !isRowVerified(row));

  return { ranked, primary, rest, checklist, usePrices, shareOfTotal };
}

export function getFirstReviewRow(rows = []) {
  return rankReviewRows(rows)[0] || null;
}

// "šią 1 eilutę" / "šias 6 eilutes" / "šias 11 eilučių" — LT numeral agreement
// for the review-queue copy.
export function ltEilutesPhrase(n) {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return `šią ${n} eilutę`;
  if (mod10 >= 2 && mod10 <= 9 && !(mod100 >= 11 && mod100 <= 19)) return `šias ${n} eilutes`;
  return `šias ${n} eilučių`;
}

export function getRowTargetPage(row, project = {}) {
  const eksplikacijaPage = project?._eksplikacija?.eksplikacija_source_page;
  if (row?.eksplikacija_row_bbox && eksplikacijaPage) return eksplikacijaPage;
  return row?.puslapio_nr || null;
}

export function filterTakeoffRows(rows = [], { query = '', mode = TAKEOFF_FILTER_MODES.all } = {}) {
  const normalizedQuery = String(query || '').trim().toLowerCase();
  return rows.filter((row) => {
    if (mode === TAKEOFF_FILTER_MODES.review && !needsTakeoffReview(row)) return false;
    if (mode === TAKEOFF_FILTER_MODES.manual && !isManualQuantity(row)) return false;
    if (mode === TAKEOFF_FILTER_MODES.missing_price && !isMissingPrice(row)) return false;
    if (!normalizedQuery) return true;
    const haystack = [
      row?.eil_nr,
      row?.nr,
      row?.aprasymas,
      row?.pavadinimas,
      row?.skyrius,
      row?.mato_vnt,
    ].filter(Boolean).join(' ').toLowerCase();
    return haystack.includes(normalizedQuery);
  });
}

// ── Patikra — the guided audit loop (2026-09-02) ─────────────────────────────
//
// Three pure pieces the rail renders: how much of the sąmata a human has
// actually stood behind (`trustMeter`), what the unchecked part is worth
// (`unverifiedRisk`), and which single input the biggest room in a line leans
// on (`pickSensitiveInput`) — plus the diff that turns a recompute into a
// visible „N eilučių · ±X €" (`diffDarbuSarasas`).

/**
 * A row a HUMAN has stood behind. Confidence does not count: the measured
 * false-green rate was 50–60 % before the confidence pass, so a meter that
 * green rows could raise would report trust nobody gave.
 */
export function isRowVerified(row) {
  return !!(row?.user_verified_at
    || row?._review_status === 'accepted'
    || isManualQuantity(row));
}

/**
 * The one line under the sąmata, in the contractor's own words:
 *
 *   „42 eilutės iš brėžinio, patikrintos 38 · 5 jūsų · 3 be kiekio“
 *
 * Four counts, no jargon, no percentage. `mine` is the rows he typed himself —
 * they carry the `rnk-` (rankinė) id `darbuRows.manualRowId` mints, which is
 * the only durable marker that survives a rebuild. `noQty` is the honest part:
 * rows nobody could give a number to, which he must fill in or delete before
 * the sąmata goes out.
 */
export function summarizeSamataRows(rows = []) {
  const all = Array.isArray(rows) ? rows.filter(Boolean) : [];
  const isMine = (r) => String(r?.id || r?._id || '').startsWith('rnk-');
  const fromDrawingRows = all.filter((r) => !isMine(r));
  return {
    total: all.length,
    fromDrawing: fromDrawingRows.length,
    verified: fromDrawingRows.filter(isRowVerified).length,
    mine: all.length - fromDrawingRows.length,
    noQty: all.filter((r) => !(Number(r?.kiekis) > 0)).length,
  };
}

/**
 * Share of the sąmata that has been verified by hand — by € once prices exist,
 * by kiekis before that (`usePrices` says which, so the UI can be honest).
 * An empty project reads 0, never 100.
 */
export function trustMeter(allRows = []) {
  // Checklist rows have no quantity to trust or distrust — they are the
  // contractor's own input, not a claim — so they are neither in the numerator
  // nor the denominator.
  const rows = (allRows || []).filter(row => !isChecklistRow(row));
  const usePrices = hasAnyPrice(rows);
  let total = 0;
  let verified = 0;
  let verifiedCount = 0;
  rows.forEach((row) => {
    const impact = getRowImpact(row, usePrices);
    total += impact;
    if (isRowVerified(row)) {
      verified += impact;
      verifiedCount += 1;
    }
  });
  return {
    usePrices,
    total,
    verified,
    verifiedCount,
    totalCount: rows.length,
    share: total > 0 ? verified / total : 0,
    // Before prices exist the € share is unavailable, and a Σ over kg + m² +
    // vnt. is not a number anybody can act on — so the meter falls back to the
    // share of ROWS, which at least means what it says.
    countShare: rows.length > 0 ? verifiedCount / rows.length : 0,
  };
}

/** What the rows still waiting for review are worth. */
export function unverifiedRisk(rows = []) {
  const usePrices = hasAnyPrice(rows);
  const pending = rows.filter(row => needsTakeoffReview(row) && !isChecklistRow(row));
  return {
    usePrices,
    count: pending.length,
    amount: pending.reduce((sum, row) => sum + getRowImpact(row, usePrices), 0),
  };
}

// How much of a contribution each candidate input drives, when the family has
// no sub-terms to say otherwise. Paint is perimeter × H with no terms at all,
// so the height is its whole story.
const NO_TERMS_DRIVER_SHARE = { height: 1, area: 0 };

function inputScore(driverShare, soft) {
  return driverShare + (soft ? 1 : 0);
}

/**
 * „Jautriausia vieta" — the one input this line leans on hardest, in the room
 * that contributes most to it.
 *
 * Scored, not guessed: each candidate gets the share of the top contribution it
 * drives (from the `terms` vocabulary, or the family default when a line has no
 * terms) plus a point when the room's source says the value was ASSUMED rather
 * than read off the drawing. Ties go to the height, because it multiplies.
 * A line with no contributions has nothing to point at and falls back to the
 * row's own `_confidence_reason`.
 */
export function pickSensitiveInput(row, rooms = []) {
  const reason = row?._confidence_reason || null;
  const contributions = sortedContributions(contributionsOf(row));
  const top = contributions[0];
  if (!top) return reason ? { kind: 'reason', reason } : null;

  const room = (rooms || []).find(r => String(r?.nr) === String(top.room_nr));
  if (!room) return reason ? { kind: 'reason', reason } : null;

  const heightSource = room.lubu_aukstis_saltinis;
  const areaSource = room.plotas_saltinis;
  const heightSoft = !isHeightRead(heightSource);
  const areaSoft = !isAreaRead(areaSource);

  const heightShare = termShare(top.terms, 'height') ?? NO_TERMS_DRIVER_SHARE.height;
  const areaShare = termShare(top.terms, 'perimeter') ?? NO_TERMS_DRIVER_SHARE.area;

  const height = {
    kind: 'height',
    value: Number(room.lubu_aukstis_m) || null,
    unit: 'm',
    source: heightSource || null,
    assumed: heightSoft,
    score: inputScore(heightShare, heightSoft),
  };
  const area = {
    kind: 'area',
    value: Number(room.plotas_m2) || null,
    unit: 'm²',
    source: areaSource || null,
    assumed: areaSoft,
    score: inputScore(areaShare, areaSoft),
  };
  const pick = area.score > height.score ? area : height;

  return {
    ...pick,
    reason,
    roomNr: top.room_nr,
    roomName: top.room_name,
    page: top.page ?? null,
    geometry: top.geometry || 'none',
    contributionValue: Number(top.value) || 0,
    contributionUnit: top.unit || row?.mato_vnt || '',
    // The share of the line this room alone accounts for — „nuo jos priklauso…"
    // is only worth saying when the room is actually a big part of the line.
    contributionShare: Number(row?.kiekis) > 0
      ? (Number(top.value) || 0) / Number(row.kiekis)
      : null,
  };
}

function rowSum(row) {
  return (Number(row?.kiekis) || 0) * (Number(row?.kaina) || 0);
}

/**
 * What a recompute actually moved — „Perskaičiuota: N eilučių · −212 €".
 *
 * Rows are matched by `id`, but ONLY while that id is unique on BOTH sides: a
 * merge can carry an orphaned prior row that keeps an id the rebuilt row also
 * has, and attributing an edit to the wrong line is worse than reporting one
 * fewer change. Ambiguous ids and old id-less blobs fall back to the
 * section+label pair, and anything still unmatched counts as added or removed.
 */
export function diffDarbuSarasas(prior = [], next = []) {
  // NUL as the separator: it cannot occur in a label, so 'A'+'BC' and 'AB'+'C'
  // never collide. Written as an escape - a literal NUL byte in the source made
  // grep/file treat this module as binary (2026-09-04).
  const labelOf = row => `${row?.skyrius || ''}\u0000${row?.aprasymas || ''}`;

  const index = (rows) => {
    const byId = new Map();
    const byLabel = new Map();
    rows.forEach((row) => {
      const id = row?.id || row?._id;
      if (id) byId.set(id, (byId.get(id) || []).concat(row));
      const label = labelOf(row);
      byLabel.set(label, (byLabel.get(label) || []).concat(row));
    });
    return { byId, byLabel };
  };

  const priorIdx = index(prior);
  const nextIdx = index(next);
  const matchInPrior = (row) => {
    const id = row?.id || row?._id;
    if (id) {
      const here = nextIdx.byId.get(id) || [];
      const there = priorIdx.byId.get(id) || [];
      if (here.length === 1 && there.length === 1) return there[0];
    }
    const label = labelOf(row);
    const hereL = nextIdx.byLabel.get(label) || [];
    const thereL = priorIdx.byLabel.get(label) || [];
    return (hereL.length === 1 && thereL.length === 1) ? thereL[0] : null;
  };

  const changed = [];
  const matched = new Set();
  let deltaEur = 0;
  next.forEach((row) => {
    const before = matchInPrior(row);
    if (before) matched.add(before);
    const beforeQty = before ? Number(before.kiekis) || 0 : null;
    const afterQty = Number(row.kiekis) || 0;
    const delta = rowSum(row) - (before ? rowSum(before) : 0);
    deltaEur += delta;
    if (before == null) {
      changed.push({ kind: 'added', row, before: null, after: afterQty, deltaEur: delta });
    } else if (Math.abs(afterQty - beforeQty) > 0.005) {
      changed.push({ kind: 'changed', row, before: beforeQty, after: afterQty, deltaEur: delta });
    }
  });
  prior.forEach((row) => {
    if (matched.has(row)) return;
    deltaEur -= rowSum(row);
    changed.push({
      kind: 'removed', row, before: Number(row.kiekis) || 0, after: null,
      deltaEur: -rowSum(row),
    });
  });

  const folded = foldTierMoves(changed);
  return {
    changed: folded,
    count: folded.length,
    deltaEur: Math.round(deltaEur * 100) / 100,
    usePrices: hasAnyPrice(next) || hasAnyPrice(prior),
  };
}

/**
 * A line that split into „… (iki 3m aukščio)" + „… (virš 3m aukščio)" — or
 * merged back — is ONE quantity that moved a little, not a row that vanished
 * and two that appeared. Reported raw, a 3,00 m ceiling on one room read
 * „Sienų glaistymas/dažymas −279,08 m²" (2026-09-08). Entries sharing a
 * section and a tier key, where at least one label carries a tier suffix and
 * something was added or removed, fold into a single `changed` entry on the
 * base label; a pure re-tiering that moved nothing is not a change at all.
 */
function foldTierMoves(changed) {
  const groups = new Map();
  changed.forEach((c) => {
    const key = `${c.row?.skyrius || ''}\u0000${tierKey(c.row?.aprasymas)}`;
    groups.set(key, (groups.get(key) || []).concat(c));
  });
  const out = [];
  groups.forEach((entries) => {
    const tiered = entries.some((c) => tierBaseLabel(c.row?.aprasymas) !== String(c.row?.aprasymas || '').trim());
    const moved = entries.some((c) => c.kind === 'added' || c.kind === 'removed');
    if (entries.length < 2 || !tiered || !moved) {
      out.push(...entries);
      return;
    }
    const before = entries.reduce((sum, c) => sum + (Number(c.before) || 0), 0);
    const after = entries.reduce((sum, c) => sum + (Number(c.after) || 0), 0);
    const eur = entries.reduce((sum, c) => sum + (Number(c.deltaEur) || 0), 0);
    if (Math.abs(after - before) <= 0.005 && Math.abs(eur) <= 0.005) return;
    const base = entries.find((c) => tierBaseLabel(c.row?.aprasymas) === String(c.row?.aprasymas || '').trim())?.row
      || entries[0].row;
    out.push({
      kind: 'changed',
      row: { ...base, aprasymas: tierBaseLabel(base.aprasymas) },
      before: Math.round(before * 100) / 100,
      after: Math.round(after * 100) / 100,
      deltaEur: Math.round(eur * 100) / 100,
      tiers: entries.map((c) => ({ kind: c.kind, aprasymas: c.row?.aprasymas, before: c.before, after: c.after })),
    });
  });
  return out;
}

export function summarizeTakeoffWorkflow(project = {}, { hasPdf = false } = {}) {
  const rows = project.darbu_sarasas || [];
  const rooms = project.v8_rooms || project.patalpos || [];
  const pages = project.puslapiai || project.v8_pages || [];
  const totalRows = rows.length;
  const reviewRows = rows.filter(needsTakeoffReview).length;
  const manualOverrides = rows.filter(isManualQuantity).length;
  const missingPrices = rows.filter(isMissingPrice).length;
  const totalRooms = rooms.length;
  const totalPages = pages.length;
  const totalArea = rooms.reduce((sum, room) => sum + (Number(room?.plotas_m2) || 0), 0);

  const aiSymbolRows = rows.filter(row => getQuantitySourceKind(row) === 'ai_symbol').length;
  const assumptionRows = rows.filter(row => getQuantitySourceKind(row) === 'assumption').length;
  const reviewPenalty = totalRows ? (reviewRows / totalRows) * 45 : 0;
  const sourcePenalty = totalRows ? ((aiSymbolRows * 1.5 + assumptionRows) / totalRows) * 10 : 0;
  const pricePenalty = totalRows ? (missingPrices / totalRows) * 35 : 0;
  const pdfPenalty = hasPdf ? 0 : 20;
  const readinessScore = Math.max(0, Math.round(100 - reviewPenalty - sourcePenalty - pricePenalty - pdfPenalty));

  return {
    totalRows,
    reviewRows,
    manualOverrides,
    missingPrices,
    totalRooms,
    totalPages,
    totalArea,
    aiSymbolRows,
    assumptionRows,
    hasPdf,
    readinessScore,
    readyForBeta: hasPdf && reviewRows === 0 && missingPrices === 0,
  };
}

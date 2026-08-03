import { CONF_RAUDONA, confidenceNeedsReview, confidenceRank, normalizeConfidence } from './confidence.js';

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

export function rankReviewRows(rows = []) {
  const usePrices = hasAnyPrice(rows);
  return rows
    .filter(needsTakeoffReview)
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

  return { ranked, primary, rest, usePrices, shareOfTotal };
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

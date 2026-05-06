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
  const confidence = String(row?.confidence || '').toLowerCase();
  if (isManualQuantity(row) || row?.user_verified_at) return false;
  if (row?.review_required === true) return true;
  return confidence === 'low' || confidence === 'medium';
}

export function isMissingPrice(row) {
  return !(Number(row?.kaina) > 0);
}

export function getFirstReviewRow(rows = []) {
  return rows.find(needsTakeoffReview) || null;
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

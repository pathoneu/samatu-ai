import test from 'node:test';
import assert from 'node:assert/strict';
import {
  filterTakeoffRows,
  getFirstReviewRow,
  getQuantitySourceKind,
  getQuantitySourceLabel,
  getRowImpact,
  getRowTargetPage,
  needsTakeoffReview,
  rankReviewRows,
  selectReviewQueue,
  summarizeTakeoffWorkflow,
} from './takeoffWorkflow.js';

// Production vocabulary is LT (backend extractor/confidence.py): zalia/geltona/raudona.
const rows = [
  { eil_nr: 1, aprasymas: 'Sienu dazymas', kiekis: 10, kaina: 5, confidence: 'zalia', mato_vnt: 'm2' },
  { eil_nr: 2, aprasymas: 'Rozetes', kiekis: 4, kaina: 0, confidence: 'geltona', mato_vnt: 'vnt' },
  { eil_nr: 3, aprasymas: 'Lubos', kiekis: 12, kaina: 3, confidence: 'raudona', manual_override: true },
  { eil_nr: 4, aprasymas: 'Grindjuostes', kiekis: 20, kaina: 0, confidence: 'zalia', quantity_source: 'manual_override' },
];

test('summarizeTakeoffWorkflow: counts review, manual and missing price rows (LT confidence vocabulary)', () => {
  const summary = summarizeTakeoffWorkflow({
    darbu_sarasas: rows,
    patalpos: [{ plotas_m2: 10 }, { plotas_m2: 12.5 }],
    puslapiai: [{}, {}, {}],
  }, { hasPdf: true });

  assert.equal(summary.totalRows, 4);
  assert.equal(summary.reviewRows, 1);
  assert.equal(summary.manualOverrides, 2);
  assert.equal(summary.missingPrices, 2);
  assert.equal(summary.totalRooms, 2);
  assert.equal(summary.totalPages, 3);
  assert.equal(summary.totalArea, 22.5);
  assert.equal(summary.aiSymbolRows, 0);
  assert.equal(summary.assumptionRows, 0);
  assert.equal(summary.hasPdf, true);
  assert.equal(summary.readyForBeta, false);
  assert.equal(summary.readinessScore, 71);
});

test('needsTakeoffReview: engine-flagged LT rows need review, zalia and unstamped rows do not', () => {
  assert.equal(needsTakeoffReview({ confidence: 'geltona' }), true);
  assert.equal(needsTakeoffReview({ confidence: 'raudona' }), true);
  assert.equal(needsTakeoffReview({ confidence: 'zalia' }), false);
  assert.equal(needsTakeoffReview({}), false);
});

test('needsTakeoffReview: legacy EN blobs (old localStorage caches) still flag correctly', () => {
  assert.equal(needsTakeoffReview({ confidence: 'medium' }), true);
  assert.equal(needsTakeoffReview({ confidence: 'low' }), true);
  assert.equal(needsTakeoffReview({ confidence: 'high' }), false);
});

test('needsTakeoffReview: rows already accepted/rejected in the review queue drop out', () => {
  assert.equal(needsTakeoffReview({ confidence: 'raudona', _review_status: 'accepted' }), false);
  assert.equal(needsTakeoffReview({ confidence: 'geltona', _review_status: 'rejected' }), false);
  assert.equal(needsTakeoffReview({ confidence: 'geltona', _review_status: 'kita' }), true);
});

test('takeoff review: explicit review_required forces review even with zalia confidence', () => {
  const row = {
    eil_nr: 5,
    aprasymas: 'WC rėmo montavimas',
    confidence: 'zalia',
    review_required: true,
    quantity_source: 'room_type_assumption',
  };

  assert.deepEqual(filterTakeoffRows([row], { mode: 'review' }).map(r => r.aprasymas), ['WC rėmo montavimas']);
  assert.equal(getQuantitySourceKind(row), 'assumption');
  assert.equal(getQuantitySourceLabel(row), 'Prielaida');
});

test('takeoff summary: AI symbols and assumptions are counted separately', () => {
  const summary = summarizeTakeoffWorkflow({
    darbu_sarasas: [
      { aprasymas: 'Sienos', confidence: 'zalia', kaina: 2, quantity_source: 'deterministic_formula' },
      { aprasymas: 'Šviestuvai', confidence: 'raudona', kaina: 2, quantity_source: 'ai_symbol_candidate', review_required: true },
      { aprasymas: 'WC', confidence: 'geltona', kaina: 2, quantity_source: 'room_type_assumption', review_required: true },
    ],
    patalpos: [],
    puslapiai: [{}],
  }, { hasPdf: true });

  assert.equal(summary.aiSymbolRows, 1);
  assert.equal(summary.assumptionRows, 1);
  assert.equal(summary.reviewRows, 2);
  assert.equal(summary.readyForBeta, false);
  assert.ok(summary.readinessScore < 70);
});

test('getRowImpact: kiekis × kaina when prices are used, kiekis alone before prices exist', () => {
  const row = { kiekis: 12, kaina: 2.5 };
  assert.equal(getRowImpact(row, true), 30);
  assert.equal(getRowImpact(row, false), 12);
  assert.equal(getRowImpact({ kiekis: null, kaina: 4 }, true), 0);
  assert.equal(getRowImpact({}, false), 0);
});

test('rankReviewRows: review rows come back ranked by € impact, not confidence order', () => {
  const impactRows = [
    { eil_nr: 1, aprasymas: 'Mazas raudonas', kiekis: 2, kaina: 1, confidence: 'raudona' },
    { eil_nr: 2, aprasymas: 'Didelis geltonas', kiekis: 100, kaina: 30, confidence: 'geltona' },
    { eil_nr: 3, aprasymas: 'Zalias', kiekis: 500, kaina: 50, confidence: 'zalia' },
    { eil_nr: 4, aprasymas: 'Vidutinis geltonas', kiekis: 10, kaina: 8, confidence: 'geltona' },
  ];
  assert.deepEqual(
    rankReviewRows(impactRows).map(r => r.aprasymas),
    ['Didelis geltonas', 'Vidutinis geltonas', 'Mazas raudonas'],
  );
});

test('rankReviewRows: before any prices exist the ranking falls back to kiekis', () => {
  const noPrices = [
    { eil_nr: 1, aprasymas: 'A', kiekis: 3, kaina: 0, confidence: 'geltona' },
    { eil_nr: 2, aprasymas: 'B', kiekis: 40, kaina: 0, confidence: 'geltona' },
  ];
  assert.deepEqual(rankReviewRows(noPrices).map(r => r.aprasymas), ['B', 'A']);
});

test('rankReviewRows: equal impact breaks ties by severity (raudona first), then eil_nr', () => {
  const tied = [
    { eil_nr: 7, aprasymas: 'Geltonas', kiekis: 5, kaina: 2, confidence: 'geltona' },
    { eil_nr: 9, aprasymas: 'Raudonas', kiekis: 10, kaina: 1, confidence: 'raudona' },
    { eil_nr: 3, aprasymas: 'Geltonas ankstesnis', kiekis: 10, kaina: 1, confidence: 'geltona' },
  ];
  assert.deepEqual(
    rankReviewRows(tied).map(r => r.aprasymas),
    ['Raudonas', 'Geltonas ankstesnis', 'Geltonas'],
  );
});

test('getFirstReviewRow: returns the highest-impact review row and skips manual overrides', () => {
  assert.equal(getFirstReviewRow(rows).aprasymas, 'Rozetes');

  const impactRows = [
    { eil_nr: 1, aprasymas: 'Mazas raudonas', kiekis: 2, kaina: 1, confidence: 'raudona' },
    { eil_nr: 2, aprasymas: 'Didelis geltonas', kiekis: 100, kaina: 30, confidence: 'geltona' },
  ];
  assert.equal(getFirstReviewRow(impactRows).aprasymas, 'Didelis geltonas');
  assert.equal(getFirstReviewRow([]), null);
});

test('selectReviewQueue: default view = all raudona + top-5 geltona by value, rest collapsed', () => {
  const queueRows = [
    { eil_nr: 1, aprasymas: 'R1', kiekis: 1, kaina: 2, confidence: 'raudona' },
    { eil_nr: 2, aprasymas: 'R2', kiekis: 1, kaina: 1, confidence: 'raudona' },
    { eil_nr: 3, aprasymas: 'G100', kiekis: 10, kaina: 10, confidence: 'geltona' },
    { eil_nr: 4, aprasymas: 'G90', kiekis: 9, kaina: 10, confidence: 'geltona' },
    { eil_nr: 5, aprasymas: 'G80', kiekis: 8, kaina: 10, confidence: 'geltona' },
    { eil_nr: 6, aprasymas: 'G70', kiekis: 7, kaina: 10, confidence: 'geltona' },
    { eil_nr: 7, aprasymas: 'G60', kiekis: 6, kaina: 10, confidence: 'geltona' },
    { eil_nr: 8, aprasymas: 'G50', kiekis: 5, kaina: 10, confidence: 'geltona' },
    { eil_nr: 9, aprasymas: 'G40', kiekis: 4, kaina: 10, confidence: 'geltona' },
    { eil_nr: 10, aprasymas: 'Zalias', kiekis: 100, kaina: 5, confidence: 'zalia' },
  ];
  const queue = selectReviewQueue(queueRows);

  assert.equal(queue.usePrices, true);
  assert.equal(queue.ranked.length, 9);
  // All raudona present regardless of value + the five biggest geltona.
  // Primary preserves the impact ranking (biggest € first).
  assert.deepEqual(
    queue.primary.map(r => r.aprasymas),
    ['G100', 'G90', 'G80', 'G70', 'G60', 'R1', 'R2'],
  );
  assert.deepEqual(queue.rest.map(r => r.aprasymas), ['G50', 'G40']);

  // Share of the whole estimate the primary rows represent:
  // primary € = 403 of the 993 € total (2+1+100+90+80+70+60+50+40+500).
  const expectedShare = (100 + 90 + 80 + 70 + 60 + 2 + 1) / 993;
  assert.ok(Math.abs(queue.shareOfTotal - expectedShare) < 1e-9);
});

test('selectReviewQueue: before prices exist there is no € share and ranking uses kiekis', () => {
  const queueRows = [
    { eil_nr: 1, aprasymas: 'G maza', kiekis: 2, kaina: 0, confidence: 'geltona' },
    { eil_nr: 2, aprasymas: 'G didele', kiekis: 30, kaina: 0, confidence: 'geltona' },
  ];
  const queue = selectReviewQueue(queueRows);
  assert.equal(queue.usePrices, false);
  assert.equal(queue.shareOfTotal, null);
  assert.deepEqual(queue.primary.map(r => r.aprasymas), ['G didele', 'G maza']);
  assert.deepEqual(queue.rest, []);
});

test('selectReviewQueue: excluded rows (eksplikacija-locked) leave the queue but stay in the € total', () => {
  const queueRows = [
    { eil_nr: 1, aprasymas: 'Locked geltona', kiekis: 10, kaina: 10, confidence: 'geltona', saltinis: 'eksplikacija' },
    { eil_nr: 2, aprasymas: 'G', kiekis: 5, kaina: 10, confidence: 'geltona' },
    { eil_nr: 3, aprasymas: 'Zalias', kiekis: 5, kaina: 10, confidence: 'zalia' },
  ];
  const queue = selectReviewQueue(queueRows, { exclude: r => r.saltinis === 'eksplikacija' });
  assert.deepEqual(queue.ranked.map(r => r.aprasymas), ['G']);
  assert.deepEqual(queue.primary.map(r => r.aprasymas), ['G']);
  // total = 100 + 50 + 50 = 200; primary = 50.
  assert.ok(Math.abs(queue.shareOfTotal - 50 / 200) < 1e-9);
});

test('selectReviewQueue: maxGeltona is configurable', () => {
  const queueRows = [
    { eil_nr: 1, aprasymas: 'G1', kiekis: 3, kaina: 1, confidence: 'geltona' },
    { eil_nr: 2, aprasymas: 'G2', kiekis: 2, kaina: 1, confidence: 'geltona' },
    { eil_nr: 3, aprasymas: 'G3', kiekis: 1, kaina: 1, confidence: 'geltona' },
  ];
  const queue = selectReviewQueue(queueRows, { maxGeltona: 1 });
  assert.deepEqual(queue.primary.map(r => r.aprasymas), ['G1']);
  assert.deepEqual(queue.rest.map(r => r.aprasymas), ['G2', 'G3']);
});

test('ltEilutesPhrase: Lithuanian numeral agreement for the review copy', async () => {
  const { ltEilutesPhrase } = await import('./takeoffWorkflow.js');
  assert.equal(ltEilutesPhrase(1), 'šią 1 eilutę');
  assert.equal(ltEilutesPhrase(6), 'šias 6 eilutes');
  assert.equal(ltEilutesPhrase(11), 'šias 11 eilučių');
  assert.equal(ltEilutesPhrase(20), 'šias 20 eilučių');
  assert.equal(ltEilutesPhrase(21), 'šią 21 eilutę');
  assert.equal(ltEilutesPhrase(102), 'šias 102 eilutes');
});

test('filterTakeoffRows: filters by review mode, manual mode, missing price mode and query', () => {
  assert.deepEqual(filterTakeoffRows(rows, { mode: 'review' }).map(r => r.aprasymas), ['Rozetes']);
  assert.deepEqual(filterTakeoffRows(rows, { mode: 'manual' }).map(r => r.aprasymas), ['Lubos', 'Grindjuostes']);
  assert.deepEqual(filterTakeoffRows(rows, { mode: 'missing_price' }).map(r => r.aprasymas), ['Rozetes', 'Grindjuostes']);
  assert.deepEqual(filterTakeoffRows(rows, { query: 'sienu' }).map(r => r.aprasymas), ['Sienu dazymas']);
});

test('getRowTargetPage: prefers eksplikacija page for table-backed rows and falls back to row page', () => {
  const project = { _eksplikacija: { eksplikacija_source_page: 7 } };
  assert.equal(getRowTargetPage({ eksplikacija_row_bbox: [1, 2, 3, 4], puslapio_nr: 2 }, project), 7);
  assert.equal(getRowTargetPage({ puslapio_nr: 2 }, project), 2);
  assert.equal(getRowTargetPage({}, project), null);
});

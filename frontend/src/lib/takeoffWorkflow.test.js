import test from 'node:test';
import assert from 'node:assert/strict';
import {
  filterTakeoffRows,
  getFirstReviewRow,
  getQuantitySourceKind,
  getQuantitySourceLabel,
  getRowTargetPage,
  summarizeTakeoffWorkflow,
} from './takeoffWorkflow.js';

const rows = [
  { eil_nr: 1, aprasymas: 'Sienu dazymas', kiekis: 10, kaina: 5, confidence: 'high', mato_vnt: 'm2' },
  { eil_nr: 2, aprasymas: 'Rozetes', kiekis: 4, kaina: 0, confidence: 'medium', mato_vnt: 'vnt' },
  { eil_nr: 3, aprasymas: 'Lubos', kiekis: 12, kaina: 3, confidence: 'low', manual_override: true },
  { eil_nr: 4, aprasymas: 'Grindjuostes', kiekis: 20, kaina: 0, confidence: 'high', quantity_source: 'manual_override' },
];

test('summarizeTakeoffWorkflow: counts review, manual and missing price rows', () => {
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

test('takeoff review: explicit review_required forces review even with high confidence', () => {
  const row = {
    eil_nr: 5,
    aprasymas: 'WC rėmo montavimas',
    confidence: 'high',
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
      { aprasymas: 'Sienos', confidence: 'high', kaina: 2, quantity_source: 'deterministic_formula' },
      { aprasymas: 'Šviestuvai', confidence: 'low', kaina: 2, quantity_source: 'ai_symbol_candidate', review_required: true },
      { aprasymas: 'WC', confidence: 'medium', kaina: 2, quantity_source: 'room_type_assumption', review_required: true },
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

test('getFirstReviewRow: skips manual override rows even when confidence is low', () => {
  assert.equal(getFirstReviewRow(rows).aprasymas, 'Rozetes');
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

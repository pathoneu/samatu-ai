import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  scorePair,
  bestMatchForPozicija,
  applyPriceListToPositions,
  manualPricePatch,
} from './applyPriceList.js';

test('scorePair: exact match → 1.0', () => {
  assert.equal(scorePair('Sienų dažymas', 'sienų dažymas'), 1.0);
});

test('scorePair: substring → 0.92', () => {
  assert.equal(scorePair('Sienų dažymas', 'Sienų dažymas, 2 sluoksniai'), 0.92);
});

test('scorePair: Jaccard on shared tokens', () => {
  const s = scorePair('Sienų pirminis glaistymas Q1', 'Sienų antrinis glaistymas Q2');
  // Shared tokens: ['sienų', 'glaistymas'] → jaccard = 2/4 = 0.5
  assert.ok(s >= 0.4 && s <= 0.6, `expected ~0.5, got ${s}`);
});

test('scorePair: empty inputs → 0', () => {
  assert.equal(scorePair('', 'whatever'), 0);
  assert.equal(scorePair('whatever', ''), 0);
});

test('bestMatchForPozicija: picks highest score', () => {
  const poz = { aprasymas: 'Sienų dažymas (1 sluoksnis)', vnt: 'm²' };
  const items = [
    { aprasymas: 'Lubų dažymas', vnt: 'm²', kaina: 8 },
    { aprasymas: 'Sienų dažymas, 1 sluoksnis', vnt: 'm²', kaina: 12 },
    { aprasymas: 'Grindjuosčių montavimas', vnt: 'm', kaina: 5 },
  ];
  const m = bestMatchForPozicija(poz, items);
  assert.ok(m);
  assert.equal(m.item.kaina, 12);
});

test('bestMatchForPozicija: rejects unit mismatch', () => {
  const poz = { aprasymas: 'Sienų dažymas', vnt: 'm²' };
  const items = [
    { aprasymas: 'Sienų dažymas', vnt: 'vnt', kaina: 12 },
  ];
  // Even though aprašymas is identical, vnt differs → no match
  assert.equal(bestMatchForPozicija(poz, items), null);
});

test('bestMatchForPozicija: returns null below threshold', () => {
  const poz = { aprasymas: 'Sienų dažymas', vnt: 'm²' };
  const items = [{ aprasymas: 'Visiškai kitas darbas', vnt: 'm²', kaina: 99 }];
  assert.equal(bestMatchForPozicija(poz, items), null);
});

test('applyPriceListToPositions: fills matched, leaves rest', () => {
  const poz = [
    { id: 1, aprasymas: 'Sienų dažymas', vnt: 'm²', kiekis: 100 },
    { id: 2, aprasymas: 'Specialus darbas niekur nerastas', vnt: 'kompl', kiekis: 1 },
  ];
  const priceList = [
    { aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 },
  ];
  const out = applyPriceListToPositions(poz, priceList);
  assert.equal(out.applied, 1);
  assert.equal(out.skipped, 1);
  assert.equal(out.items[0].kaina, 7.5);
  assert.equal(out.items[0].kaina_source, 'kainynas');
  assert.equal(out.items[1].kaina, undefined);
});

test('applyPriceListToPositions: respects manual overrides by default', () => {
  const poz = [
    { id: 1, aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 99, kaina_source: 'manual' },
  ];
  const priceList = [{ aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 }];
  const out = applyPriceListToPositions(poz, priceList);
  assert.equal(out.applied, 0);
  assert.equal(out.skipped, 1);
  assert.equal(out.items[0].kaina, 99);  // manual price preserved
});

test('applyPriceListToPositions: overwriteManual flag does override', () => {
  const poz = [
    { id: 1, aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 99, kaina_source: 'manual' },
  ];
  const priceList = [{ aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 }];
  const out = applyPriceListToPositions(poz, priceList, { overwriteManual: true });
  assert.equal(out.applied, 1);
  assert.equal(out.items[0].kaina, 7.5);
});

test('applyPriceListToPositions: empty inputs', () => {
  const out1 = applyPriceListToPositions([], [{ aprasymas: 'x', kaina: 1 }]);
  assert.equal(out1.applied, 0);
  assert.deepEqual(out1.items, []);

  const out2 = applyPriceListToPositions([{ aprasymas: 'x' }], []);
  assert.equal(out2.applied, 0);
  assert.equal(out2.skipped, 1);
});

// ── manualPricePatch — provenance stamping at the price editors ─────────────
// Mirrors how every commit site merges the patch into the row.
function commitPrice(row, typedKaina) {
  return {
    ...row,
    kaina: typedKaina,
    suma: (row.kiekis || 0) * typedKaina,
    ...manualPricePatch(row, typedKaina),
  };
}

test('manualPricePatch: typing a price into an empty row marks it manual', () => {
  const row = commitPrice({ aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 0 }, 40);
  assert.equal(row.kaina, 40);
  assert.equal(row.kaina_source, 'manual');
});

test('manualPricePatch: editing a kainynas price flips source to manual and drops match score', () => {
  const applied = { aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 7.5, kaina_source: 'kainynas', kaina_match_score: 0.92 };
  const row = commitPrice(applied, 9);
  assert.equal(row.kaina_source, 'manual');
  assert.equal(row.kaina_match_score, undefined);
});

test('manualPricePatch: committing an unchanged price leaves provenance alone', () => {
  const applied = { aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 7.5, kaina_source: 'kainynas', kaina_match_score: 0.92 };
  // Row editor saved with only the description changed — price untouched.
  const row = commitPrice(applied, 7.5);
  assert.equal(row.kaina_source, 'kainynas');
  assert.equal(row.kaina_match_score, 0.92);
});

test('manualPricePatch: clearing to 0 resets source so kainynas may refill', () => {
  const manual = { aprasymas: 'Sienų dažymas', vnt: 'm²', kiekis: 100, kaina: 40, kaina_source: 'manual' };
  const cleared = commitPrice(manual, 0);
  assert.notEqual(cleared.kaina_source, 'manual');
  const out = applyPriceListToPositions([cleared], [{ aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 }]);
  assert.equal(out.items[0].kaina, 7.5);
  assert.equal(out.items[0].kaina_source, 'kainynas');
});

test('P0 flow: hand-typed price survives apply; kainynas rows update on re-apply', () => {
  const rows = [
    commitPrice({ aprasymas: 'Sienų dažymas', vnt: 'm²', kiekis: 100, kaina: 0 }, 40),
    { aprasymas: 'Lubų dažymas', vnt: 'm²', kiekis: 50 },
  ];
  const listV1 = [
    { aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 7.5 },
    { aprasymas: 'Lubų dažymas', vnt: 'm²', kaina: 6 },
  ];
  const first = applyPriceListToPositions(rows, listV1);
  assert.equal(first.items[0].kaina, 40);          // the P0: typed price survives
  assert.equal(first.items[0].kaina_source, 'manual');
  assert.equal(first.items[1].kaina, 6);

  const listV2 = [
    { aprasymas: 'Sienų dažymas', vnt: 'm²', kaina: 8 },
    { aprasymas: 'Lubų dažymas', vnt: 'm²', kaina: 6.5 },
  ];
  const second = applyPriceListToPositions(first.items, listV2);
  assert.equal(second.items[0].kaina, 40);         // manual still survives re-apply
  assert.equal(second.items[1].kaina, 6.5);        // kainynas price updates on re-apply
});

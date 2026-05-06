import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  scorePair,
  bestMatchForPozicija,
  applyPriceListToPositions,
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

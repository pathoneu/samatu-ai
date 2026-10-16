import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  applyAssembliesToPositions, assemblyForRow, assemblyUnitPrice, componentUnitCost,
  doubleBilledMaterials, matchTemplate,
} from './assemblyPricing.js';
import { applyPriceListToPositions, manualPricePatch } from './applyPriceList.js';

const work = (over = {}) => ({
  id: 'w1', skyrius: 'Sienų glaistymas dažymas', aprasymas: 'Sienų glaistymas/dažymas',
  vnt: 'm2', kiekis: 100, ...over,
});
const mat = (aprasymas, kiekis, over = {}) => ({
  id: `m-${aprasymas}`, skyrius: 'Medžiagos', aprasymas, vnt: 'kg', kiekis,
  susijes_darbas: 'Sienų glaistymas/dažymas', _medziaga: true, ...over,
});
const asm = (komponentai, over = {}) => ({
  id: 'a1', name: 'Mano dažymas',
  taikoma: { aprasymas: 'Sienų glaistymas/dažymas', vnt: 'm2', eilutes_id: [] },
  komponentai, ...over,
});
const labour = (kaina) => ({ rusis: 'darbas', pavadinimas: 'Darbas', norma: 1, vnt: 'm2', kaina });

test('component cost = norma × (1 + atliekos) × kaina', () => {
  assert.equal(componentUnitCost({ norma: 1.25, atliekos_proc: 10, kaina: 2 }), 1.25 * 1.1 * 2);
  assert.equal(assemblyUnitPrice(asm([labour(4.2), { rusis: 'medziaga', norma: 2, kaina: 0.9 }])), 6);
});

test('matchTemplate mirrors the server', () => {
  assert.equal(matchTemplate('{vieta} plytelių klijavimas', 'Vonios sienų plytelių klijavimas'), 'Vonios sienų');
  assert.equal(matchTemplate('Sienų glaistymas/dažymas{vieta}', 'Sienų glaistymas/dažymas'), '');
  assert.equal(matchTemplate('Dažymo kampų montavimas', 'Kampų montavimas'), null);
});

test('case 1 — the Medžiagos row exists: it gets the material price, the work row only labour', () => {
  const rows = [work(), mat('Glaistas sienoms (pradinis + baigiamasis)', 125)];
  const a = asm([labour(4.2),
    { rusis: 'medziaga', pavadinimas: 'Glaistas sienoms (pradinis + baigiamasis)', norma: 1.25, vnt: 'kg', kaina: 0.8 }]);
  const out = applyAssembliesToPositions(rows, [a]);
  const [w, m] = out.items;
  assert.equal(w.kaina_darbo, 4.2);
  assert.equal(w.kaina_medziagu, 0);
  assert.equal(w.kaina, 4.2);
  assert.equal(w.suma, 420);
  assert.equal(w.kaina_source, 'rinkinys');
  assert.equal(w.rinkinys_id, 'a1');
  assert.equal(m.kaina, 0.8);
  assert.equal(m.suma, 100);
  assert.equal(m.kiekis, 125, 'the material quantity never moves');
  assert.equal(m.kaina_source, 'rinkinys');
  assert.equal(out.applied, 1);
  assert.equal(out.materialsPriced, 1);
  assert.deepEqual(doubleBilledMaterials(out.items), []);
  assert.equal(rows[0].kaina, undefined, 'input not mutated');
});

test('case 2 — no Medžiagos row: the material goes into kaina_medziagu, named for the guard', () => {
  const a = asm([labour(4.2),
    { rusis: 'medziaga', pavadinimas: 'Klijai', norma: 2, vnt: 'kg', atliekos_proc: 10, kaina: 0.5 }]);
  const out = applyAssembliesToPositions([work()], [a]);
  const [w] = out.items;
  assert.equal(w.kaina_darbo, 4.2);
  assert.equal(w.kaina_medziagu, 1.1);
  assert.equal(w.kaina, 5.3);
  assert.equal(w.kaina, Math.round((w.kaina_darbo + w.kaina_medziagu) * 100) / 100);
  assert.deepEqual(w.rinkinys_medziagos, ['Klijai']);
  // the guard: a priced Medžiagos row for the same component appearing later
  const later = [...out.items, mat('Klijai', 220, { kaina: 0.6, kaina_source: 'manual' })];
  assert.deepEqual(doubleBilledMaterials(later), [{ darbas: 'Sienų glaistymas/dažymas', medziaga: 'Klijai' }]);
});

test('case 3 — a Medžiagos row already priced by him or a kainynas is left and reported, never zeroed', () => {
  for (const src of ['manual', 'kainynas']) {
    const rows = [work(), mat('Glaistas sienoms (pradinis + baigiamasis)', 125, { kaina: 1.1, kaina_source: src })];
    const a = asm([labour(4.2),
      { rusis: 'medziaga', pavadinimas: 'Glaistas sienoms (pradinis + baigiamasis)', norma: 1.25, kaina: 0.8 }]);
    const out = applyAssembliesToPositions(rows, [a]);
    assert.equal(out.items[1].kaina, 1.1);
    assert.equal(out.items[1].kaina_source, src);
    assert.deepEqual(out.kept, [{ aprasymas: 'Glaistas sienoms (pradinis + baigiamasis)', kaina: 1.1 }]);
    assert.equal(out.items[0].kaina_medziagu, 0, 'never both for one component');
  }
});

test('a hand-typed work price is never overwritten', () => {
  const out = applyAssembliesToPositions([work({ kaina: 9, kaina_source: 'manual' })], [asm([labour(4.2)])]);
  assert.equal(out.items[0].kaina, 9);
  assert.equal(out.skipped, 1);
});

test('binding: rinkinys_id beats the label; eilutes_id; templates fill {vieta}', () => {
  const a1 = asm([labour(1)], { id: 'a1' });
  const a2 = asm([labour(2)], { id: 'a2', taikoma: { aprasymas: 'Kita', eilutes_id: ['w9'] } });
  assert.equal(assemblyForRow(work({ rinkinys_id: 'a2' }), [a1, a2]).assembly.id, 'a2');
  assert.equal(assemblyForRow(work({ id: 'w9', aprasymas: 'Nesutampa' }), [a1, a2]).assembly.id, 'a2');
  const tiles = asm([labour(15), { rusis: 'medziaga', pavadinimas: '{vieta} plytelių klijai (~5 kg/m²)', norma: 5, kaina: 0.4 }],
    { id: 't', taikoma: { aprasymas: '{vieta} plytelių klijavimas' } });
  const rows = [
    { id: 'p1', skyrius: 'Plytelių klijavimas', aprasymas: 'Vonios sienų plytelių klijavimas', vnt: 'm2', kiekis: 40 },
    { id: 'p2', skyrius: 'Medžiagos', aprasymas: 'Vonios sienų plytelių klijai (~5 kg/m²)', vnt: 'kg', kiekis: 200,
      susijes_darbas: 'Vonios sienų plytelių klijavimas', _medziaga: true },
  ];
  const out = applyAssembliesToPositions(rows, [tiles]);
  assert.equal(out.items[0].kaina, 15);
  assert.equal(out.items[1].kaina, 0.4);
});

test('the label matcher keeps the kainynas unit guard', () => {
  const a = asm([labour(3)], { taikoma: { aprasymas: 'Sienų glaistymas/dažymas', vnt: 'm' } });
  assert.equal(assemblyForRow(work(), [a]), null);
});

test('a manual price clears the split; an unchanged one does not', () => {
  const row = work({ kaina: 5.3, kaina_darbo: 4.2, kaina_medziagu: 1.1, kaina_source: 'rinkinys' });
  const p = manualPricePatch(row, 6);
  assert.equal(p.kaina_source, 'manual');
  assert.ok('kaina_darbo' in p && p.kaina_darbo === undefined);
  assert.ok('kaina_medziagu' in p && p.kaina_medziagu === undefined);
  assert.deepEqual(manualPricePatch(row, 5.3), {});
  assert.deepEqual(manualPricePatch(work({ kaina: 3 }), 4), { kaina_source: 'manual', kaina_match_score: undefined });
});

// ── kainynas with a „Medžiagų kaina" column (backend manager's option A) ────

const kainynas = (medziagu_kaina) => [{ aprasymas: 'Sienų glaistymas/dažymas', mato_vnt: 'm2', kaina: 4.2,
  ...(medziagu_kaina != null ? { medziagu_kaina } : {}) }];

test('a list WITHOUT a material column behaves exactly as before', () => {
  const rows = [work(), mat('Glaistas sienoms (pradinis + baigiamasis)', 125)];
  const out = applyPriceListToPositions(rows, kainynas(null));
  assert.deepEqual(JSON.parse(JSON.stringify(out.items)), [
    { ...work(), kaina: 4.2, kaina_source: 'kainynas', kaina_match_score: 1 },
    mat('Glaistas sienoms (pradinis + baigiamasis)', 125),
  ]);
  assert.equal(out.materialsInRow, 0);
  assert.equal(out.materialsPriced, 0);
});

test('material column, no Medžiagos row: work row = darbo + medžiagų', () => {
  const out = applyPriceListToPositions([work()], kainynas(1.8));
  const [w] = out.items;
  assert.equal(w.kaina_darbo, 4.2);
  assert.equal(w.kaina_medziagu, 1.8);
  assert.equal(w.kaina, 6);
  assert.equal(w.kaina_source, 'kainynas');
  assert.equal(out.materialsInRow, 1);
});

test('material column, one Medžiagos row: that row is priced per ITS unit, work keeps the work price', () => {
  const out = applyPriceListToPositions([work(), mat('Glaistas sienoms (pradinis + baigiamasis)', 125)], kainynas(1.8));
  const [w, m] = out.items;
  assert.equal(w.kaina, 4.2);
  assert.equal(w.kaina_medziagu, 0);
  assert.equal(m.kaina, 1.44);              // 1,8 €/m² × 100 m² ÷ 125 kg
  assert.equal(m.kiekis, 125);
  assert.equal(out.materialsPriced, 1);
});

test('material column, Medžiagos row already priced: left and reported', () => {
  const out = applyPriceListToPositions(
    [work(), mat('Glaistas sienoms (pradinis + baigiamasis)', 125, { kaina: 1, kaina_source: 'manual' })], kainynas(1.8));
  assert.equal(out.items[1].kaina, 1);
  assert.equal(out.kept.length, 1);
  assert.equal(out.items[0].kaina, 4.2);
});

test('material column, several Medžiagos rows: nothing split, the work is named', () => {
  const out = applyPriceListToPositions(
    [work(), mat('Glaistas sienoms (pradinis + baigiamasis)', 125), mat('Gruntas sienoms', 14, { vnt: 'l' })],
    kainynas(1.8));
  assert.equal(out.items[0].kaina, 4.2);
  assert.equal(out.items[1].kaina, undefined);
  assert.deepEqual(out.notSplit, ['Sienų glaistymas/dažymas']);
});

test('a kainynas price replacing a rinkinys split clears it', () => {
  const out = applyPriceListToPositions(
    [work({ kaina: 5.3, kaina_darbo: 4.2, kaina_medziagu: 1.1, kaina_source: 'rinkinys' })], kainynas(null));
  assert.equal(out.items[0].kaina, 4.2);
  assert.equal(out.items[0].kaina_darbo, undefined);
  assert.equal(out.items[0].kaina_medziagu, undefined);
});

test('the apply result names what happened to the material prices', async () => {
  const { describeMaterialPrices } = await import('./applyPriceList.js');
  const t = (k, o) => `${k.split('.').pop()}:${o.count}`;
  assert.equal(describeMaterialPrices({ materialsInRow: 0, materialsPriced: 0, kept: [], notSplit: [] }, t), undefined);
  assert.equal(describeMaterialPrices({ materialsInRow: 2, materialsPriced: 12, kept: [{}, {}], notSplit: ['x'] }, t),
    'materialsInRow:2 · materialsPriced:12 · materialsKept:2 · materialsNotSplit:1');
});

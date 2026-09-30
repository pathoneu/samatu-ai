// The made-up price list, read through the browser's CSV importer (founder
// request, 2026-09-30). The spec and the .csv live beside the backend test in
// backend/tests/fixtures_price_list/ so the .xlsx upload and the CSV upload
// are checked against ONE list of expected prices. Every name is invented.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseCsv, parseLtPrice, describeUnreadablePrices, UNREADABLE_ROWS_SHOWN } from './priceListCsv.js';

const FIXTURES = new URL('../../../backend/tests/fixtures_price_list/', import.meta.url);
const SPEC = JSON.parse(readFileSync(new URL('kainynas_eilutes.json', FIXTURES), 'utf8'));
const CSV_TEXT = readFileSync(new URL('bandomasis_kainynas.csv', FIXTURES), 'utf8');

// Line 1 of the CSV is the header, so spec row i sits on line i + 2.
const lineOf = (i) => i + 2;

test('made-up list: every row comes out of the CSV at its expected price', () => {
  const out = parseCsv(CSV_TEXT);
  const want = SPEC.rows.filter(r => 'kaina' in r.expect);
  assert.deepEqual(out.items.map(i => i.aprasymas), want.map(r => r.darbas));
  out.items.forEach((item, k) => {
    const exp = want[k].expect;
    assert.equal(item.kaina, exp.kaina, `${want[k].darbas}: „${want[k].csv}“ gave ${item.kaina}`);
    assert.equal(item.mato_vnt, exp.mato_vnt, want[k].darbas);
    assert.equal(item.skyrius, exp.skyrius, want[k].darbas);
  });
});

test('made-up list: skipped rows are counted and the unreadable ones named by line', () => {
  const out = parseCsv(CSV_TEXT);
  assert.equal(out.skippedRows, SPEC.rows.filter(r => r.expect.skip).length);
  const named = SPEC.rows
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => r.expect.skip === 'unreadable')
    .map(({ r, i }) => ({ row: lineOf(i), aprasymas: r.darbas, kaina: r.csv }));
  assert.deepEqual(out.problemRows, named);
});

// Same table as backend/tests/test_price_list_made_up.py — the two readers
// must agree cell for cell.
const READABLE = [
  ['15', 15, null],
  ['15,50', 15.5, null],
  ['15.50', 15.5, null],
  ['15 €', 15, null],
  ['15€', 15, null],
  ['15 €/m2', 15, 'm2'],          // was 152
  ['5 Eur/m2', 5, 'm2'],          // was 52
  ['12,50 €/m2', 12.5, 'm2'],     // was 12.502
  ['12,5 Eur/m²', 12.5, 'm²'],
  ['8 €/m3', 8, 'm3'],            // was 83
  ['3 € už m3', 3, 'm3'],
  ['4,10 EUR / m', 4.1, 'm'],
  ['45 € vnt.', 45, 'vnt.'],
  ['120 eur/kompl.', 120, 'kompl.'],
  ['7 m²', 7, 'm²'],
  ['1 234,56 €', 1234.56, null],
  ['1 234,56 €', 1234.56, null],
  ['1 234,56', 1234.56, null],
  ['1 234,56', 1234.56, null],
  ['1.234,56', 1234.56, null],      // was 1.234
  ['1,234.56', 1234.56, null],
];

for (const [cell, price, unit] of READABLE) {
  test(`price cell „${cell}“ → ${price}${unit ? ` ${unit}` : ''}`, () => {
    assert.deepEqual(parseLtPrice(cell), { price, unit, status: 'ok' });
  });
}

for (const cell of ['sutartinė', '15–20 €', '15-20', '15 € be pagrindo', '15 2', 'apie 15 €', 'vnt.', '-']) {
  test(`price cell „${cell}“ is unreadable, never a number`, () => {
    assert.deepEqual(parseLtPrice(cell), { price: null, unit: null, status: 'unreadable' });
  });
}

test('an empty price cell is empty', () => {
  for (const cell of [undefined, null, '', '   ']) {
    assert.deepEqual(parseLtPrice(cell), { price: null, unit: null, status: 'empty' });
  }
});

test('the old header words still work', () => {
  const out = parseCsv('skyrius,aprasymas,vnt,kaina\nDažymas,Sienų dažymas,m²,"7,50"\n');
  assert.deepEqual(out.items, [{ skyrius: 'Dažymas', aprasymas: 'Sienų dažymas', mato_vnt: 'm²', kaina: 7.5 }]);
  assert.equal(out.skippedRows, 0);
  assert.deepEqual(out.problemRows, []);
});

const tFake = (key, vars = {}) => `${key}|${Object.entries(vars).map(([k, v]) => `${k}=${v}`).join(',')}`;

test('describeUnreadablePrices names the rows, and nothing when there are none', () => {
  assert.equal(describeUnreadablePrices([], tFake), undefined);
  assert.equal(describeUnreadablePrices(undefined, tFake), undefined);
  const out = describeUnreadablePrices([{ row: 30, aprasymas: 'Palangių montavimas', kaina: 'sutartinė' }], tFake);
  assert.ok(out.startsWith('priceLists.unreadableDescription|rows='), out);
  assert.ok(out.includes('priceLists.unreadableRow|row=30,name=Palangių montavimas,value=sutartinė'), out);
});

test('describeUnreadablePrices shows a few rows and counts the rest', () => {
  const many = Array.from({ length: UNREADABLE_ROWS_SHOWN + 3 }, (_, i) => ({ row: i + 2, aprasymas: `Darbas ${i}`, kaina: '?' }));
  const out = describeUnreadablePrices(many, tFake);
  assert.equal(out.split('priceLists.unreadableRow|').length - 1, UNREADABLE_ROWS_SHOWN);
  assert.ok(out.includes('priceLists.unreadableMore|count=3'), out);
});

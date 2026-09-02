import { test } from 'node:test';
import assert from 'node:assert/strict';
import { insertRowInSection, nextEilNr, rowSection } from './darbuRows.js';

const OTHER = 'Kiti darbai';

const list = [
  { eil_nr: 1, aprasymas: 'Sienų dažymas', skyrius: 'Dažymo darbai' },
  { eil_nr: 2, aprasymas: 'Lubų dažymas', skyrius: 'Dažymo darbai' },
  { eil_nr: 3, aprasymas: 'Klozeto montavimas', skyrius: 'Santechnikos darbai' },
  { eil_nr: 4, aprasymas: 'Sena eilutė be skyriaus' },
];

test('insertRowInSection: lands right after the last row of the target section', () => {
  const row = { eil_nr: 5, aprasymas: 'Nauja', skyrius: 'Dažymo darbai' };
  const out = insertRowInSection(list, 'Dažymo darbai', row, OTHER);
  assert.equal(out.length, 5);
  assert.equal(out[2], row);
  assert.equal(out[3].aprasymas, 'Klozeto montavimas');
  assert.equal(list.length, 4); // input not mutated
});

test('insertRowInSection: section-less rows group under otherLabel like the UI does', () => {
  const row = { aprasymas: 'X', skyrius: OTHER };
  const out = insertRowInSection(list, OTHER, row, OTHER);
  assert.equal(out[out.length - 1], row); // after the section-less row (last)
  assert.equal(rowSection(list[3], OTHER), OTHER);
});

test('insertRowInSection: unknown section appends at the end', () => {
  const row = { aprasymas: 'Y', skyrius: 'Ventiliacija' };
  const out = insertRowInSection(list, 'Ventiliacija', row, OTHER);
  assert.equal(out[out.length - 1], row);
});

test('insertRowInSection: empty list appends at index 0', () => {
  const row = { aprasymas: 'Z', skyrius: 'Dažymo darbai' };
  assert.deepEqual(insertRowInSection([], 'Dažymo darbai', row, OTHER), [row]);
});

test('nextEilNr: max + 1, not length + 1 (deletion gaps)', () => {
  assert.equal(nextEilNr([{ eil_nr: 1 }, { eil_nr: 7 }]), 8);
});

test('nextEilNr: tolerates missing/garbage eil_nr', () => {
  assert.equal(nextEilNr([{ eil_nr: null }, { eil_nr: 'x' }, {}]), 1);
  assert.equal(nextEilNr([]), 1);
});

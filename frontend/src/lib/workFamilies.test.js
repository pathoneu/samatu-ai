import test from 'node:test';
import assert from 'node:assert/strict';
import {
  WORK_FAMILIES, countRowsRemoved, filterRowsByFamilies, sectionFamily,
} from './workFamilies.js';

// The section names the builder actually emitted on the 11-room dev project.
const ROWS = [
  { aprasymas: 'Sienų lyginimas', skyrius: 'Sienų glaistymas dažymas' },
  { aprasymas: 'Lubų dažymas', skyrius: 'Lubų glaistymas dažymas' },
  { aprasymas: 'GKP pertvaros', skyrius: 'GKP montavimas' },
  { aprasymas: 'Plytelių klijavimas', skyrius: 'Plytelių klijavimas' },
  { aprasymas: 'Hidroizoliacija', skyrius: 'Hidroizoliacija' },
  { aprasymas: 'Parketo klojimas', skyrius: 'Grindys' },
  { aprasymas: 'Klozeto montavimas', skyrius: 'Santechnikos darbai' },
  { aprasymas: 'Ortakių montavimas', skyrius: 'Ventiliacijos darbai' },
  { aprasymas: 'Rozečių pajungimas', skyrius: 'Elektros instaliacijos darbai' },
  { aprasymas: 'Slenksniai', skyrius: 'Pridėtiniai elementai' },
  { aprasymas: 'Sanitarinis silikonas', skyrius: 'Medžiagos', susijes_darbas: 'Klozeto montavimas' },
  { aprasymas: 'Gruntas', skyrius: 'Medžiagos', susijes_darbas: 'Sienų lyginimas' },
];

test('sectionFamily: the real LT section names land in the family a contractor expects', () => {
  assert.equal(sectionFamily('Sienų glaistymas dažymas'), 'apdaila');
  assert.equal(sectionFamily('Lubų glaistymas dažymas'), 'apdaila');
  assert.equal(sectionFamily('GKP montavimas'), 'apdaila');
  assert.equal(sectionFamily('Grindys'), 'grindys');
  assert.equal(sectionFamily('Plytelių klijavimas'), 'plyteles');
  assert.equal(sectionFamily('Santechnikos darbai'), 'santechnika');
  assert.equal(sectionFamily('Elektros instaliacijos darbai'), 'elektra');
});

test('sectionFamily: a section no family is sure about belongs to none', () => {
  for (const s of ['Ventiliacijos darbai', 'Pridėtiniai elementai', 'Medžiagos',
                   'Hidroizoliacija', 'Kažkoks naujas skyrius', '', null, undefined]) {
    assert.equal(sectionFamily(s), null, `expected no family for ${s}`);
  }
});

test('filterRowsByFamilies: everything ticked changes nothing', () => {
  const out = filterRowsByFamilies(ROWS, WORK_FAMILIES);
  assert.equal(out.length, ROWS.length);
});

test('filterRowsByFamilies: unticking one family removes exactly its sections', () => {
  const out = filterRowsByFamilies(ROWS, WORK_FAMILIES.filter(f => f !== 'elektra'));
  assert.equal(out.find(r => r.skyrius === 'Elektros instaliacijos darbai'), undefined);
  assert.equal(out.length, ROWS.length - 1);
});

test('filterRowsByFamilies: a dropped work takes its material with it', () => {
  const out = filterRowsByFamilies(ROWS, WORK_FAMILIES.filter(f => f !== 'santechnika'));
  assert.equal(out.find(r => r.skyrius === 'Santechnikos darbai'), undefined);
  // …and the silicone bought for it
  assert.equal(out.find(r => r.aprasymas === 'Sanitarinis silikonas'), undefined);
  // …while an unrelated material stays
  assert.ok(out.find(r => r.aprasymas === 'Gruntas'));
});

test('filterRowsByFamilies: sections belonging to no family survive every choice', () => {
  const out = filterRowsByFamilies(ROWS, []);
  const kept = out.map(r => r.skyrius);
  assert.ok(kept.includes('Ventiliacijos darbai'));
  assert.ok(kept.includes('Pridėtiniai elementai'));
  assert.ok(kept.includes('Hidroizoliacija'));
});

test('filterRowsByFamilies: never mutates its input and tolerates junk', () => {
  const before = ROWS.length;
  filterRowsByFamilies(ROWS, ['grindys']);
  assert.equal(ROWS.length, before);
  assert.deepEqual(filterRowsByFamilies(null, ['grindys']), []);
  assert.deepEqual(filterRowsByFamilies([null, undefined], ['grindys']), []);
});

test('countRowsRemoved: reports what the hint promises before anything is deleted', () => {
  assert.equal(countRowsRemoved(ROWS, WORK_FAMILIES), 0);
  assert.equal(countRowsRemoved(ROWS, WORK_FAMILIES.filter(f => f !== 'santechnika')), 2);
  assert.equal(countRowsRemoved(ROWS, WORK_FAMILIES.filter(f => f !== 'grindys')), 1);
});

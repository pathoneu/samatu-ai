import test from 'node:test';
import assert from 'node:assert/strict';

import { readChanges, rereadUndoTarget, rowChangeCount, rowChanges, withChanges } from './changeSummary.js';

const before = {
  darbu_sarasas: [
    { id: 'a', aprasymas: 'Grindjuostės', skyrius: 'Grindys', mato_vnt: 'm', kiekis: 40 },
    { id: 'b', aprasymas: 'Lubų dažymas', skyrius: 'Lubos', mato_vnt: 'm²', kiekis: 60 },
    { id: 'c', aprasymas: 'Kampai', skyrius: 'Sienos', mato_vnt: 'm', kiekis: 12 },
    { aprasymas: 'Be id', skyrius: 'Kita', mato_vnt: 'vnt.', kiekis: 1 },
  ],
  _duru_ziniarastis: { status: 'lentele', eilutes: 3 },
  _meta: { zonos: { 1: [{ kind: 'planas' }] } },
};
const after = {
  darbu_sarasas: [
    { id: 'a', aprasymas: 'Grindjuostės', skyrius: 'Grindys', mato_vnt: 'm', kiekis: 41.2 },
    { id: 'b', aprasymas: 'Lubų dažymas', skyrius: 'Lubos', mato_vnt: 'm²', kiekis: 60.004 },
    { id: 'd', aprasymas: 'Hidroizoliacija', skyrius: 'Vonia', mato_vnt: 'm²', kiekis: 9 },
    { aprasymas: 'Be id', skyrius: 'Kita', mato_vnt: 'vnt.', kiekis: null },
  ],
  _duru_ziniarastis: { status: 'lentele', eilutes: 3 },
  _langu_ziniarastis: { status: 'lentele', eilutes: 4 },
  _meta: { zonos: { 1: [{ kind: 'planas' }] }, lenteles: { status: 'ok' } },
};

test('the rows a read moved: changed by more than a cent, new, gone — matched by id, else by label', () => {
  const r = rowChanges(before.darbu_sarasas, after.darbu_sarasas);
  assert.deepEqual(r.changed.map((c) => [c.aprasymas, c.from, c.to, c.unit]), [
    ['Grindjuostės', 40, 41.2, 'm'], ['Be id', 1, null, 'vnt.'],
  ]);
  assert.deepEqual(r.added.map((c) => [c.aprasymas, c.to]), [['Hidroizoliacija', 9]]);
  assert.deepEqual(r.removed.map((c) => [c.aprasymas, c.from]), [['Kampai', 12]]);
});

test('the reads that came with it count as changes when they appear — the same read again does not', () => {
  assert.deepEqual(readChanges(before, after), ['_langu_ziniarastis', 'lenteles']);
  assert.deepEqual(readChanges(after, after), []);
  assert.deepEqual(readChanges({}, { _apdailos_lentele: { eilutes: 7 }, _meta: { zonos: { 2: [] } } }),
    ['_apdailos_lentele', 'zonos']);
});

test('the diff carries rooms, rows and reads; the count is every row that moved', () => {
  const rooms = { at: 'T', changed: [{ nr: '01', fields: [] }], kept: [], added: [], removed: [] };
  const d = withChanges(rooms, before, after);
  assert.equal(d.at, 'T');
  assert.equal(d.changed.length, 1, 'the rooms part stays as the re-read recorded it');
  assert.equal(rowChangeCount(d), 4);
  assert.deepEqual(d.perskaityta, ['_langu_ziniarastis', 'lenteles']);
  assert.equal(rowChangeCount(withChanges(null, before, before)), 0, 'no rooms diff and nothing moved');
  assert.equal(rowChangeCount({ changed: [] }), 0, 'an older diff without rows');
});

test('„Atšaukti" puts back the save just before the newest read, and says how many later saves go with it', () => {
  const versions = [
    { id: 9, saltinis: 'issaugota', dabartine: true },
    { id: 8, saltinis: 'issaugota' },
    { id: 7, saltinis: 'perskaityta' },
    { id: 6, saltinis: 'issaugota' },
    { id: 5, saltinis: 'lapas' },
  ];
  const u = rereadUndoTarget(versions);
  assert.equal(u.target.id, 6);
  assert.equal(u.read.id, 7);
  assert.equal(u.later, 2);
  assert.equal(rereadUndoTarget([{ id: 3, saltinis: 'lapas', dabartine: true }, { id: 2, saltinis: 'kita' }]).later, 0);
  assert.equal(rereadUndoTarget([{ id: 1, saltinis: 'perskaityta' }]), null, 'nothing saved before the read');
  assert.equal(rereadUndoTarget([{ id: 1, saltinis: 'issaugota' }]), null, 'no read at all');
  assert.equal(rereadUndoTarget(null), null);
});

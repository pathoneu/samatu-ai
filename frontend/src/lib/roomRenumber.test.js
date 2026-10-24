import test from 'node:test';
import assert from 'node:assert/strict';
import { renumberMap, renumberProject, carryIdentity } from './roomRenumber.js';
import { mergeFreeReread } from './freeReread.js';

// A project read before the room identity came from the drawing: the model's keys K1/K2/D1 (v4 Phase 3a).
const stored = () => ({
  id: 'p', name: 'Namas', vat_rate: 21,
  _meta: { model: 'x' },
  _per_room_overrides: { K2: { lubu_aukstis_m: 2.7 } },
  _apimtis: { patalpos_ne: ['D1'], patalpu_sritys_ne: { K1: ['grindys'] }, darbai_ne: ['elektra'] },
  _overrides: { garazas_painted: false, apimtis: { patalpos_ne: ['D1'], patalpu_sritys_ne: { K1: ['grindys'] } } },
  darbu_sarasas: [{ id: 'r1', aprasymas: 'Sienų glaistymas/dažymas', kiekis: 120, kaina: 6.5,
    contributions: [{ room_nr: 'K1', value: 60 }, { room_nr: 'K2', value: 60 }] }],
  patalpos: [
    { nr: 'K1', pavadinimas: 'Koridorius', plotas_m2: 16.14, perimetras_m: 24, user_verified_at: '2026-10-20T10:00:00Z' },
    { nr: 'K2', pavadinimas: 'Miegamasis', plotas_m2: 14.56, perimetras_m: 15.4, perimetras_saltinis: 'user_override' },
    { nr: 'D1', pavadinimas: 'Koridorius', plotas_m2: 12.09, perimetras_m: 22, polygon_source: 'synthesized_from_bbox' },
  ],
});

// …and the free re-read's answer: the drawing's numbers, the lane's outlines, the map.
const answer = () => ({
  status: 'ok', lane: 'applied',
  _perkeisti_numeriai: { K1: '1-1', K2: '1-2', D1: '2-1' },
  _meta: { geometrija: { versija: 17 }, kambariu_tapatybe: { saltinis: 'lentele' } },
  patalpos: [
    { nr: '1-1', _vienetas: 1, _nr_brezinyje: '1', _modelio_nr: 'K1', pavadinimas: 'Koridorius', plotas_m2: 16.14, perimetras_m: 23.1, perimetras_saltinis: 'matmenu_eilutes', polygon_source: 'vektoriniai_konturai' },
    { nr: '1-2', _vienetas: 1, _nr_brezinyje: '2', _modelio_nr: 'K2', pavadinimas: 'Miegamasis', plotas_m2: 14.56, perimetras_m: 16.0, perimetras_saltinis: 'matmenu_eilutes', polygon_source: 'vektoriniai_konturai' },
    { nr: '2-1', _vienetas: 2, _nr_brezinyje: '1', _modelio_nr: 'D1', pavadinimas: 'Koridorius', plotas_m2: 12.09, perimetras_m: 21.2, perimetras_saltinis: 'matmenu_eilutes', polygon_source: 'vektoriniai_konturai' },
  ],
});

test('the map keeps only real renames', () => {
  assert.deepEqual(renumberMap({ K1: '1-1', K2: 'K2', '': 'x', D1: null }), { K1: '1-1' });
  assert.deepEqual(renumberMap(null), {});
});

test('renumbering moves every room key he set something under — and nothing else', () => {
  const p = stored();
  const out = renumberProject(p, { K1: '1-1', K2: '1-2', D1: '2-1' });
  assert.deepEqual(out.patalpos.map((r) => [r.nr, r._modelio_nr]), [['1-1', 'K1'], ['1-2', 'K2'], ['2-1', 'D1']]);
  assert.deepEqual(out._per_room_overrides, { '1-2': { lubu_aukstis_m: 2.7 } });
  assert.deepEqual(out._apimtis, { patalpos_ne: ['2-1'], patalpu_sritys_ne: { '1-1': ['grindys'] }, darbai_ne: ['elektra'] });
  assert.deepEqual(out._overrides.apimtis.patalpos_ne, ['2-1']);
  assert.equal(out._overrides.garazas_painted, false);
  assert.deepEqual(out.darbu_sarasas[0].contributions.map((c) => c.room_nr), ['1-1', '1-2']);
  assert.equal(out.darbu_sarasas[0].kaina, 6.5);
  assert.deepEqual(out._perkeisti_numeriai, { K1: '1-1', K2: '1-2', D1: '2-1' });
  assert.equal(p.patalpos[0].nr, 'K1', 'pure — the stored project is not touched');
  assert.equal(renumberProject(p, {}), p);
});

test('an earlier map is composed with the new one', () => {
  const out = renumberProject({ patalpos: [{ nr: 'K2' }], _perkeisti_numeriai: { X: 'K2' } }, { K2: '1-2' });
  assert.deepEqual(out._perkeisti_numeriai, { X: '1-2', K2: '1-2' });
});

test('a free re-read that renumbers keeps his checked room, his typed length and his prices', () => {
  const { project, diff } = mergeFreeReread(stored(), answer(), 'T');
  const [r1, r2, r3] = project.patalpos;
  assert.deepEqual(project.patalpos.map((r) => r.nr), ['1-1', '1-2', '2-1'], 'no K-key left, no room twice');
  // the room he verified keeps its facts — and learns its unit
  assert.equal(r1.perimetras_m, 24);
  assert.equal(r1.user_verified_at, '2026-10-20T10:00:00Z');
  assert.equal(r1._vienetas, 1);
  assert.equal(r1._nr_brezinyje, '1');
  // the length he typed stays; the outline is the lane's
  assert.equal(r2.perimetras_m, 15.4);
  assert.equal(r2.perimetras_saltinis, 'user_override');
  assert.equal(r2.polygon_source, 'vektoriniai_konturai');
  // an untouched room takes the read
  assert.equal(r3.perimetras_m, 21.2);
  assert.deepEqual(diff.added, []);
  assert.deepEqual(diff.removed, []);
  assert.deepEqual(diff.kept.map((k) => [k.nr, k.why]), [['1-1', 'verified'], ['1-2', 'user']]);
  // what he set elsewhere follows the rooms; prices stay on their rows
  assert.deepEqual(project._per_room_overrides, { '1-2': { lubu_aukstis_m: 2.7 } });
  assert.deepEqual(project._apimtis.patalpos_ne, ['2-1']);
  assert.equal(project.darbu_sarasas[0].kaina, 6.5);
  assert.deepEqual(project._perkeisti_numeriai, { K1: '1-1', K2: '1-2', D1: '2-1' });
  assert.deepEqual(project.v8_rooms, project.patalpos);
  assert.deepEqual(project._meta.kambariu_tapatybe, { saltinis: 'lentele' });
});

test('without a map the re-read merges exactly as before', () => {
  const a = answer();
  delete a._perkeisti_numeriai;
  const { project, diff } = mergeFreeReread(stored(), a, 'T');
  // the old by-number merge: every fresh room is new, the touched old ones stay as missing
  assert.equal(diff.added.length, 3);
  assert.equal(project._perkeisti_numeriai, undefined);
});

test('carryIdentity adds only the unit keys, only to renamed rooms, only when absent', () => {
  const rooms = [{ nr: '1-1' }, { nr: '03', _vienetas: 9 }];
  const out = carryIdentity(rooms, [{ nr: '1-1', _vienetas: 1, _nr_brezinyje: '1', perimetras_m: 9 }], { K1: '1-1' });
  assert.deepEqual(out, [{ nr: '1-1', _vienetas: 1, _nr_brezinyje: '1' }, { nr: '03', _vienetas: 9 }]);
});

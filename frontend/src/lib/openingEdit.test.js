import test from 'node:test';
import assert from 'node:assert/strict';
import { openingsOnPage, openingAt, linkedEntry, openingState, applyOpeningEdit, openingForEdge, addEdgeOpening, openingText } from './openingEdit.js';

const room = {
  nr: '03', puslapio_nr: 1,
  _angos_sienose: { page: 1, angos: [
    { plotis_m: 1, line_pct: [[0.46, 0.41], [0.46, 0.44]], i: '01' },
    { plotis_m: 0.8, line_pct: [[0.5, 0.3], [0.53, 0.3]], i: 'vidus', nupiesta: 'durys' },
    { plotis_m: 1.2, line_pct: [[0.6, 0.2], [0.64, 0.2]], i: 'laukas', nupiesta: 'langas' },
  ] },
  elementai: [
    { tipas: 'duris', kiekis: 1, plotis_mm: 1000, aukstis_mm: 2100, _anga_ks: [0], _anga_i: '01' },
    { tipas: 'duris', kiekis: 2, plotis_mm: 800, aukstis_mm: 2100, _anga_ks: [1, 5] },
    { tipas: 'led', kiekis: 1 },
  ],
};

test('opening marks on a sheet and the one under a click (the focused room wins)', () => {
  assert.equal(openingsOnPage([room], 1).length, 3);
  assert.equal(openingsOnPage([room], 2).length, 0);
  const other = { nr: '01', _angos_sienose: { page: 1, angos: [{ plotis_m: 1, line_pct: [[0.46, 0.41], [0.46, 0.44]], i: '03' }] } };
  assert.equal(openingAt([room, other], 1, [0.461, 0.425], { preferNr: '01' }).nr, '01');
  assert.equal(openingAt([room, other], 1, [0.461, 0.425]).nr, '03');
  assert.equal(openingAt([room], 1, [0.2, 0.9]), null);
});

test('the pop-up starts from the entry that stands in the opening, or says passage', () => {
  assert.equal(linkedEntry(room.elementai, 1), 1);
  assert.deepEqual(openingState(room, { k: 0, plotisM: 1 }), { kind: 'durys', plotisMm: 1000, aukstisMm: 2100, linked: true });
  assert.deepEqual(openingState(room, { k: 2, plotisM: 1.2, nupiesta: 'langas' }), { kind: 'praejimas', plotisMm: 1200, aukstisMm: null, linked: false });
});

test('editing an opening rewrites its entry; a passage removes it; a shared entry gives one up', () => {
  const o0 = { k: 0, i: '01' };
  const wider = applyOpeningEdit(room.elementai, o0, { kind: 'durys', plotisMm: 1100 });
  assert.equal(wider[0].plotis_mm, 1100); assert.equal(wider[0]._dydis_user, true); assert.equal(wider[0].aukstis_mm, 2100);
  assert.equal(applyOpeningEdit(room.elementai, o0, { kind: 'durys', plotisMm: 1000 }), null);
  const win = applyOpeningEdit(room.elementai, o0, { kind: 'langas', plotisMm: 1000 });
  assert.equal(win[0].tipas, 'langas'); assert.equal(win[0].aukstis_mm, 1500);
  assert.equal(applyOpeningEdit(room.elementai, o0, { kind: 'praejimas' }).length, 2);
  const split = applyOpeningEdit(room.elementai, { k: 1, i: 'vidus' }, { kind: 'durys', plotisMm: 900 });
  assert.equal(split[1].kiekis, 1); assert.deepEqual(split[1]._anga_ks, [5]);
  assert.deepEqual(split[3], { tipas: 'duris', kiekis: 1, plotis_mm: 900, aukstis_mm: 2100, _anga_ks: [1], _is_sienu_angos: 'vidus', _dydis_user: true });
  const added = applyOpeningEdit(room.elementai, { k: 2, i: 'laukas' }, { kind: 'langas', plotisMm: 1200 });
  assert.equal(added.length, 4); assert.equal(added[3].tipas, 'langas');
  assert.equal(applyOpeningEdit(room.elementai, { k: 2 }, { kind: 'praejimas' }), null);
  assert.equal(applyOpeningEdit(room.elementai, o0, { kind: 'durys', plotisMm: 0 }), null);
});

test('„Iškirpti angą" on an outline edge takes the opening the walls show there, else a standard door', () => {
  const near = openingForEdge(room, 1, [0.62, 0.205], { w: 1000, h: 1000 });
  assert.equal(near.from, 'walls'); assert.equal(near.kind, 'langas'); assert.equal(near.plotisMm, 1200);
  const far = openingForEdge(room, 1, [0.1, 0.9], { w: 1000, h: 1000 });
  assert.equal(far.from, 'standard'); assert.equal(far.plotisMm, 900);
  assert.equal(addEdgeOpening(room.elementai, far).length, 4);
  assert.equal(openingText('durys', 900), 'Durys 0,90 m');
  assert.equal(openingText('praejimas'), 'Praėjimas');
});

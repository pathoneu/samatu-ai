/**
 * A room's doors and windows set to the number he typed on the question card (2026-10-19, „negaliu iškart vietoje
 * pataisyti to, ką reikia"). The walls pass's marks decide which units go and which come.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import { countChangeText, setOpeningCount, setRoomOpeningCounts } from './openingCounts.js';

// objektas_h 03 Koridorius as stored: 4 doors stand in openings, 3 the walls show no opening for, an LED niche
const corridor = () => [
  { tipas: 'nisa_LED', kiekis: 1 },
  { tipas: 'pasleptos_duris', kiekis: 1, plotis_mm: 870, aukstis_mm: 2400, _anga_ks: [5], _anga_i: '11' },
  { tipas: 'duris', kiekis: 1, plotis_mm: 800, aukstis_mm: 2100, _anga_ks: [4], _anga_i: '07' },
  { tipas: 'duris', kiekis: 1, plotis_mm: 770, aukstis_mm: 2100, _anga_ks: [3], _anga_i: '06' },
  { tipas: 'duris', kiekis: 1, plotis_mm: 1000, aukstis_mm: 2100, _anga_ks: [0], _anga_i: '01' },
  { tipas: 'duris', kiekis: 1, plotis_mm: 1000, aukstis_mm: 2100, _be_angos: true },
  { tipas: 'duris', kiekis: 1, plotis_mm: 900, aukstis_mm: 2100, _be_angos: true },
  { tipas: 'pasleptos_duris', kiekis: 1, plotis_mm: 900, aukstis_mm: 2400, _be_angos: true },
];
const doors = (els) => els.filter((e) => ['duris', 'pasleptos_duris'].includes(e.tipas)).reduce((s, e) => s + e.kiekis, 0);

test('the walls\' number takes out exactly the doors no opening backs — the niche and the backed doors stay', () => {
  const r = setOpeningCount(corridor(), 'durys', 4);
  assert.equal(doors(r.elementai), 4);
  assert.ok(r.elementai.some((e) => e.tipas === 'nisa_LED'), 'an LED niche is never touched');
  assert.ok(r.elementai.every((e) => !e._be_angos), 'the three unbacked doors are gone');
  assert.deepEqual(r.removed.map((x) => x.plotis_mm), [1000, 900, 900]);
  assert.equal(r.added.length, 0);
  assert.equal(countChangeText(r, 'durys'), 'Išimsiu 3 duris (1,00, 0,90 ir 0,90 m) — jų angų sienose nėra.');
});

test('a number between keeps the unbacked doors in list order; the list number changes nothing', () => {
  const r5 = setOpeningCount(corridor(), 'durys', 5);
  assert.equal(doors(r5.elementai), 5);
  assert.deepEqual(r5.removed.map((x) => x.plotis_mm), [900, 900]);
  const r7 = setOpeningCount(corridor(), 'durys', 7);
  assert.equal(r7.changed, false);
  assert.deepEqual(r7.elementai, corridor());
  assert.equal(countChangeText(r7, 'durys'), 'Sąrašas nesikeis.');
});

test('fewer than the walls back: the last backed door stays on its element at 0 (the engine keeps its opening empty)', () => {
  const r = setOpeningCount(corridor(), 'durys', 3);
  assert.equal(doors(r.elementai), 3);
  const last = r.elementai.find((e) => e.plotis_mm === 1000 && e._anga_ks);
  assert.equal(last.kiekis, 0);
  assert.ok(!countChangeText(r, 'durys').includes('angų sienose nėra'), 'a backed door removed is not said to have no opening');
});

test('more than the list: standard sizes, the way „+ Durys" adds them', () => {
  const r = setOpeningCount(corridor(), 'durys', 8);
  assert.equal(doors(r.elementai), 8);
  assert.deepEqual(r.added, [{ plotis_mm: 900, from: 'standard' }]);
  assert.equal(countChangeText(r, 'durys'), 'Pridėsiu 1 duris (0,90 m) — standartinio dydžio.');
});

test('listed windows no opening took are stood in the free openings at the drawn width and their own height', () => {
  // objektas_a 102: two 3,00 m windows stand nowhere, the walls keep 3,90 and 0,96 m openings to the outside
  const els = [
    { tipas: 'langas', kiekis: 2, plotis_mm: 3000, aukstis_mm: 2600 },
    { tipas: 'langas', kiekis: 1, plotis_mm: 2110, aukstis_mm: 2600, _anga_ks: [1] },
    { tipas: 'duris', kiekis: 1, plotis_mm: 1730, aukstis_mm: 2400, _anga_ks: [2] },
  ];
  const free = [{ plotis_m: 3.9, i: 'laukas' }, { plotis_m: 0.96, i: 'laukas' }];
  const r = setOpeningCount(els, 'langai', 3, free);
  const windows = r.elementai.filter((e) => e.tipas === 'langas');
  assert.equal(windows.reduce((s, e) => s + e.kiekis, 0), 3);
  assert.deepEqual(windows.filter((e) => e._is_sienu_angos).map((e) => [e.plotis_mm, e.aukstis_mm, e._is_sienu_angos]),
    [[3900, 2600, 'laukas'], [1000, 2600, 'laukas']]);
  assert.equal(countChangeText(r, 'langai'), 'Langai (3,00 ir 3,00 m) bus pakeisti nubraižytais (3,90 ir 1,00 m).');
});

test('a room the walls were never read for: every listed unit counts as it is; none listed and 0 changes nothing', () => {
  const old = [{ tipas: 'duris', kiekis: 2, plotis_mm: 800, aukstis_mm: 2100 }];
  assert.equal(setOpeningCount(old, 'durys', 2).changed, false);
  const both = setRoomOpeningCounts([], { durys: 0, langai: 0 }, {});
  assert.equal(both.changed, false);
  assert.deepEqual(both.elementai, []);
  const added = setRoomOpeningCounts([], { durys: 1, langai: 2 }, {});
  assert.equal(added.elementai.length, 2);
  assert.deepEqual(added.elementai.map((e) => [e.tipas, e.kiekis, e.plotis_mm, e.aukstis_mm]), [['duris', 1, 900, 2100], ['langas', 2, 1200, 1500]]);
  assert.equal(countChangeText(added.langai, 'langai'), 'Pridėsiu 2 langus (1,20 ir 1,20 m) — standartinio dydžio.');
});

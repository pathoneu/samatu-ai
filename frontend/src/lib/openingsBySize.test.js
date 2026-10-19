// Pathon v3 W5-D D11 #76 — openings grouped by kind and size in Kiekiai.
import test from 'node:test';
import assert from 'node:assert/strict';
import { openingsBySize } from './openingsBySize.js';

test('doors and windows by size, a shared door once, unknown sizes apart', () => {
  const project = {
    patalpos: [
      { nr: '01', elementai: [
        { tipas: 'duris', kiekis: 1, plotis_mm: 900, aukstis_mm: 2100 },
        { tipas: 'langas', kiekis: 2, plotis_mm: 1200, aukstis_mm: 1500 },
        { tipas: 'nisa_LED', kiekis: 1, ilgis_m: 3 }] },
      { nr: '02', elementai: [
        { tipas: 'duris', kiekis: 1, plotis_mm: 900, aukstis_mm: 2100, _bendra_su: '01', _bendra_su_n: 1 },
        { tipas: 'duris', kiekis: 2, plotis_mm: 900, aukstis_mm: 2100 },
        { tipas: 'pasleptos_duris', kiekis: 1, plotis_mm: 870, aukstis_mm: 2400 },
        { tipas: 'langas', kiekis: 1 }] },
      { nr: '03', _neskaiciuoti: true, elementai: [{ tipas: 'duris', kiekis: 5, plotis_mm: 800, aukstis_mm: 2100 }] },
    ],
  };
  const got = openingsBySize(project).map((g) => [g.label, g.size, g.n, g.rooms.join(',')]);
  assert.deepEqual(got, [
    ['Durys', '900 × 2100', 3, '01,02'],
    ['Paslėptos durys', '870 × 2400', 1, '02'],
    ['Langai', '1200 × 1500', 2, '01'],
    ['Langai', 'dydis nežinomas', 1, '02'],
  ]);
  assert.deepEqual(openingsBySize({}), []);
});

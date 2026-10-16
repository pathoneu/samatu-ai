import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { effectiveKodas } from './kodas.js';

const CASES = JSON.parse(readFileSync(new URL('./kodas.cases.json', import.meta.url), 'utf8'));

// The browser gets the defaults and the section table from GET /api/assemblies;
// these are the server's own (api/assemblies_default.py) for the rows the cases use.
const DEFAULTS = [
  { id: 'numatyta-sienu-dazymas', is_default: true, kodas: '01.01', taikoma: { aprasymas: 'Sienų glaistymas/dažymas{vieta}' } },
  { id: 'numatyta-lubu-dazymas', is_default: true, kodas: '01.02', taikoma: { aprasymas: 'Lubų glaistymas/dažymas{vieta}' } },
  { id: 'numatyta-rotband', is_default: true, kodas: '01.03', taikoma: { aprasymas: 'Sienų lyginimas Knauf Rotband' } },
  { id: 'numatyta-plyteles-klijavimas', is_default: true, kodas: '03.01', taikoma: { aprasymas: '{vieta} plytelių klijavimas' } },
];
const KODAI = { paint: '01', gkp: '02', tile: '03', waterproof: '04', floor: '05', plumbing: '06',
  electrical: '07', extras: '08', materials: '09', out_of_scope: '99' };

for (const c of CASES.cases) {
  test(`kodas: ${c.name}`, () => {
    assert.equal(effectiveKodas(c.row, [...CASES.own, ...DEFAULTS], KODAI), c.want);
  });
}

test('export lines carry a code only when he asked for the column', async () => {
  const { exportLines } = await import('./exportLines.js');
  const project = { darbu_sarasas: [
    { aprasymas: 'Sienų glaistymas/dažymas', skyrius: 'Sienų glaistymas dažymas', skyrius_enum: 'paint', vnt: 'm2', kiekis: 10, kaina: 5 },
    { aprasymas: 'Klozeto montavimas', skyrius: 'Santechnikos darbai', skyrius_enum: 'plumbing', vnt: 'vnt', kiekis: 2, kodas: 'S-9' },
  ] };
  assert.ok(exportLines(project).every((l) => !('kodas' in l)));
  const lines = exportLines(project, null, { kodasOf: (r) => effectiveKodas(r, DEFAULTS, KODAI) });
  assert.deepEqual(lines.map((l) => l.kodas), ['01.01', 'S-9']);
});

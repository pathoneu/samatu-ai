/**
 * The 2026-09-02 sienų/lubų section split, browser side.
 *
 * Two halves have to agree with the backend or a project shows the same work
 * twice: the project-load migration (`migrateSkyriusRow`, mirror of
 * `vision_call.migrate_skyrius_row`) and the merge's exact-label rename map
 * (mirror of `api/recompute_quantities._PAINT_SPLIT_EXACT_RENAMES`).
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { migrateSkyriusRow } from './projectStore.js';
import { mergeDarbuSarasasEdits } from './mergeDarbuSarasas.js';

const SK_MERGED = 'Sienų lubų glaistymas dažymas';
const SK_SIENOS = 'Sienų glaistymas dažymas';
const SK_LUBOS = 'Lubų glaistymas dažymas';

test('a merged-section row is sorted by its aprašymas', () => {
  const cases = [
    ['Lubų pirminis glaistymas Q1', SK_LUBOS],
    ['Lubų glaistymas/dažymas (iki 3m aukščio)', SK_LUBOS],
    ['Lubų karnizo sumontavimas', SK_LUBOS],
    ['LED nišų glaistymas/dažymas', SK_LUBOS],
    ['Sienų lyginimas Knauf Rotband', SK_SIENOS],
    ['Angokraščių glaistymas-dažymas', SK_SIENOS],
    ['Dažymo kampų montavimas', SK_SIENOS],
    ['Grindjuosčių sumontavimas', SK_SIENOS],
  ];
  for (const [aprasymas, expected] of cases) {
    assert.equal(migrateSkyriusRow(SK_MERGED, aprasymas), expected, aprasymas);
  }
});

test('the legacy mojibake names still migrate, then split', () => {
  assert.equal(migrateSkyriusRow('Glaistymas dazymas', 'Lubų karnizo dažymas'), SK_LUBOS);
  assert.equal(migrateSkyriusRow('Glaistymas dažymas', 'Sienų dažymas'), SK_SIENOS);
  assert.equal(migrateSkyriusRow('Plyteles', 'Vonios plytelės'), 'Plytelių klijavimas');
  assert.equal(migrateSkyriusRow('GKP lubu montavimas', 'GKP lapai'), 'GKP montavimas');
});

test('a valid new name is not mapped away', () => {
  assert.equal(migrateSkyriusRow(SK_SIENOS, 'Dažymo kampų montavimas'), SK_SIENOS);
  assert.equal(migrateSkyriusRow(SK_LUBOS, 'Lubų karnizo dažymas'), SK_LUBOS);
});

test('an unknown section passes through untouched', () => {
  assert.equal(migrateSkyriusRow('Kiti darbai', 'Vartotojo eilutė'), 'Kiti darbai');
  assert.equal(migrateSkyriusRow('', 'x'), '');
  assert.equal(migrateSkyriusRow(null, null), '');
});

test('the old combined paint line is not carried alongside its successors', () => {
  // The exact failure this map exists to prevent: the browser merge sees a
  // label the rebuild no longer produces, and pass 3 appends it — so the
  // sąmata shows the priced old line AND the two new ones.
  const old = [{
    aprasymas: 'Sienų, lubų glaistymas/dažymas (iki 3m aukščio)',
    kiekis: 376.5, kaina: 8, suma: 3012,
  }];
  const rebuilt = [
    { aprasymas: 'Sienų glaistymas/dažymas (iki 3m aukščio)', kiekis: 300 },
    { aprasymas: 'Lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 141.31 },
  ];
  const notes = [];
  const merged = mergeDarbuSarasasEdits(rebuilt, old, notes);
  assert.equal(merged.length, 2, JSON.stringify(merged.map(r => r.aprasymas)));
  const byLabel = Object.fromEntries(merged.map(r => [r.aprasymas, r]));
  // The money follows the walls half, as it does on the backend.
  assert.equal(byLabel['Sienų glaistymas/dažymas (iki 3m aukščio)'].kaina, 8);
  assert.equal(byLabel['Sienų glaistymas/dažymas (iki 3m aukščio)'].suma, 2400);
  assert.equal(byLabel['Lubų glaistymas/dažymas (iki 3m aukščio)'].kaina, undefined);
  assert.equal(notes.filter(n => n.reason === 'orphan_carried').length, 0);
});

test('both tiers of the old combined line map to their own tier', () => {
  const old = [
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 300, kaina: 8 },
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (virš 3m aukščio)', kiekis: 200, kaina: 12 },
  ];
  const rebuilt = [
    { aprasymas: 'Sienų glaistymas/dažymas (iki 3m aukščio)', kiekis: 250 },
    { aprasymas: 'Sienų glaistymas/dažymas (virš 3m aukščio)', kiekis: 150 },
    { aprasymas: 'Lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 100 },
  ];
  const merged = mergeDarbuSarasasEdits(rebuilt, old, []);
  assert.equal(merged.length, 3, JSON.stringify(merged.map(r => r.aprasymas)));
  const byLabel = Object.fromEntries(merged.map(r => [r.aprasymas, r]));
  assert.equal(byLabel['Sienų glaistymas/dažymas (iki 3m aukščio)'].kaina, 8);
  assert.equal(byLabel['Sienų glaistymas/dažymas (virš 3m aukščio)'].kaina, 12);
});

test('a priced row keeps its price when only its section changes', () => {
  const old = [{
    skyrius: SK_MERGED, aprasymas: 'Lubų dažymas (2 sluoksniai)',
    kiekis: 165.64, kaina: 4.2, suma: 695.69,
  }];
  const rebuilt = [{
    skyrius: SK_LUBOS, aprasymas: 'Lubų dažymas (2 sluoksniai)', kiekis: 141.31,
  }];
  const merged = mergeDarbuSarasasEdits(rebuilt, old, []);
  assert.equal(merged.length, 1);
  assert.equal(merged[0].skyrius, SK_LUBOS);
  assert.equal(merged[0].kaina, 4.2);
  assert.equal(Math.round(merged[0].suma * 100) / 100, 593.5);
});

test('the ASCII-stripped shopping list migrates like every other section', () => {
  // An export written by a tool that drops diacritics ("Medziagos") used to
  // load as a section of its own, so the materials scattered away from the
  // foot of the sąmata. Mirror of the backend's SKYRIUS_LEGACY_MIGRATION.
  assert.equal(migrateSkyriusRow('Medziagos', 'Dažai sienoms'), 'Medžiagos');
  assert.equal(migrateSkyriusRow('Medžiagos', 'Dažai sienoms'), 'Medžiagos');
});

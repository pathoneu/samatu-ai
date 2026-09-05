import test from 'node:test';
import assert from 'node:assert/strict';
import {
  EXTRA_SECTION, FILL, acceptSuggestion, canTypeQuantity, darbaiFingerprint,
  exportRows, groupBySection, isTypedRow, sectionsOf, setPrice, summarize,
  typeQuantity, typedSourceRow,
} from './samataTemplate.js';

// Every label below is invented — no customer wording.
const blank = {
  nr: 1, skyrius: 'Omega išlaidos', aprasymas: 'Gadget nuoma', mato_vnt: 'd.d.',
  kiekis: null, kaina: null, id: 'tpl-gadget', _sablonas: true,
  _sablono_eile: 'c:gadget_gap', _pildymas: FILL.EMPTY, _saltinio_id: [],
  _pastaba: 'Iš brėžinio nenustatyta — įrašykite',
};
const suggested = {
  nr: 2, skyrius: 'Alfa darbai', aprasymas: 'Widget montavimas', mato_vnt: 'vnt',
  kiekis: null, kaina: 4, id: 'tpl-widget', _sablonas: true, _sablono_eile: 'c:widget',
  _pildymas: FILL.SUGGESTED, _siulomas_kiekis: 42, _saltinio_id: ['w-1'],
};
const done = {
  nr: 3, skyrius: 'Alfa darbai', aprasymas: 'Gizmo klijavimas', mato_vnt: 'm2',
  kiekis: 20, kaina: 7, suma: 140, id: 'tpl-gizmo', _sablonas: true,
  _sablono_eile: 'c:gizmo', _pildymas: FILL.DONE, _saltinio_id: ['g-1'],
};
const kita = {
  nr: 4, skyrius: EXTRA_SECTION, aprasymas: 'Mūsų eilutė', mato_vnt: 'm',
  kiekis: 3, kaina: 0, id: 'x-1', _sablonas: false, _pildymas: FILL.SUGGESTED,
  _saltinio_id: ['x-1'],
};
const rendered = [blank, suggested, done, kita];

const darbai = [
  { id: 'w-1', eil_nr: 1, aprasymas: 'Widget assembly', mato_vnt: 'vnt', kiekis: 42, kaina: 4, skyrius: 'Darbai' },
  { id: 'g-1', eil_nr: 2, aprasymas: 'Gizmo glue', mato_vnt: 'm2', kiekis: 20, kaina: 7, skyrius: 'Darbai',
    roll_up: [{ op: 'sum', value: 20 }] },
  { id: 'x-1', eil_nr: 3, aprasymas: 'Mūsų eilutė', mato_vnt: 'm', kiekis: 3, kaina: 0, skyrius: 'Darbai' },
];

test('groupBySection keeps HIS order and puts Kita where the render put it', () => {
  const groups = groupBySection(rendered);
  assert.deepEqual(groups.map((g) => g.label), ['Omega išlaidos', 'Alfa darbai', EXTRA_SECTION]);
  assert.equal(groups[1].rows.length, 2);
});

test('summarize mirrors the backend summary and ignores Kita rows', () => {
  assert.deepEqual(summarize(rendered), {
    eilutes: 4, sablonoEilutes: 3, kitosEilutes: 1, uzpildyta: 1, pasiulyta: 1, tuscia: 1,
  });
});

test('sectionsOf counts blank rows too — a section of only blanks still exports', () => {
  assert.deepEqual(sectionsOf(rendered), [
    { name: 'Omega išlaidos', count: 1 },
    { name: 'Alfa darbai', count: 2 },
    { name: EXTRA_SECTION, count: 1 },
  ]);
});

test('typing into a blank cell adds a hand-added row that carries the family key', () => {
  const next = typeQuantity(darbai, blank, 3, { now: '2026-09-05T08:00:00.000Z' });
  assert.equal(next.length, darbai.length + 1);
  const row = next.find(isTypedRow);
  assert.ok(row.id.startsWith('rnk-'));
  assert.equal(row._sablono_eile, 'c:gadget_gap');
  assert.equal(row.aprasymas, 'Gadget nuoma');
  assert.equal(row.mato_vnt, 'd.d.');
  assert.equal(row.skyrius, 'Omega išlaidos');
  assert.equal(row.kiekis, 3);
  assert.equal(row.manual_override, true);
  assert.equal(row.quantity_source, 'manual_override');
  assert.equal(row.eil_nr, 4, 'max existing + 1, never length + 1');
  assert.equal(row.kaina, 0);
  assert.equal(row.kaina_source, undefined, 'no price typed → no price source');
});

test('typing again updates the SAME row instead of adding a second one', () => {
  const once = typeQuantity(darbai, blank, 3, { now: 't1' });
  const typed = once.find(isTypedRow);
  const filled = { ...blank, _pildymas: FILL.DONE, kiekis: 3, _saltinio_id: [typed.id] };
  assert.equal(typedSourceRow(filled, once), typed);
  assert.equal(canTypeQuantity(filled, once), true);
  const twice = typeQuantity(once, filled, 5, { kaina: 12, now: 't2' });
  assert.equal(twice.length, once.length);
  const again = twice.find(isTypedRow);
  assert.equal(again.kiekis, 5);
  assert.equal(again.kaina, 12);
  assert.equal(again.suma, 60);
  assert.equal(again.kaina_source, 'manual');
});

test('a cell filled from OUR computed rows cannot be typed over', () => {
  assert.equal(canTypeQuantity(done, darbai), false);
  assert.equal(canTypeQuantity(suggested, darbai), false);
  assert.equal(canTypeQuantity(kita, darbai), false);
  assert.throws(() => typeQuantity(darbai, done, 99));
  assert.throws(() => typeQuantity(darbai, blank, -1));
});

test('accepting a suggestion stamps the source rows like Patikra does', () => {
  const next = acceptSuggestion(darbai, suggested, '2026-09-05T08:00:00.000Z');
  const w = next.find((r) => r.id === 'w-1');
  assert.equal(w.user_verified_at, '2026-09-05T08:00:00.000Z');
  assert.equal(w.quantity_source, 'user_verified_ai');
  assert.equal(w.confidence, 'high');
  assert.equal(next.find((r) => r.id === 'g-1').user_verified_at, undefined);
  assert.equal(next[0] === darbai[0], false, 'a new object, never a mutation');
  assert.equal(darbai[0].user_verified_at, undefined);
});

test('a price lands on the single source row', () => {
  const next = setPrice(darbai, done, 9.5);
  const g = next.find((r) => r.id === 'g-1');
  assert.equal(g.kaina, 9.5);
  assert.equal(g.suma, 190);
  assert.equal(g.kaina_source, 'manual');
  assert.throws(() => setPrice(darbai, blank, 5), /No single source/);
});

test('exportRows keeps blank cells blank and never exports a suggestion', () => {
  const rows = exportRows(rendered);
  assert.equal(rows.length, 4);
  const g = rows.find((r) => r.aprasymas === 'Gadget nuoma');
  assert.equal(g.kiekis, null);
  assert.equal(g.suma, null);
  const w = rows.find((r) => r.aprasymas === 'Widget montavimas');
  assert.equal(w.kiekis, null, 'the greyed 42 must not reach his client');
  assert.equal('_siulomas_kiekis' in w, false);
  const d = rows.find((r) => r.aprasymas === 'Gizmo klijavimas');
  assert.equal(d.kiekis, 20);
  assert.equal(d.suma, 140);
  assert.equal(d.skyrius, 'Alfa darbai');
});

test('exportRows honours the section filter', () => {
  const rows = exportRows(rendered, new Set(['Alfa darbai']));
  assert.deepEqual(rows.map((r) => r.aprasymas), ['Widget montavimas', 'Gizmo klijavimas']);
});

test('darbaiFingerprint moves only when something the render reads moves', () => {
  const a = darbaiFingerprint(darbai);
  assert.equal(a, darbaiFingerprint(darbai.map((r) => ({ ...r, aprasymas: r.aprasymas + '!' }))),
    'a relabel does not change the fingerprint');
  assert.notEqual(a, darbaiFingerprint(acceptSuggestion(darbai, suggested, 'now')));
  assert.notEqual(a, darbaiFingerprint(setPrice(darbai, done, 1)));
});

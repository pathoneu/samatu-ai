import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeFreeReread, freeRereadSummary } from './freeReread.js';

// A project read before the geometry lane existed: guessed perimeters, box outlines, floors by purpose.
const base = () => ({
  id: 'p1', name: 'Namas', vat_rate: 21,
  _meta: { model: 'x', apdailos_page: 3 },
  _overrides: { lubu_auksciai: { '02': 3.1 } },
  darbu_sarasas: [{ id: 'a', aprasymas: 'Grindjuosčių montavimas', kiekis: 40, kaina: 3.5 }],
  patalpos: [
    { nr: '01', pavadinimas: 'Tambūras', plotas_m2: 4.48, perimetras_m: 8.6, user_verified_at: '2026-09-18T10:00:00Z' },
    { nr: '02', pavadinimas: 'Katilinė', plotas_m2: 6.9, perimetras_m: 11.0, perimetras_saltinis: 'user_override' },
    { nr: '03', pavadinimas: 'Koridorius', plotas_m2: 10.12, perimetras_m: 16.4, polygon_source: 'synthesized_from_bbox' },
  ],
});

// …and what the lane read for it, for free.
const result = () => ({
  status: 'ok', lane: 'applied',
  _meta: { model: 'x', apdailos_page: 3, geometrija: { versija: 3, konturai: ['02', '03'] } },
  santrauka: { konturai: 2, perimetrai_sudeti: 1, perimetrai_tusti: 1, grindu_dangos: 3, sekundes: 0.8 },
  patalpos: [
    { nr: '01', pavadinimas: 'Tambūras', plotas_m2: 4.48, perimetras_m: 8.9, grindu_danga: 'minksta', grindu_danga_saltinis: 'grindu_planas' },
    { nr: '02', pavadinimas: 'Katilinė', plotas_m2: 6.9, perimetras_m: 12.17, perimetras_saltinis: 'matmenu_eilutes',
      polygon_source: 'vektoriniai_konturai', polygon_pct: [[0.4, 0.25], [0.46, 0.25], [0.46, 0.38]], grindu_danga: 'plyteles', grindu_danga_saltinis: 'grindu_planas' },
    { nr: '03', pavadinimas: 'Koridorius', plotas_m2: 10.12, perimetras_m: 21.23, perimetras_saltinis: 'konturo_ivertis',
      polygon_source: 'vektoriniai_konturai', polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]], grindu_danga: 'minksta', grindu_danga_saltinis: 'grindu_planas' },
  ],
});

test('a free re-read takes what the lane read — and leaves his own work alone', () => {
  const { project, diff } = mergeFreeReread(base(), result(), '2026-09-20T12:00:00Z');
  const [r1, r2, r3] = project.patalpos;
  // a room he verified keeps its facts entirely
  assert.equal(r1.perimetras_m, 8.6);
  assert.equal(r1.grindu_danga, undefined);
  // a perimeter he typed stays; the outline and the floor covering the lane read are new
  assert.equal(r2.perimetras_m, 11.0);
  assert.equal(r2.perimetras_saltinis, 'user_override');
  assert.equal(r2.polygon_source, 'vektoriniai_konturai');
  assert.equal(r2.grindu_danga, 'plyteles');
  // an untouched room takes the read
  assert.equal(r3.perimetras_m, 21.23);
  assert.equal(r3.grindu_danga, 'minksta');
  assert.deepEqual(project.v8_rooms, project.patalpos, 'both room lists — the check sheet reads v8_rooms first');
  // the diff he is shown
  assert.equal(diff.at, '2026-09-20T12:00:00Z');
  assert.deepEqual(diff.changed.map((c) => c.nr), ['02', '03']);
  assert.ok(diff.changed.find((c) => c.nr === '03').fields.some((f) => f.key === 'perimetras_m' && f.from === 16.4 && f.to === 21.23));
  assert.ok(diff.changed.find((c) => c.nr === '03').fields.some((f) => f.key === 'grindu_danga' && f.to === 'minksta'));
  assert.deepEqual(diff.kept.map((k) => [k.nr, k.why]), [['01', 'verified'], ['02', 'user']]);
  assert.deepEqual(project._reread_diff, diff);
});

test('only the rooms and the lane\'s record change — rows, prices, assumptions and the rest of the meta stay', () => {
  const b = base();
  const { project } = mergeFreeReread(b, result(), 'T');
  assert.deepEqual(project.darbu_sarasas, b.darbu_sarasas);
  assert.deepEqual(project._overrides, b._overrides);
  assert.equal(project.name, 'Namas');
  assert.deepEqual(project._meta, { model: 'x', apdailos_page: 3, geometrija: { versija: 3, konturai: ['02', '03'] } });
  assert.equal(project._geometrija_perskaityta_at, 'T');
  assert.equal(project._reextracted_at, undefined, 'this was not a paid re-read');
});

test('the door schedule and the symbol count the lane brings along land on the project — and their absence changes nothing', () => {
  const withReads = { ...result(), _duru_ziniarastis: { status: 'lentele', beapvadines: 2 }, _vector_symbols: { difuzoriai: { defined: true, count: 9 } } };
  const { project } = mergeFreeReread(base(), withReads, 'T');
  assert.equal(project._duru_ziniarastis.beapvadines, 2);
  assert.equal(project._vector_symbols.difuzoriai.count, 9);
  const kept = mergeFreeReread({ ...base(), _duru_ziniarastis: { status: 'nera' } }, result(), 'T').project;
  assert.deepEqual(kept._duru_ziniarastis, { status: 'nera' }, 'a response without the read keeps the stored one');
  assert.equal('_vector_symbols' in kept, false);
});

test('a lane that failed or returned nothing changes nothing', () => {
  const b = base();
  assert.equal(mergeFreeReread(b, { status: 'ok', lane: 'failed', patalpos: b.patalpos, _meta: b._meta }).project, null);
  assert.equal(mergeFreeReread(b, { status: 'ok', lane: 'applied', patalpos: [] }).project, null);
  assert.equal(mergeFreeReread(b, null).project, null);
});

test('a lane that read nothing new still records that it looked — so the offer is not made again', () => {
  const b = base();
  const same = { status: 'ok', lane: 'no_match', patalpos: b.patalpos, _meta: { ...b._meta, geometrija: { versija: 3 } } };
  const { project, diff } = mergeFreeReread(b, same, 'T');
  assert.equal(project._meta.geometrija.versija, 3);
  assert.deepEqual(diff.changed, []);
});

test('what the banner says afterwards', () => {
  assert.deepEqual(freeRereadSummary(result().santrauka), { konturai: 2, perimetrai: 1, tusti: 1, dangos: 3 });
  assert.deepEqual(freeRereadSummary(null), { konturai: 0, perimetrai: 0, tusti: 0, dangos: 0 });
});

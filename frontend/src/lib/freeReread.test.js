import test from 'node:test';
import assert from 'node:assert/strict';
import { mergeFreeReread } from './freeReread.js';

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

test('a lane that read nothing new still records that it looked — so the next read sees the stored geometry version', () => {
  const b = base();
  const same = { status: 'ok', lane: 'no_match', patalpos: b.patalpos, _meta: { ...b._meta, geometrija: { versija: 3 } } };
  const { project, diff } = mergeFreeReread(b, same, 'T');
  assert.equal(project._meta.geometrija.versija, 3);
  assert.deepEqual(diff.changed, []);
});

test('an outline the lane drew last time and cannot draw now leaves with the re-read — a verified room keeps it', () => {
  // 2026-09-29 (geometry_lane._forget_outline): the server answers such a room WITHOUT its old outline and
  // with the perimeter it had before; the merge takes that answer whole for a room he never touched.
  const outlined = { polygon_source: 'vektoriniai_konturai', polygon_pct: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2]],
    _konturas: { page: 1 }, _sienos: [{ ilgis_m: 4 }], _perimetras_suma: { suma_m: 14 }, perimetras_m: 14, perimetras_saltinis: 'matmenu_eilutes' };
  const b = { patalpos: [{ nr: '01', plotas_m2: 12, ...outlined }, { nr: '02', plotas_m2: 9, ...outlined, user_verified_at: 'T0' }] };
  const r = {
    status: 'ok', lane: 'applied', _meta: { geometrija: { versija: 9, konturai: [] } },
    patalpos: [
      { nr: '01', plotas_m2: 30, perimetras_m: 13.9, _konturo_priezastis: 'sienos prie numerio uždaro 12,00 m², lentelėje 30,00 m²' },
      { nr: '02', plotas_m2: 9, ...outlined, user_verified_at: 'T0' },
    ],
  };
  const [r1, r2] = mergeFreeReread(b, r, 'T').project.patalpos;
  for (const key of ['polygon_source', 'polygon_pct', '_konturas', '_sienos', '_perimetras_suma', 'perimetras_saltinis']) {
    assert.equal(r1[key], undefined, key);
  }
  assert.equal(r1.perimetras_m, 13.9);
  assert.equal(r2.polygon_source, 'vektoriniai_konturai');
  assert.equal(r2.perimetras_saltinis, 'matmenu_eilutes');
});

test('the drawing\'s tables land with the re-read: the window and finish schedules, and the „lentelės" record', () => {
  const lenteles = { versija: 1, status: 'ok', lapai: [5], lenteles: { 5: [{ table_id: 't1', bbox_pct: [0.1, 0.1, 0.4, 0.3] }] }, ziniarasciai: {} };
  const withTables = {
    ...result(),
    _meta: { ...result()._meta, lenteles },
    _langu_ziniarastis: { status: 'lentele', eilutes: 4 },
    _apdailos_lentele: { status: 'lentele', eilutes: 7 },
  };
  const { project } = mergeFreeReread(base(), withTables, 'T');
  assert.equal(project._langu_ziniarastis.eilutes, 4);
  assert.equal(project._apdailos_lentele.eilutes, 7);
  assert.deepEqual(project._meta.lenteles, lenteles);
  assert.equal(project._meta.model, 'x', 'the rest of the stored meta stays');
  // a read without them keeps the stored ones — never overwritten by their absence
  const stored = { ...base(), _langu_ziniarastis: { status: 'lentele', eilutes: 2 }, _meta: { ...base()._meta, lenteles } };
  const kept = mergeFreeReread(stored, result(), 'T').project;
  assert.equal(kept._langu_ziniarastis.eilutes, 2);
  assert.deepEqual(kept._meta.lenteles, lenteles);
});

test('sheet zones merge sheet by sheet — a sheet the read did not look at keeps its zones, a zone he drew stays', () => {
  const zone = (kind, source = 'vektoriai') => ({ kind, bbox_pct: [0, 0, 0.2, 0.2], evidence: { source, detail: '' } });
  const stored = { ...base(), _meta: { ...base()._meta, zonos: { 1: [zone('planas'), zone('legenda', 'naudotojas')], 2: [zone('antspaudas')] } } };
  const read = { ...result(), _meta: { ...result()._meta, zonos: { 1: [zone('planas'), zone('lentele')] } } };
  const { project } = mergeFreeReread(stored, read, 'T');
  assert.deepEqual(project._meta.zonos[1].map((z) => z.kind), ['planas', 'lentele', 'legenda'], 'his zone stays on the re-read sheet');
  assert.deepEqual(project._meta.zonos[2].map((z) => z.kind), ['antspaudas'], 'a sheet the read skipped keeps its zones');
  // no zones in the read: the stored ones stay as they were
  assert.deepEqual(mergeFreeReread(stored, result(), 'T').project._meta.zonos, stored._meta.zonos);
});

test('the floor sheet key lines land whole, and a read without them keeps the stored ones (W5-D D1)', () => {
  const key = [{ tekstas: 'Plyteles 60x60', klase: 'plyteles', spalva: [0.1, 0.3, 0.9], page: 4, rect_pct: [0.7, 0.1, 0.9, 0.12] }];
  const read = { ...result(), _meta: { ...result()._meta, grindu_legenda: key } };
  assert.deepEqual(mergeFreeReread(base(), read, 'T').project._meta.grindu_legenda, key);
  const stored = { ...base(), _meta: { ...base()._meta, grindu_legenda: key } };
  assert.deepEqual(mergeFreeReread(stored, result(), 'T').project._meta.grindu_legenda, key);
});

test('the designer figures and anchors (sent only with the server flag on) land, the figures list included (W5-D D6)', () => {
  const figures = [{ page: 6, label: 'Sienų dažai', value: 320, unit: 'm2' }];
  const read = { ...result(), _autoriaus_kiekiai: figures, _walls_anchor: { total_area_m2: 320 } };
  const { project } = mergeFreeReread(base(), read, 'T');
  assert.deepEqual(project._autoriaus_kiekiai, figures);
  assert.equal(project._walls_anchor.total_area_m2, 320);
  const kept = mergeFreeReread({ ...base(), _autoriaus_kiekiai: figures }, result(), 'T').project;
  assert.deepEqual(kept._autoriaus_kiekiai, figures, 'never overwritten by their absence');
});

test('the legend count proposals and the sheet kinds read from the text land with the re-read and are kept when absent', () => {
  const legendos_siulymai = { versija: 1, eilutes: [{ lapas: 3, kiekis: 13, pavadinimas: 'Priglaistomas šviestuvas' }] };
  const lapu_rusys_is_teksto = { 1: 'planas', 3: 'apšvietimo planas' };
  const fresh = { ...result(), _meta: { ...result()._meta, legendos_siulymai, lapu_rusys_is_teksto } };
  const { project } = mergeFreeReread(base(), fresh, 'T');
  assert.deepEqual(project._meta.legendos_siulymai, legendos_siulymai);
  assert.deepEqual(project._meta.lapu_rusys_is_teksto, lapu_rusys_is_teksto);
  assert.equal(project._meta.model, 'x', 'the rest of the stored meta stays');
  // a read without them keeps the stored ones — never overwritten by their absence
  const stored = { ...base(), _meta: { ...base()._meta, legendos_siulymai, lapu_rusys_is_teksto } };
  const kept = mergeFreeReread(stored, result(), 'T').project;
  assert.deepEqual(kept._meta.legendos_siulymai, legendos_siulymai);
  assert.deepEqual(kept._meta.lapu_rusys_is_teksto, lapu_rusys_is_teksto);
});

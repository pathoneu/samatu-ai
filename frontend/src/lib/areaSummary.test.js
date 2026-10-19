// Pathon v3 W5-D D13 — the project's area three ways, each with its source sentence. Sums only.
import test from 'node:test';
import assert from 'node:assert/strict';
import { areaSummary, AREA_LABELS } from './areaSummary.js';

const room = (nr, extra) => ({ nr, plotas_m2: 10, ...extra });
const outlined = (nr, m2, page = 1) => room(nr, { polygon_source: 'vektoriniai_konturai', _konturas: { page, plotas_m2: m2 } });

test('the room table total, the outlines and a footprint the drawing writes', () => {
  const project = {
    _ceiling_anchor: { total_area_m2: 143.27, label: 'BENDRAS PLOTAS', page: 1 },
    patalpos: [outlined('01', 20.5), outlined('02', 30.25), room('03', { _sujungta_i: '01', polygon_source: 'vektoriniai_konturai', _konturas: { page: 1, plotas_m2: 5 } })],
    _autoriaus_kiekiai: [{ page: 2, label: 'Užstatymo plotas', value: 160.4, unit: 'm2' }, { page: 6, label: 'Sienų dažai', value: 320, unit: 'm2' }],
  };
  const [table, outlines, footprint] = areaSummary(project);
  assert.deepEqual([table.key, outlines.key, footprint.key], ['lentele', 'konturai', 'uzstatymas']);
  assert.equal(table.value, 143.27);
  assert.equal(table.sentence, 'Patalpų lentelėje (1 psl.) parašyta „BENDRAS PLOTAS“: 143,27 m².');
  assert.equal(outlines.value, 50.75);            // the merged room is in the room that kept it
  assert.equal(outlines.sentence, 'Visų patalpų kontūrų pagal sienas plotų suma (1 psl.): 50,75 m².');
  assert.equal(footprint.value, 160.4);
  assert.equal(footprint.sentence, 'Brėžinyje (2 psl.) parašyta „Užstatymo plotas“: 160,40 m².');
  assert.equal(table.label, AREA_LABELS.lentele);
});

test('what the drawing does not give stays blank and says so', () => {
  const project = { patalpos: [outlined('01', 12), room('02')] };
  const [table, outlines, footprint] = areaSummary(project);
  assert.equal(table.value, null);
  assert.match(table.sentence, /neradau/);
  assert.equal(outlines.value, 12);
  assert.equal(outlines.sentence, '1 iš 2 patalpų kontūrų pagal sienas plotų suma (1 psl.): 12,00 m² — be patalpų, kurių kontūro nėra.');
  assert.equal(footprint.value, null);
  assert.deepEqual(areaSummary({}).map((e) => e.value), [null, null, null]);
});

test('no room table: the plan labels added up, or the table rows the rooms carry', () => {
  const labels = areaSummary({ _ceiling_anchor: { total_area_m2: 98.1, label: 'plano užrašų suma', page: 4 }, patalpos: [] })[0];
  assert.equal(labels.value, 98.1);
  assert.match(labels.sentence, /plane prie patalpų parašyti plotai \(4 psl\.\): 98,10 m²/);
  const rows = areaSummary({ patalpos: [room('1', { plotas_saltinis: 'eksplikacija', plotas_m2: 4.48 }), room('2', { plotas_saltinis: 'eksplikacija', plotas_m2: 10.1 })] })[0];
  assert.equal(rows.value, 14.58);
  assert.match(rows.sentence, /sudėtos 2 patalpų lentelės eilutės: 14,58 m²/);
});

test('no pipeline words in what he reads', () => {
  const texts = areaSummary({}).concat(areaSummary({ _ceiling_anchor: { total_area_m2: 1, page: 1 }, patalpos: [outlined('1', 1)] }))
    .flatMap((e) => [e.label, e.sentence]);
  for (const t of texts) assert.doesNotMatch(t, /analiz|ekstrakc|vision|\bmodel|zon(a|os|ą|ų|ai|oje)\b|koeficient/i);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import {
  DEFAULT_GROUPING, GROUPINGS, OVERLAY_LAYERS, exportLinesWithParts, exportSheets, groupingsFor, isGrouping,
  overlayPageChoices, overlayRequestBody, overlayScales, rowOrigin,
} from './exportGrouping.js';
import { exportLines } from './exportLines.js';

const contributions = [
  { room_nr: '01', room_name: 'Tambūras', page: 1, value: 4, unit: 'm2' },
  { room_nr: '02', room_name: 'Katilinė', page: 1, value: 6, unit: 'm2' },
];
const project = (over = {}) => ({
  darbu_sarasas: [
    { eil_nr: 1, id: 'a', aprasymas: 'Sienų dažymas', mato_vnt: 'm²', kiekis: 10, kaina: 5, skyrius: 'Dažymas',
      confidence: 'zalia', contributions, _assumption: 'Prielaida: dvi dažų sluoksnės' },
    { eil_nr: 2, id: 'b', aprasymas: 'LED nišos — suveskite ilgį', mato_vnt: 'm', kiekis: null, skyrius: 'GKP' },
    { eil_nr: 3, id: 'rnk-1', aprasymas: 'Šiukšlių išvežimas', mato_vnt: 'kompl', kiekis: 1, kaina: 90, skyrius: 'Kiti' },
    { eil_nr: 4, id: 'c', aprasymas: 'WC rėmas', mato_vnt: 'vnt', kiekis: 2, skyrius: 'Santechnika',
      manual_override: true, ai_kiekis_original: 1 },
  ],
  puslapiai: [{ nr: 1, pavadinimas: 'PLANAS' }, { nr: 5, pavadinimas: 'LUBŲ PLANAS' }],
  ...over,
});

test('the grouping choices: today first, every value the server takes', () => {
  assert.equal(GROUPINGS[0].value, DEFAULT_GROUPING);
  assert.deepEqual(GROUPINGS.map((g) => g.value),
    ['skyriai', 'patalpos', 'seimos', 'lapai', 'be_grupavimo', 'aukstai', 'butai']);
  assert.ok(isGrouping('lapai') && isGrouping('aukstai') && !isGrouping('kita'));
});

test('„Butus" is offered only when some room carries a flat (v3 M5)', () => {
  const values = (p) => groupingsFor(p).map((g) => g.value);
  assert.ok(!values({ v8_rooms: [{ nr: '01' }] }).includes('butai'));
  assert.ok(values({ v8_rooms: [{ nr: '01', butas: '3' }] }).includes('butai'));
  assert.ok(values({}).includes('aukstai'));
});

test('exportLinesWithParts prints exactly exportLines, with room parts and origin attached', () => {
  const p = project();
  const plain = exportLines(p);
  const withParts = exportLinesWithParts(p);
  assert.equal(withParts.length, plain.length);
  withParts.forEach((line, i) => {
    const { dalys, kilme, prielaida, ...rest } = line;
    assert.deepEqual(rest, plain[i]);
    assert.ok(Array.isArray(dalys) && typeof kilme === 'string' && typeof prielaida === 'string');
  });
  assert.deepEqual(withParts[0].dalys.map((d) => [d.room_nr, d.value, d.page]), [['01', 4, 1], ['02', 6, 1]]);
  assert.deepEqual(withParts.map((l) => l.kilme), ['programa', 'jusu', 'pataisyta']);
  assert.equal(withParts[0].prielaida, 'Prielaida: dvi dažų sluoksnės');
});

test('room parts follow the floor multiplier like the quantity does', () => {
  const p = project({ prielaidos: { aukstu_skaicius: 3 } });
  const [first] = exportLinesWithParts(p);
  assert.equal(first.kiekis, 30);
  assert.deepEqual(first.dalys.map((d) => d.value), [12, 18]);
});

test('the section filter drops the same lines exportLines drops', () => {
  const allowed = new Set(['Dažymas', 'Santechnika']);
  assert.deepEqual(exportLinesWithParts(project(), allowed).map((l) => l.nr), exportLines(project(), allowed).map((l) => l.nr));
});

test('a KŽ project without darbu_sarasas passes through', () => {
  const p = { rows: [{ nr: '1.1', aprasymas: 'Kasimas', mato_vnt: 'm³', kiekis: 3, skyrius: 'Žemės darbai' }] };
  assert.deepEqual(exportLinesWithParts(p), exportLines(p));
});

test('rowOrigin', () => {
  assert.equal(rowOrigin({ id: 'rnk-x' }), 'jusu');
  assert.equal(rowOrigin({ manual_override: true }), 'pataisyta');
  assert.equal(rowOrigin({}), 'programa');
});

test('sheets and the overlay page list', () => {
  assert.deepEqual(exportSheets(project()), [{ nr: 1, pavadinimas: 'PLANAS' }, { nr: 5, pavadinimas: 'LUBŲ PLANAS' }]);
  const pages = overlayPageChoices(project(), 6);
  assert.equal(pages.length, 6);
  assert.deepEqual(pages[0], { nr: 1, name: 'PLANAS' });
  assert.deepEqual(pages[1], { nr: 2, name: '' });
  assert.equal(overlayPageChoices(project()).length, 5);
});

test('overlay scales: his calibration over the drawing ratio over nothing', () => {
  const p = project({
    _meta: { geometrija: { masteliai: { 1: { m_per_pt: 0.0176, mastelis: 50 }, 2: { m_per_pt: 0.0353, mastelis: 100 } } } },
    pageScalesDurable: { 2: { metersPerPointX: 0.01, metersPerPointY: 0.01, calibrated: true, source: 'user' },
      3: { metersPerPointX: 0, calibrated: false } },
  });
  const s = overlayScales(p);
  assert.equal(s['1'].source, 'plan');
  assert.ok(Math.abs(s['1'].metersPerPointX - 50 * 0.0254 / 72) < 1e-9);
  assert.deepEqual(s['2'], { metersPerPointX: 0.01, metersPerPointY: 0.01, source: 'user' });
  assert.equal(s['3'], undefined);
});

test('overlay request body: default layers, sorted pages, dry run', () => {
  const body = overlayRequestBody(project(), { pages: new Set([3, 1]), layers: { walls: true }, dryRun: true });
  assert.deepEqual(body.pages, [1, 3]);
  assert.deepEqual(body.layers, { outlines: true, measurements: true, counts: true, walls: true, labels: true });
  assert.equal(body.dry_run, true);
  assert.equal(overlayRequestBody(project()).pages, 'all');
  assert.equal(OVERLAY_LAYERS.find((l) => l.key === 'walls').on, false);
  assert.equal(OVERLAY_LAYERS.find((l) => l.key === 'labels').on, true);
  assert.equal(overlayRequestBody(project()).layers.labels, true);
});

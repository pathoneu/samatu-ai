import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  applyMeasuredRows, defaultKaip, linkKey, linksOf, linkPatch, measuredContributions, rowMeasurements,
  syncMeasuredRows, unitOfRow, unitsMatch,
} from './measuredRows.js';

const CASES = JSON.parse(readFileSync(new URL('./measuredRows.cases.json', import.meta.url), 'utf8'));

// The shared cases — backend/tests/test_measured_rows.py runs the very same file through the server's twin.
for (const c of CASES.cases) {
  test(`measured rows: ${c.name}`, () => {
    const before = JSON.parse(JSON.stringify(c.rows));
    const out = applyMeasuredRows(c.rows, c.contributions);
    assert.deepEqual(c.rows, before, 'the input rows are never mutated');
    for (const w of c.want) {
      const row = out.find((r) => r.id === w.id);
      const orig = c.rows.find((r) => r.id === w.id);
      assert.ok(row, `row ${w.id}`);
      if (w.untouched) assert.equal(row, orig, `${w.id}: an unchanged row keeps its identity`);
      if ('kiekis' in w) assert.equal(row.kiekis, w.kiekis, `${w.id} kiekis`);
      if ('kiekis_programos' in w) assert.equal(row.kiekis_programos, w.kiekis_programos, `${w.id} kiekis_programos`);
      if ('suma' in w) assert.equal(row.suma, w.suma, `${w.id} suma`);
      if (w.lines) assert.deepEqual(row.matavimai.map((l) => l.tekstas), w.lines, `${w.id} lines`);
      if (w.taikoma) assert.deepEqual(row.matavimai.map((l) => l.taikoma), w.taikoma, `${w.id} taikoma`);
      if (w.priezastys) assert.deepEqual(row.matavimai.map((l) => l.priezastis), w.priezastys, `${w.id} priezastys`);
      if (w.roll_up_ops) assert.deepEqual((row.roll_up || []).map((s) => s.op), w.roll_up_ops, `${w.id} roll_up ops`);
      if ('roll_up_last' in w) assert.equal(row.roll_up.at(-1).value, w.roll_up_last, `${w.id} chain ends on kiekis`);
      if (w.roll_up_notes) assert.deepEqual(row.roll_up.map((s) => s.note ?? null), w.roll_up_notes, `${w.id} notes`);
      if ('sum_flag' in w) assert.equal(row.contributions_sum_to_total, w.sum_flag, `${w.id} sum flag`);
      for (const k of w.absent || []) assert.equal(k in row, false, `${w.id} must not carry ${k}`);
    }
  });
}

test('nothing linked → the very same list back (the fast path every save takes)', () => {
  const rows = [{ id: 'a', kiekis: 1 }];
  assert.equal(applyMeasuredRows(rows, []), rows);
  const project = { darbu_sarasas: rows, measurements: [{ id: 'm1', kind: 'distance', page: 1, points: [] }] };
  assert.equal(syncMeasuredRows(project), project);
});

// A sheet whose scale he calibrated: 1 PDF point = 0,01 m, so a 420-point line is 4,20 m.
const SCALE = { 1: { calibrated: true, metersPerPointX: 0.01, metersPerPointY: 0.01, source: 'user' } };
const project = (extra = {}) => ({
  id: 'p',
  pageScalesDurable: SCALE,
  measurements: [
    { id: 'd1', kind: 'distance', page: 1, points: [{ x: 0, y: 0 }, { x: 420, y: 0 }] },
    { id: 'd2', kind: 'distance', page: 2, points: [{ x: 0, y: 0 }, { x: 100, y: 0 }], name: 'Siena' },
    { id: 'c1', kind: 'count', page: 1, typeId: 'rozetes', points: [{ x: 1, y: 1 }] },
    { id: 'c2', kind: 'count', page: 3, typeId: 'rozetes', points: [{ x: 2, y: 2 }] },
    { id: 'c3', kind: 'count', page: 1, typeId: 'rozetes', points: [{ x: 3, y: 3 }] },
  ],
  countTypes: [{ id: 'rozetes', label: 'Rozetės' }],
  darbu_sarasas: [
    { id: 'a', aprasymas: 'Grindjuostės', mato_vnt: 'm', kiekis: 40, roll_up: [{ op: 'sum', label: 'Σ', value: 40 }] },
    { id: 'r', aprasymas: 'Rozetės', mato_vnt: 'vnt.', kiekis: 0 },
  ],
  ...extra,
});

test('a link is kept beside the measurements — the viewer rewrites its own list and never erases it', () => {
  const p = project();
  const patch = linkPatch(p, linkKey({ kind: 'measurement', id: 'd1' }), { eilute_id: 'a', kaip: 'pridėti' });
  assert.deepEqual(Object.keys(patch).sort(), ['darbu_sarasas', 'measurementRows']);
  assert.equal(patch.measurementRows['m:d1'].eilute_id, 'a');
  assert.equal(patch.darbu_sarasas[0].kiekis, 44.2);
  // the viewer saves its list again, without any link on the objects: the row keeps the length
  const afterViewerSave = syncMeasuredRows({ ...p, ...patch, measurements: p.measurements.map((m) => ({ ...m })) });
  assert.equal(afterViewerSave.darbu_sarasas[0].kiekis, 44.2);
});

test('the measured value comes from the sheet\'s scale; a sheet without one gives no number', () => {
  const p = { ...project(), measurementRows: { 'm:d1': { eilute_id: 'a', kaip: 'pridėti' }, 'm:d2': { eilute_id: 'a', kaip: 'pridėti' } } };
  const cs = measuredContributions(p);
  assert.deepEqual(cs.map((c) => [c.key, c.value, c.unit, c.pages]), [['m:d1', 4.2, 'm', [1]], ['m:d2', null, 'm', [2]]]);
  assert.equal(cs[1].pavadinimas, 'Siena');
  const row = syncMeasuredRows(p).darbu_sarasas[0];
  assert.equal(row.kiekis, 44.2, 'only the measured one counts');
  assert.match(row.matavimai[1].priezastis, /2 lape nenustatytas mastelis/);
});

test('a count type on a row: every mark of the type, pages listed; a new mark moves the row', () => {
  const p = { ...project(), measurementRows: { 'type:rozetes': { eilute_id: 'r', kaip: 'kiekis' } } };
  const [c] = measuredContributions(p);
  assert.deepEqual([c.value, c.unit, c.pages, c.pavadinimas], [3, 'vnt.', [1, 3], 'Rozetės']);
  assert.equal(syncMeasuredRows(p).darbu_sarasas[1].kiekis, 3);
  const more = { ...p, measurements: [...p.measurements, { id: 'c4', kind: 'count', page: 3, typeId: 'rozetes', points: [] }] };
  assert.equal(syncMeasuredRows(more).darbu_sarasas[1].kiekis, 4);
  assert.equal(syncMeasuredRows(more).darbu_sarasas[1].matavimai[0].tekstas, 'matavimas „Rozetės“ 4 vnt. (lapai 1, 3)');
});

test('a link written on the object itself (the viewer, a legend row) counts too; the panel\'s map wins over it', () => {
  const p = project({ countTypes: [{ id: 'rozetes', label: 'Rozetės', eilute_id: 'r', kaip: 'kiekis' }] });
  assert.deepEqual(linksOf(p).get('type:rozetes'), { eilute_id: 'r', kaip: 'kiekis' });
  assert.equal(syncMeasuredRows(p).darbu_sarasas[1].kiekis, 3);
  const off = { ...p, measurementRows: { 'type:rozetes': { eilute_id: null } } };
  assert.equal(linksOf(off).has('type:rozetes'), false, 'taken off in the panel');
});

test('taking a measurement off: the map forgets it and the row returns to the program\'s number', () => {
  const p0 = project();
  const on = { ...p0, ...linkPatch(p0, 'm:d1', { eilute_id: 'a', kaip: 'pridėti' }) };
  const off = linkPatch(on, 'm:d1', null);
  assert.equal('m:d1' in off.measurementRows, false);
  assert.equal(off.darbu_sarasas[0].kiekis, 40);
  assert.equal('matavimai' in off.darbu_sarasas[0], false);
});

test('a deleted measurement leaves its row; the viewer\'s Undo brings both back', () => {
  const p0 = project();
  const on = { ...p0, ...linkPatch(p0, 'm:d1', { eilute_id: 'a', kaip: 'pridėti' }) };
  const deleted = syncMeasuredRows({ ...on, measurements: on.measurements.filter((m) => m.id !== 'd1') });
  assert.equal(deleted.darbu_sarasas[0].kiekis, 40);
  const undone = syncMeasuredRows({ ...deleted, measurements: on.measurements });
  assert.equal(undone.darbu_sarasas[0].kiekis, 44.2);
});

test('what a drop proposes: instead of an empty line, added to one that has a number', () => {
  assert.equal(defaultKaip({ kiekis: null }), 'kiekis');
  assert.equal(defaultKaip({ kiekis: 0 }), 'kiekis');
  assert.equal(defaultKaip({ kiekis: 12 }), 'pridėti');
});

test('units: the row\'s own spelling folds to one', () => {
  assert.equal(unitOfRow({ mato_vnt: 'm2' }), 'm²');
  assert.equal(unitOfRow({ vnt: 'vnt' }), 'vnt.');
  assert.equal(unitsMatch('m²', 'm2'), true);
  assert.equal(unitsMatch('m', 'm²'), false);
});

test('the row\'s measurements, for the chip and its list', () => {
  const p0 = project();
  const on = { ...p0, ...linkPatch(p0, 'm:d1', { eilute_id: 'a', kaip: 'pridėti' }) };
  const list = rowMeasurements(on, on.darbu_sarasas[0]);
  assert.deepEqual(list.map((l) => [l.key, l.tekstas, l.taikoma]), [['m:d1', '+ matavimas 4,20 m (lapas 1)', true]]);
  assert.deepEqual(rowMeasurements(on, on.darbu_sarasas[1]), []);
});

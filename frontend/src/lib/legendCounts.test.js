import { test } from 'node:test';
import assert from 'node:assert/strict';
import { legendCounts, legendKind } from './legendCounts.js';
import { buildRecomputeContext } from './recomputeContext.js';

const mark = (typeId, page, i) => ({ id: `${typeId}-${i}`, kind: 'count', typeId, page, x: i, y: i });

test('legend row texts fold to a kind; anything else is no kind', () => {
  assert.equal(legendKind('Trapas'), 'trapai');
  assert.equal(legendKind('Linijinis trapas dušui'), 'trapai');
  assert.equal(legendKind('Ištraukimo difuzorius'), 'difuzoriai');
  assert.equal(legendKind('Viengubas perjungėjas'), 'jungikliai');
  assert.equal(legendKind('Interneto lizdas'), 'rozetes');
  assert.equal(legendKind('Elektros išvadas pakabinamiems šviestuvams'), 'sviestuvai');
  assert.equal(legendKind('Signalizacijos judesio daviklis'), 'davikliai');
  assert.equal(legendKind('LED juosta'), null);
  assert.equal(legendKind(''), null);
});

test('a legend count type and its marks become the contract fixture_rows_flag reads', () => {
  const project = {
    countTypes: [
      { id: 't1', label: 'Trapas', legend_row_id: 'p4-aa', legend_text: 'Trapas' },
      { id: 't2', label: 'Linijinis trapas', legend_row_id: 'p4-bb', legend_text: 'Linijinis trapas' },
      { id: 't3', label: 'Rankinis', legend_row_id: null },                      // his own type: not a legend count
      { id: 't4', label: 'LED juosta', legend_row_id: 'p4-cc', legend_text: 'LED juosta' },   // no kind
      { id: 't5', label: 'Rozetė', legend_row_id: 'p2-dd', legend_text: 'Rozetė' },            // no marks
    ],
    measurements: [mark('t1', 4, 1), mark('t1', 5, 2), mark('t2', 4, 3), mark('t3', 4, 4), mark('t4', 4, 5),
      { id: 'd', kind: 'distance', typeId: 't1', page: 4 }],
  };
  assert.deepEqual(legendCounts(project), {
    trapai: { kiekis: 3, tekstas: 'Trapas; Linijinis trapas', row_id: 'p4-aa', page: 4, eilutes: ['Trapas', 'Linijinis trapas'] },
  });
});

test('nothing counted from a legend: undefined, and the recompute context does not carry it', () => {
  assert.equal(legendCounts({}), undefined);
  assert.equal(legendCounts({ countTypes: [{ id: 't1', legend_row_id: 'x', legend_text: 'Trapas' }], measurements: [] }), undefined);
  assert.equal(JSON.stringify(buildRecomputeContext({})).includes('_legendos_kiekiai'), false);
});

test('the recompute context carries the legend counts, so a recount reaches the rows', () => {
  const project = { countTypes: [{ id: 't1', label: 'Trapas', legend_row_id: 'r', legend_text: 'Trapas' }], measurements: [mark('t1', 3, 1)] };
  assert.equal(buildRecomputeContext(project)._legendos_kiekiai.trapai.kiekis, 1);
  project.measurements.push(mark('t1', 3, 2));
  assert.equal(buildRecomputeContext(project)._legendos_kiekiai.trapai.kiekis, 2);
});

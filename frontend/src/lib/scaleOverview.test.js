import test from 'node:test';
import assert from 'node:assert/strict';
import { buildScaleOverview, dimensionStringsOf, overviewCounts, plural } from './scaleOverview.js';
import { confirmLaneScales, laneScalesOf } from './durableScale.js';

const eil = (text, page, y = 0.41) => ({ text, value_m: Number(text) / 1000, page, line_pct: [[0.39, y], [0.42, y]] });
// objektas_h's shape: eight sheets, the lane measured 1:115 on sheets 1–3 (fewer here), strings on 1 and 3.
const project = {
  _meta: { geometrija: {
    masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 }, 2: { m_per_pt: 0.040598, mastelis: 115 }, 3: { m_per_pt: 0.040602, mastelis: 115 } },
    masteliai_kiti: { 3: { ismatuota: 115, uzrasyta: [100] } },
  } },
  v8_rooms: [
    { nr: '01', _sienos: [{ eilutes: [eil('600', 1), eil('996', 1, 0.5)] }, { eilutes: [eil('1140', 3)] }] },
    // the neighbour shares the 600 wall — counted once
    { nr: '02', _sienos: [{ eilutes: [eil('600', 1)] }] },
  ],
};

test('dimension strings per sheet, deduplicated across rooms', () => {
  const s = dimensionStringsOf(project);
  assert.deepEqual(s[1].map((x) => x.text), ['600', '996']);
  assert.deepEqual(s[3].map((x) => x.text), ['1140']);
  assert.deepEqual(dimensionStringsOf({ v8_rooms: [{ _sienos: [{ eilutes: [{ text: 'x', page: 1 }] }] }] }), {});
});

test('one row per sheet of the PDF with scale, source, written scale, strings and state', () => {
  const { rows } = buildScaleOverview(project, { pageCount: 4 });
  assert.equal(rows.length, 4);
  assert.deepEqual(rows.map((r) => r.state), ['spejamas', 'spejamas', 'spejamas', 'nenustatytas']);
  assert.equal(rows[0].label, '1:115');
  assert.equal(rows[0].source, 'Išmatuotas pagal matmenis');
  assert.equal(rows[0].strings, 2);
  assert.deepEqual(rows[0].sample, ['600', '996']);
  assert.equal(rows[2].written, '1:100');
  assert.match(rows[2].source, /lape užrašyta 1:100/);
  assert.equal(rows[3].label, '');
  assert.equal(rows[3].source, 'Nėra');
  assert.equal(rows[3].canConfirm, false);
  assert.deepEqual(overviewCounts(rows), { nenustatytas: 1, spejamas: 3, patvirtintas: 0 });
});

test('sheets sharing one lane ratio form a confirm-all group; confirming moves them to patvirtintas', () => {
  const { groups } = buildScaleOverview(project, { pageCount: 4 });
  assert.deepEqual(groups, [{ ratio: 115, label: '1:115', pages: [1, 2, 3] }]);
  const durable = confirmLaneScales({}, [1, 2], laneScalesOf(project), 0);
  const after = buildScaleOverview(project, { pageCount: 4, durable });
  assert.deepEqual(after.rows.map((r) => r.state), ['patvirtintas', 'patvirtintas', 'spejamas', 'nenustatytas']);
  assert.equal(after.rows[0].canConfirm, false);
  assert.equal(after.rows[0].source, 'Išmatuotas pagal matmenis');
  assert.deepEqual(after.groups, [], 'one unconfirmed sheet left — no group');
});

test('a confirmation the re-read lane no longer supports is flagged on its row', () => {
  const durable = confirmLaneScales({}, [1], laneScalesOf(project), 0);
  const reread = { ...project, _meta: { geometrija: { masteliai: { 1: { m_per_pt: 0.035278, mastelis: 100 } } } } };
  const { rows } = buildScaleOverview(reread, { pageCount: 1, durable });
  assert.deepEqual(rows[0].stale, { confirmed: 115, now: 100 });
  assert.equal(rows[0].state, 'patvirtintas', 'his confirmation still rules until he changes it');
});

test('his own calibration and the approximate area scale', () => {
  const durable = { 4: { calibrated: true, source: 'user', metersPerPointX: 50 * 0.0254 / 72, label: '1:50' } };
  const { rows } = buildScaleOverview(project, { pageCount: 4, durable });
  assert.equal(rows[3].state, 'patvirtintas');
  assert.equal(rows[3].label, '1:50');
  assert.equal(rows[3].source, 'Jūsų nustatytas pagal žinomą atstumą');
  // without a page count the pages come from what is known
  assert.deepEqual(buildScaleOverview(project).rows.map((r) => r.page), [1, 2, 3]);
});

test('plural: matmuo / matmenys / matmenų', () => {
  const f = (n) => plural(n, 'matmuo', 'matmenys', 'matmenų');
  assert.deepEqual([1, 2, 9, 10, 11, 12, 20, 21, 22, 46, 111].map(f),
    ['matmuo', 'matmenys', 'matmenys', 'matmenų', 'matmenų', 'matmenų', 'matmenų', 'matmuo', 'matmenys', 'matmenys', 'matmenų']);
});

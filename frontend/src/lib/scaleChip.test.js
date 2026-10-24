import test from 'node:test';
import assert from 'node:assert/strict';
import { scaleChipModel } from './scaleChip.js';
import { confirmLaneScales, laneScalesOf } from './durableScale.js';
import { effectivePageScales } from './pageScales.js';
import { makeT } from './testT.js';

const t = makeT('lt');

// objektas_h's shape: the lane measured 1:115 on sheets 1–3, sheet 3 writes 1:100; sheet 4 has no scale.
const project = {
  _meta: { geometrija: {
    masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 }, 2: { m_per_pt: 0.040598, mastelis: 115 }, 3: { m_per_pt: 0.040602, mastelis: 115 } },
    masteliai_kiti: { 3: { ismatuota: 115, uzrasyta: [100] } },
  } },
  v8_rooms: [],
};

test('a guessed sheet (no backend provenance): „1:115 — spėjamas …", one-click confirm, the sheets that share the ratio', () => {
  const scales = effectivePageScales(project, {});
  const chip = scaleChipModel({ page: 2, scales, project, durable: {}, pageCount: 4, t });
  assert.equal(chip.text, '1:115 — spėjamas pagal plano matmenis');
  assert.equal(chip.phrase, 'spėjamas pagal plano matmenis');
  assert.equal(chip.short, 'spėjamas', 'the chip keeps to a few words');
  assert.equal(chip.state, 'spejamas');
  assert.equal(chip.line, 'dashed');
  assert.equal(chip.canConfirm, true);
  assert.deepEqual(chip.group, { pages: [1, 2, 3], label: '1:115' });
  assert.equal(chip.sentence, 'Mastelis 1:115 — spėjamas pagal plano matmenis');
  // the card explains what the scale is; its buttons — not a hint to another panel — say what to do
  assert.match(chip.title, /^Tai programos spėjimas/);
  assert.doesNotMatch(chip.title, /Masteliai|Spustelėkite/);
});

test('a confirmed sheet says so and offers no confirm; the others still form their group', () => {
  const durable = confirmLaneScales({}, [2], laneScalesOf(project), 0);
  const scales = effectivePageScales(project, durable);
  const chip = scaleChipModel({ page: 2, scales, project, durable, pageCount: 4, t });
  assert.equal(chip.text, '1:115 — patvirtinote jūs');
  assert.equal(chip.state, 'patvirtintas');
  assert.equal(chip.line, 'solid');
  assert.equal(chip.canConfirm, false);
  assert.equal(chip.group, null);
  assert.deepEqual(scaleChipModel({ page: 1, scales, project, durable, pageCount: 4, t }).group, { pages: [1, 3], label: '1:115' });
});

test('a sheet with no scale: „mastelio nėra", nothing to confirm', () => {
  const scales = effectivePageScales(project, {});
  const chip = scaleChipModel({ page: 4, scales, project, durable: {}, pageCount: 4, t });
  assert.equal(chip.text, 'mastelio nėra');
  assert.equal(chip.state, 'nenustatytas');
  assert.equal(chip.line, 'none');
  assert.equal(chip.canConfirm, false);
  assert.equal(chip.group, null);
  assert.equal(chip.sentence, 'Mastelio nėra');
});

test('his own calibration reads as confirmed and is never offered for confirming', () => {
  const durable = { 4: { metersPerPointX: 0.0176389, metersPerPointY: 0.0176389, calibrated: true, source: 'user', label: '1:50' } };
  const scales = effectivePageScales(project, durable);
  const chip = scaleChipModel({ page: 4, scales, project, durable, pageCount: 4, t });
  assert.equal(chip.text, '1:50 — jūsų nustatytas pagal žinomą ilgį');
  assert.equal(chip.state, 'patvirtintas');
  assert.equal(chip.canConfirm, false);
});

// objektas_i (A) as stored in the local DB: sheets 4, 5 at 1:75 and 7 at 1:71 from dimension strings on their
// hairlines (backend source 2), sheet 6 blank with the lane's reason (a synthetic reason — the record shape is
// backend/geometry/scale.py's).
const objektasI = {
  _meta: {
    plan_dimension_lane: { mastelis: { 4: 75, 5: 75, 7: 71 } },
    geometrija: {
      masteliai: {
        4: { m_per_pt: 0.026458, mastelis: 75, saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '139 matmenų eilutės ant matmenų linijų' },
        5: { m_per_pt: 0.026458, mastelis: 75, saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '55 matmenų eilutės ant matmenų linijų' },
        7: { m_per_pt: 0.025161, mastelis: 71, saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '78 matmenų eilutės ant matmenų linijų' },
      },
      masteliai_tusti: { 6: 'Šiame lape nėra nei užrašyto mastelio, nei matmenų teksto. Nubrėžkite liniją ant žinomo matmens, kad nustatytumėte mastelį.' },
    },
  },
  v8_rooms: [],
};

test('objektas_i: the chip says where 1:75 comes from — read from the plan, solid, never „spėjamas"', () => {
  const scales = effectivePageScales(objektasI, {});
  const chip = scaleChipModel({ page: 4, scales, project: objektasI, durable: {}, pageCount: 7, t });
  assert.equal(chip.state, 'nuskaitytas');
  assert.equal(chip.line, 'solid');
  assert.equal(chip.text, '1:75 — iš plano matmenų (139 skaičiai)');
  assert.equal(chip.short, 'iš plano matmenų');
  assert.equal(chip.sentence, 'Mastelis 1:75 — iš plano matmenų (139 skaičiai)');
  assert.doesNotMatch(`${chip.text} ${chip.sentence} ${chip.title}`, /spėj|užrašytas brėžinyje/i);
  assert.equal(chip.canConfirm, true, 'he can still make it his');
  assert.deepEqual(chip.group, { pages: [4, 5], label: '1:75' });
  const blank = scaleChipModel({ page: 6, scales, project: objektasI, durable: {}, pageCount: 7, t });
  assert.equal(blank.text, 'mastelio nėra — Šiame lape nėra nei užrašyto mastelio, nei matmenų teksto. Nubrėžkite liniją ant žinomo matmens, kad nustatytumėte mastelį.');
  assert.match(blank.sentence, /^Mastelio nėra — Šiame lape/);
});

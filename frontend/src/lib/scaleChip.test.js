import test from 'node:test';
import assert from 'node:assert/strict';
import { scaleChipModel } from './scaleChip.js';
import { confirmLaneScales, laneScalesOf } from './durableScale.js';
import { effectivePageScales } from './pageScales.js';

// objektas_h's shape: the lane measured 1:115 on sheets 1–3, sheet 3 writes 1:100; sheet 4 has no scale.
const project = {
  _meta: { geometrija: {
    masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 }, 2: { m_per_pt: 0.040598, mastelis: 115 }, 3: { m_per_pt: 0.040602, mastelis: 115 } },
    masteliai_kiti: { 3: { ismatuota: 115, uzrasyta: [100] } },
  } },
  v8_rooms: [],
};

test('a guessed sheet: „1:115 · spėjamas", one-click confirm, and the sheets that share the ratio', () => {
  const scales = effectivePageScales(project, {});
  const chip = scaleChipModel({ page: 2, scales, project, durable: {}, pageCount: 4 });
  assert.equal(chip.text, '1:115 · spėjamas');
  assert.equal(chip.state, 'spejamas');
  assert.equal(chip.canConfirm, true);
  assert.deepEqual(chip.group, { pages: [1, 2, 3], label: '1:115' });
  assert.match(chip.sentence, /^Spėjamas mastelis 1:115/);
  // the card explains where the scale comes from; its buttons — not a hint to another panel — say what to do
  assert.match(chip.title, /^Mastelis išmatuotas pagal plane užrašytus matmenis/);
  assert.doesNotMatch(chip.title, /Masteliai|Spustelėkite/);
});

test('a confirmed sheet says so and offers no confirm; the others still form their group', () => {
  const durable = confirmLaneScales({}, [2], laneScalesOf(project), 0);
  const scales = effectivePageScales(project, durable);
  const chip = scaleChipModel({ page: 2, scales, project, durable, pageCount: 4 });
  assert.equal(chip.text, '1:115 · patvirtintas');
  assert.equal(chip.canConfirm, false);
  assert.equal(chip.group, null);
  assert.deepEqual(scaleChipModel({ page: 1, scales, project, durable, pageCount: 4 }).group, { pages: [1, 3], label: '1:115' });
});

test('a sheet with no scale: „Mastelis nenustatytas", nothing to confirm', () => {
  const scales = effectivePageScales(project, {});
  const chip = scaleChipModel({ page: 4, scales, project, durable: {}, pageCount: 4 });
  assert.equal(chip.text, 'Mastelis nenustatytas');
  assert.equal(chip.state, 'nenustatytas');
  assert.equal(chip.canConfirm, false);
  assert.equal(chip.group, null);
  assert.match(chip.sentence, /nenustatytas/);
});

test('his own calibration reads as confirmed and is never offered for confirming', () => {
  const durable = { 4: { metersPerPointX: 0.0176389, metersPerPointY: 0.0176389, calibrated: true, source: 'user', label: '1:50' } };
  const scales = effectivePageScales(project, durable);
  const chip = scaleChipModel({ page: 4, scales, project, durable, pageCount: 4 });
  assert.equal(chip.text, '1:50 · patvirtintas');
  assert.equal(chip.canConfirm, false);
});

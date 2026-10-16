import test from 'node:test';
import assert from 'node:assert/strict';
import { laneScaleOriginOf, laneScalesOf, confirmedLaneScale, METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';
import { scaleStatusText, scaleStatusTitle, scaleState, scaleSourceText } from './scaleLabel.js';
import { calibrateUniform } from './measureGeometry.js';
import { isBannedText } from './userText.js';

// The lane rounds metres per point to six places (geometry_lane: `round(v, 6)`).
const exactMpp = (ratio) => Math.round(ratio * METERS_PER_POINT_AT_1_TO_1 * 1e6) / 1e6;

// ── where a lane scale comes from ───────────────────────────────────────────

test('objektas_h: 1:115 is measured from the dimensions, never „from the drawing" as if written', () => {
  // the stored project's own record (2026-10-06): eight sheets, all measured at 1:115, none writes another
  const masteliai = {};
  for (const p of [1, 2, 3]) masteliai[p] = { m_per_pt: 0.04065, mastelis: 115 };
  const project = { _meta: { geometrija: { masteliai, masteliai_kiti: {} } } };
  assert.deepEqual(laneScaleOriginOf(project)['1'], { kilme: 'ismatuotas', uzrasyta: [] });
  const scale = laneScalesOf(project)[1];
  assert.equal(scaleStatusText(scale), 'Spėjamas mastelis 1:115 (išmatuotas pagal matmenis)');
  assert.match(scaleStatusTitle(scale), /nėra įprastas braižymo mastelis/);
});

test('a sheet that writes its scale and whose dimensions agree says so', () => {
  // the lane took the written 1:50 — its metres per point are exactly 1:50's
  const project = { _meta: { geometrija: { masteliai: { 2: { m_per_pt: exactMpp(50), mastelis: 50 } } } } };
  assert.equal(laneScaleOriginOf(project)['2'].kilme, 'uzrasytas');
  assert.equal(scaleStatusText(laneScalesOf(project)[2]), 'Spėjamas mastelis 1:50 (užrašytas brėžinyje)');
  // 1:20 rounds furthest from exact and still counts as written
  const twenty = { _meta: { geometrija: { masteliai: { 1: { m_per_pt: exactMpp(20), mastelis: 20 } } } } };
  assert.equal(laneScaleOriginOf(twenty)['1'].kilme, 'uzrasytas');
});

test('a standard ratio the strings MEASURED (not exactly the scale) is measured, not written', () => {
  // no written scale; the strings measure 1:100,4 → the lane keeps that, rounded label 100
  const mpp = Math.round(100.4 * METERS_PER_POINT_AT_1_TO_1 * 1e6) / 1e6;
  const project = { _meta: { geometrija: { masteliai: { 3: { m_per_pt: mpp, mastelis: 100 } } } } };
  assert.equal(laneScaleOriginOf(project)['3'].kilme, 'ismatuotas');
  const scale = laneScalesOf(project)[3];
  assert.equal(scaleStatusText(scale), 'Spėjamas mastelis 1:100 (išmatuotas pagal matmenis)');
  assert.doesNotMatch(scaleStatusTitle(scale), /nėra įprastas/, '1:100 is a drawing scale — nothing odd to explain');
});

test('a sheet printed at another size than drawn names the scale it writes', () => {
  const project = { _meta: { geometrija: {
    masteliai: { 4: { m_per_pt: 0.040598, mastelis: 115 } },
    masteliai_kiti: { 4: { ismatuota: 115, uzrasyta: [100] } },
  } } };
  assert.deepEqual(laneScaleOriginOf(project)['4'], { kilme: 'ismatuotas', uzrasyta: [100] });
  const scale = laneScalesOf(project)[4];
  assert.equal(scaleStatusText(scale), 'Spėjamas mastelis 1:115 (išmatuotas pagal matmenis; lape užrašyta 1:100)');
  assert.match(scaleStatusTitle(scale), /Lape užrašyta 1:100, bet plane užrašyti matmenys rodo 1:115/);
});

test('the pair lane\'s rounded ratio: measured when no drawing uses it, else „from the dimensions"', () => {
  const project = { _meta: { plan_dimension_lane: { mastelis: { 2: 50, 5: 97 } } } };
  const origin = laneScaleOriginOf(project);
  assert.equal(origin['2'].kilme, 'matmenys');
  assert.equal(origin['5'].kilme, 'ismatuotas');
  const scales = laneScalesOf(project);
  assert.equal(scaleStatusText(scales[2]), 'Spėjamas mastelis 1:50 (pagal brėžinio matmenis)');
  assert.equal(scaleStatusText(scales[5]), 'Spėjamas mastelis 1:97 (išmatuotas pagal matmenis)');
  // …and the geometry lane's exact record settles it when it has the sheet
  const both = { _meta: { ...project._meta, geometrija: { masteliai: { 2: { m_per_pt: exactMpp(50), mastelis: 50 } } } } };
  assert.equal(laneScaleOriginOf(both)['2'].kilme, 'uzrasytas');
});

test('laneScalesOf keeps the exact scale and the plain label it always had', () => {
  const scales = laneScalesOf({ _meta: { geometrija: { masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 } } } } });
  assert.equal(scales[1].label, '1:115');
  assert.equal(scales[1].source, 'plan');
  assert.ok(Math.abs(scales[1].metersPerPointX - 115 * METERS_PER_POINT_AT_1_TO_1) < 1e-12);
  assert.deepEqual(laneScalesOf(null), {});
  assert.deepEqual(laneScaleOriginOf({ _meta: {} }), {});
});

// ── his own, the areas', none ────────────────────────────────────────────────

test('his own two clicks, the room areas, and no scale at all — each says so', () => {
  const his = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');   // 5 m over 100 pt ≈ 1:142
  assert.equal(scaleStatusText(his), 'Patvirtintas mastelis 1:142 (jūsų nustatytas)');
  assert.match(scaleStatusTitle(his), /nustatėte patys/);
  const auto = { metersPerPointX: 105 * METERS_PER_POINT_AT_1_TO_1, metersPerPointY: 1, calibrated: true, source: 'auto' };
  assert.equal(scaleStatusText(auto), 'Spėjamas mastelis ~1:105 (apytikslis, pagal patalpų plotus)');
  assert.equal(scaleStatusText(undefined), 'Mastelis nenustatytas — spustelėkite čia');
  assert.equal(scaleStatusText({ calibrated: false }), 'Mastelis nenustatytas — spustelėkite čia');
});

test('no state says it in words the contractor never has to learn', () => {
  const states = [
    undefined,
    { calibrated: true, source: 'user', metersPerPointX: 0.03 },
    { calibrated: true, source: 'auto', metersPerPointX: 0.03 },
    ...['uzrasytas', 'ismatuotas', 'matmenys'].flatMap((kilme) => ['plan', 'lane-confirmed'].map((source) => ({
      calibrated: true, source, label: '1:115', metersPerPointX: 0.04, kilme, uzrasyta: [100],
    }))),
  ];
  for (const s of states) {
    for (const text of [scaleStatusText(s), scaleStatusTitle(s)]) {
      assert.equal(isBannedText(text), false, text);
      assert.doesNotMatch(text, /kalibr|iš brėžinio\)/i, text);
    }
  }
});

// ── spėjamas vs patvirtintas (Togal-v2 W6) ──────────────────────────────────

test('a lane scale is a guess until he confirms it; then the status bar says so', () => {
  const lane = laneScalesOf({ _meta: { geometrija: { masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 } } } } })[1];
  assert.equal(scaleState(lane), 'spejamas');
  assert.match(scaleStatusTitle(lane), /programos spėjimas/);
  const mine = confirmedLaneScale(lane, 0);
  assert.equal(scaleState(mine), 'patvirtintas');
  assert.equal(scaleStatusText(mine), 'Patvirtintas mastelis 1:115 (išmatuotas pagal matmenis)');
  assert.match(scaleStatusTitle(mine), /Jūs jį patvirtinote/);
  assert.doesNotMatch(scaleStatusTitle(mine), /spėjimas/);
});

test('scaleState: none, the areas (a guess), his own (confirmed)', () => {
  assert.equal(scaleState(undefined), 'nenustatytas');
  assert.equal(scaleState({ calibrated: true, metersPerPointX: 0 }), 'nenustatytas');
  assert.equal(scaleState({ calibrated: true, source: 'auto', metersPerPointX: 0.03 }), 'spejamas');
  assert.equal(scaleState({ calibrated: true, source: 'user', metersPerPointX: 0.03 }), 'patvirtintas');
});

test('scaleSourceText names the source in a few words', () => {
  const lane = { calibrated: true, source: 'plan', label: '1:115', metersPerPointX: 0.04, kilme: 'ismatuotas', uzrasyta: [100] };
  assert.equal(scaleSourceText(lane), 'Išmatuotas pagal matmenis; lape užrašyta 1:100');
  assert.equal(scaleSourceText({ ...lane, kilme: 'uzrasytas' }), 'Užrašytas brėžinyje');
  assert.equal(scaleSourceText({ ...lane, kilme: 'matmenys' }), 'Pagal brėžinio matmenis');
  assert.equal(scaleSourceText({ calibrated: true, source: 'auto', metersPerPointX: 0.03 }), 'Apytikslis, pagal patalpų plotus');
  assert.equal(scaleSourceText({ calibrated: true, source: 'user', metersPerPointX: 0.03 }), 'Jūsų nustatytas pagal žinomą atstumą');
  assert.equal(scaleSourceText(null), 'Nėra');
});

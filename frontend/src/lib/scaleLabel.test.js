import test from 'node:test';
import assert from 'node:assert/strict';
import { laneScaleOriginOf, laneScalesOf, confirmedLaneScale, METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';
import { scaleStatusText, scaleStatusTitle, scaleState, scaleSourceText } from './scaleLabel.js';
import { calibrateUniform } from './measureGeometry.js';
import { isBannedText } from './userText.js';
import { makeT } from './testT.js';

const t = makeT('lt');

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
  // an older blob without the backend's provenance: a guess, and it never claims a written scale
  assert.equal(scaleStatusText(scale, t), 'Mastelis 1:115 — spėjamas pagal plano matmenis');
  assert.match(scaleStatusTitle(scale, t), /nėra įprastas braižymo mastelis/);
});

test('a sheet that writes its scale and whose dimensions agree says so', () => {
  // the lane took the written 1:50 — its metres per point are exactly 1:50's
  const project = { _meta: { geometrija: { masteliai: { 2: { m_per_pt: exactMpp(50), mastelis: 50 } } } } };
  assert.equal(laneScaleOriginOf(project)['2'].kilme, 'uzrasytas');
  // v4: `kilme` no longer drives the words — without the backend's provenance the scale is a guess (objektas_i
  // read „Spėjamas mastelis 1:75 (užrašytas brėžinyje)" for a scale measured from 139 strings)
  assert.equal(scaleStatusText(laneScalesOf(project)[2], t), 'Mastelis 1:50 — spėjamas pagal plano matmenis');
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
  assert.equal(scaleStatusText(scale, t), 'Mastelis 1:100 — spėjamas pagal plano matmenis');
  assert.doesNotMatch(scaleStatusTitle(scale, t), /nėra įprastas/, '1:100 is a drawing scale — nothing odd to explain');
});

test('a sheet printed at another size than drawn names the scale it writes', () => {
  const project = { _meta: { geometrija: {
    masteliai: { 4: { m_per_pt: 0.040598, mastelis: 115 } },
    masteliai_kiti: { 4: { ismatuota: 115, uzrasyta: [100] } },
  } } };
  assert.deepEqual(laneScaleOriginOf(project)['4'], { kilme: 'ismatuotas', uzrasyta: [100] });
  const scale = laneScalesOf(project)[4];
  assert.equal(scaleStatusText(scale, t), 'Mastelis 1:115 — spėjamas pagal plano matmenis; užrašytas 1:100 neatitinka');
});

test('the pair lane\'s rounded ratio: measured when no drawing uses it, else „from the dimensions"', () => {
  const project = { _meta: { plan_dimension_lane: { mastelis: { 2: 50, 5: 97 } } } };
  const origin = laneScaleOriginOf(project);
  assert.equal(origin['2'].kilme, 'matmenys');
  assert.equal(origin['5'].kilme, 'ismatuotas');
  const scales = laneScalesOf(project);
  assert.equal(scaleStatusText(scales[2], t), 'Mastelis 1:50 — spėjamas pagal plano matmenis');
  assert.equal(scaleStatusText(scales[5], t), 'Mastelis 1:97 — spėjamas pagal plano matmenis');
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
  assert.equal(scaleStatusText(his, t), 'Mastelis 1:142 — jūsų nustatytas pagal žinomą ilgį');
  assert.match(scaleStatusTitle(his, t), /nustatėte patys/);
  const auto = { metersPerPointX: 105 * METERS_PER_POINT_AT_1_TO_1, metersPerPointY: 1, calibrated: true, source: 'auto' };
  assert.equal(scaleStatusText(auto, t), 'Mastelis ~1:105 — spėjamas pagal patalpų plotus');
  assert.equal(scaleStatusText(undefined, t), 'Mastelis nenustatytas — spustelėkite čia');
  assert.equal(scaleStatusText({ calibrated: false }, t), 'Mastelis nenustatytas — spustelėkite čia');
  // with the lane's reason, the reason instead of the click hint; the check card reads without the hint
  assert.equal(scaleStatusText(undefined, t, { blankReason: 'Lape nėra matmenų.' }), 'Mastelio nėra — Lape nėra matmenų.');
  assert.equal(scaleStatusText(undefined, t, { clickable: false }), 'Mastelio nėra');
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
    for (const text of [scaleStatusText(s, t), scaleStatusTitle(s, t)]) {
      assert.equal(isBannedText(text), false, text);
      assert.doesNotMatch(text, /kalibr|iš brėžinio\)/i, text);
    }
  }
});

// ── spėjamas vs patvirtintas (Togal-v2 W6) ──────────────────────────────────

test('a lane scale is a guess until he confirms it; then the status bar says so', () => {
  const lane = laneScalesOf({ _meta: { geometrija: { masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 } } } } })[1];
  assert.equal(scaleState(lane), 'spejamas');
  assert.match(scaleStatusTitle(lane, t), /programos spėjimas/);
  const mine = confirmedLaneScale(lane, 0);
  assert.equal(scaleState(mine), 'patvirtintas');
  assert.equal(scaleStatusText(mine, t), 'Mastelis 1:115 — patvirtinote jūs');
  assert.match(scaleStatusTitle(mine, t), /Jūs jį patvirtinote/);
  assert.doesNotMatch(scaleStatusTitle(mine, t), /spėjimas/);
});

test('scaleState: none, the areas (a guess), his own (confirmed)', () => {
  assert.equal(scaleState(undefined), 'nenustatytas');
  assert.equal(scaleState({ calibrated: true, metersPerPointX: 0 }), 'nenustatytas');
  assert.equal(scaleState({ calibrated: true, source: 'auto', metersPerPointX: 0.03 }), 'spejamas');
  assert.equal(scaleState({ calibrated: true, source: 'user', metersPerPointX: 0.03 }), 'patvirtintas');
});

test('scaleSourceText names the source in a few words', () => {
  const lane = { calibrated: true, source: 'plan', label: '1:115', metersPerPointX: 0.04, kilme: 'ismatuotas', uzrasyta: [100] };
  assert.equal(scaleSourceText(lane, t), 'Spėjamas pagal plano matmenis; užrašytas 1:100 neatitinka');
  assert.equal(scaleSourceText({ ...lane, uzrasyta: [], provenance: { saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '139 matmenų eilutės ant matmenų linijų' } }, t),
    'Iš plano matmenų (139 skaičiai)');
  assert.equal(scaleSourceText({ calibrated: true, source: 'auto', metersPerPointX: 0.03 }, t), 'Spėjamas pagal patalpų plotus');
  assert.equal(scaleSourceText({ calibrated: true, source: 'user', metersPerPointX: 0.03 }, t), 'Jūsų nustatytas pagal žinomą ilgį');
  assert.equal(scaleSourceText(null, t), 'Nėra');
});

test('a scale the backend read from the drawing reads „nuskaitytas", not „spėjamas"', () => {
  const masteliai = { 4: { m_per_pt: 0.026458, mastelis: 75, saltinis: 'dimension_lines', patikimumas: 'high', tekstas: '139 matmenų eilutės ant matmenų linijų' } };
  const scale = laneScalesOf({ _meta: { geometrija: { masteliai } } })[4];
  assert.equal(scaleState(scale), 'nuskaitytas');
  assert.equal(scaleStatusText(scale, t), 'Mastelis 1:75 — iš plano matmenų (139 skaičiai)');
  assert.doesNotMatch(scaleStatusTitle(scale, t), /spėj/i);
});

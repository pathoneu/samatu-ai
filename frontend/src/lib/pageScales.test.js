import test from 'node:test';
import assert from 'node:assert/strict';
import { mergePageScales, effectivePageScales, pageScaleIn, checkViewerScales } from './pageScales.js';
import { METERS_PER_POINT_AT_1_TO_1, autoPageScalesFromRooms, laneScalesOf, confirmPageScalesDurable } from './durableScale.js';
import { scaleState, scaleStatusText } from './scaleLabel.js';
import { makeT } from './testT.js';

const t = makeT('lt');

// objektas_h's shape: the geometry lane measured every sheet; nothing calibrated by hand.
const H = { _meta: { geometrija: { masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 }, 3: { m_per_pt: 0.040602, mastelis: 115 } } } } };

test('a sheet whose scale comes from the lane has metres — the Matavimai bug (it said „nekalibruota")', () => {
  const s = effectivePageScales(H);
  assert.equal(pageScaleIn(s, 1).calibrated, true);
  assert.equal(pageScaleIn(s, 1).source, 'plan');
  assert.equal(pageScaleIn(s, '3').label, '1:115');
  assert.equal(pageScaleIn(s, 2), null);
});

test('merge order: auto < lane < his own; an uncalibrated durable entry never hides the lane', () => {
  const auto = { 1: { calibrated: true, source: 'auto', metersPerPointX: 0.01 }, 2: { calibrated: true, source: 'auto', metersPerPointX: 0.01 } };
  const lane = { 1: { calibrated: true, source: 'plan', metersPerPointX: 0.02 } };
  const durable = { 1: { calibrated: false, source: 'none', metersPerPointX: 0 }, 2: { calibrated: true, source: 'user', metersPerPointX: 0.03 } };
  const m = mergePageScales(auto, lane, durable);
  assert.equal(m[1].source, 'plan');
  assert.equal(m[2].source, 'user');
});

test('the viewer\'s live durable map overrides the stored one', () => {
  const live = { 1: { calibrated: true, source: 'user', metersPerPointX: 50 * METERS_PER_POINT_AT_1_TO_1 } };
  const stored = { ...H, pageScalesDurable: {} };
  assert.equal(pageScaleIn(effectivePageScales(stored, live), 1).source, 'user');
  assert.equal(pageScaleIn(effectivePageScales(stored), 1).source, 'plan');
  assert.deepEqual(effectivePageScales(null), {});
});

// ── One per-sheet scale for both viewers (2026-10-18 audit, side finding A) ──────────────────────────────
// TakeoffViewer measures with mergePageScales(autoPageScalesFromRooms(rooms), laneScales, its live durable map).
// The main viewer gets the project's rooms, lane scales and pageScalesDurable; Patikra's room sheet passes no
// rooms and keeps no durable map of its own — it was handed the lane alone, so a sheet he had confirmed read
// „Patvirtintas mastelis 1:115" in the main viewer and „Spėjamas mastelis 1:115" on the room sheet.
const viewerMerge = ({ rooms = [], laneScales = {}, durable = {} }) =>
  mergePageScales(autoPageScalesFromRooms(rooms), laneScales || {}, durable || {});
const mainViewer = (project) => viewerMerge({
  rooms: project.v8_rooms || project.patalpos || [], laneScales: laneScalesOf(project), durable: project.pageScalesDurable,
});
const roomSheetViewer = (project) => viewerMerge({ laneScales: checkViewerScales(project) });

test('a sheet he confirmed says „Patvirtintas" on the room sheet too, word for word as in the main viewer', () => {
  const confirmed = confirmPageScalesDurable(H, [1], undefined, Date.UTC(2026, 9, 17));
  const main = pageScaleIn(mainViewer(confirmed), 1);
  const sheet = pageScaleIn(roomSheetViewer(confirmed), 1);
  assert.equal(scaleState(main), 'patvirtintas');
  assert.equal(scaleState(sheet), 'patvirtintas');
  assert.equal(scaleStatusText(sheet, t), scaleStatusText(main, t));
  assert.match(scaleStatusText(sheet, t), /^Mastelis 1:115 — patvirtinote jūs/);
  // the sheet he did not confirm stays the program's guess in both
  assert.equal(scaleStatusText(pageScaleIn(roomSheetViewer(confirmed), 3), t), scaleStatusText(pageScaleIn(mainViewer(confirmed), 3), t));
  assert.match(scaleStatusText(pageScaleIn(roomSheetViewer(confirmed), 3), t), /^Mastelis 1:115 — spėjamas/);
});

test('the room sheet shows the main viewer\'s whole map — the rooms\' approximate scale included', () => {
  const room = (side, m2) => ({
    puslapio_nr: 2, polygon_source: 'auto_floodfill', plotas_m2: m2, page_width_pdf: 1000, page_height_pdf: 500,
    polygon_pct: [[0, 0], [side, 0], [side, side], [0, side]],
  });
  const project = { ...H, v8_rooms: [room(0.1, 10), room(0.2, 40), room(0.3, 90)], pageScalesDurable: {} };
  assert.equal(pageScaleIn(mainViewer(project), 2).source, 'auto');
  assert.deepEqual(roomSheetViewer(project), mainViewer(project));
  assert.deepEqual(checkViewerScales(null), {});
});

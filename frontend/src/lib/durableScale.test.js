import test from 'node:test';
import assert from 'node:assert/strict';
import { setPageScaleDurable, getPageScaleDurable, pxPerMeterFromDurable, durableFromPxPerMeter, autoPageScalesFromRooms, pageScalesFromLane, METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';

test('set/get durable scale on a project object', () => {
  let project = {};
  project = setPageScaleDurable(project, 2, { metersPerPointX: 0.05, metersPerPointY: 0.05, calibrated: true, source: 'user' });
  const s = getPageScaleDurable(project, 2);
  assert.equal(s.metersPerPointX, 0.05);
  assert.equal(s.calibrated, true);
});
test('uncalibrated page returns calibrated:false', () => {
  assert.equal(getPageScaleDurable({}, 9).calibrated, false);
});
test('apply-to-all sets the scale on every listed page', () => {
  let project = setPageScaleDurable({}, 1, { metersPerPointX: 0.04, metersPerPointY: 0.04, calibrated: true, source: 'user' }, [1, 2, 3]);
  assert.equal(getPageScaleDurable(project, 3).metersPerPointX, 0.04);
});
test('bridge px/m <-> metres/point at a render scale (px per pdf-point)', () => {
  assert.ok(Math.abs(pxPerMeterFromDurable({ metersPerPointX: 0.05 }, 2) - 40) < 1e-9);
  const dur = durableFromPxPerMeter(40, 2);
  assert.ok(Math.abs(dur.metersPerPointX - 0.05) < 1e-9);
});

// ── autoPageScalesFromRooms robustness (audit P2, 2026-07-27) ───────────────
// A room contributing one sample: `frac` is the shoelace area of polygon_pct,
// so a square of side s covers s² of the page. m2 / frac is the page's real m².
function roomOn(page, side, m2, extra = {}) {
  return {
    puslapio_nr: page,
    polygon_source: 'auto_floodfill',
    plotas_m2: m2,
    page_width_pdf: 1000,
    page_height_pdf: 500,
    polygon_pct: [[0, 0], [side, 0], [side, side], [0, side]],
    ...extra,
  };
}

test('autoPageScales: 3 consistent rooms → an auto scale for the page', () => {
  // side 0.1 → frac 0.01; 10 m² / 0.01 = 1000 m² page → mpp = sqrt(1000/500000)
  const out = autoPageScalesFromRooms([roomOn(2, 0.1, 10), roomOn(2, 0.2, 40), roomOn(2, 0.3, 90)]);
  assert.ok(out[2]);
  assert.equal(out[2].source, 'auto');
  assert.ok(Math.abs(out[2].metersPerPointX - Math.sqrt(1000 / 500000)) < 1e-12);
  assert.equal(out[2].metersPerPointY, out[2].metersPerPointX);
});

test('autoPageScales: 2 samples are no longer enough (their "median" was a mean)', () => {
  const out = autoPageScalesFromRooms([roomOn(2, 0.1, 10), roomOn(2, 0.2, 40)]);
  assert.deepEqual(out, {});
});

test('autoPageScales: true median of 5, not an average — one wild sample cannot drag it', () => {
  const rooms = [
    roomOn(2, 0.1, 10), roomOn(2, 0.2, 40), roomOn(2, 0.3, 90),
    roomOn(2, 0.1, 10.5), roomOn(2, 0.1, 30),   // last one = 3000 m² page (outlier, kept: <4x)
  ];
  const out = autoPageScalesFromRooms(rooms);
  // samples sorted: 1000, 1000, 1000, 1050, 3000 → median 1000
  assert.ok(Math.abs(out[2].metersPerPointX - Math.sqrt(1000 / 500000)) < 1e-12);
});

test('autoPageScales: samples outside [0.25x, 4x] of the median are discarded', () => {
  const rooms = [
    roomOn(2, 0.1, 10), roomOn(2, 0.2, 40), roomOn(2, 0.3, 90), roomOn(2, 0.1, 10),
    roomOn(2, 0.1, 1000),   // leaked whole-floor polygon: 100 000 m² page
  ];
  const out = autoPageScalesFromRooms(rooms);
  assert.ok(Math.abs(out[2].metersPerPointX - Math.sqrt(1000 / 500000)) < 1e-12);
});

test('autoPageScales: fewer than 3 survivors after the outlier cut → no auto scale', () => {
  const rooms = [
    roomOn(2, 0.1, 10), roomOn(2, 0.1, 10),      // 1000
    roomOn(2, 0.1, 100), roomOn(2, 0.1, 100),    // 10 000 — median lands between
  ];
  const out = autoPageScalesFromRooms(rooms);
  assert.deepEqual(out, {});
});

test('autoPageScales: float-noise polygons (frac <= 1e-6) never make a 1:infinity scale', () => {
  const tiny = (m2) => roomOn(2, 0.0001, m2);   // frac = 1e-8
  const out = autoPageScalesFromRooms([tiny(10), tiny(10), tiny(10)]);
  assert.deepEqual(out, {});
});

test('autoPageScales: rooms disagreeing on the page size skip that page', () => {
  const rooms = [
    roomOn(2, 0.1, 10), roomOn(2, 0.2, 40),
    roomOn(2, 0.3, 90, { page_width_pdf: 842 }),   // different sheet size
  ];
  assert.deepEqual(autoPageScalesFromRooms(rooms), {});
});

test('autoPageScales: only trusted polygon sources count', () => {
  const rooms = [
    roomOn(2, 0.1, 10, { polygon_source: 'synthesized_from_bbox' }),
    roomOn(2, 0.2, 40, { polygon_source: 'bbox_fallback' }),
    roomOn(2, 0.3, 90),
  ];
  assert.deepEqual(autoPageScalesFromRooms(rooms), {});
});

test('autoPageScales: page_nr rooms are honoured via the shared roomPageOf', () => {
  const rooms = [0.1, 0.2, 0.3].map((s, i) => {
    const r = roomOn(2, s, [10, 40, 90][i]);
    delete r.puslapio_nr;
    r.page_nr = 3;
    return r;
  });
  const out = autoPageScalesFromRooms(rooms);
  assert.ok(out[3]);
});

test('autoPageScales: the Objektas A demo page 2 still auto-calibrates to ~1:105', () => {
  // 5 traced rooms, real values from backend/data/demo-objektas-a-snapshot-20260714.json
  // (frac = polygon_pct shoelace area, m2 from the eksplikacija).
  const W = 1191.24, H = 842.04;
  const mk = (frac, m2) => {
    const s = Math.sqrt(frac);
    return { puslapio_nr: 2, polygon_source: 'auto_floodfill', plotas_m2: m2,
             page_width_pdf: W, page_height_pdf: H,
             polygon_pct: [[0, 0], [s, 0], [s, s], [0, s]] };
  };
  const out = autoPageScalesFromRooms([
    mk(0.046819, 50.54), mk(0.008146, 11.01), mk(0.005391, 7.45),
    mk(0.006520, 9.64), mk(0.006986, 10.67),
  ]);
  assert.ok(out[2], 'demo page 2 must still get an auto scale');
  const ratio = Math.round((out[2].metersPerPointX * 72) / 0.0254);
  assert.equal(ratio, 105);
});

test('the dimension-string lane\'s ratios become exact page scales, labelled from the drawing', () => {
  const out = pageScalesFromLane({ 2: 50, '8': 25, '9': 'x', 0: 50, '-1': 50 });
  assert.deepEqual(Object.keys(out).sort(), ['2', '8']);
  assert.equal(out[2].label, '1:50');
  assert.equal(out[2].source, 'plan');
  assert.equal(out[2].calibrated, true);
  // 1 pt = 1/72 in of paper; at 1:50 one point is 50 × 0,3528 mm = 17,64 mm of reality
  assert.ok(Math.abs(out[2].metersPerPointX - 50 * METERS_PER_POINT_AT_1_TO_1) < 1e-12);
  assert.ok(Math.abs(out[2].metersPerPointX - 0.017639) < 1e-6);
  assert.equal(out[8].label, '1:25');
  assert.deepEqual(pageScalesFromLane(undefined), {});
  assert.deepEqual(pageScalesFromLane(null), {});
});

// ── the two lanes' scales, merged per page (2026-10-06) ─────────────────────

test('laneMastelisOf, pair lane only: its ratios, nothing invented', async () => {
  const { laneMastelisOf, laneScaleOriginOf } = await import('./durableScale.js');
  const project = { _meta: { plan_dimension_lane: { mastelis: { 4: 82, '11': 50, 9: 'x', 13: 0 } } } };
  assert.deepEqual(laneMastelisOf(project), { 4: 82, 11: 50 });
  assert.deepEqual(laneScaleOriginOf(project), {
    4: { kilme: 'ismatuotas', uzrasyta: [] },     // 1:82 is no drawing's scale — measured
    11: { kilme: 'matmenys', uzrasyta: [] },      // a rounded 1:50: written or measured cannot be told
  });
  assert.deepEqual(laneMastelisOf({ _meta: {} }), {});
  assert.deepEqual(laneMastelisOf(null), {});
});

test('laneMastelisOf, geometry lane only: its exact sheet scales', async () => {
  const { laneMastelisOf } = await import('./durableScale.js');
  assert.deepEqual(
    laneMastelisOf({ _meta: { plan_dimension_lane: { mastelis: {} }, geometrija: { masteliai: { 1: { m_per_pt: 0.04065, mastelis: 115 }, 6: { mastelis: 115 }, 9: { mastelis: 0 } } } } }),
    { 1: 115, 6: 115 },
  );
});

test('objektas_a on production: the main floor plan (sheet 2) gets the geometry lane\'s 1:82 beside the pair lane\'s sheets', async () => {
  const { laneMastelisOf, laneScaleOriginOf, laneScalesOf } = await import('./durableScale.js');
  const { scaleStatusText } = await import('./scaleLabel.js');
  // the reading's own records: the pair lane never read sheets 2 and 3, the geometry lane did
  const project = { _meta: {
    plan_dimension_lane: { mastelis: { 4: 82, 8: 83, 9: 83, 11: 50, 12: 50, 13: 50, 14: 52, 15: 50, 17: 50 }, mastelis_kitas: {} },
    geometrija: { masteliai: {
      2: { m_per_pt: 0.029101, mastelis: 82 }, 3: { m_per_pt: 0.029101, mastelis: 82 }, 4: { m_per_pt: 0.029101, mastelis: 82 },
      8: { m_per_pt: 0.029226, mastelis: 83 }, 9: { m_per_pt: 0.029155, mastelis: 83 }, 11: { m_per_pt: 0.017795, mastelis: 50 },
      12: { m_per_pt: 0.017422, mastelis: 49 }, 13: { m_per_pt: 0.017778, mastelis: 50 }, 14: { m_per_pt: 0.018256, mastelis: 52 },
      15: { m_per_pt: 0.01753, mastelis: 50 }, 17: { m_per_pt: 0.018116, mastelis: 51 },
    }, masteliai_kiti: {} },
  } };
  const merged = laneMastelisOf(project);
  assert.deepEqual(Object.keys(merged).map(Number).sort((a, b) => a - b), [2, 3, 4, 8, 9, 11, 12, 13, 14, 15, 17]);
  assert.equal(merged[2], 82);
  assert.equal(merged[3], 82);
  const scales = laneScalesOf(project);
  assert.equal(scales[2].calibrated, true);
  assert.equal(scales[2].label, '1:82');
  assert.equal(scaleStatusText(scales[2]), 'Mastelis 1:82 (išmatuotas pagal matmenis)');
  // the label says where sheet 2's scale came from: the geometry lane's own record (1:82,49 measured, not written)
  assert.deepEqual(laneScaleOriginOf(project)[2], { kilme: 'ismatuotas', uzrasyta: [] });
  // a sheet both lanes read keeps the pair lane's ratio — and what it said before: every sheet of that reading
  // was measured from its strings (1:50 on sheets 11–17 is the pair lane's rounding of 1:49,4 … 1:51,4)
  assert.equal(merged[4], 82);
  assert.equal(merged[11], 50);
  const origin = laneScaleOriginOf(project);
  for (const p of [2, 3, 4, 8, 9, 11, 12, 13, 14, 15, 17]) assert.deepEqual(origin[p], { kilme: 'ismatuotas', uzrasyta: [] }, `sheet ${p}`);
});

test('both lanes on the same sheet: the pair lane\'s ratio wins, and only a record of THAT ratio tells its origin', async () => {
  const { laneMastelisOf, laneScaleOriginOf } = await import('./durableScale.js');
  const exact50 = Math.round(50 * METERS_PER_POINT_AT_1_TO_1 * 1e6) / 1e6;
  const project = { _meta: {
    plan_dimension_lane: { mastelis: { 2: 50, 8: 83, 12: 50, 20: 115, 21: 50 } },
    geometrija: {
      masteliai: {
        2: { m_per_pt: exact50, mastelis: 50 },          // agrees, at exactly the written 1:50
        8: { m_per_pt: 0.029226, mastelis: 83 },         // agrees, measured
        12: { m_per_pt: 0.017422, mastelis: 49 },        // 1:49,4 — the pair lane's 1:50 is the same measurement, snapped
        20: { m_per_pt: 0.040598, mastelis: 115 },
        21: { m_per_pt: 0.028928, mastelis: 82 },        // another measurement altogether
      },
      masteliai_kiti: {
        20: { ismatuota: 115, uzrasyta: [100] },         // the same ratio: the sheet writes 1:100
        21: { ismatuota: 82, uzrasyta: [50] },           // about 1:82 — says nothing of the pair lane's 1:50
      },
    },
  } };
  assert.deepEqual(laneMastelisOf(project), { 2: 50, 8: 83, 12: 50, 20: 115, 21: 50 });
  const origin = laneScaleOriginOf(project);
  assert.deepEqual(origin[2], { kilme: 'uzrasytas', uzrasyta: [] });
  assert.deepEqual(origin[8], { kilme: 'ismatuotas', uzrasyta: [] });
  assert.deepEqual(origin[12], { kilme: 'ismatuotas', uzrasyta: [] }, 'objektas_a sheet 12: measured, not written');
  assert.deepEqual(origin[20], { kilme: 'ismatuotas', uzrasyta: [100] });
  // a record of 1:82 tells nothing of the pair lane's 1:50: written or measured cannot be told — and never
  // „1:50, the sheet writes 1:50"
  assert.deepEqual(origin[21], { kilme: 'matmenys', uzrasyta: [] });
  // a page whose pair ratio is no number is the geometry lane's
  const gap = { _meta: { plan_dimension_lane: { mastelis: { 2: 0 } }, geometrija: { masteliai: { 2: { m_per_pt: 0.029101, mastelis: 82 } } } } };
  assert.deepEqual(laneMastelisOf(gap), { 2: 82 });
});

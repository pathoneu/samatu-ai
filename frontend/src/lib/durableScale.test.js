import test from 'node:test';
import assert from 'node:assert/strict';
import { setPageScaleDurable, getPageScaleDurable, pxPerMeterFromDurable, durableFromPxPerMeter, autoPageScalesFromRooms } from './durableScale.js';

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

test('autoPageScales: the Beržų demo page 2 still auto-calibrates to ~1:105', () => {
  // 5 traced rooms, real values from backend/data/demo-berzu-24-snapshot-20260714.json
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

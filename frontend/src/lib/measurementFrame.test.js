import test from 'node:test';
import assert from 'node:assert/strict';
import { MEASUREMENTS_FRAME, migrateMeasurementFrame, recheckScalesNotice } from './measurementFrame.js';
import { makeEmbedAdapter } from './viewerEngine/embedPdfAdapter.js';
import { mediaboxSizeFrom } from './viewerEngine/pageRotation.js';

// objektas_a-like: sheet 1 upright 1191×842, sheet 2 an 842×1191 mediabox shown at /Rotate 270 (EmbedPDF
// reports the displayed 1191×842 for it).
const PAGES = [{ size: { width: 1191, height: 842 }, rotation: 0 }, { size: { width: 1191, height: 842 }, rotation: 3 }];
const MPP = 50 * 0.0254 / 72;
const len = (m) => Math.hypot(m.points[1].x - m.points[0].x, m.points[1].y - m.points[0].y) * MPP;

// What the old wiring stored for a click pair on sheet 2: the adapter fed the reported (displayed) size.
function storedOld(screenA, screenB) {
  const a = makeEmbedAdapter({ renderedWidth: 1191, renderedHeight: 842, pageWidthPt: 1191, pageHeightPt: 842,
    reportedRotation: 270 });
  return [a.toPdf(screenA), a.toPdf(screenB)];
}
function storedNew(screenA, screenB) {
  const mb = mediaboxSizeFrom(PAGES[1].size, 270);
  const a = makeEmbedAdapter({ renderedWidth: 1191, renderedHeight: 842, pageWidthPt: mb.width, pageHeightPt: mb.height,
    reportedRotation: 270 });
  return [a.toPdf(screenA), a.toPdf(screenB)];
}

test('old points on a rotated sheet become exactly the points the fixed viewer stores', () => {
  const wall = 4 / MPP;                                  // a 4 m wall, horizontal on screen
  const old = { id: 'h', kind: 'distance', page: 2, points: storedOld({ x: 100, y: 300 }, { x: 100 + wall, y: 300 }) };
  const vert = { id: 'v', kind: 'distance', page: 2, points: storedOld({ x: 500, y: 80 }, { x: 500, y: 80 + wall }) };
  assert.ok(Math.abs(len(old) - 4 * 842 / 1191) < 1e-6);      // 2,83 m before
  assert.ok(Math.abs(len(vert) - 4 * 1191 / 842) < 1e-6);     // 5,66 m before
  const out = migrateMeasurementFrame([old, vert], PAGES, undefined, {});
  assert.equal(out.frame, MEASUREMENTS_FRAME);
  assert.equal(out.changed, 2);
  const expected = storedNew({ x: 100, y: 300 }, { x: 100 + wall, y: 300 });
  out.measurements[0].points.forEach((p, i) => {
    assert.ok(Math.abs(p.x - expected[i].x) < 1e-9 && Math.abs(p.y - expected[i].y) < 1e-9);
  });
  assert.ok(Math.abs(len(out.measurements[0]) - 4) < 1e-9);
  assert.ok(Math.abs(len(out.measurements[1]) - 4) < 1e-9);
});

test('upright sheets, holes, counts and an already-migrated project', () => {
  const upright = { id: 'u', kind: 'distance', page: 1, points: [{ x: 1, y: 2 }, { x: 3, y: 4 }] };
  const area = { id: 'a', kind: 'area', page: 2, points: [{ x: 10, y: 10 }, { x: 20, y: 10 }, { x: 20, y: 20 }],
    holes: [[{ x: 12, y: 12 }, { x: 14, y: 12 }, { x: 14, y: 14 }]] };
  const count = { id: 'c', kind: 'count', page: 2, points: [{ x: 1191, y: 842 }], typeId: 'rozetes' };
  const out = migrateMeasurementFrame([upright, area, count], PAGES, null, {});
  assert.equal(out.measurements[0], upright);                  // untouched object
  const k = 842 / 1191;
  assert.deepEqual(out.measurements[1].holes[0][1], { x: 14 * k, y: 12 / k });
  assert.deepEqual(out.measurements[2].points[0], { x: 842, y: 1191 });   // the corner maps to the mediabox corner
  assert.equal(out.changed, 2);
  assert.equal(migrateMeasurementFrame([area], PAGES, MEASUREMENTS_FRAME), null);
});

test('a project with no rotated sheets just gets the flag', () => {
  const pages = [{ size: { width: 842, height: 595 }, rotation: 0 }];
  const ms = [{ id: 'x', kind: 'distance', page: 1, points: [{ x: 0, y: 0 }, { x: 5, y: 0 }] }];
  const out = migrateMeasurementFrame(ms, pages, undefined);
  assert.equal(out.changed, 0);
  assert.equal(out.measurements, ms);
  assert.equal(out.frame, MEASUREMENTS_FRAME);
});

test('pages not loaded yet: wait', () => {
  assert.equal(migrateMeasurementFrame([], null, undefined), null);
  assert.equal(migrateMeasurementFrame([], [{ rotation: 0 }], undefined), null);
});

test('a calibration he drew on a rotated sheet is named for a recheck; the lane and a picked ratio are not', () => {
  const out = migrateMeasurementFrame([], PAGES, undefined,
    { 1: { source: 'user' }, 2: { source: 'user', metersPerPointX: 0.01 } });
  assert.deepEqual(out.recheckScales, [2]);
  assert.deepEqual(migrateMeasurementFrame([], PAGES, undefined, { 2: { source: 'standard' } }).recheckScales, []);
});

test('the recheck notice names the sheets, once', () => {
  assert.equal(recheckScalesNotice([]), null);
  assert.equal(recheckScalesNotice(undefined), null);
  assert.equal(recheckScalesNotice([2]), 'Lapo 2 mastelis nustatytas ranka pasuktame lape — patikrinkite jį vieną kartą');
  assert.equal(recheckScalesNotice([2, 5]), 'Lapų 2, 5 masteliai nustatyti ranka pasuktuose lapuose — patikrinkite juos vieną kartą');
});

test('migrating twice is a no-op: the second pass sees the flag', () => {
  const ms = [{ id: 'd', kind: 'distance', page: 2, points: [{ x: 10, y: 10 }, { x: 20, y: 30 }] }];
  const once = migrateMeasurementFrame(ms, PAGES, null, {});
  assert.equal(once.changed, 1);
  assert.equal(migrateMeasurementFrame(once.measurements, PAGES, once.frame, {}), null);
});

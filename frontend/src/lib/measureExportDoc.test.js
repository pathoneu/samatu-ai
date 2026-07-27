import test from 'node:test';
import assert from 'node:assert/strict';
import { buildMeasureExportDoc } from './measureExportDoc.js';
import { toMeasurementsCSV } from './measureExport.js';

// Three traced rooms on page 2 → autoPageScalesFromRooms yields a page scale.
// (THREE, not two: autoPageScalesFromRooms requires ≥3 samples per page since
// the 2026-07-27 robustness fix — a 2-sample "median" was really a mean.)
// Each polygon covers 1% of the page and is 10 m², page is 1000x1000 pt:
//   m2/frac = 1000 ; mpp = sqrt(1000 / 1_000_000) = 0.0316227766 m/pt
const square = (x, y, s) => [[x, y], [x + s, y], [x + s, y + s], [x, y + s]];
const room = (nr, x) => ({
  nr,
  plotas_m2: 10,
  polygon_pct: square(x, 0.1, 0.1),
  page_width_pdf: 1000,
  page_height_pdf: 1000,
  puslapio_nr: 2,
  polygon_source: 'auto_floodfill',
});

const project = {
  patalpos: [room(1, 0.1), room(2, 0.3), room(3, 0.5)],
  measurements: [
    { id: 'm1', kind: 'distance', page: 2, points: [{ x: 0, y: 0 }, { x: 100, y: 0 }] },
  ],
  countTypes: [],
};

test('buildMeasureExportDoc: auto page scale is merged in', () => {
  const doc = buildMeasureExportDoc(project);
  assert.ok(doc.measureScales[2], 'page 2 must carry the auto scale');
  assert.equal(doc.measureScales[2].source, 'auto');
  assert.ok(Math.abs(doc.measureScales[2].metersPerPointX - Math.sqrt(0.001)) < 1e-9);
});

test('buildMeasureExportDoc: a user calibration overrides the auto scale', () => {
  const withUser = {
    ...project,
    pageScalesDurable: { 2: { metersPerPointX: 0.05, metersPerPointY: 0.05, calibrated: true, source: 'user' } },
  };
  assert.equal(buildMeasureExportDoc(withUser).measureScales[2].source, 'user');
});

test('CSV export of an auto-calibrated page is NOT 0,00', () => {
  const csv = toMeasurementsCSV(buildMeasureExportDoc(project));
  const row = csv.split('\r\n')[1];
  assert.ok(/Atstumas/.test(row), row);
  assert.ok(!/;0,00;/.test(row), `expected a non-zero length, got: ${row}`);
  // 100 pt * 0.0316227766 m/pt = 3.16 m
  assert.ok(/;3,16;m/.test(row), row);
});

test('buildMeasureExportDoc: empty project is safe', () => {
  const doc = buildMeasureExportDoc({});
  assert.deepEqual(doc.measurements, []);
  assert.deepEqual(doc.measureScales, {});
  assert.deepEqual(doc.countTypes, []);
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { csvSafe } from './csvSafe.js';
import { toMeasurementsCSV } from './measureExport.js';

test('formula-looking text gets an apostrophe; numbers and plain text do not', () => {
  assert.equal(csvSafe('=HYPERLINK("http://x","spausk")'), `'=HYPERLINK("http://x","spausk")`);
  assert.equal(csvSafe('+370 600'), `'+370 600`);
  assert.equal(csvSafe('@SUM(A1)'), `'@SUM(A1)`);
  assert.equal(csvSafe('\tx'), `'\tx`);
  assert.equal(csvSafe('-1,5'), '-1,5');
  assert.equal(csvSafe('12.40'), '12.40');
  assert.equal(csvSafe('Svetainė'), 'Svetainė');
  assert.equal(csvSafe(null), '');
});

test('the measurements CSV neutralises a formula in a classification', () => {
  const csv = toMeasurementsCSV({
    measurements: [{ id: 'm1', kind: 'distance', page: 1, points: [{ x: 0, y: 0 }, { x: 10, y: 0 }],
      classification: '=1+1' }],
    measureScales: { 1: { metersPerPointX: 0.01, metersPerPointY: 0.01, calibrated: true } },
  });
  assert.ok(!/;=1\+1/.test(csv), csv);
});

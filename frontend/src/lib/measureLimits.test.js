import test from 'node:test';
import assert from 'node:assert/strict';
import { MEASUREMENTS_PER_SHEET_WARN, sheetsCrossingLimit, sheetLimitMessage } from './measureLimits.js';
import { isBannedText } from './userText.js';

const many = (page, n) => Array.from({ length: n }, (_, i) => ({ id: `${page}-${i}`, page }));

test('the warning fires once, when a sheet crosses the measured limit', () => {
  const L = MEASUREMENTS_PER_SHEET_WARN;
  assert.equal(L, 1500);
  assert.deepEqual(sheetsCrossingLimit(many(1, L - 1), many(1, L)), [{ page: 1, count: L }]);
  assert.deepEqual(sheetsCrossingLimit(many(1, L), many(1, L + 1)), [], 'already over: no second warning');
  assert.deepEqual(sheetsCrossingLimit([], [...many(2, L), ...many(1, 10)]), [{ page: 2, count: L }]);
  assert.deepEqual(sheetsCrossingLimit(many(1, L), many(1, L - 5)), [], 'going down never warns');
  assert.deepEqual(sheetsCrossingLimit(null, undefined), []);
});

test('the message says what happened and what to do, in plain words', () => {
  const msg = sheetLimitMessage({ page: 3, count: 1500 });
  assert.match(msg, /^3 lape jau 1500 matavimų/);
  assert.match(msg, /ištrinkite|eksportuokite/);
  assert.equal(isBannedText(msg), false);
});

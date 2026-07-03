import test from 'node:test';
import assert from 'node:assert/strict';
import { makeMeasurement, measurementValue, DEFAULT_COUNT_TYPES } from './measurements.js';

const s = { metersPerPointX: 0.05, metersPerPointY: 0.05, calibrated: true };

test('distance measurement value = metres', () => {
  const m = makeMeasurement('distance', 2, [{ x: 0, y: 0 }, { x: 200, y: 0 }]);
  assert.ok(Math.abs(measurementValue(m, s).value - 10) < 1e-9);
});
test('area measurement reports value (m²) + secondary (perimeter m)', () => {
  const m = makeMeasurement('area', 2, [{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 100 }, { x: 0, y: 100 }]);
  const r = measurementValue(m, s);
  assert.ok(Math.abs(r.value - 50) < 1e-9);
  assert.ok(Math.abs(r.secondary - 30) < 1e-9);
});
test('seed count types exist', () => {
  assert.ok(DEFAULT_COUNT_TYPES.find(t => t.id === 'rozetes'));
});

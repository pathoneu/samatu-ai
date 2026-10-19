import test from 'node:test';
import assert from 'node:assert/strict';
import { makeMeasurement, measurementValue, DEFAULT_COUNT_TYPES, makeCountType, nextTypeLook, COUNT_TYPE_SHAPES } from './measurements.js';

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

// Red means an error on the drawing (Pathon v3 overlay vocabulary) — never a count type's default colour.
test('no default or cycled count-type colour is red', () => {
  const hue = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const max = Math.max(r, g, b); const min = Math.min(r, g, b); const d = max - min;
    if (!d) return null;
    const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
    return (h * 60 + 360) % 360;
  };
  const isRed = (hex) => { const h = hue(hex); return h != null && (h < 15 || h > 345); };
  const cycled = [];
  for (let i = 0; i < 16; i += 1) cycled.push(makeCountType(`Tipas ${i}`, cycled));
  for (const t of [...DEFAULT_COUNT_TYPES, ...cycled]) assert.equal(isRed(t.color), false, `${t.label}: ${t.color}`);
});

test('W5-A A7: every new count type differs from the last in shape as well as colour; a chosen shape is kept', () => {
  const types = [];
  for (let i = 0; i < 12; i += 1) types.push(makeCountType(`T${i}`, types));
  for (let i = 1; i < types.length; i += 1) {
    assert.notEqual(types[i].shape, types[i - 1].shape, `${i}`);
    assert.notEqual(types[i].color, types[i - 1].color, `${i}`);
  }
  assert.equal(new Set(types.map((t) => `${t.color}|${t.shape}`)).size, types.length);
  assert.ok(types.slice(0, 4).every((t, i, all) => all.findIndex((x) => x.shape === t.shape) === i), 'the first four use all four shapes');
  const chosen = makeCountType('Kvadratas', types, { shape: 'square' });
  assert.equal(chosen.shape, 'square');
  assert.ok(!types.some((t) => t.color === chosen.color && t.shape === 'square'));
  assert.ok(COUNT_TYPE_SHAPES.includes(nextTypeLook([]).shape));
});

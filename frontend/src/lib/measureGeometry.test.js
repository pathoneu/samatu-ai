import test from 'node:test';
import assert from 'node:assert/strict';
import {
  calibrateUniform, realDistanceM, shoelaceAreaM2, realPathLengthM,
  netAreaM2, scaleFromRatio, parseFeetInches, formatFeetInches, formatNumberLT,
} from './measureGeometry.js';

const rect = [{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 100 }, { x: 0, y: 100 }];

test('calibrateUniform solves metres-per-point', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  assert.ok(Math.abs(s.metersPerPointX - 0.05) < 1e-9);
});
test('realDistanceM under scale', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  assert.ok(Math.abs(realDistanceM({ x: 0, y: 0 }, { x: 200, y: 0 }, s) - 10) < 1e-9);
});
test('anisotropic shoelace gives correct m² for stretched scans', () => {
  const aniso = { metersPerPointX: 0.01, metersPerPointY: 0.03, calibrated: true };
  assert.ok(Math.abs(shoelaceAreaM2(rect, aniso) - 6) < 1e-9);
  assert.ok(Math.abs(shoelaceAreaM2([...rect].reverse(), aniso) - 6) < 1e-9);
});
test('closed perimeter 30 m, open polyline 25 m', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  assert.ok(Math.abs(realPathLengthM(rect, s, true) - 30) < 1e-9);
  assert.ok(Math.abs(realPathLengthM(rect, s, false) - 25) < 1e-9);
});
test('net area subtracts holes', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  const holes = [[{ x: 10, y: 10 }, { x: 60, y: 10 }, { x: 60, y: 60 }, { x: 10, y: 60 }]];
  assert.ok(Math.abs(netAreaM2(rect, holes, s) - 43.75) < 1e-9);
});
test('scaleFromRatio 1:50', () => {
  assert.ok(Math.abs(scaleFromRatio(50).metersPerPointX - (50 / 72) * 0.0254) < 1e-12);
});
test('imperial parse/format edge cases (the fixed bugs)', () => {
  assert.ok(parseFeetInches('-0\'6"') < 0);
  assert.ok(Math.abs(parseFeetInches('5\' 1/2"') - 60.5 * 0.0254) < 1e-9);
  assert.ok(!formatFeetInches(-0.0001).includes('−'));
  assert.equal(formatFeetInches(3.81), '12\' 6"');
});
test('LT number formatting', () => {
  assert.equal(formatNumberLT(1234.5, 2), '1 234,50');
  assert.equal(formatNumberLT(1234, 0), '1 234');
});

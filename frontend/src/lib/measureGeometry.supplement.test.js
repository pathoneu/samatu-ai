// Supplementary coverage for measureGeometry.js gaps not already exercised by
// measureGeometry.test.js: raw pdfDistance, uncalibratedScale, per-axis
// (anisotropic) calibration, and an explicit unit-square / scaled-distance
// sanity check as requested for the accuracy-critical calc audit.
//
// CORE INVARIANT (per file header): geometry lives in PDF-point space; one
// calibration ratio (meters-per-point) converts to real units at the end.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  pdfDistance, calibrateAxis, uncalibratedScale, calibrateUniform,
  realDistanceM, shoelaceAreaM2,
} from './measureGeometry.js';

test('pdfDistance: 3-4-5 triangle in raw point space', () => {
  assert.equal(pdfDistance({ x: 0, y: 0 }, { x: 3, y: 4 }), 5);
});

test('uncalibratedScale: zeroed scale, calibrated=false, source=none', () => {
  const s = uncalibratedScale();
  assert.deepEqual(s, {
    metersPerPointX: 0, metersPerPointY: 0, calibrated: false, source: 'none',
  });
});

test('unit square: 1pt-per-meter scale gives area=1 m2 for a 1x1 point square', () => {
  const s = { metersPerPointX: 1, metersPerPointY: 1, calibrated: true };
  const unitSquare = [{ x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 }];
  assert.equal(shoelaceAreaM2(unitSquare, s), 1);
});

test('scaled distance: calibrating 100pt = 5m makes a 300pt segment read as 15m', () => {
  const s = calibrateUniform({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm');
  const d = realDistanceM({ x: 10, y: 10 }, { x: 310, y: 10 }, s);
  assert.ok(Math.abs(d - 15) < 1e-9);
});

test('calibrateAxis: explicit x-axis calibration only updates metersPerPointX', () => {
  const base = { metersPerPointX: 0.02, metersPerPointY: 0.02, calibrated: true, source: 'user' };
  const next = calibrateAxis({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm', base, 'x');
  assert.ok(Math.abs(next.metersPerPointX - 0.05) < 1e-9);
  assert.equal(next.metersPerPointY, 0.02); // untouched axis carried over from base
  assert.equal(next.calibrated, true);
});

test('calibrateAxis: auto-picks the longer axis when axis arg omitted', () => {
  // dx=100 > dy=10 → should calibrate X even though we pass axis=undefined
  const next = calibrateAxis({ x: 0, y: 0 }, { x: 100, y: 10 }, 10, 'm', null, undefined);
  assert.ok(Math.abs(next.metersPerPointX - 0.1) < 1e-9);
});

test('calibrateAxis: flags anisotropic=true when X/Y scales diverge by >2%', () => {
  const base = { metersPerPointX: 0.05, metersPerPointY: 0.05, calibrated: true, source: 'user' };
  // Recalibrate Y to a noticeably different ratio (stretched scan simulation)
  const next = calibrateAxis({ x: 0, y: 0 }, { x: 0, y: 100 }, 8, 'm', base, 'y');
  assert.equal(next.anisotropic, true);
});

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
  storedAxisForDisplayAxis, axisSpanShare, AXIS_SPAN_MIN_SHARE,
  draftCommitPoints, dedupeDraftPoints,
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

// ── Audit fixes 2026-07-27 ──────────────────────────────────────────────────

test('calibrateAxis P0: axis mode on an UNCALIBRATED base seeds BOTH axes', () => {
  // Virgin page: uncalibratedScale() is the base the dialog passes.
  const next = calibrateAxis({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm', uncalibratedScale(), 'x');
  assert.ok(Math.abs(next.metersPerPointX - 0.05) < 1e-9);
  assert.equal(next.metersPerPointY, next.metersPerPointX); // NOT 0 → areas are real
  assert.equal(next.calibrated, true);
  assert.equal(next.anisotropic, false);
});

test('calibrateAxis P0: a virgin axis calibration gives a NON-ZERO area', () => {
  const s = calibrateAxis({ x: 0, y: 0 }, { x: 0, y: 100 }, 5, 'm', uncalibratedScale(), 'y');
  const square = [{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 100 }, { x: 0, y: 100 }];
  assert.ok(Math.abs(shoelaceAreaM2(square, s) - 25) < 1e-9);
});

test('calibrateAxis P0: base with calibrated:true but a 0 axis is treated as virgin', () => {
  const broken = { metersPerPointX: 0.04, metersPerPointY: 0, calibrated: true, source: 'user' };
  const next = calibrateAxis({ x: 0, y: 0 }, { x: 100, y: 0 }, 5, 'm', broken, 'x');
  assert.equal(next.metersPerPointY, next.metersPerPointX);
});

test('calibrateAxis: a CALIBRATED base keeps the per-axis override behaviour', () => {
  const base = { metersPerPointX: 0.02, metersPerPointY: 0.02, calibrated: true, source: 'user' };
  const next = calibrateAxis({ x: 0, y: 0 }, { x: 0, y: 100 }, 5, 'm', base, 'y');
  assert.equal(next.metersPerPointX, 0.02);           // untouched axis preserved
  assert.ok(Math.abs(next.metersPerPointY - 0.05) < 1e-9);
});

test('calibrateAxis: still throws on a degenerate axis span', () => {
  assert.throws(
    () => calibrateAxis({ x: 10, y: 0 }, { x: 10, y: 90 }, 5, 'm', null, 'x'),
    /Kalibravimo ašis per trumpa/,
  );
});

test('calibrateUniform: still throws on a zero-length line', () => {
  assert.throws(
    () => calibrateUniform({ x: 7, y: 7 }, { x: 7, y: 7 }, 5, 'm'),
    /Kalibravimo linija per trumpa/,
  );
});

test('storedAxisForDisplayAxis: unrotated pages map display axes 1:1', () => {
  for (const rot of [0, 180]) {
    assert.equal(storedAxisForDisplayAxis('x', rot), 'x');
    assert.equal(storedAxisForDisplayAxis('y', rot), 'y');
  }
});

test('storedAxisForDisplayAxis: 90/270 swap what the user calls horizontal', () => {
  for (const rot of [90, 270]) {
    assert.equal(storedAxisForDisplayAxis('x', rot), 'y');
    assert.equal(storedAxisForDisplayAxis('y', rot), 'x');
  }
});

test('storedAxisForDisplayAxis: uniform + junk rotations pass through safely', () => {
  assert.equal(storedAxisForDisplayAxis('uniform', 90), 'uniform');
  assert.equal(storedAxisForDisplayAxis('x', undefined), 'x');
  assert.equal(storedAxisForDisplayAxis('x', -90), 'y');   // -90 normalises to 270
  assert.equal(storedAxisForDisplayAxis('x', 450), 'y');   // 450 normalises to 90
});

test('axisSpanShare: axis-aligned line is a full share, perpendicular is zero', () => {
  assert.equal(axisSpanShare({ x: 0, y: 0 }, { x: 100, y: 0 }, 'x'), 1);
  assert.equal(axisSpanShare({ x: 0, y: 0 }, { x: 100, y: 0 }, 'y'), 0);
  assert.ok(Math.abs(axisSpanShare({ x: 0, y: 0 }, { x: 3, y: 4 }, 'x') - 0.6) < 1e-9);
  assert.equal(axisSpanShare({ x: 5, y: 5 }, { x: 5, y: 5 }, 'x'), 0);   // degenerate
});

test('axisSpanShare: a near-perpendicular pick falls below the rejection floor', () => {
  // 100 pt long, 5 pt of it along X → 5% share: mis-scales 20x if accepted.
  assert.ok(axisSpanShare({ x: 0, y: 0 }, { x: 5, y: 100 }, 'x') < AXIS_SPAN_MIN_SHARE);
  assert.ok(axisSpanShare({ x: 0, y: 0 }, { x: 5, y: 100 }, 'y') > AXIS_SPAN_MIN_SHARE);
});

test('draftCommitPoints: 2-point area draft does NOT commit', () => {
  assert.equal(draftCommitPoints([{ x: 0, y: 0 }, { x: 10, y: 0 }], 'area'), null);
});

test('draftCommitPoints: 3 clicks that dedupe to 2 do NOT commit as an area', () => {
  // click A, click B, double-click at B → B appended twice.
  const pts = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10.2, y: 0 }];
  assert.equal(draftCommitPoints(pts, 'area'), null);
});

test('draftCommitPoints: 3 distinct points commit as an area, deduped', () => {
  const pts = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 10, y: 10.1 }];
  const out = draftCommitPoints(pts, 'area');
  assert.equal(out.length, 3);
});

test('draftCommitPoints: distance/perimeter still commit at 2 points', () => {
  const pts = [{ x: 0, y: 0 }, { x: 10, y: 0 }];
  assert.equal(draftCommitPoints(pts, 'distance').length, 2);
  assert.equal(draftCommitPoints(pts, 'perimeter').length, 2);
  assert.equal(draftCommitPoints([{ x: 0, y: 0 }], 'distance'), null);
});

test('dedupeDraftPoints: drops only CONSECUTIVE coincident vertices', () => {
  const pts = [{ x: 0, y: 0 }, { x: 0, y: 0 }, { x: 5, y: 0 }, { x: 0, y: 0 }];
  assert.equal(dedupeDraftPoints(pts).length, 3);
  assert.deepEqual(dedupeDraftPoints(null), []);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { setPageScaleDurable, getPageScaleDurable, pxPerMeterFromDurable, durableFromPxPerMeter } from './durableScale.js';

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

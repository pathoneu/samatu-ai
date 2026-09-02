import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  isStretchCeiling,
  stretchCeilingMap,
  withStretchCeiling,
} from './stretchCeiling.js';

test('an untouched project has no stretch ceilings', () => {
  assert.deepEqual(stretchCeilingMap(undefined), {});
  assert.deepEqual(stretchCeilingMap(null), {});
  assert.deepEqual(stretchCeilingMap({}), {});
  assert.equal(isStretchCeiling({}, '101'), false);
  assert.equal(isStretchCeiling(undefined, '101'), false);
});

test('garbage in the blob never throws and never flips a room on', () => {
  for (const raw of ['nope', 42, [], null]) {
    assert.deepEqual(stretchCeilingMap({ stretch_ceiling_override: raw }), {});
  }
  const a = { stretch_ceiling_override: { 101: 'taip', 102: '', 103: null } };
  assert.equal(isStretchCeiling(a, '101'), false);
  assert.equal(isStretchCeiling(a, '102'), false);
  assert.equal(isStretchCeiling(a, '103'), false);
});

test('the on-values the backend accepts are the on-values here', () => {
  const a = { stretch_ceiling_override: { 101: 1, 102: 1.0, 103: '1', 104: true } };
  for (const nr of ['101', '102', '103', '104']) {
    assert.equal(isStretchCeiling(a, nr), true, nr);
  }
  const off = { stretch_ceiling_override: { 101: 0, 102: '0', 103: false } };
  for (const nr of ['101', '102', '103']) {
    assert.equal(isStretchCeiling(off, nr), false, nr);
  }
});

test('flipping a room writes the payload the backend whitelists', () => {
  const before = { sienos_storis_m: 0.1 };
  const after = withStretchCeiling(before, '101', true);
  assert.deepEqual(after.stretch_ceiling_override, { 101: 1 });
  // Other assumptions survive; the input is not mutated.
  assert.equal(after.sienos_storis_m, 0.1);
  assert.equal(before.stretch_ceiling_override, undefined);
});

test('flipping a room back writes an explicit 0, not a delete', () => {
  const on = withStretchCeiling({}, '101', true);
  const off = withStretchCeiling(on, '101', false);
  assert.deepEqual(off.stretch_ceiling_override, { 101: 0 });
  assert.equal(isStretchCeiling(off, '101'), false);
});

test('flipping one room leaves the others alone', () => {
  let a = withStretchCeiling({}, '101', true);
  a = withStretchCeiling(a, '102', true);
  a = withStretchCeiling(a, '101', false);
  assert.deepEqual(a.stretch_ceiling_override, { 101: 0, 102: 1 });
});

test('withStretchCeiling tolerates a null assumptions blob', () => {
  const a = withStretchCeiling(null, '101', true);
  assert.deepEqual(a.stretch_ceiling_override, { 101: 1 });
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { withoutDismissed } from './sanityDismissals.js';
import { warningKey } from './sanitySeverity.js';

const WARNINGS = [
  { source: 'sanity_checks', code: 'paintable_floor_ratio', message: 'a' },
  { source: 'sanity_checks', code: 'ceiling_floor_mismatch', message: 'b' },
  { source: 'perimeter_validator', code: 'perimeter_out_of_bounds', message: 'c' },
];

test('withoutDismissed: drops exactly the judged warnings', () => {
  const dismissed = new Set([warningKey(WARNINGS[1])]);
  const left = withoutDismissed(WARNINGS, dismissed, warningKey);
  assert.deepEqual(left.map((w) => w.code),
    ['paintable_floor_ratio', 'perimeter_out_of_bounds']);
});

test('withoutDismissed: an empty set is a pass-through, same reference', () => {
  assert.equal(withoutDismissed(WARNINGS, new Set(), warningKey), WARNINGS);
  assert.equal(withoutDismissed(WARNINGS, null, warningKey), WARNINGS);
});

test('withoutDismissed: a malformed list is an empty list, never a throw', () => {
  assert.deepEqual(withoutDismissed(undefined, new Set(), warningKey), []);
  assert.deepEqual(withoutDismissed('nope', new Set(), warningKey), []);
});

test('withoutDismissed: dismissing every warning empties the pill', () => {
  // The reason the pill shares this store: it must be able to reach zero.
  const all = new Set(WARNINGS.map(warningKey));
  assert.deepEqual(withoutDismissed(WARNINGS, all, warningKey), []);
});

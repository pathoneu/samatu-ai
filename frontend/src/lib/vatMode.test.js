import test from 'node:test';
import assert from 'node:assert/strict';
import { VAT_REVERSE, VAT_STANDARD, isReverseVat, vatChoice, vatPercent } from './vatMode.js';

// The drawing label `archetipas` is read off the drawing, not chosen by the
// contractor. His explicit `vat_mode` must win in both directions; with none,
// the old label rule stays so stored projects do not change (audit 2026-09-29).

test('his explicit choice wins over the drawing label, both ways', () => {
  assert.equal(isReverseVat({ vat_mode: 'standard', archetipas: 'renovacija' }), false);
  assert.equal(isReverseVat({ vat_mode: 'reverse_vat', archetipas: 'premium' }), true);
  assert.equal(vatPercent({ vat_mode: 'standard', archetipas: 'renovacija' }), 21);
  assert.equal(vatPercent({ vat_mode: 'reverse_vat' }), 0);
});

test('without his choice the old label rule stays exactly', () => {
  assert.equal(isReverseVat({ archetipas: 'renovacija' }), true);
  assert.equal(isReverseVat({ archetipas: 'Renovacija' }), true);
  assert.equal(isReverseVat({ archetipas: 'premium' }), false);
  assert.equal(isReverseVat({}), false);
  assert.equal(isReverseVat(null), false);
  assert.equal(isReverseVat({ vat_mode: 'be_pvm', archetipas: 'renovacija' }), true,
    'an unknown value is not a choice');
  assert.equal(vatPercent({ archetipas: 'renovacija' }), 0);
  assert.equal(vatPercent({}), 21);
  assert.equal(vatPercent({ vat_rate: 9 }), 9, 'the stored rate still applies');
});

test('vatChoice says whether the mode came from him or from the label', () => {
  assert.deepEqual(vatChoice({ archetipas: 'renovacija' }), { mode: VAT_REVERSE, fromLabel: true });
  assert.deepEqual(vatChoice({ archetipas: 'premium' }), { mode: VAT_STANDARD, fromLabel: false });
  assert.deepEqual(vatChoice({ vat_mode: 'reverse_vat', archetipas: 'renovacija' }),
    { mode: VAT_REVERSE, fromLabel: false });
  assert.deepEqual(vatChoice({ vat_mode: 'standard', archetipas: 'renovacija' }),
    { mode: VAT_STANDARD, fromLabel: false });
});

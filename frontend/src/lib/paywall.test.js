import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectPaywall, paywallErrorFrom } from './paywall.js';

test('detectPaywall: 402 quota_exceeded → reason + message', () => {
  const pw = detectPaywall({ status: 402, body: { error: 'quota_exceeded', message: 'Limitas' } });
  assert.deepEqual(pw, { reason: 'quota_exceeded', message: 'Limitas' });
});

test('detectPaywall: 402 trial_used', () => {
  const pw = detectPaywall({ status: 402, body: { error: 'trial_used', message: 'Panaudota' } });
  assert.equal(pw.reason, 'trial_used');
});

test('detectPaywall: 403 company_code_required', () => {
  const pw = detectPaywall({ status: 403, body: { error: 'company_code_required' } });
  assert.equal(pw.reason, 'company_code_required');
  assert.equal(pw.message, undefined);
});

test('detectPaywall: 200/other status → null', () => {
  assert.equal(detectPaywall({ status: 500, body: { error: 'quota_exceeded' } }), null);
  assert.equal(detectPaywall({ status: 200, body: {} }), null);
});

test('detectPaywall: 403 with unrelated error (e.g. plain auth) → null', () => {
  assert.equal(detectPaywall({ status: 403, body: { error: 'forbidden' } }), null);
  assert.equal(detectPaywall({ status: 402, body: null }), null);
});

test('detectPaywall: null/undefined input → null', () => {
  assert.equal(detectPaywall(null), null);
  assert.equal(detectPaywall(undefined), null);
});

test('paywallErrorFrom: carries status + body', () => {
  const err = paywallErrorFrom(402, { error: 'quota_exceeded', message: 'Limitas pasiektas' });
  assert.equal(err.status, 402);
  assert.equal(err.message, 'Limitas pasiektas');
  assert.equal(err.body.error, 'quota_exceeded');
  // round-trips through detectPaywall
  assert.equal(detectPaywall(err).reason, 'quota_exceeded');
});

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectPaywall, paywallErrorFrom, planById } from './paywall.js';

// Verbatim `plans` array from GET /api/billing/v2/status, captured 2026-07-27
// off a real backend booted with BILLING_ENABLED=1. Do not "tidy" it — the
// whole point is that `name` is a display label that does NOT equal the id.
const REAL_PLANS = [
  { id: 'pro', name: 'Pro', price_eur: 49, pdf_quota_per_month: 10, overage_eur_per_pdf: 8, seats: 1, features: ['interior', 'f2f3_export', 'audit_trail', 'priority_queue'] },
  { id: 'studio', name: 'Studio', price_eur: 149, pdf_quota_per_month: 35, overage_eur_per_pdf: 5, seats: 3, features: ['interior', 'f2f3_export', 'audit_trail', 'priority_queue', 'multi_seat', 'unit_price_overrides'] },
  { id: 'oneoff', name: 'Vienkartinis', price_eur: 12, pdf_quota_per_month: 0, overage_eur_per_pdf: null, seats: 1, features: ['interior', 'f2f3_export'] },
];

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

test('planById: all 3 purchasable plans resolve from the real /status payload', () => {
  const pro = planById(REAL_PLANS, 'pro');
  const studio = planById(REAL_PLANS, 'studio');
  const oneoff = planById(REAL_PLANS, 'oneoff');
  // UpgradeDialog renders a PlanRow per truthy plan — all three must be found,
  // or the paywall shows a dialog with nothing to buy.
  assert.equal([pro, studio, oneoff].filter(Boolean).length, 3);
  assert.equal(pro.price_eur, 49);
  assert.equal(studio.price_eur, 149);
  assert.equal(oneoff.price_eur, 12);
});

test('planById: matching on `name` (the old bug) resolves NOTHING', () => {
  // Regression witness for 2026-07-27 / 175a206: `plans.find(p => p.name === id)`
  // is what UpgradeDialog + Pricing both shipped, and it finds zero plans
  // because name is "Pro"/"Studio"/"Vienkartinis".
  const byName = (id) => REAL_PLANS.find((p) => p.name === id);
  assert.equal(['pro', 'studio', 'oneoff'].map(byName).filter(Boolean).length, 0);
});

test('planById: unknown id / non-array input → undefined, never throws', () => {
  assert.equal(planById(REAL_PLANS, 'enterprise'), undefined);
  assert.equal(planById([], 'pro'), undefined);
  assert.equal(planById(undefined, 'pro'), undefined);
  assert.equal(planById(null, 'pro'), undefined);
});

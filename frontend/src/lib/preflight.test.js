import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  preflightCard, verdictKey, pollLimitMs, PREFLIGHT_VERDICTS, DEFAULT_POLL_MINUTES,
} from './preflight.js';

/**
 * Verbatim `POST /api/pdf-preflight` payloads, captured off the real backend
 * against backend/test_pdfs. Do not "tidy" them — the shapes are the contract.
 */
const VIDAUS_APDAILA = {   // 17 pp interior project — the happy path
  page_count: 17, verdict: 'interior_plan', interior_pages_estimate: 15,
  est_minutes: 'iki 30 min', est_minutes_max: 30, warnings: [],
  hard_block: false, hard_block_reason: null,
  sampled_pages: 11, sample_truncated: true,
};
const SA_02 = {            // 37 pp architectural set, no interior sheets
  page_count: 37, verdict: 'mixed_bundle', interior_pages_estimate: 1,
  est_minutes: '30–60 min', est_minutes_max: 60,
  warnings: ['Interjero brėžinių požymių radome maždaug 1 iš 37 psl. …'],
  hard_block: false, hard_block_reason: null,
  sampled_pages: 35, sample_truncated: true,
};
const BD_139 = {           // 139 pp bundle — past the pipeline's page limit
  page_count: 139, verdict: 'mixed_bundle', interior_pages_estimate: 2,
  est_minutes: 'virš valandos', est_minutes_max: 90, warnings: [],
  hard_block: true,
  hard_block_reason: 'PDF turi 139 psl., o vienu kartu analizuojame iki 100. …',
  sampled_pages: 56, sample_truncated: false,
};

test('interior project reads as information, not as a question', () => {
  const card = preflightCard(VIDAUS_APDAILA);
  assert.equal(card.tone, 'ok');
  assert.equal(card.blocked, false);
  // No "Tęsti vis tiek?" on a good file — that trains people to click through.
  assert.equal(card.needsDecision, false);
  assert.equal(card.pageCount, 17);
  assert.equal(card.estMinutes, 'iki 30 min');
});

test('a bundle without interior sheets asks the user to decide', () => {
  const card = preflightCard(SA_02);
  assert.equal(card.tone, 'caution');
  assert.equal(card.needsDecision, true);
  assert.equal(card.blocked, false);
  assert.equal(card.warnings.length, 1);
});

test('an over-length bundle is blocked and carries the reason', () => {
  const card = preflightCard(BD_139);
  assert.equal(card.tone, 'blocked');
  assert.equal(card.blocked, true);
  assert.match(card.reason, /139 psl/);
  assert.equal(card.needsDecision, true);
});

test('hard_block outranks the verdict', () => {
  const card = preflightCard({ ...BD_139, verdict: 'interior_plan' });
  assert.equal(card.tone, 'blocked');
});

for (const v of ['table_only', 'photo_or_scan', 'facade_or_site', 'mixed_bundle']) {
  test(`${v} is a caution`, () => {
    assert.equal(preflightCard({ ...SA_02, verdict: v }).tone, 'caution');
  });
}

test('unknown is neutral — we did not decide, so we do not alarm', () => {
  const card = preflightCard({ ...SA_02, verdict: 'unknown', warnings: [] });
  assert.equal(card.tone, 'neutral');
  assert.equal(card.needsDecision, true);
});

test('a verdict from a newer backend degrades to unknown, never to a crash', () => {
  const card = preflightCard({ ...SA_02, verdict: 'some_future_verdict' });
  assert.equal(card.verdict, 'unknown');
  assert.equal(card.tone, 'neutral');
});

test('a failed or empty probe renders no card at all', () => {
  assert.equal(preflightCard(null), null);
  assert.equal(preflightCard(undefined), null);
  assert.equal(preflightCard({}), null);
  assert.equal(preflightCard({ page_count: 0, verdict: 'unknown' }), null);
});

test('missing warnings array does not break the card', () => {
  const card = preflightCard({ page_count: 5, verdict: 'unknown' });
  assert.deepEqual(card.warnings, []);
  assert.equal(card.estMinutes, '');
});

test('verdictKey maps every verdict, and anything else to unknown', () => {
  for (const v of PREFLIGHT_VERDICTS) {
    assert.equal(verdictKey(v), `newProject.preflight.verdict.${v}`);
  }
  assert.equal(verdictKey('nonsense'), 'newProject.preflight.verdict.unknown');
  assert.equal(verdictKey(undefined), 'newProject.preflight.verdict.unknown');
});

test('poller ceiling: no preflight keeps the historical 40 minutes', () => {
  assert.equal(pollLimitMs(null), DEFAULT_POLL_MINUTES * 60 * 1000);
  assert.equal(pollLimitMs(undefined), 40 * 60 * 1000);
  assert.equal(pollLimitMs({}), 40 * 60 * 1000);
});

test('poller ceiling never drops below the historical floor', () => {
  assert.equal(pollLimitMs(VIDAUS_APDAILA), 40 * 60 * 1000);   // tier says 30
});

test('poller ceiling grows for the long tiers', () => {
  assert.equal(pollLimitMs(SA_02), 60 * 60 * 1000);
  assert.equal(pollLimitMs(BD_139), 90 * 60 * 1000);
});

test('poller ceiling ignores a nonsense est_minutes_max', () => {
  assert.equal(pollLimitMs({ est_minutes_max: 'soon' }), 40 * 60 * 1000);
  assert.equal(pollLimitMs({ est_minutes_max: -5 }), 40 * 60 * 1000);
});

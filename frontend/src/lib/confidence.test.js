import test from 'node:test';
import assert from 'node:assert/strict';
import {
  CONF_ZALIA,
  CONF_GELTONA,
  CONF_RAUDONA,
  CONFIDENCE_LABELS,
  CONFIDENCE_DOT_CLASS,
  normalizeConfidence,
  confidenceRank,
  confidenceNeedsReview,
  confidenceLabel,
  areaConfidenceSentence,
} from './confidence.js';

test('normalizeConfidence: production LT vocabulary maps to itself', () => {
  assert.equal(normalizeConfidence('zalia'), CONF_ZALIA);
  assert.equal(normalizeConfidence('geltona'), CONF_GELTONA);
  assert.equal(normalizeConfidence('raudona'), CONF_RAUDONA);
});

test('normalizeConfidence: legacy EN vocabulary maps to LT tiers', () => {
  assert.equal(normalizeConfidence('high'), CONF_ZALIA);
  assert.equal(normalizeConfidence('medium'), CONF_GELTONA);
  assert.equal(normalizeConfidence('low'), CONF_RAUDONA);
});

test('normalizeConfidence: case, whitespace and diacritics are tolerated', () => {
  assert.equal(normalizeConfidence(' Geltona '), CONF_GELTONA);
  assert.equal(normalizeConfidence('HIGH'), CONF_ZALIA);
  assert.equal(normalizeConfidence('žalia'), CONF_ZALIA);
  assert.equal(normalizeConfidence('Žalia'), CONF_ZALIA);
});

test('normalizeConfidence: unstamped rows stay zalia (legacy KŽ rows must not be flagged retroactively)', () => {
  assert.equal(normalizeConfidence(null), CONF_ZALIA);
  assert.equal(normalizeConfidence(undefined), CONF_ZALIA);
  assert.equal(normalizeConfidence(''), CONF_ZALIA);
  assert.equal(normalizeConfidence('   '), CONF_ZALIA);
});

test('normalizeConfidence: unknown non-empty vocabulary is never trusted green', () => {
  assert.equal(normalizeConfidence('labai_gerai'), CONF_GELTONA);
  assert.equal(normalizeConfidence('unknown'), CONF_GELTONA);
});

test('confidenceRank: zalia < geltona < raudona across both vocabularies', () => {
  assert.equal(confidenceRank('zalia'), 0);
  assert.equal(confidenceRank('geltona'), 1);
  assert.equal(confidenceRank('raudona'), 2);
  assert.equal(confidenceRank('high'), 0);
  assert.equal(confidenceRank('medium'), 1);
  assert.equal(confidenceRank('low'), 2);
  assert.equal(confidenceRank(null), 0);
});

test('confidenceNeedsReview: geltona/raudona in either vocabulary need review, zalia and unstamped do not', () => {
  assert.equal(confidenceNeedsReview('geltona'), true);
  assert.equal(confidenceNeedsReview('raudona'), true);
  assert.equal(confidenceNeedsReview('medium'), true);
  assert.equal(confidenceNeedsReview('low'), true);
  assert.equal(confidenceNeedsReview('zalia'), false);
  assert.equal(confidenceNeedsReview('high'), false);
  assert.equal(confidenceNeedsReview(null), false);
  assert.equal(confidenceNeedsReview(''), false);
});

test('confidenceLabel: LT labels for every tier in both vocabularies', () => {
  assert.equal(confidenceLabel('zalia'), 'Skaityta tiesiogiai');
  assert.equal(confidenceLabel('geltona'), 'Patikrinti');
  assert.equal(confidenceLabel('raudona'), 'Būtina patikrinti');
  assert.equal(confidenceLabel('high'), 'Skaityta tiesiogiai');
  assert.equal(confidenceLabel('medium'), 'Patikrinti');
  assert.equal(confidenceLabel('low'), 'Būtina patikrinti');
  assert.equal(CONFIDENCE_LABELS[CONF_ZALIA], 'Skaityta tiesiogiai');
});

test('CONFIDENCE_DOT_CLASS: tiers map onto the existing index.css dot classes', () => {
  assert.equal(CONFIDENCE_DOT_CLASS[CONF_ZALIA], 'dot-high');
  assert.equal(CONFIDENCE_DOT_CLASS[CONF_GELTONA], 'dot-med');
  assert.equal(CONFIDENCE_DOT_CLASS[CONF_RAUDONA], 'dot-low');
});

// 2026-10-18 audit §6 item 10: the room chip's tooltip read „Ploto pasitikėjimas: high".
test('areaConfidenceSentence: one Lithuanian sentence per tier, in the labels\' words, any vocabulary', () => {
  assert.equal(areaConfidenceSentence('high'), 'Plotas skaitytas tiesiogiai — tikrinti nereikia.');
  assert.equal(areaConfidenceSentence('zalia'), areaConfidenceSentence('high'));
  assert.equal(areaConfidenceSentence('medium'), 'Plotą verta patikrinti.');
  assert.equal(areaConfidenceSentence('low'), 'Plotą būtina patikrinti.');
  // areaConfidence's 'unknown' is drift-safe: never read as trusted green
  assert.equal(areaConfidenceSentence('unknown'), 'Plotą verta patikrinti.');
  for (const v of ['high', 'medium', 'low', 'unknown']) {
    assert.doesNotMatch(areaConfidenceSentence(v), /pasitikėjim|high|medium|low/i);
  }
});

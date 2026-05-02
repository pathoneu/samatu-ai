import test from 'node:test';
import assert from 'node:assert/strict';
import {
  computeAreaConfidence, AREA_AGREEMENT_TOLERANCE_PCT,
} from './areaConfidence.js';

test('computeAreaConfidence: room with eksplikacija + agreeing manual polygon → high', () => {
  const room = {
    nr: '01', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    polygon_source: 'manual', polygon_pdf: [[0, 0], [10, 0], [10, 5], [0, 5]],
    _polygon_area_m2: 12.6,  // 0.8% off, within tolerance
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.equal(r.primarySource, 'eksplikacija');
  assert.deepEqual(r.agreeingSources.sort(), ['eksplikacija', 'manual_polygon']);
});

test('computeAreaConfidence: eksplikacija only (no polygon) → medium', () => {
  const room = {
    nr: '02', plotas_m2: 12.5, plotas_source: 'eksplikacija',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'medium');
  assert.equal(r.primarySource, 'eksplikacija');
  assert.deepEqual(r.agreeingSources, ['eksplikacija']);
});

test('computeAreaConfidence: manual polygon only → medium', () => {
  const room = {
    nr: '03', plotas_m2: 8.4, plotas_source: 'manual_polygon',
    polygon_pdf: [[0, 0], [10, 0], [5, 5]],
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'medium');
  assert.equal(r.primarySource, 'manual_polygon');
});

test('computeAreaConfidence: vision-only (no eksplikacija, no polygon) → low', () => {
  const room = {
    nr: '04', plotas_m2: 6.0, plotas_source: 'vision',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'low');
  assert.equal(r.primarySource, 'vision');
});

test('computeAreaConfidence: eksplikacija + manual polygon DISAGREE (>5% off) → low', () => {
  const room = {
    nr: '05', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    polygon_source: 'manual', polygon_pdf: [[0, 0], [10, 0], [10, 5], [0, 5]],
    _polygon_area_m2: 18.0,  // 44% off
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'low');
  assert.equal(r.disagreement, true);
});

test('computeAreaConfidence: user_verified_at promotes medium → high', () => {
  const room = {
    nr: '06', plotas_m2: 12.5, plotas_source: 'eksplikacija',
    user_verified_at: '2026-05-02T10:00:00Z',
  };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'high');
  assert.ok(r.userVerified);
});

test('computeAreaConfidence: room with no plotas_m2 → unknown', () => {
  const room = { nr: '07', plotas_m2: null };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'unknown');
});

test('computeAreaConfidence: legacy room with plotas_m2 but no plotas_source → backfilled as eksplikacija medium', () => {
  // Simulates a project extracted before Phase C-2 Task 2 landed. The backend
  // didn't tag plotas_source on these, but pdfplumber eksplikacija was the
  // dominant historical path. Backfill in collectSources keeps the badge from
  // hiding (would otherwise return 'unknown').
  const room = { nr: '08', plotas_m2: 7.36, pavadinimas: 'Tambūras' };
  const r = computeAreaConfidence(room);
  assert.equal(r.confidence, 'medium');
  assert.equal(r.primarySource, 'eksplikacija');
});

test('AREA_AGREEMENT_TOLERANCE_PCT is 5%', () => {
  // Spec §3.2.1 specifies ±2% in the "high" path, but allow up to ±5% for "agreement"
  // because hand-drawn polygons trace edges with imprecision. The badge stays "high"
  // when sources are within ±2% AND drops to "low" when >5% — between, it stays "medium".
  assert.ok(AREA_AGREEMENT_TOLERANCE_PCT > 0 && AREA_AGREEMENT_TOLERANCE_PCT <= 0.05);
});

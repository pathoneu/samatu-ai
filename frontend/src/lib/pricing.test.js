import test from 'node:test';
import assert from 'node:assert/strict';
import { calcClaudeCostUSD, RATES } from './pricing.js';

test('opus: plain in/out, no cache', () => {
  // 1M in + 1M out = $5 + $25
  assert.equal(calcClaudeCostUSD({ input_tokens: 1e6, output_tokens: 1e6 }), 30);
});

test('cache reads ADD at 0.1x input rate (regression: old code subtracted at 0.9x)', () => {
  // 500k cache-read tokens on opus: +$0.25, never negative
  const cost = calcClaudeCostUSD({ cache_read_tokens: 500_000 });
  assert.ok(Math.abs(cost - 0.25) < 1e-9, `expected 0.25, got ${cost}`);
  assert.ok(cost > 0);
});

test('cache writes billed at 2x input rate for 1h TTL, 1.25x for 5m', () => {
  assert.ok(Math.abs(calcClaudeCostUSD({ cache_write_tokens: 1e6 }) - 10) < 1e-9);
  assert.ok(Math.abs(calcClaudeCostUSD({ cache_write_tokens: 1e6, cache_ttl: '5m' }) - 6.25) < 1e-9);
});

test('fable-5 is exactly 2x opus on every component', () => {
  const usage = { input_tokens: 100_000, output_tokens: 50_000, cache_read_tokens: 200_000, cache_write_tokens: 30_000 };
  const opus = calcClaudeCostUSD({ ...usage, model: 'claude-opus-4-8' });
  const fable = calcClaudeCostUSD({ ...usage, model: 'claude-fable-5' });
  assert.ok(Math.abs(fable - 2 * opus) < 1e-9);
});

test('legacy _meta (no model field) prices as opus; unknown model falls back without throwing', () => {
  assert.equal(calcClaudeCostUSD({ input_tokens: 1e6 }), RATES['claude-opus-4-8'].in);
  const orig = console.warn; let warned = false; console.warn = () => { warned = true; };
  try {
    assert.equal(calcClaudeCostUSD({ input_tokens: 1e6, model: 'claude-unknown-9' }), 5);
  } finally { console.warn = orig; }
  assert.ok(warned);
});

test('empty usage costs zero', () => {
  assert.equal(calcClaudeCostUSD({}), 0);
  assert.equal(calcClaudeCostUSD(), 0);
});

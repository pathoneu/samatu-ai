/**
 * pricing.js — Anthropic Claude API pricing, model-aware (mirrors backend/pricing.py).
 *
 * Update both files together when model pricing changes.
 * Rates (USD per MTok) verified 2026-07-03 against the claude-api reference:
 *   claude-opus-4-8: $5 in / $25 out · claude-fable-5: $10 in / $50 out
 * Cache READ = 0.1× input rate. Cache WRITE = 2× input rate (1h TTL, our
 * vision default) or 1.25× (5m TTL).
 *
 * BUG FIX (2026-07-03, mirrors backend): the old formula SUBTRACTED cache
 * reads at $4.50/MTok — but Anthropic's `input_tokens` is the uncached
 * remainder only, so cached tokens must be ADDED at 0.1×, and cache writes
 * billed at 2×. Cache-heavy calls previously displayed negative/undersized
 * costs.
 *
 * Unlike the backend (which raises on unknown models so metering never
 * silently misprices), this is display-only: legacy `_meta` without a model
 * field is priced as Opus 4.8 (all pre-2026-07 extractions were Opus), and a
 * present-but-unknown model falls back to Opus rates with a console.warn.
 */

// USD per 1M tokens.
export const RATES = {
  'claude-opus-5': { in: 5.0, out: 25.0 },   // production champion since 2026-07-28 (backend/pricing.py)
  'claude-opus-4-8': { in: 5.0, out: 25.0 },
  'claude-fable-5': { in: 10.0, out: 50.0 },
  'claude-fable-5-1': { in: 10.0, out: 50.0 },  // 2026-09-01 release; benchmarked 2026-09-02
};

const DEFAULT_MODEL = 'claude-opus-4-8';
export const CACHE_READ_MULT = 0.1;
export const CACHE_WRITE_MULT = { '1h': 2.0, '5m': 1.25 };

/**
 * Compute total USD cost for a Claude API call from a `_meta`-shaped object.
 *
 * @param {Object} usage - {input_tokens, output_tokens, cache_read_tokens?,
 *   cache_write_tokens?, model?, cache_ttl?}
 * @returns {number} USD cost (always ≥ 0)
 */
export function calcClaudeCostUSD({
  input_tokens = 0,
  output_tokens = 0,
  cache_read_tokens = 0,
  cache_write_tokens = 0,
  model = DEFAULT_MODEL,
  cache_ttl = '1h',
} = {}) {
  let rates = RATES[model];
  if (!rates) {
    console.warn(`pricing.js: unknown model "${model}" — displaying at Opus 4.8 rates`);
    rates = RATES[DEFAULT_MODEL];
  }
  const writeMult = CACHE_WRITE_MULT[cache_ttl] ?? CACHE_WRITE_MULT['1h'];
  const perTokIn = rates.in / 1e6;
  const perTokOut = rates.out / 1e6;
  return (
    input_tokens * perTokIn
    + output_tokens * perTokOut
    + cache_read_tokens * perTokIn * CACHE_READ_MULT
    + cache_write_tokens * perTokIn * writeMult
  );
}

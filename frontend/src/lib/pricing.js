/**
 * pricing.js — Anthropic Claude API pricing constants (Sprint §AUDIT, 2026-04-29).
 *
 * Single source of truth for cost calculation across frontend.
 * Backend mirror: backend/pricing.py.
 *
 * Update both files together when model pricing changes.
 *
 * Source: https://docs.claude.com/en/docs/about-claude/pricing
 * Last verified: 2026-04 — Claude Opus 4.x pricing
 */

// USD per token. Multiply by token count for total USD cost.
export const CLAUDE_OPUS_INPUT_PER_TOKEN  = 5e-6;     // $5  / 1M tokens
export const CLAUDE_OPUS_OUTPUT_PER_TOKEN = 25e-6;    // $25 / 1M tokens
export const CLAUDE_OPUS_CACHE_DISCOUNT_PER_TOKEN = 4.5e-6;  // 90% off cached input

/**
 * Compute total USD cost for a Claude API call.
 *
 * @param {Object} usage - {input_tokens, output_tokens, cache_read_tokens?}
 * @returns {number} USD cost (positive)
 */
export function calcClaudeCostUSD({ input_tokens = 0, output_tokens = 0, cache_read_tokens = 0 } = {}) {
  return (
    input_tokens * CLAUDE_OPUS_INPUT_PER_TOKEN
    + output_tokens * CLAUDE_OPUS_OUTPUT_PER_TOKEN
    - cache_read_tokens * CLAUDE_OPUS_CACHE_DISCOUNT_PER_TOKEN
  );
}

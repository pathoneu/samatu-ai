"""Anthropic Claude API pricing — model-aware cost calculation (W1.1, 2026-07-03).

Single source of truth for cost calculation across backend.
Frontend mirror: frontend/src/lib/pricing.js (still Opus-only as of
2026-07-03 — update it when the model flip lands).

Rates (USD per MTok) from the claude-api reference, verified 2026-07-03:
  claude-opus-4-8:  $5 in / $25 out
  claude-fable-5:   $10 in / $50 out
Cache READ  = 0.1× the model's input rate.
Cache WRITE = 2.0× input rate for 1-hour TTL, 1.25× for 5-minute TTL.
(Our vision path uses explicit ``ttl: "1h"`` — see vision_call_v2.py.)

BUG FIX (2026-07-03): the previous formula charged cache reads at
MINUS $4.50/MTok (it subtracted a "discount" from an input total that never
included the cached tokens — Anthropic's ``usage.input_tokens`` is the
UNCACHED remainder only) and billed cache writes at $0. Correct is
+$0.50/MTok for reads (0.1×) and +$10/MTok for 1h-TTL writes (2×). Every
cache-heavy extraction was under-metered by $5/MTok-read + $10/MTok-written;
a big cached call could even record a negative cost.

Unknown model → ValueError. Never silently price a model we have no rate
for — add the rate here instead.
"""

# USD per 1M tokens.
RATES: dict[str, dict[str, float]] = {
    "claude-opus-4-8": {"in": 5.0, "out": 25.0},
    "claude-fable-5": {"in": 10.0, "out": 50.0},
}

CACHE_READ_MULT = 0.1                       # × input rate
CACHE_WRITE_MULT = {"1h": 2.0, "5m": 1.25}  # × input rate, by TTL


def calc_claude_cost_usd(
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    model: str = "claude-opus-4-8",
    cache_ttl: str = "1h",
) -> float:
    """Compute total USD cost for a Claude API call.

    Args:
        input_tokens: ``usage.input_tokens`` — the UNCACHED remainder only
            (cache reads/writes are reported separately by the API).
        output_tokens: ``usage.output_tokens``.
        cache_read_tokens: ``usage.cache_read_input_tokens`` (0.1× in-rate).
        cache_write_tokens: ``usage.cache_creation_input_tokens``
            (2× in-rate for "1h" TTL, 1.25× for "5m").
        model: exact model ID; must exist in RATES.
        cache_ttl: "1h" (our vision default) or "5m".

    Raises:
        ValueError: unknown model or cache_ttl — never silently price wrong.
    """
    rates = RATES.get(model)
    if rates is None:
        raise ValueError(
            f"no pricing rate for model {model!r} — add it to pricing.RATES "
            f"(known: {', '.join(sorted(RATES))})"
        )
    if cache_ttl not in CACHE_WRITE_MULT:
        raise ValueError(
            f"unknown cache_ttl {cache_ttl!r} (known: "
            f"{', '.join(sorted(CACHE_WRITE_MULT))})"
        )
    in_rate = rates["in"] / 1_000_000
    out_rate = rates["out"] / 1_000_000
    return (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_read_tokens * in_rate * CACHE_READ_MULT
        + cache_write_tokens * in_rate * CACHE_WRITE_MULT[cache_ttl]
    )

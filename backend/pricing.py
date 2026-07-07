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


def _calc_extra_calls_cost_usd(meta: dict, cache_ttl: str) -> float:
    """Price ``meta["extra_calls"]`` — the sub-Vision calls the extraction
    pipeline makes beyond Pass-1 (eksplikacija Vision fallback, apdailos,
    doors, door_type ×N voted rounds, zoom fixed-crop, agentic zoom, sanitary
    fixtures). Each entry is ``{model, input_tokens, output_tokens,
    cache_read_tokens, cache_write_tokens}`` and is priced at ITS OWN model's
    rate (sub-readers each resolve their own model_for(...), so a call may run
    on a DIFFERENT model than Pass-1).

    An extra_call with no ``model`` key is a capture bug, not a free call —
    raise (via calc_claude_cost_usd's unknown-model guard) rather than
    silently pricing at the default and undercounting again.
    """
    total = 0.0
    for c in (meta.get("extra_calls") or []):
        total += calc_claude_cost_usd(
            input_tokens=int(c.get("input_tokens") or 0),
            output_tokens=int(c.get("output_tokens") or 0),
            cache_read_tokens=int(c.get("cache_read_tokens") or 0),
            cache_write_tokens=int(c.get("cache_write_tokens") or 0),
            model=c.get("model") or "",  # "" → ValueError (never silent)
            cache_ttl=cache_ttl,
        )
    return total


def calc_meta_cost_usd(
    meta: dict,
    default_model: str = "claude-opus-4-8",
    cache_ttl: str = "1h",
) -> float:
    """Price a pipeline ``_meta`` block, mixed-model-voting + sub-call aware.

    Mixed-model voting runs (env ``SAMATU_VOTING_MODELS``, 2026-07-04
    experiment #7) carry a per-round token/model split in
    ``meta["voting_models"]`` — the top-level token sums span rounds on
    DIFFERENT models, so pricing them at ``meta["model"]`` (the first
    round's model) would be wrong. Here each round is priced at ITS OWN
    model's rates and summed.

    Single-model metas (no ``voting_models`` key) price the top-level token
    sums at ``meta["model"]`` — byte-identical to the previous behaviour of
    every call site.

    On TOP of the main/voting cost, the cost of every sub-Vision call captured
    in ``meta["extra_calls"]`` is added (2026-07-04 sub-call metering fix) —
    each at its own model's rate. Absent/empty → adds nothing (regression-safe:
    metas that predate the fix price identically).

    Raises ValueError on an unknown model rate — in the main sums, a voting
    round, OR an extra_call — same as calc_claude_cost_usd; never silently
    price wrong.
    """
    extra = _calc_extra_calls_cost_usd(meta, cache_ttl)

    rounds = [r for r in (meta.get("voting_models") or [])
              if r.get("model") and not r.get("error")]
    if rounds:
        return extra + sum(
            calc_claude_cost_usd(
                input_tokens=int(r.get("input_tokens") or 0),
                output_tokens=int(r.get("output_tokens") or 0),
                cache_read_tokens=int(r.get("cache_read_tokens") or 0),
                cache_write_tokens=int(r.get("cache_write_tokens") or 0),
                model=r["model"],
                cache_ttl=cache_ttl,
            )
            for r in rounds
        )
    return extra + calc_claude_cost_usd(
        input_tokens=int(meta.get("input_tokens") or 0),
        output_tokens=int(meta.get("output_tokens") or 0),
        cache_read_tokens=int(meta.get("cache_read_tokens") or 0),
        cache_write_tokens=int(meta.get("cache_write_tokens") or 0),
        model=meta.get("model") or default_model,
        cache_ttl=cache_ttl,
    )


# EUR conversion factor — kept in sync with db.py's record_usage / save_extraction
# (both apply this same fixed rate). Single knob for the whole cost stack.
USD_TO_EUR = 0.93


def true_cost_eur_per_project(meta: dict) -> float:
    """True €/project given COMPLETE metering.

    Feed a project's extraction ``_meta`` that carries BOTH the Pass-1 (or
    voting) token sums AND the ``extra_calls`` list of every sub-Vision call
    (2026-07-04 sub-call metering fix). Returns the full USD cost converted to
    EUR — the per-project number the pricing analysis consumes.

    ── OFFLINE RECOVERABILITY (verified 2026-07-04 against eval_runs artifacts) ──
    Existing ``eval_runs/<config>/<run>_vision/{results.json,parsed.json}``
    artifacts DROPPED the sub-call token data: ``_meta`` (aka results.json's
    ``meta_rollup.raw_meta``) carries only the Pass-1/voting token sums plus
    sub-reader ELAPSED times + counts — no ``extra_calls``, no apdailos/doors/
    door_type/fixtures tokens, and the per-room ``_zoom`` dicts hold the
    ZoomResult schema but NO usage (resp.usage was discarded). The stored
    ``cost_usd``/``cost_eur`` were therefore computed from Pass-1 alone — the
    exact 34-76% undercount this fix addresses.

    => True €/project is NOT recoverable offline from the historical artifacts.
       A FRESH instrumented run (this code path, which now populates
       ``extra_calls``) is the only way to obtain true per-project cost.
       The elapsed-time proxies in the old artifacts can bound the MAGNITUDE of
       the historical undercount, but not its exact euros.
    """
    return calc_meta_cost_usd(meta) * USD_TO_EUR

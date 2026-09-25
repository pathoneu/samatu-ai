"""pricing.calc_claude_cost_usd — model-aware math (W1.1, 2026-07-03).

Locks in the cache-read bug fix: reads bill at +0.1× the input rate (the old
formula SUBTRACTED 0.9× — cache-heavy calls under-metered, even negative),
and cache writes bill at 2× (1h TTL) / 1.25× (5m TTL).
"""
import pytest

from pricing import RATES, calc_claude_cost_usd

MTOK = 1_000_000


def test_opus_plain_input_output():
    # 1M in + 1M out on Opus 4.8 = $5 + $25
    assert calc_claude_cost_usd(MTOK, MTOK, model="claude-opus-4-8") == pytest.approx(30.0)


def test_fable_plain_input_output():
    # 1M in + 1M out on Fable 5 = $10 + $50
    assert calc_claude_cost_usd(MTOK, MTOK, model="claude-fable-5") == pytest.approx(60.0)


def test_cache_read_is_one_tenth_input_rate():
    # 1M cache-read tokens on Opus = $0.50; on Fable = $1.00
    assert calc_claude_cost_usd(cache_read_tokens=MTOK,
                                model="claude-opus-4-8") == pytest.approx(0.50)
    assert calc_claude_cost_usd(cache_read_tokens=MTOK,
                                model="claude-fable-5") == pytest.approx(1.00)


def test_cache_read_never_reduces_cost():
    """Regression for the pre-2026-07-03 bug: cache reads must ADD cost,
    never subtract it (the old formula could produce negative totals)."""
    base = calc_claude_cost_usd(10_000, 1_000)
    with_cache = calc_claude_cost_usd(10_000, 1_000, cache_read_tokens=500_000)
    assert with_cache > base > 0


def test_cache_write_1h_ttl_is_2x_input_rate():
    # 1M cache-write tokens, 1h TTL: Opus $10; Fable $20
    assert calc_claude_cost_usd(cache_write_tokens=MTOK, model="claude-opus-4-8",
                                cache_ttl="1h") == pytest.approx(10.0)
    assert calc_claude_cost_usd(cache_write_tokens=MTOK, model="claude-fable-5",
                                cache_ttl="1h") == pytest.approx(20.0)


def test_cache_write_5m_ttl_is_1_25x_input_rate():
    assert calc_claude_cost_usd(cache_write_tokens=MTOK, model="claude-opus-4-8",
                                cache_ttl="5m") == pytest.approx(6.25)


def test_combined_realistic_extraction_opus():
    # 50k uncached in, 8k out, 200k cache read, 30k cache written (1h)
    expected = (
        50_000 * 5 / MTOK
        + 8_000 * 25 / MTOK
        + 200_000 * 5 * 0.1 / MTOK
        + 30_000 * 5 * 2.0 / MTOK
    )
    got = calc_claude_cost_usd(50_000, 8_000, 200_000, 30_000,
                               model="claude-opus-4-8", cache_ttl="1h")
    assert got == pytest.approx(expected)


def test_unknown_model_raises_value_error():
    with pytest.raises(ValueError, match="no pricing rate"):
        calc_claude_cost_usd(1000, 100, model="claude-haiku-4-5")


def test_unknown_ttl_raises_value_error():
    with pytest.raises(ValueError, match="cache_ttl"):
        calc_claude_cost_usd(1000, 100, cache_ttl="2h")


def test_default_model_is_opus_48():
    assert calc_claude_cost_usd(MTOK) == pytest.approx(5.0)


def test_rates_table_shape():
    assert RATES["claude-opus-4-8"] == {"in": 5.0, "out": 25.0}
    assert RATES["claude-fable-5"] == {"in": 10.0, "out": 50.0}


def test_per_model_cache_read_rates_2026_09_25():
    """Fable 5.1 bills cache reads at 0.025× ($0.25/MTok), Opus 5.5 at 0.05× ($0.20/MTok); every other
    model at the standard 0.1×. Opus 5.5 is $4 / $20 (live pricing page, 2026-09-25)."""
    assert calc_claude_cost_usd(cache_read_tokens=MTOK, model="claude-fable-5-1") == pytest.approx(0.25)
    assert calc_claude_cost_usd(cache_read_tokens=MTOK, model="claude-opus-5-5") == pytest.approx(0.20)
    assert calc_claude_cost_usd(MTOK, MTOK, model="claude-opus-5-5") == pytest.approx(24.0)
    assert calc_claude_cost_usd(cache_read_tokens=MTOK, model="claude-opus-5") == pytest.approx(0.50)
    assert calc_claude_cost_usd(MTOK, MTOK, model="claude-sonnet-5") == pytest.approx(12.0)

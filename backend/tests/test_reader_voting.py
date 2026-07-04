"""Self-consistency voting for the single-pass readers (door_type + sanitary).

Mode aggregation (median tiebreak) — NOT max, which would covertly drift counts
up toward the AI-parsed oracle. Spread is recorded so the caller flags geltona."""
from extractor.door_type_reader import _mode_int, _aggregate_door_votes
from extractor.sanitary_fixture_reader import _aggregate_fixture_votes


def test_mode_ignores_a_single_outlier():
    # The exact (2,2,7) door swing the variance runs showed → mode picks 2.
    assert _mode_int([2, 2, 7]) == 2
    assert _mode_int([3, 3, 7]) == 3
    assert _mode_int([7, 2, 2]) == 2  # order-independent


def test_mode_median_tiebreak_not_max():
    # All distinct → no mode → median, never max.
    assert _mode_int([2, 5, 8]) == 5
    assert _mode_int([2, 4]) == 3  # 2-way tie → median (rounds)
    assert _mode_int([10, 2]) != 10  # explicitly NOT max


def test_aggregate_door_votes_picks_mode_and_records_spread():
    runs = [
        {"status": "ok", "beapvadines_count": 7, "standartines_count": 3, "stumdomos_count": 1, "bendras_tipas": "x"},
        {"status": "ok", "beapvadines_count": 2, "standartines_count": 3, "stumdomos_count": 1},
        {"status": "ok", "beapvadines_count": 2, "standartines_count": 3, "stumdomos_count": 1},
    ]
    out = _aggregate_door_votes(runs)
    assert out["beapvadines_count"] == 2          # mode, not the 7 outlier, not max
    assert out["standartines_count"] == 3
    assert out["_vote"]["spread"] == 5            # 7-2 disagreement surfaced
    assert out["_vote"]["beapvadines_values"] == [7, 2, 2]


def test_aggregate_door_votes_all_failed_returns_first():
    runs = [{"status": "error", "beapvadines_count": 0, "_error": "boom"}]
    assert _aggregate_door_votes(runs)["status"] == "error"


def test_aggregate_fixture_votes_modes_each_key():
    runs = [
        {"status": "ok", "counts": {"praustuves": 4, "klozetai": 2, "vonios": 1, "dusai": 1, "wc_remai": 2}},
        {"status": "ok", "counts": {"praustuves": 3, "klozetai": 2, "vonios": 1, "dusai": 1, "wc_remai": 2}},
        {"status": "ok", "counts": {"praustuves": 4, "klozetai": 2, "vonios": 1, "dusai": 1, "wc_remai": 2}},
    ]
    out = _aggregate_fixture_votes(runs)
    assert out["counts"]["praustuves"] == 4       # mode of (4,3,4)
    assert out["counts"]["klozetai"] == 2
    assert out["_vote"]["spread"]["praustuves"] == 1


# ── Per-round token roll-up for cost metering (2026-07-04) ─────────────────────
# Voted readers make N Anthropic calls but returned only the representative
# round's _meta — the other rounds' tokens were dropped, undercounting cost.
# The aggregators now expose EVERY OK round's _meta under _round_metas so the
# extraction flow can append each into _meta.extra_calls (priced per-model).

def test_aggregate_door_votes_exposes_every_round_meta():
    runs = [
        {"status": "ok", "beapvadines_count": 2,
         "_meta": {"model": "claude-opus-4-8", "input_tokens": 5000, "output_tokens": 300}},
        {"status": "ok", "beapvadines_count": 2,
         "_meta": {"model": "claude-opus-4-8", "input_tokens": 5100, "output_tokens": 310}},
        {"status": "ok", "beapvadines_count": 7,
         "_meta": {"model": "claude-opus-4-8", "input_tokens": 4900, "output_tokens": 290}},
    ]
    out = _aggregate_door_votes(runs)
    assert len(out["_round_metas"]) == 3          # ALL 3 calls, not just the rep
    assert [m["input_tokens"] for m in out["_round_metas"]] == [5000, 5100, 4900]


def test_aggregate_door_votes_round_metas_excludes_failed_rounds():
    runs = [
        {"status": "ok", "beapvadines_count": 2,
         "_meta": {"model": "claude-opus-4-8", "input_tokens": 5000, "output_tokens": 300}},
        {"status": "error", "beapvadines_count": 0, "_error": "boom"},  # no API tokens billed
    ]
    out = _aggregate_door_votes(runs)
    assert len(out["_round_metas"]) == 1


def test_aggregate_fixture_votes_exposes_every_round_meta():
    runs = [
        {"status": "ok", "counts": {"praustuves": 4, "klozetai": 2, "vonios": 1, "dusai": 1, "wc_remai": 2},
         "_meta": {"model": "claude-opus-4-8", "input_tokens": 6000, "output_tokens": 200}},
        {"status": "ok", "counts": {"praustuves": 3, "klozetai": 2, "vonios": 1, "dusai": 1, "wc_remai": 2},
         "_meta": {"model": "claude-opus-4-8", "input_tokens": 6100, "output_tokens": 210}},
    ]
    out = _aggregate_fixture_votes(runs)
    assert len(out["_round_metas"]) == 2
    assert [m["input_tokens"] for m in out["_round_metas"]] == [6000, 6100]

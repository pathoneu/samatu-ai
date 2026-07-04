"""Sub-call cost roll-up — complete per-extraction metering (2026-07-04).

The extraction pipeline makes MANY Anthropic calls beyond Pass-1 (eksplikacija
Vision fallback, apdailos, doors, door_type ×N voted rounds, zoom fixed-crop,
agentic zoom, sanitary fixtures). Their tokens used to be dropped — only Pass-1
was priced — so per-user/per-project cost (and the hard spend cap) undercounted
true spend by 34-76%.

Design mirrors the existing `voting_models` mechanism: ONE usage_event per
extraction, but its cost is complete. `calc_meta_cost_usd` now also prices an
optional `meta["extra_calls"]` list — each entry at ITS OWN model's rate — and
sums it on top of the main/voting cost. Sub-readers may use DIFFERENT models
than Pass-1 (each resolves its own model_for(...)), so a naive single-model
token sum would misprice.
"""
import pytest

import db
from pricing import calc_claude_cost_usd, calc_meta_cost_usd

MTOK = 1_000_000


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "rollup.db")
    db.init_schema()


# ── extra_calls: additive, per-model-correct ──────────────────────────────────

def test_extra_calls_absent_is_unchanged():
    """Regression guard: a meta WITHOUT extra_calls prices exactly as before."""
    meta = {"input_tokens": 50_000, "output_tokens": 8_000,
            "cache_read_tokens": 200_000, "cache_write_tokens": 30_000,
            "model": "claude-opus-4-8"}
    got = calc_meta_cost_usd(meta)
    expected = calc_claude_cost_usd(50_000, 8_000, 200_000, 30_000,
                                    model="claude-opus-4-8")
    assert got == pytest.approx(expected)


def test_extra_calls_empty_list_is_unchanged():
    meta = {"input_tokens": 50_000, "output_tokens": 8_000,
            "model": "claude-opus-4-8", "extra_calls": []}
    got = calc_meta_cost_usd(meta)
    expected = calc_claude_cost_usd(50_000, 8_000, model="claude-opus-4-8")
    assert got == pytest.approx(expected)


def test_extra_calls_added_on_top_of_single_model_main():
    """Pass-1 Opus + one Apdailos Opus sub-call = sum of both, priced per-call."""
    meta = {
        "input_tokens": 40_000, "output_tokens": 6_000,
        "cache_read_tokens": 100_000, "cache_write_tokens": 20_000,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 12_000,
             "output_tokens": 900, "cache_read_tokens": 5_000,
             "cache_write_tokens": 0},
        ],
    }
    main_cost = calc_claude_cost_usd(40_000, 6_000, 100_000, 20_000,
                                     model="claude-opus-4-8")
    extra_cost = calc_claude_cost_usd(12_000, 900, 5_000, 0,
                                      model="claude-opus-4-8")
    assert calc_meta_cost_usd(meta) == pytest.approx(main_cost + extra_cost)


def test_extra_calls_mixed_models_each_at_own_rate():
    """Pass-1 Opus + an Apdailos Opus call + a Fable door-type round.
    Each extra_call is priced at ITS OWN model's rate, not the main model's."""
    meta = {
        "input_tokens": 40_000, "output_tokens": 6_000,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 10_000,
             "output_tokens": 500},
            {"model": "claude-fable-5", "input_tokens": 8_000,
             "output_tokens": 400, "cache_read_tokens": 2_000},
        ],
    }
    main_cost = calc_claude_cost_usd(40_000, 6_000, model="claude-opus-4-8")
    apdailos = calc_claude_cost_usd(10_000, 500, model="claude-opus-4-8")
    door_fable = calc_claude_cost_usd(8_000, 400, cache_read_tokens=2_000,
                                      model="claude-fable-5")
    assert calc_meta_cost_usd(meta) == pytest.approx(
        main_cost + apdailos + door_fable)


def test_extra_calls_added_on_top_of_voting_main():
    """extra_calls stack on top of a mixed-model VOTING main cost, not instead."""
    meta = {
        "model": "claude-opus-4-8",
        "voting_models": [
            {"model": "claude-opus-4-8", "input_tokens": 30_000,
             "output_tokens": 4_000},
            {"model": "claude-fable-5", "input_tokens": 28_000,
             "output_tokens": 3_800},
        ],
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 9_000,
             "output_tokens": 600},
        ],
    }
    vote = (calc_claude_cost_usd(30_000, 4_000, model="claude-opus-4-8")
            + calc_claude_cost_usd(28_000, 3_800, model="claude-fable-5"))
    extra = calc_claude_cost_usd(9_000, 600, model="claude-opus-4-8")
    assert calc_meta_cost_usd(meta) == pytest.approx(vote + extra)


def test_extra_call_unknown_model_raises():
    """An unknown model in an extra_call must RAISE — never silently mis-price,
    consistent with calc_claude_cost_usd / the voting path."""
    meta = {
        "input_tokens": 10_000, "output_tokens": 500,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-haiku-4-5", "input_tokens": 5_000,
             "output_tokens": 200},
        ],
    }
    with pytest.raises(ValueError, match="no pricing rate"):
        calc_meta_cost_usd(meta)


def test_extra_call_missing_tokens_default_to_zero():
    """Partial token fields default to 0 (best-effort capture); a bare {model}
    extra_call adds nothing."""
    meta = {"input_tokens": 10_000, "output_tokens": 500,
            "model": "claude-opus-4-8",
            "extra_calls": [{"model": "claude-opus-4-8"}]}
    expected = calc_claude_cost_usd(10_000, 500, model="claude-opus-4-8")
    assert calc_meta_cost_usd(meta) == pytest.approx(expected)


def test_extra_call_without_model_key_raises():
    """An extra_call MUST name its model — a missing model key is a capture bug,
    not a free call. Raise rather than silently pricing at the default."""
    meta = {"input_tokens": 10_000, "output_tokens": 500,
            "model": "claude-opus-4-8",
            "extra_calls": [{"input_tokens": 5_000, "output_tokens": 200}]}
    with pytest.raises(ValueError):
        calc_meta_cost_usd(meta)


# ── record_usage stores the FULL summed cost, not just Pass-1 ──────────────────

def test_record_usage_includes_extra_calls_cost(tmp_path, monkeypatch):
    """record_usage on a response whose _meta.extra_calls is populated must
    ledger the FULL summed cost (×0.93 EUR), not just the Pass-1 tokens."""
    _isolate(tmp_path, monkeypatch)
    meta = {
        "input_tokens": 40_000, "output_tokens": 6_000,
        "model": "claude-opus-4-8",
        "extra_calls": [
            {"model": "claude-opus-4-8", "input_tokens": 20_000,
             "output_tokens": 1_500},
            {"model": "claude-fable-5", "input_tokens": 8_000,
             "output_tokens": 400},
        ],
    }
    cost = db.record_usage("u1", {"_meta": meta}, "extract-interior")
    expected_usd = calc_meta_cost_usd(meta)
    assert cost == pytest.approx(expected_usd * 0.93)
    total, n = db.user_usage_since("u1", hours=24)
    assert n == 1
    assert total == pytest.approx(round(expected_usd * 0.93, 4))


def test_record_usage_extra_calls_strictly_greater_than_pass1_only(tmp_path, monkeypatch):
    """The whole point of the fix: a response with sub-calls must ledger MORE
    than the same response with Pass-1 tokens alone (the old undercount)."""
    _isolate(tmp_path, monkeypatch)
    base_meta = {"input_tokens": 40_000, "output_tokens": 6_000,
                 "model": "claude-opus-4-8"}
    full_meta = {**base_meta, "extra_calls": [
        {"model": "claude-opus-4-8", "input_tokens": 25_000, "output_tokens": 2_000},
        {"model": "claude-opus-4-8", "input_tokens": 25_000, "output_tokens": 2_000},
    ]}
    pass1_only = db.record_usage("u1", {"_meta": dict(base_meta)}, "extract-interior")
    with_subs = db.record_usage("u2", {"_meta": full_meta}, "extract-interior")
    assert with_subs > pass1_only > 0


# ── _append_extra_call helper — the single merge point for every sub-reader ────

def test_append_extra_call_records_model_and_tokens():
    from extractor.vision_call import _append_extra_call
    parsed = {"_meta": {"input_tokens": 100, "model": "claude-opus-4-8"}}
    _append_extra_call(parsed, {"input_tokens": 5_000, "output_tokens": 300,
                                "cache_read_tokens": 1_000,
                                "cache_write_tokens": 200,
                                "model": "claude-opus-4-8"})
    ec = parsed["_meta"]["extra_calls"]
    assert ec == [{"model": "claude-opus-4-8", "input_tokens": 5_000,
                   "output_tokens": 300, "cache_read_tokens": 1_000,
                   "cache_write_tokens": 200}]


def test_append_extra_call_creates_list_and_appends_multiple():
    from extractor.vision_call import _append_extra_call
    parsed = {"_meta": {}}
    _append_extra_call(parsed, {"input_tokens": 1_000, "output_tokens": 100,
                                "model": "claude-opus-4-8"})
    _append_extra_call(parsed, {"input_tokens": 2_000, "output_tokens": 200,
                                "model": "claude-fable-5"})
    assert len(parsed["_meta"]["extra_calls"]) == 2
    assert [c["model"] for c in parsed["_meta"]["extra_calls"]] == [
        "claude-opus-4-8", "claude-fable-5"]


def test_append_extra_call_skips_pdfplumber_meta_without_model():
    """The pdfplumber eksplikacija path returns _meta with source=pdfplumber_table
    and NO model / tokens (cost $0). It must NOT be appended (an entry without a
    model would later RAISE in pricing)."""
    from extractor.vision_call import _append_extra_call
    parsed = {"_meta": {}}
    _append_extra_call(parsed, {"source": "pdfplumber_table", "elapsed_s": 0.4,
                                "pages_scanned": 12})
    assert parsed["_meta"].get("extra_calls") in (None, [])


def test_append_extra_call_skips_zero_token_meta():
    """A reader that errored before the API call returns an empty/zero _meta —
    nothing billable, don't append."""
    from extractor.vision_call import _append_extra_call
    parsed = {"_meta": {}}
    _append_extra_call(parsed, {})
    _append_extra_call(parsed, {"model": "claude-opus-4-8", "input_tokens": 0,
                                "output_tokens": 0})
    assert parsed["_meta"].get("extra_calls") in (None, [])


def test_append_extra_call_handles_none_token_values():
    """Reader _meta uses getattr(usage, ..., None) → None token values must be
    coerced to 0, not crash and not skip a real call (output_tokens present)."""
    from extractor.vision_call import _append_extra_call
    parsed = {"_meta": {}}
    _append_extra_call(parsed, {"model": "claude-opus-4-8",
                                "input_tokens": None, "output_tokens": 300})
    ec = parsed["_meta"]["extra_calls"]
    assert ec == [{"model": "claude-opus-4-8", "input_tokens": 0,
                   "output_tokens": 300, "cache_read_tokens": 0,
                   "cache_write_tokens": 0}]


def test_append_extra_call_priced_end_to_end():
    """A parsed built only via _append_extra_call prices as the sum of Pass-1 +
    each appended sub-call — the full production path in miniature."""
    from extractor.vision_call import _append_extra_call
    parsed = {"_meta": {"input_tokens": 40_000, "output_tokens": 6_000,
                        "model": "claude-opus-4-8"}}
    _append_extra_call(parsed, {"model": "claude-opus-4-8",
                                "input_tokens": 10_000, "output_tokens": 800})
    _append_extra_call(parsed, {"model": "claude-fable-5",
                                "input_tokens": 8_000, "output_tokens": 400})
    got = calc_meta_cost_usd(parsed["_meta"])
    expected = (calc_claude_cost_usd(40_000, 6_000, model="claude-opus-4-8")
                + calc_claude_cost_usd(10_000, 800, model="claude-opus-4-8")
                + calc_claude_cost_usd(8_000, 400, model="claude-fable-5"))
    assert got == pytest.approx(expected)


# ── zoom fixed-crop returns its token meta (was discarded entirely) ────────────

class _FakeUsage:
    def __init__(self, i, o, cr=0, cw=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = cr
        self.cache_creation_input_tokens = cw


class _FakeBlock:
    type = "text"
    def __init__(self, text):
        self.text = text


class _FakeResp:
    def __init__(self, text, usage, stop_reason="end_turn"):
        self.content = [_FakeBlock(text)]
        self.usage = usage
        self.stop_reason = stop_reason


class _FakeStreamCtx:
    def __init__(self, resp):
        self._resp = resp
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def get_final_message(self):
        return self._resp


class _FakeMessages:
    def __init__(self, resp):
        self._resp = resp
    def stream(self, **kwargs):
        return _FakeStreamCtx(self._resp)


class _FakeClient:
    def __init__(self, resp):
        self.messages = _FakeMessages(resp)


def test_vision_zoom_room_returns_result_and_token_meta():
    """_vision_zoom_room must ALSO return the call's token meta (model +
    input/output/cache) — it used to drop resp.usage entirely, so every zoom
    call was unmetered. Output zoom dict itself is unchanged (no _meta key)."""
    from extractor import vision_call
    import json as _json
    zoom_json = {"confidence_zoom": "high", "perimetras_m": 12.3}
    resp = _FakeResp(_json.dumps(zoom_json), _FakeUsage(3000, 250, cr=1000))
    client = _FakeClient(resp)
    result, zmeta = vision_call._vision_zoom_room(client, "b64crop", {"nr": "1"})
    assert result == zoom_json                       # zoom output unchanged
    assert zmeta["input_tokens"] == 3000
    assert zmeta["output_tokens"] == 250
    assert zmeta["cache_read_tokens"] == 1000
    assert zmeta["model"]                            # resolved model id present


def test_vision_zoom_room_none_result_still_returns_meta_shape():
    """A refusal/parse-fail returns (None, meta) — the tuple contract holds so
    the caller never unpacks a bare None."""
    from extractor import vision_call
    resp = _FakeResp("not json", _FakeUsage(3000, 250), stop_reason="end_turn")
    client = _FakeClient(resp)
    result, zmeta = vision_call._vision_zoom_room(client, "b64crop", {"nr": "1"})
    assert result is None
    assert "model" in zmeta  # meta still returned so tokens for the failed-parse call are captured


# ── _reader_call_metas: normalize voted (_round_metas) vs single-pass (_meta) ──

def test_reader_call_metas_voted_returns_every_round():
    from extractor.vision_call import _reader_call_metas
    result = {"status": "ok", "_round_metas": [
        {"model": "claude-opus-4-8", "input_tokens": 5000},
        {"model": "claude-opus-4-8", "input_tokens": 5100},
        {"model": "claude-opus-4-8", "input_tokens": 4900},
    ]}
    metas = _reader_call_metas(result)
    assert [m["input_tokens"] for m in metas] == [5000, 5100, 4900]


def test_reader_call_metas_single_pass_returns_one():
    from extractor.vision_call import _reader_call_metas
    result = {"status": "ok",
              "_meta": {"model": "claude-opus-4-8", "input_tokens": 5000}}
    metas = _reader_call_metas(result)
    assert len(metas) == 1
    assert metas[0]["input_tokens"] == 5000


def test_reader_call_metas_errored_reader_returns_empty():
    from extractor.vision_call import _reader_call_metas
    assert _reader_call_metas({"status": "error", "_error": "boom"}) == []
    assert _reader_call_metas({}) == []


def test_flow_appends_each_reader_meta_into_extra_calls():
    """Simulate the extraction merge points: append apdailos + doors +
    (voted) door_type rounds + fixtures into ONE parsed._meta.extra_calls,
    then price the whole thing. Proves each sub-reader's tokens are captured
    exactly once and summed per-model on top of Pass-1."""
    from extractor.vision_call import _append_extra_call, _reader_call_metas
    parsed = {"_meta": {"input_tokens": 40_000, "output_tokens": 6_000,
                        "model": "claude-opus-4-8"}}
    apdailos = {"status": "ok",
                "_meta": {"model": "claude-opus-4-8", "input_tokens": 12_000, "output_tokens": 900}}
    doors = {"status": "ok",
             "_meta": {"model": "claude-opus-4-8", "input_tokens": 9_000, "output_tokens": 700}}
    door_type_voted = {"status": "ok", "_round_metas": [
        {"model": "claude-opus-4-8", "input_tokens": 6_000, "output_tokens": 300},
        {"model": "claude-opus-4-8", "input_tokens": 6_100, "output_tokens": 310},
        {"model": "claude-opus-4-8", "input_tokens": 5_900, "output_tokens": 290},
    ]}
    fixtures = {"status": "ok",
                "_meta": {"model": "claude-fable-5", "input_tokens": 7_000, "output_tokens": 250}}

    _append_extra_call(parsed, apdailos.get("_meta"))
    _append_extra_call(parsed, doors.get("_meta"))
    for m in _reader_call_metas(door_type_voted):
        _append_extra_call(parsed, m)
    for m in _reader_call_metas(fixtures):
        _append_extra_call(parsed, m)

    assert len(parsed["_meta"]["extra_calls"]) == 1 + 1 + 3 + 1  # apdailos, doors, 3 door rounds, fixtures
    total = calc_meta_cost_usd(parsed["_meta"])
    expected = (
        calc_claude_cost_usd(40_000, 6_000, model="claude-opus-4-8")  # Pass-1
        + calc_claude_cost_usd(12_000, 900, model="claude-opus-4-8")   # apdailos
        + calc_claude_cost_usd(9_000, 700, model="claude-opus-4-8")    # doors
        + calc_claude_cost_usd(6_000, 300, model="claude-opus-4-8")    # door round 1
        + calc_claude_cost_usd(6_100, 310, model="claude-opus-4-8")    # door round 2
        + calc_claude_cost_usd(5_900, 290, model="claude-opus-4-8")    # door round 3
        + calc_claude_cost_usd(7_000, 250, model="claude-fable-5")     # fixtures (Fable)
    )
    assert total == pytest.approx(expected)


# ── Chat metering: its own usage_event, NOT counted as an extract ─────────────

def test_chat_usage_event_does_not_count_as_extract(tmp_path, monkeypatch):
    """A chat call recorded with kind='chat' must NOT match the hourly-EXTRACT
    COUNT filter ('%extract%'), so heavy chat use can't trip the extracts/hour
    cap — while its EUR still counts toward the spend total."""
    _isolate(tmp_path, monkeypatch)
    resp = {"_meta": {"input_tokens": 3_000, "output_tokens": 400,
                      "model": "claude-opus-4-8"}}
    cost = db.record_usage("u1", resp, kind="chat")
    assert cost > 0
    spend, n_extracts = db.user_usage_since("u1", hours=1, kind_like="%extract%")
    assert n_extracts == 0     # chat is NOT an extract
    assert spend > 0           # but it DOES count toward EUR spend
    total_all, n_all = db.user_usage_since("u1", hours=1)
    assert n_all == 1          # the chat event exists in the ledger


def test_chat_path_is_self_metered_no_double_count(tmp_path, monkeypatch):
    """/chat-project is self-metered (records the actual after the call), so the
    conservative pre-charge reservation must be SKIPPED — otherwise chat is
    counted twice (reservation + actual), same rule as /extract-interior."""
    _isolate(tmp_path, monkeypatch)
    import main
    main._reserve_billable("u1", "/chat-project")
    _, n = db.user_usage_since("u1")
    assert n == 0  # no reservation — chat self-reports actuals like extract-interior

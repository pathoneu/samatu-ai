"""First reading pass: output cap and the one bounded retry on a cut-off answer.

Audit 2026-09-30 (vision-pipeline-4 / llm-api-4): the first pass asked for at
most 32,768 output tokens while the model thinks by default and spends most of
that on thinking, so rounds ended with stop_reason max_tokens and were thrown
away (2 of 3 rounds on one plan), which turned a three-round vote into one.

The cap is now 64,000 (billing is by actual use), the call stays streamed (the
installed SDK refuses a non-streamed request whose max_tokens implies a call
longer than ten minutes), and an answer still cut off at the new cap gets ONE
more try. Every attempt's usage is kept, cut off or not.

Stubbed clients only — no network, no Anthropic call.
"""
from __future__ import annotations

import json

import anthropic
import pytest

import pricing  # noqa: E402
from extractor import prompt, vision_call  # noqa: E402


class _Usage:
    def __init__(self, i, o, cr=0, cw=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = cr
        self.cache_creation_input_tokens = cw


class _Block:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text, stop_reason, usage):
        self.content = [_Block(text)]
        self.stop_reason = stop_reason
        self.usage = usage


class _Ctx:
    def __init__(self, resp):
        self._resp = resp

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self._resp


class _SeqClient:
    """Streams one prepared answer per call, in order; records every request.
    Has no `create`, so a non-streamed call would fail loudly."""

    def __init__(self, resps):
        self._resps = list(resps)
        self.requests: list[dict] = []

    def with_options(self, **_kw):
        return self

    @property
    def messages(self):
        return self

    def stream(self, **kw):
        self.requests.append(kw)
        return _Ctx(self._resps.pop(0))


_PAGES = [{"page_index": 1, "image_b64": "x"}]
_MODEL = "claude-opus-5"
_OK_TEXT = json.dumps({"patalpos": [{"nr": "1", "pavadinimas": "Kambarys"}]})


@pytest.fixture(autouse=True)
def _no_content_build(monkeypatch):
    monkeypatch.setattr(vision_call, "build_user_content", lambda pages: [])


def _run(resps):
    client = _SeqClient(resps)
    out = vision_call._run_pass1_once(client, [], _PAGES, model=_MODEL)
    return out, client


def test_first_pass_cap_is_64000_and_streamed():
    assert prompt.MAX_OUTPUT_TOKENS == 64_000
    out, client = _run([_Resp(_OK_TEXT, "end_turn", _Usage(100, 50))])
    assert out["patalpos"][0]["nr"] == "1"
    assert len(client.requests) == 1
    req = client.requests[0]
    assert req["max_tokens"] == 64_000
    # model API rules: no sampling parameters, effort unchanged
    assert not {"temperature", "top_p", "top_k"} & set(req)
    assert req["output_config"] == {"effort": "high"}


def test_installed_sdk_refuses_this_cap_without_streaming():
    """Why the pass must stay streamed: the SDK raises before sending."""
    c = anthropic.Anthropic(api_key="test-not-used")
    with pytest.raises(ValueError, match="Streaming is required"):
        c._calculate_nonstreaming_timeout(prompt.MAX_OUTPUT_TOKENS, None)


def test_cut_off_once_then_answered_keeps_both_usages():
    out, client = _run([
        _Resp('{"patalpos": [', "max_tokens", _Usage(40_000, 64_000, 1_000, 2_000)),
        _Resp(_OK_TEXT, "end_turn", _Usage(40_000, 20_000, 30_000, 0)),
    ])
    assert len(client.requests) == 2, "one more try after a cut-off answer"
    assert client.requests[1]["max_tokens"] == 64_000
    assert out.get("status") != "error"
    assert out["patalpos"][0]["nr"] == "1"
    meta = out["_meta"]
    # the round's usage is the SUM of both paid attempts
    assert meta["input_tokens"] == 80_000
    assert meta["output_tokens"] == 84_000
    assert meta["cache_read_tokens"] == 31_000
    assert meta["cache_write_tokens"] == 2_000
    assert meta["stop_reason"] == "end_turn"
    assert meta["truncated_attempts"] == [{
        "input_tokens": 40_000, "output_tokens": 64_000,
        "cache_read_tokens": 1_000, "cache_write_tokens": 2_000,
        "stop_reason": "max_tokens", "attempt": 1,
    }]


def test_cut_off_twice_stops_after_one_retry_and_keeps_both_usages():
    out, client = _run([
        _Resp('{"patalpos": [', "max_tokens", _Usage(40_000, 64_000)),
        _Resp('{"patalpos": [', "max_tokens", _Usage(40_000, 64_000)),
        _Resp(_OK_TEXT, "end_turn", _Usage(1, 1)),   # must never be asked for
    ])
    assert len(client.requests) == 2, "the retry is bounded to one"
    assert out["status"] == "error" and out["_error"] == "output_truncated"
    meta = out["_meta"]
    assert meta["input_tokens"] == 80_000
    assert meta["output_tokens"] == 128_000
    assert len(meta["truncated_attempts"]) == 1
    one = pricing.calc_claude_cost_usd(input_tokens=40_000, output_tokens=64_000, model=_MODEL)
    assert pricing.calc_claude_cost_usd(
        input_tokens=meta["input_tokens"], output_tokens=meta["output_tokens"],
        model=_MODEL) == pytest.approx(2 * one)


@pytest.mark.parametrize("stop_reason,text,error", [
    ("refusal", "", "model_refused"),
    ("end_turn", "tai ne JSON {{{", "json_decode_failure"),
])
def test_other_paid_errors_still_do_not_retry(stop_reason, text, error):
    out, client = _run([_Resp(text, stop_reason, _Usage(10, 10)),
                        _Resp(_OK_TEXT, "end_turn", _Usage(1, 1))])
    assert len(client.requests) == 1
    assert out["_error"] == error
    assert "truncated_attempts" not in out["_meta"]


def test_answer_without_cut_off_meta_unchanged():
    out, _ = _run([_Resp(_OK_TEXT, "end_turn", _Usage(100, 50, 7, 3))])
    assert out["_meta"] == {
        "input_tokens": 100, "output_tokens": 50,
        "cache_read_tokens": 7, "cache_write_tokens": 3,
        "stop_reason": "end_turn", "attempt": 1, "pages_sent": 1, "model": _MODEL,
    }


# ═══════════ the voting record shows each round's stop and retries ══════════

def _stub_rounds(monkeypatch, seq):
    seq = list(seq)
    monkeypatch.setattr(vision_call, "_run_pass1_once",
                        lambda *a, **k: json.loads(json.dumps(seq.pop(0))))


def _ok(extra_meta=None):
    meta = {"model": _MODEL, "input_tokens": 20_000, "output_tokens": 2_000,
            "cache_read_tokens": 0, "cache_write_tokens": 0, "stop_reason": "end_turn"}
    meta.update(extra_meta or {})
    return {"patalpos": [{"nr": "101", "pavadinimas": "Kambarys"}], "_meta": meta}


def test_voting_record_carries_stop_reason_and_retries(monkeypatch):
    monkeypatch.delenv("SAMATU_VOTING_MODELS", raising=False)
    retried = _ok({"input_tokens": 40_000, "output_tokens": 66_000,
                   "truncated_attempts": [{"input_tokens": 20_000, "output_tokens": 64_000,
                                           "cache_read_tokens": 0, "cache_write_tokens": 0,
                                           "stop_reason": "max_tokens", "attempt": 1}]})
    failed = {"status": "error", "_error": "output_truncated", "_stop_reason": "max_tokens",
              "_meta": {"model": _MODEL, "input_tokens": 40_000, "output_tokens": 128_000,
                        "cache_read_tokens": 0, "cache_write_tokens": 0,
                        "stop_reason": "max_tokens",
                        "truncated_attempts": [{"output_tokens": 64_000}]}}
    _stub_rounds(monkeypatch, [retried, _ok(), failed])
    out = vision_call._run_pass1_voted(object(), system=[], pages=_PAGES, n=3,
                                       _emit=lambda _e: None)
    rounds = out["_meta"]["voting_models"]
    assert [r.get("stop_reason") for r in rounds] == ["end_turn", "end_turn", "max_tokens"]
    assert [r.get("truncated_attempts", 0) for r in rounds] == [1, 0, 1]
    assert rounds[0]["output_tokens"] == 66_000
    assert rounds[2]["output_tokens"] == 128_000
    # the run-level meta must not present round 1's retry list as the run's
    assert "truncated_attempts" not in out["_meta"]
    ok_cost = pricing.calc_claude_cost_usd(input_tokens=40_000, output_tokens=66_000,
                                           model=_MODEL) \
        + pricing.calc_claude_cost_usd(input_tokens=20_000, output_tokens=2_000, model=_MODEL) \
        + pricing.calc_claude_cost_usd(input_tokens=40_000, output_tokens=128_000, model=_MODEL)
    assert pricing.calc_meta_cost_usd(out["_meta"]) == pytest.approx(ok_cost)


class _Boom(Exception):
    pass


def test_retry_that_errors_out_still_keeps_the_cut_off_usage(monkeypatch):
    """The cut-off attempt was billed even when every later try raises."""
    monkeypatch.setattr(vision_call.time, "sleep", lambda _s: None)
    first = [_Resp('{"patalpos": [', "max_tokens", _Usage(40_000, 64_000))]

    class _Client(_SeqClient):
        def stream(self, **kw):
            self.requests.append(kw)
            if first:
                return _Ctx(first.pop(0))
            raise _Boom("529 overloaded")

    client = _Client([])
    out = vision_call._run_pass1_once(client, [], _PAGES, model=_MODEL)
    assert out["status"] == "error" and out["_error"].startswith("vision_call_failed")
    assert len(client.requests) == 4          # 1 cut off + the usual 3 tries on errors
    assert out["_meta"]["model"] == _MODEL
    assert out["_meta"]["input_tokens"] == 40_000
    assert out["_meta"]["output_tokens"] == 64_000
    assert len(out["_meta"]["truncated_attempts"]) == 1


def test_errors_without_a_cut_off_keep_their_old_shape(monkeypatch):
    monkeypatch.setattr(vision_call.time, "sleep", lambda _s: None)

    class _Client(_SeqClient):
        def stream(self, **kw):
            self.requests.append(kw)
            raise _Boom("529 overloaded")

    out = vision_call._run_pass1_once(_Client([]), [], _PAGES, model=_MODEL)
    assert out == {"status": "error", "_error": "vision_call_failed: 529 overloaded"}

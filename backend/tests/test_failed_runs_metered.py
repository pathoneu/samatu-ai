"""Spend metering, direction 2 — tokens paid for by a FAILED extraction count.

Audit 2026-09-29 (llm-api-1 / data-ops-infra-3): a Pass-1 answer that was cut
off (stop_reason max_tokens), refused, or not parseable JSON was billed in full
by Anthropic, but the error dict carried no `_meta`, so db.record_usage wrote
nothing; an errored voting round kept only its error text; the stream endpoint
skipped metering on every error. The hourly and daily caps could not see any
of it. Success-path `_meta` must stay exactly as it was.

Stubbed clients only — no network, no Anthropic call.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import main  # noqa: E402
import db  # noqa: E402
import pricing  # noqa: E402
from extractor import vision_call  # noqa: E402


# ─────────────────────────── fakes (no network) ────────────────────────────

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


class _Client:
    def __init__(self, resp):
        self._resp = resp
        self.calls = 0

    def with_options(self, **_kw):
        return self

    @property
    def messages(self):
        return self

    def stream(self, **_kw):
        self.calls += 1
        return _Ctx(self._resp)


_PAGES = [{"page_index": 1, "image_b64": "x"}]
_MODEL = "claude-opus-4-8"


@pytest.fixture(autouse=True)
def _no_content_build(monkeypatch):
    monkeypatch.setattr(vision_call, "build_user_content", lambda pages: [])


def _once(resp):
    client = _Client(resp)
    out = vision_call._run_pass1_once(client, [], _PAGES, model=_MODEL)
    return out, client


# ═══════════════ Pass-1 error shapes carry the paid usage ═══════════════════

# A cut-off answer (max_tokens) now gets ONE bounded retry and keeps the usage
# of both attempts — covered in test_pass1_output_cap.py (audit 2026-09-30).
@pytest.mark.parametrize("stop_reason,text,error", [
    ("refusal", "", "model_refused"),
    ("end_turn", "tai ne JSON {{{", "json_decode_failure"),
])
def test_pass1_error_keeps_token_usage(stop_reason, text, error):
    out, client = _once(_Resp(text, stop_reason, _Usage(40_000, 32_768, 1_000, 2_000)))
    assert out["status"] == "error" and out["_error"] == error
    assert client.calls == 1, "a paid error shape must not retry"
    meta = out["_meta"]
    assert meta["input_tokens"] == 40_000
    assert meta["output_tokens"] == 32_768
    assert meta["cache_read_tokens"] == 1_000
    assert meta["cache_write_tokens"] == 2_000
    assert meta["model"] == _MODEL
    assert meta["stop_reason"] == stop_reason


def test_pass1_success_meta_unchanged():
    out, _ = _once(_Resp(json.dumps({"patalpos": []}), "end_turn", _Usage(100, 50, 7, 3)))
    assert out["_meta"] == {
        "input_tokens": 100, "output_tokens": 50,
        "cache_read_tokens": 7, "cache_write_tokens": 3,
        "stop_reason": "end_turn", "attempt": 1, "pages_sent": 1, "model": _MODEL,
    }
    assert out["patalpos"] == []


def test_record_usage_writes_a_row_for_a_truncated_run(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "failed_meter.db")
    db.init_schema()
    db._migrate_schema()
    out, _ = _once(_Resp("{", "max_tokens", _Usage(40_000, 32_768)))
    cost = db.record_usage("u1", out, kind="extract-interior-failed")
    assert cost > 0
    spend, n = db.user_usage_since("u1", hours=1, kind_like="%extract%")
    assert n == 1 and spend == pytest.approx(cost, abs=1e-3)


# ═══════════════ voting keeps the usage of errored rounds ═══════════════════

_ROUND = {"model": _MODEL, "input_tokens": 20_000, "output_tokens": 2_000,
          "cache_read_tokens": 0, "cache_write_tokens": 0}
_FAILED = {"status": "error", "_error": "output_truncated", "_stop_reason": "max_tokens",
           "_meta": {"model": _MODEL, "input_tokens": 20_000, "output_tokens": 32_768,
                     "cache_read_tokens": 0, "cache_write_tokens": 0}}


def _stub_rounds(monkeypatch, seq):
    seq = list(seq)
    monkeypatch.setattr(vision_call, "_run_pass1_once",
                        lambda *a, **k: json.loads(json.dumps(seq.pop(0))))


def _ok():
    return {"patalpos": [{"nr": "101", "pavadinimas": "Kambarys"}], "_meta": dict(_ROUND)}


def test_voted_run_prices_the_errored_round(monkeypatch):
    monkeypatch.delenv("SAMATU_VOTING_MODELS", raising=False)
    _stub_rounds(monkeypatch, [_FAILED, _ok(), _ok()])
    out = vision_call._run_pass1_voted(object(), system=[], pages=_PAGES, n=3,
                                       _emit=lambda _e: None)
    assert out.get("status") != "error"
    rounds = out["_meta"]["voting_models"]
    assert rounds[0]["error"] == "output_truncated"
    assert rounds[0]["output_tokens"] == 32_768
    ok_only = 2 * pricing.calc_claude_cost_usd(
        input_tokens=20_000, output_tokens=2_000, model=_MODEL)
    failed = pricing.calc_claude_cost_usd(
        input_tokens=20_000, output_tokens=32_768, model=_MODEL)
    assert pricing.calc_meta_cost_usd(out["_meta"]) == pytest.approx(ok_only + failed)


def test_all_rounds_failed_still_carries_usage(monkeypatch):
    monkeypatch.delenv("SAMATU_VOTING_MODELS", raising=False)
    _stub_rounds(monkeypatch, [_FAILED, _FAILED,
                               {"status": "error", "_error": "vision_call_failed: 529"}])
    out = vision_call._run_pass1_voted(object(), system=[], pages=_PAGES, n=3,
                                       _emit=lambda _e: None)
    assert out["status"] == "error" and out["_error"] == "all_voting_runs_failed"
    meta = out["_meta"]
    assert meta["input_tokens"] == 40_000
    assert meta["output_tokens"] == 65_536
    one = pricing.calc_claude_cost_usd(input_tokens=20_000, output_tokens=32_768, model=_MODEL)
    assert pricing.calc_meta_cost_usd(meta) == pytest.approx(2 * one)


# ═══════════════ both endpoints record the failed run ═══════════════════════

class _FakeUpload:
    def __init__(self, data: bytes, filename: str = "plan.pdf"):
        self._data = data
        self.filename = filename

    async def read(self):
        return self._data


class _FakeRequest:
    class _Client:
        host = "127.0.0.1"

    client = _Client()


_ERROR_RESULT = {"status": "error", "_error": "output_truncated",
                 "_meta": {"model": _MODEL, "input_tokens": 40_000,
                           "output_tokens": 32_768}}


def _endpoint_env(tmp_path, monkeypatch, user_id):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "failed_endpoint.db")
    db.init_schema()
    db._migrate_schema()
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": user_id})
    monkeypatch.setattr(main, "_check_user_quota", lambda uid: None)
    monkeypatch.setattr(main, "_check_trial_gate", lambda uid: None)
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)
    monkeypatch.setattr(main, "_client_key", lambda request: "127.0.0.1")
    monkeypatch.setattr(main, "_validate_pdf_upload", lambda b, n: {"page_count": 1})


def _kinds(user_id):
    with db._conn() as c:
        return [r["kind"] for r in c.execute(
            "SELECT kind FROM usage_events WHERE user_id = ? AND cost_eur > 0", (user_id,))]


def test_extract_interior_records_a_failed_run(tmp_path, monkeypatch):
    _endpoint_env(tmp_path, monkeypatch, "f1")
    import extractor
    monkeypatch.setattr(extractor, "extract_interior",
                        lambda pdf_bytes, overrides: json.loads(json.dumps(_ERROR_RESULT)))
    out = asyncio.run(main.extract_interior_endpoint(
        request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None))
    assert out["status"] == "error"
    assert _kinds("f1") == ["extract-interior-failed"]


def test_extract_interior_stream_records_a_failed_run(tmp_path, monkeypatch):
    _endpoint_env(tmp_path, monkeypatch, "f2")
    import extractor

    def _fake_stream(pdf_bytes, overrides):
        yield {"event": "started"}
        yield {"event": "error", "message": "output_truncated"}
        yield {"event": "done", "result": json.loads(json.dumps(_ERROR_RESULT))}
    monkeypatch.setattr(extractor, "extract_interior_stream", _fake_stream)

    async def _run():
        resp = await main.extract_interior_stream_endpoint(
            request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")],
            rules_override=None)
        return b"".join([chunk async for chunk in resp.body_iterator])
    body = asyncio.run(_run()).decode("utf-8")
    assert '"status": "error"' in body
    assert _kinds("f2") == ["extract-interior-stream-failed"]


def test_extract_interior_stream_success_kind_unchanged(tmp_path, monkeypatch):
    _endpoint_env(tmp_path, monkeypatch, "f3")
    import extractor
    ok = {"status": "ok", "patalpos": [], "_meta": dict(_ROUND)}

    def _fake_stream(pdf_bytes, overrides):
        yield {"event": "done", "result": ok}
    monkeypatch.setattr(extractor, "extract_interior_stream", _fake_stream)

    async def _run():
        resp = await main.extract_interior_stream_endpoint(
            request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")],
            rules_override=None)
        return b"".join([chunk async for chunk in resp.body_iterator])
    asyncio.run(_run())
    assert _kinds("f3") == ["extract-interior-stream"]


def test_failed_extraction_keeps_the_eksplikacija_prepass_cost(monkeypatch):
    """The eksplikacija pre-pass runs (and may be paid) before Pass-1; when
    Pass-1 then fails, its tokens ride on the error result too."""
    import anthropic
    from extractor import eksplikacija_reader
    monkeypatch.setattr(anthropic, "Anthropic", lambda **_k: object())
    monkeypatch.setattr(vision_call, "pdf_to_b64_images",
                        lambda _b, **_k: [{"page_index": 1, "image_b64": "x"}])
    eks_meta = {"model": _MODEL, "input_tokens": 5_000, "output_tokens": 800}
    monkeypatch.setattr(eksplikacija_reader, "read_eksplikacija", lambda _b, _c: {
        "patalpos": [], "schedule_tables": {"durys": [], "langai": []},
        "_meta": dict(eks_meta)})
    monkeypatch.setattr(vision_call, "_run_pass1_once",
                        lambda *a, **k: json.loads(json.dumps(_FAILED)))
    out = vision_call.extract_interior(b"%PDF-1.4 fake")
    assert out["status"] == "error"
    extra = out["_meta"]["extra_calls"]
    assert [(e["reader"], e["input_tokens"], e["output_tokens"]) for e in extra] == [
        ("eksplikacija", 5_000, 800)]

"""Spend metering, direction 3 — tokens a run already paid for count when it DIES.

Audit follow-up 2026-09-30 (llm-api-1 / data-ops-infra-3, the case the
2026-09-29 round left open): when extract_interior raised after Pass-1 or a
sub-reader had already been paid, the tokens were lost — stream.py queued a
bare error with no `_meta`, the stream endpoint's two `except Exception`
handlers and the orphan drain wrote nothing, the non-stream endpoint let the
exception escape unmetered, and db.record_usage dropped a result whose only
usage was `extra_calls` (all Pass-1 attempts raised, the room-table pre-pass
was paid). A successful run must still write exactly the rows it wrote before.

Stubbed clients only — no network, no Anthropic call.
"""
from __future__ import annotations

import asyncio
import io
import json
import time
import types

import pytest

import main  # noqa: E402  (main before auth — house idiom)
import db  # noqa: E402
import pricing  # noqa: E402
from extractor import vision_call  # noqa: E402


_MODEL = "claude-opus-4-8"
_EKS = {"model": _MODEL, "input_tokens": 5_000, "output_tokens": 800}
_ADJ = {"model": _MODEL, "input_tokens": 2_000, "output_tokens": 300}
_READER = {"model": _MODEL, "input_tokens": 3_000, "output_tokens": 400,
           "cache_read_tokens": 100, "cache_write_tokens": 50}


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
    """Every Pass-1 call answers the same paid, parseable JSON."""

    def __init__(self):
        self.calls = 0

    def with_options(self, **_kw):
        return self

    @property
    def messages(self):
        return self

    def stream(self, **_kw):
        self.calls += 1
        return _Ctx(_Resp(json.dumps({"patalpos": [
            {"nr": "101", "pavadinimas": "Kambarys", "puslapio_nr": 1}]}),
            "end_turn", _Usage(10_000, 1_000)))


class _FakeUpload:
    def __init__(self, data: bytes, filename: str = "plan.pdf"):
        self._data = data
        self.filename = filename

    async def read(self):
        return self._data


class _FakeRequest:
    class _C:
        host = "127.0.0.1"

    client = _C()


# ─────────────────────────── helpers ────────────────────────────────────────

def _endpoint_env(tmp_path, monkeypatch, user_id):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "dead_runs.db")
    db.init_schema()
    db._migrate_schema()
    monkeypatch.delenv("BILLING_ENABLED", raising=False)
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": user_id})
    monkeypatch.setattr(main, "_check_user_quota", lambda uid: None)
    monkeypatch.setattr(main, "_check_trial_gate", lambda uid: None)
    monkeypatch.setattr(main, "_check_rate_limit", lambda ip, ep: None)
    monkeypatch.setattr(main, "_client_key", lambda request: "127.0.0.1")
    monkeypatch.setattr(main, "_validate_pdf_upload", lambda b, n: {"page_count": 1})


def _rows(user_id):
    with db._conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT kind, input_tokens, output_tokens, cache_read_tokens, "
            "cache_write_tokens, extra_calls_cost_eur, cost_eur, model "
            "FROM usage_events WHERE user_id = ? ORDER BY created_at", (user_id,))]


def _cost_eur(*calls):
    return sum(pricing.calc_claude_cost_usd(
        input_tokens=c.get("input_tokens", 0), output_tokens=c.get("output_tokens", 0),
        cache_read_tokens=c.get("cache_read_tokens", 0),
        cache_write_tokens=c.get("cache_write_tokens", 0), model=c["model"])
        for c in calls) * 0.93


def _stream_body(**kw):
    async def _run():
        resp = await main.extract_interior_stream_endpoint(
            request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")],
            rules_override=None, **kw)
        return b"".join([chunk async for chunk in resp.body_iterator])
    return asyncio.run(_run()).decode("utf-8")


def _stub_pipeline_front(monkeypatch):
    """Real extract_interior up to Pass-1; the model client and the PDF
    rendering are fakes, the room-table pre-pass is paid."""
    import anthropic
    from extractor import eksplikacija_reader
    monkeypatch.setattr(anthropic, "Anthropic", lambda **_k: _Client())
    monkeypatch.setattr(vision_call, "pdf_to_b64_images",
                        lambda _b, **_k: [{"page_index": 1, "image_b64": "x"}])
    monkeypatch.setattr(vision_call, "build_user_content", lambda pages: [])
    monkeypatch.setenv("SAMATU_PDF_NATIVE", "0")
    monkeypatch.setattr(eksplikacija_reader, "read_eksplikacija", lambda _b, _c: {
        "patalpos": [], "schedule_tables": {"durys": [], "langai": []},
        "_meta": dict(_EKS)})


# ═══════════════ db.record_usage takes an extra_calls-only result ════════════

def test_record_usage_accepts_a_result_with_only_extra_calls(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "extra_only.db")
    db.init_schema()
    db._migrate_schema()
    res = {"status": "error", "_error": "vision_call_failed: 529",
           "_meta": {"extra_calls": [dict(_EKS, reader="eksplikacija"), dict(_READER)]}}
    cost = db.record_usage("x1", res, kind="extract-interior-failed")
    assert cost == pytest.approx(_cost_eur(_EKS, _READER))
    [row] = _rows("x1")
    assert row["kind"] == "extract-interior-failed"
    assert (row["input_tokens"], row["output_tokens"],
            row["cache_read_tokens"], row["cache_write_tokens"]) == (8_000, 1_200, 100, 50)
    assert row["model"] == _MODEL
    assert row["cost_eur"] == pytest.approx(round(cost, 4))
    assert row["extra_calls_cost_eur"] == pytest.approx(round(cost, 4))


def test_record_usage_still_skips_a_result_with_no_paid_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "nothing.db")
    db.init_schema()
    db._migrate_schema()
    assert db.record_usage("x2", {"status": "error", "_meta": {"extra_calls": []}}) == 0.0
    assert db.record_usage("x2", {"status": "error"}) == 0.0
    assert _rows("x2") == []


def test_all_pass1_attempts_raise_keeps_the_room_table_cost(tmp_path, monkeypatch):
    """Every Pass-1 attempt raised (no `_meta`), the pre-pass was paid: the
    error result carries it and the endpoint writes one failed row."""
    _endpoint_env(tmp_path, monkeypatch, "p1")
    _stub_pipeline_front(monkeypatch)
    monkeypatch.setenv("ENABLE_EXTRACTION_VOTING", "0")
    monkeypatch.setattr(vision_call, "_run_pass1_once", lambda *a, **k: {
        "status": "error", "_error": "vision_call_failed: 529"})
    out = asyncio.run(main.extract_interior_endpoint(
        request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None))
    assert out["status"] == "error"
    [row] = _rows("p1")
    assert row["kind"] == "extract-interior-failed"
    assert (row["input_tokens"], row["output_tokens"]) == (5_000, 800)
    assert row["cost_eur"] == pytest.approx(round(_cost_eur(_EKS), 4))


# ═══════════════ a run that pays, then raises ═══════════════════════════════

def _paid_then_raise(monkeypatch):
    """Real extract_interior with 3 PARALLEL voting rounds on the fake client
    (each paid), a paid adjacency reader, then the vote itself raises."""
    _stub_pipeline_front(monkeypatch)
    monkeypatch.setenv("ENABLE_EXTRACTION_VOTING", "1")
    monkeypatch.setenv("ENABLE_PARALLEL_VOTING", "1")
    monkeypatch.setenv("VOTING_N", "3")
    monkeypatch.delenv("SAMATU_VOTING_MODELS", raising=False)
    import extractor.vision.extraction_voter as ev

    def _boom(_runs):
        raise RuntimeError("vote blew up after everything was paid")
    monkeypatch.setattr(ev, "vote_extraction", _boom)


_PASS1 = {"model": _MODEL, "input_tokens": 10_000, "output_tokens": 1_000}
_PAID_SUM = (5_000 + 3 * 10_000, 800 + 3 * 1_000)   # no adjacency pass since v4 3b


def test_non_stream_run_that_raises_records_what_it_paid(tmp_path, monkeypatch):
    _endpoint_env(tmp_path, monkeypatch, "r1")
    _paid_then_raise(monkeypatch)
    with pytest.raises(RuntimeError, match="vote blew up"):
        asyncio.run(main.extract_interior_endpoint(
            request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")],
            rules_override=None))
    [row] = _rows("r1")
    assert row["kind"] == "extract-interior-failed"
    assert (row["input_tokens"], row["output_tokens"]) == _PAID_SUM
    assert row["cost_eur"] == pytest.approx(
        round(_cost_eur(_EKS, _PASS1, _PASS1, _PASS1), 4))


def test_stream_worker_exception_records_what_it_paid(tmp_path, monkeypatch):
    """stream.py's worker used to queue a bare {'status':'error'} — the paid
    tokens now ride on that done event and the endpoint meters them once."""
    _endpoint_env(tmp_path, monkeypatch, "r2")
    _paid_then_raise(monkeypatch)
    body = _stream_body()
    assert '"event": "done"' in body and '"status": "error"' in body
    [row] = _rows("r2")
    assert row["kind"] == "extract-interior-stream-failed"
    assert (row["input_tokens"], row["output_tokens"]) == _PAID_SUM


def _paying_stream(tail):
    """A stand-in stream that pays one reader call inside the run (reported the
    way every reader reports: through _append_extra_call), then `tail`."""
    from extractor import run_usage

    def _fake(pdf_bytes, overrides):
        usage = run_usage.current()

        def _gen():
            run_usage.run_with(usage, vision_call._append_extra_call, {}, dict(_READER))
            yield {"event": "started"}
            yield from tail()
        return _gen()
    return _fake


def _raises_on_next():
    raise RuntimeError("next(gen) blew up")
    yield  # pragma: no cover


def _unserialisable_event():
    yield {"event": "step", "bad": object()}   # json.dumps fails in the loop body


@pytest.mark.parametrize("tail", [_raises_on_next, _unserialisable_event],
                         ids=["inner_except", "outer_except"])
def test_stream_endpoint_exception_paths_record_what_was_paid(tmp_path, monkeypatch, tail):
    _endpoint_env(tmp_path, monkeypatch, "r3")
    import extractor
    monkeypatch.setattr(extractor, "extract_interior_stream", _paying_stream(tail))
    body = _stream_body()
    assert '"status": "error"' in body
    [row] = _rows("r3")
    assert row["kind"] == "extract-interior-stream-failed"
    assert (row["input_tokens"], row["output_tokens"],
            row["cache_read_tokens"], row["cache_write_tokens"]) == (3_000, 400, 100, 50)


def _dies_raising():
    time.sleep(0.6)
    raise RuntimeError("pipeline died")          # drain: "stream orphan drain failed"
    yield  # pragma: no cover


def _dies_silently():
    time.sleep(0.6)
    return                                       # drain: "no done event (pipeline died)"
    yield  # pragma: no cover


@pytest.mark.parametrize("_dies", [_dies_raising, _dies_silently],
                         ids=["drain_except", "no_done_event"])
def test_orphan_drain_records_a_run_that_died(tmp_path, monkeypatch, _dies):
    """Client gone mid-run, then the pipeline dies with no done event: the
    drain used to log and return. What was paid is metered, once."""
    _endpoint_env(tmp_path, monkeypatch, "r4")
    from starlette.requests import Request
    from fastapi import UploadFile

    import extractor
    monkeypatch.setattr(extractor, "extract_interior_stream", _paying_stream(_dies))
    monkeypatch.setattr(main.db, "upsert_project", lambda *a, **k: None)

    async def drive():
        scope = {"type": "http", "method": "POST", "path": "/extract-interior-stream",
                 "headers": [], "client": ("127.0.0.1", 1234), "query_string": b"",
                 "app": main.app, "scheme": "http", "server": ("t", 80)}
        req = Request(scope, receive=lambda: asyncio.sleep(3600))
        f = UploadFile(filename="objektas_a.pdf", file=io.BytesIO(b"%PDF-1.4\n" + b"x" * 400))
        resp = await main.extract_interior_stream_endpoint(req, files=[f], rules_override=None)
        it = resp.body_iterator
        assert b"recovery_id" in await it.__anext__()
        await it.__anext__()                 # "started" — the next step is now in flight
        try:
            await it.athrow(asyncio.CancelledError())
        except (asyncio.CancelledError, StopAsyncIteration):
            pass
        for _ in range(40):                  # the drain is detached
            if _rows("r4"):
                break
            await asyncio.sleep(0.25)

    asyncio.run(drive())
    [row] = _rows("r4")
    assert row["kind"] == "extract-interior-stream-failed"
    assert (row["input_tokens"], row["output_tokens"]) == (3_000, 400)


# ═══════════════ a successful run writes exactly what it wrote before ═══════
# Golden rows captured on the code BEFORE this change (HEAD 3778e4a): same
# kind, same token columns, same cost, one row — the tally the run keeps on the
# side must never add a second one.

_OK_META = {"model": _MODEL, "input_tokens": 40_000, "output_tokens": 6_000,
            "cache_read_tokens": 1_000, "cache_write_tokens": 2_000}


def _ok_result():
    res = {"status": "ok", "patalpos": [], "_meta": dict(_OK_META)}
    vision_call._append_extra_call(res, dict(_READER), reader="apdailos")
    return res


_GOLDEN_OK = {"input_tokens": 40_000, "output_tokens": 6_000, "cache_read_tokens": 1_000,
              "cache_write_tokens": 2_000, "extra_calls_cost_eur": 0.0236,
              "cost_eur": 0.3612, "model": _MODEL}


def test_successful_non_stream_run_rows_unchanged(tmp_path, monkeypatch):
    _endpoint_env(tmp_path, monkeypatch, "s1")
    import extractor
    monkeypatch.setattr(extractor, "extract_interior", lambda pdf_bytes, overrides: _ok_result())
    out = asyncio.run(main.extract_interior_endpoint(
        request=_FakeRequest(), files=[_FakeUpload(b"%PDF-1.4 fake")], rules_override=None))
    assert out["status"] == "ok"
    assert _rows("s1") == [{"kind": "extract-interior", **_GOLDEN_OK}]


def test_successful_stream_run_rows_unchanged(tmp_path, monkeypatch):
    _endpoint_env(tmp_path, monkeypatch, "s2")
    import extractor.stream as st
    monkeypatch.setattr(st, "extract_interior",
                        lambda pdf_bytes, overrides, progress_cb=None: _ok_result())
    body = _stream_body()
    assert '"status": "ok"' in body
    assert _rows("s2") == [{"kind": "extract-interior-stream", **_GOLDEN_OK}]


def test_done_row_then_loop_failure_writes_no_second_row(tmp_path, monkeypatch):
    """The done result is metered, THEN the loop body fails sending it: the
    outer handler must not add the tally on top of the row just written."""
    _endpoint_env(tmp_path, monkeypatch, "s3")
    import extractor.stream as st

    def _ok_but_unsendable(pdf_bytes, overrides, progress_cb=None):
        res = _ok_result()
        res["unsendable"] = object()             # json.dumps fails after metering
        return res
    monkeypatch.setattr(st, "extract_interior", _ok_but_unsendable)
    body = _stream_body()
    assert '"status": "error"' in body           # the stream still terminates
    assert _rows("s3") == [{"kind": "extract-interior-stream", **_GOLDEN_OK}]

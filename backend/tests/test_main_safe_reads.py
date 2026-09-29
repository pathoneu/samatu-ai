"""main.py's two old response reads (llm-api-3, 2026-09-29).

`_call_claude` (the quantity-schedule reading behind /extract) and
`_call_vision` (the facade / roof / earthworks / concrete readers) used to
return `msg.content[0].text`. On a model with thinking on, block 0 is often a
ThinkingBlock with no `.text`, so the read died INTERMITTENTLY:

  - /extract swallowed the error per window, so a multi-window KŽ came back
    with rows missing and nothing said about it;
  - `_run_vision_on_pages` retried the crash three times, each retry a paid
    call, and then dropped the page.

A refusal and an answer cut off at the token limit were read as ordinary
answers. These tests feed made-up SDK responses through the REAL
`_call_claude` / `_call_vision` (only the client is stubbed) — no API call.
"""
import asyncio
import json
import types

import pytest
from anthropic.types import TextBlock, ThinkingBlock
from fastapi.testclient import TestClient

import main  # noqa: E402
from main import app  # noqa: E402

import auth  # noqa: E402
import db  # noqa: E402

http = TestClient(app)

_ROW = {"nr": "1.1", "aprasymas": "Sienų dažymas", "mato_vnt": "m²",
        "kiekis": 10, "skyrius": "APDAILA"}
_ROW2 = {"nr": "2.1", "aprasymas": "Grindų klojimas", "mato_vnt": "m²",
         "kiekis": 20, "skyrius": "GRINDYS"}


def _msg(*blocks, stop_reason="end_turn"):
    return types.SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def _thinking():
    return ThinkingBlock(type="thinking", thinking="...", signature="sig")


def _text(s):
    return TextBlock(type="text", text=s)


class _StubClient:
    """Stands in for main.client; hands out scripted responses in order."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = 0
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls += 1
        return self._responses.pop(0)


@pytest.fixture(autouse=True)
def _hermetic_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "safe_reads.db")
    db.init_schema()
    db._migrate_schema()
    auth._ensure_dev_user()
    yield


# ── _call_claude ────────────────────────────────────────────────────────────

def test_call_claude_reads_text_after_a_thinking_block(monkeypatch):
    # OLD: AttributeError 'ThinkingBlock' object has no attribute 'text'.
    monkeypatch.setattr(main, "client", _StubClient(
        _msg(_thinking(), _text('[{"a": 1}]'))))
    assert main._call_claude("p") == '[{"a": 1}]'


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_call_claude_reports_refusal_and_cut_off(monkeypatch, stop):
    # OLD: returned whatever text there was, as if it were a finished answer.
    monkeypatch.setattr(main, "client", _StubClient(
        _msg(_thinking(), _text("[{"), stop_reason=stop)))
    with pytest.raises(main._UnfinishedAnswer) as exc:
        main._call_claude("p")
    assert exc.value.stop_reason == stop
    assert exc.value.text == "[{"


def test_call_claude_ordinary_answer_unchanged(monkeypatch):
    monkeypatch.setattr(main, "client", _StubClient(_msg(_text("[]"))))
    assert main._call_claude("p") == "[]"


# ── _call_vision + _run_vision_on_pages ─────────────────────────────────────

def test_call_vision_reads_text_after_a_thinking_block(monkeypatch):
    monkeypatch.setattr(main, "client", _StubClient(
        _msg(_thinking(), _text('{"plotis": 12}'))))
    assert main._call_vision("b64", "p") == '{"plotis": 12}'


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_call_vision_reports_refusal_and_cut_off(monkeypatch, stop):
    monkeypatch.setattr(main, "client", _StubClient(
        _msg(_text('{"plotis": 1'), stop_reason=stop)))
    with pytest.raises(main._UnfinishedAnswer) as exc:
        main._call_vision("b64", "p")
    assert exc.value.stop_reason == stop


def _run_pages(monkeypatch, stub):
    monkeypatch.setattr(main, "client", stub)
    monkeypatch.setattr(main, "_pdf_to_images", lambda b: [(1, "b64")])

    async def _no_sleep(_s):
        return None
    monkeypatch.setattr(main.asyncio, "sleep", _no_sleep)
    return asyncio.run(main._run_vision_on_pages(b"%PDF", None, "prompt"))


def test_vision_pages_thinking_first_is_read_once(monkeypatch):
    # OLD: three paid calls, all crashing, then the page was dropped.
    stub = _StubClient(_msg(_thinking(), _text('{"plotis": 12}')))
    assert _run_pages(monkeypatch, stub) == [{"plotis": 12}]
    assert stub.calls == 1


@pytest.mark.parametrize("stop", ["refusal", "max_tokens"])
def test_vision_pages_refusal_and_cut_off_are_not_retried_or_used(monkeypatch, stop):
    # A refused or cut-off page is not a result, and asking again sends the
    # same input for the same answer — so one call, page dropped.
    stub = _StubClient(_msg(_text('{"plotis": 12}'), stop_reason=stop),
                       _msg(_text('{"plotis": 12}'), stop_reason=stop),
                       _msg(_text('{"plotis": 12}'), stop_reason=stop))
    assert _run_pages(monkeypatch, stub) == []
    assert stub.calls == 1


def test_vision_pages_ordinary_answer_unchanged(monkeypatch):
    stub = _StubClient(_msg(_text('{"plotis": 12}')))
    assert _run_pages(monkeypatch, stub) == [{"plotis": 12}]
    assert stub.calls == 1


# ── /extract (quantity schedule, Path 2) ────────────────────────────────────

def _patch_extract(monkeypatch, stub, chunks):
    monkeypatch.setattr(main, "_billable_user", lambda request: {"id": "u1"})
    monkeypatch.setattr(main, "_validate_pdf_upload", lambda b, n: {"page_count": 9})
    monkeypatch.setattr(main, "_extract_kz_direct", lambda b: None)  # force path 2
    monkeypatch.setattr(main, "_pdf_to_chunks", lambda b: ("Testas", chunks))
    monkeypatch.setattr(main, "client", stub)


def _post_extract():
    r = http.post("/extract", files={"file": ("kz.pdf", b"%PDF-1.4 fake",
                                              "application/pdf")})
    assert r.status_code == 200, r.text
    return r.json()


_TWO_CHUNKS = [{"text": "chunk one", "pages": "1-5"},
               {"text": "chunk two", "pages": "6-7"}]


def test_extract_thinking_first_keeps_every_row(monkeypatch):
    # OLD: each thinking-first window crashed and its rows silently vanished.
    _patch_extract(monkeypatch, _StubClient(
        _msg(_thinking(), _text(json.dumps([_ROW]))),
        _msg(_thinking(), _text(json.dumps([_ROW2])))), _TWO_CHUNKS)
    body = _post_extract()
    assert [e["aprasymas"] for e in body["eilutes"]] == [
        "Sienų dažymas", "Grindų klojimas"]
    assert body["meta"]["failed_windows"] == 0
    assert "warnings" not in body


def test_extract_refused_window_is_counted_and_warned(monkeypatch):
    _patch_extract(monkeypatch, _StubClient(
        _msg(_text("Negaliu padėti."), stop_reason="refusal"),
        _msg(_text(json.dumps([_ROW2])))), _TWO_CHUNKS)
    body = _post_extract()
    assert [e["aprasymas"] for e in body["eilutes"]] == ["Grindų klojimas"]
    assert body["meta"]["failed_windows"] == 1
    msgs = [w["message"] for w in body["warnings"]]
    assert len(msgs) == 1
    assert "5 psl." in msgs[0] and "1–5" in msgs[0], msgs[0]
    assert body["warnings"][0]["level"] == "WARN"


def test_extract_cut_off_window_keeps_complete_rows_and_warns(monkeypatch):
    # A cut-off answer still carries the rows it finished — keep those, but
    # say that the rest of those pages was not read.
    cut = json.dumps([_ROW])[:-1] + ', {"nr": "1.2", "apras'
    _patch_extract(monkeypatch, _StubClient(
        _msg(_text(json.dumps([_ROW2]))),
        _msg(_thinking(), _text(cut), stop_reason="max_tokens")), _TWO_CHUNKS)
    body = _post_extract()
    assert [e["aprasymas"] for e in body["eilutes"]] == [
        "Grindų klojimas", "Sienų dažymas"]
    assert body["meta"]["failed_windows"] == 0
    msgs = [w["message"] for w in body["warnings"]]
    assert len(msgs) == 1
    assert "2 psl." in msgs[0] and "6–7" in msgs[0], msgs[0]


def test_extract_uses_the_real_page_numbers_when_known(monkeypatch):
    # A large PDF sends only its quantity-schedule pages, so a chunk labelled
    # "3-17" may hold five pages. Count those, not the label's span.
    chunks = [{"text": "big", "pages": "3-17", "page_nums": [3, 4, 9, 16, 17]},
              {"text": "ok", "pages": "18-18", "page_nums": [18]}]
    _patch_extract(monkeypatch, _StubClient(
        _msg(_text(""), stop_reason="refusal"),
        _msg(_text(json.dumps([_ROW])))), chunks)
    msg = _post_extract()["warnings"][0]["message"]
    assert "5 psl." in msg and "3–4, 9, 16–17" in msg, msg


def test_extract_ordinary_answer_gives_the_same_result_as_before(monkeypatch):
    _patch_extract(monkeypatch, _StubClient(
        _msg(_text(json.dumps([_ROW]))),
        _msg(_text(json.dumps([_ROW2])))), _TWO_CHUNKS)
    body = _post_extract()
    assert set(body) == {"projektas", "eilutes", "meta"}
    assert body["projektas"] == "Testas"
    assert body["meta"] == {
        "total_pages": 7, "chunks_processed": 2, "chunks_with_data": 2,
        "windows_total": 2, "failed_windows": 0, "extraction_method": "claude",
        "extraction_model": main.model_for("extraction"),
    }
    assert [(e["nr"], e["aprasymas"], e["kiekis"], e["skyrius"])
            for e in body["eilutes"]] == [
        ("1.1", "Sienų dažymas", 10, "APDAILA"),
        ("2.1", "Grindų klojimas", 20, "GRINDYS")]


def test_no_main_reader_reads_content_zero_text():
    """The extractor-package guard (test_thinking_block_safety) never looked
    at main.py, which is how these two reads survived."""
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "main.py").read_text(
        encoding="utf-8")
    assert "content[0].text" not in src

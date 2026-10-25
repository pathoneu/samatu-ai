"""Readers recognise a refused or cut-off answer (2026-09-30).

The paid read of objektas_g left every room's doors unread: the doors request
came back with stop_reason "refusal", no content blocks, 5,497 input tokens
billed and 0 output, stop details category "reasoning_extraction". The doors
reader never looked at stop_reason, so the refusal surfaced only as "no JSON
in response" and its billed input tokens were never recorded.

Every reader call covered here must now:
  * return (or raise) its existing error shape with a clear `_error`
    ("refused:<category>" or "cut_off"),
  * carry the call's usage in `_meta` so the spend tally counts it,
  * never retry a refusal,
  * return exactly what it returned before on a normal answer.

No Anthropic API call is made: every client below is a stub.
"""
from __future__ import annotations

import base64
import io
import json
import types

import pytest

from extractor.response_text import ModelStopped, read_answer, stop_error


# ── stubs ─────────────────────────────────────────────────────────────────────

def _usage(i=5497, o=0):
    return types.SimpleNamespace(input_tokens=i, output_tokens=o)


def _refusal(category="reasoning_extraction"):
    details = (types.SimpleNamespace(category=category, type="refusal")
               if category else None)
    return types.SimpleNamespace(content=[], stop_reason="refusal",
                                 stop_details=details, usage=_usage())


def _cut_off(text='{"doors": [{"id": "d1"'):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="text", text=text)],
        stop_reason="max_tokens", stop_details=None, usage=_usage(900, 16384))


def _ok(text):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="thinking", thinking="..."),
                 types.SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn", stop_details=None, usage=_usage(1200, 300))


class _CreateClient:
    """messages.create stub returning the queued responses in order."""
    def __init__(self, *responses):
        self._queue = list(responses)
        self.calls = 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        return self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]


class _StreamClient:
    """messages.stream stub (context manager with get_final_message)."""
    def __init__(self, resp):
        self._resp = resp
        self.calls = 0
        self.messages = self

    def stream(self, **kw):
        self.calls += 1
        resp = self._resp

        class _Ctx:
            def __enter__(self_inner):
                return types.SimpleNamespace(get_final_message=lambda: resp)

            def __exit__(self_inner, *a):
                return False
        return _Ctx()


def _png_b64() -> str:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


# ── the shared helper ─────────────────────────────────────────────────────────

def test_stop_error_names_refusal_category_and_cut_off():
    assert stop_error(_refusal()) == "refused:reasoning_extraction"
    assert stop_error(_refusal(category=None)) == "refused"
    assert stop_error(_cut_off()) == "cut_off"
    assert stop_error(_ok("{}")) is None
    # stubs without the attribute, and MagicMock-ish objects, read as normal
    assert stop_error(types.SimpleNamespace(content=[])) is None
    from unittest.mock import MagicMock
    assert stop_error(MagicMock()) is None


def test_read_answer_logs_one_line_and_returns_no_text(capsys):
    text, err = read_answer(_refusal(), reader="doors_reader", page=2)
    assert (text, err) == ("", "refused:reasoning_extraction")
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    assert "doors_reader" in out[0] and "2" in out[0] and "reasoning_extraction" in out[0]

    text, err = read_answer(_ok('{"a": 1}'), reader="doors_reader", page=2)
    assert (text, err) == ('{"a": 1}', None)
    assert capsys.readouterr().out == ""


def test_model_stopped_is_a_value_error_carrying_meta():
    exc = ModelStopped("cut_off", {"model": "m", "input_tokens": 1})
    assert isinstance(exc, ValueError)
    assert exc.error == "cut_off" and exc._meta["input_tokens"] == 1


# v4 3c-2 (2026-10-25): the doors, door-type, fixture, apdailos, material-spec, page-classifier and schedule readers
# no longer call a model on an image (deleted, or reduced to the text layer + text/schema_llm.py); their refusal /
# cut-off tests went with them. text/schema_llm.py's own stop handling is in tests/test_text_first_readers_2026_10_25.py.

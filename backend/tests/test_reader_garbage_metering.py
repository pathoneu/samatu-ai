"""A billed call stays billed whatever its answer says (2026-10-05).

The golden-replay mutation check found it: the doors reader, the door-type
reader and the sanitary fixture reader returned WITHOUT `_meta` when the
model's answer held no JSON or broken JSON, so the call vanished from
`_meta.extra_calls` and from the run's usage metering — tokens paid for and
never counted. The doors reader also raised on an answer with unusable counts
(„total_count": "12+"), which lost every sheet's doors and every sheet's call.

Each test feeds a garbage answer and asserts exactly ONE metered call per model
call, through the same path the extraction uses (`_reader_call_metas` →
`_append_extra_call`), in `_meta.extra_calls` and in the run's side tally
(`run_usage`, what a run that dies is billed from). No Anthropic API call is
made: every client is a stub.
"""
from __future__ import annotations

import types

import pytest

from extractor import run_usage
from extractor.vision_call import _append_extra_call, _reader_call_metas

_USAGE = {"input_tokens": 4321, "output_tokens": 210}
_META = {"model": "claude-test", **_USAGE}

GARBAGE = {
    "no_json": "Atsiprašau, šiame lape durų nematau.",
    "broken_json": '{"doors": [{"id": "d1", "between": ["01" "02"]}], "total_count": 1',
}


def _answer(text: str):
    return types.SimpleNamespace(
        content=[types.SimpleNamespace(type="thinking", thinking="..."),
                 types.SimpleNamespace(type="text", text=text)],
        stop_reason="end_turn", stop_details=None,
        usage=types.SimpleNamespace(**_USAGE))


class _Client:
    """messages.create stub answering every call with the same response."""

    def __init__(self, text: str):
        self._resp = _answer(text)
        self.calls = 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        return self._resp


def _billed(calls: list[dict]) -> list[tuple]:
    return [(c["model"], c["input_tokens"], c["output_tokens"]) for c in calls]


def _metered(result: dict) -> list[dict]:
    """What the extraction would bill for this reader result: its `extra_calls`
    rows, which the run's side tally must count call for call."""
    parsed: dict = {}
    tally = run_usage.RunUsage()
    for m in _reader_call_metas(result):
        run_usage.run_with(tally, _append_extra_call, parsed, m, reader="test")
    calls = (parsed.get("_meta") or {}).get("extra_calls") or []
    assert _billed(tally.meta().get("extra_calls") or []) == _billed(calls)
    return calls


# v4 3c-2 (2026-10-25): the doors, door-type and fixture readers no longer call a model (deleted or read the
# text layer) — their metering tests went with them.

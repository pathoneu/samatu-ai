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


# ── doors_reader ──────────────────────────────────────────────────────────────

@pytest.fixture
def doors(monkeypatch):
    from extractor import doors_reader as m
    monkeypatch.setattr(m, "_render_page_b64", lambda pdf, page, dpi=220: "AAAA")
    monkeypatch.setattr(m, "model_for", lambda role: "claude-test")
    return m


_ROOMS = [{"nr": "01", "pavadinimas": "Holas", "plotas_m2": 5.0, "puslapio_nr": 2},
          {"nr": "02", "pavadinimas": "Vonia", "plotas_m2": 4.0, "puslapio_nr": 3}]


@pytest.mark.parametrize("kind", sorted(GARBAGE))
def test_doors_garbage_answer_is_one_metered_call(doors, kind):
    client = _Client(GARBAGE[kind])
    out = doors.read_doors_from_plan(b"%PDF", _ROOMS[:1], client=client, page=2)
    assert client.calls == 1
    assert out["status"] == "error" and out["doors"] == [] and out["total_count"] == 0
    assert out["_meta"] == _META
    assert _billed(_metered(out)) == [("claude-test", 4321, 210)]


@pytest.mark.parametrize("answer", [
    '{"doors": [], "total_count": "12+"}',               # a count that is not a number
    '{"doors": ["d1", "d2"], "exterior_count": null}',   # doors that are not objects
])
def test_doors_unusable_counts_are_an_error_not_a_crash(doors, answer):
    out = doors.read_doors_from_plan(b"%PDF", _ROOMS[:1], client=_Client(answer), page=2)
    assert out["status"] == "error" and out["_error"].startswith("unusable answer")
    assert _billed(_metered(out)) == [("claude-test", 4321, 210)]


def test_doors_one_garbage_sheet_keeps_the_other_sheet_and_both_calls(doors):
    """Two plan sheets, the first answer unusable: the second sheet's doors still
    merge, and both calls are billed — the raise used to lose both."""
    good = ('{"doors": [{"id": "d1", "tipas": "standart", "between": ["02", "exterior"]}], '
            '"total_count": 1, "interior_count": 0, "exterior_count": 1}')

    class _TwoAnswers(_Client):
        def __init__(self):
            super().__init__(good)
            self._first = _answer('{"doors": [], "total_count": "daug"}')

        def create(self, **kw):
            self.calls += 1
            return self._first if self.calls == 1 else self._resp

    client = _TwoAnswers()
    res = doors.read_doors_from_plan_pages(b"%PDF", _ROOMS, client=client)
    assert client.calls == 2
    assert res["status"] == "ok" and res["pages_read"] == [3] and res["pages_unread"] == [2]
    assert res["total_count"] == 1
    assert _billed(_metered(res)) == [("claude-test", 4321, 210)] * 2


@pytest.mark.parametrize("kind", sorted(GARBAGE))
def test_doors_pages_bill_the_garbage_sheet(doors, kind):
    res = doors.read_doors_from_plan_pages(b"%PDF", _ROOMS[:1], client=_Client(GARBAGE[kind]))
    assert res["status"] == "error" and res["pages_unread"] == [2]
    assert _billed(_metered(res)) == [("claude-test", 4321, 210)]


# ── door_type_reader ──────────────────────────────────────────────────────────

@pytest.fixture
def door_types(monkeypatch):
    from extractor import door_type_reader as m
    monkeypatch.setattr(m, "_render_page_b64", lambda pdf, page, *a, **k: "AAAA")
    monkeypatch.setattr(m, "_find_door_pages", lambda *a, **k: [3])
    monkeypatch.setattr(m, "model_for", lambda role: "claude-test")
    return m


@pytest.mark.parametrize("kind", sorted(GARBAGE))
def test_door_types_garbage_answer_is_one_metered_call(door_types, kind):
    client = _Client(GARBAGE[kind])
    out = door_types.read_door_types(b"%PDF", [], [{"nr": 3, "tipas": "floor_plan"}], client=client)
    assert client.calls == 1
    assert out["status"] == "error" and out["beapvadines_count"] == 0
    assert out["_meta"] == _META
    assert _billed(_metered(out)) == [("claude-test", 4321, 210)]


@pytest.mark.parametrize("kind", sorted(GARBAGE))
def test_voted_door_types_bill_every_garbage_round(door_types, kind):
    client = _Client(GARBAGE[kind])
    out = door_types.read_door_types_voted(b"%PDF", [], [{"nr": 3, "tipas": "floor_plan"}],
                                           client=client, n=3)
    assert client.calls == 3                     # garbage is not a refusal: every vote runs
    assert out["status"] == "error"
    assert _billed(_metered(out)) == [("claude-test", 4321, 210)] * 3


def test_voted_door_types_bill_the_garbage_round_beside_the_good_ones(door_types):
    ok = _answer('{"doors": [], "beapvadines_count": 2}')
    bad = _answer(GARBAGE["no_json"])

    class _Mixed(_Client):
        def create(self, **kw):
            self.calls += 1
            return bad if self.calls == 2 else ok

    client = _Mixed("")
    out = door_types.read_door_types_voted(b"%PDF", [], [{"nr": 3, "tipas": "floor_plan"}],
                                           client=client, n=3)
    assert client.calls == 3 and out["status"] == "ok" and out["beapvadines_count"] == 2
    assert _billed(_metered(out)) == [("claude-test", 4321, 210)] * 3


# ── sanitary_fixture_reader ───────────────────────────────────────────────────

@pytest.fixture
def fixtures(monkeypatch):
    from extractor import sanitary_fixture_reader as m
    monkeypatch.setattr(m, "_render_page_b64", lambda pdf, page, *a, **k: "AAAA")
    monkeypatch.setattr(m, "_find_sanitary_pages", lambda *a, **k: [3])
    monkeypatch.setattr(m, "model_for", lambda role: "claude-test")
    return m


@pytest.mark.parametrize("kind", sorted(GARBAGE))
def test_fixtures_garbage_answer_is_one_metered_call(fixtures, kind):
    client = _Client(GARBAGE[kind])
    out = fixtures.read_fixtures(b"%PDF", [], client, [{"nr": 3, "tipas": "plumbing"}])
    assert client.calls == 1
    assert out["status"] == "error"
    assert out["_meta"] == _META
    assert _billed(_metered(out)) == [("claude-test", 4321, 210)]


@pytest.mark.parametrize("kind", sorted(GARBAGE))
def test_voted_fixtures_bill_every_garbage_round(fixtures, kind):
    client = _Client(GARBAGE[kind])
    out = fixtures.read_fixtures_voted(b"%PDF", [], client, n=3,
                                       pages_meta=[{"nr": 3, "tipas": "plumbing"}])
    assert client.calls == 3
    assert out["status"] == "error"
    assert _billed(_metered(out)) == [("claude-test", 4321, 210)] * 3

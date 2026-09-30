"""Reading text out of a thinking-enabled response (2026-07-29).

Regression test for a live production failure. `resp.content[0].text` is
wrong whenever the model emits a thinking block first — `.text` does not
exist on it, so the reader raised
`'ThinkingBlock' object has no attribute 'text'` and died.

Observed on objektas_a: the apdailos (išklotinių) reader crashed mid-run, every
room fell back to paskirtis defaults, the garažas walls (31.45 m² of real
paint) vanished from the total and `Sienų dažomas plotas` came in 31% low.
It is intermittent — the previous run of the same PDF was fine — so nothing
but a type filter makes it reliable.
"""
from __future__ import annotations

import pytest

from extractor.response_text import response_text


class _Block:
    def __init__(self, type_, text=None):
        self.type = type_
        if text is not None:
            self.text = text


class _Thinking:
    """A thinking block as the SDK returns it: no `.text` attribute at all,
    so any attribute access on it raises rather than returning None."""
    type = "thinking"

    def __init__(self, thinking=""):
        self.thinking = thinking


class _Resp:
    def __init__(self, content):
        self.content = content


def test_thinking_block_first_does_not_raise():
    """THE bug. content[0] is a ThinkingBlock; the text is in block 1."""
    resp = _Resp([_Thinking("hmm, which page is the išklotinė..."),
                  _Block("text", '{"patalpos": []}')])
    assert response_text(resp) == '{"patalpos": []}'


def test_plain_text_first_still_works():
    """The old happy path must be byte-identical, or this 'fix' is a change."""
    resp = _Resp([_Block("text", '{"ok": 1}')])
    assert response_text(resp) == '{"ok": 1}'


def test_multiple_text_blocks_are_concatenated():
    """A long JSON answer can arrive split across blocks. The old
    content[0].text silently truncated it to the first fragment."""
    resp = _Resp([_Thinking(), _Block("text", '{"a":'), _Block("text", ' 1}')])
    assert response_text(resp) == '{"a": 1}'


def test_non_text_blocks_are_skipped():
    resp = _Resp([_Thinking(), _Block("tool_use"), _Block("text", "x"),
                  _Block("redacted_thinking")])
    assert response_text(resp) == "x"


@pytest.mark.parametrize("resp", [
    _Resp([]),
    _Resp(None),
    _Resp([_Thinking()]),          # thinking only, no answer
    object(),                       # no .content at all
])
def test_no_text_returns_empty_string_never_raises(resp):
    """Callers treat "" as 'reader produced nothing' and degrade with an
    explicit warning. Raising instead would take down the whole extraction."""
    assert response_text(resp) == ""


def test_untyped_block_with_text_is_still_read():
    """Backward compatibility: `content[0].text` did not care about `.type`,
    so neither may this. A block that carries text but declares no type is
    read when nothing better exists — the swap must never read LESS than the
    code it replaced."""
    class _Untyped:
        text = '{"doors": []}'
    assert response_text(_Resp([_Untyped()])) == '{"doors": []}'


def test_typed_text_wins_over_untyped():
    """When a proper text block exists, untyped stragglers are ignored."""
    class _Untyped:
        text = "ignore me"
    resp = _Resp([_Thinking(), _Untyped(), _Block("text", "real answer")])
    assert response_text(resp) == "real answer"


def test_malformed_block_is_skipped_not_fatal():
    """A block claiming type=text but carrying no usable text must not kill
    the read — losing one block beats losing the whole answer."""
    bad = _Block("text")            # type says text, attribute missing
    resp = _Resp([bad, _Block("text", "good")])
    assert response_text(resp) == "good"

    weird = _Block("text", 42)      # non-string text
    assert response_text(_Resp([weird, _Block("text", "ok")])) == "ok"


def test_interior_readers_all_use_the_safe_path():
    """The four readers that run during an interior extraction must not
    reintroduce `content[0].text`. This is the check that keeps the bug from
    spreading back by copy-paste."""
    import inspect
    from extractor import (apdailos_reader, door_type_reader, doors_reader,
                           sanitary_fixture_reader)
    for mod in (apdailos_reader, doors_reader, door_type_reader,
                sanitary_fixture_reader):
        src = inspect.getsource(mod)
        assert "content[0].text" not in src, (
            f"{mod.__name__} reads content[0].text — it will crash on any "
            f"response that starts with a thinking block")
        # read_answer() (2026-09-30) reads text through response_text() and
        # also names a refused / cut-off answer — either is the safe path.
        assert "response_text(resp)" in src or "read_answer(resp" in src, (
            f"{mod.__name__} should extract text via response_text() or read_answer()")

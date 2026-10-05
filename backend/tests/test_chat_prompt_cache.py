"""/chat-project prompt caching — the call-shape contract (2026-07-28).

OLD: system was a plain string and the ~29k-token project context a plain
string content — NO cache breakpoints, so every question re-sent both at full
price (~€0.14/question measured in the 4B interrogation: 72 calls, 2.14M input
tokens, ~$10.96). NEW: the system prompt and the context block each carry
cache_control ephemeral (2 of the 4 allowed breakpoints); history and the
current question stay AFTER the cached prefix so they never invalidate it.

No network calls — client.messages.create is stubbed and its kwargs captured.
"""
import types

import pytest
from fastapi.testclient import TestClient

import main  # noqa: E402  (main before auth — house idiom)
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _own_database(tmp_path, monkeypatch):
    """`with TestClient(app)` runs the app's startup: it marks other boots' running extractions interrupted
    and prunes held re-reads. Until 2026-10-05 that ran against backend/data/samatu.db — a dev server's live
    read could be marked interrupted by a test run."""
    monkeypatch.setattr(main.db, "_DB_PATH", tmp_path / "chat.db")
    main.db.init_schema()
    main.db._migrate_schema()


class _StubUsage:
    input_tokens = 10
    output_tokens = 5
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


def _stub_response():
    block = types.SimpleNamespace(text="Atsakymas.")
    return types.SimpleNamespace(content=[block], usage=_StubUsage())


def _capture_call(monkeypatch):
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return _stub_response()

    monkeypatch.setattr(main.client.messages, "create", fake_create)
    # Keep the dev DB untouched — metering is not under test here.
    monkeypatch.setattr(main.db, "record_usage", lambda *a, **k: None)
    return captured


def _ask(payload):
    with TestClient(app) as tc:
        r = tc.post("/chat-project", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    return body


def test_system_prompt_is_a_cached_block(monkeypatch):
    captured = _capture_call(monkeypatch)
    _ask({"project_context": {"name": "T", "patalpos": []}, "question": "Kiek patalpų?"})

    system = captured["system"]
    assert isinstance(system, list) and len(system) == 1
    blk = system[0]
    assert blk["type"] == "text"
    assert blk["text"] == main._CHAT_SYSTEM_PROMPT
    assert blk["cache_control"] == {"type": "ephemeral"}


def test_context_turn_is_the_only_cached_message(monkeypatch):
    captured = _capture_call(monkeypatch)
    _ask({
        "project_context": {"name": "T", "patalpos": []},
        "messages": [
            {"role": "user", "content": "ankstesnis klausimas"},
            {"role": "assistant", "content": "ankstesnis atsakymas"},
        ],
        "question": "Kiek patalpų?",
    })

    msgs = captured["messages"]
    # First turn: context as a block list with the breakpoint.
    ctx = msgs[0]
    assert ctx["role"] == "user"
    assert isinstance(ctx["content"], list) and len(ctx["content"]) == 1
    assert ctx["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert ctx["content"][0]["text"].startswith("Projekto duomenys:")

    # History + current question come AFTER the breakpoint, as plain strings —
    # a cache_control there would invalidate the prefix every turn.
    assert [m["content"] for m in msgs[2:]] == [
        "ankstesnis klausimas", "ankstesnis atsakymas", "Kiek patalpų?",
    ]
    for m in msgs[1:]:
        assert isinstance(m["content"], str)


def test_breakpoint_budget_stays_at_two(monkeypatch):
    """The API allows at most 4 cache_control breakpoints per request; the
    chat uses exactly 2 (system + context) so future additions have headroom
    and a refactor can't silently blow the limit."""
    captured = _capture_call(monkeypatch)
    _ask({"project_context": {"name": "T", "patalpos": []}, "question": "Labas"})

    n = len(captured["system"])  # 1 system block
    for m in captured["messages"]:
        if isinstance(m["content"], list):
            n += sum(1 for b in m["content"] if "cache_control" in b)
    assert n == 2
